"""
TechPulse - Narration Stage
Converts each vide"""
TechPulse - Narration Stage
Converts each video's narration text into speech via Edge TTS (Microsoft's free, natural-sounding TTS).
Voice: en-US-GuyNeural (male, upbeat/confident), sped up slightly for a punchier, more energetic read.
Also captures real word-level timing from Edge TTS's WordBoundary events and writes an SRT caption
file grouped into short on-screen chunks - 85% of Shorts are watched muted, so burned-in captions
are treated as required output, not a nice-to-have.
"""

import asyncio
import json
import os
import edge_tts

AUDIO_DIR = "narration/audio"
VOICE = "en-US-GuyNeural"
RATE = "+8%"
PITCH = "+0Hz"
WORDS_PER_CAPTION_CHUNK = 4  # short, punchy on-screen groups - easy to read at a glance on vertical video


def format_srt_timestamp(ticks):
    """Edge TTS WordBoundary offsets/durations are in 100-nanosecond units."""
    total_ms = ticks / 10000
    hours = int(total_ms // 3600000)
    total_ms %= 3600000
    minutes = int(total_ms // 60000)
    total_ms %= 60000
    seconds = int(total_ms // 1000)
    millis = int(total_ms % 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


async def generate_narration_audio_and_captions(text, audio_out_path, srt_out_path):
    communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE, pitch=PITCH)
    word_boundaries = []
    with open(audio_out_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append(chunk)

    if not word_boundaries:
        # Fallback: no timing data available, skip captions for this item rather than fail the run
        return False

    srt_lines = []
    index = 1
    for i in range(0, len(word_boundaries), WORDS_PER_CAPTION_CHUNK):
        group = word_boundaries[i:i + WORDS_PER_CAPTION_CHUNK]
        start_ticks = group[0]["offset"]
        last = group[-1]
        end_ticks = last["offset"] + last["duration"]
        caption_text = "".join(w["text"] + (" " if not w["text"].endswith((",", ".", "?", "!")) else " ")
                                for w in group).strip()
        srt_lines.append(str(index))
        srt_lines.append(f"{format_srt_timestamp(start_ticks)} --> {format_srt_timestamp(end_ticks)}")
        srt_lines.append(caption_text)
        srt_lines.append("")
        index += 1

    with open(srt_out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    return True


def generate_all_narrations(videos_path="video/latest_videos.json", out_path="narration/latest_narrations.json"):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(videos_path) as f:
        videos = json.load(f)

    results = []
    for i, v in enumerate(videos):
        audio_path = f"{AUDIO_DIR}/narration_{i}.mp3"
        srt_path = f"{AUDIO_DIR}/narration_{i}.srt"
        try:
            has_captions = asyncio.run(
                generate_narration_audio_and_captions(v["narration"], audio_path, srt_path)
            )
            item = {**v, "audio_path": audio_path}
            if has_captions:
                item["captions_path"] = srt_path
            else:
                print(f"  No word-timing data returned for '{v['title']}' - proceeding without captions.")
            results.append(item)
            print(f"Narrated: {v['title']}")
        except Exception as e:
            print(f"Error narrating {v['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} narrations to {out_path}")


if __name__ == "__main__":
    generate_all_narrations()o's narration text into speech via Edge TTS (Microsoft's free, natural-sounding TTS).
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
