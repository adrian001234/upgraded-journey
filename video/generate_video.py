"""
TechPulse - Video Generation Stage (LONG-FORM)
Rewritten 2026-08-05 to fix a schema mismatch with generate_script.py and
narration/generate_narration.py.

SCHEMA FIX (2026-08-05): the 2026-08-04 version of this file read shots
from a separate video_shots table (scene_description field) keyed off
generation_status='shots_generating' - a schema that generate_script.py
no longer writes and that has no connection to shot_durations computed
by narration.py. This version instead pulls the oldest video_pipeline
row with status='narrated' (set by generate_narration.py once real
per-shot audio timing is known), and renders each shot in its shot_list
directly, sized to that shot's own entry in shot_durations - the exact
values narration.py already computed from real narration audio, instead
of a hardcoded 8s/shot guess.

FRAME-COUNT FIX (2026-08-05): Agnes requires num_frames in the form
8*n + 1 (its native video-diffusion chunking window) and returns HTTP 400
on any other value. The previous version passed duration_seconds*FRAME_RATE
truncated to an int with no regard for this constraint - this worked by
chance on some shots and failed on others (e.g. a 3.2s shot at 24fps =
76 frames, not a valid 8n+1 value). Now rounds to the nearest valid
8n+1 frame count instead.

RETRY LOGIC (2026-08-05): previously any failure (Agnes error, bad data,
timeout) permanently marked the row status='failed' with no automatic
retry - a stuck row just sat there until a human noticed and manually
reset it. Now failures requeue the row back to status='narrated' (so
the next run picks it up again) up to RETRY_LIMIT times, tracked via a
retry_count column, before giving up and marking it permanently failed.

SCOPE NOTE: this does NOT port Marius's character-reference/continuity-
anchor chaining, SFX, or background-music layering - those are feature
additions, not part of this schema-consistency fix. Shots are generated
independently (text-to-video only), same as this file's previous
version. Flagged separately since it affects visual consistency across
shots on longer videos.

TIMEOUT RISK (unresolved, flagged not fixed): pipeline.yml runs this
inside the same 20-minute job as every other stage, with all ~45 shots
for a video generated sequentially in a single call to main(). At Agnes's
typical per-clip generation+poll time this will not reliably fit for a
45-shot long-form video inside the remaining time budget after
research/script/narration already ran in the same job. Not addressed
here - would need either a per-run shot budget + resume logic (the
pattern Marius uses) or a separate workflow/timeout, both of which are
scope decisions beyond this bug fix.
"""
import json
import os
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

RETRY_LIMIT = 3


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


def get_next_narrated_row():
    rows = _supabase_request(
        "GET",
        "video_pipeline?status=eq.narrated&order=created_at.asc&limit=1&select=*",
    )
    return rows[0] if rows else None


def mark_failed(row_id, reason, retry_count):
    if retry_count < RETRY_LIMIT:
        next_count = retry_count + 1
        print(f"Row {row_id} failed (attempt {next_count}/{RETRY_LIMIT}): {reason}. Requeuing as 'narrated'.")
        _supabase_request("PATCH", f"video_pipeline?id=eq.{row_id}", {
            "status": "narrated",
            "retry_count": next_count,
        })
    else:
        print(f"Row {row_id} failed permanently after {RETRY_LIMIT} attempts: {reason}")
        _supabase_request("PATCH", f"video_pipeline?id=eq.{row_id}", {"status": "failed"})


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
        import time
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


def mark_video_complete(row_id, video_urls):
    _supabase_request("PATCH", f"video_pipeline?id=eq.{row_id}", {
        "status": "video_complete",
        "video_urls": video_urls,
    })


def main():
    row = get_next_narrated_row()
    if not row:
        print("No 'narrated' rows found. Nothing to do.")
        return

    row_id = row["id"]
    retry_count = row.get("retry_count") or 0
    shot_list = row.get("shot_list")
    if isinstance(shot_list, str):
        shot_list = json.loads(shot_list)
    shot_durations = row.get("shot_durations")
    if isinstance(shot_durations, str):
        shot_durations = json.loads(shot_durations)

    if not shot_list:
        mark_failed(row_id, "no shot_list on a 'narrated' row", retry_count)
        return
    if not shot_durations or len(shot_durations) != len(shot_list):
        mark_failed(row_id, f"shot_durations missing or length mismatch ({len(shot_durations or [])} vs {len(shot_list)} shots)", retry_count)
        return

    print(f"Generating {len(shot_list)} shots for pipeline row {row_id}...")
    video_urls = []
    for i, shot in enumerate(shot_list):
        prompt = shot.get("visual_description", "").strip()
        duration = shot_durations[i]
        print(f"  Shot {i + 1}/{len(shot_list)} (~{duration:.1f}s): {prompt[:80]!r}")
        try:
            video_id = submit_agnes_task(prompt, duration)
            video_url = poll_agnes_task(video_id)
            local_path = f"/tmp/shot_{row_id}_{i:03d}.mp4"
            download_file(video_url, local_path)
            clip_url = upload_clip(row_id, i, local_path)
            os.remove(local_path)
            video_urls.append(clip_url)
        except Exception as e:
            mark_failed(row_id, f"shot {i + 1}/{len(shot_list)} failed: {e}", retry_count)
            return

    mark_video_complete(row_id, video_urls)
    print(f"Row {row_id}: all {len(video_urls)} shots generated. Status -> video_complete.")


if __name__ == "__main__":
    main()
