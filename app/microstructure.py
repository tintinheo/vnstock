"""
microstructure.py — Market microstructure primitives for Vietnam stock market.

Implements:
  • Micro-price  — volume-weighted bid/ask estimator (superior to mid-price)
  • Multi-level OFI — Order Flow Imbalance across top-3 book levels
  • T+2.5 window detector — True when local time is in 12:45–13:15 window
  • fetch_orderbook  — stub pending SSI WebSocket integration
  • compute_vwap_intraday — cumulative VWAP from SSI 5-min bars

Notes on stubs
──────────────
fetch_orderbook() always returns None because SSI's public REST API does not
expose a Level-2 orderbook endpoint.  The SSI FastConnect WebSocket protocol
delivers OrderBookSnapshot events — wire them here once that connection is live.
"""

import logging
import time as _time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import requests

from qp_config import (
    VWAP_INTRADAY_RESOLUTION,
    T25_WINDOW_START,
    T25_WINDOW_END,
)

_log = logging.getLogger("microstructure")

_SSI_API_BASE = "https://iboard-api.ssi.com.vn"
_SSI_HDR = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "vi",
    "Referer":         "https://iboard.ssi.com.vn/",
    "Origin":          "https://iboard.ssi.com.vn",
    "device-id":       "0116B7B1-976D-437A-AA2C-C72FC3E6F956",
}

# ── Micro-price ───────────────────────────────────────────────────────────────

def compute_micro_price(
    bid_px: float,
    ask_px: float,
    bid_sz: float,
    ask_sz: float,
) -> tuple[float, float]:
    """
    Compute mid-price and micro-price from top-of-book quote.

    Mid-price:   simple average of bid and ask.
    Micro-price: volume-weighted — gives more weight toward the side with
                 higher queue depth, reflecting which side has more conviction.

    Formula: P_micro = (bid_sz * ask_px + ask_sz * bid_px) / (bid_sz + ask_sz)

    Args:
        bid_px: Best bid price (thousands-VND).
        ask_px: Best ask price (thousands-VND).
        bid_sz: Queue size at best bid (shares).
        ask_sz: Queue size at best ask (shares).

    Returns:
        (mid_price, micro_price) — both in thousands-VND.
    """
    mid_price = (bid_px + ask_px) / 2.0

    total = bid_sz + ask_sz
    if total <= 0:
        return mid_price, mid_price

    micro_price = (bid_sz * ask_px + ask_sz * bid_px) / total
    return round(mid_price, 3), round(micro_price, 3)


# ── Multi-level Order Flow Imbalance ─────────────────────────────────────────

def compute_ofi_multilevel(
    book: list[dict],
    prev: list[dict],
    levels: int = 3,
) -> float:
    """
    Compute Order Flow Imbalance across multiple book levels.

    Single-level OFI (as in proposal) is easily manipulated via fake orders
    at the top of the queue.  Using 3 levels materially reduces spoofing noise.

    Each level dict must have keys: bid_px, bid_sz, ask_px, ask_sz.
    Levels should be ordered best-to-worse (level[0] = top of book).

    OFI interpretation:
        > 0  →  net buy pressure  (buyers more aggressive)
        < 0  →  net sell pressure (sellers more aggressive)
        = 0  →  balanced

    Args:
        book:   Current orderbook snapshot (list of level dicts).
        prev:   Previous orderbook snapshot.
        levels: Number of levels to aggregate (default 3).

    Returns:
        Float OFI score.
    """
    ofi = 0.0
    n = min(len(book), len(prev), levels)

    for i in range(n):
        cur  = book[i]
        prv  = prev[i]

        # Bid side pressure
        if cur["bid_px"] > prv["bid_px"]:
            bid_pressure = cur["bid_sz"]
        elif cur["bid_px"] == prv["bid_px"]:
            bid_pressure = cur["bid_sz"] - prv["bid_sz"]
        else:
            bid_pressure = -prv["bid_sz"]

        # Ask side pressure
        if cur["ask_px"] < prv["ask_px"]:
            ask_pressure = cur["ask_sz"]
        elif cur["ask_px"] == prv["ask_px"]:
            ask_pressure = cur["ask_sz"] - prv["ask_sz"]
        else:
            ask_pressure = -prv["ask_sz"]

        ofi += bid_pressure - ask_pressure

    return float(ofi)


