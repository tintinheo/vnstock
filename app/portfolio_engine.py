#!/usr/bin/env python3
"""
portfolio_engine.py  —  Portfolio Hub: CSV parsing, T+2.5 settlement, P&L
═══════════════════════════════════════════════════════════════════════════
Handles SSI broker export CSV (Saturn/iboard format) with fuzzy column
matching, VN-holiday-aware trading calendar, and T+2 KRX settlement logic.

Usage (standalone smoke test):
    python portfolio_engine.py path/to/holdings.csv
"""

import os
import re
import io
from datetime import date, timedelta, datetime
from typing import Optional

import numpy as np
import pandas as pd

try:
    from nl_explainer import generate_nl_explanation as _gen_nl
except Exception:
    def _gen_nl(r, rec):  # type: ignore
        return ""

# ─── VN Public Holidays (fixed + approximate recurring) ──────────────────────
_VN_HOLIDAYS_2025_2026 = {
    date(2025, 1, 1),   # Tết Dương lịch
    date(2025, 1, 27),  date(2025, 1, 28),  date(2025, 1, 29),
    date(2025, 1, 30),  date(2025, 1, 31),  # Tết Nguyên Đán 2025
    date(2025, 4, 30),  date(2025, 5, 1),   # 30/4 + 1/5
    date(2025, 9, 1),   date(2025, 9, 2),   # Giỗ Tổ Hùng Vương + Quốc khánh
    date(2026, 1, 1),   # Tết Dương lịch
    date(2026, 1, 26),  date(2026, 1, 27),  date(2026, 1, 28),
    date(2026, 1, 29),  date(2026, 1, 30),  # Tết Nguyên Đán 2026
    date(2026, 4, 7),   # Giỗ Tổ Hùng Vương
    date(2026, 4, 30),  date(2026, 5, 1),
    date(2026, 9, 2),
}


# ─── Column aliases: SSI, DNSE, manual entry ─────────────────────────────────
_COL_ALIASES = {
    "ticker": [
        "mã ck", "mã", "ticker", "symbol", "ck", "stock", "co phieu",
        "mã cổ phiếu", "stock code",
    ],
    "qty": [
        "sl đang có", "sl hiện có", "số lượng", "quantity", "qty", "sl",
        "klcp", "kl", "số lượng hiện tại", "sl khớp", "volume",
    ],
    "avg_cost": [
        "giá vốn bq", "giá vốn", "giá vv (vnđ)", "giá vv", "giá mua tb",
        "average cost", "avg cost", "avg_cost", "giá tb", "vốn bình quân",
        "gia von", "giá bình quân",
    ],
    "trade_date": [
        "ngày gd", "ngày mua", "trade date", "date", "ngày", "gd date",
    ],
    "sector": [
        "ngành", "sector", "ngành/sector", "nganh",
    ],
}


def _fuzzy_match(col_name: str, aliases: list[str]) -> bool:
    """Case-insensitive partial match of a column name against a list of aliases."""
    # Normalize newlines (SSI XLSX uses \n inside column headers)
    c = col_name.strip().lower().replace("\n", " ").replace("  ", " ")
    return any(a in c or c in a for a in aliases)


def detect_portfolio_csv_format(df: pd.DataFrame) -> dict:
    """
    Sniff the column mapping from an uploaded DataFrame.
    Returns {'ticker': col, 'qty': col, 'avg_cost': col, 'trade_date': col|None, 'sector': col|None}
    Raises ValueError if ticker or qty cannot be detected.
    """
    mapping = {}
    for field, aliases in _COL_ALIASES.items():
        for col in df.columns:
            if _fuzzy_match(col, aliases):
                mapping[field] = col
                break
    missing = [f for f in ("ticker", "qty", "avg_cost") if f not in mapping]
    if missing:
        raise ValueError(
            f"Không tìm thấy cột: {missing}. "
            f"Cột hiện có: {list(df.columns)}"
        )
    return mapping


def _detect_xlsx(uploaded_file) -> bool:
    """Return True if the file appears to be an Excel XLSX/XLS file."""
    name = ""
    if isinstance(uploaded_file, (str, os.PathLike)):
        name = str(uploaded_file)
    elif hasattr(uploaded_file, "name"):
        name = uploaded_file.name or ""
    return name.lower().endswith((".xlsx", ".xls"))


