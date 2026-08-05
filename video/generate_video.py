"""
TechPulse - Video Generation Stage (LONG-FORM, RESUMABLE)
Rewritten 2026-08-05 to fix a real, confirmed production failure: the
previous version rendered ALL shots for a video (up to 63+ on a long-form
episode) sequentially inside a single pipeline.yml job, but Agnes AI
allows only 1 request/minute. That job can never finish a long-form
video's shots in one run, and every retry hits the identical wall - this
is exactly what happened to row 77b60f3d ("Bending Spoons to buy Airtable
for $1.28B"): it exhausted all 3 retries and was marked permanently
'failed' without ever getting past shot 1. That row has been reset back
to 'narrated' with shot_retry_count=0 so this version can pick it back up.

NEW DESIGN: this script does ONE shot per invocation, same resumable
pattern proven in Marius:
  1. Find the oldest 'narrated' row (or a row already mid-render, tracked
     via video_urls already having some entries).
  2. Render exactly the next not-yet-done shot (index = len(video_urls)).
  3. Upload that one clip, append its URL to video_urls, save.
  4. If that was the last shot, flip status to 'video_complete' (with
     the full video_urls array assemble.py already expects - unchanged).
  5. Exit. The next cron tick renders the next shot - whether that's
     shot 2 of this same video, or shot 1 of the next one once this one
     is done. A single Agnes rate-limit failure now costs one shot's
     worth of delay, not the whole video's retry budget.

Frame-count fix (num_frames must be 8n+1) and Agnes endpoints are carried
over unchanged from the 2026-08-05 schema-fix version of this file.

New Supabase column added for this: shot_retry_count (integer, default 0)
on video_pipeline - tracks retries for the CURRENT shot only, separate
from any whole-video retry_count used elsewhere.
"""
import json
import os
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
AGNES_API_KEY = os.environ["AGNES_API_KEY"]

AGNES_SUBMIT_URL = "https://apihub.agnes-ai.com/v1/videos"
AGNES_POLL_URL = "https://apihub.agnes-ai.com/agnesapi"
AGNES_MODEL = "agnes-video-v2.0"
AGNES_HEADERS = {
    "Authorization": f"Bearer {AGNES_API_KEY}",
    "Content-Type": "application/json",
}

WIDTH, HEIGHT = 1280, 720
FRAME_RATE = 24
POLL_MAX_WAIT = 240
POLL_INTERVAL = 10

VIDEO_CLIPS_BUCKET = "video_clips"
RETRY_LIMIT = 3  # per-SHOT retries now, not per-video


