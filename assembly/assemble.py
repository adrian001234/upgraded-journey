"""
TechPulse - Assembly Stage
Downloads each video clip + its narration audio, muxes them together
with ffmpeg, outputs a final assembled MP4 per script.
"""

import json
import os
import subprocess
import urllib.request

FINAL_DIR = "assembly/final"


def download(url, out_path):
    urllib.request.urlretrieve(url, out_path)


def assemble_one(video_url, audio_path, out_path):
    tmp_video = out_path.replace(".mp4", "_raw.mp4")
    download(video_url, tmp_video)

    cmd = [
        "ffmpeg", "-y",
        "-i", tmp_video,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    os.remove(tmp_video)


def assemble_all(narrations_path="narration/latest_narrations.json", out_path="assembly/latest_final.json"):
    os.makedirs(FINAL_DIR, exist_ok=True)
    with open(narrations_path) as f:
        items = json.load(f)

    results = []
    for i, item in enumerate(items):
        final_path = f"{FINAL_DIR}/final_{i}.mp4"
        try:
            assemble_one(item["video_url"], item["audio_path"], final_path)
            results.append({**item, "final_path": final_path})
            print(f"Assembled: {item['title']}")
        except Exception as e:
            print(f"Error assembling {item['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} final videos to {out_path}")


if __name__ == "__main__":
    assemble_all()
