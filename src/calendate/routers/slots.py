"""Slot CRUD routes."""

from datetime import date, datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..auth import generate_token, get_current_user
from ..db import get_db
from ..utils import render, templates

router = APIRouter()


@router.post("/slots", response_class=HTMLResponse)
async def create_slot(request: Request, start_time: str = Form(...), end_time: str = Form(...),
                      cal_month: str = Form(""), cal_year: str = Form(""), all_day: str = Form("")):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    if end_time <= start_time:
        if request.headers.get("HX-Request"):
            resp = HTMLResponse('<div class="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-xl mt-2">End time must be after start.</div>')
            resp.headers["HX-Retarget"] = "#modal-error"
            resp.headers["HX-Reswap"] = "innerHTML"
            return resp
        return RedirectResponse("/dashboard?error=invalid_times", status_code=302)

    db = await get_db()
    try:
        token = generate_token()
        await db.execute(
            "INSERT INTO availability_slots (user_id, token, start_time, end_time, deposit_cents) VALUES (?, ?, ?, ?, 0)",
            (user["id"], token, start_time, end_time),
        )
        await db.commit()
    finally:
        await db.close()

    if request.headers.get("HX-Request"):
        return _dashboard_response(request, user, cal_month, cal_year)

    return RedirectResponse("/dashboard", status_code=302)


@router.delete("/slots/{slot_id}")
async def delete_slot(request: Request, slot_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    db = await get_db()
    try:
        await db.execute("DELETE FROM availability_slots WHERE id = ? AND user_id = ?", (slot_id, user["id"]))
        await db.commit()
    finally:
        await db.close()

    if request.headers.get("HX-Request"):
        return _dashboard_response(request, user)

    return RedirectResponse("/dashboard", status_code=302)


@router.post("/slots/{slot_id}/edit")
async def edit_slot(request: Request, slot_id: int, start_time: str = Form(...), end_time: str = Form(...)):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    db = await get_db()
    try:
        await db.execute(
            "UPDATE availability_slots SET start_time = ?, end_time = ? WHERE id = ? AND user_id = ?",
            (start_time, end_time, slot_id, user["id"]),
        )
        await db.commit()
    finally:
        await db.close()
    return RedirectResponse("/dashboard", status_code=302)


async def _dashboard_response(request, user, month=None, year=None):
    from ..db import get_db
    from ..services.calendar import _build_calendar
    from datetime import date

    db = await get_db()
    try:
        slots = [dict(r) for r in await (await db.execute(
            "SELECT * FROM availability_slots WHERE user_id = ? ORDER BY start_time", (user["id"],)
        )).fetchall()]
        requests = [dict(r) for r in await (await db.execute(
            """SELECT r.*, a.start_time, a.end_time FROM date_requests r
               JOIN availability_slots a ON r.slot_id = a.id
               WHERE a.user_id = ? ORDER BY r.created_at DESC""", (user["id"],)
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
    m = int(month or request.query_params.get("month") or today.month)
    y = int(year or request.query_params.get("year") or today.year)
    cal = _build_calendar(y, m, slots, booked, approved)

    from ..config import settings
    resp = templates.TemplateResponse(request, "partials/_dashboard_wrapper.html", {
        "request": request, "slots": slots, "requests": requests, "user": user,
        "month": m, "year": y, "cal": cal, "booked_dates": booked,
        "base_url": settings.BASE_URL,
    })
    resp.headers["HX-Trigger"] = "closeModal"
    return resp
