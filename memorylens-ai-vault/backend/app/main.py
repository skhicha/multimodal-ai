from __future__ import annotations

import os

from dotenv import load_dotenv

# Load backend/.env (if present) before anything reads os.environ.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.db import init_db
from app.routers import admin, ask, auth, collections, dashboard, media, search
from app.routers.auth import limiter
from app.services.pipeline import start_worker

app = FastAPI(
    title="MemoryLens AI",
    description="Personal AI media vault: upload photos/videos, auto-process "
    "(faces, transcripts, EXIF/GPS, tags), browse a timeline/map, full-text "
    "search, and chat with a retrieval-augmented Ask AI assistant.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    start_worker()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(media.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(collections.router)
