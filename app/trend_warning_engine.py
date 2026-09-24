"""
trend_warning_engine.py  —  Trend Transition Warning Engine (TTWE)
===================================================================
Three-layer architecture:
  Layer 1  Raw feature detection (divergence, ADX states, BB squeeze, structure break)
  Layer 2  Data-quality guard
  Layer 3  Explainable state engine → 8 output states

All state constants and scoring logic follow the design document:
  document/insight_report_trend_transition (1).md

Dependencies: pandas, numpy only (no Streamlit — engine is UI-agnostic).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    # Layer-1 detectors
    "detect_macd_divergence",
    "detect_adx_states",
    "detect_bb_squeeze",
    "detect_structure_break",
    # Layer-3 main entry point
    "compute_trend_warning",
    # State constants (for external consumers / tests)
    "UPTREND_STRENGTHENING",
    "UPTREND_EXHAUSTING",
    "DOWNTREND_STRENGTHENING",
    "DOWNTREND_EXHAUSTING",
    "RANGE_COMPRESSION",
    "BREAKOUT_EMERGING",
    "REVERSAL_WARNING_LOW_CONF",
    "REVERSAL_WARNING_CONFIRMED",
    "INSUFFICIENT_DATA",
]

# ─────────────────────────────────────────────────────────────────────────────
#  STATE CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
UPTREND_STRENGTHENING      = "UPTREND_STRENGTHENING"
UPTREND_EXHAUSTING         = "UPTREND_EXHAUSTING"
DOWNTREND_STRENGTHENING    = "DOWNTREND_STRENGTHENING"
DOWNTREND_EXHAUSTING       = "DOWNTREND_EXHAUSTING"
RANGE_COMPRESSION          = "RANGE_COMPRESSION"
BREAKOUT_EMERGING          = "BREAKOUT_EMERGING"
REVERSAL_WARNING_LOW_CONF  = "REVERSAL_WARNING_LOW_CONF"
REVERSAL_WARNING_CONFIRMED = "REVERSAL_WARNING_CONFIRMED"
INSUFFICIENT_DATA          = "INSUFFICIENT_DATA"

_STATE_LABELS: dict[str, str] = {
    UPTREND_STRENGTHENING:      "Xu hướng tăng — Đang tăng cường",
    UPTREND_EXHAUSTING:         "Xu hướng tăng — Dấu hiệu kiệt sức",
    DOWNTREND_STRENGTHENING:    "Xu hướng giảm — Đang tăng cường",
    DOWNTREND_EXHAUSTING:       "Xu hướng giảm — Dấu hiệu kiệt sức",
    RANGE_COMPRESSION:          "Tích lũy / Vùng nén (Squeeze)",
    BREAKOUT_EMERGING:          "Breakout đang hình thành",
    REVERSAL_WARNING_LOW_CONF:  "Cảnh báo đảo chiều — Độ tin cậy thấp",
    REVERSAL_WARNING_CONFIRMED: "Cảnh báo đảo chiều — Được xác nhận",
    INSUFFICIENT_DATA:          "Không đủ dữ liệu",
}

_STATE_COLORS: dict[str, str] = {
    UPTREND_STRENGTHENING:      "#00c853",   # bright green
    UPTREND_EXHAUSTING:         "#ffab40",   # amber
    DOWNTREND_STRENGTHENING:    "#f44336",   # red
    DOWNTREND_EXHAUSTING:       "#ff7043",   # deep orange
    RANGE_COMPRESSION:          "#90a4ae",   # blue-grey
    BREAKOUT_EMERGING:          "#29b6f6",   # light blue
    REVERSAL_WARNING_LOW_CONF:  "#ffd740",   # yellow
    REVERSAL_WARNING_CONFIRMED: "#e040fb",   # purple
    INSUFFICIENT_DATA:          "#546e7a",   # slate grey
}


# ─────────────────────────────────────────────────────────────────────────────
#  LAYER 1 — RAW FEATURE DETECTORS
# ─────────────────────────────────────────────────────────────────────────────

def detect_macd_divergence(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Detect MACD histogram divergence with price over the last *lookback* bars.

    Regular bullish  — price makes lower low,  MACD_Hist makes higher low  → reversal warning ↑
    Regular bearish  — price makes higher high, MACD_Hist makes lower high  → reversal warning ↓
    Hidden  bullish  — price makes higher low,  MACD_Hist makes lower low   → uptrend continues
    Hidden  bearish  — price makes lower high,  MACD_Hist makes higher high → downtrend continues

    Returns
    -------
    dict: bull_div, bear_div, hidden_bull, hidden_bear  (all bool)
    """
    result = dict(bull_div=False, bear_div=False, hidden_bull=False, hidden_bear=False)

    if not {"Close", "MACD_Hist"}.issubset(df.columns) or len(df) < lookback + 2:
        return result

    window = df.tail(lookback + 1).copy()
    closes = window["Close"].values
    hists  = window["MACD_Hist"].values

    valid = ~(np.isnan(closes) | np.isnan(hists))
    if valid.sum() < 4:
        return result

    c_all = closes[valid]
    h_all = hists[valid]

    c_curr = c_all[-1]
    h_curr = h_all[-1]
    c_prev = c_all[:-1]
    h_prev = h_all[:-1]

    c_low_prev  = float(np.min(c_prev))
    c_high_prev = float(np.max(c_prev))
    h_low_prev  = float(np.min(h_prev))
    h_high_prev = float(np.max(h_prev))

    # Regular divergence
    result["bull_div"]    = bool(c_curr < c_low_prev  and h_curr > h_low_prev)
    result["bear_div"]    = bool(c_curr > c_high_prev and h_curr < h_high_prev)

    # Hidden divergence (continuation signals)
    result["hidden_bull"] = bool(c_curr > c_low_prev  and h_curr < h_low_prev  and h_curr < 0)
    result["hidden_bear"] = bool(c_curr < c_high_prev and h_curr > h_high_prev and h_curr > 0)

    return result


