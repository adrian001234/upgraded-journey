"""
TechPulse - Publish Stage (Supabase-native, matched by row id)
Pulls the next Supabase video_pipeline row with status='video_generated',
downloads its video_url, uploads it to YouTube, and updates that SAME
row (by id) with status="published", youtube_video_id, youtube_url, and
published_at.

FIXED (2026-08-04): the old version matched rows back together by
title + source TEXT after the fact, which is exactly the kind of match
that silently breaks on whitespace/truncation differences - the likely
cause of the previous publish/tracking discrepancy (YOUTUBE_READY=true
for weeks with zero published rows despite at least one real upload).
Now that every row has had a single stable id since the script stage
created it, there is no text matching involved at all - this stage reads
the row's own id and writes back to that exact id, full stop.
"""
import os
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


def mark_failed(row_id, reason):
    print(f"  Marking row {row_id} failed: {reason}")
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
        headers=HEADERS, json={"status": "failed"}, timeout=30,
    )


def download(url, out_path):
    resp = requests.get(url, headers={"User-Agent": "TechPulse/1.0"}, timeout=300)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


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


def upload_to_youtube(youtube, title, description, local_path):
    body = {
        "snippet": {
            "title": title,
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
            "youtube_video_id": youtube_video_id,
            "youtube_url": youtube_url,
            "published_at": datetime.now(timezone.utc).isoformat(),
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"  WARNING: could not write publish status back to Supabase for row {row_id} "
              f"({resp.status_code}): {resp.text} - youtube_video_id={youtube_video_id} "
              f"(the YouTube upload itself still succeeded).")
    else:
        print(f"  Row {row_id} marked published in Supabase.")


def main():
    row = get_next_video_generated_row()
    if not row:
        print("No 'video_generated' rows ready to publish. Nothing to do.")
        return

    row_id = row["id"]
    title = row.get("title", "untitled")
    narration_text = row.get("script", "")
    video_url = row.get("video_url")

    if not video_url:
        mark_failed(row_id, "video_generated row has no video_url")
        return

    os.makedirs(TMP_DIR, exist_ok=True)
    local_path = f"{TMP_DIR}/{row_id}.mp4"

    try:
        print(f"Downloading final video for '{title}'...")
        download(video_url, local_path)

        youtube = get_youtube_client()
        print(f"Uploading '{title}' to YouTube...")
        youtube_video_id = upload_to_youtube(youtube, title, narration_text, local_path)
        print(f"Uploaded: {title} -> {youtube_video_id}")

        mark_published(row_id, youtube_video_id)

    except Exception as e:
        print(f"ERROR publishing '{title}' (row {row_id}): {e}")
        raise
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


if __name__ == "__main__":
    main()
