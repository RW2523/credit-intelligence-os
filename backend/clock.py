"""Malaysia time, and the demo's notion of "today".

Every timestamp the platform writes is in Asia/Kuala_Lumpur (UTC+8). The synthetic data is laid
out relative to one anchor date so the demo never goes stale:

  * CIOS_TODAY=YYYY-MM-DD   freezes "today" to a demo day (new events are shifted to match);
  * otherwise the anchor is the date the database was first created, stored in it, so restarting
    the service keeps the data consistent. CIOS_RESET=1 (a fresh database) re-anchors to today.
"""
from __future__ import annotations
import os, datetime as dt
from zoneinfo import ZoneInfo

import store

TZ = ZoneInfo("Asia/Kuala_Lumpur")


def _anchor() -> tuple[dt.date, bool]:
    env = os.environ.get("CIOS_TODAY", "").strip()
    if env:
        return dt.date.fromisoformat(env), True
    store.init()
    saved = store.get("demo_anchor")
    if saved:
        return dt.date.fromisoformat(saved), False
    d = dt.datetime.now(TZ).date()
    store.put("demo_anchor", d.isoformat())
    return d, False


TODAY, FROZEN = _anchor()
# when the demo day is frozen, new events move with it so they never predate the seeded cases
_SHIFT = (TODAY - dt.datetime.now(TZ).date()) if FROZEN else dt.timedelta(0)


def now() -> dt.datetime:
    return dt.datetime.now(TZ) + _SHIFT


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def at(day: dt.date, hh: int = 9, mm: int = 0) -> str:
    """ISO timestamp in Malaysia time for a seeded event."""
    return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ).isoformat(timespec="seconds")


def days_ago(n: int, hh: int = 9, mm: int = 0) -> str:
    return at(TODAY - dt.timedelta(days=n), hh, mm)


def add_months(d: dt.date, n: int, day: int | None = None) -> dt.date:
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    last = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31][m - 1]
    return dt.date(y, m, min(day or d.day, last))


def months_between(a: dt.date, b: dt.date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)
