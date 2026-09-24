"""Utility: Vietnamese trading calendar helpers."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


# ── Vietnam timezone (UTC+7) ──────────────────────────────────────────────────

VN_TZ = timezone(timedelta(hours=7))


def vn_now() -> datetime:
    """Return the current datetime in Vietnam timezone (UTC+7)."""
    return datetime.now(VN_TZ)


def vn_session_phase() -> str:
    """
    Return the current HOSE/HNX trading session phase based on Vietnam time.
    Phases: PRE_MARKET | PRE_ATO | ATO | MORNING | LUNCH | AFTERNOON | NEAR_ATC | ATC | CLOSED
    """
    now = vn_now().time()
    if now < time(9, 0):      return "PRE_MARKET"
    elif now < time(9, 15):   return "PRE_ATO"   # ATO order input 9:00-9:15
    elif now < time(9, 20):   return "ATO"        # ATO matching + settle buffer 9:15-9:20
    elif now < time(11, 30):  return "MORNING"    # HOSE continuous morning 9:20-11:30
    elif now < time(13, 0):   return "LUNCH"      # HOSE break 11:30-13:00
    elif now < time(14, 30):  return "AFTERNOON"
    elif now < time(14, 43):  return "NEAR_ATC"
    elif now <= time(14, 45): return "ATC"
    else:                     return "CLOSED"


def vn_is_atc_time() -> bool:
    """Return True when currently inside the ATC window (14:43–14:45 Vietnam time)."""
    now = vn_now().time()
    return time(14, 43) <= now <= time(14, 45)


# VN public holidays 2025-2026 (static; extend as needed)
_VN_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),
    date(2025, 1, 27), date(2025, 1, 28), date(2025, 1, 29),
    date(2025, 1, 30), date(2025, 1, 31), date(2025, 2, 3),
    date(2025, 4, 7), date(2025, 4, 30), date(2025, 5, 1),
    date(2025, 9, 1), date(2025, 9, 2),
    # 2026
    date(2026, 1, 1),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20),
    date(2026, 4, 17), date(2026, 4, 30), date(2026, 5, 1),
    date(2026, 9, 2),
    # 2027  (Lỳ Tết Ất Tỵ 2027 = 28/1; các ngày nghỉ lễ)
    date(2027, 1, 1),
    date(2027, 1, 25), date(2027, 1, 26), date(2027, 1, 27),
    date(2027, 1, 28), date(2027, 1, 29),
    date(2027, 4, 6),   # Giỗ Tổ Hùng Vương (10/3 âm lịch)
    date(2027, 4, 30), date(2027, 5, 1),
    date(2027, 9, 2),
}


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in _VN_HOLIDAYS


def prev_trading_day(d: date | None = None) -> date:
    d = d or date.today()
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def next_trading_day(d: date | None = None) -> date:
    d = d or date.today()
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def trading_day_offset(d: date, n: int) -> date:
    """Return d + n trading days (n can be negative)."""
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    cur = d
    while remaining > 0:
        cur += timedelta(days=step)
        if is_trading_day(cur):
            remaining -= 1
    return cur


def trading_days_between(start: date, end: date) -> int:
    """Count trading days in [start, end) exclusive of end."""
    count = 0
    d = start
    while d < end:
        if is_trading_day(d):
            count += 1
        d += timedelta(days=1)
    return count


def last_n_trading_days(n: int, as_of: date | None = None) -> list[date]:
    """Return list of last n trading days ending at as_of (inclusive if trading)."""
    end = as_of or date.today()
    result: list[date] = []
    d = end
    while len(result) < n:
        if is_trading_day(d):
            result.append(d)
        d -= timedelta(days=1)
    return list(reversed(result))
