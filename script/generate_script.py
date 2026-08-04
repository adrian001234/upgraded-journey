"""
TechPulse - Script Stage
Turns the latest researched headline into a full long-form narration script
plus a shot-by-shot production plan, then inserts it directly into the
Supabase video_pipeline table with status='scripted' - ready for the
(resumable, checkpointed) video stage to pick up.

ARCHITECTURE CHANGE (2026-08-04): TDP moved from 30-40s Shorts to 6-8 minute
long-form videos, matching the format/quality bar of the Erased and
Alternate Earth channels. A single CI run can no longer generate a whole
episode's shots in one pass (Agnes AI is rate-limited per-minute; a 6-8 min
episode needs 60-90 shots). This stage no longer hands off via a JSON file
to a single-run video stage - it writes a full row (including the entire
shot_list) straight into video_pipeline, and video/generate_video.py now
resumes across multiple scheduled runs, checkpointing progress after every
shot (ported from the proven pattern in marius-command-center/scripts/video_generation.py).

RETENTION ENGINEERING: the prompt below is built around what actually
proven high-retention channels do - a hard stake-first hook in the first
8 seconds (no channel intro, no throat-clearing), a curiosity gap the
episode is structured to resolve, escalating tension through the middle,
a payoff that reuses the single most specific/surprising detail from the
story, and an in-voice CTA folded into the payoff's energy rather than a
generic "smash that like button" tacked on the end.
"""
import json
import os
import time
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}

MIN_SHOTS = 60
MAX_SHOTS = 90
MAX_GENERATION_ATTEMPTS = 5
MIN_SETTING_CHARS = 40
MAX_SETTING_CHARS = 900
MIN_WORDS = 900
MAX_WORDS = 1400

CTA_KEYWORDS = (
    "comment", "comments", "subscribe", "share this", "share it",
    "like this", "like and", "tell us", "let us know", "hit follow",
    "hit that", "follow along", "leave a", "drop a",
)
CTA_SEARCH_WINDOW_CHARS = 700

VALID_SHOT_TYPES = {
    "wide", "medium", "close_up", "extreme_close_up", "establishing", "detail_insert"
}
VALID_CAMERA_MOVEMENTS = {
    "static", "pan_left", "pan_right", "tilt_up", "tilt_down", "zoom_in", "zoom_out",
    "push_in", "pull_out", "dolly_in", "dolly_out", "tracking", "crash_zoom",
    "whip_pan", "handheld_shake", "orbit", "drone_rise", "drone_descend",
    "parallax", "focus_pull", "dutch_angle", "snap_zoom", "speed_ramp",
}
VALID_LENS_EFFECTS = {"shallow_depth_of_field", "lens_flare", "film_grain", "none"}

ZOOM_FAMILY_MOVEMENTS = {"push_in", "crash_zoom", "zoom_in", "snap_zoom", "dolly_in"}
MAX_ZOOM_SHOT_RATIO = 0.32
MAX_CONSECUTIVE_ZOOM_SHOTS = 2


def load_headline(path="research/latest_headlines.json"):
    with open(path) as f:
        headlines = json.load(f)
    return headlines[0] if headlines else None


def call_gemini(prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }).encode()
    req_headers = {"Content-Type": "application/json"}
    last_error = None
    for attempt in range(4):
        try:
            resp = requests.post(GEMINI_URL, data=body, headers=req_headers, timeout=120)
        except requests.exceptions.RequestException as e:
            last_error = e
            wait = (attempt + 1) * 15
            print(f"Network error calling Gemini ({e}), waiting {wait}s before retry...")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            wait = (attempt + 1) * 15
            print(f"Gemini rate limited, waiting {wait}s before retry...")
            time.sleep(wait)
            last_error = resp.text
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from Gemini. Body: {resp.text[:500]}")
        data = resp.json()
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected response shape from Gemini: {json.dumps(data)[:500]}") from e
        if not content or not content.strip():
            raise RuntimeError("Gemini returned an empty completion.")
        return content.strip()
    raise RuntimeError(f"Gemini still failing after retries: {last_error}")


def extract_json(raw_text):
    if not raw_text:
        raise ValueError("Model returned empty/None content.")
    text = raw_text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{"):
                text = candidate
                break
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start:end + 1])


def normalize_shot(shot, index):
    shot_type = shot.get("shot_type")
    if shot_type not in VALID_SHOT_TYPES:
        shot_type = "medium"
    camera_movement = shot.get("camera_movement")
    if camera_movement not in VALID_CAMERA_MOVEMENTS:
        camera_movement = "static"
    lens_effect = shot.get("lens_effect")
    if lens_effect not in VALID_LENS_EFFECTS:
        lens_effect = "none"
    return {
        "shot_number": shot.get("shot_number", index + 1),
        "visual_description": shot.get("visual_description", ""),
        "narration_excerpt": shot.get("narration_excerpt", ""),
        "shot_type": shot_type,
        "camera_movement": camera_movement,
        "camera_reason": shot.get("camera_reason", ""),
        "lens_effect": lens_effect,
        "sfx_cue": shot.get("sfx_cue", ""),
    }


