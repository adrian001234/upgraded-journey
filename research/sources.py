"""
TechPulse - Research Stage
Pulls trending tech / AI / science headlines from free RSS feeds.
No API key required.
"""

import feedparser
import json
from datetime import datetime

# Free, no-key-required RSS feeds covering tech / AI / science
FEEDS = {
    "techcrunch": "https://techcrunch.com/feed/",
    "verge": "https://www.theverge.com/rss/index.xml",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
    "science_daily": "https://www.sciencedaily.com/rss/top/technology.xml",
}


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
            })
    return results


def save_headlines(headlines, path="research/latest_headlines.json"):
    """Save fetched headlines to a JSON file."""
    with open(path, "w") as f:
        json.dump(headlines, f, indent=2)
    print(f"Saved {len(headlines)} headlines to {path}")


if __name__ == "__main__":
    headlines = fetch_headlines()
    save_headlines(headlines)
