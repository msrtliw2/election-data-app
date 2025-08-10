#!/usr/bin/env python3
"""
Update data/combined_news.json by pulling the latest items from site RSS feeds
(or auto-discovering them). Keeps it light so it runs fast on GitHub Actions.
"""

import json, time, re, sys, hashlib
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import feedparser

BASE_DIR = Path(__file__).resolve().parents[1]  # repo root
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTFILE = DATA_DIR / "combined_news.json"

# Seed list of sites (add more later)
SITES = [
    "https://www.theboltonnews.co.uk/",
    "https://www.manchestereveningnews.co.uk/",
    "https://www.bournemouthecho.co.uk/",
    "https://www.thetelegraphandargus.co.uk/",
    "https://www.lep.co.uk/",
    "https://www.theargus.co.uk/",
    "https://www.bathchronicle.co.uk/",
    "https://www.birminghamlive.co.uk/",
    "https://www.birminghampost.co.uk/",
    "https://www.wigantoday.net/",
]

HEADERS = {"User-Agent": "election-data.io-bot/1.0 (+https://www.election-data.io)"}

def discover_rss(url: str) -> List[str]:
    """Try to find RSS/Atom links in <link rel='alternate'> tags."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    feeds = []
    for link in soup.find_all("link", rel=lambda x: x and "alternate" in x.lower()):
        t = (link.get("type") or "").lower()
        href = link.get("href")
        if not href:
            continue
        if "rss" in t or "atom" in t or href.endswith((".rss", ".xml", "/feed")):
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                # make absolute
                from urllib.parse import urljoin
                href = urljoin(url, href)
            feeds.append(href)
    # de-dup
    uniq = []
    seen = set()
    for f in feeds:
        if f not in seen:
            uniq.append(f)
            seen.add(f)
    return uniq[:3]  # keep it small

def parse_feed(feed_url: str) -> List[Dict]:
    d = feedparser.parse(feed_url)
    items = []
    for e in d.entries[:20]:
        title = getattr(e, "title", "").strip()
        link = getattr(e, "link", "").strip()
        summary = (getattr(e, "summary", "") or getattr(e, "description", "") or "").strip()
        # published
        published = ""
        if getattr(e, "published", None):
            published = e.published
        elif getattr(e, "updated", None):
            published = e.updated
        items.append({
            "title": title,
            "url": link,
            "summary": BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)[:500],
            "published": published,
            "source": d.feed.get("title", "") if d.feed else "",
            "topics": [],            # (optional: fill via NLP later)
            "entities": {"people": [], "locations": []},  # placeholders
        })
    return items

def collect() -> List[Dict]:
    all_items = []
    seen_links = set()
    for site in SITES:
        feeds = discover_rss(site)
        # Fallback: common patterns if auto-discovery fails
        if not feeds:
            cand = [
                site.rstrip("/") + "/rss",
                site.rstrip("/") + "/feed",
                site.rstrip("/") + "/rss.xml",
                site.rstrip("/") + "/feed.xml",
            ]
            feeds = cand
        for f in feeds:
            try:
                items = parse_feed(f)
            except Exception:
                continue
            for it in items:
                url = it.get("url")
                if not url or url in seen_links:
                    continue
                seen_links.add(url)
                all_items.append(it)
        # brief politeness
        time.sleep(1.0)
    # simple sort: newest first by published text (best-effort)
    def _key(x):
        return x.get("published") or ""
    all_items.sort(key=_key, reverse=True)
    return all_items[:200]

def main():
    items = collect()
    # Only write if changed (reduces noisy commits)
    new_blob = json.dumps(items, ensure_ascii=False, indent=2)
    new_hash = hashlib.sha256(new_blob.encode("utf-8")).hexdigest()

    if OUTFILE.exists():
        old_blob = OUTFILE.read_text(encoding="utf-8")
        old_hash = hashlib.sha256(old_blob.encode("utf-8")).hexdigest()
        if new_hash == old_hash:
            print("No changes detected; skipping write.")
            return

    OUTFILE.write_text(new_blob, encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUTFILE}")

if __name__ == "__main__":
    sys.exit(main())
