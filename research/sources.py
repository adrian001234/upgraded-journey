"""
TechPulse - Research Stage
Pulls trending tech / AI / science headlines from free RSS feeds.
Selects the most recent headline that hasn't already been processed
(checked against the Supabase video_pipeline table).
No API key required for RSS; Supabase credentials are optional but
recommended to avoid re-publishing the same story.

FIXED (2026-08-04): RSS summaries were passed to the script stage as raw,
unsanitized text. Some feeds (TechCrunch, Ars Technica, etc.) embed HTML,
<code>/<pre> blocks, or literal code snippets inside the summary excerpt
for programming-related stories. That raw text was going straight into the
Gemini prompt, and Gemini would sometimes quote the code verbatim into the
narration - which the TTS stage then read aloud word-for-word, producing
a video where the narrator reads Python syntax mid-story. Now every
summary is HTML-stripped, code-block-stripped, and length-capped before
it's saved, so nothing but plain prose ever reaches the script stage.

FIXED (2026-08-06): duplicate-check bypass. The dedup check only ran
inside `if link and _link_already_processed(link)` - if an RSS entry's
link ever came back empty (some feeds omit it, or feedparser returns ""
on a malformed entry), the whole check was skipped and that headline was
free to be picked again on a future run with zero protection, producing
a repeat video with a different id. Now every candidate is checked -
by link when one exists, falling back to an exact title match against
already-processed rows when it doesn't - so an empty link can no longer
silently disable dedup.
"""
import feedparser
import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Free, no-key-required RSS feeds covering tech / AI / science
FEEDS = {
    "techcrunch": "https://techcrunch.com/feed/",
    "verge": "https://www.theverge.com/rss/index.xml",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
    "science_daily": "https://www.sciencedaily.com/rss/top/technology.xml",
}

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Matches <pre>...</pre> and <code>...</code> blocks (code snippets embedded
# in the RSS excerpt), including multi-line content, before the general tag strip.
CODE_BLOCK_RE = re.compile(r"<(pre|code)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
MAX_SUMMARY_CHARS = 600


def _clean_summary(raw_summary):
    """Strips embedded code blocks, then all remaining HTML tags, collapses
    whitespace, and caps length - so only plain prose reaches the script stage."""
    if not raw_summary:
        return ""
    text = CODE_BLOCK_RE.sub(" ", raw_summary)
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_SUMMARY_CHARS:
        text = text[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "..."
    return text


def _parse_date(entry):
    """Best-effort parse of an entry's published date. Falls back to epoch (UTC) if missing/bad."""
    raw = entry.get("published", "")
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _query_supabase_exists(filter_clause):
    """Runs a single exists-check query against video_pipeline. filter_clause is
    a raw PostgREST filter string, e.g. 'link=eq.foo' or 'title=eq.bar'."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False
    url = f"{SUPABASE_URL}/rest/v1/video_pipeline?{filter_clause}&select=id"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read())
            return len(rows) > 0
    except Exception as e:
        print(f"Warning: could not reach Supabase for a dedup check ({e}). Proceeding without it for this check.")
        return False


def _headline_already_processed(link, title):
    """Check whether this headline has already been processed. Prefers an
    exact link match; if link is missing/empty, falls back to an exact title
    match so a blank link can never silently bypass dedup entirely."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("Warning: SUPABASE_URL/SUPABASE_ANON_KEY not set in this stage - skipping duplicate check.")
        return False
    if link:
        encoded_link = urllib.parse.quote(link, safe="")
        if _query_supabase_exists(f"link=eq.{encoded_link}"):
            return True
    if title:
        encoded_title = urllib.parse.quote(title, safe="")
        if _query_supabase_exists(f"title=eq.{encoded_title}"):
            return True
    return False


def fetch_headlines(limit_per_source=5):
    """Fetch latest headlines from all sources."""
    results = []
    for source_name, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit_per_source]:
            results.append({
                "source": source_name,
                "title": entry.get("title", ""),
                "summary": _clean_summary(entry.get("summary", "")),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "fetched_at": datetime.utcnow().isoformat(),
                "_sort_date": _parse_date(entry),
            })
    return results


def select_top_headline(headlines):
    """Pick the most recent headline that hasn't already been processed."""
    if not headlines:
        return []
    ranked = sorted(headlines, key=lambda h: h["_sort_date"], reverse=True)
    for candidate in ranked:
        link = candidate.get("link", "")
        title = candidate.get("title", "")
        if _headline_already_processed(link, title):
            print(f"Skipping already-processed headline: {title}")
            continue
        candidate.pop("_sort_date", None)
        return [candidate]
    print("All candidate headlines this run were already processed — nothing new to publish.")
    return []


def save_headlines(headlines, path="research/latest_headlines.json"):
    """Save selected headline(s) to a JSON file."""
    with open(path, "w") as f:
        json.dump(headlines, f, indent=2)
    print(f"Saved {len(headlines)} headline(s) to {path}")


if __name__ == "__main__":
    all_headlines = fetch_headlines()
    selected = select_top_headline(all_headlines)
    save_headlines(selected)
