"""
Tiny Lawn Tales - Assembly storage and database calls (the ONLY file that talks
to Supabase for the assembly stage).

To move clip and video storage to Backblaze B2 later, change download() and
upload_final_video() here and nothing else.
"""
import requests
import os

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}
VIDEOS_BUCKET = "videos"
RETRY_LIMIT = 3


def get_next_video_complete_row():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?status=eq.video_complete&order=created_at.asc&limit=1",
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def mark_failed(row_id, reason, retry_count):
    if retry_count < RETRY_LIMIT:
        print(f"  Row {row_id} failed (attempt {retry_count + 1}/{RETRY_LIMIT}): {reason}. Requeuing.")
        body = {"status": "video_complete", "retry_count": retry_count + 1}
    else:
        print(f"  Row {row_id} failed permanently after {RETRY_LIMIT} attempts: {reason}")
        body = {"status": "failed"}
    requests.patch(f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
                   headers=HEADERS, json=body, timeout=30)


def download(url, out_path):
    resp = requests.get(url, headers={"User-Agent": "TinyLawnTales/1.0"}, timeout=180)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


def upload_final_video(local_path, row_id):
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    dest_name = f"{row_id}.mp4"
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{VIDEOS_BUCKET}/{dest_name}", data=file_bytes,
        headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                 "Content-Type": "video/mp4", "x-upsert": "true"},
        timeout=300,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Final video upload failed ({resp.status_code}): {resp.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{VIDEOS_BUCKET}/{dest_name}"


def mark_video_generated(row_id, video_url):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}", headers=HEADERS,
        json={"status": "video_generated", "video_url": video_url}, timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to update row after assembly ({resp.status_code}): {resp.text}")