def _supabase_request(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw.strip() else None


def get_next_row_to_render():
    """Oldest 'narrated' row (whether fresh or already partway through
    rendering - progress is tracked via how many entries video_urls has,
    not via a separate status)."""
    rows = _supabase_request(
        "GET",
        "video_pipeline?status=eq.narrated&order=created_at.asc&limit=1&select=*",
    )
    return rows[0] if rows else None


def frames_for_duration(duration_seconds, frame_rate=FRAME_RATE):
    """Round to the nearest frame count Agnes accepts (must be 8*n + 1)."""
    raw = duration_seconds * frame_rate
    n = max(round((raw - 1) / 8), 1)
    return 8 * n + 1


def submit_agnes_task(prompt, duration_seconds):
    body = json.dumps({
        "model": AGNES_MODEL,
        "prompt": prompt,
        "height": HEIGHT,
        "width": WIDTH,
        "num_frames": frames_for_duration(duration_seconds),
        "frame_rate": FRAME_RATE,
    }).encode()
    req = urllib.request.Request(AGNES_SUBMIT_URL, data=body, method="POST", headers=AGNES_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Agnes submit HTTP {e.code}: {error_body}") from e
    video_id = data.get("video_id") or data.get("id")
    if not video_id:
        raise RuntimeError(f"Agnes submit response had no video_id: {data}")
    return video_id


def poll_agnes_task(video_id):
    waited = 0
    url = f"{AGNES_POLL_URL}?video_id={video_id}&model_name={AGNES_MODEL}"
    while waited < POLL_MAX_WAIT:
        req = urllib.request.Request(url, headers=AGNES_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Agnes poll HTTP {e.code}: {error_body}") from e
        status = data.get("status")
        if status == "completed":
            for key in ("video_url", "url"):
                val = data.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    return val
            raise RuntimeError(f"Agnes completed but no video URL found: {data}")
        if status == "failed":
            raise RuntimeError(f"Agnes generation failed: {data}")
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
    raise RuntimeError(f"Agnes generation timed out after {POLL_MAX_WAIT}s for video_id {video_id}")


def download_file(url, out_path):
    urllib.request.urlretrieve(url, out_path)
    return out_path


def upload_clip(row_id, index, local_path):
    dest_name = f"{row_id}/shot_{index:03d}.mp4"
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/storage/v1/object/{VIDEO_CLIPS_BUCKET}/{dest_name}",
        data=file_bytes,
        method="POST",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "video/mp4",
            "x-upsert": "true",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Clip upload failed ({resp.status})")
    return f"{SUPABASE_URL}/storage/v1/object/public/{VIDEO_CLIPS_BUCKET}/{dest_name}"


def save_progress(row_id, video_urls, shot_retry_count):
    """Persist progress after every shot - whether it succeeded (new URL
    appended) or failed (just the retry counter bumped). Status stays
    'narrated' until every shot is done."""
    _supabase_request("PATCH", f"video_pipeline?id=eq.{row_id}", {
        "video_urls": video_urls,
        "shot_retry_count": shot_retry_count,
    })


def mark_video_complete(row_id, video_urls):
    _supabase_request("PATCH", f"video_pipeline?id=eq.{row_id}", {
        "status": "video_complete",
        "video_urls": video_urls,
    })


def mark_row_permanently_failed(row_id, reason):
    print(f"Row {row_id} permanently failed: {reason}")
    _supabase_request("PATCH", f"video_pipeline?id=eq.{row_id}", {"status": "failed"})


def main():
    row = get_next_row_to_render()
    if not row:
        print("No 'narrated' rows found. Nothing to do.")
        return

    row_id = row["id"]
    shot_list = row.get("shot_list")
    if isinstance(shot_list, str):
        shot_list = json.loads(shot_list)
    shot_durations = row.get("shot_durations")
    if isinstance(shot_durations, str):
        shot_durations = json.loads(shot_durations)
    video_urls = row.get("video_urls") or []
    if isinstance(video_urls, str):
        video_urls = json.loads(video_urls) if video_urls else []
    shot_retry_count = row.get("shot_retry_count") or 0

    if not shot_list:
        mark_row_permanently_failed(row_id, "no shot_list on a 'narrated' row")
        return
    if not shot_durations or len(shot_durations) != len(shot_list):
        mark_row_permanently_failed(
            row_id,
            f"shot_durations missing or length mismatch ({len(shot_durations or [])} vs {len(shot_list)} shots)",
        )
        return

    next_index = len(video_urls)
    total_shots = len(shot_list)

    if next_index >= total_shots:
        print(f"Row {row_id}: all {total_shots} shots already done, finalizing.")
        mark_video_complete(row_id, video_urls)
        return

    shot = shot_list[next_index]
    prompt = shot.get("scene_description") or shot.get("visual_description", "")
    prompt = prompt.strip()
    duration = shot_durations[next_index]

    print(f"Row {row_id}: rendering shot {next_index + 1}/{total_shots} (~{duration:.1f}s): {prompt[:80]!r}")
    try:
        video_id = submit_agnes_task(prompt, duration)
        video_url = poll_agnes_task(video_id)
        local_path = f"/tmp/shot_{row_id}_{next_index:03d}.mp4"
        download_file(video_url, local_path)
        clip_url = upload_clip(row_id, next_index, local_path)
        os.remove(local_path)

        video_urls.append(clip_url)
        if len(video_urls) >= total_shots:
            mark_video_complete(row_id, video_urls)
            print(f"Row {row_id}: all {total_shots} shots done this run. Status -> video_complete.")
        else:
            save_progress(row_id, video_urls, 0)  # reset per-shot retry counter on success
            print(f"Row {row_id}: shot {next_index + 1}/{total_shots} done. "
                  f"{total_shots - len(video_urls)} remaining, will continue next run.")
    except Exception as e:
        next_retry = shot_retry_count + 1
        if next_retry >= RETRY_LIMIT:
            mark_row_permanently_failed(row_id, f"shot {next_index + 1}/{total_shots} failed {RETRY_LIMIT}x: {e}")
        else:
            print(f"Row {row_id}: shot {next_index + 1}/{total_shots} failed "
                  f"(attempt {next_retry}/{RETRY_LIMIT}): {e}. Will retry next run.")
            save_progress(row_id, video_urls, next_retry)


if __name__ == "__main__":
    main()
