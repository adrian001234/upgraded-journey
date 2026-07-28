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

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

MAX_SCENE_RETRIES = 5
SCENE_DELAY_SECONDS = 5
RETRY_BACKOFF_BASE_SECONDS = 8
RATE_LIMIT_BACKOFF_SECONDS = 45  # used for 429 / 503, which mean "slow down / try later"

# Tracks how many scenes failed due to 429/503 in this run, across all videos
RATE_LIMIT_FAILURE_COUNT = 0

# Scene text containing any of these words is treated as an intentionally
# dark/night shot and is left alone instead of being forced bright.
DARK_SCENE_KEYWORDS = (
    "night", "nighttime", "dark", "dim", "shadow", "shadowy",
    "moonlit", "midnight", "dusk", "candlelit", "silhouette",
)


def log_debug(stage, message):
    """Best-effort write of a diagnostic line to Supabase pipeline_debug,
    so failures are visible without needing GitHub Actions log access.
    Never raises - a logging failure must not break the pipeline."""
    print(f"  [debug] {stage}: {message}")
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return
    try:
        body = json.dumps({"stage": stage, "message": str(message)[:2000]}).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/pipeline_debug",
            data=body,
            method="POST",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def build_video_prompt(scene):
    """Prepend a strong, front-loaded lighting cue to every scene prompt.
    Text-to-video models weight earlier tokens more heavily, so the
    lighting instruction goes FIRST, not appended at the end."""
    is_intentionally_dark = any(word in scene.lower() for word in DARK_SCENE_KEYWORDS)
    if is_intentionally_dark:
        lighting_cue = "Moody, intentionally low-light scene as part of the story. "
    else:
        lighting_cue = (
            "Brightly and evenly lit scene, strong natural daylight or bright "
            "clean interior lighting, no underexposure, no murky shadows. "
        )
    return lighting_cue + scene


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
        raw = resp.read()
    try:
        result = json.loads(raw)
        code = result.get("code")
        data = result.get("data") or {}
        if code not in (200, None) or not data or "taskId" not in data:
            msg = result.get("msg") or result.get("message") or "no message"
            raise RuntimeError(f"Kie.ai rejected the task (code={code}, msg={msg}, raw={json.dumps(result)[:300]})")
        return data["taskId"]
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Kie.ai createTask response wasn't in the expected shape ({e}). Raw body: {raw[:500]!r}") from e


def poll_task(task_id, max_retries=20, delay=15):
    for _ in range(max_retries):
        req = urllib.request.Request(
            f"{STATUS_URL}?taskId={task_id}",
            headers={"Authorization": f"Bearer {KIE_KEY}"},
        )
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
        try:
            result = json.loads(raw)
            data = result.get("data") or {}
            state = data.get("state")
            if state == "success":
                result_json = json.loads(data.get("resultJson") or "{}")
                urls = result_json.get("resultUrls", [])
                return urls[0] if urls else None
            if state == "fail":
                fail_msg = data.get("failMsg") or data.get("msg") or "no failure message provided"
                print(f"  Kie.ai task {task_id} failed: {fail_msg}")
                log_debug("video", f"Kie.ai task {task_id} state=fail: {fail_msg}")
                return None
        except Exception as e:
            print(f"  Kie.ai poll response for task {task_id} wasn't in the expected shape ({e}). Raw body: {raw[:500]!r}")
            log_debug("video", f"poll_task bad response shape for {task_id}: {e}. Raw: {raw[:300]!r}")
            return None
        time.sleep(delay)
    log_debug("video", f"poll_task timed out after {max_retries} retries for task {task_id}")
    return None


def generate_scene_clip(scene, title):
    global RATE_LIMIT_FAILURE_COUNT
    prompt = build_video_prompt(scene)
    for attempt in range(1, MAX_SCENE_RETRIES + 1):
        try:
            task_id = create_task(prompt)
            clip_url =
