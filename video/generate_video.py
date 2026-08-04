"""
TechPulse - Video Stage (long-form, resumable)
Pulls the next Supabase video_pipeline row with status='narrated', and
generates AI video clips shot-by-shot from its shot_list (60-90 shots),
checkpointing progress (video_urls, video_next_index) into Supabase after
EVERY shot so a killed/timed-out run picks up exactly where it left off on
the next scheduled invocation - ported from the proven pattern in
marius-command-center's video generation stage, since Agnes AI is
rate-limited per-minute and a single CI run cannot generate 60-90 shots
in one pass.

For has_recurring_person=true stories: a one-time character reference
image is generated from setting_and_characters (once, cached on the row
as character_reference_url), then every shot after anchors to the last
frame of the previous shot's clip for continuity - same chaining
architecture as Marius/Erased.

For has_recurring_person=false stories: no character reference or
cross-shot anchoring - each shot generates independently from its own
visual_description so wide/data/environment shots vary instead of
locking onto one invented static figure.
"""
import json
import os
import time
import subprocess
import requests

AGNES_API_KEY = os.environ["AGNES_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

AGNES_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_POLL_URL = "https://apihub.agnes-ai.com/agnesapi"
AGNES_IMAGE_URL = f"{AGNES_BASE}/images/generations"

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}
VIDEO_CLIPS_BUCKET = "video_clips"

WIDTH, HEIGHT = 1280, 720
FRAME_RATE = 24
MIN_FRAMES = 49
MAX_FRAMES = 169
DEFAULT_SHOT_SECONDS = 4.0  # fallback if a shot has no measured duration yet

MAX_SHOT_RETRIES = 3
AGNES_RETRYABLE = {429, 500, 502, 503, 504}
RETRY_BACKOFF_BASE = 15

RUN_TIME_BUDGET_SECONDS = 11 * 60  # leaves headroom inside a scheduled run before GitHub kills it

QUALITY_GUARD = ("shot on film, natural film grain, vivid saturated color, no sepia tone, "
                  "no muted documentary color grading, no artificial CGI look")
LIGHTING_CUE_BRIGHT = "bright natural daylight, high-key lighting, well-exposed, vivid colors"
DARK_SCENE_KEYWORDS = ("night", "dark", "dim", "shadow", "dusk", "candlelit", "moonlit", "silhouette")


def round_to_valid_frames(n):
    k = max(0, round((n - 1) / 8))
    return 8 * k + 1


def agnes_headers():
    return {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}


def build_prompt(shot, setting_and_characters, use_fallback=False):
    visual = shot.get("visual_description", "")
    is_dark = any(k in visual.lower() for k in DARK_SCENE_KEYWORDS)
    lighting = "moody, intentionally low-light scene as part of the story" if is_dark else LIGHTING_CUE_BRIGHT
    if use_fallback:
        return f"{lighting}, {QUALITY_GUARD}, cinematic documentary shot, {setting_and_characters}"
    movement = shot.get("camera_movement", "static").replace("_", " ")
    return f"{lighting}, {QUALITY_GUARD}, {setting_and_characters}. {visual}. Camera: {movement}."


def http_post_json(url, payload, headers, timeout=60):
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {}
    return resp.status_code, data