def narration_has_engagement_cta(narration_text):
    if not narration_text:
        return False
    window = narration_text[-CTA_SEARCH_WINDOW_CHARS:].lower()
    return any(keyword in window for keyword in CTA_KEYWORDS)


def validate_and_normalize(result):
    narration_text = (result.get("narration_text") or "").strip()
    if not narration_text:
        return False, "missing narration_text"

    word_count = len(narration_text.split())
    if word_count < MIN_WORDS or word_count > MAX_WORDS:
        return False, f"narration_text word count {word_count} outside {MIN_WORDS}-{MAX_WORDS} range"

    setting_and_characters = (result.get("setting_and_characters") or "").strip()
    if len(setting_and_characters) < MIN_SETTING_CHARS:
        return False, (
            f"setting_and_characters missing or too short ({len(setting_and_characters)} chars, "
            f"need at least {MIN_SETTING_CHARS}) - must fix the real-world setting and describe any "
            f"recurring figure's appearance"
        )
    result["setting_and_characters"] = setting_and_characters[:MAX_SETTING_CHARS]

    if not narration_has_engagement_cta(narration_text):
        return False, (
            "narration_text is missing an in-voice engagement call-to-action "
            "(like/subscribe/comment) near the end"
        )

    shot_list = result.get("shot_list")
    if not isinstance(shot_list, list) or len(shot_list) == 0:
        return False, "missing or empty shot_list"
    if len(shot_list) < MIN_SHOTS or len(shot_list) > MAX_SHOTS:
        return False, f"shot count {len(shot_list)} outside {MIN_SHOTS}-{MAX_SHOTS} range"

    normalized_shots = [normalize_shot(s, i) for i, s in enumerate(shot_list)]

    zoom_count = sum(
        1 for s in normalized_shots
        if s["camera_movement"] in ZOOM_FAMILY_MOVEMENTS or s["shot_type"] == "extreme_close_up"
    )
    zoom_ratio = zoom_count / len(normalized_shots)
    if zoom_ratio > MAX_ZOOM_SHOT_RATIO:
        return False, (
            f"too many zoomed-in shots: {zoom_count}/{len(normalized_shots)} ({zoom_ratio:.0%}) "
            f"over the {MAX_ZOOM_SHOT_RATIO:.0%} ceiling"
        )

    consecutive_zoom = 0
    max_consecutive_zoom = 0
    for s in normalized_shots:
        if s["camera_movement"] in ZOOM_FAMILY_MOVEMENTS:
            consecutive_zoom += 1
            max_consecutive_zoom = max(max_consecutive_zoom, consecutive_zoom)
        else:
            consecutive_zoom = 0
    if max_consecutive_zoom > MAX_CONSECUTIVE_ZOOM_SHOTS:
        return False, f"{max_consecutive_zoom} zoom-in-family shots in a row (max {MAX_CONSECUTIVE_ZOOM_SHOTS})"

    result["narration_text"] = narration_text
    result["shot_list"] = normalized_shots
    result["music_mood"] = (result.get("music_mood") or "").strip() or (
        "Tense cinematic thriller score, sparse low synth and rising strings at the start, "
        "driving percussion building through the middle, punchy climax at the biggest reveal, "
        "tapering to a quiet resolution."
    )
    result["has_recurring_person"] = bool(result.get("has_recurring_person", False))
    return True, result


