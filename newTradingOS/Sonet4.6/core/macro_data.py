"""
core/macro_data.py — NewTradingOS v14.0
World markets, VN-Index breadth, foreign flow, NHNN rates.
All data from free public APIs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests

from config import WORLD_SYMBOLS, API_TIMEOUT

logger = logging.getLogger("TradingOS.macro")

_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept":     "application/json",
}


# ─────────────────────────────────────────────────────────────
# WORLD MARKETS
# ─────────────────────────────────────────────────────────────
def _yahoo_price(yf_symbol: str, period: str = "3mo") -> Optional[dict]:
    """
    Fetch closing price history from Yahoo Finance chart API.
    Returns dict with 'prices' (list), 'timestamps' (list), 'current', 'pct_5d'.
    """
    url = _YAHOO_CHART.format(symbol=yf_symbol)
    params = {"range": period, "interval": "1d", "includePrePost": False}
    try:
        r = requests.get(url, headers=_YAHOO_HEADERS, params=params,
                         timeout=API_TIMEOUT)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        closes = result["indicators"]["quote"][0].get("close", [])
        timestamps = result.get("timestamp", [])
        closes  = [c for c in closes if c is not None]
        if not closes:
            return None
        current = closes[-1]
        pct_1d  = ((closes[-1] / closes[-2]) - 1) * 100 if len(closes) >= 2 else 0
        pct_5d  = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) >= 6 else 0
        pct_20d = ((closes[-1] / closes[-21]) - 1) * 100 if len(closes) >= 21 else 0
        return {
            "current":   current,
            "pct_1d":    round(pct_1d, 2),
            "pct_5d":    round(pct_5d, 2),
            "pct_20d":   round(pct_20d, 2),
            "prices":    closes,
            "timestamps": timestamps,
        }
    except Exception as exc:
        logger.debug("Yahoo %s: %s", yf_symbol, exc)
        return None


def fetch_world_markets() -> dict[str, Optional[dict]]:
    """
    Fetch all world market indicators in parallel.

    Returns
    -------
    dict[name → {current, pct_1d, pct_5d, pct_20d, prices, timestamps}]
    """
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(WORLD_SYMBOLS))) as pool:
        futures = {
            name: pool.submit(_yahoo_price, yf_sym)
            for name, yf_sym in WORLD_SYMBOLS.items()
        }
        return {name: fut.result() for name, fut in futures.items()}


# ─────────────────────────────────────────────────────────────
# VN-INDEX & MARKET BREADTH
# ─────────────────────────────────────────────────────────────
def fetch_vni_data(days: int = 365) -> pd.DataFrame:
    """
    Fetch VN-Index (VNINDEX) daily OHLCV from DNSE Entrade.
    Returns empty DataFrame on failure.
    """
    from core.data_fetcher import _fetch_dnse
    df = _fetch_dnse("VNINDEX", days=days)
    if df.empty:
        # fallback: Yahoo Finance
        data = _yahoo_price("^VN30", "2y")
        if data and data["prices"]:
            df = pd.DataFrame({"Close": data["prices"]})
    return df


def fetch_market_breadth() -> dict:
    """
    Fetch advance/decline data from SSI iBoard.
    Returns dict with advance, decline, unchanged counts.
    """
    url = "https://iboard-query.ssi.com.vn/v2/market/advance-decline"
    try:
        r = requests.get(url, timeout=API_TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        return {
            "advance":   int(data.get("advance",   data.get("up",   0))),
            "decline":   int(data.get("decline",   data.get("down", 0))),
            "unchanged": int(data.get("unchanged", data.get("noChange", 0))),
            "fetch_ok":  True,
        }
    except Exception as exc:
        logger.debug("Breadth: %s", exc)
        return {"advance": 0, "decline": 0, "unchanged": 0, "fetch_ok": False}


# ─────────────────────────────────────────────────────────────
# FOREIGN FLOW
# ─────────────────────────────────────────────────────────────
def fetch_foreign_flow_ticker(symbol: str) -> dict:
    """
    Fetch foreign buy/sell for a specific ticker via TCBS API.

    Returns
    -------
    dict with keys: net_buy_value, buy_value, sell_value, net_20d, trend_20d
    All values in VND.
    net_20d is the cumulative net foreign buy over the most-recent 20 sessions
    (or however many are available). trend_20d is one of: 'accumulate', 'distribute',
    'neutral'.
    """
    url = f"https://analysis.tcbs.com.vn/api/v1/stock/{symbol}/investors"
    try:
        r = requests.get(url, timeout=API_TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        items = data.get("data", [])
        if not items:
            return {"net_buy_value": 0, "buy_value": 0, "sell_value": 0,
                    "net_20d": 0, "trend_20d": "neutral"}

        latest = items[0]
        net_today = (
            float(latest.get("foreignBuyValue", 0) or 0)
            - float(latest.get("foreignSellValue", 0) or 0)
        )

        # 20-day cumulative net  — previously unimplemented
        window = items[:20]  # API returns newest-first
        net_20d = sum(
            float(d.get("foreignBuyValue", 0) or 0)
            - float(d.get("foreignSellValue", 0) or 0)
            for d in window
        )
        if net_20d > 5e10:      # >50B VND net buy over 20 days
            trend_20d = "accumulate"
        elif net_20d < -5e10:
            trend_20d = "distribute"
        else:
            trend_20d = "neutral"

        return {
            "net_buy_value": net_today,
            "buy_value":     float(latest.get("foreignBuyValue",  0) or 0),
            "sell_value":    float(latest.get("foreignSellValue", 0) or 0),
            "net_20d":       net_20d,
            "trend_20d":     trend_20d,
        }
    except Exception as exc:
        logger.debug("ForeignFlow %s: %s", symbol, exc)
        return {"net_buy_value": 0, "buy_value": 0, "sell_value": 0,
                "net_20d": 0, "trend_20d": "neutral"}


def fetch_market_foreign_flow(days: int = 20) -> dict:
    """
    Fetch aggregate market foreign flow from SSI iBoard.

    Returns
    -------
    dict with net_buy (VND), buy, sell, trend label.
    """
    url = "https://iboard-query.ssi.com.vn/v2/market/foreign-trading"
    try:
        r = requests.get(url, timeout=API_TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        net = float(data.get("foreignBuyValue", 0) or 0) \
            - float(data.get("foreignSellValue", 0) or 0)
        return {
            "net_buy":   net,
            "buy":       float(data.get("foreignBuyValue",  0) or 0),
            "sell":      float(data.get("foreignSellValue", 0) or 0),
            "trend":     "Mua ròng" if net > 0 else "Bán ròng",
            "fetch_ok":  True,
        }
    except Exception as exc:
        logger.debug("MarketForeignFlow: %s", exc)
        return {"net_buy": 0, "buy": 0, "sell": 0, "trend": "N/A", "fetch_ok": False}


# ─────────────────────────────────────────────────────────────
# MACRO INDICATORS
# ─────────────────────────────────────────────────────────────
def fetch_macro_indicators() -> dict:
    """
    Compile macro dashboard data.

    Returns
    -------
    dict with world_markets, breadth, foreign_flow, vni_info, stale_fields.
    stale_fields: list[str] of data names that could not be fetched —
    callers should warn the user when this list is non-empty so they know
    macro_score is degraded (e.g. defaulting to neutral for missing components).
    """
    world   = fetch_world_markets()
    breadth = fetch_market_breadth()
    ff      = fetch_market_foreign_flow()
    # ── Detect stale/missing data fields ─────────────────────────────────
    # Use fetch_ok sentinel to distinguish API failure from valid zero values
    # (e.g. non-trading day breadth of 0/0 is not a stale condition).
    stale_fields: list[str] = []
    critical_symbols = ["DXY (USD Index)", "VIX", "S&P 500"]
    for sym in critical_symbols:
        if not world.get(sym):
            stale_fields.append(sym)
    if not breadth.get("fetch_ok", True):
        stale_fields.append("market_breadth")
    if not ff.get("fetch_ok", True):
        stale_fields.append("foreign_flow")
    dxy_info   = world.get("DXY (USD Index)")
    dxy_trend  = "neutral"
    if dxy_info:
        if dxy_info["pct_5d"] > 0.5:
            dxy_trend = "strong_up"
        elif dxy_info["pct_5d"] > 0.1:
            dxy_trend = "up"
        elif dxy_info["pct_5d"] < -0.5:
            dxy_trend = "strong_down"
        elif dxy_info["pct_5d"] < -0.1:
            dxy_trend = "down"

    # Derive VIX risk signal
    vix_info  = world.get("VIX")
    vix_level = "normal"
    if vix_info and vix_info["current"]:
        if vix_info["current"] > 30:
            vix_level = "fear"
        elif vix_info["current"] > 20:
            vix_level = "elevated"

    # Advance/Decline ratio
    total   = breadth["advance"] + breadth["decline"]
    ad_ratio = (breadth["advance"] / total) if total > 0 else 0.5

    return {
        "world":        world,
        "breadth":      breadth,
        "ad_ratio":     round(ad_ratio, 3),
        "foreign_flow": ff,
        "dxy_trend":    dxy_trend,
        "vix_level":    vix_level,
        "stale_fields": stale_fields,
        "fetched_at":   datetime.now().isoformat(),
    }


def get_macro_score(macro: dict) -> tuple[float, str, list[str]]:
    """
    Convert macro dict to a 0-10 score, label, and list of stale fields.

    Returns
    -------
    (score, label, stale_fields)
      score       : float 0-10
      label       : 'bull' | 'neutral' | 'bear'
      stale_fields: list of data names that were missing/default —
                    pass these to the UI to show a warning.
    """
    score = 5.0  # neutral baseline
    stale_fields: list[str] = list(macro.get("stale_fields", []))

    # DXY: down = good for EM
    dxy_trend = macro.get("dxy_trend", "neutral")
    if dxy_trend == "strong_down":  score += 1.5
    elif dxy_trend == "down":       score += 0.75
    elif dxy_trend == "up":         score -= 0.75
    elif dxy_trend == "strong_up":  score -= 1.5

    # VIX: low = good
    vix_level = macro.get("vix_level", "normal")
    if vix_level == "fear":      score -= 2.0
    elif vix_level == "elevated": score -= 0.75

    # Foreign flow
    ff_net = macro.get("foreign_flow", {}).get("net_buy", 0)
    if ff_net > 1e10:    score += 1.5   # Strong foreign buy (>10B VND)
    elif ff_net > 0:     score += 0.5
    elif ff_net < -1e10: score -= 1.5
    elif ff_net < 0:     score -= 0.5

    # Market breadth
    ad_ratio = macro.get("ad_ratio", 0.5)
    if ad_ratio > 0.65:  score += 1.0
    elif ad_ratio < 0.35: score -= 1.0

    score = max(0.0, min(10.0, score))

    if score >= 7.5:    label = "bull"
    elif score >= 4.5:  label = "neutral"
    else:               label = "bear"

    return round(score, 2), label, stale_fields
