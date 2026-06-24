"""Auth routes."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import generate_booking_slug, hash_password, normalize_phone, verify_password, get_current_user
from ..db import get_db
from ..utils import render

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render(request, "login.html")


@router.post("/login")
async def login(request: Request, phone: str = Form(...), password: str = Form(...)):
    phone = normalize_phone(phone)
    db = await get_db()
    try:
        row = await db.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        user = await row.fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            return render(request, "login.html", error="Invalid phone or password.")
        request.session["user_phone"] = phone
        return RedirectResponse("/dashboard", status_code=302)
    finally:
        await db.close()


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return render(request, "signup.html")


@router.post("/signup")
async def signup(request: Request, phone: str = Form(...), password: str = Form(...), name: str = Form(...)):
    phone = normalize_phone(phone)
    name = name.strip()

    if not name:
        return render(request, "signup.html", error="Name is required.")
    if len(name) > 40:
        return render(request, "signup.html", error="Name must be 40 characters or fewer.")
    if len(password) < 6:
        return render(request, "signup.html", error="Password must be 6+ characters.")
    if len(password) > 128:
        return render(request, "signup.html", error="Password too long.")
    if not phone or not phone.startswith("+1") or len(phone) != 12:
        return render(request, "signup.html", error="Enter a valid US phone (10 digits).")

    db = await get_db()
    try:
        existing = await db.execute("SELECT id FROM users WHERE phone = ?", (phone,))
        if await existing.fetchone():
            return render(request, "signup.html", error="Phone already registered.")

        slug = generate_booking_slug(name)
        await db.execute(
            "INSERT INTO users (phone, password_hash, name, booking_slug) VALUES (?, ?, ?, ?)",
            (phone, hash_password(password), name, slug),
        )
        await db.commit()
        request.session["user_phone"] = phone
        return RedirectResponse("/dashboard", status_code=302)
    finally:
        await db.close()


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

