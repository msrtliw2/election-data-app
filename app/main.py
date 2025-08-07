from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os

app = FastAPI()

# Static and template setup
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Load articles from JSON
def load_articles():
    data_path = os.path.join("data", "combined_news.json")
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, topic: str = None):
    articles = load_articles()

    # Filter by topic if provided
    if topic:
        articles = [a for a in articles if topic in a.get("topics", [])]

    # Gather list of all topics for dropdown
    all_topics = sorted({t for a in articles for t in a.get("topics", [])})

    return templates.TemplateResponse("index.html", {
        "request": request,
        "articles": articles,
        "topics": all_topics,
        "selected_topic": topic
    })