def detect_adx_states(df: pd.DataFrame) -> dict:
    """
    Detect ADX-based trend-strength states from the last 3 ADX bars.

    Returns
    -------
    dict:
      breakout_20   ADX crossed above 20 from below (in last 3 bars)
      breakout_25   ADX crossed above 25 from below (in last 3 bars)
      exhaustion    ADX > 45 AND currently falling (last 3 bars)
      acceleration  ADX rose > 3 pts from prev → prev bar
      adx_rising    ADX is consistently rising (last 3 bars)
      adx_falling   ADX is consistently falling (last 3 bars)
    """
    result = dict(
        breakout_20=False, breakout_25=False,
        exhaustion=False, acceleration=False,
        adx_rising=False, adx_falling=False,
    )

    if "ADX" not in df.columns or len(df) < 4:
        return result

    adx_arr = df["ADX"].dropna().values
    if len(adx_arr) < 3:
        return result

    adx_cur  = float(adx_arr[-1])
    adx_prev = float(adx_arr[-2])
    adx_ago  = float(adx_arr[-3])

    result["adx_rising"]  = bool(adx_cur > adx_prev > adx_ago)
    result["adx_falling"] = bool(adx_cur < adx_prev < adx_ago)

    # Breakout: ADX was below threshold 3 bars ago, now above
    result["breakout_20"] = bool(adx_cur >= 20.0 and adx_ago < 20.0)
    result["breakout_25"] = bool(adx_cur >= 25.0 and adx_ago < 25.0)

    # Exhaustion: ADX > 45 and trending down for 3 bars
    result["exhaustion"]    = bool(adx_cur > 45.0 and result["adx_falling"])

    # Acceleration: ADX jumped > 3 pts in a single bar
    result["acceleration"]  = bool((adx_cur - adx_prev) > 3.0)

    return result


