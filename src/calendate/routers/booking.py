"""Public booking page — Cal.com style."""

from datetime import date, datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from ..auth import generate_token, normalize_phone
from ..config import settings
from ..db import get_db
from ..services.calendar import _build_booking_calendar, _free_time_ranges
from ..utils import render, send_sms

router = APIRouter()


@router.get("/book/{token}", response_class=HTMLResponse)
async def booking_page(request: Request, token: str):
    """Cal.com-style public booking page."""
    db = await get_db()
    try:
        user = await (await db.execute(
            "SELECT * FROM users WHERE booking_slug = ?", (token,)
        )).fetchone()
        if not user:
            user = await (await db.execute(
                "SELECT u.* FROM availability_slots a JOIN users u ON a.user_id=u.id WHERE a.token=?", (token,)
            )).fetchone()
        if not user:
            return HTMLResponse(
                "<div class='text-center py-20'><h1 class='text-2xl font-bold'>Link not found</h1></div>"
            )

        user = dict(user)
        slots = [dict(r) for r in await (await db.execute(
            "SELECT * FROM availability_slots WHERE user_id=? ORDER BY start_time", (user["id"],)
        )).fetchall()]
    finally:
        await db.close()

    cal = _build_booking_calendar(slots)
    return render(request, "booking.html", host=user, slots=slots, cal=cal, token=user["booking_slug"])


@router.get("/book/{token}/day", response_class=HTMLResponse)
async def booking_day(request: Request, token: str):
    """Show free time windows for a specific day."""
    date_str = request.query_params.get("date", "")
    db = await get_db()
    try:
        user = await (await db.execute("SELECT * FROM users WHERE booking_slug=?", (token,))).fetchone()
        if not user:
            return HTMLResponse("<p class='text-sm text-red-500'>Not found.</p>")
        user = dict(user)

        slots = [dict(r) for r in await (await db.execute(
            "SELECT * FROM availability_slots WHERE user_id=? AND date(start_time)=? ORDER BY start_time",
            (user["id"], date_str)
        )).fetchall()]

        free_slots = []
        for slot in slots:
            booked_rows = await db.execute(
                "SELECT proposed_start, proposed_end FROM date_requests WHERE slot_id=? AND status='approved'",
                (slot["id"],)
            )
            booked = [dict(r) for r in await booked_rows.fetchall()]
            free = _free_time_ranges(slot, booked)
            for f_start, f_end in free:
                free_slots.append({"start_time": f_start, "end_time": f_end, "id": slot["id"]})
    finally:
        await db.close()

    from ..utils import render
    return render(request, "partials/_booking_day.html",
                  slots=free_slots, date_str=date_str, token=token,
                  deposit_cents=user.get("deposit_cents", 0))


@router.post("/book/{token}/reserve")
async def reserve_slot(request: Request, token: str,
                       date_name: str = Form(...), date_phone: str = Form(...),
                       slot_id: int = Form(...),
                       proposed_start: str = Form(""), proposed_end: str = Form(""),
                       location: str = Form(""), label: str = Form("")):
    date_phone = normalize_phone(date_phone)
    date_name = date_name.strip()

    if not date_name:
        return HTMLResponse('<p class="text-sm text-red-500">Name is required.</p>')
    if len(date_name) > 40:
        return HTMLResponse('<p class="text-sm text-red-500">Name must be 40 characters or fewer.</p>')
    if not date_phone or len(date_phone) != 12 or not date_phone.startswith("+1"):
        return HTMLResponse('<p class="text-sm text-red-500">Enter a valid US phone.</p>')

    db = await get_db()
    try:
        slot = await (await db.execute("SELECT * FROM availability_slots WHERE id=?", (slot_id,))).fetchone()
        if not slot:
            return HTMLResponse('<p class="text-sm text-red-500">Slot not found.</p>')

        slot_date = slot["start_time"][:10]
        prop_start = f"{slot_date}T{proposed_start}" if proposed_start else None
        prop_end = f"{slot_date}T{proposed_end}" if proposed_end else None

        if prop_start and prop_end:
            overlap = await db.execute(
                "SELECT id FROM date_requests WHERE slot_id=? AND status='approved' AND proposed_start IS NOT NULL AND proposed_start<? AND proposed_end>?",
                (slot_id, prop_end, prop_start))
            if await overlap.fetchone():
                return HTMLResponse('<p class="text-sm text-red-500">That time is already booked.</p>')

        await db.execute(
            "INSERT INTO date_requests (slot_id, date_name, date_phone, status, proposed_start, proposed_end, location, label) VALUES (?,?,?,?,?,?,?,?)",
            (slot_id, date_name, date_phone, "pending", prop_start, prop_end, location, label))
        await db.commit()
    finally:
        await db.close()

    return HTMLResponse("""
    <div class='text-center py-8'>
        <div class='text-5xl mb-4'>🎉</div>
        <h2 class='text-xl font-bold mb-2'>Request sent!</h2>
        <p class='text-gray-500'>You'll get a text when it's confirmed.</p>
    </div>""")
