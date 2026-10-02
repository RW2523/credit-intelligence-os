"""Ringgit and date formatting shared by every engine, prompt and ledger summary."""
from __future__ import annotations
import datetime as dt

MONTHS_MS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogo", "Sep", "Okt", "Nov", "Dis"]
MONTHS_MS_LONG = ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September",
                  "Oktober", "November", "Disember"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_EN_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
                  "September", "October", "November", "December"]


def rm(x, d: int = 0) -> str:
    """RM18,250 / RM501.80 — never a dollar sign, never 'RM-200'."""
    x = float(x or 0)
    s = f"{abs(x):,.{d}f}"
    return ("-RM" if x < 0 else "RM") + s


def _d(v) -> dt.date:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def date(v, lang: str = "en") -> str:
    d = _d(v)
    return f"{d.day} {(MONTHS_MS if lang == 'ms' else MONTHS_EN)[d.month - 1]} {d.year}"


def month(v, lang: str = "en") -> str:
    d = _d(v)
    return f"{(MONTHS_MS_LONG if lang == 'ms' else MONTHS_EN_LONG)[d.month - 1]} {d.year}"
