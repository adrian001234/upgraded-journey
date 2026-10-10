"""
One-off helper: make the character reference picture for the wordless show
and save it somewhere permanent, then print its URL.

Run it once from GitHub Actions (or anywhere with the env vars below). It:
  1. asks Agnes's image model for a clean character-sheet picture,
  2. downloads it,
  3. uploads it to the existing public 'video_clips' Supabase bucket as
     refs/<name>.png (Agnes's own image links can expire),
  4. prints the permanent URL to use as the CHARACTER_REFERENCE_URL variable.

Env vars needed: SUPABASE_URL, SUPABASE_ANON_KEY, AGNES_API_KEY
Optional: CHARACTER_NAME (default "pebble"), CHARACTER_PROMPT (to override the picture prompt)
"""
import json
import os
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
AGNES_API_KEY = os.environ["AGNES_API_KEY"]

NAME = os.environ.get("CHARACTER_NAME", "pebble").strip().lower()
BUCKET = "video_clips"
AGNES_IMAGE_URL = "https://apihub.agnes-ai.com/v1/images/generations"
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
SIZE = "1920x1080"

DEFAULT_PROMPT = (
    "Pebble, a small round grey pillbug (isopod). Smooth segmented armored shell, "
    "six tiny legs, two big shiny black eyes, and ONE small orange dot in the middle of his back. "
    "Photoreal 3D animated insect, macro lens, standing on green grass in a sunny park, "
    "bright natural daylight, soft shallow depth of field, full body clearly visible, "
    "three-quarter view, character centered, nothing else in the frame."
)
PROMPT = os.environ.get("CHARACTER_PROMPT", "").strip() or DEFAULT_PROMPT

HEADERS = {
    "Authorization": f"Bearer {AGNES_API_KEY}",
    "Content-Type": "application/json",
}


def make_image():
    body = json.dumps({
        "model": AGNES_IMAGE_MODEL,
        "prompt": PROMPT,
        "size": SIZE,
        "extra_body": {"response_format": "url"},
    }).encode()
    last = None
    for attempt in range(4):
        req = urllib.request.Request(AGNES_IMAGE_URL, data=body, method="POST", headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
            print(f"Image request failed (attempt {attempt + 1}/4): {last}")
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(15 * (attempt + 1))
                continue
            raise SystemExit(f"Agnes image request failed permanently: {last}")
        for entry in data.get("data", []):
            if isinstance(entry, dict) and entry.get("url"):
                return entry["url"]
        if data.get("url"):
            return data["url"]
        raise SystemExit(f"Agnes image response had no URL: {data}")
    raise SystemExit(f"Agnes image request still failing after retries: {last}")


def upload(image_bytes):
    dest = f"refs/{NAME}.png"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{dest}",
        data=image_bytes,
        method="POST",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status >= 400:
            raise SystemExit(f"Upload failed ({resp.status})")
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{dest}"


def main():
    print("Asking Agnes for the character picture...")
    agnes_url = make_image()
    print(f"Got picture: {agnes_url}")
    image_bytes = urllib.request.urlopen(agnes_url, timeout=120).read()
    permanent_url = upload(image_bytes)
    print("")
    print("DONE. Permanent character picture URL (use as CHARACTER_REFERENCE_URL):")
    print(permanent_url)


if __name__ == "__main__":
    main()
