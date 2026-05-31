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
        # fallback: Yahoo Finance — ^VNINDEX is the correct symbol for VN-Index
        data = _yahoo_price("^VNINDEX", "2y")
        if data and data["prices"]:
            df = pd.DataFrame({"Close": data["prices"]})
    return df


# ─────────────────────────────────────────────────────────────
# KBS IIS API — single endpoint for breadth + foreign flow
# Replaces deprecated SSI iboard-query v2 (gone 2025) and TCBS analysis
# API (deprecated Dec 2024). KBS endpoint covers HOSE/HNX/UPCOM ~370 stocks.
# ─────────────────────────────────────────────────────────────
_KBS_FF_URL  = "https://kbbuddywts.kbsec.com.vn/iis-server/investment/rtranking/foreignTotal"
_KBS_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
# Simple TTL cache: (_data, _timestamp)
_kbs_snapshot_cache: tuple[list, datetime | None] = ([], None)
_KBS_CACHE_TTL = timedelta(minutes=5)


def _fetch_kbs_market_snapshot() -> list:
    """
    Fetch real-time market snapshot from KBS IIS API.
    Returns list of dicts: SB=ticker, EX=exchange,
    RE=reference_price, CP=current_price,
    FB=foreign_buy_vol, FS=foreign_sell_vol (in shares).
    Result is cached for 5 minutes to avoid duplicate calls.
    """
    global _kbs_snapshot_cache
    data, ts = _kbs_snapshot_cache
    if ts and (datetime.now() - ts) < _KBS_CACHE_TTL and data:
        return data
    try:
        r = requests.get(
            _KBS_FF_URL,
            params={"top": 500},
            headers=_KBS_HEADERS,
            timeout=API_TIMEOUT,
        )
        r.raise_for_status()
        fresh = r.json()
        if isinstance(fresh, list) and fresh:
            _kbs_snapshot_cache = (fresh, datetime.now())
            return fresh
    except Exception as exc:
        logger.debug("KBS snapshot: %s", exc)
    return []


def fetch_market_breadth() -> dict:
    """
    Compute advance/decline from KBS IIS real-time snapshot.
    Counts stocks with CP > RE (advance), CP < RE (decline), CP == RE (unchanged).
    """
    data = _fetch_kbs_market_snapshot()
    if not data:
        return {"advance": 0, "decline": 0, "unchanged": 0, "fetch_ok": False}
    advance = decline = unchanged = 0
    for item in data:
        cp = item.get("CP", 0) or 0
        re = item.get("RE", 0) or 0
        if cp > re:
            advance += 1
        elif cp < re:
            decline += 1
        else:
            unchanged += 1
    return {
        "advance":   advance,
        "decline":   decline,
        "unchanged": unchanged,
        "fetch_ok":  True,
    }


# ─────────────────────────────────────────────────────────────
# FOREIGN FLOW
# ─────────────────────────────────────────────────────────────
def _empty_foreign_flow() -> dict:
    return {
        "net_buy_value": 0,
        "buy_value": 0,
        "sell_value": 0,
        "net_20d": 0,
        "trend_20d": "neutral",
        "session_net_proxy": 0,
        "session_trend": "neutral",
        "history_sessions": 0,
        "is_20d_proxy": False,
        "basis": "not_available",
    }


def _foreign_flow_from_snapshot_item(item: dict | None) -> dict:
    if not item:
        return _empty_foreign_flow()

    cp  = float(item.get("CP", 0) or 0)
    fb  = float(item.get("FB", 0) or 0)
    fs  = float(item.get("FS", 0) or 0)
    net = (fb - fs) * cp
    buy = fb * cp
    sel = fs * cp
    if net > 5e10:
        session_trend = "accumulate"
    elif net < -5e10:
        session_trend = "distribute"
    else:
        session_trend = "neutral"
    return {
        "net_buy_value": net,
        "buy_value":     buy,
        "sell_value":    sel,
        # Intraday snapshot has no verified 20-session continuity.
        # Keep the 20d fields neutral/unavailable and expose the session signal
        # separately so callers cannot mistake one snapshot for real 20d history.
        "net_20d":   0,
        "trend_20d": "neutral",
        "session_net_proxy": net,
        "session_trend": session_trend,
        "history_sessions": 1,
        "is_20d_proxy": True,
        "basis": "KBS snapshot | session net only",
    }


