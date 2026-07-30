"""
TechPulse - Video Stage
Generates one still image per scene using Pollinations (free, no API key,
no billing). Assembly stage animates each image with a pan/zoom effect
to build the final video, so no paid text-to-video model is needed.
"""
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

IMAGE_BASE_URL = "https://image.pollinations.ai/prompt/"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720

MAX_SCENE_RETRIES = 4
SCENE_DELAY_SECONDS = 16  # Pollinations' anonymous tier is rate-capped to ~1 req/15s
RETRY_BACKOFF_BASE_SECONDS = 10

# Front-loaded style cue applied to every scene. Change this one string to
# switch the whole channel's visual identity.
STYLE_CUE = (
    "Flat 2D vector motion-graphic illustration, clean flat colors, "
    "bold simple shapes, no photorealism, no live-action, no 3D render. "
)

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


def build_image_prompt(scene):
    """Prepend a strong, front-loaded style + lighting cue to every scene
    prompt. Front-loading matters because prompt weighting favors earlier
    tokens."""
    is_intentionally_dark = any(word in scene.lower() for word in DARK_SCENE_KEYWORDS)
    if is_intentionally_dark:
        lighting_cue = "Moody, intentionally low-light scene as part of the story. "
    else:
        lighting_cue = (
            "Brightly and evenly lit scene, no underexposure, no murky shadows. "
        )
    return STYLE_CUE + lighting_cue + scene


def fetch_image(prompt, out_path, seed):
    encoded = urllib.parse.quote(prompt, safe="")
    url = (
        f"{IMAGE_BASE_URL}{encoded}"
        f"?width={IMAGE_WIDTH}&height={IMAGE_HEIGHT}&seed={seed}&nologo=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "TechPulse/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
    if len(data) < 1000:
        # Pollinations returns a tiny error/placeholder image on failure
        # rather than an HTTP error status in some cases.
        raise RuntimeError(f"Pollinations returned a suspiciously small image ({len(data)} bytes)")
    with open(out_path, "wb") as f:
        f.write(data)


def generate_scene_image(scene, title, out_path, seed):
    prompt = build_image_prompt(scene)
    for attempt in range(1, MAX_SCENE_RETRIES + 1):
        try:
            fetch_image(prompt, out_path, seed)
            return True
        except urllib.error.HTTPError as e:
            wait = RETRY_BACKOFF_BASE_SECONDS * attempt
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: HTTP {e.code}")
            log_debug("video", f"HTTP {e.code} for {title} scene image, attempt {attempt}")
        except Exception as e:
            wait = RETRY_BACKOFF_BASE_SECONDS * attempt
            print(f"  Attempt {attempt}/{MAX_SCENE_RETRIES} error on a scene for {title}: {e}")
            log_debug("video", f"Attempt {attempt} exception for {title}: {e}")
        if attempt < MAX_SCENE_RETRIES:
            time.sleep(wait)
    return False


def generate_videos(scripts_path="script/latest_scripts.json", out_path="video/latest_videos.json"):
    """Kept the name generate_videos()/latest_videos.json so pipeline.yml
    and downstream stages don't need to change - the output now contains
    image_urls (local file paths) instead of clip_urls."""
    with open(scripts_path) as f:
        scripts = json.load(f)

    os.makedirs("video/images", exist_ok=True)
    videos = []
    for s_idx, s in enumerate(scripts):
        expected = len(s["scenes"])
        image_paths = []
        for i, scene in enumerate(s["scenes"]):
            if i > 0:
                time.sleep(SCENE_DELAY_SECONDS)
            out_path = f"video/images/scene_{s_idx}_{i}.jpg"
            seed = abs(hash((s["title"], i))) % 1_000_000
            ok = generate_scene_image(scene, s["title"], out_path, seed)
            if ok:
                image_paths.append(out_path)
                print(f"  Generated scene image for: {s['title']}")
            else:
                print(f"  Giving up on a scene for: {s['title']} after {MAX_SCENE_RETRIES} retries")

        if len(image_paths) == expected:
            videos.append({**s, "image_urls": image_paths})
            print(f"Generated {len(image_paths)}/{expected} images for: {s['title']}")
        else:
            print(f"SKIPPING '{s['title']}': only {len(image_paths)}/{expected} scenes succeeded")
            log_debug("video", f"SKIPPING '{s['title']}': only {len(image_paths)}/{expected} scenes succeeded")

    with open(out_path, "w") as f:
        json.dump(videos, f, indent=2)
    print(f"Saved {len(videos)} videos to {out_path}")


if __name__ == "__main__":
    generate_videos()
