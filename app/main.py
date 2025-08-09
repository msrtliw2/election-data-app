from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jinja2 import TemplateNotFound
import json
import os

app = FastAPI()

# Mount /static only if the folder exists (prevents startup errors)
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

def load_articles():
    path = os.path.join("data", "combined_news.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.get("/", response_class=HTMLResponse)
async def site_home(request: Request):
    # Try to render your restored site homepage (site_index.html).
    try:
        return templates.TemplateResponse("site_index.html", {"request": request})
    except TemplateNotFound:
        # Temporary fallback so the site shows something while we add files.
        return HTMLResponse(
            "<h1>Election Data</h1>"
            "<p>Homepage template not added yet. "
            "Continue setup, or visit <a href='/news'>/news</a>.</p>"
        )

@app.get("/news", response_class=HTMLResponse)
async def news_home(request: Request, topic: str | None = None):
    all_articles = load_articles()
    articles = all_articles
    if topic:
        articles = [a for a in all_articles if topic in (a.get('topics') or [])]

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
        # Temporary fallback while we add the template next.
        return HTMLResponse(
            f"<h1>News</h1><p>Template not added yet. "
            f"Found {len(articles)} articles in data/combined_news.json.</p>"
        )
