"""Data normalizer: tick-size rounding, ex-dividend adjustment."""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── VN Tick Size Table ────────────────────────────────────────────────────────

def tick_size(price: float, exchange: str = "HOSE") -> int:
    """Return tick size in VND for given price and exchange."""
    if exchange == "HOSE":
        if price < 10_000:
            return 10
        elif price < 50_000:
            return 50
        elif price < 100_000:
            return 100
        else:
            return 100
    else:  # HNX, UPCOM
        return 100


def round_to_tick(price: float, exchange: str = "HOSE") -> float:
    """Round price to nearest valid tick."""
    t = tick_size(price, exchange)
    return round(round(price / t) * t, 0)


# ── Ex-Dividend Adjustment ────────────────────────────────────────────────────

def adjust_ex_dividend(df: pd.DataFrame, dividend_events: list[dict]) -> pd.DataFrame:
    """
    Backward-adjust OHLCV for ex-dividend events.

    dividend_events: list of {date: str, dividend: float (VND per share)}
    Returns a copy of df with adjusted close/open/high/low.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    cumulative_ratio = 1.0
    for event in sorted(dividend_events, key=lambda e: e["date"], reverse=True):
        ex_date = pd.to_datetime(event["date"])
        div = float(event["dividend"])
        mask = df["date"] < ex_date
        if mask.any():
            # Price before ex-date has div baked in; adjust backward
            ref_price = df.loc[df["date"] >= ex_date, "close"].iloc[0] if (df["date"] >= ex_date).any() else df["close"].iloc[-1]
            ratio = (ref_price - div) / ref_price
            cumulative_ratio *= ratio
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df.loc[mask, col] = df.loc[mask, col] * ratio

    return df


# ── OHLCV Cleaning ────────────────────────────────────────────────────────────

def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Remove zero-volume rows, fill gaps, ensure dtypes."""
    df = df.copy()
    df = df[df["volume"] > 0].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalise from thousands-VND (e.g. 57.7) to full VND (57 700).
    # SSI iboard-api returns prices in thousands; this converts once at the
    # data boundary so all downstream code works in full VND.
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = normalize_price_series(df[col])

    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
    df = df.dropna(subset=["close"])
    return df


# ── Price Scale Detection ─────────────────────────────────────────────────────

def detect_price_scale(price: float) -> str:
    """Detect whether price is in VND units (>= 100) or thousands (need ×1000)."""
    if price < 100:
        return "thousands"
    return "vnd"


def normalize_price_series(series: pd.Series) -> pd.Series:
    """Convert prices that appear to be in thousands to full VND."""
    median = series.median()
    if detect_price_scale(median) == "thousands":
        return series * 1000
    return series
