from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jinja2 import TemplateNotFound
import os, json

app = FastAPI()

# --- Force apex -> www redirect (so election-data.io becomes www.election-data.io) ---
WWW_HOST = "www.election-data.io"  # change if you ever use a different host

@app.middleware("http")
async def force_www(request: Request, call_next):
    host = request.headers.get("host", "")
    # Only redirect if it's the apex (no www) and not hitting Render's preview URL
    if host and host.lower() == "election-data.io":
        url = request.url.replace(netloc=WWW_HOST)
        return RedirectResponse(url=url, status_code=301)
    return await call_next(request)

# --- Static + templates ---
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# --- Data loader for the news page ---
def load_articles():
    path = os.path.join("data", "combined_news.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# --- Routes ---

# Homepage (your single-file site HTML in app/templates/site_index.html)
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

# News dashboard
@app.get("/news", response_class=HTMLResponse)
async def news_home(request: Request, topic: str | None = None):
    all_articles = load_articles()
    articles = all_articles if not topic else [a for a in all_articles if topic in (a.get('topics') or [])]
    all_topics = sorted({t for a in all_articles for t in (a.get('topics') or [])})
    try:
        return templates.TemplateResponse(
            "news_index.html",
            {
                "request": request,
                "articles": articles,
                "topics": all_topics,
                "selected_topic": topic or "",
            },
        )
    except TemplateNotFound:
        return HTMLResponse(
            f"<h1>News</h1><p>Template missing. "
            f"Add <code>app/templates/news_index.html</code>. "
            f"Found {len(articles)} articles in data/combined_news.json.</p>"
        )
