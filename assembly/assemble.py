"""
TechPulse - Assembly Stage
Takes the real AI video clips from the Video stage (video_urls, one clip
per scene) and fits each to its share of the narration's total length -
trimming if the clip runs long, holding its final frame if it runs short -
then concatenates and muxes with the narration audio. Replaces the old
still-image + Ken-Burns pan/zoom approach now that Video stage generates
real motion clips.
"""
import json
import os
import subprocess

FINAL_DIR = "assembly/final"
TMP_DIR = "assembly/tmp"
FPS = 24


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

    subprocess.run([
        "ffmpeg", "-y", "-i", concat_video_path, "-i", audio_path,
        "-c:v", "libx264", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", out_path,
    ], check=True, capture_output=True)

    for p in fitted_paths:
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
    