# ── T+2.5 window ─────────────────────────────────────────────────────────────

def t25_window_active() -> bool:
    """
    Return True if the current local time is within the T+2.5 singularity
    window (default 12:45 – 13:15 ICT, configurable in qp_config.py).

    The T+0 asset release at 13:00 creates a predictable surge in volatility
    and liquidity on HOSE — valid signals in this window carry higher weight.
    """
    now = datetime.now()
    start_min = T25_WINDOW_START[0] * 60 + T25_WINDOW_START[1]
    end_min   = T25_WINDOW_END[0]   * 60 + T25_WINDOW_END[1]
    cur_min   = now.hour * 60 + now.minute
    return start_min <= cur_min <= end_min


# ── Orderbook stub ────────────────────────────────────────────────────────────

def fetch_orderbook(ticker: str) -> Optional[list[dict]]:
    """
    Fetch Level-2 orderbook snapshot for ticker.

    STUB — returns None until SSI WebSocket integration is wired.

    To implement: subscribe to SSI FastConnect WebSocket and handle
    'OrderBookSnapshot' events. Each event delivers 3 bid/ask levels.
    Wire the latest snapshot into this function's return value as:
        [
            {"bid_px": .., "bid_sz": .., "ask_px": .., "ask_sz": ..},  # level 1
            {"bid_px": .., "bid_sz": .., "ask_px": .., "ask_sz": ..},  # level 2
            {"bid_px": .., "bid_sz": .., "ask_px": .., "ask_sz": ..},  # level 3
        ]
    """
    # TODO: wire SSI FastConnect WebSocket OrderBookSnapshot here
    return None


# ── Intraday VWAP ─────────────────────────────────────────────────────────────

def _fetch_intraday_ssi(symbol: str, resolution: str = "5") -> pd.DataFrame:
    """
    Fetch today's intraday OHLCV bars from SSI iBoard API.
    Returns DataFrame with columns: open, high, low, close, volume; indexed by datetime.
    """
    to_ts   = int(_time.time())
    from_ts = to_ts - 86400  # 24h back (covers current session)
    url     = f"{_SSI_API_BASE}/statistics/charts/history"
    params  = {
        "resolution": resolution,
        "symbol":     symbol.upper(),
        "from":       from_ts,
        "to":         to_ts,
    }
    try:
        r = requests.get(url, headers=_SSI_HDR, params=params, timeout=8)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        _log.warning("intraday SSI %s %smin: %s", symbol, resolution, e)
        return pd.DataFrame()

    if not raw or raw.get("code") != "SUCCESS":
        return pd.DataFrame()

    d = raw.get("data") or {}
    t_list = d.get("t", [])
    c_list = d.get("c", [])
    if not t_list or not c_list:
        return pd.DataFrame()

    n = len(t_list)
    df = pd.DataFrame({
        "time":   pd.to_datetime(t_list, unit="s", utc=True)
                    .tz_convert("Asia/Ho_Chi_Minh")
                    .tz_localize(None),
        "open":   [float(x) for x in d.get("o", c_list)[:n]],
        "high":   [float(x) for x in d.get("h", c_list)[:n]],
        "low":    [float(x) for x in d.get("l", c_list)[:n]],
        "close":  [float(x) for x in c_list[:n]],
        "volume": [float(x) for x in d.get("v", [0] * n)[:n]],
    })
    df = df.set_index("time").sort_index()
    # Keep today's session only (09:00 – 14:45)
    today = datetime.now().strftime("%Y-%m-%d")
    df = df[df.index.strftime("%Y-%m-%d") == today]
    return df


