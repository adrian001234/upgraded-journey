"""
TechPulse - Research Stage
Pulls trending tech / AI / science headlines from free RSS feeds.
Selects the most recent headline that hasn't already been processed
(checked against the Supabase video_pipeline table).
No API key required for RSS; Supabase credentials are optional but
recommended to avoid re-publishing the same story.
"""
import feedparser
import json
import os
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


def _link_already_processed(link):
    """Check the Supabase video_pipeline table for an existing row with this link."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("Warning: SUPABASE_URL/SUPABASE_ANON_KEY not set in this stage — skipping duplicate check.")
        return False
    encoded_link = urllib.parse.quote(link, safe="")
    url = f"{SUPABASE_URL}/rest/v1/video_pipeline?link=eq.{encoded_link}&select=id"
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
        print(f"Warning: could not reach Supabase to check duplicates ({e}). Proceeding without dedup check for this run.")
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
                "summary": entry.get("summary", ""),
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
        if link and _link_already_processed(link):
            print(f"Skipping already-processed headline: {candidate['title']}")
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
