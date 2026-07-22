"""
TechPulse - Video Stage
Sends each script to Agnes AI for video generation using pre-claimed free credits.
"""

import json
import os
import time
import urllib.request

AGNES_URL = os.environ["AGNES_API_URL"]
AGNES_KEY = os.environ["AGNES_API_KEY"]


def create_agnes_task(script_text):
    body = json.dumps({
        "prompt": script_text,
        "duration": 40,
    }).encode()
    req = urllib.request.Request(
        f"{AGNES_URL}/v1/video/generate",
        data=body,
        headers={
            "Authorization": f"Bearer {AGNES_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["task_id"]


def poll_agnes_task(task_id, max_retries=20, delay=15):
    for _ in range(max_retries):
        req = urllib.request.Request(
            f"{AGNES_URL}/v1/video/status/{task_id}",
            headers={"Authorization": f"Bearer {AGNES_KEY}"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            if result.get("status") == "completed":
                return result.get("video_url")
            if result.get("status") == "failed":
                return None
        time.sleep(delay)
    return None


def generate_videos(scripts_path="script/latest_scripts.json", out_path="video/latest_videos.json"):
    with open(scripts_path) as f:
        scripts = json.load(f)

    videos = []
    for s in scripts:
        try:
            task_id = create_agnes_task(s["script"])
            video_url = poll_agnes_task(task_id)
            if video_url:
                videos.append({**s, "video_url": video_url})
                print(f"Generated video for: {s['title']}")
            else:
                print(f"Failed/timed out: {s['title']}")
        except Exception as e:
            print(f"Error on {s['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(videos, f, indent=2)
    print(f"Saved {len(videos)} videos to {out_path}")


if __name__ == "__main__":
    generate_videos()
