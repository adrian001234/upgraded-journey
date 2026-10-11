"""
Tiny Lawn Tales - Assembly Stage (music and sound effects, no narration)

Takes the oldest video_pipeline row with status='video_complete', downloads its
shot clips (video_urls), makes every clip exactly shot_durations[i] long (cut if
long, last frame held if short), joins them, adds a soft music bed and the
cartoon sound effects named in each shot's "sound" text (see sound.py), uploads
the final video and updates that SAME row: video_url + status='video_generated'.

The sound that Agnes puts inside its clips is thrown away on purpose. This show
is wordless and every sound is placed by us.

Rewritten 2026-10-11. The old version needed narration_url and always failed.

RETRY LOGIC: a failure puts the row back to 'video_complete' up to RETRY_LIMIT
times (retry_count column), then marks it 'failed'.

Storage note: store.download() and store.upload_final_video() are the only two places that
touch Supabase Storage, so moving them to Backblaze B2 later changes only those.
"""
import json
import os
import subprocess

import sound
import store

FINAL_DIR = "assembly/final"
TMP_DIR = "assembly/tmp"

WIDTH, HEIGHT, FPS = 1280, 720, 24
MUSIC_VOLUME = 0.35      # music bed under everything
EFFECT_VOLUME = 1.0
EFFECT_OFFSET = 0.4      # seconds after a shot starts when its first effect plays
EFFECT_SPACING = 0.35    # seconds between two effects in the same shot


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def get_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", path],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def normalize_clip(clip_path, target, out_path):
    """One clip -> exactly `target` seconds, 1280x720, 24 fps, no audio."""
    extra = max(0.0, target - get_duration(clip_path))
    vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={WIDTH}:{HEIGHT},fps={FPS}")
    if extra > 0:
        vf += f",tpad=stop_mode=clone:stop_duration={extra:.3f}"
    vf += ",format=yuv420p"
    run(["ffmpeg", "-y", "-i", clip_path, "-an", "-vf", vf, "-t", f"{target:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out_path])


def build_video(clip_paths, durations, work, out_path):
    parts = []
    for i, (clip, dur) in enumerate(zip(clip_paths, durations)):
        part = os.path.join(work, f"part_{i:03d}.mp4")
        normalize_clip(clip, dur, part)
        parts.append(part)
    list_path = os.path.join(work, "concat.txt")
    with open(list_path, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    return parts + [list_path]


def build_audio(durations, sounds, work, out_path):
    """Music bed plus every shot's sound effects at the right moment."""
    total = sum(durations)
    cmd = ["ffmpeg", "-y", "-i", sound.make_music(total, work)]
    filters, labels, start = [], [], 0.0
    for dur, text in zip(durations, sounds):
        for k, name in enumerate(sound.sounds_for_shot(text)):
            at = start + EFFECT_OFFSET + k * EFFECT_SPACING
            if at >= total:
                continue
            cmd += ["-i", sound.make_effect(name, work)]
            n = len(labels) + 1
            ms = int(at * 1000)
            filters.append(f"[{n}:a]adelay={ms}:all=1,volume={EFFECT_VOLUME}[e{n}]")
            labels.append(f"[e{n}]")
        start += dur
    mix = f"[0:a]volume={MUSIC_VOLUME}[m]"
    if labels:
        mix += ";" + ";".join(filters)
        mix += f";[m]{''.join(labels)}amix=inputs={len(labels) + 1}:normalize=0:duration=first,alimiter=limit=0.95[a]"
    else:
        mix += ";[m]alimiter=limit=0.95[a]"
    run(cmd + ["-filter_complex", mix, "-map", "[a]", "-t", f"{total:.3f}",
               "-c:a", "aac", "-b:a", "192k", out_path])
    print(f"  Audio: music bed + {len(labels)} sound effects over {total:.0f}s")


def assemble_files(clip_paths, durations, sounds, work, final_path):
    """Everything except the network. Returns the temp files to delete."""
    video = os.path.join(work, "video_only.mp4")
    audio = os.path.join(work, "audio.m4a")
    temp = build_video(clip_paths, durations, work, video)
    build_audio(durations, sounds, work, audio)
    run(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", final_path])
    return temp + [video, audio]


def as_list(value):
    if isinstance(value, str):
        value = json.loads(value) if value else []
    return value or []


def main():
    row = store.get_next_video_complete_row()
    if not row:
        print("No 'video_complete' rows found. Nothing to do.")
        return
    row_id = row["id"]
    retry_count = row.get("retry_count") or 0
    video_urls = as_list(row.get("video_urls"))
    shot_list = as_list(row.get("shot_list"))
    shot_durations = as_list(row.get("shot_durations"))
    if not video_urls:
        store.mark_failed(row_id, "no video_urls on a 'video_complete' row", retry_count)
        return

    os.makedirs(FINAL_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"Assembling '{row.get('title', 'untitled')}' ({len(video_urls)} clips)...")
    temp = []
    try:
        clips = []
        for i, url in enumerate(video_urls):
            path = f"{TMP_DIR}/clip_{row_id}_{i}.mp4"
            store.download(url, path)
            clips.append(path)
        durations = [shot_durations[i] if i < len(shot_durations) else get_duration(c)
                     for i, c in enumerate(clips)]
        sounds = [shot_list[i].get("sound") if i < len(shot_list) else None
                  for i in range(len(clips))]
        final_path = f"{FINAL_DIR}/final_{row_id}.mp4"
        temp = clips + assemble_files(clips, durations, sounds, TMP_DIR, final_path) + [final_path]
        store.mark_video_generated(row_id, store.upload_final_video(final_path, row_id))
        print(f"Row {row_id}: assembled and uploaded. Status -> video_generated.")
    except Exception as e:
        store.mark_failed(row_id, f"assembly exception: {e}", retry_count)
    finally:
        for p in temp:
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    main()
