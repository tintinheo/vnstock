"""Multi-Horizon Forecast Engine — rule-based probabilistic forecast across
three time horizons for VN equities.

Horizons:
  Short  3–5 trading days  — momentum & candlestick signals
  Mid    ~1 calendar month — trend structure & regime
  Long   3–6 months        — fundamentals, macro, secular trend

All signals are derived from columns already present in the DataFrame
produced by ``compute_all()``.  No new data fetches or ML models are
required.

Returns a dict with 11 keys:
  {short,mid,long}_{vote,conf,reasons}
  overall_{vote,conf}

Votes: "TĂNG" | "GIẢM" | "TRUNG LẬP"
Conf:  0.0–100.0 (percentage)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.config import cfg


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(df: pd.DataFrame, col: str) -> float | None:
    try:
        if col not in df.columns:
            return None
        v = df[col].iloc[-1]
        return None if pd.isna(float(v)) else float(v)
    except Exception:
        return None


def _arr(df: pd.DataFrame, col: str, n: int) -> list[float]:
    try:
        if col not in df.columns or len(df) < n:
            return []
        return [float(v) for v in df[col].iloc[-n:].tolist() if not np.isnan(float(v))]
    except Exception:
        return []


def _slope_pct(series_tail: list[float]) -> float:
    """Return (last - first) / |first| * 100."""
    if len(series_tail) < 2:
        return 0.0
    try:
        first = series_tail[0]
        last  = series_tail[-1]
        return (last - first) / max(abs(first), 1e-9) * 100
    except Exception:
        return 0.0


def _vote(bull_pts: float, bear_pts: float, threshold: float = 2.0) -> tuple[str, float]:
    """Convert raw bull/bear scores into a normalised vote + confidence."""
    margin = bull_pts - bear_pts
    total  = bull_pts + bear_pts + 1e-9
    raw_conf = abs(margin) / total * 100
    conf = min(95.0, max(5.0, raw_conf))
    if   margin >  threshold: return "TĂNG",      round(conf, 1)
    elif margin < -threshold: return "GIẢM",       round(conf, 1)
    else:                     return "TRUNG LẬP",  round(min(conf, 60.0), 1)


# ── Short horizon (3–5 days) ──────────────────────────────────────────────────

def _forecast_short(df: pd.DataFrame) -> tuple[str, float, list[str]]:
    """RSI momentum, MACD, Stochastic, BB position, vol, gap."""
    bull, bear = 0.0, 0.0
    reasons: list[str] = []

    close   = _f(df, "close")
    rsi     = _f(df, "RSI14")
    stoch_k = _f(df, "STOCH_K")
    stoch_d = _f(df, "STOCH_D")
    bb_upper= _f(df, "BB_upper")
    bb_lower= _f(df, "BB_lower")
    bb_mid  = _f(df, "BB_mid")
    mh_arr  = _arr(df, "MACD_hist", 4)
    vol_arr = _arr(df, "volume", 10)
    gap_type = ""
    try:
        if "gap_type" in df.columns:
            v = df["gap_type"].iloc[-1]
            if isinstance(v, str):
                gap_type = v
    except Exception:
        pass

    # RSI
    if rsi is not None:
        if rsi < 35:
            bull += 3.0; reasons.append(f"RSI quá bán ({rsi:.0f}) — phục hồi khả năng cao")
        elif 35 <= rsi < 50:
            bull += 1.5; reasons.append(f"RSI tích lũy ({rsi:.0f})")
        elif 50 < rsi <= 65:
            bull += 1.0; reasons.append(f"RSI tăng ({rsi:.0f})")
        elif rsi > 75:
            bear += 3.0; reasons.append(f"RSI quá mua ({rsi:.0f}) — rủi ro điều chỉnh")
        elif 65 < rsi <= 75:
            bear += 1.0; reasons.append(f"RSI cao ({rsi:.0f})")

    # MACD histogram slope
    if len(mh_arr) >= 3:
        if mh_arr[-1] > mh_arr[-2] > mh_arr[-3]:
            bull += 2.0; reasons.append("MACD_hist tăng nhanh — momentum ngắn hạn tích cực")
        elif mh_arr[-3] < 0 < mh_arr[-1]:
            bull += 3.0; reasons.append("MACD_hist vừa cắt qua 0 lên — tín hiệu mua")
        elif mh_arr[-1] < mh_arr[-2] < mh_arr[-3]:
            bear += 2.0; reasons.append("MACD_hist giảm — áp lực bán ngắn hạn")
        elif mh_arr[-3] > 0 > mh_arr[-1]:
            bear += 3.0; reasons.append("MACD_hist vừa cắt qua 0 xuống — tín hiệu bán")

    # Stochastic
    if stoch_k is not None and stoch_d is not None:
        stk_arr = _arr(df, "STOCH_K", 3)
        std_arr = _arr(df, "STOCH_D", 3)
        if (len(stk_arr) >= 2 and len(std_arr) >= 2
                and stk_arr[-1] > std_arr[-1] and stk_arr[-2] < std_arr[-2]):
            if stoch_k < 40:
                bull += 2.5; reasons.append(f"Stoch golden cross vùng quá bán ({stoch_k:.0f})")
            elif stoch_k < 60:
                bull += 1.0; reasons.append(f"Stoch cross dưới trung bình ({stoch_k:.0f})")
        if (len(stk_arr) >= 2 and len(std_arr) >= 2
                and stk_arr[-1] < std_arr[-1] and stk_arr[-2] > std_arr[-2]):
            if stoch_k > 70:
                bear += 2.5; reasons.append(f"Stoch death cross vùng quá mua ({stoch_k:.0f})")

    # Bollinger Band position
    if close and bb_lower and bb_upper and bb_mid:
        bb_range = max(bb_upper - bb_lower, 1e-9)
        pos = (close - bb_lower) / bb_range  # 0=lower, 0.5=mid, 1=upper
        if pos < 0.15:
            bull += 2.0; reasons.append("Giá tại dải BB dưới — hỗ trợ mạnh")
        elif pos > 0.88:
            bear += 1.5; reasons.append("Giá áp sát dải BB trên — kháng cự")

    # Volume confirmation
    if len(vol_arr) >= 5:
        vol_now = vol_arr[-1]
        vol_avg = float(np.mean(vol_arr[:-1]))
        if vol_avg > 0:
            vr = vol_now / vol_avg
            if vr > 1.8:
                bull += 1.0; reasons.append(f"Khối lượng bùng nổ ({vr:.1f}x)")
            elif vr < 0.5:
                bear += 0.5; reasons.append("Khối lượng cạn — thiếu xác nhận")

    # Gap
    if gap_type == "GAP_UP":
        bull += 1.5; reasons.append("Gap tăng — momentum ngắn hạn tích cực")
    elif gap_type == "GAP_DOWN":
        bear += 1.5; reasons.append("Gap giảm — áp lực ngắn hạn")

    vote, conf = _vote(bull, bear, threshold=2.0)
    return vote, conf, reasons[:5]   # cap reasons at 5


# ── Mid horizon (~1 month) ────────────────────────────────────────────────────

def _forecast_mid(df: pd.DataFrame, profile_context: dict) -> tuple[str, float, list[str]]:
    """MA alignment, AMD phase, OBV slope, HMM state, ADX trend."""
    bull, bear = 0.0, 0.0
    reasons: list[str] = []

    close   = _f(df, "close")
    sma20   = _f(df, "SMA20")
    sma50   = _f(df, "SMA50")
    sma200  = _f(df, "SMA200")
    adx     = _f(df, "ADX")
    di_plus = _f(df, "DI_plus")
    di_minus= _f(df, "DI_minus")
    rsi     = _f(df, "RSI14")

    hmm_state  = str(profile_context.get("hmm_state", ""))
    amd_phase  = str(profile_context.get("amd_phase", ""))
    macro_regime = str(profile_context.get("macro_regime", ""))

    # MA stack (SMA20 vs SMA50 vs SMA200)
    if sma20 and sma50 and sma200:
        if sma20 > sma50 > sma200:
            bull += 3.0; reasons.append("MA stack tăng hoàn chỉnh (SMA20>50>200)")
        elif sma20 < sma50 < sma200:
            bear += 3.0; reasons.append("MA stack giảm hoàn chỉnh (SMA20<50<200)")
        elif sma20 > sma50:
            bull += 1.0; reasons.append("SMA20 trên SMA50 — xu hướng trung hạn tích cực")
        else:
            bear += 1.0; reasons.append("SMA20 dưới SMA50 — xu hướng trung hạn yếu")

    # Price vs SMA200
    if close and sma200:
        if close > sma200 * 1.02:
            bull += 2.0; reasons.append("Giá trên SMA200 — xu hướng dài hạn tăng")
        elif close < sma200 * 0.98:
            bear += 2.0; reasons.append("Giá dưới SMA200 — xu hướng dài hạn giảm")

    # OBV 20-day slope
    obv_arr_20 = _arr(df, "OBV", 20)
    obv_slope  = _slope_pct(obv_arr_20)
    if obv_slope > 5:
        bull += 1.5; reasons.append(f"OBV tăng bền vững ({obv_slope:+.1f}%) — tổ chức tích lũy")
    elif obv_slope < -5:
        bear += 1.5; reasons.append(f"OBV giảm bền vững ({obv_slope:+.1f}%) — tổ chức phân phối")

    # ADX trend strength
    if adx and di_plus and di_minus:
        if adx > 25 and di_plus > di_minus:
            bull += 2.0; reasons.append(f"Xu hướng tăng mạnh (ADX={adx:.0f}, DI+>{di_minus:.0f})")
        elif adx > 25 and di_minus > di_plus:
            bear += 2.0; reasons.append(f"Xu hướng giảm mạnh (ADX={adx:.0f}, DI->{di_minus:.0f})")

    # HMM state
    if "BULL" in hmm_state:
        bull += 1.5; reasons.append(f"HMM state: {hmm_state}")
    elif "BEAR" in hmm_state:
        bear += 1.5; reasons.append(f"HMM state: {hmm_state}")

    # AMD phase
    if amd_phase in ("ACCUMULATION", "MARKUP"):
        bull += 1.5; reasons.append(f"Giai đoạn Wyckoff: {amd_phase}")
    elif amd_phase in ("DISTRIBUTION", "MARKDOWN"):
        bear += 1.5; reasons.append(f"Giai đoạn Wyckoff: {amd_phase}")

    # Macro
    if macro_regime == "ACCOMMODATIVE":
        bull += 1.0; reasons.append("Môi trường vĩ mô thuận lợi")
    elif macro_regime == "RESTRICTIVE":
        bear += 1.0; reasons.append("Môi trường vĩ mô thắt chặt")

    vote, conf = _vote(bull, bear, threshold=2.5)
    return vote, conf, reasons[:5]


# ── Long horizon (3–6 months) ─────────────────────────────────────────────────

def _forecast_long(df: pd.DataFrame, profile_context: dict) -> tuple[str, float, list[str]]:
    """SMA200 slope, macro, fundamentals, OBV long-term, Hurst."""
    bull, bear = 0.0, 0.0
    reasons: list[str] = []

    close   = _f(df, "close")

    macro_regime    = str(profile_context.get("macro_regime", ""))
    macro_score     = profile_context.get("macro_score")
    fundamental_score = profile_context.get("fundamental_score")
    hurst = _f(df, "Hurst")

    # SMA200 slope (long-term trend direction)
    sma200_arr = _arr(df, "SMA200", 40)
    sma200_slope = _slope_pct(sma200_arr)
    if sma200_slope > 3.0:
        bull += 3.0; reasons.append(f"SMA200 xu hướng tăng ({sma200_slope:+.1f}%/40 phiên)")
    elif sma200_slope < -3.0:
        bear += 3.0; reasons.append(f"SMA200 xu hướng giảm ({sma200_slope:+.1f}%/40 phiên)")
    elif sma200_slope > 1.0:
        bull += 1.0; reasons.append(f"SMA200 tăng nhẹ ({sma200_slope:+.1f}%)")
    elif sma200_slope < -1.0:
        bear += 1.0; reasons.append(f"SMA200 giảm nhẹ ({sma200_slope:+.1f}%)")

    # Macro score
    # [BUG-29 FIX] Use config-driven thresholds (accommodative_min / restrictive_max)
    # instead of hardcoded ±20, which was inconsistent with the macro engine’s own ±15
    # classification bands, causing vote mismatches at scores between ±15 and ±20.
    _acc_thr  = float(cfg.strategy("macro", "accommodative_min", default=15))
    _rest_thr = float(cfg.strategy("macro", "restrictive_max",   default=-15))
    if macro_score is not None:
        if macro_score > _acc_thr:
            bull += 2.0; reasons.append(f"Kinh tế vĩ mô thuận ({macro_score:+.0f})")
        elif macro_score < _rest_thr:
            bear += 2.0; reasons.append(f"Kinh tế vĩ mô bất lợi ({macro_score:+.0f})")
    if macro_regime == "ACCOMMODATIVE":
        bull += 1.5; reasons.append("Chính sách tiền tệ nới lỏng")
    elif macro_regime == "RESTRICTIVE":
        bear += 1.5; reasons.append("Chính sách tiền tệ thắt chặt")

    # Fundamental score
    if fundamental_score is not None:
        if fundamental_score > 65:
            bull += 2.5; reasons.append(f"Cơ bản tốt (score={fundamental_score:.0f})")
        elif fundamental_score > 45:
            bull += 1.0; reasons.append(f"Cơ bản ổn (score={fundamental_score:.0f})")
        elif fundamental_score < 30:
            bear += 2.0; reasons.append(f"Cơ bản yếu (score={fundamental_score:.0f})")

    # OBV 60-bar slope
    obv_long = _arr(df, "OBV", 60)
    obv_slope_long = _slope_pct(obv_long)
    if obv_slope_long > 10:
        bull += 1.5; reasons.append(f"OBV dài hạn tăng mạnh ({obv_slope_long:+.1f}%)")
    elif obv_slope_long < -10:
        bear += 1.5; reasons.append(f"OBV dài hạn giảm mạnh ({obv_slope_long:+.1f}%)")

    # Hurst exponent
    if hurst is not None:
        if hurst > 0.60:
            # Trending asset — follow whatever direction SMA200 says
            if sma200_slope > 0: bull += 1.0
            else:                 bear += 1.0
            reasons.append(f"Hurst={hurst:.2f} → xu hướng bền vững")
        elif hurst < 0.45:
            reasons.append(f"Hurst={hurst:.2f} → thị trường hồi quy trung bình (ít tin cậy)")

    vote, conf = _vote(bull, bear, threshold=3.0)
    return vote, conf, reasons[:5]


# ── Overall aggregation ───────────────────────────────────────────────────────

_VOTE_VAL = {"TĂNG": 1, "TRUNG LẬP": 0, "GIẢM": -1}


def _aggregate(
    sv: str, sc: float,
    mv: str, mc: float,
    lv: str, lc: float,
) -> tuple[str, float]:
    """Weighted aggregate vote (Short 40%, Mid 35%, Long 25%)."""
    weights = {"short": 0.40, "mid": 0.35, "long": 0.25}
    score = (
        _VOTE_VAL.get(sv, 0) * sc / 100 * weights["short"]
        + _VOTE_VAL.get(mv, 0) * mc / 100 * weights["mid"]
        + _VOTE_VAL.get(lv, 0) * lc / 100 * weights["long"]
    )
    avg_conf = sc * weights["short"] + mc * weights["mid"] + lc * weights["long"]
    if   score >  0.12: return "TĂNG",      round(avg_conf, 1)
    elif score < -0.12: return "GIẢM",      round(avg_conf, 1)
    else:               return "TRUNG LẬP", round(avg_conf * 0.7, 1)


# ── Public API ────────────────────────────────────────────────────────────────

def compute_multi_horizon_forecast(
    df: pd.DataFrame,
    profile_context: dict | None = None,
) -> dict:
    """
    Compute a three-horizon forecast for a ticker.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV + indicators from ``compute_all()``.
    profile_context : dict, optional
        Keys: hmm_state, amd_phase, macro_regime, macro_score,
              fundamental_score, t25_score

    Returns
    -------
    dict with keys:
        short_vote, short_conf, short_reasons
        mid_vote,   mid_conf,   mid_reasons
        long_vote,  long_conf,  long_reasons
        overall_vote, overall_conf
    """
    ctx = profile_context or {}

    if len(df) < 20:
        empty = {"vote": "TRUNG LẬP", "conf": 0.0, "reasons": ["Không đủ dữ liệu"]}
        return {
            "short_vote": "TRUNG LẬP", "short_conf": 0.0,
            "short_reasons": ["Không đủ dữ liệu"],
            "mid_vote":   "TRUNG LẬP", "mid_conf":   0.0,
            "mid_reasons":  ["Không đủ dữ liệu"],
            "long_vote":  "TRUNG LẬP", "long_conf":  0.0,
            "long_reasons": ["Không đủ dữ liệu"],
            "overall_vote": "TRUNG LẬP", "overall_conf": 0.0,
        }

    sv, sc, sr = _forecast_short(df)
    mv, mc, mr = _forecast_mid(df, ctx)
    lv, lc, lr = _forecast_long(df, ctx)
    ov, oc = _aggregate(sv, sc, mv, mc, lv, lc)

    return {
        "short_vote":    sv,
        "short_conf":    sc,
        "short_reasons": sr,
        "mid_vote":      mv,
        "mid_conf":      mc,
        "mid_reasons":   mr,
        "long_vote":     lv,
        "long_conf":     lc,
        "long_reasons":  lr,
        "overall_vote":  ov,
        "overall_conf":  oc,
    }