def http_get_json(url, headers, timeout=30):
    resp = requests.get(url, headers=headers, timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {}
    return resp.status_code, data


def create_video_task(prompt, num_frames, image_url=None):
    payload = {"model": "agnes-video-v2.0", "prompt": prompt, "height": HEIGHT,
               "width": WIDTH, "num_frames": num_frames, "frame_rate": FRAME_RATE}
    if image_url:
        payload["image"] = image_url
    last_status = None
    for attempt in range(4):
        status, data = http_post_json(f"{AGNES_BASE}/videos", payload, agnes_headers())
        if status == 400 and "content_policy_violation" in json.dumps(data):
            raise ValueError("content_policy_violation")
        if status in AGNES_RETRYABLE:
            last_status = status
            time.sleep(RETRY_BACKOFF_BASE * (attempt + 1))
            continue
        if status >= 400:
            raise RuntimeError(f"Agnes video create error {status}: {data}")
        return data.get("video_id") or data.get("id") or data.get("task_id")
    raise RuntimeError(f"Agnes overloaded after retries (last status {last_status})")


def poll_video_task(video_id, max_wait=280, interval=10):
    waited = 0
    while waited < max_wait:
        status, data = http_get_json(
            f"{AGNES_POLL_URL}?video_id={video_id}&model_name=agnes-video-v2.0", agnes_headers())
        if status == 400 and "content_policy_violation" in json.dumps(data):
            raise ValueError("content_policy_violation")
        st = data.get("status")
        if st == "completed":
            for k in ("video_url", "url"):
                if isinstance(data.get(k), str):
                    return data[k]
            for v in data.values():
                if isinstance(v, str) and v.startswith("http") and v.endswith(".mp4"):
                    return v
            raise RuntimeError(f"Completed but no video URL: {data}")
        if st == "failed":
            raise RuntimeError(f"Agnes generation failed: {data}")
        time.sleep(interval)
        waited += interval
    raise RuntimeError("Agnes video generation timed out")


def download(url, out_path):
    resp = requests.get(url, headers={"User-Agent": "TechPulse/1.0"}, timeout=120)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


def generate_character_reference(setting_and_characters, out_path):
    prompt = (f"{setting_and_characters}, character reference portrait, full figure visible, "
              f"neutral pose, clear face and clothing detail, {LIGHTING_CUE_BRIGHT}, {QUALITY_GUARD}")
    status, data = http_post_json(AGNES_IMAGE_URL,
        {"model": "agnes-image-2.1-flash", "prompt": prompt, "size": f"{WIDTH}x{HEIGHT}",
         "extra_body": {"response_format": "url"}}, agnes_headers())
    if status >= 400:
        print(f"  Character reference failed ({status}): {data} - continuing without one.")
        return None
    url = None
    for entry in data.get("data", []):
        if isinstance(entry, dict) and entry.get("url"):
            url = entry["url"]
            break
    return url or data.get("url")


def extract_last_frame(video_path, out_png):
    subprocess.run(["ffmpeg", "-y", "-sseof", "-1", "-i", video_path, "-update", "1", "-q:v", "2", out_png],
                   check=True, capture_output=True)
    return out_png


def upload_to_supabase(local_path, dest_subdir, content_type):
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    dest_name = f"{dest_subdir}/{os.path.basename(local_path)}"
    url = f"{SUPABASE_URL}/storage/v1/object/{VIDEO_CLIPS_BUCKET}/{dest_name}"
    resp = requests.post(
        url, data=file_bytes,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        timeout=120,
    )
    if resp.status_code >= 400:
        print(f"  Supabase upload failed ({resp.status_code}): {resp.text}")
        return None
    return f"{SUPABASE_URL}/storage/v1/object/public/{VIDEO_CLIPS_BUCKET}/{dest_name}"


def get_next_narrated_row():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?status=eq.narrated&order=created_at.asc&limit=1",
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def save_progress(row_id, video_urls, video_next_index, character_reference_url=None, status=None):
    payload = {"video_urls": video_urls, "video_next_index": video_next_index}
    if character_reference_url is not None:
        payload["character_reference_url"] = character_reference_url
    if status:
        payload["status"] = status
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
        headers=HEADERS, json=payload, timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to save video progress ({resp.status_code}): {resp.text}")


def generate_one_shot(shot, setting_and_characters, out_path, anchor_image_url, duration_seconds):
    num_frames = round_to_valid_frames(int(max(duration_seconds, 1.0) * FRAME_RATE))
    num_frames = max(MIN_FRAMES, min(MAX_FRAMES, num_frames))
    for attempt in range(1, MAX_SHOT_RETRIES + 1):
        try:
            prompt = build_prompt(shot, setting_and_characters, use_fallback=False)
            try:
                video_id = create_video_task(prompt, num_frames, image_url=anchor_image_url)
            except ValueError:
                print("  Content policy rejection - retrying with generic fallback prompt")
                fallback_prompt = build_prompt(shot, setting_and_characters, use_fallback=True)
                video_id = create_video_task(fallback_prompt, num_frames, image_url=anchor_image_url)
            video_url = poll_video_task(video_id)
            download(video_url, out_path)
            return True
        except Exception as e:
            print(f"  Attempt {attempt}/{MAX_SHOT_RETRIES} failed: {e}")
            if attempt < MAX_SHOT_RETRIES:
                time.sleep(RETRY_BACKOFF_BASE * attempt)
    return False


def main():
    row = get_next_narrated_row()
    if not row:
        print("No 'narrated' rows found. Nothing to do.")
        return

    row_id = row["id"]
    shot_list = row.get("shot_list") or []
    if isinstance(shot_list, str):
        shot_list = json.loads(shot_list)
    shot_durations = row.get("shot_durations") or []
    if isinstance(shot_durations, str):
        shot_durations = json.loads(shot_durations)
    setting_and_characters = row.get("setting_and_characters") or ""
    has_person = bool(row.get("has_recurring_person", False))
    video_urls = row.get("video_urls") or []
    if isinstance(video_urls, str):
        video_urls = json.loads(video_urls)
    next_index = row.get("video_next_index") or 0
    character_reference_url = row.get("character_reference_url")

    total_shots = len(shot_list)
    print(f"Row {row_id}: {total_shots} shots, resuming from index {next_index}, "
          f"{len(video_urls)} clips already saved.")

    if total_shots == 0:
        print("shot_list is empty on this row - marking failed.")
        save_progress(row_id, video_urls, next_index, status="failed")
        return

    os.makedirs("video/clips", exist_ok=True)

    if has_person and not character_reference_url:
        ref_path = "video/clips/character_reference.png"
        remote_url = generate_character_reference(setting_and_characters, ref_path)
        if remote_url:
            download(remote_url, ref_path)
            uploaded = upload_to_supabase(ref_path, "anchors", "image/png")
            character_reference_url = uploaded or remote_url
            save_progress(row_id, video_urls, next_index, character_reference_url=character_reference_url)
            print("Character reference ready and saved.")
        else:
            print("No character reference generated - shots will chain without an initial anchor.")

    anchor_url = character_reference_url if has_person else None
    # If resuming mid-video, chain from the last saved clip instead of the character ref.
    if has_person and next_index > 0 and video_urls:
        anchor_url = video_urls[-1]

    start_time = time.time()
    while next_index < total_shots:
        if time.time() - start_time > RUN_TIME_BUDGET_SECONDS:
            print(f"Time budget reached at shot {next_index}/{total_shots} - "
                  f"checkpoint saved, next scheduled run will resume.")
            break

        shot = shot_list[next_index]
        duration = shot_durations[next_index] if next_index < len(shot_durations) else DEFAULT_SHOT_SECONDS
        clip_path = f"video/clips/shot_{row_id}_{next_index}.mp4"

        print(f"Shot {next_index + 1}/{total_shots} ({duration:.1f}s target)...")
        ok = generate_one_shot(shot, setting_and_characters, clip_path,
                                anchor_image_url=anchor_url, duration_seconds=duration)
        if not ok:
            print(f"Giving up on shot {next_index} after retries - marking row failed.")
            save_progress(row_id, video_urls, next_index, status="failed")
            return

        clip_url = upload_to_supabase(clip_path, "clips", "video/mp4")
        if not clip_url:
            print(f"Could not upload shot {next_index} to Supabase - marking row failed.")
            save_progress(row_id, video_urls, next_index, status="failed")
            return

        video_urls.append(clip_url)
        next_index += 1

        if has_person:
            try:
                last_frame_png = f"video/clips/lastframe_{row_id}_{next_index}.png"
                extract_last_frame(clip_path, last_frame_png)
                new_anchor = upload_to_supabase(last_frame_png, "anchors", "image/png")
                if new_anchor:
                    anchor_url = new_anchor
                if os.path.exists(last_frame_png):
                    os.remove(last_frame_png)
            except Exception as e:
                print(f"  Could not extract continuity anchor from shot {next_index - 1}, "
                      f"next shot generates blind: {e}")

        if os.path.exists(clip_path):
            os.remove(clip_path)

        save_progress(row_id, video_urls, next_index)
        print(f"Checkpoint saved: {next_index}/{total_shots} shots done.")

    if next_index >= total_shots:
        save_progress(row_id, video_urls, next_index, status="video_complete")
        print(f"Row {row_id}: all {total_shots} shots complete. Status -> video_complete.")


if __name__ == "__main__":
    main()
