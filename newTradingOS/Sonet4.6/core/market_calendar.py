from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Iterable

import holidays
import pandas as pd

_SUPPORTED_EXCHANGES = ("HOSE", "HNX", "UPCOM")
_EXCHANGE_CLOSED_OVERRIDES: dict[str, frozenset[date]] = {
    exchange: frozenset() for exchange in _SUPPORTED_EXCHANGES
}


def _coerce_calendar_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    return datetime.fromisoformat(str(value)).date()


def normalize_exchange(exchange: str | None) -> str:
    normalized = str(exchange or "HOSE").strip().upper()
    return normalized if normalized in _SUPPORTED_EXCHANGES else "HOSE"


@lru_cache(maxsize=32)
def vn_public_holidays(year: int) -> frozenset[date]:
    return frozenset(holidays.country_holidays("VN", years=[year]).keys())


def exchange_closed_overrides(exchange: str | None = None) -> frozenset[date]:
    return _EXCHANGE_CLOSED_OVERRIDES.get(normalize_exchange(exchange), frozenset())


def is_trading_day(day, exchange: str | None = None) -> bool:
    current = _coerce_calendar_date(day)
    return (
        current.weekday() < 5
        and current not in vn_public_holidays(current.year)
        and current not in exchange_closed_overrides(exchange)
    )


def future_trading_dates(start_date, periods: int, exchange: str | None = None) -> pd.DatetimeIndex:
    periods = max(int(periods or 0), 0)
    if periods == 0:
        return pd.DatetimeIndex([])

    current = _coerce_calendar_date(start_date)
    dates: list[pd.Timestamp] = []
    while len(dates) < periods:
        current += timedelta(days=1)
        if not is_trading_day(current, exchange=exchange):
            continue
        dates.append(pd.Timestamp(current))
    return pd.DatetimeIndex(dates)


def trading_sessions_between(
    start_date,
    end_date=None,
    exchange: str | None = None,
) -> int:
    start = _coerce_calendar_date(start_date)
    end = _coerce_calendar_date(end_date or date.today())
    if end <= start:
        return 0

    trading_days = 0
    current = start
    while current <= end:
        if is_trading_day(current, exchange=exchange):
            trading_days += 1
        current += timedelta(days=1)

    start_offset = 1 if is_trading_day(start, exchange=exchange) else 0
    return max(trading_days - start_offset, 0)


@lru_cache(maxsize=96)
def trading_sessions_in_year(year: int, exchange: str | None = None) -> int:
    exchange = normalize_exchange(exchange)
    current = date(year, 1, 1)
    end = date(year, 12, 31)
    sessions = 0
    while current <= end:
        if is_trading_day(current, exchange=exchange):
            sessions += 1
        current += timedelta(days=1)
    return sessions


def annualization_sessions_per_year(
    date_index: Iterable | None = None,
    *,
    exchange: str | None = None,
    fallback_year: int | None = None,
) -> int:
    if date_index is None:
        return trading_sessions_in_year(fallback_year or date.today().year, exchange=exchange)

    years: dict[int, int] = {}
    for value in date_index:
        if value is None:
            continue
        year = _coerce_calendar_date(value).year
        years[year] = years.get(year, 0) + 1

    if not years:
        return trading_sessions_in_year(fallback_year or date.today().year, exchange=exchange)

    total_weight = sum(years.values())
    weighted_sessions = sum(
        count * trading_sessions_in_year(year, exchange=exchange)
        for year, count in years.items()
    )
    return max(int(round(weighted_sessions / total_weight)), 1)


def calendar_basis_label(exchange: str | None = None) -> str:
    exchange = normalize_exchange(exchange)
    override_count = len(exchange_closed_overrides(exchange))
    if override_count:
        return f"VN public holidays + {exchange} overrides:{override_count}"
    return f"VN public holidays ({exchange} shared schedule)"


def calendar_basis_summary(exchange_map: dict[str, str] | None = None) -> str:
    exchanges = sorted({normalize_exchange(exchange) for exchange in (exchange_map or {}).values()})
    if not exchanges:
        return "VN public holidays (shared HOSE/HNX/UPCOM schedule)"

    override_counts = {
        exchange: len(exchange_closed_overrides(exchange))
        for exchange in exchanges
    }
    if any(count > 0 for count in override_counts.values()):
        details = ", ".join(
            f"{exchange}:{count} override" + ("s" if count != 1 else "")
            for exchange, count in override_counts.items()
            if count > 0
        )
        return f"VN public holidays + {details}"
    return "VN public holidays (shared HOSE/HNX/UPCOM schedule)"