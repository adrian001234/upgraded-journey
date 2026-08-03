"""
TechPulse - Publish Stage
Uploads each assembled final video to YouTube (public by default).
Requires YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN secrets.

FIXED (2026-08-03): this stage used to write its result only to a local
JSON file on the disposable GitHub Actions runner - never back to
Supabase. That meant video_pipeline could only ever say "video_generated"
or "failed", with no way to confirm from the database whether a video
had actually reached YouTube. Now, after each successful upload, this
stage updates that video's row directly - setting status="published",
youtube_video_id, youtube_url, and published_at - by matching on title
+ source against the most recent row still sitting at status=
"video_generated" with no youtube_video_id yet. If the Supabase update
itself fails, the upload to YouTube has still succeeded (it already
happened) - only the write-back is retried/logged as a warning, so a
Supabase hiccup can never be mistaken for a failed upload.
"""

import json
import os
import urllib.request
import urllib.error
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CLIENT_ID = os.environ["YT_CLIENT_ID"]
CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")


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


def upload_video(youtube, item):
    body = {
        "snippet": {
            "title": item["title"],
            "description": item.get("narration", "")[:4900],
            "categoryId": "28",
        },
        "status": {"privacyStatus": "public"},
    }
    media = MediaFileUpload(item["final_path"], resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response["id"]


def mark_published_in_supabase(title, source, video_id):
    """Best-effort write-back. If Supabase isn't configured or the update
    fails, this only logs a warning - it never undoes or hides the fact
    that the YouTube upload itself already succeeded."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("  SUPABASE_URL/SUPABASE_ANON_KEY not set - skipping status write-back "
              "(upload to YouTube still succeeded).")
        return

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    from datetime import datetime, timezone
    body = json.dumps({
        "status": "published",
        "youtube_video_id": video_id,
        "youtube_url": youtube_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }).encode()

    query = (
        f"title=eq.{urllib.parse.quote(title)}"
        f"&source=eq.{urllib.parse.quote(source)}"
        f"&status=eq.video_generated&youtube_video_id=is.null"
        f"&order=created_at.desc&limit=1"
    )
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?{query}",
        data=body,
        method="PATCH",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        urllib.request.urlopen(req)
        print(f"  Supabase row marked published for: {title}")
    except Exception as e:
        print(f"  WARNING: could not write publish status back to Supabase for '{title}': {e} "
              f"(the YouTube upload itself still succeeded - video_id={video_id})")


def publish_all(final_path="assembly/latest_final.json", out_path="publish/latest_published.json"):
    with open(final_path) as f:
        items = json.load(f)

    youtube = get_youtube_client()
    results = []
    for item in items:
        try:
            video_id = upload_video(youtube, item)
            results.append({**item, "youtube_video_id": video_id})
            print(f"Uploaded: {item['title']} -> {video_id}")
            mark_published_in_supabase(item.get("title", ""), item.get("source", ""), video_id)
        except Exception as e:
            print(f"Error uploading {item['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Published {len(results)} videos")


if __name__ == "__main__":
    import urllib.parse
    publish_all()