def generate_script(headline):
    title = headline["title"]
    summary = headline.get("summary", "")

    prompt = f"""You are the head writer for a tech/AI/science YouTube channel built for
maximum retention and subscriber growth - the goal is a video that plays like a thriller,
not a news recap.

Headline: {title}
Summary: {summary}

SETTING AND CHARACTERS - write this FIRST, as a fixed visual anchor for the whole video:
- Ground the story in a concrete real-world setting (company, lab, city, product, event)
  strictly from what the headline/summary actually describe. Do not invent an unrelated
  location or institution.
- "has_recurring_person": true only if the story is genuinely about a specific named
  individual whose face/actions are central (a founder, scientist, public figure). If true,
  give ONE fixed physical description (age, build, distinguishing features) that must repeat
  identically in every shot they appear in. If false, do not invent a person at all - build
  shots from environments, devices, screens, data visualizations, and objects instead.
This anchor gets attached to every shot's video-generation prompt later, so write it as a
standalone paragraph, 2-5 sentences.

OPENING HOOK (first 8 seconds are everything):
1. STAKE (1-2 sentences): the single most dramatic, concrete fact - a real number, name, or
   consequence. No "today we're looking at," no channel intro, no setup. Lead with the fact.
2. VISUAL LOCK (1 sentence): one concrete, specific image/moment that proves the stake is real.
3. CURIOSITY GAP (1-2 sentences): the specific question the rest of the video answers.

Write a complete 6-8 minute narration script ({MIN_WORDS}-{MAX_WORDS} words) with this
opening, an escalating middle that keeps raising the stakes and withholding the full picture,
and a payoff that reuses the single most specific/surprising detail from the headline/summary
(a number, a name, a timeframe) - never a generic "this changes everything."

CALL TO ACTION - REQUIRED: immediately after the payoff and before any closing line, write
one natural in-voice sentence that folds the CTA into the payoff's specific energy - it must
reference the actual detail just delivered (a number, an outcome), not a generic urgency line
that could paste onto any other story. Use natural phrasing that clearly asks the viewer to
like, subscribe, and comment (weave in words like "comment," "share," or "subscribe").

NEVER OUTPUT CODE: even if the story is about programming or software, narration must ONLY be
plain spoken English - never literal code, syntax, file paths, or function calls read aloud.

CINEMATIC DIRECTOR - shot list:
Break the video into EXACTLY between {MIN_SHOTS} and {MAX_SHOTS} shots, dense sub-sentence
level breakdown (a narration sentence often spans 2-3 shots). Every shot's visual_description
must stay consistent with setting_and_characters.

For each shot, provide "shot_type" (wide/medium/close_up/extreme_close_up/establishing/
detail_insert), "camera_movement" (static/pan_left/pan_right/tilt_up/tilt_down/zoom_in/
zoom_out/push_in/pull_out/dolly_in/dolly_out/tracking/crash_zoom/whip_pan/handheld_shake/
orbit/drone_rise/drone_descend/parallax/focus_pull/dutch_angle/snap_zoom/speed_ramp),
"camera_reason" (one sentence), "lens_effect" (shallow_depth_of_field/lens_flare/film_grain/
none - use sparingly).

PACING: default to quick shots (2-4s of narration each), fast-cut feel. Only hold a static
shot deliberately right before a reveal. Never repeat the same camera_movement more than
twice in a row.

ZOOM DISCIPLINE (hard budget, not a suggestion): at most 1 in 4 shots may use a zoom-in-family
movement (push_in/crash_zoom/zoom_in/snap_zoom/dolly_in) or extreme_close_up - never two in a
row. At least 1 in 4 shots must be "wide" or "establishing", spread through the video, not
clustered at the start.

SOUND: "music_mood" - describe a thriller-movie score arc (restrained start, building
intensity, percussive climax at the biggest reveal, resolving). For each shot, "sfx_cue" -
both dramatic sounds (alerts, crashes, crowd reactions) and ambient/atmospheric sound
(keyboard clicks, servers humming, wind, footsteps, notification pings) - aim for at least
half of all shots to carry some cue; leave empty only where truly no sound would be audible.

Return ONLY valid JSON, no markdown fences, in this exact format:
{{
  "setting_and_characters": "...",
  "has_recurring_person": false,
  "narration_text": "...",
  "music_mood": "...",
  "shot_list": [
    {{
      "shot_number": 1,
      "visual_description": "...",
      "narration_excerpt": "...",
      "shot_type": "wide",
      "camera_movement": "push_in",
      "camera_reason": "...",
      "lens_effect": "none",
      "sfx_cue": ""
    }}
  ]
}}
Include between {MIN_SHOTS} and {MAX_SHOTS} shots covering the full narration."""

    last_reason = None
    for attempt in range(MAX_GENERATION_ATTEMPTS):
        raw = call_gemini(prompt)
        try:
            parsed = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            last_reason = f"JSON parse failed: {e}"
            print(f"Attempt {attempt + 1}/{MAX_GENERATION_ATTEMPTS} failed - {last_reason}")
            continue
        is_valid, result = validate_and_normalize(parsed)
        if is_valid:
            return result
        last_reason = result
        print(f"Attempt {attempt + 1}/{MAX_GENERATION_ATTEMPTS} failed - {last_reason}")

    raise RuntimeError(f"Script generation failed after {MAX_GENERATION_ATTEMPTS} attempts. Last reason: {last_reason}")


def save_to_pipeline(headline, result):
    payload = {
        "title": headline["title"],
        "source": headline.get("source", ""),
        "link": headline.get("link", ""),
        "script": result["narration_text"],
        "shot_list": result["shot_list"],
        "setting_and_characters": result["setting_and_characters"],
        "has_recurring_person": result["has_recurring_person"],
        "music_mood": result["music_mood"],
        "video_urls": [],
        "video_next_index": 0,
        "status": "scripted",
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/video_pipeline",
        headers={**HEADERS, "Prefer": "return=representation"},
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to save script to video_pipeline: {resp.status_code} {resp.text}")
    print(f"Saved script to video_pipeline: {resp.json()[0]['id']}")


def main():
    headline = load_headline()
    if not headline:
        print("No headline found in research/latest_headlines.json. Nothing to do.")
        return

    print(f"Writing long-form script for: {headline['title']}")
    result = generate_script(headline)
    save_to_pipeline(headline, result)
    print(f"Done. {len(result['shot_list'])} shots, {len(result['narration_text'].split())} words.")


if __name__ == "__main__":
    main()
