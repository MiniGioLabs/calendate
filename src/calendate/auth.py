"""Authentication helpers."""

from __future__ import annotations

import re
import secrets

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_token() -> str:
    return secrets.token_urlsafe(8)


def generate_booking_slug(name: str) -> str:
    import string
    base62 = string.digits + string.ascii_letters
    suffix = "".join(secrets.choice(base62) for _ in range(8))
    clean = re.sub(r"[^a-zA-Z0-9]", "", name).lower()[:20] or "user"
    return f"{clean}-{suffix}"


def normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


async def get_current_user(request) -> dict | None:
    from .db import get_db
    phone = request.session.get("user_phone")
    if not phone:
        return None
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT * FROM users WHERE phone = ?", (phone,)
        )
        user = await row.fetchone()
        return dict(user) if user else None
    finally:
        await db.close()
