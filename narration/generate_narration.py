"""
TechPulse - Narration Stage
Takes one video_pipeline row with status='scripted' and synthesizes its
full long-form narration via Chatterbox TTS, one real SENTENCE at a time
(correct prosody, no mid-sentence resets), with a real silence gap after
every sentence. Each sentence's single measured audio duration is then
distributed across the shots that fall inside it (proportional to word
count), producing accurate per-shot timing for the video stage to size
clips against - ported directly from the proven pattern in
marius-command-center/scripts/narration.py.

ARCHITECTURE CHANGE (2026-08-04): previously this stage ran AFTER video
generation, reading video/latest_videos.json in a single CI run (fine for
a single 30-40s Short assembled in one pass). Long-form needs per-shot
clip durations BEFORE video generation even starts (Agnes needs to know
how long each of 60-90 shots should be), so narration now runs right after
the script stage and writes narration_url + shot_durations onto the
video_pipeline row. The old inline [SFX:]/[VOICE:quote] tag parsing is
dropped - long-form scripts carry sound cues per-shot in shot_list[].sfx_cue
instead (matching the Marius shot-level sfx approach), not as inline
narration tags.

VOICE CHANGE (2026-08-06): narrator voice reference finalized as Mark F.
Smith (LibriVox, "The Call of the Wild"). Reference clip is fetched once
per run from CHATTERBOX_VOICE_REF_URL (a public Supabase Storage URL) and
passed to Chatterbox as audio_prompt_path for voice cloning. exaggeration/
cfg_weight tuned for a steadier, less exaggerated documentary read than
Chatterbox's defaults. Also fixes two known issues:
  - Sentence-stitch clicks: each sentence clip now gets a short fade
    in/out before concatenation (raw edge-to-edge joins were producing
    audible clicks at sentence boundaries).
  - Atempo artifact: the slowdown pass now upsamples to 48kHz before
    atempo and back down after, instead of applying atempo directly at
    24kHz, which was producing a warble/artifact on the slowed audio.

TEMPO FIX (2026-08-06): the previous TEMPO_FACTOR of 0.92 (8% SLOWER than
raw TTS output) was Zia's confirmed judgment based on actually listening
to a real generated test-row narration - too slow. Changed to 1.25 (25%
FASTER than raw output) per his direct feedback comparing both speeds on
the same real audio. Renamed from SLOWDOWN_FACTOR to TEMPO_FACTOR since
it's no longer a slowdown - the duration-scaling math below already works
correctly in either direction (a factor >1 correctly shortens
scaled_shot_durations, a factor <1 correctly lengthens them), so no other
logic needed to change.
"""
import os
import re
import json
import subprocess
import requests
import torchaudio
from chatterbox.tts import ChatterboxTTS
from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}

NARRATION_BUCKET = "narration"

TEMPO_FACTOR = "1.25"  # 25% faster, pitch preserved - Zia confirmed via real test-row output that the previous 0.92 (8% slower) pacing sounded too slow, and 1.25x sounds better

PAUSE_SECONDS_MIN = 1.0
PAUSE_SECONDS_MAX = 2.0

MIN_PLAUSIBLE_WORDS_PER_SECOND = 1.6
DURATION_SLACK_SECONDS = 1.0
MAX_SENTENCE_TTS_ATTEMPTS = 3

STITCH_FADE_MS = 12  # short fade in/out on every sentence clip to kill stitch clicks

# Voice reference (Mark F. Smith, "The Call of the Wild", finalized 2026-08-06)
VOICE_REFERENCE_URL = os.environ["CHATTERBOX_VOICE_REF_URL"]
VOICE_REFERENCE_PATH = "/tmp/chatterbox_voice_reference.wav"

# Tuned for a steadier, less theatrical documentary read than Chatterbox's
# defaults (0.5 / 0.5). Lower exaggeration = flatter, more even delivery;
# slightly lower cfg_weight = looser adherence to the reference's exact
# cadence, so it doesn't sound like it's straining to mimic every inflection.
EXAGGERATION = 0.4
CFG_WEIGHT = 0.4

_tts_model = None


def get_tts_model():
    global _tts_model
    if _tts_model is None:
        _tts_model = ChatterboxTTS.from_pretrained(device="cpu")
    return _tts_model


def ensure_voice_reference():
    """Download the approved voice reference clip once per run."""
    if os.path.exists(VOICE_REFERENCE_PATH):
        return VOICE_REFERENCE_PATH
    resp = requests.get(VOICE_REFERENCE_URL, timeout=60)
    resp.raise_for_status()
    with open(VOICE_REFERENCE_PATH, "wb") as f:
        f.write(resp.content)
    return VOICE_REFERENCE_PATH


def get_next_scripted_row():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?status=eq.scripted&order=created_at.asc&limit=1",
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def split_into_segments(narration_text):
    raw_segments = re.split(r"(?<=[.!?])\s+", narration_text.strip())
    segments = [seg.strip() for seg in raw_segments if seg.strip()]
    return segments if segments else [narration_text.strip()]


def _max_plausible_duration(text):
    word_count = max(len(text.split()), 1)
    return (word_count / MIN_PLAUSIBLE_WORDS_PER_SECOND) + DURATION_SLACK_SECONDS


