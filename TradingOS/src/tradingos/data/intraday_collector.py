"""Intraday Market Data Collector — open public feeds, no credentials required.

Sources (in priority order):
  TCBS     — tick-by-tick trades with aggressor side ("B" / "S")  [primary tick]
  SSI iBoard — L3 bid/ask snapshot + foreign flow               [primary orderbook]
  VNDirect   — L3 bid/ask snapshot, best1–3 Bid/Offer fields    [orderbook fallback]

Fallback chain:
  1. fetch_ssi_orderbook()      → if fails
  2. fetch_vndirect_orderbook() → if fails → ob = None (zero-fill)

Provides:
  fetch_tcbs_trades()        — raw trade list with aggressor
  fetch_ssi_orderbook()      — L3 order book snapshot (SSI iBoard)
  fetch_vndirect_orderbook() — L3 order book snapshot (VNDirect public API)
  compute_tfi()              — Trade Flow Imbalance [-1, +1]
  compute_obi()              — Order Book Imbalance [-1, +1]
  reconstruct_lob()          — infer L5–L10 depth from ticks + L3 snapshot
  fetch_intraday_features()  — master entry point; ALWAYS returns a dict (silent fallback)

All network calls use a 3-second timeout. Any exception returns zero values so
the profiler pipeline is never blocked by unavailable intraday data.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

from ..utils.logging import get_logger

log = get_logger("intraday_collector")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
_TIMEOUT = 3  # seconds per request

_TCBS_URL = (
    "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/{symbol}"
    "?page=0&size={size}&headIndex=-1"
)
_SSI_URL = "https://iboard.ssi.com.vn/dchart/api/v2/stock_prices/{symbol}"
_VNDIRECT_URL = (
    "https://api.vndirect.com.vn/v4/stocks"
    "?q=code:{symbol}"
    "&fields=code,lastPrice,totalVolume"
    ",best1Bid,best1BidVol,best1Offer,best1OfferVol"
    ",best2Bid,best2BidVol,best2Offer,best2OfferVol"
    ",best3Bid,best3BidVol,best3Offer,best3OfferVol"
    ",foreignBuyVolume,foreignSellVolume"
    "&size=1"
)

# ── TCBS tick fetcher ──────────────────────────────────────────────────────────

def fetch_tcbs_trades(symbol: str, size: int = 300) -> list[dict]:
    """
    Fetch intraday tick trades from TCBS public feed.

    Returns list of dicts with keys:
        price     : float — matched price
        volume    : int   — matched volume (shares)
        aggressor : str   — "B" (buy-driven) | "S" (sell-driven) | "U" (unknown)
        time      : str   — HH:MM:SS string
    """
    url = _TCBS_URL.format(symbol=symbol.upper(), size=size)
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    raw = resp.json().get("data", [])
    return [
        {
            "price":     float(t.get("p", 0) or 0),
            "volume":    int(t.get("v", 0) or 0),
            "aggressor": str(t.get("a", "U")).upper(),
            "time":      str(t.get("t", "")),
        }
        for t in raw
        if t.get("p") and t.get("v")
    ]


# ── SSI iBoard order book fetcher ─────────────────────────────────────────────

def fetch_ssi_orderbook(symbol: str) -> dict | None:
    """
    Fetch L3 bid/ask snapshot from SSI iBoard.

    Returns dict with:
        bids         : list of {"price": float, "vol": int}  (best 3 bids)
        asks         : list of {"price": float, "vol": int}  (best 3 asks)
        last_price   : float
        last_volume  : int
        foreign_buy  : int  (shares)
        foreign_sell : int  (shares)
    or None on failure.
    """
    url = _SSI_URL.format(symbol=symbol.upper())
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    raw: dict[str, Any] = data.get("data", data)  # iBoard sometimes nests under "data"

    def _bids() -> list[dict]:
        out = []
        for i in range(1, 4):
            p = raw.get(f"buyPrice{i}", 0) or 0
            v = raw.get(f"buyVol{i}", 0) or 0
            if p and v:
                out.append({"price": float(p), "vol": int(v)})
        return out

    def _asks() -> list[dict]:
        out = []
        for i in range(1, 4):
            p = raw.get(f"sellPrice{i}", 0) or 0
            v = raw.get(f"sellVol{i}", 0) or 0
            if p and v:
                out.append({"price": float(p), "vol": int(v)})
        return out

    return {
        "bids":        _bids(),
        "asks":        _asks(),
        "last_price":  float(raw.get("matchedPrice", 0) or 0),
        "last_volume": int(raw.get("matchedVolume", 0) or 0),
        "foreign_buy": int(raw.get("foreignBuyVolume", 0) or 0),
        "foreign_sell":int(raw.get("foreignSellVolume", 0) or 0),
    }


# ── VNDirect order book fetcher (fallback) ────────────────────────────────────

def fetch_vndirect_orderbook(symbol: str) -> dict | None:
    """
    Fetch L3 bid/ask snapshot from VNDirect public API.

    Used as a fallback when SSI iBoard is unavailable. Returns the same dict
    format as fetch_ssi_orderbook() so callers are source-agnostic.

    Returns dict with:
        bids         : list of {"price": float, "vol": int}  (best 3 bids)
        asks         : list of {"price": float, "vol": int}  (best 3 asks)
        last_price   : float
        last_volume  : int
        foreign_buy  : int  (shares)  — 0 if field absent
        foreign_sell : int  (shares)  — 0 if field absent
    or None if the symbol is not found or request fails.
    """
    url = _VNDIRECT_URL.format(symbol=symbol.upper())
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    data_list = resp.json().get("data", [])
    if not data_list:
        return None
    raw: dict[str, Any] = data_list[0]

    def _bids() -> list[dict]:
        out = []
        for i in range(1, 4):
            p = raw.get(f"best{i}Bid", 0) or 0
            v = raw.get(f"best{i}BidVol", 0) or 0
            if p and v:
                out.append({"price": float(p), "vol": int(v)})
        return out

    def _asks() -> list[dict]:
        out = []
        for i in range(1, 4):
            p = raw.get(f"best{i}Offer", 0) or 0
            v = raw.get(f"best{i}OfferVol", 0) or 0
            if p and v:
                out.append({"price": float(p), "vol": int(v)})
        return out

    return {
        "bids":        _bids(),
        "asks":        _asks(),
        "last_price":  float(raw.get("lastPrice", 0) or 0),
        "last_volume": int(raw.get("totalVolume", 0) or 0),
        "foreign_buy": int(raw.get("foreignBuyVolume", 0) or 0),
        "foreign_sell":int(raw.get("foreignSellVolume", 0) or 0),
    }


# ── Feature computations ───────────────────────────────────────────────────────

def compute_tfi(trades: list[dict]) -> float:
    """
    Trade Flow Imbalance: (buy_aggressor_vol - sell_aggressor_vol) / total_vol.

    Range: -1 (all sell-driven) to +1 (all buy-driven).
    Returns 0.0 if no trades or all unknown aggressor.
    """
    if not trades:
        return 0.0
    buy_vol  = sum(t["volume"] for t in trades if t["aggressor"] == "B")
    sell_vol = sum(t["volume"] for t in trades if t["aggressor"] == "S")
    total    = buy_vol + sell_vol
    if total == 0:
        return 0.0
    return round((buy_vol - sell_vol) / total, 4)


def compute_mcvd(trades: list[dict]) -> int:
    """
    Micro-Cumulative Volume Delta (M-CVD): signed net aggressor volume.

    Unlike the bar-level proxy in anti_manip (close > open heuristic),
    this uses TCBS tick-level aggressor field directly:
        M-CVD = Σ(buy_vol) - Σ(sell_vol)   over all intraday ticks

    Positive → net buy pressure; negative → net sell pressure.
    Returns 0 if no trades or all aggressor unknown.
    """
    if not trades:
        return 0
    cvd = 0
    for t in trades:
        agg = t.get("aggressor", "U")
        vol = t.get("volume", 0)
        if agg == "B":
            cvd += vol
        elif agg == "S":
            cvd -= vol
    return cvd


def compute_obi(ob: dict | None, use_reconstructed: bool = False) -> float:
    """
    Order Book Imbalance from L3 snapshot.

    OBI = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)
    Range: -1 (ask-heavy) to +1 (bid-heavy).
    Returns 0.0 if ob is None or empty.
    """
    if not ob:
        return 0.0
    levels_key = "bids_reconstructed" if use_reconstructed else "bids"
    bid_vol = sum(lvl["vol"] for lvl in ob.get(levels_key, ob.get("bids", [])))
    ask_vol = sum(lvl["vol"] for lvl in ob.get("asks_reconstructed" if use_reconstructed else "asks", []))
    total   = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return round((bid_vol - ask_vol) / total, 4)


def reconstruct_lob(
    trades: list[dict],
    ob_snapshot: dict | None,
    half_life_minutes: float = 10.0,
) -> dict:
    """
    LOB Reconstruction — infer L5–L10 depth by fusing TCBS tick history
    with SSI L3 snapshot.

    Algorithm:
    - L3 snapshot levels are authoritative (kept as-is).
    - For each tick: buy-aggressor at price P implies resting ask liquidity at P;
      sell-aggressor at price P implies resting bid liquidity at P.
    - Synthetic levels are weighted by recency: w = exp(-age_minutes / half_life).
    - Resulting extended book is merged: L3 tops + synthetic extensions.

    Returns ob_snapshot dict extended with:
        bids_reconstructed : list of {"price", "vol"} — merged L3 + inferred bid levels
        asks_reconstructed : list of {"price", "vol"} — merged L3 + inferred ask levels
        reconstruction_depth : int — number of synthetic levels added
    """
    if not ob_snapshot:
        return ob_snapshot or {}

    result = dict(ob_snapshot)
    if not trades:
        result["bids_reconstructed"] = ob_snapshot.get("bids", [])
        result["asks_reconstructed"] = ob_snapshot.get("asks", [])
        result["reconstruction_depth"] = 0
        return result

    now_ts = datetime.now(timezone.utc)

    # Accumulate synthetic depth buckets: {price: weighted_vol}
    syn_bids: dict[float, float] = defaultdict(float)
    syn_asks: dict[float, float] = defaultdict(float)

    for t in trades:
        price  = t["price"]
        vol    = t["volume"]
        agg    = t["aggressor"]
        t_str  = t.get("time", "")

        # Parse time to estimate age (assume today)
        age_minutes = 0.0
        if t_str:
            try:
                parts = t_str.split(":")
                hh, mm, ss = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
                trade_dt = now_ts.replace(hour=hh, minute=mm, second=ss, microsecond=0)
                age_minutes = max(0.0, (now_ts - trade_dt).total_seconds() / 60.0)
            except (ValueError, IndexError):
                age_minutes = 30.0  # default to mid-session if unparseable

        weight = math.exp(-age_minutes / half_life_minutes)

        if agg == "B":
            # Buy-aggressor lifts resting asks → implies ask supply at this price
            syn_asks[round(price, 2)] += vol * weight
        elif agg == "S":
            # Sell-aggressor hits resting bids → implies bid demand at this price
            syn_bids[round(price, 2)] += vol * weight

    # Build L3 authoritative levels
    l3_bids = {lvl["price"]: lvl["vol"] for lvl in ob_snapshot.get("bids", [])}
    l3_asks = {lvl["price"]: lvl["vol"] for lvl in ob_snapshot.get("asks", [])}

    # Merge: L3 wins at prices where both exist
    merged_bids = {**{p: int(v) for p, v in syn_bids.items()}, **l3_bids}
    merged_asks = {**{p: int(v) for p, v in syn_asks.items()}, **l3_asks}

    # Sort: bids descending, asks ascending
    sorted_bids = sorted(merged_bids.items(), key=lambda x: -x[0])
    sorted_asks = sorted(merged_asks.items(), key=lambda x:  x[0])

    synthetic_count = len(set(merged_bids) - set(l3_bids)) + len(set(merged_asks) - set(l3_asks))

    result["bids_reconstructed"] = [{"price": p, "vol": v} for p, v in sorted_bids[:10]]
    result["asks_reconstructed"] = [{"price": p, "vol": v} for p, v in sorted_asks[:10]]
    result["reconstruction_depth"] = synthetic_count
    return result


# ── Master entry point ─────────────────────────────────────────────────────────

def fetch_intraday_features(symbol: str) -> dict:
    """
    Fetch and compute all intraday features for a ticker.

    Always returns a dict — never raises. On any failure, returns zeros.

    Returns:
        tfi               : float  Trade Flow Imbalance [-1, +1]
        obi_l3            : float  Order Book Imbalance from L3 snapshot
        obi_reconstructed : float  OBI from reconstructed LOB (L5–L10)
        foreign_buy       : int    Foreign buy volume (shares)
        foreign_sell      : int    Foreign sell volume (shares)
        foreign_net       : int    foreign_buy - foreign_sell
        reconstruction_depth : int  number of synthetic LOB levels added
    """
    _zero = {
        "tfi": 0.0, "obi_l3": 0.0, "obi_reconstructed": 0.0,
        "foreign_buy": 0, "foreign_sell": 0, "foreign_net": 0,
        "reconstruction_depth": 0,
        "mcvd": 0,
    }
    try:
        trades = fetch_tcbs_trades(symbol)
    except Exception as e:
        log.debug(f"[{symbol}] TCBS fetch failed: {e}")
        trades = []

    try:
        ob = fetch_ssi_orderbook(symbol)
    except Exception as e:
        log.debug(f"[{symbol}] SSI orderbook fetch failed: {e}")
        ob = None

    # ── Fallback: VNDirect (same dict format, no credentials needed) ──────
    if ob is None:
        try:
            ob = fetch_vndirect_orderbook(symbol)
            if ob:
                log.debug(f"[{symbol}] VNDirect orderbook fallback used")
        except Exception as e:
            log.debug(f"[{symbol}] VNDirect orderbook fallback failed: {e}")
            ob = None

    try:
        tfi    = compute_tfi(trades)
        obi_l3 = compute_obi(ob, use_reconstructed=False)

        ob_recon   = reconstruct_lob(trades, ob)
        obi_recon  = compute_obi(ob_recon, use_reconstructed=True) if ob_recon else 0.0
        rec_depth  = ob_recon.get("reconstruction_depth", 0) if ob_recon else 0

        foreign_buy  = ob.get("foreign_buy",  0) if ob else 0
        foreign_sell = ob.get("foreign_sell", 0) if ob else 0

        mcvd = compute_mcvd(trades)

        return {
            "tfi":                tfi,
            "obi_l3":             obi_l3,
            "obi_reconstructed":  obi_recon,
            "foreign_buy":        foreign_buy,
            "foreign_sell":       foreign_sell,
            "foreign_net":        foreign_buy - foreign_sell,
            "reconstruction_depth": rec_depth,
            "mcvd":               mcvd,
        }
    except Exception as e:
        log.debug(f"[{symbol}] Intraday feature computation failed: {e}")
        return _zero
