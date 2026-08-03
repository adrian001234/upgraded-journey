"""
TechPulse - Tracking Stage
Pushes generated videos into the Supabase video_pipeline table.

FIXED (2026-08-01): this stage used to read video/latest_videos.json (the
PRE-narration, PRE-assembly per-scene clip list) and insert a row with
status hardcoded to "video_generated" regardless of whether narration,
assembly, or upload had actually happened - it never referenced the real
final video at all. Every run since the gTTS narration fix landed
(2026-07-30 onward) was writing false-success rows: status="video_generated"
with video_url left NULL, while zero files ever reached Supabase storage.

FIXED (2026-08-03): dest_name used to be built from source + list-index +
the local file's basename (e.g. "techcrunch_0_final_0.mp4"). Since every
run's assembly output is always a single-item list, i is always 0, and
assemble.py always names its output final_0.mp4 - so EVERY run for the
same source produced the exact same dest_name. Combined with x-upsert:true,
each new run silently overwrote the previous run's video at that same
storage path, so a titled row from days ago would end up pointing at
today's video (or vice versa) instead of its own file. dest_name now
includes the row's own id (generated here, before insert) so every run
gets a guaranteed-unique storage path.

Now this stage:
1. Reads assembly/latest_final.json - the REAL post-assembly output, which
   has a final_path pointing to an actual muxed video+narration mp4 on disk.
2. Uploads that file to the "videos" Supabase Storage bucket under a
   unique, per-row path.
3. Only inserts status="video_generated" (with a real, working video_url)
   if the upload actually succeeds. If assembly never produced a file, or
   the upload fails, the row is inserted as status="failed" with an error
   note instead - so the database can never again silently claim success
   for something that didn't happen.
"""

import json
import os
import mimetypes
import uuid
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET = "videos"


def upload_video_file(local_path, dest_name):
    """Uploads a local video file to the 'videos' storage bucket and
    returns its public URL, or None if the upload fails for any reason."""
    if not os.path.exists(local_path):
        print(f"  Upload skipped - file does not exist on disk: {local_path}")
        return None

    with open(local_path, "rb") as f:
        file_bytes = f.read()

    if not file_bytes:
        print(f"  Upload skipped - file is empty: {local_path}")
        return None

    content_type = mimetypes.guess_type(local_path)[0] or "video/mp4"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{dest_name}"
    req = urllib.request.Request(
        url,
        data=file_bytes,
        method="POST",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            resp.read()
        print(f"  Uploaded {local_path} -> {dest_name} ({len(file_bytes)} bytes)")
        return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{dest_name}"
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  Upload FAILED ({e.code}) for {local_path}: {body}")
        return None
    except Exception as e:
        print(f"  Upload FAILED (exception) for {local_path}: {e}")
        return None


def insert_video(record):
    body = json.dumps(record).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/video_pipeline",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    urllib.request.urlopen(req)


def sync_videos(final_path="assembly/latest_final.json"):
    if not os.path.exists(final_path):
        print(f"FATAL: {final_path} does not exist - assembly stage produced no output file at all. "
              f"Nothing to sync this run.")
        return

    with open(final_path) as f:
        items = json.load(f)

    if not items:
        print("Assembly produced an empty list - no videos to sync this run.")
        return

    success_count = 0
    fail_count = 0

    for i, item in enumerate(items):
        title = item.get("title", f"untitled_{i}")
        local_final_path = item.get("final_path")
        row_id = uuid.uuid4().hex

        video_url = None
        if local_final_path:
            ext = os.path.splitext(local_final_path)[1] or ".mp4"
            dest_name = f"{item.get('source', 'techpulse')}_{row_id}{ext}"
            video_url = upload_video_file(local_final_path, dest_name)

        record = {
            "title": title,
            "source": item.get("source", ""),
            "link": item.get("link", ""),
            "script": item.get("narration", item.get("script", "")),
        }

        if video_url:
            record["status"] = "video_generated"
            record["video_url"] = video_url
            success_count += 1
        else:
            record["status"] = "failed"
            fail_count += 1
            print(f"  '{title}' marked status=failed - no working video_url (assembly output missing, "
                  f"empty, or upload failed). This will NOT be counted as a successful video.")

        try:
            insert_video(record)
        except Exception as e:
            print(f"  Could not even insert the tracking row for '{title}': {e}")

    print(f"Synced {success_count + fail_count} rows to Supabase: "
          f"{success_count} real videos, {fail_count} marked failed (no false successes).")


if __name__ == "__main__":
    sync_videos()
