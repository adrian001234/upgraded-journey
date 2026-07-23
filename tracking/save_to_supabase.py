"""
TechPulse - Tracking Stage
Pushes generated videos into the Supabase video_pipeline table.
"""

import json
import os
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]


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


def sync_videos(videos_path="video/latest_videos.json"):
    with open(videos_path) as f:
        videos = json.load(f)

    count = 0
    for v in videos:
        try:
            insert_video({
                "title": v["title"],
                "source": v["source"],
                "link": v["link"],
                "script": v.get("narration", ""),
                "video_url": v["video_url"],
                "status": "video_generated",
            })
            count += 1
        except Exception as e:
            print(f"Failed to sync {v['title']}: {e}")

    print(f"Synced {count} videos to Supabase")


if __name__ == "__main__":
    sync_videos()
