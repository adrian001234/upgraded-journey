"""
Tiny Lawn Tales - Video Generation Stage (resumable, one shot at a time)

Finds the oldest 'narrated' row in video_pipeline and renders its shots one
by one with Agnes Video 2.5 Flash, saving progress after every shot.

- Model: agnes-video-2.5-flash (Agnes retired agnes-video-v2.0 on 2026-09-25).
  720P only, 4 to 12 seconds per shot, asynchronous: create a task with
  POST /v1/videos, then poll GET /agnesapi?video_id=...&model_name=...
- Pacing: Agnes allows 1 request per minute on this account, so submissions
  are spaced AGNES_MIN_SECONDS_BETWEEN_SUBMITS apart.
- Character reference: if CHARACTER_REFERENCE_URL and CHARACTER_REFERENCE_NAME
  are both set, any shot whose text contains the character name is rendered in
  Agnes "reference" mode with the character picture, so she looks the same in
  every clip. Other shots are rendered text-only.
- Retries: transient errors (429, 5xx) are retried with backoff. A shot that
  keeps failing is retried across runs (shot_retry_count), then the row is
  marked 'failed'. A content-policy rejection fails the row immediately.
- Resume: video_urls holds finished clips. Before rendering, recorded clip
  URLs are checked and any dead link is re-rendered.
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
AGNES_MODEL = "agnes-video-2.5-flash"
AGNES_HEADERS = {
    "Authorization": f"Bearer {AGNES_API_KEY}",
    "Content-Type": "application/json",
}

VIDEO_SIZE = "720P"  # Flash supports only "720P"
ASPECT_RATIO = "16:9"
MIN_SHOT_SECONDS = 4
MAX_SHOT_SECONDS = 12

POLL_MAX_WAIT = 900
POLL_INTERVAL = 10

AGNES_RETRYABLE_CODES = {429, 500, 502, 503, 504}
AGNES_MAX_RETRIES = 4

VIDEO_CLIPS_BUCKET = "video_clips"
RETRY_LIMIT = 3  # per-shot retries

CLIP_VERIFY_TIMEOUT = 15

AGNES_MIN_SECONDS_BETWEEN_SUBMITS = 65
MAX_SHOTS_PER_RUN = 30
RUN_TIME_BUDGET_SECONDS = 260 * 60

CHARACTER_REFERENCE_URL = os.environ.get("CHARACTER_REFERENCE_URL", "").strip()
CHARACTER_REFERENCE_NAME = os.environ.get("CHARACTER_REFERENCE_NAME", "").strip().lower()


class ContentPolicyRejection(Exception):
    pass


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
    """Oldest 'narrated' row (fresh or partway through rendering; progress is
    tracked by how many entries video_urls has)."""
    rows = _supabase_request(
        "GET",
        "video_pipeline?status=eq.narrated&order=created_at.asc&limit=1&select=*",
    )
    return rows[0] if rows else None


def seconds_for_duration(duration_seconds):
    """Agnes 2.5 wants the duration as a string between "4" and "12"."""
    return str(min(max(round(duration_seconds), MIN_SHOT_SECONDS), MAX_SHOT_SECONDS))


def submit_agnes_task(prompt, duration_seconds, image_url=None):
    """Create an Agnes video task and return its video_id. Retries 429/5xx
    with backoff. A content-policy rejection (400) raises immediately."""
    payload = {
        "model": AGNES_MODEL,
        "prompt": prompt,
        "mode": "text",
        "seconds": seconds_for_duration(duration_seconds),
        "size": VIDEO_SIZE,
        "aspect_ratio": ASPECT_RATIO,
        "n": 1,
    }
    if image_url:
        payload["mode"] = "reference"
        payload["images"] = [image_url]
        payload["prompt"] = (
            "Use the character and art style in <Picture 1> as reference, "
            "keeping her appearance exactly the same. " + prompt
        )
    body = json.dumps(payload).encode()

    last_error_text = None
    for attempt in range(AGNES_MAX_RETRIES):
        req = urllib.request.Request(AGNES_SUBMIT_URL, data=body, method="POST", headers=AGNES_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode(errors="replace")[:500]
            if e.code == 400 and "content_policy_violation" in error_body:
                raise ContentPolicyRejection(error_body)
            if e.code in AGNES_RETRYABLE_CODES:
                last_error_text = f"HTTP {e.code}: {error_body}"
                wait = 20 * (attempt + 1)
                print(f"Agnes submit transient error {e.code} (attempt {attempt + 1}/{AGNES_MAX_RETRIES}): {error_body}")
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Agnes submit HTTP {e.code}: {error_body}") from e

        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            raise RuntimeError(f"Agnes submit response had no video_id: {data}")
        return video_id

    raise RuntimeError(f"Agnes submit still failing after {AGNES_MAX_RETRIES} attempts: {last_error_text}")


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
            if e.code == 400 and "content_policy_violation" in error_body:
                raise ContentPolicyRejection(error_body)
            if e.code in AGNES_RETRYABLE_CODES:
                print(f"Agnes poll transient error {e.code}, will retry within the same poll loop: {error_body}")
                time.sleep(POLL_INTERVAL)
                waited += POLL_INTERVAL
                continue
            raise RuntimeError(f"Agnes poll HTTP {e.code}: {error_body}") from e
        status = data.get("status")
        if status == "completed":
            for key in ("url", "video_url"):
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


def verify_clip_url(url):
    """HEAD-check an already-recorded clip URL before trusting it."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=CLIP_VERIFY_TIMEOUT) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Clip verification failed for {url}: {e}")
        return False


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
    """Persist progress after every shot. Status stays 'narrated' until every
    shot is done."""
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


