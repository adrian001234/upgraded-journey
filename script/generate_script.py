"""
TechPulse - Script Stage (LONG-FORM)
Rewritten 2026-08-04 for the move away from 30-40s Shorts toward long-form
videos matching Erased/Alternate Earth's format.

Old design: exactly 7 scenes + a single 90-120 word narration block,
everything generated in one pass. That doesn't scale to long-form because
Agnes AI is rate-limited per-minute (same wall Marius hit) - a 6-8 minute
video needs 40-50+ shots, which cannot all render in a single Actions run.

New design: this stage now does ONLY the writing (Gemini call), producing
a full long-form narration + a full shot list. It writes the narration to
video_pipeline.narration_full and inserts every shot as its own row in
video_shots with status='pending'. The separate video-generation stage
(next to be rewritten) pulls ONE pending shot per run, renders it via
Agnes, and exits - so a rate-limit hit just pauses progress on that video
instead of failing the whole thing. generation_status moves
scripting -> shots_generating as soon as this stage completes.
"""
import json
import os
import re
import urllib.request
import urllib.error

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

TARGET_WORD_COUNT = "900-1100"   # ~6-7 minutes spoken
TARGET_SHOT_COUNT = 45           # roughly one shot per 8-9 seconds of narration

PROMPT_TEMPLATE = """You are writing a long-form YouTube video (6-7 minutes) for a tech/AI/science news channel. Your job is to hold attention for the full length with a documentary-style narrative, not a quick hook-and-CTA format.
Headline: {title}
Summary: {summary}

Write THREE separate things:

1. NARRATION: A full {word_count} word documentary-style spoken script covering this story in depth - background/context, what happened, why it matters, and implications/what's next. Structure it in clear sections (open with a strong hook, build through the story's key developments, close with a considered takeaway) but write it as continuous flowing narration, not headers or bullet points.
   NEVER OUTPUT CODE: even if the story is about programming, software, or a technical tool, the narration must ONLY ever be plain spoken English describing what happened and why it matters - never literal code, syntax, command-line text, file paths, variable names, or function calls read as if spoken aloud. Describe technical concepts in plain language a general audience would understand, never quote source material verbatim if it contains code or markup.
   SOUND TAGGING: Wherever the narration describes a concrete, audible event, insert an inline tag: [SFX: short sound description]. Only tag real diegetic sounds implied by the story content.
   QUOTE TAGGING: If the narration includes a direct quote from a named person actually attributed in the source material, wrap ONLY that quoted portion in [VOICE:quote]...[/VOICE] tags. Never invent a quote.

2. HAS_RECURRING_PERSON: true only if the headline/summary is actually about a specific, named individual whose face or actions are central to the story. false for abstract, statistical, institutional, or trend-based stories.

3. SHOTS: An array of exactly {shot_count} short cinematic scene descriptions for an AI video generator, meant to play in sequence as B-roll matching the story as it unfolds across the full narration - each describing camera angle, lighting, and setting. Vary the shots (don't repeat the same framing).

CRITICAL consistency rules - the video generator has NO memory between shots, so every shot description must be fully self-contained:
- Pick ONE real-world setting (country/city/company/location) strictly from what the headline and summary actually describe. Do not invent or drift to an unrelated location, and do not add institutions, uniforms, flags, or military/national symbols that are not actually part of the story.
- If HAS_RECURRING_PERSON is true: invent ONE fixed physical description the first time (approximate age, gender, one or two distinguishing features) and repeat that EXACT description word-for-word in every shot they appear in. Never let age, gender, or appearance drift between shots.
- If HAS_RECURRING_PERSON is false: do NOT invent any person at all. Build every shot from setting, objects, data visualizations, cityscapes, office/lab/exterior shots, screens, documents, charts - whatever fits the story. A generic unnamed person may appear at most incidentally, never as a repeating anchor.
- ZOOM DISCIPLINE: at most 1-in-4 shots may be push_in/crash_zoom/extreme_close_up. At least 1-in-4 shots must be wide/establishing. Never place two zoom-in-family shots back to back.
- Avoid close-up shots of hands operating small precise objects (dials, switches, buttons, keyboards) - AI video generators render fine hand-object interaction unreliably. Favor wider shots instead.
- Every shot must be clearly, brightly lit (natural daylight or bright interior lighting) and state this explicitly, UNLESS the story specifically requires darkness or nighttime - in which case say so explicitly instead.
- No anachronisms: only include objects/technology that plausibly belong to the actual time period and setting of the story.

Output strict JSON only, no other text:
{{"narration": "...", "has_recurring_person": true, "shots": ["...", "..."]}}"""


def call_gemini(prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }).encode()
    req = urllib.request.Request(
        GEMINI_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            status = resp.status
            raw_bytes = resp.read()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code} from Gemini. Body: {error_body}") from e
    if not raw_bytes.strip():
        raise RuntimeError(f"Gemini returned an EMPTY body. Status={status}")
    try:
        result = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        preview = raw_bytes[:500].decode(errors="replace")
        raise RuntimeError(f"Gemini response wasn't valid JSON. Status={status}. Body preview: {preview}") from e
    try:
        content = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected response shape from Gemini: {json.dumps(result)[:500]}") from e
    if not content or not content.strip():
        raise RuntimeError("Gemini returned an empty completion.")
    print("=== RAW GEMINI OUTPUT (truncated to 1000 chars) ===")
    print(content.strip()[:1000])
    print("=== END ===")
    return content.strip()


def _supabase_request(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw.strip() else None


def insert_pipeline_row(headline, narration, has_recurring_person, total_shots):
    row = {
        "title": headline["title"],
        "link": headline.get("link", ""),
        "source": headline.get("source", ""),
        "narration_full": narration,
        "total_shots": total_shots,
        "shots_completed": 0,
        "generation_status": "shots_generating",
        "status": "video_generated",  # legacy column, kept in sync; shot generation happens next stage
    }
    result = _supabase_request("POST", "video_pipeline", row)
    return result[0]["id"]


def insert_shots(pipeline_id, shots):
    rows = [
        {"pipeline_id": pipeline_id, "shot_number": i + 1, "scene_description": s, "status": "pending"}
        for i, s in enumerate(shots)
    ]
    _supabase_request("POST", "video_shots", rows)


def generate_scripts(headlines_path="research/latest_headlines.json"):
    with open(headlines_path) as f:
        headlines = json.load(f)
    for h in headlines:
        prompt = PROMPT_TEMPLATE.format(
            title=h["title"], summary=h["summary"],
            word_count=TARGET_WORD_COUNT, shot_count=TARGET_SHOT_COUNT,
        )
        try:
            raw = call_gemini(prompt)
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            shots = parsed["shots"]
            pipeline_id = insert_pipeline_row(
                h, parsed["narration"], bool(parsed.get("has_recurring_person", False)), len(shots)
            )
            insert_shots(pipeline_id, shots)
            print(f"Created pipeline row {pipeline_id} for '{h['title']}' with {len(shots)} shots.")
        except Exception as e:
            print(f"Failed on {h['title']}: {e}")


if __name__ == "__main__":
    generate_scripts()
