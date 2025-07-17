## grid_bot/docker/Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

---

## grid_bot/docker-compose.yml

version: '3.8'

services:
  db:
    image: postgres:16
    container_name: gridbot_db
    restart: always
    environment:
      POSTGRES_USER: griduser
      POSTGRES_PASSWORD: gridpass
      POSTGRES_DB: gridbot
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: gridbot_api
    ports:
      - "8000:8000"
    depends_on:
      - db
    env_file:
      - .env

volumes:
  pgdata:

---

## grid_bot/.env

POSTGRES_USER=griduser
POSTGRES_PASSWORD=gridpass
POSTGRES_DB=gridbot
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://griduser:gridpass@db:5432/gridbot

---

## grid_bot/requirements.txt

fastapi
uvicorn[standard]
SQLAlchemy
psycopg2-binary
python-dotenv

---

## grid_bot/app/main.py

from fastapi import FastAPI
from app.db.session import engine
from app.models import base

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    base.Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "GridBot API running"}

---

## grid_bot/app/db/session.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

---

## grid_bot/app/models/base.py

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
