"""
TechPulse - Narration Stage
Converts each video's narration text into speech via FreeLLMAPI's
OpenAI-compatible /v1/audio/speech endpoint.
"""

import json
import os
import urllib.request
import urllib.error

FREELLM_URL = os.environ["FREELLM_API_URL"].replace("/chat/completions", "")
FREELLM_KEY = os.environ["FREELLM_API_KEY"]

AUDIO_DIR = "narration/audio"


def generate_narration_audio(text, out_path):
    body = json.dumps({
        "model": "auto",
        "input": text,
    }).encode()
    req = urllib.request.Request(
        f"{FREELLM_URL}/audio/speech",
        data=body,
        headers={
            "Authorization": f"Bearer {FREELLM_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code} from FreeLLMAPI audio endpoint. Body: {error_body}") from e

    with open(out_path, "wb") as f:
        f.write(audio_bytes)


def generate_all_narrations(videos_path="video/latest_videos.json", out_path="narration/latest_narrations.json"):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(videos_path) as f:
        videos = json.load(f)

    results = []
    for i, v in enumerate(videos):
        audio_path = f"{AUDIO_DIR}/narration_{i}.mp3"
        try:
            generate_narration_audio(v["narration"], audio_path)
            results.append({**v, "audio_path": audio_path})
            print(f"Narrated: {v['title']}")
        except Exception as e:
            print(f"Error narrating {v['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} narrations to {out_path}")


if __name__ == "__main__":
    generate_all_narrations()