def fetch_foreign_flow_tickers(symbols: list[str]) -> dict[str, dict]:
    """Fetch foreign-flow data for many symbols using a single KBS snapshot."""
    if not symbols:
        return {}

    data = _fetch_kbs_market_snapshot()
    lookup = {
        (item.get("SB", "") or "").upper(): item
        for item in data
    }
    return {
        symbol: _foreign_flow_from_snapshot_item(lookup.get(symbol.upper()))
        for symbol in symbols
    }


def fetch_foreign_flow_ticker(symbol: str) -> dict:
    """
    Fetch foreign buy/sell for a specific ticker from KBS IIS snapshot.

    Returns
    -------
    dict with keys: net_buy_value, buy_value, sell_value, net_20d, trend_20d,
    session_net_proxy, session_trend, history_sessions, is_20d_proxy, basis.
    All monetary values in VND (shares × price).
    Verified 20-session history is not available from the intraday snapshot;
    callers should use net_buy_value/session_net_proxy for today's session signal.
    """
    data = _fetch_kbs_market_snapshot()
    sym_upper = symbol.upper()
    for item in data:
        if (item.get("SB", "") or "").upper() == sym_upper:
            return _foreign_flow_from_snapshot_item(item)
    # Ticker not found in snapshot (may be halted or not in top 500)
    return _empty_foreign_flow()


def fetch_market_foreign_flow(days: int = 20) -> dict:
    """
    Compute aggregate market foreign flow from KBS IIS snapshot.
    Sums (FB-FS)*CP across all stocks to get net VND flow for the session.
    """
    data = _fetch_kbs_market_snapshot()
    if not data:
        return {"net_buy": 0, "buy": 0, "sell": 0, "trend": "N/A", "fetch_ok": False}
    net_buy = buy = sell = 0.0
    for item in data:
        cp = float(item.get("CP", 0) or 0)
        fb = float(item.get("FB", 0) or 0)
        fs = float(item.get("FS", 0) or 0)
        net_buy += (fb - fs) * cp
        buy     += fb * cp
        sell    += fs * cp
    return {
        "net_buy":  net_buy,
        "buy":      buy,
        "sell":     sell,
        "trend":    "Mua r\u00f2ng" if net_buy > 0 else "B\u00e1n r\u00f2ng",
        "fetch_ok": True,
    }


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

    # ── S&P 500 — global risk-on/risk-off signal ──────────────────────────
    # S&P 500 and VN-Index show moderate positive correlation (~0.4-0.6).
    # A sustained S&P rally signals global risk appetite and drives EM inflows.
    # A S&P crash (>-2% in 5d) triggers foreign outflows from VN within 1-3 days.
    sp500 = macro.get("world", {}).get("S&P 500")
    if sp500:
        sp5_pct = sp500.get("pct_5d", 0) or 0
        if sp5_pct > 2.0:    score += 0.50   # global risk-on
        elif sp5_pct > 0.5:  score += 0.25
        elif sp5_pct < -2.0: score -= 0.75   # risk-off: faster VN reaction
        elif sp5_pct < -0.5: score -= 0.25

    # ── CSI 300 — China's market, major driver for VN sectors ────────────
    # CSI 300 has the HIGHEST regional correlation with VN-Index (~0.55-0.70).
    # Key channels: commodity pricing (steel/HPG, coal, chemicals), FDI from
    # Chinese firms, and VN export demand from Chinese buyers.
    csi300 = macro.get("world", {}).get("CSI 300 (CN)")
    if csi300:
        csi_pct = csi300.get("pct_5d", 0) or 0
        if csi_pct > 2.0:    score += 0.50   # China rally → positive for VN
        elif csi_pct > 0.5:  score += 0.25
        elif csi_pct < -2.0: score -= 0.50   # China selloff → VN sells
        elif csi_pct < -0.5: score -= 0.25

    score = max(0.0, min(10.0, score))

    if score >= 7.5:    label = "bull"
    elif score >= 4.5:  label = "neutral"
    else:               label = "bear"

    return round(score, 2), label, stale_fields