def synthesize_sentence(text, tts, tmp_path, voice_ref_path):
    max_plausible = _max_plausible_duration(text)
    last_duration = None
    clip = None

    for attempt in range(MAX_SENTENCE_TTS_ATTEMPTS):
        wav = tts.generate(
            text,
            audio_prompt_path=voice_ref_path,
            exaggeration=EXAGGERATION,
            cfg_weight=CFG_WEIGHT,
        )
        torchaudio.save(tmp_path, wav, tts.sr)
        clip = AudioSegment.from_file(tmp_path)
        duration_seconds = len(clip) / 1000.0
        last_duration = duration_seconds

        if duration_seconds <= max_plausible:
            return clip.fade_in(STITCH_FADE_MS).fade_out(STITCH_FADE_MS)

        print(f"TTS output for sentence looks like a stutter/duplicate "
              f"({duration_seconds:.1f}s, expected under {max_plausible:.1f}s for "
              f"{len(text.split())} words) - attempt {attempt + 1}/{MAX_SENTENCE_TTS_ATTEMPTS}. "
              f"Sentence: {text[:80]!r}")

    print(f"Sentence still looks anomalous after {MAX_SENTENCE_TTS_ATTEMPTS} attempts "
          f"({last_duration:.1f}s) - using the last attempt anyway rather than blocking the whole run: "
          f"{text[:80]!r}")
    return clip.fade_in(STITCH_FADE_MS).fade_out(STITCH_FADE_MS)


def _assign_shots_to_sentences(sentences, shot_list):
    sentence_word_counts = [max(len(s.split()), 1) for s in sentences]
    shot_word_counts = [
        len((shot.get("narration_excerpt") or "").split()) for shot in shot_list
    ]

    total_sentence_words = sum(sentence_word_counts)
    total_shot_words = sum(shot_word_counts)
    if total_shot_words == 0:
        return None

    scale = total_sentence_words / total_shot_words

    sentence_bounds = []
    running = 0
    for wc in sentence_word_counts:
        sentence_bounds.append((running, running + wc))
        running += wc

    contributions = []
    running_shot_pos = 0.0
    for wc in shot_word_counts:
        start = running_shot_pos * scale
        end = (running_shot_pos + wc) * scale
        running_shot_pos += wc

        shot_contribs = []
        for s_idx, (s_start, s_end) in enumerate(sentence_bounds):
            overlap = min(end, s_end) - max(start, s_start)
            if overlap > 0:
                shot_contribs.append((s_idx, overlap))
        contributions.append(shot_contribs)

    return contributions, sentence_bounds


def synthesize_per_sentence_with_shot_durations(narration_text, shot_list, tts, voice_ref_path):
    sentences = split_into_segments(narration_text)
    print(f"Narration split into {len(sentences)} real sentence(s) for natural TTS.")

    combined = AudioSegment.silent(duration=0)
    sentence_durations = []

    for i, sentence in enumerate(sentences):
        clip = synthesize_sentence(sentence, tts, f"/tmp/sent_{i}.wav", voice_ref_path)
        combined += clip
        sentence_durations.append(len(clip) / 1000.0)

        if i < len(sentences) - 1:
            pause_len = PAUSE_SECONDS_MIN if i % 2 == 0 else PAUSE_SECONDS_MAX
            combined += AudioSegment.silent(duration=int(pause_len * 1000))
            sentence_durations[-1] += pause_len

    shot_durations = [0.0] * len(shot_list)
    result = _assign_shots_to_sentences(sentences, shot_list)
    if result is None:
        even_share = sum(sentence_durations) / max(len(shot_list), 1)
        shot_durations = [even_share] * len(shot_list)
    else:
        contributions, sentence_bounds = result
        for shot_idx, shot_contribs in enumerate(contributions):
            for s_idx, words in shot_contribs:
                s_start, s_end = sentence_bounds[s_idx]
                sentence_word_span = max(s_end - s_start, 1)
                share = (words / sentence_word_span) * sentence_durations[s_idx]
                shot_durations[shot_idx] += share

    return combined, shot_durations


def upload_narration(row_id, local_path):
    dest_name = f"narration_{row_id}.wav"
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{NARRATION_BUCKET}/{dest_name}",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "audio/wav",
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=120,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Narration upload failed ({resp.status_code}): {resp.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{NARRATION_BUCKET}/{dest_name}"


def save_progress(row_id, narration_url, shot_durations):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/video_pipeline?id=eq.{row_id}",
        headers=HEADERS,
        json={
            "status": "narrated",
            "narration_url": narration_url,
            "shot_durations": shot_durations,
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to save narration progress ({resp.status_code}): {resp.text}")


def main():
    row = get_next_scripted_row()
    if not row:
        print("No 'scripted' rows found. Nothing to do.")
        return

    row_id = row["id"]
    narration_text = row["script"]
    shot_list = row.get("shot_list")
    if isinstance(shot_list, str):
        shot_list = json.loads(shot_list)
    print(f"Narrating row id={row_id}, {len(narration_text)} chars, {len(shot_list or [])} shots")

    voice_ref_path = ensure_voice_reference()
    tts = get_tts_model()
    combined_audio, shot_durations = synthesize_per_sentence_with_shot_durations(
        narration_text, shot_list, tts, voice_ref_path
    )

    combined_audio = pydub_normalize(combined_audio)

    raw_filename = f"/tmp/narration_{row_id}_raw.wav"
    output_filename = f"/tmp/narration_{row_id}.wav"
    combined_audio.export(raw_filename, format="wav")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", raw_filename,
            "-filter:a", f"aresample=48000,atempo={TEMPO_FACTOR},aresample=24000",
            output_filename,
        ],
        check=True, capture_output=True,
    )
    os.remove(raw_filename)
    print(f"Audio written to {output_filename}")

    narration_url = upload_narration(row_id, output_filename)
    print(f"Uploaded. Public URL: {narration_url}")

    slowdown = float(TEMPO_FACTOR)
    scaled_shot_durations = [d / slowdown for d in shot_durations]

    save_progress(row_id, narration_url, scaled_shot_durations)
    print(f"Row {row_id} status updated to 'narrated'. Done.")


if __name__ == "__main__":
    main()
