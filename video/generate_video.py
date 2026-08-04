"""
TechPulse - Video Generation Stage (LONG-FORM, RESUMABLE)
Rewritten 2026-08-04 alongside generate_script.py for the move to long-form
video, matching the resumable shot-by-shot pattern proven in Marius.

Old design: generated all 7 scenes in a single run via Agnes AI. That
doesn't work for long-form because Agnes is rate-limited per-minute and a
6-7 minute video has 40-50+ shots - far more than one run can render.

New design: this script does ONE unit of work per invocation:
  1. Find the oldest pipeline row still in 'shots_generating' status.
  2. Pull its single oldest 'pending' shot from video_shots.
  3. Render that one shot via Agnes AI.
  4. Mark that shot 'generated', bump shots_completed on the pipeline row.
  5. If that was the last shot, aggregate all shot video_urls +
     shot_durations onto the pipeline row itself and flip status to
     'video_complete' - the exact trigger assemble.py already polls for
     (assemble.py itself needed NO changes; it was already built to
     handle a variable number of shots this way).
  6. Exit. The next cron tick repeats this for the next pending shot -
     of this video, or the next video once this one's shots are done.

This means a rate-limit failure on shot 23 of 45 just pauses progress;
the next run retries shot 23 rather than losing the whole video.

FIXED (2026-08-04): the first version of this file flipped
generation_status to 'assembling' when shots finished - but assemble.py
never reads generation_status; it polls the 'status' column for
'video_complete' and expects video_urls/shot_durations arrays directly
on the pipeline row. Corrected below.
"""
import json
import os
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
AGNES_API_KEY = os.environ["AGNES_API_KEY"]
AGNES_URL = os.environ.get("AGNES_API_URL", "https://api.agnes.ai/v1/generate")
SHOT_DURATION_SECONDS = 8


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


def get_next_pipeline_row():
    """Oldest pipeline row still generating shots."""
    rows = _supabase_request(
        "GET",
        "video_pipeline?generation_status=eq.shots_generating&order=created_at.asc&limit=1&select=*",
    )
    return rows[0] if rows else None


def get_next_pending_shot(pipeline_id):
    rows = _supabase_request(
        "GET",
        f"video_shots?pipeline_id=eq.{pipeline_id}&status=eq.pending&order=shot_number.asc&limit=1&select=*",
    )
    return rows[0] if rows else None


def get_all_shot_urls(pipeline_id):
    """Fetch every shot's video_url for this pipeline, in shot order."""
    rows = _supabase_request(
        "GET",
        f"video_shots?pipeline_id=eq.{pipeline_id}&order=shot_number.asc&select=video_url,status",
    )
    return rows


def render_shot_via_agnes(scene_description):
    """Call Agnes AI to render a single clip for this shot."""
    body = json.dumps({
        "prompt": scene_description,
        "duration_seconds": SHOT_DURATION_SECONDS,
        "aspect_ratio": "9:16",
    }).encode()
    req = urllib.request.Request(
        AGNES_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
            return result["video_url"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Agnes HTTP {e.code}: {error_body}") from e


def mark_shot_generated(shot_id, video_url):
    _supabase_request("PATCH", f"video_shots?id=eq.{shot_id}", {"status": "generated", "video_url": video_url})


def mark_shot_pending_again(shot_id):
    """Reset a failed shot back to pending so the next tick retries it, rather than skipping it permanently."""
    _supabase_request("PATCH", f"video_shots?id=eq.{shot_id}", {"status": "pending"})


def mark_shot_failed(shot_id):
    _supabase_request("PATCH", f"video_shots?id=eq.{shot_id}", {"status": "failed"})


def bump_shots_completed(pipeline_id, new_count, total_shots):
    update = {"shots_completed": new_count}
    if new_count >= total_shots:
        shots = get_all_shot_urls(pipeline_id)
        video_urls = [s["video_url"] for s in shots if s["status"] == "generated"]
        shot_durations = [SHOT_DURATION_SECONDS] * len(video_urls)
        update["video_urls"] = video_urls
        update["shot_durations"] = shot_durations
        update["status"] = "video_complete"
    _supabase_request("PATCH", f"video_pipeline?id=eq.{pipeline_id}", update)


def main():
    pipeline_row = get_next_pipeline_row()
    if not pipeline_row:
        print("No pipeline rows currently in shots_generating status. Nothing to do this run.")
        return

    pipeline_id = pipeline_row["id"]
    total_shots = pipeline_row["total_shots"]
    shot = get_next_pending_shot(pipeline_id)

    if not shot:
        print(f"Pipeline {pipeline_id}: no pending shots left, finalizing to video_complete.")
        bump_shots_completed(pipeline_id, total_shots, total_shots)
        return

    print(f"Pipeline {pipeline_id}: rendering shot {shot['shot_number']}/{total_shots}")
    try:
        video_url = render_shot_via_agnes(shot["scene_description"])
        mark_shot_generated(shot["id"], video_url)
        new_count = (pipeline_row.get("shots_completed") or 0) + 1
        bump_shots_completed(pipeline_id, new_count, total_shots)
        print(f"Shot {shot['shot_number']}/{total_shots} done. {total_shots - new_count} remaining.")
    except Exception as e:
        print(f"Shot {shot['shot_number']} failed this run, will retry next tick: {e}")
        mark_shot_failed(shot["id"])
        time.sleep(1)
        mark_shot_pending_again(shot["id"])


if __name__ == "__main__":
    main()
