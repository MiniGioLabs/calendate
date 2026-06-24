"""Calendar building + slot splitting/merging."""


def _build_calendar(year: int, month: int, slots: list, booked: list, approved_requests: list = None) -> list:
    import calendar as cal_mod
    from datetime import date

    today = date.today()
    cal = cal_mod.Calendar(cal_mod.SUNDAY)
    booked_dates = set(booked)

    slot_request_map = {}
    if approved_requests:
        for req in approved_requests:
            slot_request_map[req["slot_id"]] = req["id"]

    by_date = {}
    for s in slots:
        ds = s["start_time"][:10]
        by_date.setdefault(ds, []).append(s)

    weeks = []
    for week in cal.monthdayscalendar(year, month):
        week_days = []
        for day_num in week:
            if day_num == 0:
                week_days.append({"day": "", "date_str": "", "slots": [], "is_today": False, "is_other_month": True})
            else:
                ds = f"{year}-{month:02d}-{day_num:02d}"
                day_slots = by_date.get(ds, [])
                slot_list = []
                for s in day_slots:
                    status = "booked" if s["start_time"][:10] in booked_dates else "open"
                    slot_list.append({
                        "id": s["id"], "start_time": s["start_time"], "end_time": s["end_time"],
                        "status": status,
                        "request_id": slot_request_map.get(s["id"]) if status == "booked" else None,
                    })
                week_days.append({"day": day_num, "date_str": ds, "slots": slot_list,
                                  "is_today": ds == today.isoformat(), "is_other_month": False})
        weeks.append(week_days)
    return weeks


def _build_booking_calendar(slots: list, year: int = None, month: int = None) -> dict:
    import calendar as cal_mod
    from datetime import date

    today = date.today()
    if year is None: year = today.year
    if month is None: month = today.month

    cal = cal_mod.Calendar(cal_mod.SUNDAY)
    open_dates = set(s["start_time"][:10] for s in slots)

    weeks = []
    for week in cal.monthdayscalendar(year, month):
        week_days = []
        for day_num in week:
            if day_num == 0:
                week_days.append({"day": "", "date_str": "", "is_open": False, "is_today": False, "is_other_month": True})
            else:
                ds = f"{year}-{month:02d}-{day_num:02d}"
                week_days.append({"day": day_num, "date_str": ds, "is_open": ds in open_dates,
                                  "is_today": ds == today.isoformat(), "is_other_month": False})
        weeks.append(week_days)
    return {"year": year, "month": month, "weeks": weeks}


def _free_time_ranges(slot: dict, booked: list[dict]) -> list:
    from datetime import datetime

    slot_start = datetime.fromisoformat(slot["start_time"])
    slot_end = datetime.fromisoformat(slot["end_time"])

    booked_intervals = []
    for req in booked:
        b_start = req.get("proposed_start")
        b_end = req.get("proposed_end")
        if b_start and b_end:
            booked_intervals.append((datetime.fromisoformat(b_start), datetime.fromisoformat(b_end)))

    booked_intervals.sort()
    merged = []
    for start, end in booked_intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    free = []
    cursor = slot_start
    for b_start, b_end in merged:
        if cursor < b_start:
            free.append((cursor.isoformat(), b_start.isoformat()))
        cursor = max(cursor, b_end)
    if cursor < slot_end:
        free.append((cursor.isoformat(), slot_end.isoformat()))
    return free


async def _split_slot_around_booking(db, slot_id: int, booked_start: str, booked_end: str) -> None:
    from ..auth import generate_token

    row = await db.execute("SELECT * FROM availability_slots WHERE id=?", (slot_id,))
    slot = await row.fetchone()
    if not slot: return

    if booked_start > slot["start_time"]:
        await db.execute(
            "INSERT INTO availability_slots (user_id, token, start_time, end_time, deposit_cents) VALUES (?,?,?,?,0)",
            (slot["user_id"], generate_token(), slot["start_time"], booked_start))
    if booked_end < slot["end_time"]:
        await db.execute(
            "INSERT INTO availability_slots (user_id, token, start_time, end_time, deposit_cents) VALUES (?,?,?,?,0)",
            (slot["user_id"], generate_token(), booked_end, slot["end_time"]))


async def _merge_adjacent_slots(db, user_id: int, date_str: str) -> None:
    rows = await db.execute(
        "SELECT * FROM availability_slots WHERE user_id=? AND date(start_time)=? ORDER BY start_time",
        (user_id, date_str))
    slots = [dict(r) for r in await rows.fetchall()]
    if len(slots) < 2: return

    merged = [slots[0]]
    for s in slots[1:]:
        last = merged[-1]
        if s["start_time"] <= last["end_time"]:
            if s["end_time"] > last["end_time"]:
                await db.execute("UPDATE availability_slots SET end_time=? WHERE id=?", (s["end_time"], last["id"]))
                last["end_time"] = s["end_time"]
            await db.execute("DELETE FROM availability_slots WHERE id=?", (s["id"],))
        else:
            merged.append(s)
