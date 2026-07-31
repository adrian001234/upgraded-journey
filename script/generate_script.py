"""
TechPulse - Video Stage
Generates one real AI video clip per scene via Agnes AI (agnes-video-v2.0).
For stories with a genuine recurring person (has_recurring_person=true),
uses image-to-video anchoring for character/scene continuity: scene 0 builds
a one-time character reference image, and every scene after anchors to the
last frame of the previous scene's clip - same architecture as Marius/Erased.
For abstract/data-driven stories (has_recurring_person=false), NO character
reference or cross-scene anchoring is used at all - each scene generates
independently from its own text so shots vary instead of locking onto one
invented, static figure for the whole video.
"""
import json
import os
import time
import subprocess
import urllib.request
import urllib.error

AGNES_API_KEY = os.environ["AGNES_API_KEY"]
AGNES_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_POLL_URL = "https://apihub.agnes-ai.com/agnesapi"
AGNES_IMAGE_URL = f"{AGNES_BASE}/images/generations"

WIDTH, HEIGHT = 1280, 720
FRAME_RATE = 24
MIN_FRAMES = 49
MAX_FRAMES = 169
CLIP_SECONDS = 5.0  # per-scene target; Assembly stage trims/extends to the real per-segment duration

MAX_SCENE_RETRIES = 3
AGNES_RETRYABLE = {429, 500, 502, 503, 504}
RETRY_BACKOFF_BASE = 15

QUALITY_GUARD = ("shot on film, natural film grain, vivid saturated color, no sepia tone, "
                  "no muted documentary color grading, no artificial CGI look")
LIGHTING_CUE_BRIGHT = "bright natural daylight, high-key lighting, well-exposed, vivid colors"
DARK_SCENE_KEYWORDS = ("night", "dark", "dim", "shadow", "dusk", "candlelit", "moonlit", "silhouette")


def round_to_valid_frames(n):
    k = max(0, round((n - 1) / 8))
    return 8 * k + 1


def agnes_headers():
    return {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}


def build_prompt(scene_text, use_fallback=False):
    is_dark = any(k in scene_text.lower() for k in DARK_SCENE_KEYWORDS)
    lighting = "moody, intentionally low-light scene as part of the story" if is_dark else LIGHTING_CUE_BRIGHT
    if use_fallback:
        return f"{lighting}, {QUALITY_GUARD}, cinematic documentary shot"
    return f"{lighting}, {QUALITY_GUARD}, {scene_text}"


def http_post_json(url, payload, headers, timeout=60):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read() or b"{}")
        except Exception:
            data = {}
        return e.code, data


def http_get_json(url, headers, timeout=30):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read() or b"{}")
        except Exception:
            data = {}
        return e.code, data


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
    req = urllib.request.Request(url, headers={"User-Agent": "TechPulse/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)


def generate_character_reference(anchor_text, out_path):
    prompt = (f"{anchor_text}, character reference portrait, full figure visible, "
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


def upload_to_tmpfiles(local_path):
    """Agnes needs a public image URL for image-to-video anchoring. Uses
    tmpfiles.org (free, no key, no signup) to host the extracted frame /
    reference image just long enough for Agnes to fetch it."""
    boundary = "----tpdboundary"
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"f.png\"\r\n"
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request("https://tmpfiles.org/api/v1/upload", data=body,
                                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        url = result.get("data", {}).get("url", "")
        return url.replace("tmpfiles.org/", "tmpfiles.org/dl/") if url else None
    except Exception as e:
        print(f"  tmpfiles upload failed, continuing without a continuity anchor: {e}")
        return None


def generate_scene_clip(scene_text, out_path, anchor_image_url=None):
    num_frames = round_to_valid_frames(int(CLIP_SECONDS * FRAME_RATE))
    num_frames = max(MIN_FRAMES, min(MAX_FRAMES, num_frames))
    for attempt in range(1, MAX_SCENE_RETRIES + 1):
        try:
            prompt = build_prompt(scene_text, use_fallback=False)
            try:
                video_id = create_video_task(prompt, num_frames, image_url=anchor_image_url)
            except ValueError:
                print("  Content policy rejection - retrying with generic fallback prompt")
                fallback_prompt = build_prompt(scene_text, use_fallback=True)
                video_id = create_video_task(fallback_prompt, num_frames, image_url=anchor_image_url)
            video_url = poll_video_task(video_id)
            download(video_url, out_path)
            return True
        except Exception as e:
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} failed: {e}")
            if attempt < MAX_SCENE_RETRIES:
                time.sleep(RETRY_BACKOFF_BASE * attempt)
    return False


def generate_videos(scripts_path="script/latest_scripts.json", out_path="video/latest_videos.json"):
    with open(scripts_path) as f:
        scripts = json.load(f)

    os.makedirs("video/clips", exist_ok=True)
    videos = []
    for s_idx, s in enumerate(scripts):
        scenes = s["scenes"]
        clip_paths = []
        has_person = bool(s.get("has_recurring_person", False))

        anchor_url = None
        if has_person:
            ref_path = f"video/clips/ref_{s_idx}.png"
            anchor_url = generate_character_reference(scenes[0], ref_path)
            if anchor_url:
                print(f"  Character reference ready for: {s['title']}")
            else:
                print(f"  No character reference for: {s['title']} - first scene will generate blind.")
        else:
            print(f"  No recurring person for: {s['title']} - scenes will generate independently, no anchor chain.")

        for i, scene in enumerate(scenes):
            clip_path = f"video/clips/clip_{s_idx}_{i}.mp4"
            ok = generate_scene_clip(scene, clip_path, anchor_image_url=anchor_url)
            if not ok:
                print(f"  Giving up on scene {i} for: {s['title']}")
                break
            clip_paths.append(clip_path)

            if has_person:
                try:
                    last_frame_png = f"video/clips/lastframe_{s_idx}_{i}.png"
                    extract_last_frame(clip_path, last_frame_png)
                    new_anchor = upload_to_tmpfiles(last_frame_png)
                    if new_anchor:
                        anchor_url = new_anchor
                    if os.path.exists(last_frame_png):
                        os.remove(last_frame_png)
                except Exception as e:
                    print(f"  Could not extract continuity anchor from scene {i}, next scene generates blind: {e}")

        if len(clip_paths) == len(scenes):
            videos.append({**s, "video_urls": clip_paths})
            print(f"Generated {len(clip_paths)}/{len(scenes)} clips for: {s['title']}")
        else:
            print(f"SKIPPING '{s['title']}': only {len(clip_paths)}/{len(scenes)} scenes succeeded")

    with open(out_path, "w") as f:
        json.dump(videos, f, indent=2)
    print(f"Saved {len(videos)} videos to {out_path}")


if __name__ == "__main__":
    generate_videos()
