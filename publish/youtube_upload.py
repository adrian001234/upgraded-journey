"""
TechPulse - Publish Stage
Uploads each assembled final video to YouTube (unlisted by default).
Requires YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN secrets.
"""

import json
import os
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CLIENT_ID = os.environ["YT_CLIENT_ID"]
CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]


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
        "status": {"privacyStatus": "unlisted"},
    }
    media = MediaFileUpload(item["final_path"], resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response["id"]


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
        except Exception as e:
            print(f"Error uploading {item['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Published {len(results)} videos")


if __name__ == "__main__":
    publish_all()