def parse_portfolio_csv(uploaded_file) -> pd.DataFrame:
    """
    Parse an SSI/DNSE portfolio CSV or XLSX (file path, bytes, or file-like object).
    Returns a clean DataFrame with columns:
        ticker, qty, avg_cost, trade_date (date | None), sector (str | '')
    Filters out rows with qty <= 0 or avg_cost <= 0.

    SSI iBoard XLSX format:
        Row 0: blank / metadata
        Row 1: account info
        Row 2: column headers  ← header=2
        Row 3+: data
    """
    is_xlsx = _detect_xlsx(uploaded_file)

    if is_xlsx:
        # ── XLSX path ────────────────────────────────────────────────────────
        # SSI iBoard exports have 2 header/metadata rows before the real column row
        try:
            df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=2, thousands=",")
        except Exception:
            # Fallback: try first sheet with no skip
            df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=0)
        # Seek back so Streamlit can re-read if needed
        if hasattr(uploaded_file, "seek"):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
    else:
        # ── CSV path ─────────────────────────────────────────────────────────
        if isinstance(uploaded_file, (str, os.PathLike)):
            raw = open(uploaded_file, "rb").read()
        elif hasattr(uploaded_file, "read"):
            raw = uploaded_file.read()
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
        else:
            raw = uploaded_file  # bytes

        # Try UTF-8 then cp1258 (Vietnamese Windows encoding)
        text = ""
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, AttributeError):
                text = raw if isinstance(raw, str) else ""
                break

        try:
            df_raw = pd.read_csv(io.StringIO(text), thousands=",")
        except Exception:
            df_raw = pd.read_csv(io.StringIO(text), thousands=",", sep=";")

    # Rename purely-unnamed columns (common in SSI/DNSE export padding)
    df_raw.columns = [
        c if not str(c).startswith("Unnamed") else f"_col{i}"
        for i, c in enumerate(df_raw.columns)
    ]

    mapping = detect_portfolio_csv_format(df_raw)
    out = pd.DataFrame()
    out["ticker"]     = df_raw[mapping["ticker"]].astype(str).str.strip().str.upper()
    out["qty"]        = pd.to_numeric(df_raw[mapping["qty"]].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    out["avg_cost"]   = pd.to_numeric(df_raw[mapping["avg_cost"]].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    if "trade_date" in mapping:
        out["trade_date"] = pd.to_datetime(df_raw[mapping["trade_date"]], dayfirst=True, errors="coerce").dt.date
    else:
        out["trade_date"] = None

    if "sector" in mapping:
        out["sector"] = df_raw[mapping["sector"]].astype(str).str.strip()
    else:
        out["sector"] = ""

    # Clean
    out = out[out["qty"] > 0]
    out = out[out["avg_cost"] > 0]
    out = out[out["ticker"].str.len() >= 2]
    out = out.reset_index(drop=True)
    return out


# ─── VN Trading Calendar ─────────────────────────────────────────────────────

def is_vn_trading_day(d: date) -> bool:
    """Return True if d is a Vietnam Stock Exchange trading day."""
    if d.weekday() >= 5:   # Saturday=5, Sunday=6
        return False
    if d in _VN_HOLIDAYS_2025_2026:
        return False
    return True


def get_vn_trading_days(start: date, end: date) -> list[date]:
    """Return a sorted list of trading days in [start, end]."""
    days = []
    cur = start
    while cur <= end:
        if is_vn_trading_day(cur):
            days.append(cur)
        cur += timedelta(days=1)
    return days


def calculate_t2_settlement(trade_date: date) -> date:
    """
    Calculate the T+2 settlement date per KRX rules (2 VN trading days forward).
    For KRX the new standard is T+2 (net cash available at end of T+2).
    """
    count = 0
    d = trade_date
    while count < 2:
        d += timedelta(days=1)
        if is_vn_trading_day(d):
            count += 1
    return d


def classify_settlement_status(
    holdings_df: pd.DataFrame,
    today: Optional[date] = None,
) -> pd.DataFrame:
    """
    Add 'settlement_date' and 'status' columns to a holdings DataFrame.
    status values:
        'settled'    — shares fully available
        't2_pending' — trade date = today, settles in 2 trading days
        't1_pending' — settles tomorrow
    """
    if today is None:
        today = date.today()
    df = holdings_df.copy()

    def _status(row):
        td = row.get("trade_date")
        if pd.isna(td) or td is None:
            return date.fromisoformat(str(today - timedelta(days=5))), "settled"
        if isinstance(td, str):
            td = date.fromisoformat(td)
        settle = calculate_t2_settlement(td)
        if today >= settle:
            return settle, "settled"
        remaining = len(get_vn_trading_days(today, settle)) - 1
        if remaining <= 1:
            return settle, "t1_pending"
        return settle, "t2_pending"

    results = df.apply(_status, axis=1)
    df["settlement_date"] = [r[0] for r in results]
    df["status"] = [r[1] for r in results]
    return df

# ─── VN-Swing Alpha Improvement: Dynamic Fractional Kelly ───────────────────────────

def calculate_fractional_kelly(
    win_prob: float,
    gain_loss_ratio: float,
    market_volatility: float,
) -> float:
    """
    Volatility-scaled Fractional Kelly — VN-Swing Alpha Improvement proposal.
    Adjusts f* based on current market stress (Catastrophic Risk filter).

    Args:
        win_prob: Historical win probability (0–1).
        gain_loss_ratio: avg_win / avg_loss ratio (b in Kelly formula).
        market_volatility: ATR/price daily ratio.  >0.03 = high-stress session.

    Returns:
        f_kelly: Recommended position size as a fraction (0–1).
                 Quarter-Kelly when market_volatility > 0.03 (crash/recovery).
                 Half-Kelly otherwise (normal conditions).
    """
    b = float(gain_loss_ratio)
    p = max(0.01, min(0.99, float(win_prob)))
    q = 1.0 - p
    f_star = (b * p - q) / b
    if market_volatility > 0.03:          # High stress — Quarter-Kelly
        return max(0.0, f_star * 0.25)
    return max(0.0, f_star * 0.5)         # Normal — Half-Kelly


# ─── VN-Swing Alpha T+2.5 Exit Manager ────────────────────────────────────────────

class T25ExitManager:
    """
    VN-Swing Alpha T+2.5 Exit Manager.
    Manages adaptive exit rules for the T+2.5 swing trading strategy.
    All exit messages include 'recommend by VN-Swing Alpha'.

    Usage:
        mgr = T25ExitManager(entry_price=22_000, atr=500, bt_win_rate=0.65)
        action = mgr.daily_update(current_price=23_100, day_in_trade=2,
                                  regime="BULL_TREND", macd_hist_slope=-1.0,
                                  vol_ratio=0.75)
    """

    def __init__(self, entry_price: float, atr: float, bt_win_rate: float = 0.60,
                 kl_ratio: float = 1.0, beta: float = 1.0):
        self.entry    = float(entry_price)
        self.atr      = float(atr) if atr else self.entry * 0.02
        # F10: Dynamic SL multiplier — wider for illiquid/high-beta, tighter otherwise
        #   base 1.5×; +0.4× per unit of illiquidity below 1.0; +0.2× per unit of beta above 1.5
        _sl_mult = 1.5 + max(0.0, (1.0 - float(kl_ratio)) * 0.4) + max(0.0, (float(beta) - 1.5) * 0.2)
        _sl_mult = max(1.0, min(2.2, _sl_mult))         # clamp [1.0, 2.2]
        self.sl       = self.entry - _sl_mult * self.atr # Hard stop-loss
        self.tp1      = self.entry + 2.0 * self.atr      # TP1 — target 60% exit
        self.tp2      = self.entry + 3.5 * self.atr      # TP2 — remaining 40%
        self.trail    = self.sl                           # Trailing stop (updated daily)
        self.win_rate = max(0.40, min(0.80, bt_win_rate))
        # Dynamic Fractional Kelly — Quarter/Half based on market_volatility (ATR/price)
        avg_win    = self.atr * 2.0
        avg_loss   = self.atr * _sl_mult
        glr        = avg_win / max(avg_loss, 1e-9)       # gain/loss ratio
        market_vol = self.atr / max(self.entry, 1e-9)    # daily vol proxy
        kelly_f    = calculate_fractional_kelly(self.win_rate, glr, market_vol)
        self.recommended_size_pct = round(max(5.0, min(25.0, kelly_f * 100)), 1)
        self.kelly_mode = "Quarter-Kelly" if market_vol > 0.03 else "Half-Kelly"

    def daily_update(
        self,
        current_price:    float,
        day_in_trade:     int,
        regime:           str   = "SIDEWAYS",
        macd_hist_slope:  float = 0.0,   # positive = rising, negative = falling
        vol_ratio:        float = 1.0,   # current vol / vol_ma20
    ) -> dict:
        """
        Call once per session close with the day's closing price.
        Returns {"action": str, "reason": str, "trail": float, "tp1": float, "tp2": float}
        Actions: HOLD | SELL_ALL | SELL_60PCT | SELL_50PCT
        """
        p = float(current_price)

        # ── Hard Stop-Loss (non-negotiable) ───────────────────────────────────
        if p <= self.sl:
            return self._out("SELL_ALL", f"Stop-loss hit: {self.sl:,.0f} — recommend by VN-Swing Alpha")

        # ── T+1: Monitor momentum, manage trailing stop ──────────────────────────
        if day_in_trade == 1:
            if p >= self.tp1 * 0.95:
                self.trail = self.entry              # Move stop to breakeven
            if macd_hist_slope < 0 and vol_ratio < 0.8:
                return self._out("SELL_50PCT", "Momentum fading on T+1 — recommend by VN-Swing Alpha")

        # ── T+2: Settlement day — core exit logic ─────────────────────────────
        if day_in_trade == 2:
            if p >= self.tp1:
                self.trail = self.entry + 0.5 * (p - self.entry)
                pct = (p / self.entry - 1) * 100
                return self._out("SELL_60PCT", f"TP1 (±{pct:.1f}%) reached on T+2 — recommend by VN-Swing Alpha")
            if p > self.entry * 1.01 and regime != "BEAR_TREND":
                return self._out("HOLD", "Profitable on T+2, extending to T+3 — recommend by VN-Swing Alpha")
            if p < self.entry * 0.99:
                return self._out("SELL_ALL", "Below entry on T+2 — exit before T+3 gap risk (VN-Swing Alpha)")

        # ── T+3+: Extended hold or mandatory exit ─────────────────────────────
        if day_in_trade >= 3:
            if p >= self.tp2:
                pct = (p / self.entry - 1) * 100
                return self._out("SELL_ALL", f"TP2 reached (+{pct:.1f}%) — recommend by VN-Swing Alpha")
        if day_in_trade >= 4:
            return self._out("SELL_ALL", "T+2.5 window expired (≥T+4) — mandatory exit per VN-Swing Alpha")

        # ── Update trailing stop ──────────────────────────────────────────────
        new_trail = p - 1.5 * self.atr
        if new_trail > self.trail:
            self.trail = new_trail
        if p <= self.trail and day_in_trade >= 2:
            return self._out("SELL_ALL", f"Trailing stop: {self.trail:,.0f} — recommend by VN-Swing Alpha")

        return self._out("HOLD", f"Within parameters (day {day_in_trade}) — recommend by VN-Swing Alpha")

    def _out(self, action: str, reason: str) -> dict:
        return {
            "action":          action,
            "reason":          reason,
            "trail":           round(self.trail, 0),
            "tp1":             round(self.tp1,   0),
            "tp2":             round(self.tp2,   0),
            "sl":              round(self.sl,    0),
            "rec_size_pct":    self.recommended_size_pct,
            "kelly_mode":      self.kelly_mode,
        }

    @staticmethod
    def entry_timing_note() -> str:
        """VN-Swing Alpha entry timing recommendation."""
        return (
            "⏰ VN-Swing Alpha không cần:  • Giờ vào lệnh TỐT NHẤT: 10:00–11:00 sáng  "
            "• Giờ thay thế: 13:30–14:00  • TRÁNH: 09:15–09:25 (ATO), 14:30–15:00 (ATC)"
        )


# ─── T+ Recommendation Engine ────────────────────────────────────────────────


# Action labels and their Grade codes
_T_REC_GRADES = {
    "STRONG_BUY": "A",
    "BUY":        "B",
    "WATCH":      "C",
    "SKIP":       "D",
    "AVOID":      "E",
}

_T_REC_COLORS = {
    "STRONG_BUY": "#22c55e",
    "BUY":        "#4ade80",
    "WATCH":      "#f59e0b",
    "SKIP":       "#94a3b8",
    "AVOID":      "#ef4444",
}


def generate_t_plus_recommendation(r: dict, fc: dict = None, cf_result: dict = None) -> dict:
    """
    Synthesize all VN-Swing Alpha signals into a single T+ entry recommendation.

    Scoring (0–100):
      T+2.5 signal   (40 pts)  T25_BUY=40, T25_WATCH=25, T25_NEUTRAL=10, T25_AVOID=0
      Momentum       (30 pts)  bull_pct ≥65→30, ≥55→20, ≥50→10, <50→0; +5 if confirmed
      Market regime  (20 pts)  BULL_TREND=20, SIDEWAYS=12, UNKNOWN=8, BEAR_TREND=3
      Structure      (10 pts)  VSA_ACCUM+5, VSA_NO_SUPPLY+3, bullish_candle+3,
                               RSI_div_bullish+4, at_floor+2 (capped at 10)

    Risk deductions: at_ceiling−20, unconfirmed−5, bearish_div−5,
                     VSA_DISTRIB−5, beta>1.5−5, illiquid−5.

    Overrides: T25_AVOID or at_ceiling → forced AVOID/Grade E.

    Args:
        r:  Full analyse_ticker result dict.
        fc: Optional multi_horizon_forecast dict (informational only, no grade impact).

    Returns dict with keys:
        action, grade, confidence_score,
        entry_zone_low, entry_zone_high,
        sl_price, tp1_price, tp2_price, rr_ratio,
        position_size_pct, kelly_mode,
        entry_timing, risk_flags, supporting_signals,
        max_risk_pct, expected_return_pct,
        lstm_info,   # str or None — LSTM/Ridge pred (informational)
    """
    # ── Extract fields with safe defaults ────────────────────────────────────
    t25_sig    = r.get("t25_signal",   "T25_NEUTRAL")
    bull_pct   = float(r.get("bull_pct",   50.0) or 50.0)
    regime     = r.get("regime",       "UNKNOWN")
    confirmed  = bool(r.get("signal_confirmed", False))
    vsa_state  = r.get("vsa_state",    "NEUTRAL")
    candle_p   = r.get("candle_pattern","NEUTRAL")
    rsi_div    = r.get("rsi_divergence","NONE")
    at_ceiling = bool(r.get("at_ceiling", False))
    at_floor   = bool(r.get("at_floor",   False))
    beta         = float(r.get("rolling_beta_5d", 1.0) or 1.0)
    kl_ratio     = float(r.get("kl_ratio", 1.0)  or 1.0)
    price        = float(r.get("price",    0.0)   or 0.0)
    sma20        = float(r.get("sma20",    0.0)   or 0.0)
    sma200       = float(r.get("sma200",   0.0)   or 0.0)
    sma200_slope = float(r.get("sma200_slope", 0.0) or 0.0)
    atr          = float(r.get("atr",      0.0)   or 0.0)
    sl           = r.get("sl")
    tp1          = r.get("tp1")
    tp2          = r.get("tp2")
    win_rate     = float(
        r.get("bt5_win_rate") or r.get("bt_win_rate") or 0.55
    )
    bt5_win_rate  = float(r.get("bt5_win_rate")  or 0.0)
    bt5_avg_ret   = float(r.get("bt5_avg_return") or -99.0)

    # ── CF enrichment: extract Candlestick Forecast signals ──────────────────
    _garch_sigma    = None
    _garch_high_vol = False
    _hmm_transition = None
    _hmm_bull_next  = 0.0
    _hmm_bear_next  = 0.0
    _day1_pct       = None
    _forecast_ci_low  = None
    _forecast_ci_high = None
    _sl_garch  = None
    _tp1_garch = None
    _tp2_garch = None
    if cf_result and not cf_result.get("error"):
        _garch_cf = cf_result.get("garch")
        _hmm_cf   = cf_result.get("hmm")
        _ens_cf   = cf_result.get("ensemble")
        if _garch_cf and hasattr(_garch_cf, "sigma_t1"):
            _garch_sigma    = float(_garch_cf.sigma_t1)       # already fraction
            _garch_high_vol = bool(_garch_cf.high_vol_regime)
            if price > 0 and _garch_sigma > 0:
                _tp_mult   = 2.5 if (_hmm_cf and getattr(_hmm_cf, "regime_label", "") == "Bull") else 2.0
                _sl_garch  = round(price * (1.0 - 1.645 * _garch_sigma), 0)
                _tp1_garch = round(price * (1.0 + _tp_mult * _garch_sigma), 0)
                _tp2_garch = round(price * (1.0 + (_tp_mult + 1.0) * _garch_sigma), 0)
        if _hmm_cf and hasattr(_hmm_cf, "next_state_probs") and len(_hmm_cf.next_state_probs) == 3:
            _hmm_bear_next  = float(_hmm_cf.next_state_probs[0])
            _hmm_bull_next  = float(_hmm_cf.next_state_probs[2])
            _curr_lbl       = getattr(_hmm_cf, "regime_label", "?")
            _ns_idx         = int(np.argmax(_hmm_cf.next_state_probs))
            _ns_lbl         = ("Bear", "Range", "Bull")[_ns_idx]
            _ns_pct         = round(_hmm_cf.next_state_probs[_ns_idx] * 100)
            _hmm_transition = f"{_curr_lbl}\u2192{_ns_lbl} ({_ns_pct}%)"
        if _ens_cf and hasattr(_ens_cf, "pct_changes") and _ens_cf.pct_changes:
            _day1_pct   = float(_ens_cf.pct_changes[0])
            _candles_cf = cf_result.get("candles", [])
            if _candles_cf:
                _c0 = _candles_cf[0]
                if hasattr(_c0, "lower_ci"):
                    _forecast_ci_low  = round(float(_c0.lower_ci), 0)
                    _forecast_ci_high = round(float(_c0.upper_ci), 0)

    # ── Backtest rescue check (for T25_AVOID only) ───────────────────────────
    # When T25 scores AVOID but long-term statistics are positive AND price is
    # above a rising SMA200 in a SIDEWAYS regime, allow scoring to continue
    # but cap the final output at WATCH (score ≤50).  BEAR_TREND is excluded.
    _bt_rescue = (
        t25_sig == "T25_AVOID"
        and regime != "BEAR_TREND"
        and sma200 > 0
        and price > sma200
        and sma200_slope > 1.0
        and bt5_win_rate >= 55.0
        and bt5_avg_ret  >  0.0
    )
    # Effective T25 signal used for score_a — rescue promotes to NEUTRAL
    _t25_sig_eff = "T25_NEUTRAL" if _bt_rescue else t25_sig

    # ── Forced override checks ────────────────────────────────────────────────
    if (t25_sig == "T25_AVOID" and not _bt_rescue) or at_ceiling:
        _avoid_sigs: list = []
        for _s in (r.get("t25_confirms") or [])[:5]:
            _avoid_sigs.append(_s)
        if r.get("rsi_divergence") == "BULLISH" and "RSI_div\u2191" not in _avoid_sigs:
            _avoid_sigs.insert(0, "RSI_div\u2191")
        risk_flags = []
        if t25_sig == "T25_AVOID":
            risk_flags.append("T+2.5 score: AVOID zone")
        if at_ceiling:
            risk_flags.append("Giá chạm TRẦN — rủi ro cao nhất")
        _avoid_rec = {
            "action": "AVOID", "grade": "E", "confidence_score": 0,
            "entry_zone_low": None, "entry_zone_high": None,
            "sl_price":  _sl_garch  if _sl_garch  is not None else (round(float(sl),  0) if sl  else None),
            "tp1_price": _tp1_garch if _tp1_garch is not None else (round(float(tp1), 0) if tp1 else None),
            "tp2_price": _tp2_garch if _tp2_garch is not None else (round(float(tp2), 0) if tp2 else None),
            "rr_ratio": None,
            "position_size_pct": 0.0, "kelly_mode": "N/A",
            "entry_timing": "AVOID_TODAY",
            "risk_flags": risk_flags,
            "supporting_signals": _avoid_sigs,
            "max_risk_pct": None, "expected_return_pct": None,
            "lstm_info": None,
            "sl_garch":          _sl_garch,
            "tp1_garch":         _tp1_garch,
            "tp2_garch":         _tp2_garch,
            "hmm_transition":    _hmm_transition,
            "day1_forecast_pct": _day1_pct,
            "forecast_ci_low":   _forecast_ci_low,
            "forecast_ci_high":  _forecast_ci_high,
        }
        _avoid_rec["nl_explanation"] = _gen_nl(r, _avoid_rec)
        return _avoid_rec

    # ── Component scoring ─────────────────────────────────────────────────────
    # A: T+2.5 signal (0-40)  — use effective signal (rescue promotes AVOID→NEUTRAL)
    _t25_pts = {"T25_BUY": 40, "T25_WATCH": 25, "T25_NEUTRAL": 10, "T25_AVOID": 0}
    score_a  = float(_t25_pts.get(_t25_sig_eff, 10))
    if _bt_rescue:
        risk_flags = [f"BT-rescue: WR={bt5_win_rate:.0f}% ret={bt5_avg_ret:+.1f}% (WATCH max)"]

    # B: Momentum (0-30)
    if bull_pct >= 65:   score_b = 30.0
    elif bull_pct >= 55: score_b = 20.0
    elif bull_pct >= 50: score_b = 10.0
    else:                score_b =  0.0
    if confirmed:        score_b = min(30.0, score_b + 5.0)

    # C: Regime (0-20)
    _reg_pts = {"BULL_TREND": 20, "SIDEWAYS": 12, "UNKNOWN": 8, "BEAR_TREND": 3}
    score_c  = float(_reg_pts.get(regime, 8))

    # D: Structure confirms (0-10)
    score_d = 0.0
    supporting_signals = []
    if vsa_state == "ACCUM":
        score_d += 5; supporting_signals.append("VSA:ACCUM")
    elif vsa_state == "NO_SUPPLY":
        score_d += 3; supporting_signals.append("VSA:NO_SUPPLY")
    if candle_p in ("HAMMER", "BULL_ENGULFING", "MORNING_STAR"):
        score_d += 3; supporting_signals.append(f"Candle:{candle_p}")
    if rsi_div == "BULLISH":
        score_d += 4; supporting_signals.append("RSI Divergence↑")
    if at_floor:
        score_d += 2; supporting_signals.append("Giá chạm SÀN")
    score_d = min(10.0, score_d)

    # F2: HH+HL structure bonus
    if r.get("is_hh") and r.get("is_hl"):
        score_d = min(10.0, score_d + 5.0)
        supporting_signals.append("HH+HL structure")
    elif r.get("is_hh") or r.get("is_hl"):
        supporting_signals.append(r.get("structure_label", ""))

    # F3: RS Rating bonus
    rs_rating = int(r.get("rs_rating") or 50)
    if rs_rating >= 70:
        score_b = min(35.0, score_b + 5.0)
        supporting_signals.append(f"RS Rating {rs_rating} — outperforming VNI")

    # Append other confirms from t25_confirms (first 4 not already listed)
    for _c in (r.get("t25_confirms") or [])[:6]:
        if _c not in supporting_signals and len(supporting_signals) < 6:
            supporting_signals.append(_c)

    raw_score = score_a + score_b + score_c + score_d

    # ── Risk deductions ───────────────────────────────────────────────────────
    # Preserve BT-rescue flag if set; otherwise start fresh
    if not _bt_rescue:
        risk_flags = []
    if not confirmed:
        raw_score -= 5; risk_flags.append("Tín hiệu chưa được xác nhận 2/3 phiên")
    if rsi_div == "BEARISH":
        raw_score -= 5; risk_flags.append("RSI Divergence âm (bearish)")
    if vsa_state == "DISTRIB":
        raw_score -= 5; risk_flags.append("VSA:DISTRIB — phân phối tổ chức")
    if beta > 1.5:
        raw_score -= 5; risk_flags.append(f"Beta 5D cao: {beta:.2f}β — biến động mạnh")
    if kl_ratio < 0.5:
        raw_score -= 5; risk_flags.append(f"Thanh khoản thấp: KL={kl_ratio:.1f}× MA20")
    # F4: Gap deduction
    gap_type = r.get("gap_type", "NO_GAP")
    if gap_type == "GAP_DOWN":
        raw_score -= 5; risk_flags.append(f"Gap DOWN sáng nay: {r.get('gap_pct', 0):.1f}%")
    # F8: Far above VWAP deduction
    vwap_dev = r.get("vwap_dev", "AT")
    pvp      = float(r.get("price_vs_vwap_pct") or 0.0)
    if vwap_dev == "ABOVE" and pvp > 3.0:
        raw_score -= 3; risk_flags.append(f"Giá {pvp:.1f}% trên VWAP — xa ngưỡng tốt")
    # F9: Dividend risk
    ex_div_days = r.get("ex_div_days")
    if ex_div_days is not None and ex_div_days <= 5:
        raw_score -= 10; risk_flags.append(f"Ex-dividend trong {ex_div_days} phiên — rủi ro giảm giá")

    # ── CF scoring adjustments (from Candlestick Forecast enrichment) ─────────
    if _hmm_bull_next > 0.60:
        raw_score += 5
        supporting_signals.append(f"HMM\u2192{_hmm_transition or 'Bull next'}")
    elif _hmm_bear_next > 0.60:
        raw_score -= 5
        risk_flags.append(f"HMM Bear next: {_hmm_transition or '?'}")
    if _day1_pct is not None:
        if _day1_pct > 1.0:
            raw_score += 5
            supporting_signals.append(f"CF ngày 1: +{_day1_pct:.1f}%")
        elif _day1_pct < -1.0:
            raw_score -= 5
            risk_flags.append(f"CF ngày 1: {_day1_pct:.1f}%")
    if _garch_high_vol:
        raw_score -= 5
        risk_flags.append("GARCH: vol regime cao (persistence>0.97)")

    confidence_score = int(max(0, min(100, raw_score)))
    if _bt_rescue:
        confidence_score = min(50, confidence_score)   # rescue path: never above WATCH

    # ── Map to action tier ────────────────────────────────────────────────────
    if confidence_score >= 80:
        action = "STRONG_BUY"
    elif confidence_score >= 65:
        action = "BUY"
    elif confidence_score >= 50:
        action = "WATCH"
    elif confidence_score >= 35:
        action = "SKIP"
    else:
        action = "AVOID"

    grade = _T_REC_GRADES[action]

    # ── Entry zone ────────────────────────────────────────────────────────────
    if price and sma20 and abs(price - sma20) / sma20 <= 0.03:
        entry_low  = round(sma20 * 0.990, 0)
        entry_high = round(sma20 * 1.010, 0)
    elif price:
        entry_low  = round(price * 0.990, 0)
        entry_high = round(price * 1.005, 0)
    else:
        entry_low = entry_high = None

    # ── Entry timing ──────────────────────────────────────────────────────────
    if action in ("STRONG_BUY", "BUY"):
        entry_timing = "10:00–11:30 (tốt nhất) · 13:30–14:00 (thay thế)"
    elif action == "WATCH":
        entry_timing = "13:30–14:00 (chờ xác nhận thêm)"
    else:
        entry_timing = "AVOID_TODAY"

    # ── GARCH-adaptive SL/TP (use CF levels when available) ─────────────────
    _sl_use  = _sl_garch  if _sl_garch  is not None else (round(float(sl),  0) if sl  else None)
    _tp1_use = _tp1_garch if _tp1_garch is not None else (round(float(tp1), 0) if tp1 else None)
    _tp2_use = _tp2_garch if _tp2_garch is not None else (round(float(tp2), 0) if tp2 else None)

    # ── Risk/reward metrics ───────────────────────────────────────────────────
    entry_ref = price or 0
    max_risk_pct = (
        round((entry_ref - float(_sl_use)) / entry_ref * 100, 2)
        if _sl_use and entry_ref > 0 else None
    )
    expected_return_pct = (
        round((float(_tp1_use) - entry_ref) / entry_ref * 100, 2)
        if _tp1_use and entry_ref > 0 else None
    )
    rr_ratio = (
        round((float(_tp1_use) - entry_ref) / (entry_ref - float(_sl_use)), 2)
        if _tp1_use and _sl_use and entry_ref > float(_sl_use) > 0 else None
    )

    # ── Kelly position sizing (GARCH σ×price as ATR when CF available) ────────
    _atr_use = (
        (_garch_sigma * entry_ref)
        if (_garch_sigma and entry_ref > 0)
        else (atr if atr > 0 else entry_ref * 0.02)
    )
    try:
        _mgr = T25ExitManager(
            entry_ref or 1, _atr_use,
            min(0.80, max(0.40, win_rate)),
            kl_ratio=kl_ratio, beta=beta,
        )
        position_size_pct = _mgr.recommended_size_pct
        kelly_mode        = _mgr.kelly_mode
    except Exception:
        position_size_pct = 10.0
        kelly_mode        = "Half-Kelly"
    if _garch_high_vol and position_size_pct > 0:
        position_size_pct = round(position_size_pct * 0.5, 1)

    # ── LSTM info (informational, no grade impact) ────────────────────────────
    lstm_info = None
    if fc is not None and fc.get("lstm_pred_pct") is not None:
        _src = "LSTM" if fc.get("lstm_source") == "lstm" else "Ridge ML"
        lstm_info = f"{_src}: {fc['lstm_pred_pct']:+.2f}% (5-ngày, chỉ tham khảo)"

    _rec = {
        "action":               action,
        "grade":                grade,
        "confidence_score":     confidence_score,
        "entry_zone_low":       entry_low,
        "entry_zone_high":      entry_high,
        "sl_price":             _sl_use,
        "tp1_price":            _tp1_use,
        "tp2_price":            _tp2_use,
        "rr_ratio":             rr_ratio,
        "position_size_pct":    position_size_pct,
        "kelly_mode":           kelly_mode,
        "entry_timing":         entry_timing,
        "risk_flags":           risk_flags,
        "supporting_signals":   supporting_signals,
        "max_risk_pct":         max_risk_pct,
        "expected_return_pct":  expected_return_pct,
        "lstm_info":            lstm_info,
        "sl_garch":             _sl_garch,
        "tp1_garch":            _tp1_garch,
        "tp2_garch":            _tp2_garch,
        "hmm_transition":       _hmm_transition,
        "day1_forecast_pct":    _day1_pct,
        "forecast_ci_low":      _forecast_ci_low,
        "forecast_ci_high":     _forecast_ci_high,
    }
    _rec["nl_explanation"] = _gen_nl(r, _rec)
    return _rec


# ─── F15: Swing Strength Index (SSI) ─────────────────────────────────────────
_SSI_GRADE = [
    (90, "S", "#f59e0b"),
    (75, "A", "#22c55e"),
    (60, "B", "#3b82f6"),
    (45, "C", "#94a3b8"),
    (0,  "D", "#ef4444"),
]


def compute_ssi_score(r: dict) -> dict:
    """
    Swing Strength Index — proprietary composite 1–100 score for T+2–5 trading.

    Components:
        w1=25%  t25_score         (0–100)
        w2=25%  rs_rating         (1–99, scaled 0–100)
        w3=20%  bt5_win_rate      mapped: ≥70%→100, ≥55%→60, ≥45%→20, else 0
        w4=15%  structure bonus   HH+HL→100, HH or HL only→53, else 0
        w5=15%  volume impulse    kl_ratio: ≥2→100, ≥1.5→67, ≥1→33, else 0

    Grade: S(90–100) / A(75–89) / B(60–74) / C(45–59) / D(<45)
    """
    t25    = float(r.get("t25_score")    or 0) / 100  # 0–1
    rs     = float(r.get("rs_rating")    or 50) / 99  # 0–1
    bt5_wr = float(r.get("bt5_win_rate") or r.get("bt_win_rate") or 0.50)
    if bt5_wr >= 0.70:
        w3 = 1.0
    elif bt5_wr >= 0.55:
        w3 = 0.60
    elif bt5_wr >= 0.45:
        w3 = 0.20
    else:
        w3 = 0.0
    is_hh = bool(r.get("is_hh"))
    is_hl = bool(r.get("is_hl"))
    if is_hh and is_hl:
        w4 = 1.0
    elif is_hh or is_hl:
        w4 = 0.53
    else:
        w4 = 0.0
    kl = float(r.get("kl_ratio") or 1.0)
    if kl >= 2.0:
        w5 = 1.0
    elif kl >= 1.5:
        w5 = 0.67
    elif kl >= 1.0:
        w5 = 0.33
    else:
        w5 = 0.0
    raw = 0.25 * t25 + 0.25 * rs + 0.20 * w3 + 0.15 * w4 + 0.15 * w5
    ssi = int(max(1, min(100, round(raw * 100))))
    grade = "D"
    color = "#ef4444"
    for threshold, g, c in _SSI_GRADE:
        if ssi >= threshold:
            grade = g
            color = c
            break
    return {
        "ssi":       ssi,
        "ssi_grade": grade,
        "ssi_color": color,
        "ssi_factors": {
            "t25": round(t25, 3),
            "rs":  round(rs,  3),
            "bt5": round(w3,  3),
            "struct": round(w4, 3),
            "vol":    round(w5, 3),
        },
    }


# ─── Performance Attribution ─────────────────────────────────────────────────

# Sector map (VN stock exchange) — comprehensive coverage of HOSE/HNX tickers
_SECTOR_MAP = {
    # ── Ngân hàng ─────────────────────────────────────────────────────────
    "VCB": "Ngân hàng", "BID": "Ngân hàng", "CTG": "Ngân hàng",
    "MBB": "Ngân hàng", "TCB": "Ngân hàng", "ACB": "Ngân hàng",
    "VPB": "Ngân hàng", "HDB": "Ngân hàng", "LPB": "Ngân hàng",
    "SHB": "Ngân hàng", "STB": "Ngân hàng", "TPB": "Ngân hàng",
    "OCB": "Ngân hàng", "MSB": "Ngân hàng", "VIB": "Ngân hàng",
    "EIB": "Ngân hàng", "SSB": "Ngân hàng", "NAB": "Ngân hàng",
    "BAB": "Ngân hàng", "KLB": "Ngân hàng",
    # ── Chứng khoán ────────────────────────────────────────────────────────
    "SSI": "Chứng khoán", "VCI": "Chứng khoán", "VND": "Chứng khoán",
    "HCM": "Chứng khoán", "MBS": "Chứng khoán", "BSI": "Chứng khoán",
    "TVS": "Chứng khoán", "VPS": "Chứng khoán", "AGR": "Chứng khoán",
    "CTS": "Chứng khoán", "FTS": "Chứng khoán", "SHS": "Chứng khoán",
    "ORS": "Chứng khoán", "VIX": "Chứng khoán", "BVS": "Chứng khoán",
    # ── Bảo hiểm ──────────────────────────────────────────────────────────
    "BVH": "Bảo hiểm", "BMI": "Bảo hiểm", "MIG": "Bảo hiểm",
    "PGI": "Bảo hiểm", "BIC": "Bảo hiểm", "PTI": "Bảo hiểm",
    # ── Bất động sản ──────────────────────────────────────────────────────
    "VHM": "Bất động sản", "NVL": "Bất động sản", "PDR": "Bất động sản",
    "DIG": "Bất động sản", "KDH": "Bất động sản", "TCH": "Bất động sản",
    "NLG": "Bất động sản", "DXG": "Bất động sản", "AGG": "Bất động sản",
    "HQC": "Bất động sản", "CRE": "Bất động sản", "SJS": "Bất động sản",
    "VRE": "Bất động sản", "VPI": "Bất động sản", "CEO": "Bất động sản",
    "DRH": "Bất động sản", "HDG": "Bất động sản", "NTL": "Bất động sản",
    "QCG": "Bất động sản", "SCR": "Bất động sản", "ITA": "Bất động sản",
    "TDH": "Bất động sản", "TDC": "Bất động sản", "IJC": "Bất động sản",
    "IDC": "Bất động sản", "DXS": "Bất động sản", "NBB": "Bất động sản",
    "SGR": "Bất động sản", "OGC": "Bất động sản", "DTA": "Bất động sản",
    "SZC": "Bất động sản", "KBC": "Bất động sản", "SIP": "Bất động sản",
    "SZL": "Bất động sản", "TDM": "Bất động sản", "VID": "Bất động sản",
    "HAG": "Bất động sản", "ROS": "Bất động sản", "LDG": "Bất động sản",
    "HDC": "Bất động sản", "NHA": "Bất động sản", "CLG": "Bất động sản",
    # ── Xây dựng / Hạ tầng ───────────────────────────────────────────────
    "CTD": "Xây dựng", "CTI": "Xây dựng", "CII": "Hạ tầng",
    "VCG": "Xây dựng", "C47": "Xây dựng", "C32": "Xây dựng",
    "LCG": "Xây dựng", "HBC": "Xây dựng", "DPG": "Xây dựng",
    "HTN": "Xây dựng", "FCN": "Xây dựng", "SC5": "Xây dựng",
    "L10": "Xây dựng", "L14": "Xây dựng", "L18": "Xây dựng",
    "L63": "Xây dựng", "PTB": "Xây dựng", "ST8": "Xây dựng",
    "HHV": "Xây dựng",
    # ── Vật liệu xây dựng ─────────────────────────────────────────────────
    "HT1": "Vật liệu XD", "BCC": "Vật liệu XD", "BMP": "Vật liệu XD",
    "VGC": "Vật liệu XD", "ACC": "Vật liệu XD", "PLP": "Vật liệu XD",
    # ── Thép ──────────────────────────────────────────────────────────────
    "HPG": "Thép", "HSG": "Thép", "NKG": "Thép",
    "POM": "Thép", "TLH": "Thép", "SMC": "Thép", "DTL": "Thép",
    # ── Dầu khí ────────────────────────────────────────────────────────────
    "GAS": "Dầu khí", "PVD": "Dầu khí", "PVT": "Dầu khí",
    "PLX": "Dầu khí", "BSR": "Dầu khí", "PVC": "Dầu khí",
    "PVS": "Dầu khí", "PXS": "Dầu khí", "PGD": "Dầu khí",
    "PGN": "Dầu khí", "PGC": "Dầu khí", "CNG": "Dầu khí",
    "GDT": "Dầu khí", "PET": "Dầu khí", "COM": "Dầu khí",
    # ── Điện / Năng lượng tái tạo ─────────────────────────────────────────
    "GEG": "Điện", "REE": "Điện/Hạ tầng", "PC1": "Điện",
    "POW": "Điện", "NT2": "Điện", "PPC": "Điện",
    "TBC": "Điện", "VSH": "Điện", "SJD": "Điện",
    "BWE": "Điện", "SHP": "Điện", "EVG": "Điện", "GEX": "Điện",
    # ── Tiêu dùng / Thực phẩm ─────────────────────────────────────────────
    "VNM": "Tiêu dùng", "MSN": "Tiêu dùng", "SAB": "Tiêu dùng",
    "KDC": "Tiêu dùng", "DBC": "Tiêu dùng", "AGM": "Tiêu dùng",
    "NSC": "Tiêu dùng", "PAN": "Tiêu dùng", "BHN": "Tiêu dùng",
    "LSS": "Tiêu dùng", "SBT": "Tiêu dùng",
    # ── Bán lẻ ────────────────────────────────────────────────────────────
    "MWG": "Bán lẻ", "PNJ": "Bán lẻ", "FRT": "Bán lẻ",
    "DGW": "Bán lẻ", "AST": "Bán lẻ",
    # ── Công nghệ ─────────────────────────────────────────────────────────
    "FPT": "Công nghệ", "CMG": "Công nghệ", "ELC": "Công nghệ",
    "VNG": "Công nghệ", "ICT": "Công nghệ",
    # ── Hàng không ────────────────────────────────────────────────────────
    "VJC": "Hàng không", "HVN": "Hàng không",
    # ── Vận tải / Cảng biển ───────────────────────────────────────────────
    "GMD": "Vận tải", "HAH": "Vận tải", "VOS": "Vận tải",
    "PJT": "Vận tải", "TMS": "Vận tải", "VTB": "Vận tải",
    "SGN": "Vận tải",
    "SCS": "Hạ tầng", "DVP": "Hạ tầng", "VSC": "Hạ tầng",
    # ── Dệt may ───────────────────────────────────────────────────────────
    "TNG": "Dệt may", "STK": "Dệt may", "MSH": "Dệt may",
    "TCM": "Dệt may", "EVE": "Dệt may", "HTG": "Dệt may",
    "GIL": "Dệt may",
    # ── Thủy sản ──────────────────────────────────────────────────────────
    "VHC": "Thủy sản", "ANV": "Thủy sản", "IDI": "Thủy sản",
    "ABT": "Thủy sản", "ACL": "Thủy sản", "FMC": "Thủy sản",
    # ── Y tế / Dược ───────────────────────────────────────────────────────
    "DHG": "Y tế", "DMC": "Y tế", "IMP": "Y tế",
    "OPC": "Y tế", "TRA": "Y tế", "HAI": "Y tế", "DBD": "Y tế",
    # ── Phân bón / Hóa chất ───────────────────────────────────────────────
    "DPM": "Phân bón", "DCM": "Phân bón", "LAS": "Phân bón",
    "SFG": "Phân bón", "VAF": "Phân bón", "DGC": "Hóa chất",
    # ── Cao su ────────────────────────────────────────────────────────────
    "PHR": "Cao su", "DRC": "Cao su", "CSM": "Cao su",
    "SRC": "Cao su", "HRC": "Cao su",
    # ── Khoáng sản ────────────────────────────────────────────────────────
    "KSB": "Khoáng sản", "NBC": "Khoáng sản", "BMC": "Khoáng sản",
    # ── Đa ngành ──────────────────────────────────────────────────────────
    "VIC": "Đa ngành",
}


# ─── Optimal T+: Multi-horizon target matrix ─────────────────────────────────

# Proposal table: score band → T+3/5/7/10 pct targets, SL pct, estimated win rate
_T_PLUS_TARGET_TABLE = [
    # (min_score, t3%, t5%, t7%, t10%, sl%, win_rate_est)
    (80, 4.0,  7.0,  10.0, 15.0, -3.0,  0.68),
    (70, 3.0,  5.0,   8.0, 12.0, -2.5,  0.60),
    (60, 2.0,  3.5,   6.0,  9.0, -2.0,  0.52),
    ( 0, 0.0,  0.0,   0.0,  0.0,  0.0,  0.45),
]


def compute_t_plus_multiframe(
    price: float,
    atr: float,
    score: int,
    bt5_win_rate: float = None,
) -> dict:
    """
    Map T+ confidence_score to multi-horizon absolute price targets.

    Uses the academic proposal table as base win-rate estimates,
    overriding with actual bt5_win_rate when available.

    Args:
        price        : Current price (thousands-VND).
        atr          : ATR-14 (thousands-VND). Used to compute price-band context.
        score        : T+ confidence_score 0–100 from generate_t_plus_recommendation().
        bt5_win_rate : Actual 5-day backtest win rate %. Overrides proposal default.

    Returns:
        dict:
            t3_pct, t5_pct, t7_pct, t10_pct : float  target % returns
            sl_pct                           : float  stop-loss %
            t3_price, t5_price, t7_price, t10_price, sl_price : float absolute prices
            win_rate_est    : float  estimated win rate (bt5 override if available)
            win_rate_source : str   "backtest" | "proposal"
            score_band      : str   e.g. "≥80 (STRONG BUY)"
    """
    empty = {
        "t3_pct": 0.0, "t5_pct": 0.0, "t7_pct": 0.0, "t10_pct": 0.0,
        "sl_pct": 0.0,
        "t3_price": None, "t5_price": None, "t7_price": None, "t10_price": None,
        "sl_price": None,
        "win_rate_est": 0.45, "win_rate_source": "proposal",
        "score_band": "< 60 (AVOID)",
    }
    if not price or price <= 0:
        return empty
    try:
        # Find matching band
        row = _T_PLUS_TARGET_TABLE[-1]  # default: <60
        for min_s, t3, t5, t7, t10, sl, wr in _T_PLUS_TARGET_TABLE:
            if score >= min_s:
                row = (min_s, t3, t5, t7, t10, sl, wr)
                break
        _, t3_pct, t5_pct, t7_pct, t10_pct, sl_pct, wr_est = row

        # Override win rate with actual backtest if available
        if bt5_win_rate is not None and bt5_win_rate > 0:
            win_rate_est    = round(bt5_win_rate / 100.0, 3)
            win_rate_source = "backtest"
        else:
            win_rate_est    = wr_est
            win_rate_source = "proposal"

        def _tp(pct):
            if pct == 0.0:
                return None
            # Round to nearest VN tick (100 VND = 0.1 in thousands-VND)
            raw = price * (1.0 + pct / 100.0)
            return round(raw / 0.1) * 0.1

        band_labels = {
            80: ">= 80 (STRONG BUY)",
            70: "70-79 (BUY)",
            60: "60-69 (WATCH)",
             0: "< 60 (AVOID)",
        }

        return {
            "t3_pct":          t3_pct,
            "t5_pct":          t5_pct,
            "t7_pct":          t7_pct,
            "t10_pct":         t10_pct,
            "sl_pct":          sl_pct,
            "t3_price":        _tp(t3_pct),
            "t5_price":        _tp(t5_pct),
            "t7_price":        _tp(t7_pct),
            "t10_price":       _tp(t10_pct),
            "sl_price":        _tp(sl_pct),
            "win_rate_est":    win_rate_est,
            "win_rate_source": win_rate_source,
            "score_band":      band_labels.get(row[0], "< 60 (AVOID)"),
        }
    except Exception:
        return empty


def calculate_performance(
    holdings_df: pd.DataFrame,
    current_prices: dict,
) -> pd.DataFrame:
    """
    Enrich holdings with: market_value, unrealized_pnl, pnl_pct,
    portfolio_weight, sector.
    current_prices: {ticker: price} dict from fetch_ssi_realtime or batch fetch.
    """
    df = holdings_df.copy()

    def _cur_price(ticker):
        p = current_prices.get(ticker)
        if isinstance(p, dict):
            return p.get("price") or p.get("close") or 0
        return float(p) if p else 0

    df["current_price"]   = df["ticker"].apply(_cur_price)
    df["price_available"] = df["current_price"] > 0
    # When price is unavailable (SSI fetch failed) use cost_basis as fallback
    # so market_value stays neutral and P&L shows 0 instead of fake −100%.
    df["cost_basis"]      = df["qty"] * df["avg_cost"]
    df["market_value"]    = np.where(
        df["price_available"],
        df["qty"] * df["current_price"],
        df["cost_basis"],   # fallback: hold at cost → 0 P&L
    )
    df["unrealized_pnl"]  = np.where(
        df["price_available"],
        df["market_value"] - df["cost_basis"],
        0.0,
    )
    df["pnl_pct"]         = np.where(
        df["price_available"] & (df["cost_basis"] > 0),
        df["unrealized_pnl"] / df["cost_basis"] * 100,
        0.0,
    )
    total_value = df["market_value"].sum()
    df["portfolio_weight"] = np.where(
        total_value > 0,
        df["market_value"] / total_value * 100,
        0.0,
    )
    # Enrich sector if not already set
    if "sector" not in df.columns or (df["sector"] == "").all():
        df["sector"] = df["ticker"].map(_SECTOR_MAP).fillna("Khác")
    else:
        df["sector"] = df.apply(
            lambda r: _SECTOR_MAP.get(r["ticker"], r.get("sector") or "Khác"),
            axis=1,
        )
    return df


def build_portfolio_summary(holdings_df: pd.DataFrame) -> dict:
    """
    Aggregate portfolio-level metrics and sector attribution.
    Returns dict with: total_value, total_cost, total_pnl, total_pnl_pct,
    sector_attribution {sector: pct_weight}, top_gainer, top_loser.
    """
    df = holdings_df
    total_value = df["market_value"].sum()
    total_cost  = df["cost_basis"].sum()
    total_pnl   = df["unrealized_pnl"].sum()
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    sector_attr = (
        df.groupby("sector")["market_value"].sum()
        / total_value * 100
        if total_value > 0
        else pd.Series(dtype=float)
    ).sort_values(ascending=False).to_dict()

    top_gainer = df.loc[df["pnl_pct"].idxmax()] if not df.empty and df["pnl_pct"].max() > 0 else None
    top_loser  = df.loc[df["pnl_pct"].idxmin()] if not df.empty and df["pnl_pct"].min() < 0 else None

    return {
        "total_value":     total_value,
        "total_cost":      total_cost,
        "total_pnl":       total_pnl,
        "total_pnl_pct":   total_pnl_pct,
        "sector_attribution": sector_attr,
        "top_gainer":      top_gainer["ticker"] if top_gainer is not None else "",
        "top_gainer_pct":  float(top_gainer["pnl_pct"]) if top_gainer is not None else 0.0,
        "top_loser":       top_loser["ticker"] if top_loser is not None else "",
        "top_loser_pct":   float(top_loser["pnl_pct"]) if top_loser is not None else 0.0,
        "position_count":  len(df),
    }


# ─── Smoke test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Quick T+2 test
        today = date(2026, 3, 16)  # Monday
        settle = calculate_t2_settlement(today)
        print(f"T+2 from {today} → {settle}")

        # Quick mock portfolio
        mock = pd.DataFrame({
            "ticker":   ["HPG", "VNM", "TCH"],
            "qty":      [1000, 500, 2000],
            "avg_cost": [20000, 60000, 15000],
            "trade_date": [date(2026, 3, 14), date(2026, 3, 12), date(2026, 3, 10)],
        })
        mock = classify_settlement_status(mock, today=today)
        df   = calculate_performance(mock, {"HPG": 21000, "VNM": 58000, "TCH": 16000})
        summary = build_portfolio_summary(df)
        print(df[["ticker", "qty", "avg_cost", "current_price", "pnl_pct", "status"]].to_string())
        print("\nSummary:", summary)
    else:
        df = parse_portfolio_csv(sys.argv[1])
        print(df.to_string())
