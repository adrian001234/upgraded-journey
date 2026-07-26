"""
TechPulse - Video Stage
Sends each scene's visual description to Agnes AI for video generation
using pre-claimed free credits. Produces one clip per scene.
"""
import json
import os
import time
import urllib.request
import urllib.error

AGNES_URL = os.environ["AGNES_API_URL"]
AGNES_KEY = os.environ["AGNES_API_KEY"]

MAX_SCENE_RETRIES = 3
SCENE_DELAY_SECONDS = 5  # pause between scenes so we don't burst Agnes and trip rate limits
RETRY_BACKOFF_BASE_SECONDS = 8  # exponential backoff between retry attempts on the same scene


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


def generate_scene_clip(scene, title):
    """Try up to MAX_SCENE_RETRIES times to generate one scene's clip, backing off between attempts."""
    for attempt in range(1, MAX_SCENE_RETRIES + 1):
        try:
            video_id = create_agnes_task(scene)
            clip_url = poll_agnes_task(video_id)
            if clip_url:
                return clip_url
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} failed/timed out on a scene for: {title}")
        except urllib.error.HTTPError as e:
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: HTTP Error {e.code}: {e.reason}")
        except Exception as e:
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: {e}")

        if attempt < MAX_SCENE_RETRIES:
            backoff = RETRY_BACKOFF_BASE_SECONDS * attempt
            time.sleep(backoff)
    return None


def generate_videos(scripts_path="script/latest_scripts.json", out_path="video/latest_videos.json"):
    with open(scripts_path) as f:
        scripts = json.load(f)

    videos = []
    for s in scripts:
        expected = len(s["scenes"])
        clip_urls = []
        for i, scene in enumerate(s["scenes"]):
            if i > 0:
                time.sleep(SCENE_DELAY_SECONDS)
            clip_url = generate_scene_clip(scene, s["title"])
            if clip_url:
                clip_urls.append(clip_url)
                print(f"  Generated scene clip for: {s['title']}")
            else:
                print(f"  Giving up on a scene for: {s['title']} after {MAX_SCENE_RETRIES} retries")

        if len(clip_urls) == expected:
            videos.append({**s, "clip_urls": clip_urls})
            print(f"Generated {len(clip_urls)}/{expected} clips for: {s['title']}")
        else:
            print(f"SKIPPING '{s['title']}': only {len(clip_urls)}/{expected} scenes succeeded — "
                  f"not sending a short/looped video to assembly")

    with open(out_path, "w") as f:
        json.dump(videos, f, indent=2)
    print(f"Saved {len(videos)} videos to {out_path}")


if __name__ == "__main__":
    generate_videos()
