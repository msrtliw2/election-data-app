from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jinja2 import TemplateNotFound
import os, json, time, requests
from typing import Tuple, List, Dict, Any

app = FastAPI()

# --- Force apex -> www redirect (so election-data.io becomes www.election-data.io) ---
WWW_HOST = "www.election-data.io"  # change if you ever use a different host

@app.middleware("http")
async def force_www(request: Request, call_next):
    host = request.headers.get("host", "")
    if host and host.lower() == "election-data.io":
        url = request.url.replace(netloc=WWW_HOST)
        return RedirectResponse(url=url, status_code=301)
    return await call_next(request)

# --- Static + templates ---
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# === Live data source (GitHub Raw) ===
# Example: https://raw.githubusercontent.com/msrtliw2/election-data-app/main/data/combined_news.json
RAW_JSON_URL = os.getenv(
    "RAW_JSON_URL",
    "https://raw.githubusercontent.com/msrtliw2/election-data-app/main/data/combined_news.json",
)

# Simple in-memory cache (5 minutes)
_cache_blob: Tuple[float, List[Dict[str, Any]]] | None = None
_CACHE_TTL_SECONDS = 300  # 5 minutes

def fetch_latest_articles() -> Tuple[List[Dict[str, Any]], str]:
    """
    Fetch latest combined_news.json from GitHub Raw with a 5-minute cache.
    Returns (articles, last_updated_str)
    """
    global _cache_blob
    now = time.time()

    # Use cache if fresh
    if _cache_blob and (now - _cache_blob[0] < _CACHE_TTL_SECONDS):
        articles = _cache_blob[1]
        last_updated = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_cache_blob[0]))
        return articles, last_updated

    # Fetch from GitHub Raw
    try:
        r = requests.get(RAW_JSON_URL, timeout=15, headers={"User-Agent": "election-data.io/1.0"})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            _cache_blob = (now, data)
            last_updated = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now))
            return data, last_updated
        else:
            # Fallback: empty list if malformed
            _cache_blob = (now, [])
            last_updated = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now))
            return [], last_updated
    except Exception:
        # If fetch fails, serve cached (even if stale) or empty
        if _cache_blob:
            articles = _cache_blob[1]
            last_updated = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_cache_blob[0]))
            return articles, last_updated
        return [], "unavailable"

# --- Routes ---

# Homepage
@app.get("/", response_class=HTMLResponse)
async def site_home(request: Request):
    try:
        return templates.TemplateResponse("site_index.html", {"request": request})
    except TemplateNotFound:
        return HTMLResponse(
            "<h1>Election Data</h1>"
            "<p>Homepage template missing. Add <code>app/templates/site_index.html</code>.</p>"
            "<p><a href='/news'>Go to News →</a></p>"
        )

# News dashboard (pulls live JSON from GitHub)
@app.get("/news", response_class=HTMLResponse)
async def news_home(request: Request, topic: str | None = None):
    all_articles, last_updated = fetch_latest_articles()
    articles = all_articles if not topic else [
        a for a in all_articles if topic in (a.get("topics") or [])
    ]
    all_topics = sorted({t for a in all_articles for t in (a.get("topics") or [])})

    try:
        return templates.TemplateResponse(
            "news_index.html",
            {
                "request": request,
                "articles": articles,
                "topics": all_topics,
                "selected_topic": topic or "",
                "last_updated": last_updated,
            },
        )
    except TemplateNotFound:
        return HTMLResponse(
            f"<h1>News</h1>"
            f"<p>Template missing. Found {len(articles)} articles.</p>"
            f"<p>Last updated: {last_updated}</p>"
        )
