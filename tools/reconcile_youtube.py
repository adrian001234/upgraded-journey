"""
TechPulse - One-off Reconciliation Script (2026-08-05)

Reads every video actually on the YouTube channel (source of truth) via
the YouTube Data API, and repairs video_pipeline in Supabase to match:

- If a Supabase row exists whose (truncated) title matches a YouTube
  video, and that row's youtube_video_id is still null, fill it in.
- If no row matches at all (e.g. it was deleted, or never had a row),
  insert a new row so the video is tracked going forward.

This script NEVER deletes or modifies anything on YouTube. It only
reads from YouTube and writes to Supabase. Safe to re-run any number
of times - already-linked videos (youtube_video_id already set) are
skipped every time.
"""
import os
from datetime import datetime, timezone

import requests
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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

YOUTUBE_TITLE_MAX_CHARS = 100


def build_youtube_title(title):
    """Mirrors publish/youtube_upload.py's truncation exactly, so we can
    match a Supabase row's original title to what actually got sent to
    YouTube."""
    if len(title) <= YOUTUBE_TITLE_MAX_CHARS:
        return title
    truncated = title[:YOUTUBE_TITLE_MAX_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,.-")


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


def get_uploads_playlist_id(youtube):
    resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_all_uploaded_videos(youtube, playlist_id):
    """Returns every video on the channel: [{videoId, title, description, publishedAt}, ...]"""
    videos = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            videos.append({
                "videoId": item["contentDetails"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", ""),
                "publishedAt": item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"],
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos


def get_existing_rows():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?select=id,title,youtube_video_id",
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def patch_row(row_id, youtube_video_id, youtube_url, published_at):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
        headers=HEADERS,
        json={
            "status": "published",
            "youtube_video_id": youtube_video_id,
            "youtube_url": youtube_url,
            "published_at": published_at,
        },
        timeout=30,
    )
    resp.raise_for_status()


def insert_row(title, description, youtube_video_id, youtube_url, published_at):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/video_pipeline",
        headers=HEADERS,
        json={
            "title": title,
            "source": "reconciled_from_youtube",
            "script": description,
            "status": "published",
            "youtube_video_id": youtube_video_id,
            "youtube_url": youtube_url,
            "published_at": published_at,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main():
    youtube = get_youtube_client()
    playlist_id = get_uploads_playlist_id(youtube)
    yt_videos = list_all_uploaded_videos(youtube, playlist_id)
    print(f"Found {len(yt_videos)} videos on the actual YouTube channel.")

    existing_rows = get_existing_rows()
    already_linked_ids = {r["youtube_video_id"] for r in existing_rows if r.get("youtube_video_id")}
    unlinked_rows_by_title = {
        build_youtube_title(r["title"]): r["id"]
        for r in existing_rows if not r.get("youtube_video_id") and r.get("title")
    }

    matched, inserted, skipped = 0, 0, 0

    for v in yt_videos:
        if v["videoId"] in already_linked_ids:
            skipped += 1
            continue

        youtube_url = f"https://www.youtube.com/watch?v={v['videoId']}"

        if v["title"] in unlinked_rows_by_title:
            row_id = unlinked_rows_by_title[v["title"]]
            patch_row(row_id, v["videoId"], youtube_url, v["publishedAt"])
            print(f"  MATCHED existing row -> {v['title']}")
            matched += 1
        else:
            insert_row(v["title"], v["description"], v["videoId"], youtube_url, v["publishedAt"])
            print(f"  INSERTED new row -> {v['title']}")
            inserted += 1

    print(f"\nDone. Already tracked: {skipped}. Matched to existing rows: {matched}. Newly inserted: {inserted}.")


if __name__ == "__main__":
    main()
