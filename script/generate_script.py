"""
TechPulse - Script Stage
Turns fetched headlines into a short news-brief script via FreeLLMAPI.
"""

import json
import os
import urllib.request

FREELLM_URL = os.environ["FREELLM_API_URL"]
FREELLM_KEY = os.environ["FREELLM_API_KEY"]

PROMPT_TEMPLATE = """You are writing a short, punchy tech/AI/science news-brief script for a YouTube Short.
Headline: {title}
Summary: {summary}

Write a 30-45 second spoken script (roughly 80-110 words). Style: fast hook in the first line, plain conversational language, no fluff, end with a punchy one-liner. Output ONLY the script text, nothing else."""


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
            script_text = call_freellm(prompt)
            scripts.append({
                "source": h["source"],
                "title": h["title"],
                "link": h["link"],
                "script": script_text,
            })
        except Exception as e:
            print(f"Failed on {h['title']}: {e}")

    with open(out_path, "w") as f:
        json.dump(scripts, f, indent=2)
    print(f"Saved {len(scripts)} scripts to {out_path}")


if __name__ == "__main__":
    generate_scripts()
