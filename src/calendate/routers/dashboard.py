"""Dashboard routes."""

from datetime import date
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import get_current_user
from ..db import get_db
from ..services.calendar import _build_calendar
from ..utils import render

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = await get_db()
    try:
        user_row = await db.execute("SELECT * FROM users WHERE id=?", (user["id"],))
        user = dict(await user_row.fetchone())

        slots = [dict(r) for r in await (await db.execute(
            "SELECT * FROM availability_slots WHERE user_id=? ORDER BY start_time", (user["id"],)
        )).fetchall()]

        requests = [dict(r) for r in await (await db.execute(
            """SELECT r.*, a.start_time, a.end_time FROM date_requests r
               JOIN availability_slots a ON r.slot_id=a.id
               WHERE a.user_id=? ORDER BY r.created_at DESC""", (user["id"],)
        )).fetchall()]

        approved = [dict(r) for r in await (await db.execute(
            "SELECT r.id, r.slot_id FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? AND r.status='approved'", (user["id"],)
        )).fetchall()]

        booked = [r["start_time"][:10] for r in await (await db.execute(
            "SELECT a.start_time FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? AND r.status='approved'", (user["id"],)
        )).fetchall()]
    finally:
        await db.close()

    today = date.today()
    month = int(request.query_params.get("month") or today.month)
    year = int(request.query_params.get("year") or today.year)
    if month < 1: month = 12; year -= 1
    if month > 12: month = 1; year += 1
    cal = _build_calendar(year, month, slots, booked, approved)

    from ..config import settings
    return render(request, "dashboard.html", user=user, slots=slots, requests=requests,
                  cal=cal, booked_dates=booked, month=month, year=year,
                  base_url=settings.BASE_URL)


@router.get("/dashboard/calendar", response_class=HTMLResponse)
async def dashboard_calendar(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    db = await get_db()
    try:
        slots = [dict(r) for r in await (await db.execute(
            "SELECT * FROM availability_slots WHERE user_id=? ORDER BY start_time", (user["id"],)
        )).fetchall()]

        approved = [dict(r) for r in await (await db.execute(
            "SELECT r.id, r.slot_id FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? AND r.status='approved'", (user["id"],)
        )).fetchall()]

        booked = [r["start_time"][:10] for r in await (await db.execute(
            "SELECT a.start_time FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? AND r.status='approved'", (user["id"],)
        )).fetchall()]
    finally:
        await db.close()

    today = date.today()
    month = int(request.query_params.get("month") or today.month)
    year = int(request.query_params.get("year") or today.year)
    if month < 1: month = 12; year -= 1
    if month > 12: month = 1; year += 1
    cal = _build_calendar(year, month, slots, booked, approved)

    return render(request, "partials/calendar.html", cal=cal, month=month, year=year)
