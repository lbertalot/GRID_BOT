from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

@app.get("/web", response_class=HTMLResponse)
def web_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "GridBot Web"}) 