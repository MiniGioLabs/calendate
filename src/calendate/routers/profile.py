"""Host profile/settings routes."""

import uuid
import stripe
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import get_current_user
from ..config import settings as app_settings
from ..db import get_db
from ..utils import render, static_dir, upload_to_s3

router = APIRouter()

ALLOWED_AVATAR_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return render(request, "settings.html", user=user)


@router.post("/settings/avatar", response_class=HTMLResponse)
async def update_avatar(request: Request, avatar: UploadFile = File(...)):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ext = ALLOWED_AVATAR_TYPES.get(avatar.content_type)
    if not ext:
        return render(request, "settings.html", user=user, error="Please upload a JPG, PNG, or WEBP image.")

    data = await avatar.read()
    if len(data) > MAX_AVATAR_BYTES:
        return render(request, "settings.html", user=user, error="Image must be under 5MB.")

    user_id = user["id"]
    uid = uuid.uuid4().hex[:8]
    filename = f"{user_id}-{uid}.{ext}"

    # Try S3 first, fall back to local filesystem
    s3_url = upload_to_s3(data, filename, avatar.content_type)
    if s3_url:
        avatar_url = s3_url
    else:
        avatars_dir = static_dir / "avatars"
        avatars_dir.mkdir(parents=True, exist_ok=True)
        (avatars_dir / filename).write_bytes(data)
        avatar_url = f"/static/avatars/{filename}"

    db = await get_db()
    try:
        await db.execute("UPDATE users SET avatar_url=? WHERE id=?", (avatar_url, user["id"]))
        await db.commit()
    finally:
        await db.close()

    return RedirectResponse("/settings", status_code=302)


@router.post("/settings/deposit", response_class=HTMLResponse)
async def update_deposit(request: Request, deposit_dollars: str = Form(...)):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    try:
        amount = float(deposit_dollars)
        if amount != int(amount) or int(amount) < 0 or int(amount) % 5 != 0:
            raise ValueError
        cents = int(amount) * 100
    except ValueError:
        return render(request, "settings.html", user=user, deposit_error="Deposit must be in $5 increments — $5, $10, $15...")

    db = await get_db()
    try:
        await db.execute("UPDATE users SET deposit_cents=? WHERE id=?", (cents, user["id"]))
        await db.commit()
    finally:
        await db.close()

    return RedirectResponse("/settings", status_code=302)


@router.post("/settings/stripe/connect", response_class=HTMLResponse)
async def connect_stripe(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    try:
        account_id = user.get("stripe_account_id")
        if not account_id:
            account = stripe.Account.create(type="express", email=None)
            account_id = account.id
            db = await get_db()
            try:
                await db.execute("UPDATE users SET stripe_account_id=? WHERE id=?", (account_id, user["id"]))
                await db.commit()
            finally:
                await db.close()

        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{app_settings.BASE_URL}/settings",
            return_url=f"{app_settings.BASE_URL}/settings/stripe/return",
            type="account_onboarding",
        )
        return RedirectResponse(link.url, status_code=302)
    except stripe.StripeError as e:
        return render(request, "settings.html", user=user,
                      stripe_error="Couldn't connect to Stripe — check your Stripe configuration.")


@router.get("/settings/stripe/return", response_class=HTMLResponse)
async def stripe_connect_return(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if user.get("stripe_account_id"):
        try:
            account = stripe.Account.retrieve(user["stripe_account_id"])
            complete = 1 if account.get("details_submitted") else 0
            db = await get_db()
            try:
                await db.execute("UPDATE users SET stripe_onboarding_complete=? WHERE id=?", (complete, user["id"]))
                await db.commit()
            finally:
                await db.close()
        except stripe.StripeError:
            pass

    return RedirectResponse("/settings", status_code=302)
