"""
TechPulse - Assembly Stage
Takes the real AI video clips from the Video stage (video_urls, one clip
per scene) and fits each to its share of the narration's total length -
trimming if the clip runs long, holding its final frame if it runs short -
then concatenates and muxes with the narration audio plus a low, ducked
ambient background bed (free royalty-free tracks, looped/trimmed to length)
so the final video doesn't sit dead silent under the voiceover.
"""
import json
import os
import random
import subprocess
import urllib.request

FINAL_DIR = "assembly/final"
TMP_DIR = "assembly/tmp"
FPS = 24

# Free, royalty-free, no-key-required direct download links (Pixabay Music CDN).
# Kept deliberately neutral/ambient so they sit under any story topic without
# clashing tonally.
AMBIENT_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2021/11/25/audio_00fa5b4a37.mp3",
    "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8a76c3c5b.mp3",
]
AMBIENT_VOLUME = 0.12  # relative to narration, deliberately low so it reads as atmosphere not competition


def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def fit_clip_to_duration(clip_path, target_duration, out_path):
    clip_duration = get_duration(clip_path)
    if clip_duration >= target_duration:
        subprocess.run(["ffmpeg", "-y", "-i", clip_path, "-t", str(target_duration),
                         "-c", "copy", out_path], check=True, capture_output=True)
        return

    extra = target_duration - clip_duration
    frozen_png = out_path.replace(".mp4", "_frozen.png")
    frozen_mp4 = out_path.replace(".mp4", "_frozen.mp4")

    subprocess.run([
        "ffmpeg", "-y", "-sseof", "-1", "-i", clip_path, "-update", "1", "-q:v", "2", frozen_png,
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", frozen_png,
        "-t", str(extra), "-vf", f"fps={FPS}", "-pix_fmt", "yuv420p", "-c:v", "libx264", frozen_mp4,
    ], check=True, capture_output=True)

    concat_list = out_path.replace(".mp4", "_concat.txt")
    with open(concat_list, "w") as f:
        f.write(f"file '{os.path.abspath(clip_path)}'\n")
        f.write(f"file '{os.path.abspath(frozen_mp4)}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                     "-c", "copy", out_path], check=True, capture_output=True)

    os.remove(frozen_png)
    os.remove(frozen_mp4)
    os.remove(concat_list)


def get_ambient_track(target_duration, out_path):
    """Download a random ambient track and loop/trim it to exactly target_duration.
    Returns None (caller should proceed narration-only) if the download fails -
    a missing ambient bed should never break the whole pipeline run."""
    url = random.choice(AMBIENT_TRACKS)
    raw_path = out_path.replace(".mp3", "_raw.mp3")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TechPulse/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        with open(raw_path, "wb") as f:
            f.write(data)
        subprocess.run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", raw_path,
            "-t", str(target_duration), "-c:a", "libmp3lame", out_path,
        ], check=True, capture_output=True)
        return out_path
    except Exception as e:
        print(f"  Ambient track unavailable ({e}) - proceeding with narration-only audio.")
        return None
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)


def build_audio_track(narration_path, target_duration, out_path, index):
    """Mix narration with a low, ducked ambient bed. Falls back to narration
    alone if the ambient track can't be fetched for any reason."""
    ambient_path = f"{TMP_DIR}/ambient_{index}.mp3"
    ambient = get_ambient_track(target_duration, ambient_path)

    if not ambient:
        subprocess.run(["ffmpeg", "-y", "-i", narration_path, "-c:a", "aac", out_path],
                        check=True, capture_output=True)
        return out_path

    subprocess.run([
        "ffmpeg", "-y", "-i", narration_path, "-i", ambient,
        "-filter_complex",
        f"[1:a]volume={AMBIENT_VOLUME}[amb];[0:a][amb]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]", "-c:a", "aac", out_path,
    ], check=True, capture_output=True)
    os.remove(ambient)
    return out_path


def assemble_one(clip_paths, audio_path, out_path, index):
    audio_duration = get_duration(audio_path)
    segment_duration = audio_duration / len(clip_paths)

    fitted_paths = []
    for i, clip in enumerate(clip_paths):
        fitted_path = f"{TMP_DIR}/fitted_{index}_{i}.mp4"
        fit_clip_to_duration(clip, segment_duration, fitted_path)
        fitted_paths.append(fitted_path)

    concat_list_path = f"{TMP_DIR}/concat_{index}.txt"
    with open(concat_list_path, "w") as f:
        for p in fitted_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    concat_video_path = f"{TMP_DIR}/concat_{index}.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
                     "-c", "copy", concat_video_path], check=True, capture_output=True)

    mixed_audio_path = f"{TMP_DIR}/mixed_audio_{index}.m4a"
    build_audio_track(audio_path, audio_duration, mixed_audio_path, index)

    subprocess.run([
        "ffmpeg", "-y", "-i", concat_video_path, "-i", mixed_audio_path,
        "-c:v", "libx264", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", out_path,
    ], check=True, capture_output=True)

    for p in fitted_paths:
        os.remove(p)
    os.remove(concat_list_path)
    os.remove(concat_video_path)
    if os.path.exists(mixed_audio_path):
        os.remove(mixed_audio_path)


def assemble_all(narrations_path="narration/latest_narrations.json", out_path="assembly/latest_final.json"):
    os.makedirs(FINAL_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    with open(narrations_path) as f:
        items = json.load(f)

    results = []
    for i, item in enumerate(items):
        final_path = f"{FINAL_DIR}/final_{i}.mp4"
        try:
            assemble_one(item["video_urls"], item["audio_path"], final_path, i)
            results.append({**item, "final_path": final_path})
            print(f"Assembled: {item['title']}")
        except Exception as e:
            print(f"Error assembling {item['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} final videos to {out_path}")


if __name__ == "__main__":
    assemble_all()
