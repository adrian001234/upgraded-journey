"""
TechPulse - Narration Stage
Converts each video's narration text into speech via Edge TTS (Microsoft's free, natural-sounding TTS).
Voice: en-US-GuyNeural (male, upbeat/confident), sped up slightly for a punchier, more energetic read.
"""

import asyncio
import json
import os
import edge_tts

AUDIO_DIR = "narration/audio"
VOICE = "en-US-GuyNeural"
RATE = "+8%"
PITCH = "+0Hz"


async def generate_narration_audio(text, out_path):
    communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(out_path)


def generate_all_narrations(videos_path="video/latest_videos.json", out_path="narration/latest_narrations.json"):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(videos_path) as f:
        videos = json.load(f)

    results = []
    for i, v in enumerate(videos):
        audio_path = f"{AUDIO_DIR}/narration_{i}.mp3"
        try:
            asyncio.run(generate_narration_audio(v["narration"], audio_path))
            results.append({**v, "audio_path": audio_path})
            print(f"Narrated: {v['title']}")
        except Exception as e:
            print(f"Error narrating {v['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} narrations to {out_path}")


if __name__ == "__main__":
    generate_all_narrations()
