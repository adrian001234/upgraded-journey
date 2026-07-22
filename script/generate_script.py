"""
TechPulse - Script Stage
Turns fetched headlines into a hook-first news-brief script + a separate
visual scene prompt (for the video stage), via FreeLLMAPI.
"""

import json
import os
import urllib.request

FREELLM_URL = os.environ["FREELLM_API_URL"]
FREELLM_KEY = os.environ["FREELLM_API_KEY"]

PROMPT_TEMPLATE = """You are writing a YouTube Short for a tech/AI/science news channel.
Headline: {title}
Summary: {summary}

Write TWO separate things:
1. NARRATION: A 30-40 second spoken voiceover script (90-120 words). Start with a scroll-stopping hook in the very first sentence (a bold claim, surprising number, or curiosity-gap question) — no slow lead-in. Keep every sentence short and easy to say out loud. No filler, no robotic phrasing, no repeated words. End with a punchy one-line payoff (not a generic "and that's it").
2. VISUAL: A single cinematic scene description (1-2 sentences) for an AI video generator to render as B-roll footage that matches the story's mood — describe camera angle, lighting, and setting. Do NOT restate the narration word-for-word; describe what should be SEEN, not what should be SAID.

Output strict JSON only, no other text:
{{"narration": "...", "visual": "..."}}"""


def call_freellm(prompt):
    body = json.dumps({
        "model": "auto",
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        FREELLM_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {FREELLM_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()


def generate_scripts(headlines_path="research/latest_headlines.json", out_path="script/latest_scripts.json"):
    with open(headlines_path) as f:
        headlines = json.load(f)

    scripts = []
    for h in headlines:
        prompt = PROMPT_TEMPLATE.format(title=h["title"], summary=h["summary"])
        try:
            raw = call_freellm(prompt)
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            scripts.append({
                "source": h["source"],
                "title": h["title"],
                "link": h["link"],
                "narration": parsed["narration"],
                "visual": parsed["visual"],
            })
        except Exception as e:
            print(f"Failed on {h['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(scripts, f, indent=2)
    print(f"Saved {len(scripts)} scripts to {out_path}")


if __name__ == "__main__":
    generate_scripts()
