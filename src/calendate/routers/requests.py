"""Date request action routes."""

import logging
import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse

from ..auth import generate_token, get_current_user
from ..config import settings
from ..db import get_db
from ..utils import render, templates, send_sms
from ..services.calendar import _split_slot_around_booking, _merge_adjacent_slots

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/requests/{request_id}/detail", response_class=HTMLResponse)
async def request_detail(request: Request, request_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    db = await get_db()
    try:
        req = await (await db.execute(
            """SELECT r.*, a.start_time, a.end_time, u.name as host_name
               FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id
               JOIN users u ON a.user_id=u.id WHERE r.id=? AND a.user_id=?""",
            (request_id, user["id"]))).fetchone()
        if not req:
            return HTMLResponse("Not found", status_code=404)
        return render(request, "partials/_request_detail.html", req=dict(req), status=req["status"], base_url=settings.BASE_URL)
    finally:
        await db.close()


@router.post("/requests/{request_id}/approve")
async def approve_request(request: Request, request_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    db = await get_db()
    try:
        req = await (await db.execute(
            """SELECT r.*, a.start_time, a.end_time FROM date_requests r
               JOIN availability_slots a ON r.slot_id=a.id WHERE r.id=? AND a.user_id=?""",
            (request_id, user["id"]))).fetchone()
        if not req:
            return HTMLResponse("Not found", status_code=404)

        share_token = generate_token()
        await db.execute(
            "UPDATE date_requests SET status='approved', share_token=? WHERE id=?",
            (share_token, request_id))

        prop_start = req["proposed_start"] or req["start_time"]
        prop_end = req["proposed_end"] or req["end_time"]
        await _split_slot_around_booking(db, req["slot_id"], prop_start, prop_end)
        await db.commit()
    finally:
        await db.close()

    if request.headers.get("HX-Request"):
        return _dashboard_response(request, user)
    return render(request, "partials/request_card.html", req=dict(req), status="approved", base_url=settings.BASE_URL)


@router.post("/requests/{request_id}/deny")
async def deny_request(request: Request, request_id: int):
    user = await get_current_user(request)
    if not user: raise HTTPException(status_code=401)
    db = await get_db()
    try:
        req = await (await db.execute(
            "SELECT r.* FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE r.id=? AND a.user_id=?", (request_id, user["id"]))).fetchone()
        if not req: return HTMLResponse("Not found", status_code=404)
        await db.execute("DELETE FROM date_requests WHERE id=?", (request_id,))
        await db.commit()
    finally:
        await db.close()

    req_dict = dict(req)
    if req_dict.get("stripe_session_id") and req_dict.get("deposit_paid_cents", 0) > 0:
        try:
            session = stripe.checkout.Session.retrieve(req_dict["stripe_session_id"])
            pi = stripe.PaymentIntent.retrieve(session.payment_intent)
            stripe.Refund.create(payment_intent=pi.id)
        except Exception as e:
            logger.error("Refund failed: %s", e)

    if request.headers.get("HX-Request"):
        return _dashboard_response(request, user)
    return HTMLResponse("")


@router.post("/requests/{request_id}/cancel")
async def cancel_request(request: Request, request_id: int):
    db = await get_db()
    try:
        req = await (await db.execute(
            "SELECT r.*, a.user_id FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE r.id=?", (request_id,))).fetchone()
        if not req: return HTMLResponse("Not found", status_code=404)

        prop_start = req["proposed_start"] or req["start_time"]
        prop_end = req["proposed_end"] or req["end_time"]
        date_str = prop_start[:10]

        # Restore time as open slot
        token = generate_token()
        await db.execute(
            "INSERT INTO availability_slots (user_id, token, start_time, end_time, deposit_cents) VALUES (?,?,?,?,0)",
            (req["user_id"], token, prop_start, prop_end))
        await _merge_adjacent_slots(db, req["user_id"], date_str)

        await db.execute("DELETE FROM date_requests WHERE id=?", (request_id,))
        await db.commit()
    finally:
        await db.close()

    req_dict = dict(req)
    if req_dict.get("stripe_session_id") and req_dict.get("deposit_paid_cents", 0) > 0:
        try:
            session = stripe.checkout.Session.retrieve(req_dict["stripe_session_id"])
            pi = stripe.PaymentIntent.retrieve(session.payment_intent)
            stripe.Refund.create(payment_intent=pi.id)
        except Exception as e:
            logger.error("Refund failed: %s", e)

    user = await get_current_user(request)
    if user and request.headers.get("HX-Request"):
        return _dashboard_response(request, user)
    return HTMLResponse("")


async def _dashboard_response(request, user):
    from ..db import get_db
    from ..services.calendar import _build_calendar
    from datetime import date

    db = await get_db()
    try:
        slots = [dict(r) for r in await (await db.execute(
            "SELECT * FROM availability_slots WHERE user_id=? ORDER BY start_time", (user["id"],))).fetchall()]
        requests = [dict(r) for r in await (await db.execute(
            "SELECT r.*, a.start_time, a.end_time FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? ORDER BY r.created_at DESC", (user["id"],))).fetchall()]
        approved = [dict(r) for r in await (await db.execute(
            "SELECT r.id, r.slot_id FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? AND r.status='approved'", (user["id"],))).fetchall()]
        booked = [r["start_time"][:10] for r in await (await db.execute(
            "SELECT a.start_time FROM date_requests r JOIN availability_slots a ON r.slot_id=a.id WHERE a.user_id=? AND r.status='approved'", (user["id"],))).fetchall()]
    finally:
        await db.close()

    today = date.today()
    cal = _build_calendar(today.year, today.month, slots, booked, approved)

    resp = templates.TemplateResponse(request, "partials/_dashboard_wrapper.html", {
        "request": request, "slots": slots, "requests": requests, "user": user,
        "month": today.month, "year": today.year, "cal": cal, "booked_dates": booked,
        "base_url": settings.BASE_URL,
    })
    resp.headers["HX-Trigger"] = "closeModal"
    return resp
