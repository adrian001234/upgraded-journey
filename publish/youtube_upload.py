"""
Tiny Lawn Tales - Publish Stage (Supabase-native, matched by row id)
Pulls the next Supabase video_pipeline row with status='video_generated',
downloads its video_url, uploads it to YouTube, and updates that SAME
row (by id) with status="published", youtube_video_id, youtube_url, and
published_at.

STATUS: this stage is gated in pipeline.yml behind the repo variable
YOUTUBE_READY and must stay off until the new channel is ready. It still
needs a review for the new channel: title and description, tags,
thumbnail, and the "made for kids" setting. Before any upload, confirm
which YouTube channel the refresh token is authorized for.

RETRY LOGIC: failures leave the row's status untouched (it is still
'video_generated' with youtube_video_id null, so the next run picks it up
again) and increment retry_count, up to RETRY_LIMIT times, before marking
the row permanently failed so a human notices.

TITLE LENGTH: YouTube rejects titles over 100 characters. Titles are
truncated to 100 characters at the last whole word before being sent to
YouTube. The full original title is unaffected in Supabase.

STORAGE CLEANUP: once a row is confirmed published (mark_published has
succeeded), its source video file is deleted from Supabase Storage. This is
best-effort and never raises, and it runs after mark_published so a cleanup
failure can never be mistaken for a publish failure.
"""
import os
import re
from datetime import datetime, timezone

import requests
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CLIENT_ID = os.environ["YT_CLIENT_ID"]
CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}

TMP_DIR = "publish/tmp"

RETRY_LIMIT = 3
YOUTUBE_TITLE_MAX_CHARS = 100

# Matches both public and signed Supabase Storage object URLs, e.g.
# https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>
# https://<project>.supabase.co/storage/v1/object/sign/<bucket>/<path>?token=...
STORAGE_URL_PATTERN = re.compile(r"/storage/v1/object/(?:public|sign|authenticated)/([^/]+)/([^?]+)")


def get_next_video_generated_row():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/video_pipeline"
        f"?status=eq.video_generated&youtube_video_id=is.null"
        f"&order=created_at.asc&limit=1",
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def mark_failed(row_id, reason, retry_count):
    if retry_count < RETRY_LIMIT:
        next_count = retry_count + 1
        print(f"  Row {row_id} failed (attempt {next_count}/{RETRY_LIMIT}): {reason}. Will retry next run.")
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
            headers=HEADERS, json={"retry_count": next_count}, timeout=30,
        )
    else:
        print(f"  Row {row_id} failed permanently after {RETRY_LIMIT} attempts: {reason}")
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
            headers=HEADERS, json={"status": "failed"}, timeout=30,
        )


def download(url, out_path):
    resp = requests.get(url, headers={"User-Agent": "TinyLawnTales/1.0"}, timeout=300)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


def delete_video_from_storage(video_url):
    """Parses the bucket + object path out of a Supabase Storage URL and
    deletes it via the Storage REST API. Never raises - a failed cleanup
    should never affect publish status, which is already recorded in
    Supabase by the time this runs. Silently no-ops if video_url is not a
    recognizable Supabase Storage URL."""
    if not video_url:
        return
    match = STORAGE_URL_PATTERN.search(video_url)
    if not match:
        print(f"  Storage cleanup skipped: could not parse a Supabase Storage bucket/path from {video_url}")
        return
    bucket, object_path = match.group(1), match.group(2)
    try:
        resp = requests.delete(
            f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}",
            headers=HEADERS,
            timeout=30,
        )
        if resp.status_code >= 400 and resp.status_code != 404:
            print(f"  WARNING: storage cleanup failed for {bucket}/{object_path} ({resp.status_code}): {resp.text[:300]}")
        else:
            print(f"  Deleted source video from Supabase Storage: {bucket}/{object_path}")
    except requests.RequestException as e:
        print(f"  WARNING: storage cleanup failed for {bucket}/{object_path} (network error): {e}")


def get_youtube_client():
    creds = Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
    creds.refresh(google.auth.transport.requests.Request())
    return build("youtube", "v3", credentials=creds)


def build_youtube_title(title):
    """YouTube hard-rejects titles over 100 chars. Truncate at the last
    whole word within the limit rather than cutting mid-word."""
    if len(title) <= YOUTUBE_TITLE_MAX_CHARS:
        return title
    truncated = title[:YOUTUBE_TITLE_MAX_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,.-")


def upload_to_youtube(youtube, title, description, local_path):
    body = {
        "snippet": {
            "title": build_youtube_title(title),
            "description": (description or "")[:4900],
            "categoryId": "28",
        },
        "status": {"privacyStatus": "public"},
    }
    media = MediaFileUpload(local_path, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response["id"]


def mark_published(row_id, youtube_video_id):
    youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}"
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
        headers=HEADERS,
        json={
            "status": "published",
            "youtube_video_id":