def compute_vwap_intraday(
    symbol: str,
    df_5min: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Compute cumulative intraday VWAP from 5-min SSI bars.

    VWAP resets at session open (09:00) each day.
    The cumulative formula ensures VWAP reflects a weighted average of all
    trades since open — this is what institutions use as an execution benchmark.

    Args:
        symbol:  Ticker symbol (used to fetch data if df_5min is None).
        df_5min: Optional pre-fetched 5-min DataFrame (columns: high, low, close, volume).

    Returns:
        dict with:
            vwap_last       : float  — current VWAP level (thousands-VND)
            t25_position    : str    — "ABOVE" | "BELOW" | "AT" relative to VWAP at 13:00
            vwap_slope      : float  — slope of last 6 bars (VWAP change / bar, +/-)
            t25_window_now  : bool   — True if called within T+2.5 window
            bars_available  : int    — number of intraday bars fetched
    """
    empty = {
        "vwap_last":      None,
        "t25_position":   "AT",
        "vwap_slope":     0.0,
        "t25_window_now": t25_window_active(),
        "bars_available": 0,
    }

    try:
        if df_5min is None or df_5min.empty:
            df_5min = _fetch_intraday_ssi(symbol, VWAP_INTRADAY_RESOLUTION)
        if df_5min is None or len(df_5min) < 3:
            return empty

        df = df_5min.copy()
        # Typical price and cumulative VWAP
        df["tp"]      = (df["high"] + df["low"] + df["close"]) / 3.0
        df["pv"]      = df["tp"] * df["volume"].clip(lower=1)
        df["cum_pv"]  = df["pv"].cumsum()
        df["cum_vol"] = df["volume"].clip(lower=1).cumsum()
        df["vwap"]    = df["cum_pv"] / df["cum_vol"]

        vwap_last = float(df["vwap"].iloc[-1])
        price_now = float(df["close"].iloc[-1])

        # T+2.5 position: use bar closest to 13:00
        t25_pos = "AT"
        t25_bar = df.between_time("12:55", "13:05")
        if not t25_bar.empty:
            vwap_at_t25 = float(t25_bar["vwap"].iloc[-1])
            price_at_t25 = float(t25_bar["close"].iloc[-1])
            dev = (price_at_t25 - vwap_at_t25) / vwap_at_t25 * 100 if vwap_at_t25 > 0 else 0.0
            if dev > 0.5:
                t25_pos = "ABOVE"
            elif dev < -0.5:
                t25_pos = "BELOW"
        else:
            # Fallback: use current price vs current VWAP
            dev = (price_now - vwap_last) / vwap_last * 100 if vwap_last > 0 else 0.0
            if dev > 0.5:
                t25_pos = "ABOVE"
            elif dev < -0.5:
                t25_pos = "BELOW"

        # VWAP slope: linear regression over last 6 bars
        vwap_series = df["vwap"].dropna()
        if len(vwap_series) >= 6:
            y = vwap_series.iloc[-6:].values
            x = np.arange(len(y))
            slope = float(np.polyfit(x, y, 1)[0])
        else:
            slope = 0.0

        return {
            "vwap_last":      round(vwap_last, 0),
            "t25_position":   t25_pos,
            "vwap_slope":     round(slope, 3),
            "t25_window_now": t25_window_active(),
            "bars_available": len(df),
        }

    except Exception as e:
        _log.warning("compute_vwap_intraday %s: %s", symbol, e)
        return empty


# ── HoSE session timing windows ───────────────────────────────────────────────

# Empirical intraday volatility profile — HoSE 2023-2025 (from academic proposals)
_SESSION_WINDOWS = [
    # (start_h, start_m, end_h, end_m, label, vol_mult, f0_note)
    ( 9, 15,  9, 30, "ATO aftermath",        2.1, "TRÁNH — Biến động ATO cực cao, giá chưa ổn định"),
    ( 9, 30, 10,  0, "Mở cửa tổ chức",       1.6, "THẬN TRỌNG — NĐT tổ chức và nước ngoài vào lệnh"),
    (10,  0, 11,  0, "Giao dịch bình thường", 1.0, "TỐT NHẤT — Thanh khoản tốt, ít nhiễu, vào lệnh lý tưởng"),
    (11,  0, 11, 30, "Trước nghỉ trưa",       0.8, "TRUNG BÌNH — Khối lượng giảm dần, tránh vào mới"),
    (13,  0, 13, 30, "Mở lại buổi chiều",     1.3, "THẬN TRỌNG — Áp lực T+2.5 bắt đầu, vol bùng phát"),
    (13, 30, 14, 30, "Áp lực T+2.5",          1.4, "THẬN TRỌNG — Cung T+2.5 đỉnh điểm, tốt cho thoát lệnh"),
    (14, 30, 15,  0, "Đua lệnh ATC",          1.9, "TRÁNH — ATC rush + T+2.5 exit cuối, slippage cao nhất"),
]


def build_session_timing_windows() -> list[dict]:
    """
    Return the HoSE intraday session timing table with current-window flag.

    Each dict has:
        start_hm    : str  e.g. "09:15"
        end_hm      : str  e.g. "09:30"
        label       : str  window name
        vol_mult    : float  relative volatility vs 10:00-11:00 baseline
        f0_note     : str  Vietnamese recommendation
        is_current  : bool  True for the window matching datetime.now()
        is_good     : bool  True for the two optimal entry windows
    """
    now     = datetime.now()
    cur_min = now.hour * 60 + now.minute
    windows = []
    for sh, sm, eh, em, label, vol_mult, note in _SESSION_WINDOWS:
        s_min = sh * 60 + sm
        e_min = eh * 60 + em
        windows.append({
            "start_hm":  f"{sh:02d}:{sm:02d}",
            "end_hm":    f"{eh:02d}:{em:02d}",
            "label":     label,
            "vol_mult":  vol_mult,
            "f0_note":   note,
            "is_current": bool(s_min <= cur_min < e_min),
            "is_good":   bool(vol_mult <= 1.0),   # only 10:00-11:00 baseline window
        })
    return windows


# ── Realized & Garman-Klass volatility ───────────────────────────────────────

def compute_garman_klass(
    df: pd.DataFrame,
    window: int = 20,
    trading_days: int = 252,
) -> dict:
    """
    Garman-Klass volatility estimator — works on daily OHLC, always available offline.

    Annualized formula:
        sigma_GK = sqrt(252/N * sum[ 0.5*(ln H/L)^2 - (2*ln2-1)*(ln C/O)^2 ])

    GK is 7x more efficient than close-to-close vol for the same number of observations
    and accounts for intraday high/low range — critical on HoSE with 7% daily bands.

    Args:
        df           : Daily OHLCV DataFrame (Open, High, Low, Close columns required).
        window       : Rolling window in sessions (default 20 = 1 month).
        trading_days : Annual sessions for annualisation (252 for HoSE).

    Returns:
        dict:
            gk_annualized_pct : float  annualized vol as % (e.g. 35.2 = 35.2%)
            gk_daily_pct      : float  daily vol as % (gk_annualized / sqrt(252))
            gk_window         : int    actual window used
            gk_upper_1sd      : float  price + 1SD daily range (absolute, thousands-VND)
            gk_lower_1sd      : float  price - 1SD daily range
    """
    empty = {
        "gk_annualized_pct": None,
        "gk_daily_pct":      None,
        "gk_window":         window,
        "gk_upper_1sd":      None,
        "gk_lower_1sd":      None,
    }
    try:
        if df is None or len(df) < window + 1:
            return empty

        sub = df.tail(window).copy()
        O = pd.to_numeric(sub["Open"],  errors="coerce").replace(0, np.nan)
        H = pd.to_numeric(sub["High"],  errors="coerce").replace(0, np.nan)
        L = pd.to_numeric(sub["Low"],   errors="coerce").replace(0, np.nan)
        C = pd.to_numeric(sub["Close"], errors="coerce").replace(0, np.nan)

        # Garman-Klass per-bar variance
        log_hl = np.log(H / L)
        log_co = np.log(C / O)
        gk_bar = 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2
        gk_bar = gk_bar.dropna()
        n = len(gk_bar)
        if n < 5:
            return empty

        gk_ann_var   = (trading_days / n) * float(gk_bar.sum())
        gk_ann_sigma = float(np.sqrt(max(0.0, gk_ann_var)))
        gk_daily_pct = gk_ann_sigma / np.sqrt(trading_days) * 100.0

        price_last = float(C.iloc[-1])
        return {
            "gk_annualized_pct": round(gk_ann_sigma * 100.0, 2),
            "gk_daily_pct":      round(gk_daily_pct, 3),
            "gk_window":         n,
            "gk_upper_1sd":      round(price_last * (1 + gk_daily_pct / 100.0), 1),
            "gk_lower_1sd":      round(price_last * (1 - gk_daily_pct / 100.0), 1),
        }
    except Exception as e:
        _log.debug("compute_garman_klass: %s", e)
        return empty


def compute_realized_volatility(
    symbol: str,
    df_daily: "pd.DataFrame" = None,
    window_gk: int = 20,
) -> dict:
    """
    Two-tier volatility:  Garman-Klass (offline, always)  +  Intraday RV (online, optional).

    Always returns GK vol from daily df.  When intraday 5-min bars are available
    (market hours or just after close), also computes Realized Volatility from
    5-min log-returns:  RV = sqrt( sum(r_i^2) )  where r_i = ln(c_i / c_{i-1}).

    Args:
        symbol   : Ticker for SSI 5-min fetch.
        df_daily : Daily OHLCV DataFrame (passed in to avoid extra fetch).
        window_gk: GK rolling window (default 20 sessions).

    Returns:
        dict with keys:
            gk_annualized_pct, gk_daily_pct, gk_upper_1sd, gk_lower_1sd,
            rv_intraday_pct    : float | None  today's RV from 5-min bars
            rv_bars            : int   number of 5-min bars used
            rv_upper_target    : float | None  price + 1SD intraday estimate
            rv_lower_target    : float | None  price - 1SD intraday estimate
            rv_source          : str   "intraday_5min" | "unavailable"
            rv_status_note     : str   human-readable note
    """
    result = {
        "gk_annualized_pct": None,
        "gk_daily_pct":      None,
        "gk_upper_1sd":      None,
        "gk_lower_1sd":      None,
        "rv_intraday_pct":   None,
        "rv_bars":           0,
        "rv_upper_target":   None,
        "rv_lower_target":   None,
        "rv_source":         "unavailable",
        "rv_status_note":    "Chưa có dữ liệu nội phiên",
    }
    # ── Tier 1: Garman-Klass from daily df (always) ───────────────────────────
    if df_daily is not None and not df_daily.empty:
        gk = compute_garman_klass(df_daily, window=window_gk)
        result.update(gk)

    # ── Tier 2: Intraday RV from 5-min bars (on demand) ──────────────────────
    try:
        df5 = _fetch_intraday_ssi(symbol, VWAP_INTRADAY_RESOLUTION)
        if df5 is None or len(df5) < 5:
            result["rv_status_note"] = "Thị trường đóng cửa hoặc chưa có dữ liệu nội phiên"
            return result

        log_rets = np.log(
            df5["close"].astype(float) / df5["close"].astype(float).shift(1)
        ).dropna()

        if len(log_rets) < 4:
            result["rv_status_note"] = f"Chỉ có {len(df5)} nến 5 phút — chưa đủ"
            return result

        rv = float(np.sqrt(np.sum(log_rets ** 2))) * 100.0  # as %
        price_now = float(df5["close"].iloc[-1])

        result["rv_intraday_pct"]  = round(rv, 3)
        result["rv_bars"]          = len(log_rets)
        result["rv_upper_target"]  = round(price_now * (1.0 + rv / 100.0), 1)
        result["rv_lower_target"]  = round(price_now * (1.0 - rv / 100.0), 1)
        result["rv_source"]        = "intraday_5min"
        result["rv_status_note"]   = (
            f"RV từ {len(log_rets)} nến 5 phút hôm nay "
            f"({df5.index[0].strftime('%H:%M')}–{df5.index[-1].strftime('%H:%M')})"
        )
    except Exception as e:
        _log.debug("compute_realized_volatility intraday %s: %s", symbol, e)
        result["rv_status_note"] = "Không lấy được dữ liệu nội phiên"

    return result
