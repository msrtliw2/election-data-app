from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jinja2 import TemplateNotFound
import os, json, time, requests
from typing import Tuple, Dict, Any, List

app = FastAPI()

WWW_HOST = "www.election-data.io"

@app.middleware("http")
async def force_www(request: Request, call_next):
    host = request.headers.get("host", "")
    if host and host.lower() == "election-data.io":
        url = request.url.replace(netloc=WWW_HOST)
        return RedirectResponse(url=url, status_code=301)
    return await call_next(request)

if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# Read JSON from a separate branch so code deploys aren't triggered by data commits
RAW_ARTICLES_URL = os.getenv(
    "RAW_JSON_URL",
    "https://raw.githubusercontent.com/msrtliw2/election-data-app/data-updates/data/combined_news.json",
)
RAW_CONST_URL = os.getenv(
    "RAW_CONST_URL",
    "https://raw.githubusercontent.com/msrtliw2/election-data-app/data-updates/data/constituency_rank.json",
)

_cache_articles: Tuple[float, List[Dict[str, Any]]] | None = None
_cache_const: Tuple[float, Dict[str, Any]] | None = None
_CACHE_TTL = 300  # 5 minutes

def get_json(url: str) -> Any:
    r = requests.get(url, timeout=15, headers={"User-Agent": "election-data.io/1.0"})
    r.raise_for_status()
    return r.json()

def get_articles() -> Tuple[List[Dict[str, Any]], str]:
    global _cache_articles
    now = time.time()
    if _cache_articles and now - _cache_articles[0] < _CACHE_TTL:
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_cache_articles[0]))
        return _cache_articles[1], ts
    try:
        data = get_json(RAW_ARTICLES_URL)
        if not isinstance(data, list):
            data = []
        _cache_articles = (now, data)
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now))
        return data, ts
    except Exception:
        if _cache_articles:
            ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_cache_articles[0]))
            return _cache_articles[1], ts
        return [], "unavailable"

def get_constituency_summary() -> Tuple[Dict[str, Any], str]:
    global _cache_const
    now = time.time()
    if _cache_const and now - _cache_const[0] < _CACHE_TTL:
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_cache_const[0]))
        return _cache_const[1], ts
    try:
        data = get_json(RAW_CONST_URL)
        if not isinstance(data, dict):
            data = {}
        _cache_const = (now, data)
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now))
        return data, ts
    except Exception:
        if _cache_const:
            ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_cache_const[0]))
            return _cache_const[1], ts
        return {}, "unavailable"

@app.get("/", response_class=HTMLResponse)
async def site_home(request: Request):
    try:
        return templates.TemplateResponse("site_index.html", {"request": request})
    except TemplateNotFound:
        return HTMLResponse("<h1>Election Data</h1><p><a href='/news'>News →</a></p>")

@app.get("/news", response_class=HTMLResponse)
async def news_home(request: Request, topic: str | None = None):
    all_articles, last_updated = get_articles()
    articles = all_articles if not topic else [
        a for a in all_articles if topic in (a.get("topics") or [])
    ]
    all_topics = sorted({t for a in all_articles for t in (a.get("topics") or [])})
    ctx = {
        "request": request,
        "articles": articles,
        "topics": all_topics,
        "selected_topic": topic or "",
        "last_updated": last_updated,
    }
    try:
        return templates.TemplateResponse("news_index.html", ctx)
    except TemplateNotFound:
        return HTMLResponse(f"<h1>News</h1><p>{len(articles)} articles</p>")

@app.get("/constituency", response_class=HTMLResponse)
async def constituency_page(request: Request, name: str | None = None):
    summary, last_gen = get_constituency_summary()
    all_names = sorted(summary.keys())
    sel = name or (all_names[0] if all_names else "")
    data = summary.get(sel, {"top_articles": [], "count": 0, "top_sources": []})
    ctx = {
        "request": request,
        "all_constituencies": all_names,
        "selected": sel,
        "block": data,
        "last_generated": last_gen,
    }
    try:
        return templates.TemplateResponse("constituency.html", ctx)
    except TemplateNotFound:
        return HTMLResponse(f"<h1>Constituency</h1><p>{sel}</p>")
