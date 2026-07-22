"""
TechPulse - Video Stage
Sends each script's visual description to Agnes AI for video generation
using pre-claimed free credits. Narration text is carried through for the
upcoming narration/assembly stages.
"""

import json
import os
import time
import urllib.request

AGNES_URL = os.environ["AGNES_API_URL"]
AGNES_KEY = os.environ["AGNES_API_KEY"]


def create_agnes_task(visual_prompt):
    body = json.dumps({
        "model": "agnes-video-v2.0",
        "prompt": visual_prompt,
        "num_frames": 121,
        "frame_rate": 24,
    }).encode()
    req = urllib.request.Request(
        f"{AGNES_URL}/videos",
        data=body,
        headers={
            "Authorization": f"Bearer {AGNES_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["video_id"]


def poll_agnes_task(video_id, max_retries=20, delay=15):
    base = AGNES_URL.replace("/v1", "")
    for _ in range(max_retries):
        req = urllib.request.Request(
            f"{base}/agnesapi?video_id={video_id}",
            headers={"Authorization": f"Bearer {AGNES_KEY}"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            if result.get("status") == "completed":
                return result.get("video_url") or result.get("url")
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
            video_id = create_agnes_task(s["visual"])
            video_url = poll_agnes_task(video_id)
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
