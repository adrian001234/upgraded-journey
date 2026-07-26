"""
TechPulse - Video Stage
Sends each scene's visual description to Kie.ai's HappyHorse-1.1
text-to-video API. Produces one clip per scene.
"""
import json
import os
import time
import urllib.request
import urllib.error

KIE_KEY = os.environ["KIE_API_KEY"]
CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

MAX_SCENE_RETRIES = 3
SCENE_DELAY_SECONDS = 5
RETRY_BACKOFF_BASE_SECONDS = 8


def create_task(prompt):
    body = json.dumps({
        "model": "happyhorse-1-1/text-to-video",
        "input": {
            "prompt": prompt,
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "duration": 5,
        },
    }).encode()
    req = urllib.request.Request(
        CREATE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {KIE_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["data"]["taskId"]


def poll_task(task_id, max_retries=20, delay=15):
    for _ in range(max_retries):
        req = urllib.request.Request(
            f"{STATUS_URL}?taskId={task_id}",
            headers={"Authorization": f"Bearer {KIE_KEY}"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            data = result.get("data", {})
            state = data.get("state")
            if state == "success":
                result_json = json.loads(data.get("resultJson", "{}"))
                urls = result_json.get("resultUrls", [])
                return urls[0] if urls else None
            if state == "fail":
                return None
        time.sleep(delay)
    return None


def generate_scene_clip(scene, title):
    for attempt in range(1, MAX_SCENE_RETRIES + 1):
        try:
            task_id = create_task(scene)
            clip_url = poll_task(task_id)
            if clip_url:
                return clip_url
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} failed/timed out on a scene for: {title}")
        except urllib.error.HTTPError as e:
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: HTTP Error {e.code}: {e.reason}")
        except Exception as e:
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: {e}")
        if attempt < MAX_SCENE_RETRIES:
            time.sleep(RETRY_BACKOFF_BASE_SECONDS * attempt)
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
            print(f"SKIPPING '{s['title']}': only {len(clip_urls)}/{expected} scenes succeeded")

    with open(out_path, "w") as f:
        json.dump(videos, f, indent=2)
    print(f"Saved {len(videos)} videos to {out_path}")


if __name__ == "__main__":
    generate_videos()
