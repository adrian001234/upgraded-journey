"""
TechPulse - Video Stage
Sends each scene's visual description to Kie.ai's HappyHorse-1.1
text-to-video API. Produces one clip per scene.
"""
import json
import os
import random
import time
import urllib.request
import urllib.error

KIE_KEY = os.environ["KIE_API_KEY"]
CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

MAX_SCENE_RETRIES = 5
SCENE_DELAY_SECONDS = 5
RETRY_BACKOFF_BASE_SECONDS = 8
RATE_LIMIT_BACKOFF_SECONDS = 45  # used for 429 / 503, which mean "slow down / try later"

# Tracks how many scenes failed due to 429/503 in this run, across all videos
RATE_LIMIT_FAILURE_COUNT = 0


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
        code = result.get("code")
        data = result.get("data")
        if code not in (200, None) or not data or "taskId" not in data:
            msg = result.get("msg") or result.get("message") or "no message"
            raise RuntimeError(f"Kie.ai rejected the task (code={code}, msg={msg}, raw={json.dumps(result)[:300]})")
        return data["taskId"]


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
                fail_msg = data.get("failMsg") or data.get("msg") or "no failure message provided"
                print(f"  Kie.ai task {task_id} failed: {fail_msg}")
                return None
        time.sleep(delay)
    return None


def generate_scene_clip(scene, title):
    global RATE_LIMIT_FAILURE_COUNT
    for attempt in range(1, MAX_SCENE_RETRIES + 1):
        try:
            task_id = create_task(scene)
            clip_url = poll_task(task_id)
            if clip_url:
                return clip_url
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} failed/timed out on a scene for: {title}")
            wait = RETRY_BACKOFF_BASE_SECONDS * attempt
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                RATE_LIMIT_FAILURE_COUNT += 1
                reason = "rate limited" if e.code == 429 else "Kie.ai service unavailable"
                wait = RATE_LIMIT_BACKOFF_SECONDS * attempt + random.uniform(0, 10)
                print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: "
                      f"HTTP {e.code} ({reason}) - waiting {wait:.0f}s before retry")
            elif e.code in (401, 402):
                # Auth or billing problem - retrying won't help, fail fast
                print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: "
                      f"HTTP {e.code} - this means either your KIE_API_KEY is invalid (401) "
                      f"or your Kie.ai account balance is too low (402). Check the Kie.ai dashboard.")
                return None
            else:
                wait = RETRY_BACKOFF_BASE_SECONDS * attempt
                print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: HTTP Error {e.code}: {e.reason}")
        except Exception as e:
            wait = RETRY_BACKOFF_BASE_SECONDS * attempt
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: {e}")
        if attempt < MAX_SCENE_RETRIES:
            time.sleep(wait)
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

    if RATE_LIMIT_FAILURE_COUNT > 0:
        print(f"\nNOTE: {RATE_LIMIT_FAILURE_COUNT} scene attempt(s) failed with 429/503 this run. "
              f"This almost always means your Kie.ai account is low on balance/credits or Kie.ai's "
              f"servers were temporarily down - it is not a code problem. Check "
              f"https://kie.ai account balance before the next run.")


if __name__ == "__main__":
    generate_videos()
