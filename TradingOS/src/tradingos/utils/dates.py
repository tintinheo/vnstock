"""Utility: Vietnamese trading calendar helpers."""
from __future__ import annotations

from datetime import date, timedelta


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
