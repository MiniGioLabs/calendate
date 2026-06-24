"""Database — SQLite with aiosqlite."""

from __future__ import annotations

import aiosqlite
import logging
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)
_db_path: str | None = None


def _get_db_path() -> str:
    global _db_path
    if _db_path is None:
        _db_path = settings.DATABASE_PATH or str(Path(__file__).parent.parent.parent / "calendate.db")
    return _db_path


async def get_db() -> aiosqlite.Connection:
    """Create a fresh connection per request."""
    db = await aiosqlite.connect(_get_db_path())
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                booking_slug TEXT UNIQUE,
                stripe_account_id TEXT,
                stripe_onboarding_complete INTEGER DEFAULT 0,
                timezone TEXT DEFAULT 'US/Eastern',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS availability_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token TEXT UNIQUE NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                deposit_cents INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS date_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL REFERENCES availability_slots(id),
                date_name TEXT,
                date_phone TEXT,
                status TEXT DEFAULT 'pending',
                proposed_start TEXT,
                proposed_end TEXT,
                location TEXT,
                label TEXT,
                share_token TEXT UNIQUE,
                stripe_session_id TEXT,
                deposit_paid_cents INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES date_requests(id),
                send_at TEXT NOT NULL,
                reminder_type TEXT NOT NULL
            );
        """)
        await db.commit()
        logger.info("Database initialized")
    finally:
        await db.close()
