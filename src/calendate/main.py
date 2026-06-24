"""CalenDate — FastAPI app entry point. Cal.com-inspired scheduling."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import stripe
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .utils import render, templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .db import init_db
    await init_db()
    yield


app = FastAPI(title="CalenDate", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="caldate")

static_dir = Path(settings.STATIC_DIR) if settings.STATIC_DIR else Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

from .routers import auth, dashboard, slots, booking, requests
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(slots.router)
app.include_router(booking.router)
app.include_router(requests.router)


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return render(request, "landing.html")


@app.get("/health")
async def health():
    from .db import get_db
    db = await get_db()
    try:
        await db.execute("SELECT 1")
        return {"status": "ok"}
    finally:
        await db.close()
