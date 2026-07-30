"""
TechPulse - Assembly Stage
Takes the still images from the Video stage and animates each one with a
slow pan/zoom (Ken Burns effect), sized to fill an even share of the
narration's length, then concatenates and muxes with the narration audio.
"""
import json
import os
import subprocess

FINAL_DIR = "assembly/final"
TMP_DIR = "assembly/tmp"

FPS = 30
ZOOM_PER_FRAME = 0.0012  # slow, subtle zoom - avoid a seasick effect


def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def animate_image(image_path, out_path, duration_seconds):
    frames = max(int(duration_seconds * FPS), 1)
    zoompan = (
        f"zoompan=z='min(zoom+{ZOOM_PER_FRAME},1.4)':"
        f"d={frames}:s=1280x720:fps={FPS}"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", zoompan,
        "-t", str(duration_seconds),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        out_path,
    ], check=True)


def assemble_one(image_paths, audio_path, out_path, index):
    audio_duration = get_duration(audio_path)
    segment_duration = audio_duration / len(image_paths)

    clip_paths = []
    for i, img in enumerate(image_paths):
        clip_path = f"{TMP_DIR}/clip_{index}_{i}.mp4"
        animate_image(img, clip_path, segment_duration)
        clip_paths.append(clip_path)

    concat_list_path = f"{TMP_DIR}/concat_{index}.txt"
    with open(concat_list_path, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    concat_video_path = f"{TMP_DIR}/concat_{index}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        concat_video_path,
    ], check=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", concat_video_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        out_path,
    ]
    subprocess.run(cmd, check=True)

    for p in clip_paths:
        os.remove(p)
    os.remove(concat_list_path)
    os.remove(concat_video_path)


def assemble_all(narrations_path="narration/latest_narrations.json", out_path="assembly/latest_final.json"):
    os.makedirs(FINAL_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    with open(narrations_path) as f:
        items = json.load(f)

    results = []
    for i, item in enumerate(items):
        final_path = f"{FINAL_DIR}/final_{i}.mp4"
        try:
            assemble_one(item["image_urls"], item["audio_path"], final_path, i)
            results.append({**item, "final_path": final_path})
            print(f"Assembled: {item['title']}")
        except Exception as e:
            print(f"Error assembling {item['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} final videos to {out_path}")


if __name__ == "__main__":
    assemble_all()
