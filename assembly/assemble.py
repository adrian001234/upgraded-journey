"""
TechPulse - Assembly Stage (long-form, Supabase-native)
Pulls the next Supabase video_pipeline row with status='video_complete',
downloads its shot clips (video_urls) and narration audio (narration_url),
fits each clip to its own shot_durations[i] (trim if long, freeze-extend
last frame if short), concatenates, mixes in a low ambient bed under the
narration, muxes the final video, uploads it to Supabase Storage, and
updates that SAME row (by id) with video_url + status='video_generated'.

This replaces the old file-handoff design (assembly/latest_final.json ->
tracking stage inserting a NEW row) - now there is only ever one row per
video, created once by the script stage and updated in place by every
stage after, so nothing downstream ever has to match rows back together
by title/source text.

RETRY LOGIC (2026-08-05): previously any failure permanently marked the
row status='failed' with no automatic retry. Now failures requeue the
row back to status='video_complete' (so the next run picks it up again)
up to RETRY_LIMIT times, tracked via a retry_count column, before giving
up and marking it permanently failed.
"""
import json
import os
import random
import subprocess
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}
VIDEOS_BUCKET = "videos"

FINAL_DIR = "assembly/final"
TMP_DIR = "assembly/tmp"
FPS = 24

AMBIENT_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2021/11/25/audio_00fa5b4a37.mp3",
    "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8a76c3c5b.mp3",
]
AMBIENT_VOLUME = 0.12

RETRY_LIMIT = 3


def get_next_video_complete_row():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?status=eq.video_complete&order=created_at.asc&limit=1",
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def mark_failed(row_id, reason, retry_count):
    if retry_count < RETRY_LIMIT:
        next_count = retry_count + 1
        print(f"  Row {row_id} failed (attempt {next_count}/{RETRY_LIMIT}): {reason}. Requeuing as 'video_complete'.")
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
            headers=HEADERS, json={"status": "video_complete", "retry_count": next_count}, timeout=30,
        )
    else:
        print(f"  Row {row_id} failed permanently after {RETRY_LIMIT} attempts: {reason}")
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
            headers=HEADERS, json={"status": "failed"}, timeout=30,
        )


def download(url, out_path):
    resp = requests.get(url, headers={"User-Agent": "TechPulse/1.0"}, timeout=180)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


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
    url = random.choice(AMBIENT_TRACKS)
    raw_path = out_path.replace(".mp3", "_raw.mp3")
    try:
        download(url, raw_path)
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


def build_audio_track(narration_path, target_duration, out_path, row_id):
    ambient_path = f"{TMP_DIR}/ambient_{row_id}.mp3"
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


def upload_final_video(local_path, row_id):
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    dest_name = f"{row_id}.mp4"
    url = f"{SUPABASE_URL}/storage/v1/object/{VIDEOS_BUCKET}/{dest_name}"
    resp = requests.post(
        url, data=file_bytes,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "video/mp4",
            "x-upsert": "true",
        },
        timeout=300,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Final video upload failed ({resp.status_code}): {resp.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{VIDEOS_BUCKET}/{dest_name}"


def mark_video_generated(row_id, video_url):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
        headers=HEADERS,
        json={"status": "video_generated", "video_url": video_url},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to update row after assembly ({resp.status_code}): {resp.text}")


def main():
    row = get_next_video_complete_row()
    if not row:
        print("No 'video_complete' rows found. Nothing to do.")
        return

    row_id = row["id"]
    retry_count = row.get("retry_count") or 0
    title = row.get("title", "untitled")
    video_urls = row.get("video_urls") or []
    if isinstance(video_urls, str):
        video_urls = json.loads(video_urls)
    shot_durations = row.get("shot_durations") or []
    if isinstance(shot_durations, str):
        shot_durations = json.loads(shot_durations)
    narration_url = row.get("narration_url")

    if not video_urls:
        mark_failed(row_id, "no video_urls on a 'video_complete' row", retry_count)
        return
    if not narration_url:
        mark_failed(row_id, "no narration_url on this row", retry_count)
        return

    os.makedirs(FINAL_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    print(f"Assembling '{title}' ({len(video_urls)} clips)...")

    try:
        clip_paths = []
        for i, url in enumerate(video_urls):
            local_clip = f"{TMP_DIR}/clip_{row_id}_{i}.mp4"
            download(url, local_clip)
            clip_paths.append(local_clip)

        narration_path = f"{TMP_DIR}/narration_{row_id}.wav"
        download(narration_url, narration_path)

        fitted_paths = []
        for i, clip in enumerate(clip_paths):
            duration = shot_durations[i] if i < len(shot_durations) else get_duration(clip)
            fitted_path = f"{TMP_DIR}/fitted_{row_id}_{i}.mp4"
            fit_clip_to_duration(clip, duration, fitted_path)
            fitted_paths.append(fitted_path)

        concat_list_path = f"{TMP_DIR}/concat_{row_id}.txt"
        with open(concat_list_path, "w") as f:
            for p in fitted_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        concat_video_path = f"{TMP_DIR}/concat_{row_id}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
                         "-c", "copy", concat_video_path], check=True, capture_output=True)

        narration_duration = get_duration(narration_path)
        mixed_audio_path = f"{TMP_DIR}/mixed_audio_{row_id}.m4a"
        build_audio_track(narration_path, narration_duration, mixed_audio_path, row_id)

        final_path = f"{FINAL_DIR}/final_{row_id}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", concat_video_path, "-i", mixed_audio_path,
            "-c:v", "libx264", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest",
            final_path,
        ], check=True, capture_output=True)

        video_url = upload_final_video(final_path, row_id)
        mark_video_generated(row_id, video_url)
        print(f"Row {row_id}: assembled and uploaded. Status -> video_generated.")

        for p in clip_paths + fitted_paths:
            if os.path.exists(p):
                os.remove(p)
        for p in (concat_list_path, concat_video_path, mixed_audio_path, narration_path, final_path):
            if os.path.exists(p):
                os.remove(p)

    except Exception as e:
        mark_failed(row_id, f"assembly exception: {e}", retry_count)


if __name__ == "__main__":
    main()
