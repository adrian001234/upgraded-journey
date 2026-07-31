"""
TechPulse - Script Stage
Turns fetched headlines into a hook-first news-brief script + a series
of visual scene prompts (one per ~5s clip, for the video stage), via
Google Gemini (free tier).
"""
import json
import os
import urllib.request
import urllib.error

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"

PROMPT_TEMPLATE = """You are writing a YouTube Short for a tech/AI/science news channel.
Headline: {title}
Summary: {summary}
Write THREE separate things:
1. NARRATION: A 30-40 second spoken voiceover script (90-120 words). Start with a scroll-stopping hook in the very first sentence (a bold claim, surprising number, or curiosity-gap question) — no slow lead-in. Keep every sentence short and easy to say out loud. No filler, no robotic phrasing, no repeated words. End with a punchy one-line payoff (not a generic "and that's it").
2. HAS_RECURRING_PERSON: true only if the headline/summary is actually about a specific, named individual whose face or actions are central to the story (a founder, a scientist, a public figure). false for abstract, statistical, institutional, or trend-based stories (research findings, market data, company-wide behavior, policy, industry patterns) — these should be shown through environments, objects, and data, not an invented person.
3. SCENES: An array of exactly 7 short cinematic scene descriptions for an AI video generator, meant to play in sequence as B-roll matching the story as it unfolds — each describing camera angle, lighting, and setting. Vary the shots (don't repeat the same framing).

CRITICAL consistency rules — the video generator has NO memory between scenes, so every scene description must be fully self-contained:
- Pick ONE real-world setting (country/city/company/location) strictly from what the headline and summary actually describe. Do not invent or drift to an unrelated location, and do not add institutions, uniforms, flags, or military/national symbols that are not actually part of the story.
- If HAS_RECURRING_PERSON is true: invent ONE fixed physical description the first time (approximate age, gender, one or two distinguishing features) and repeat that EXACT description word-for-word in every scene they appear in. Never let age, gender, or appearance drift between scenes.
- If HAS_RECURRING_PERSON is false: do NOT invent any person at all. Build every scene from setting, objects, data visualizations, cityscapes, office/lab/exterior shots, screens, documents, money, charts — whatever fits the story. A generic unnamed person may appear once at most, incidentally, never as a repeating anchor.
- Avoid close-up shots of hands operating small precise objects (dials, switches, buttons, keyboards) — AI video generators render fine hand-object interaction unreliably. Favor wider shots instead.
- Every scene must be clearly, brightly lit (natural daylight or bright interior lighting) and state this explicitly, UNLESS the story specifically requires darkness or nighttime — in which case say so explicitly instead.

Output strict JSON only, no other text:
{{"narration": "...", "has_recurring_person": true, "scenes": ["...", "...", "...", "...", "...", "...", "..."]}}"""


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
        with urllib.request.urlopen(req, timeout=90) as resp:
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
    print("=== RAW GEMINI OUTPUT ===")
    print(content.strip())
    print("=== END RAW GEMINI OUTPUT ===")
    return content.strip()


def generate_scripts(headlines_path="research/latest_headlines.json", out_path="script/latest_scripts.json"):
    with open(headlines_path) as f:
        headlines = json.load(f)
    scripts = []
    for h in headlines:
        prompt = PROMPT_TEMPLATE.format(title=h["title"], summary=h["summary"])
        try:
            raw = call_gemini(prompt)
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            scripts.append({
                "source": h["source"],
                "title": h["title"],
                "link": h["link"],
                "narration": parsed["narration"],
                "has_recurring_person": bool(parsed.get("has_recurring_person", False)),
                "scenes": parsed["scenes"],
            })
        except Exception as e:
            print(f"Failed on {h['title']}: {e}")
    with open(out_path, "w") as f:
        json.dump(scripts, f, indent=2)
    print(f"Saved {len(scripts)} scripts to {out_path}")


if __name__ == "__main__":
    generate_scripts()
