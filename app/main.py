from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from app.api import router as api_router
from app.scheduler.grid_job import start_scheduler
import logging

app = FastAPI()

# Plantillas Jinja2 para la interfaz web mínima
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.on_event("startup")
def on_startup():
    logging.basicConfig(level=logging.INFO)
    start_scheduler()

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "GridBot Web"})

# Incluyo los endpoints de la API (trade, etc)
app.include_router(api_router) 