def render_one_shot():
    """Render exactly the next unfinished shot on the oldest 'narrated' row.
    Returns True if progress was made (or a retry was scheduled), False if
    there was nothing to do or the row hit a stopping condition."""
    row = get_next_row_to_render()
    if not row:
        print("No 'narrated' rows found. Nothing to do.")
        return False

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
        return False
    if not shot_durations or len(shot_durations) != len(shot_list):
        mark_row_permanently_failed(
            row_id,
            f"shot_durations missing or length mismatch ({len(shot_durations or [])} vs {len(shot_list)} shots)",
        )
        return False

    if video_urls:
        verified_urls = []
        for i, url in enumerate(video_urls):
            if verify_clip_url(url):
                verified_urls.append(url)
            else:
                print(f"Row {row_id}: clip {i} failed verification, will regenerate from here.")
                break
        if len(verified_urls) != len(video_urls):
            video_urls = verified_urls
            save_progress(row_id, video_urls, 0)
            print(f"Row {row_id}: corrected progress after verification - {len(video_urls)}/{len(shot_list)} shots actually confirmed done")

    next_index = len(video_urls)
    total_shots = len(shot_list)

    if next_index >= total_shots:
        print(f"Row {row_id}: all {total_shots} shots already done, finalizing.")
        mark_video_complete(row_id, video_urls)
        return False

    shot = shot_list[next_index]
    prompt = shot.get("scene_description") or shot.get("visual_description", "")
    prompt = prompt.strip()
    duration = shot_durations[next_index]

    image_url = None
    if CHARACTER_REFERENCE_URL and CHARACTER_REFERENCE_NAME and CHARACTER_REFERENCE_NAME in prompt.lower():
        image_url = CHARACTER_REFERENCE_URL

    print(f"Row {row_id}: rendering shot {next_index + 1}/{total_shots} (~{duration:.1f}s)"
          f"{' [with character reference image]' if image_url else ''}: {prompt[:80]!r}")
    try:
        video_id = submit_agnes_task(prompt, duration, image_url)
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
            save_progress(row_id, video_urls, 0)
            print(f"Row {row_id}: shot {next_index + 1}/{total_shots} done. "
                  f"{total_shots - len(video_urls)} remaining, will continue this run if time/budget allow.")
        return True
    except ContentPolicyRejection as e:
        mark_row_permanently_failed(
            row_id,
            f"shot {next_index + 1}/{total_shots} rejected on content-policy grounds: {e}. "
            f"Prompt was: {prompt!r}. Reword shot_list[{next_index}] and reset status to 'narrated' to resume.",
        )
        return False
    except Exception as e:
        next_retry = shot_retry_count + 1
        if next_retry >= RETRY_LIMIT:
            mark_row_permanently_failed(row_id, f"shot {next_index + 1}/{total_shots} failed {RETRY_LIMIT}x: {e}")
            return False
        print(f"Row {row_id}: shot {next_index + 1}/{total_shots} failed "
              f"(attempt {next_retry}/{RETRY_LIMIT}): {e}. Will retry next run.")
        save_progress(row_id, video_urls, next_retry)
        return True


def main():
    run_start = time.monotonic()
    shots_this_run = 0

    while shots_this_run < MAX_SHOTS_PER_RUN:
        elapsed = time.monotonic() - run_start
        if elapsed >= RUN_TIME_BUDGET_SECONDS:
            print(f"Run time budget ({RUN_TIME_BUDGET_SECONDS}s) reached after {shots_this_run} shot(s) - "
                  f"stopping cleanly, next scheduled run continues.")
            break

        shot_start = time.monotonic()
        made_progress = render_one_shot()
        if not made_progress:
            break
        shots_this_run += 1

        time_spent_on_shot = time.monotonic() - shot_start
        remaining_pace = AGNES_MIN_SECONDS_BETWEEN_SUBMITS - time_spent_on_shot
        if remaining_pace > 0 and shots_this_run < MAX_SHOTS_PER_RUN:
            elapsed = time.monotonic() - run_start
            if elapsed + remaining_pace >= RUN_TIME_BUDGET_SECONDS:
                print(f"Pacing sleep would exceed the run time budget - stopping after {shots_this_run} shot(s) instead.")
                break
            print(f"Pacing {remaining_pace:.0f}s before next Agnes submission (staying under 1 req/min)...")
            time.sleep(remaining_pace)

    print(f"Run finished: {shots_this_run} shot(s) processed this run.")


if __name__ == "__main__":
    main()