def detect_bb_squeeze(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Detect Bollinger Band squeeze and expansion.

    Squeeze    — current BB width < 40% of lookback-bar average width.
    Expansion  — current BB width > 120% of average AND > prior-bar width (breakout of squeeze).
    Outer touch — Close is at or beyond the BB band edge (±0.5% tolerance).

    Returns
    -------
    dict:
      squeeze          bool
      expansion        bool
      outer_touch_upper bool
      outer_touch_lower bool
      bb_width_ratio   float  (current / avg; NaN if unavailable)
    """
    result = dict(
        squeeze=False, expansion=False,
        outer_touch_upper=False, outer_touch_lower=False,
        bb_width_ratio=float("nan"),
    )

    if not {"BB_Upper", "BB_Lower", "Close"}.issubset(df.columns) or len(df) < 4:
        return result

    upper = df["BB_Upper"].values
    lower = df["BB_Lower"].values
    close = df["Close"].values

    widths = upper - lower
    valid_w = widths[~np.isnan(widths)]
    if len(valid_w) < 4:
        return result

    cur_w  = float(valid_w[-1])
    prev_w = float(valid_w[-2])
    avg_w  = float(np.mean(valid_w[-lookback:])) if len(valid_w) >= lookback else float(np.mean(valid_w))

    if avg_w > 0:
        ratio = cur_w / avg_w
        result["bb_width_ratio"] = round(ratio, 3)
        result["squeeze"]    = bool(ratio < 0.40)
        result["expansion"]  = bool(ratio > 1.20 and cur_w > prev_w * 1.05)

    # Outer touch
    valid_c = close[~np.isnan(close)]
    valid_u = upper[~np.isnan(upper)]
    valid_l = lower[~np.isnan(lower)]
    if len(valid_c) and len(valid_u) and len(valid_l):
        lc = float(valid_c[-1])
        lu = float(valid_u[-1])
        ll = float(valid_l[-1])
        if lu > 0:
            result["outer_touch_upper"] = bool(lc >= lu * 0.995)
        if ll > 0:
            result["outer_touch_lower"] = bool(lc <= ll * 1.005)

    return result


def detect_structure_break(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Detect price-structure breaks using the prior *lookback* bars' swing High/Low.

    break_up   — Close > max(High) of prior bars → resistance broken
    break_down — Close < min(Low)  of prior bars → support broken

    Returns
    -------
    dict: break_up, break_down, resist_lvl, support_lvl
    """
    result = dict(
        break_up=False, break_down=False,
        resist_lvl=float("nan"), support_lvl=float("nan"),
    )

    if not {"High", "Low", "Close"}.issubset(df.columns) or len(df) < lookback + 2:
        return result

    prior   = df.iloc[-(lookback + 1):-1]
    current = df.iloc[-1]

    resist  = float(prior["High"].max())
    support = float(prior["Low"].min())

    result["resist_lvl"]  = resist
    result["support_lvl"] = support
    result["break_up"]    = bool(float(current["Close"]) > resist)
    result["break_down"]  = bool(float(current["Close"]) < support)

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  LAYER 2 — DATA-QUALITY GUARD
# ─────────────────────────────────────────────────────────────────────────────

def _data_quality_ok(r: dict, df: pd.DataFrame) -> tuple[bool, str]:
    """Return (True, '') if data is sufficient, else (False, reason_string)."""
    if df is None or len(df) < 30:
        return False, "Không đủ dữ liệu (< 30 phiên)"
    price = r.get("price")
    if not price or price <= 0:
        return False, "Giá không hợp lệ"
    if r.get("adx") is None or r.get("rsi") is None:
        return False, "Chỉ báo ADX/RSI chưa tính được"
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_rationale(
    state: str, evidence: list[str], confidence: str,
    adx: float, rsi: float, regime: str,
) -> str:
    """Build a plain-language Vietnamese rationale for the given TTWE state."""
    regime_vi = {
        "BULL_TREND": "xu hướng tăng",
        "BEAR_TREND": "xu hướng giảm",
        "SIDEWAYS":   "tích lũy / sideways",
        "HIGH_VOL":   "biến động cao",
    }.get(regime, regime)

    base = {
        UPTREND_STRENGTHENING:
            f"Cổ phiếu đang trong {regime_vi}. ADX={adx:.1f}, động lực còn mạnh, chưa có tín hiệu kiệt sức.",
        UPTREND_EXHAUSTING:
            f"Xu hướng tăng có thể đang suy yếu. ADX={adx:.1f}, RSI={rsi:.0f}. "
            "Xuất hiện tín hiệu phân kỳ hoặc ADX kiệt sức — thận trọng với vị thế mua mới.",
        DOWNTREND_STRENGTHENING:
            f"Cổ phiếu đang trong {regime_vi}. ADX={adx:.1f}, lực giảm còn được duy trì.",
        DOWNTREND_EXHAUSTING:
            f"Xu hướng giảm có thể đang hạ nhiệt. ADX={adx:.1f}, RSI={rsi:.0f}. "
            "Xuất hiện tín hiệu phân kỳ hướng phục hồi — theo dõi xác nhận.",
        RANGE_COMPRESSION:
            f"Biến động đang thu hẹp mạnh (BB squeeze). ADX={adx:.1f} < 20. "
            "Thị trường tích lũy, có thể bùng nổ bất kỳ lúc nào — chờ xác nhận hướng.",
        BREAKOUT_EMERGING:
            f"Tín hiệu breakout đang hình thành. ADX={adx:.1f} đang tăng và/hoặc BB đang mở rộng. "
            "Cần xác nhận thêm bằng khối lượng và giá đóng cửa cuối phiên.",
        REVERSAL_WARNING_LOW_CONF:
            f"Phân kỳ kỹ thuật xuất hiện nhưng chưa có xác nhận cấu trúc. "
            f"ADX={adx:.1f}, RSI={rsi:.0f}. Đây là cảnh báo sớm — theo dõi thêm trước khi hành động.",
        REVERSAL_WARNING_CONFIRMED:
            f"Cảnh báo đảo chiều được xác nhận bởi nhiều tín hiệu đồng thuận. "
            f"ADX={adx:.1f}, RSI={rsi:.0f}. Đánh giá lại vị thế hiện tại một cách thận trọng.",
        INSUFFICIENT_DATA:
            "Không đủ dữ liệu để phân tích xu hướng.",
    }.get(state, "")

    if evidence:
        n = len(evidence)
        ev_str = "; ".join(evidence[:3]) + ("..." if n > 3 else "")
        base += f"  ({n} tín hiệu: {ev_str})"

    return base


# ─────────────────────────────────────────────────────────────────────────────
#  LAYER 3 — EXPLAINABLE STATE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_trend_warning(r: dict, df: pd.DataFrame) -> dict:
    """
    Main TTWE entry point. Combines all three layers into a single state dict.

    Parameters
    ----------
    r  : dict returned by ``analyse_ticker()``
    df : OHLCV + indicator DataFrame from ``calculate_indicators()``

    Returns
    -------
    dict with keys:
        state               str    one of the 9 TTWE state constants
        state_label         str    Vietnamese display label
        state_color         str    hex colour string
        confidence          str    "LOW" | "MEDIUM" | "HIGH"
        exhaustion_score    int
        emergence_score     int
        evidence            list[str]  fired signals (human-readable)
        rationale           str    plain-language explanation (Vietnamese)
        macd_div            dict   from detect_macd_divergence()
        adx_states          dict   from detect_adx_states()
        bb_states           dict   from detect_bb_squeeze()
        struct_states       dict   from detect_structure_break()
        data_ok             bool
        data_issue          str    non-empty string when data_ok is False
    """
    # ── Layer 2: data-quality guard ───────────────────────────────────────────
    data_ok, data_issue = _data_quality_ok(r, df)
    if not data_ok:
        return {
            "state":            INSUFFICIENT_DATA,
            "state_label":      _STATE_LABELS[INSUFFICIENT_DATA],
            "state_color":      _STATE_COLORS[INSUFFICIENT_DATA],
            "confidence":       "LOW",
            "exhaustion_score": 0,
            "emergence_score":  0,
            "evidence":         [data_issue],
            "rationale":        data_issue,
            "macd_div":         {},
            "adx_states":       {},
            "bb_states":        {},
            "struct_states":    {},
            "data_ok":          False,
            "data_issue":       data_issue,
        }

    # ── Layer 1: raw feature detection ───────────────────────────────────────
    macd_div      = detect_macd_divergence(df)
    adx_states    = detect_adx_states(df)
    bb_states     = detect_bb_squeeze(df)
    struct_states = detect_structure_break(df)

    # Scalar shortcuts (with safe defaults so downstream maths never raises)
    rsi      = float(r.get("rsi")          or 50.0)
    adx      = float(r.get("adx")          or 0.0)
    pdi      = float(r.get("pdi")          or 0.0)
    ndi      = float(r.get("ndi")          or 0.0)
    macd_val = float(r.get("macd")         or 0.0)
    macd_sig = float(r.get("macd_signal")  or 0.0)
    macd_hst = float(r.get("macd_hist")    or 0.0)
    kl_ratio = float(r.get("kl_ratio")     or 1.0)
    regime   = str(r.get("regime", "SIDEWAYS"))
    rsi_div  = str(r.get("rsi_divergence", "NONE"))   # "BULLISH"|"BEARISH"|"NONE"

    is_uptrend   = (regime == "BULL_TREND") or (pdi > ndi and adx > 20.0)
    is_downtrend = (regime == "BEAR_TREND") or (ndi > pdi and adx > 20.0)

    evidence:         list[str] = []
    exhaustion_score: int       = 0
    emergence_score:  int       = 0

    # ── Exhaustion scoring ────────────────────────────────────────────────────

    # RSI divergence (already computed inside Quant_Profiler.py)
    if rsi_div == "BEARISH":
        exhaustion_score += 2
        evidence.append("RSI bearish divergence")
    elif rsi_div == "BULLISH":
        exhaustion_score += 2
        evidence.append("RSI bullish divergence")

    # MACD histogram divergence
    if macd_div["bear_div"] and is_uptrend:
        exhaustion_score += 2
        evidence.append("MACD bearish divergence")
    if macd_div["bull_div"] and is_downtrend:
        exhaustion_score += 2
        evidence.append("MACD bullish divergence")

    # RSI extreme (overbought / oversold)
    if rsi > 70.0 and is_uptrend:
        exhaustion_score += 1
        evidence.append(f"RSI quá mua ({rsi:.0f})")
    elif rsi < 30.0 and is_downtrend:
        exhaustion_score += 1
        evidence.append(f"RSI quá bán ({rsi:.0f})")

    # MACD crossover against the current trend
    if macd_val < macd_sig and is_uptrend:
        exhaustion_score += 1
        evidence.append("MACD cắt xuống signal (bearish cross)")
    elif macd_val > macd_sig and is_downtrend:
        exhaustion_score += 1
        evidence.append("MACD cắt lên signal (bullish cross ngược xu hướng)")

    # ADX exhaustion
    if adx_states["exhaustion"]:
        exhaustion_score += 2
        evidence.append(f"ADX kiệt sức ({adx:.1f} > 45, đang giảm)")

    # BB outer touch in trending context
    if bb_states["outer_touch_upper"] and is_uptrend:
        exhaustion_score += 1
        evidence.append("Giá chạm / vượt BB trên (vùng quá mua kỹ thuật)")
    elif bb_states["outer_touch_lower"] and is_downtrend:
        exhaustion_score += 1
        evidence.append("Giá chạm / dưới BB dưới (vùng quá bán kỹ thuật)")

    # ── Emergence / breakout scoring ─────────────────────────────────────────

    # BB squeeze release (expansion)
    if bb_states["expansion"]:
        emergence_score += 2
        evidence.append("BB squeeze mở rộng (breakout tiềm năng)")

    # ADX breakout
    if adx_states["breakout_25"]:
        emergence_score += 2
        evidence.append("ADX cắt lên 25 (xu hướng mới được xác nhận)")
    elif adx_states["breakout_20"]:
        emergence_score += 2
        evidence.append("ADX cắt lên 20 (xu hướng mới đang hình thành)")

    # MACD histogram momentum
    if macd_hst > 0.0 and macd_val > macd_sig:
        emergence_score += 1
        evidence.append("MACD histogram dương (động lượng tăng)")
    elif macd_hst < 0.0 and macd_val < macd_sig:
        emergence_score += 1
        evidence.append("MACD histogram âm (động lượng giảm)")

    # Volume confirmation
    if kl_ratio >= 1.5:
        emergence_score += 1
        evidence.append(f"Khối lượng đột biến ({kl_ratio:.1f}× MA20)")

    # Price structure break
    if struct_states["break_up"]:
        emergence_score += 1
        evidence.append("Giá phá kháng cự cấu trúc (breakout lên)")
    elif struct_states["break_down"]:
        emergence_score += 1
        evidence.append("Giá phá hỗ trợ cấu trúc (breakdown)")

    # Hidden divergence → trend continuation
    if macd_div["hidden_bull"] and is_uptrend:
        emergence_score += 1
        evidence.append("MACD hidden bullish divergence (xu hướng tăng tiếp diễn)")
    if macd_div["hidden_bear"] and is_downtrend:
        emergence_score += 1
        evidence.append("MACD hidden bearish divergence (xu hướng giảm tiếp diễn)")

    # ADX acceleration
    if adx_states["acceleration"]:
        emergence_score += 1
        evidence.append(f"ADX tăng tốc mạnh ({adx:.1f})")

    # ── Confidence ────────────────────────────────────────────────────────────
    top_score = max(exhaustion_score, emergence_score)
    if top_score >= 5:
        confidence = "HIGH"
    elif top_score >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # ── Layer 3: explainable state engine ─────────────────────────────────────
    # Convenience flags
    exhausting         = exhaustion_score >= 3
    has_reversal_div   = (rsi_div != "NONE") or macd_div["bear_div"] or macd_div["bull_div"]
    has_struct_confirm = struct_states["break_up"] or struct_states["break_down"]
    has_vol_confirm    = kl_ratio >= 1.5
    adx_breakout       = adx_states["breakout_20"] or adx_states["breakout_25"]

    # Priority order (higher priority checked first):
    #  1. BB expansion or ADX breakout            → BREAKOUT_EMERGING
    #  2. Divergence + structure / volume proof   → REVERSAL_WARNING_CONFIRMED
    #  3. Exhaustion in a clear trend             → UPTREND/DOWNTREND_EXHAUSTING
    #  4. Pure divergence, no confirmation        → REVERSAL_WARNING_LOW_CONF
    #  5. BB squeeze + low ADX                    → RANGE_COMPRESSION
    #  6. Uptrend with rising ADX                 → UPTREND_STRENGTHENING
    #  7. Downtrend with rising ADX               → DOWNTREND_STRENGTHENING
    #  8. Uptrend default                         → UPTREND_STRENGTHENING
    #  9. Downtrend default                       → DOWNTREND_STRENGTHENING
    # 10. Fallback                                → RANGE_COMPRESSION

    if adx_breakout or bb_states["expansion"]:
        state = BREAKOUT_EMERGING

    elif has_reversal_div and (
        has_struct_confirm
        or (has_vol_confirm and exhaustion_score >= 4)
    ):
        state = REVERSAL_WARNING_CONFIRMED

    elif exhausting:
        if is_uptrend:
            state = UPTREND_EXHAUSTING
        elif is_downtrend:
            state = DOWNTREND_EXHAUSTING
        else:
            state = REVERSAL_WARNING_LOW_CONF

    elif has_reversal_div:
        state = REVERSAL_WARNING_LOW_CONF

    elif bb_states["squeeze"] and adx < 20.0:
        state = RANGE_COMPRESSION

    elif is_uptrend and adx_states["adx_rising"]:
        state = UPTREND_STRENGTHENING

    elif is_downtrend and adx_states["adx_rising"]:
        state = DOWNTREND_STRENGTHENING

    elif is_uptrend:
        state = UPTREND_STRENGTHENING

    elif is_downtrend:
        state = DOWNTREND_STRENGTHENING

    else:
        state = RANGE_COMPRESSION

    rationale = _build_rationale(state, evidence, confidence, adx, rsi, regime)

    return {
        "state":            state,
        "state_label":      _STATE_LABELS[state],
        "state_color":      _STATE_COLORS[state],
        "confidence":       confidence,
        "exhaustion_score": exhaustion_score,
        "emergence_score":  emergence_score,
        "evidence":         evidence,
        "rationale":        rationale,
        "macd_div":         macd_div,
        "adx_states":       adx_states,
        "bb_states":        bb_states,
        "struct_states":    struct_states,
        "data_ok":          True,
        "data_issue":       "",
    }
