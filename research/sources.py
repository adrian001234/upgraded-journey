"""
TechPulse - Research Stage
Pulls trending tech / AI / science headlines from free RSS feeds.
Selects only the single most recent headline for this run.
No API key required.
"""
import feedparser
import json
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
    """Pick the single most recent headline across all sources."""
    if not headlines:
        return []
    ranked = sorted(headlines, key=lambda h: h["_sort_date"], reverse=True)
    top = ranked[0]
    top.pop("_sort_date", None)
    return [top]


def save_headlines(headlines, path="research/latest_headlines.json"):
    """Save selected headline(s) to a JSON file."""
    with open(path, "w") as f:
        json.dump(headlines, f, indent=2)
    print(f"Saved {len(headlines)} headline(s) to {path}")


if __name__ == "__main__":
    all_headlines = fetch_headlines()
    selected = select_top_headline(all_headlines)
    save_headlines(selected)
