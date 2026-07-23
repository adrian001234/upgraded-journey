"""
TechPulse - Assembly Stage
Downloads all scene clips for each script, concatenates them in order,
muxes the result with the narration audio, outputs a final MP4.
"""
import json
import os
import subprocess
import urllib.request

FINAL_DIR = "assembly/final"
TMP_DIR = "assembly/tmp"


def download(url, out_path):
    urllib.request.urlretrieve(url, out_path)


def assemble_one(clip_urls, audio_path, out_path, index):
    clip_paths = []
    for i, url in enumerate(clip_urls):
        clip_path = f"{TMP_DIR}/clip_{index}_{i}.mp4"
        download(url, clip_path)
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
        "-c", "libx264",
        concat_video_path,
    ], check=True)

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
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
            assemble_one(item["clip_urls"], item["audio_path"], final_path, i)
            results.append({**item, "final_path": final_path})
            print(f"Assembled: {item['title']}")
        except Exception as e:
            print(f"Error assembling {item['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} final videos to {out_path}")


if __name__ == "__main__":
    assemble_all()
