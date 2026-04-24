"""T+ Trading Recommendation Engine (VN T+3 settlement, exit at T+2.5 ATC).

Classifies the current chart setup into one of 6 T+ opportunity types and
generates a complete actionable recommendation including entry zone, targets,
stop loss, session advice, and risk factors.

Setup types (T+0 entry → T+2.5 ATC exit plan):
  T_BREAKOUT          Price breaks above resistance with volume confirmation
  T_PULLBACK_EMA      Trend-continuation pullback to EMA9/21 support
  T_SUPPORT_BOUNCE    Bounce off SMA20/50 or BB-lower in uptrend context
  T_OVERSOLD_RECOVERY Oversold RSI + Stoch cross + MACD turning up
  T_RANGE_BREAK       BB squeeze unleashing + volume/ADX breakout signal
  T_MOMENTUM_CONT     Strong ADX trend continuation — riding the wave
  T_NO_SETUP          No clear T+ pattern detected
  T_AVOID             Active distribution, AMF BLOCK, or bear-regime context

Verdict:
  MUA_NGAY      — High-confidence entry, act on confirmed trigger
  CHO_XAC_NHAN  — Setup forming, wait for next-bar confirmation
  THEO_DOI      — Watch list; not yet actionable
  TRANH_XA      — Avoid; distribution / bear signal active
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.logging import get_logger

log = get_logger("t_plus_engine")

# ── Vietnamese labels ─────────────────────────────────────────────────────────

_SETUP_VI: dict[str, str] = {
    "T_BREAKOUT":           "Breakout vượt kháng cự – xung lượng cao",
    "T_PULLBACK_EMA":       "Hồi về EMA trong xu hướng tăng",
    "T_SUPPORT_BOUNCE":     "Bật lên từ vùng hỗ trợ SMA/BB",
    "T_OVERSOLD_RECOVERY":  "Hồi phục từ vùng quá bán",
    "T_RANGE_BREAK":        "Phá vỡ đi ngang – nén BB bứt phá",
    "T_MOMENTUM_CONT":      "Tiếp diễn xu hướng mạnh – sóng momentum",
    "T_NO_SETUP":           "Chưa có tín hiệu T+ rõ ràng",
    "T_AVOID":              "Tránh xa – cảnh báo phân phối / xu hướng giảm",
}

_VERDICT_VI: dict[str, str] = {
    "MUA_NGAY":      "✅ Thích hợp giải ngân T+",
    "CHO_XAC_NHAN":  "⏳ Chờ xác nhận nến/khối lượng",
    "THEO_DOI":      "👀 Theo dõi tín hiệu T+",
    "TRANH_XA":      "🚫 Không có điểm vào T+ an toàn",
}

_SESSION_VI: dict[str, str] = {
    "ATO_OPEN":  "ATO mở cửa (9:15) — chỉ dùng khi breakout qua đêm rõ ràng",
    "MORNING":   "Sáng (9:30–11:00) — cửa sổ tốt nhất cho T+",
    "MIDDAY":    "Giữa phiên (12:45–13:30) — cửa sổ T+2.5 settlement",
    "AFTERNOON": "Chiều (13:30–14:30) — vào trước ATC nếu xu hướng rõ",
    "AVOID_ATC": "Tránh vào ATC — giá ATC không có lợi cho T+",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _f(df: pd.DataFrame, col: str, offset: int = -1) -> float | None:
    try:
        if col not in df.columns:
            return None
        v = df[col].iloc[offset]
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


def _recent_resistance(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """Highest high over last `lookback` bars (excluding last bar)."""
    try:
        if "high" not in df.columns or len(df) < lookback + 1:
            return None
        return float(df["high"].iloc[-(lookback + 1):-1].max())
    except Exception:
        return None


def _recent_support(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """Lowest low over last `lookback` bars (excluding last bar)."""
    try:
        if "low" not in df.columns or len(df) < lookback + 1:
            return None
        return float(df["low"].iloc[-(lookback + 1):-1].min())
    except Exception:
        return None


def _round_price(price: float) -> float:
    """Round to nearest 100 VND (standard VN tick for most stocks)."""
    if price <= 0:
        return 0.0
    if price < 10_000:
        return round(price / 10) * 10
    if price < 50_000:
        return round(price / 50) * 50
    return round(price / 100) * 100


# ── Setup detectors (returns score 0-10, reasons list) ────────────────────────

def _score_breakout(df: pd.DataFrame) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    price    = _f(df, "close")
    rsi      = _f(df, "RSI14")
    adx      = _f(df, "ADX")
    di_plus  = _f(df, "DI_plus")
    di_minus = _f(df, "DI_minus")
    bb_upper = _f(df, "BB_upper")
    mh_arr   = _arr(df, "MACD_hist", 3)
    vol_arr  = _arr(df, "volume", 10)

    resistance = _recent_resistance(df, 20)

    # Price vs resistance breakout
    if price and resistance and price > resistance * 0.99:
        score += 3.0; reasons.append(f"Giá áp sát / vượt kháng cự {resistance:,.0f}")

    # Volume surge
    if len(vol_arr) >= 5:
        vol_now = vol_arr[-1]
        vol_avg = float(np.mean(vol_arr[:-1]))
        if vol_avg > 0:
            vr = vol_now / vol_avg
            if vr > 2.0:
                score += 3.0; reasons.append(f"Khối lượng bùng nổ {vr:.1f}× — xác nhận breakout")
            elif vr > 1.5:
                score += 1.5; reasons.append(f"Khối lượng tăng {vr:.1f}× — momentum tích cực")

    # BB upper breach
    if price and bb_upper and price >= bb_upper * 0.99:
        score += 1.5; reasons.append("Giá phá dải Bollinger trên")

    # RSI in healthy range for breakout
    if rsi is not None and 50 <= rsi <= 72:
        score += 1.5; reasons.append(f"RSI vùng breakout ({rsi:.0f})")
    elif rsi is not None and rsi > 75:
        score -= 1.0  # overbought at breakout = risky

    # MACD hist rising
    if len(mh_arr) >= 2 and mh_arr[-1] > mh_arr[-2]:
        score += 1.0; reasons.append("MACD_hist tăng — momentum xác nhận")

    # ADX strong and DI+ leading
    if adx is not None and adx > 25 and di_plus is not None and di_minus is not None and di_plus > di_minus:
        score += 1.0; reasons.append(f"ADX mạnh ({adx:.0f}), DI+ dẫn")

    return score, reasons


def _score_pullback_ema(df: pd.DataFrame) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    price   = _f(df, "close")
    ema9    = _f(df, "EMA9")
    ema21   = _f(df, "EMA21")
    sma50   = _f(df, "SMA50")
    sma200  = _f(df, "SMA200")
    rsi     = _f(df, "RSI14")
    obv_arr = _arr(df, "OBV", 10)
    mh_arr  = _arr(df, "MACD_hist", 3)

    # Price between EMA9 and EMA21 (pullback zone)
    if price and ema9 and ema21:
        in_ema_zone = ema21 * 0.995 <= price <= ema9 * 1.005
        touching_ema9 = abs(price - ema9) / ema9 < 0.012
        if in_ema_zone or touching_ema9:
            score += 3.0; reasons.append("Giá hồi về vùng EMA9-EMA21 — cơ hội bắt sóng")

    # EMA alignment bullish
    if ema9 and ema21 and sma50 and ema9 > ema21 > sma50:
        score += 2.0; reasons.append("EMA9 > EMA21 > SMA50 — xu hướng tăng vẫn nguyên")

    # Above SMA200 = uptrend
    if price and sma200 and price > sma200:
        score += 1.5; reasons.append("Giá trên SMA200 — xu hướng dài hạn tăng")

    # RSI cool-down (pullback confirmation)
    if rsi is not None and 40 <= rsi <= 60:
        score += 2.0; reasons.append(f"RSI hạ nhiệt ({rsi:.0f}) — hồi khoẻ mạnh")

    # OBV not falling (institutions not selling into pullback)
    if len(obv_arr) >= 5 and obv_arr[-1] >= obv_arr[-4] * 0.98:
        score += 1.5; reasons.append("OBV ổn định — không có bán tháo trong đợt hồi")

    # MACD hist: negative but improving (or still slightly positive)
    if len(mh_arr) >= 2:
        if -3 < mh_arr[-1] < 3 and mh_arr[-1] >= mh_arr[-2]:
            score += 1.0; reasons.append("MACD_hist hồi phục — lực bán suy yếu")

    return score, reasons


def _score_support_bounce(df: pd.DataFrame) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    price    = _f(df, "close")
    sma20    = _f(df, "SMA20")
    sma50    = _f(df, "SMA50")
    bb_lower = _f(df, "BB_lower")
    bb_mid   = _f(df, "BB_mid")
    rsi      = _f(df, "RSI14")
    mh_arr   = _arr(df, "MACD_hist", 4)
    rsi_arr  = _arr(df, "RSI14", 4)
    vol_arr  = _arr(df, "volume", 5)

    # Price at SMA20 support
    if price and sma20 and abs(price - sma20) / sma20 < 0.015:
        score += 3.0; reasons.append(f"Giá tại SMA20 ({sma20:,.0f}) — hỗ trợ quan trọng")

    # Price at SMA50 support
    if price and sma50 and abs(price - sma50) / sma50 < 0.015:
        score += 2.5; reasons.append(f"Giá tại SMA50 ({sma50:,.0f}) — hỗ trợ trung hạn")

    # Price at BB lower
    if price and bb_lower and price <= bb_lower * 1.01:
        score += 2.5; reasons.append("Giá tại dải BB dưới — vùng mua technical")

    # RSI in recovery zone
    if rsi is not None and 35 <= rsi <= 52:
        score += 1.5; reasons.append(f"RSI phục hồi từ vùng trung tính ({rsi:.0f})")
    elif rsi is not None and rsi < 35:
        score += 2.0; reasons.append(f"RSI vùng quá bán ({rsi:.0f}) — bật kỹ thuật")

    # MACD hist turning up
    if len(mh_arr) >= 3 and mh_arr[-1] > mh_arr[-2] and mh_arr[-2] <= mh_arr[-3]:
        score += 1.5; reasons.append("MACD_hist đang bẻ gãy đà giảm — tín hiệu đảo chiều")

    # RSI divergence (price lower but RSI higher)
    if len(rsi_arr) >= 3:
        price_arr_3 = _arr(df, "close", 3)
        if (len(price_arr_3) == 3
                and price_arr_3[-1] <= price_arr_3[0]
                and rsi_arr[-1] > rsi_arr[0] + 2):
            score += 2.0; reasons.append("Phân kỳ tăng RSI — áp lực bán suy yếu")

    # Volume drying up on pullback (good sign)
    if len(vol_arr) >= 4:
        vol_now = vol_arr[-1]
        vol_prev_avg = float(np.mean(vol_arr[:-1]))
        if vol_prev_avg > 0 and vol_now < vol_prev_avg * 0.75:
            score += 1.0; reasons.append("Khối lượng cạn dần — áp lực bán yếu")

    return score, reasons


def _score_oversold_recovery(df: pd.DataFrame) -> tuple[float, list[str]]:
    score, reasons = 0.0, []

    # [VN-FIX] Sustained selling pressure guard.
    # In VN, stocks under margin call or institutional exit continue falling
    # after oscillators show "oversold" — there is no institutional counter-buying.
    # Abort T_OVERSOLD_RECOVERY if price-direction volume ratio shows sustained sells.
    if len(df) >= 10:
        _delta = df["close"].diff().fillna(0)
        _buy_v  = df["volume"].where(_delta > 0, 0).tail(20).sum()
        _sell_v = df["volume"].where(_delta < 0, 0).tail(20).sum()
        _total  = _buy_v + _sell_v
        _pv_dir = (_buy_v - _sell_v) / max(_total, 1)
        if _pv_dir < -0.3:
            return 0.0, ["Áp lực bán dai dẳng — không vào T_OVERSOLD_RECOVERY trong TTCK VN"]

    rsi      = _f(df, "RSI14")
    stoch_k  = _f(df, "STOCH_K")
    stoch_d  = _f(df, "STOCH_D")
    wr       = _f(df, "WILLIAMS_R")
    cci      = _f(df, "CCI")
    mh_arr   = _arr(df, "MACD_hist", 4)
    vol_arr  = _arr(df, "volume", 5)
    stk_arr  = _arr(df, "STOCH_K", 3)
    std_arr  = _arr(df, "STOCH_D", 3)

    # [BUG-12 FIX] Use `is not None` guards throughout — truthiness skips valid
    # 0.0 values (e.g. rsi=0 impossible in practice, but wr=0 and cci=0 can occur).
    if rsi is not None and rsi < 30:
        score += 3.0; reasons.append(f"RSI quá bán sâu ({rsi:.0f}) — tỷ lệ bật kỹ thuật cao")
    elif rsi is not None and rsi < 40:
        score += 1.5; reasons.append(f"RSI vùng quá bán ({rsi:.0f})")

    # Stochastic cross in oversold zone
    if (len(stk_arr) >= 2 and len(std_arr) >= 2
            and stk_arr[-1] > std_arr[-1]
            and stk_arr[-2] < std_arr[-2]
            and stoch_k is not None and stoch_k < 30):
        score += 3.0; reasons.append(f"Stochastic golden cross vùng quá bán ({stoch_k:.0f}) — tín hiệu mạnh")

    # Williams %R recovering
    if wr is not None and -90 <= wr <= -60:
        score += 1.5; reasons.append(f"Williams %R phục hồi từ quá bán ({wr:.0f})")

    # CCI recovering
    if cci is not None and -150 <= cci <= -80:
        score += 1.0; reasons.append(f"CCI quá bán ({cci:.0f}) — đang phục hồi")

    # MACD hist turning up from negative
    if len(mh_arr) >= 3 and mh_arr[-1] > mh_arr[-2] and mh_arr[-2] < 0:
        score += 2.0; reasons.append("MACD_hist bẻ cong lên từ vùng âm — lực bán giảm")

    # Volume surge on recovery day
    if len(vol_arr) >= 3:
        vr = vol_arr[-1] / max(float(np.mean(vol_arr[:-1])), 1)
        if vr > 1.5:
            score += 1.5; reasons.append(f"Khối lượng tăng ngày phục hồi ({vr:.1f}×)")

    return score, reasons


def _score_range_break(df: pd.DataFrame) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    adx      = _f(df, "ADX")
    di_plus  = _f(df, "DI_plus")
    di_minus = _f(df, "DI_minus")
    vol_arr  = _arr(df, "volume", 10)
    price    = _f(df, "close")
    bb_upper = _f(df, "BB_upper")
    bb_lower = _f(df, "BB_lower")
    bb_mid   = _f(df, "BB_mid")
    adx_arr  = _arr(df, "ADX", 5)

    # BB squeeze detection
    bb_width_pct = None
    try:
        if "BB_upper" in df.columns and "BB_lower" in df.columns and "BB_mid" in df.columns:
            bw = (df["BB_upper"] - df["BB_lower"]) / df["BB_mid"].replace(0, 1)
            bw_clean = bw.dropna()
            if len(bw_clean) >= 20:
                bb_width_pct = float(bw_clean.iloc[-1] / bw_clean.tail(20).mean())
    except Exception:
        pass

    if bb_width_pct is not None and bb_width_pct < 0.75:
        score += 3.0; reasons.append(f"BB cực hẹp ({bb_width_pct:.0%} so với trung bình) — năng lượng tích tụ")

    # ADX starting to rise from low (<20)
    if adx is not None and len(adx_arr) >= 3:
        if adx < 25 and adx_arr[-1] > adx_arr[-3]:
            score += 2.0; reasons.append(f"ADX đang tăng từ vùng thấp ({adx:.0f}) — xu hướng hình thành")

    # DI cross (direction beginning to establish)
    if adx is not None and di_plus is not None and di_minus is not None:
        if di_plus > di_minus and adx > 15:
            score += 1.5; reasons.append("DI+ > DI- — hướng tăng đang chiếm ưu thế")

    # Volume breakout
    if len(vol_arr) >= 5:
        vol_now = vol_arr[-1]
        vol_prev = float(np.mean(vol_arr[:-1]))
        if vol_prev > 0 and vol_now > vol_prev * 1.8:
            score += 2.5; reasons.append(f"Khối lượng phá vỡ ({vol_now / vol_prev:.1f}×) — xác nhận bứt phá")

    # Price close to BB upper (approaching upper band from consolidation)
    if price and bb_upper and bb_lower and bb_mid:
        pos = (price - bb_lower) / max(bb_upper - bb_lower, 1)
        if pos > 0.75:
            score += 1.5; reasons.append("Giá áp BB trên sau nén — bắt đầu bứt phá")

    return score, reasons


def _score_momentum_cont(df: pd.DataFrame) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    price   = _f(df, "close")
    sma20   = _f(df, "SMA20")
    sma50   = _f(df, "SMA50")
    sma200  = _f(df, "SMA200")
    adx     = _f(df, "ADX")
    di_plus = _f(df, "DI_plus")
    di_minus= _f(df, "DI_minus")
    rsi     = _f(df, "RSI14")
    obv_arr = _arr(df, "OBV", 20)
    mh_arr  = _arr(df, "MACD_hist", 3)

    # Strong ADX trend
    if adx is not None and adx > 30 and di_plus is not None and di_minus is not None and di_plus > di_minus:
        score += 4.0; reasons.append(f"ADX rất mạnh ({adx:.0f}) — xu hướng tăng bền vững")
    elif adx is not None and adx > 25 and di_plus is not None and di_minus is not None and di_plus > di_minus:
        score += 2.5; reasons.append(f"ADX mạnh ({adx:.0f}) — xu hướng tăng ổn định")

    # Full MA alignment
    if sma20 and sma50 and sma200 and price:
        if price > sma20 > sma50 > sma200:
            score += 3.0; reasons.append("Giá > SMA20 > SMA50 > SMA200 — perfect alignment")
        elif price > sma20 > sma50:
            score += 1.5; reasons.append("Giá > SMA20 > SMA50 — xu hướng trung hạn tốt")

    # RSI in healthy trend zone
    if rsi is not None and 55 <= rsi <= 72:
        score += 1.5; reasons.append(f"RSI vùng momentum ({rsi:.0f}) — chưa quá mua")

    # OBV rising (institutional accumulation)
    if len(obv_arr) >= 10 and obv_arr[-1] > obv_arr[-10] * 1.01:
        score += 1.5; reasons.append("OBV tăng bền vững — tổ chức tiếp tục mua")

    # MACD hist positive and rising
    if len(mh_arr) >= 2 and mh_arr[-1] > 0 and mh_arr[-1] > mh_arr[-2]:
        score += 1.0; reasons.append("MACD_hist dương và tăng — momentum xác nhận")

    return score, reasons


# ── Avoid conditions ──────────────────────────────────────────────────────────

def _check_avoid(
    df: pd.DataFrame,
    dist_warning: str = "NONE",
    amf_decision: str = "PASS",
    amd_phase: str = "",
) -> tuple[bool, list[str]]:
    """Returns (should_avoid, risk_reasons)."""
    risks: list[str] = []
    should_avoid = False

    # Distribution warning
    if dist_warning in ("EXIT", "FORCED_EXIT"):
        risks.append(f"⚠️ Cảnh báo phân phối: {dist_warning} — tổ chức đang thoát")
        should_avoid = True

    # AMF block
    if amf_decision == "BLOCK":
        risks.append("🚫 AMF phát hiện thao túng giá — tránh giao dịch")
        should_avoid = True

    # AMD phase — don't buy in distribution/markdown
    if amd_phase in ("DISTRIBUTION", "MARKDOWN"):
        risks.append(f"📉 Giai đoạn Wyckoff: {amd_phase} — không thích hợp mua T+")
        should_avoid = True

    # RSI severely overbought — add risk warning but let other signals decide
    rsi = _f(df, "RSI14")
    if rsi is not None and rsi > 82:
        risks.append(f"RSI quá mua ({rsi:.0f}) — theo dõi áp lực chốt lời")

    # Price vs SMA200 — deep below SMA200 in bear context
    price  = _f(df, "close")
    sma200 = _f(df, "SMA200")
    sma50  = _f(df, "SMA50")
    adx    = _f(df, "ADX")
    di_minus = _f(df, "DI_minus")
    di_plus  = _f(df, "DI_plus")
    if (price and sma200 and price < sma200 * 0.92
            and adx and adx > 25
            and di_minus and di_plus and di_minus > di_plus):
        risks.append("Giá sâu dưới SMA200 trong xu hướng giảm mạnh — không thuận")
        if not should_avoid:
            should_avoid = True  # strong bear = avoid T+

    return should_avoid, risks


# ── Price-target computation ───────────────────────────────────────────────────

def _compute_targets(
    df: pd.DataFrame,
    entry: float,
    setup_type: str,
) -> tuple[float, float, float]:
    """
    Returns (t25_target, t5_target, stop_loss) for T+2.5 and T+5 exits.

    T+2.5 target  ~ 1.5–2.0 × ATR14 from entry
    T+5 target    ~ 2.5–3.5 × ATR14 from entry (longer run)
    Stop loss     ~ 1.0–1.2 × ATR14 below entry (tight for T+)
    """
    atr = _f(df, "ATR14")
    if not atr or not entry or entry <= 0:
        return 0.0, 0.0, 0.0

    # Momentum setups can extend more; support setups are conservative
    _multipliers = {
        "T_BREAKOUT":          (2.0, 3.5, 1.0),
        "T_PULLBACK_EMA":      (1.8, 3.0, 0.9),
        "T_SUPPORT_BOUNCE":    (1.6, 2.8, 1.0),
        "T_OVERSOLD_RECOVERY": (1.5, 2.5, 1.1),
        "T_RANGE_BREAK":       (2.0, 3.5, 0.8),
        "T_MOMENTUM_CONT":     (1.5, 2.5, 0.9),
    }
    m25, m5, msl = _multipliers.get(setup_type, (1.5, 2.5, 1.0))

    t25   = _round_price(entry + atr * m25)
    t5    = _round_price(entry + atr * m5)
    sl    = _round_price(entry - atr * msl)

    # SL floor: never below BB lower or recent support
    bb_lower = _f(df, "BB_lower")
    support  = _recent_support(df, 10)
    sl_floor_candidates = [v for v in [bb_lower, support] if v and v > 0]
    if sl_floor_candidates:
        sl = max(sl, min(sl_floor_candidates) * 0.995)

    return t25, t5, sl


def _entry_zone(df: pd.DataFrame, close: float, setup_type: str) -> tuple[float, float]:
    """Return ideal entry zone [low, high]."""
    atr = _f(df, "ATR14") or (close * 0.01)
    ema9 = _f(df, "EMA9")

    if setup_type == "T_PULLBACK_EMA" and ema9:
        low  = _round_price(min(ema9 * 0.995, close * 0.99))
        high = _round_price(max(ema9 * 1.005, close))
    elif setup_type in ("T_BREAKOUT", "T_RANGE_BREAK"):
        # Entry just above breakout trigger
        low  = _round_price(close)
        high = _round_price(close + atr * 0.3)
    else:
        low  = _round_price(close - atr * 0.2)
        high = _round_price(close + atr * 0.1)

    return low, high


def _session_advice(setup_type: str, t25_signal: str = "") -> str:
    """Recommend optimal entry session for T+ traders."""
    if setup_type in ("T_BREAKOUT", "T_RANGE_BREAK"):
        return "MORNING"   # chase breakout in morning strength
    if setup_type in ("T_PULLBACK_EMA", "T_SUPPORT_BOUNCE"):
        return "MORNING"   # confirm pullback holds in morning
    if setup_type == "T_OVERSOLD_RECOVERY":
        return "MIDDAY"    # wait for midday stabilization
    if setup_type == "T_MOMENTUM_CONT":
        return "MORNING"   # ride morning momentum wave
    return "AVOID_ATC"


def _entry_trigger_vi(setup_type: str, df: pd.DataFrame) -> str:
    """Return a specific Vietnamese trigger description."""
    close = _f(df, "close") or 0.0
    ema9  = _f(df, "EMA9")
    sma20 = _f(df, "SMA20")
    resistance = _recent_resistance(df, 20)
    atr   = _f(df, "ATR14") or (close * 0.01)

    if setup_type == "T_BREAKOUT" and resistance:
        return f"Mua khi giá xác nhận vượt {resistance:,.0f} với khối lượng > 1.5× trung bình"
    if setup_type == "T_PULLBACK_EMA" and ema9:
        return f"Mua khi giá chạm EMA9 ({ema9:,.0f}) và có nến xác nhận đảo chiều tăng"
    if setup_type == "T_SUPPORT_BOUNCE" and sma20:
        return f"Mua khi giá test SMA20 ({sma20:,.0f}) và nến đóng cửa trên SMA20"
    if setup_type == "T_OVERSOLD_RECOVERY":
        return "Mua khi Stochastic golden cross + giá đóng trên mức mở cửa phiên"
    if setup_type == "T_RANGE_BREAK":
        trigger = resistance or (close * 1.02)
        return f"Mua khi giá vượt {trigger:,.0f} kèm khối lượng đột biến > 2× trung bình"
    if setup_type == "T_MOMENTUM_CONT":
        return "Mua pullback nhỏ vào SMA20 hoặc khi giá hồi về EMA9 trong phiên sáng"
    return "Chưa xác định trigger rõ ràng — chờ thêm xác nhận"


# ── Public API ────────────────────────────────────────────────────────────────

def compute_tplus_recommendation(
    df: pd.DataFrame,
    t25_result: dict | None = None,
    pattern_result: dict | None = None,
    dist_warning: str = "NONE",
    amf_decision: str = "PASS",
    amd_phase: str = "",
) -> dict:
    """
    Generate a complete T+ trading recommendation.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV + indicators from compute_all().
    t25_result : dict, optional
        Output of compute_t25_entry_score().
    pattern_result : dict, optional
        Output of detect_patterns().
    dist_warning : str
        Distribution warning level from detect_whale_distribution().
    amf_decision : str
        AMF decision ("PASS" | "BLOCK" | "WATCH").
    amd_phase : str
        Wyckoff phase string.

    Returns
    -------
    dict with keys:
        setup_type      str
        setup_vi        str    Vietnamese setup name
        entry_trigger   str    Vietnamese trigger description
        entry_zone_low  float  entry zone lower bound (VND)
        entry_zone_high float  entry zone upper bound (VND)
        target_t25      float  T+2.5 price target (sell at ATC day 3)
        target_t5       float  T+5 extended target
        stop_loss       float
        expected_return_pct  float
        risk_pct        float
        rr_ratio        float
        session         str    recommended entry session key
        session_vi      str    Vietnamese session advice
        confidence      float  0–100
        reasons         list[str]
        risks           list[str]
        verdict         str
        verdict_vi      str
        t25_score_used  float  (pass-through from t25_result)
    """
    _empty = {
        "setup_type": "T_NO_SETUP", "setup_vi": _SETUP_VI["T_NO_SETUP"],
        "entry_trigger": "Chưa có setup", "entry_zone_low": 0.0, "entry_zone_high": 0.0,
        "target_t25": 0.0, "target_t5": 0.0, "stop_loss": 0.0,
        "expected_return_pct": 0.0, "risk_pct": 0.0, "rr_ratio": 0.0,
        "session": "AVOID_ATC", "session_vi": _SESSION_VI["AVOID_ATC"],
        "confidence": 0.0, "reasons": [], "risks": [],
        "verdict": "THEO_DOI", "verdict_vi": _VERDICT_VI["THEO_DOI"],
        "t25_score_used": 0.0,
    }

    if df is None or len(df) < 20:
        return _empty

    # ── 1. Check avoid conditions first ──────────────────────────────────────
    should_avoid, avoid_risks = _check_avoid(df, dist_warning, amf_decision, amd_phase)
    if should_avoid:
        result = _empty.copy()
        result.update({
            "setup_type": "T_AVOID",
            "setup_vi":   _SETUP_VI["T_AVOID"],
            "verdict":    "TRANH_XA",
            "verdict_vi": _VERDICT_VI["TRANH_XA"],
            "risks":      avoid_risks,
            "t25_score_used": float((t25_result or {}).get("t25_score") or 0.0),
        })
        return result

    # ── 2. Score each setup type ──────────────────────────────────────────────
    detectors = [
        ("T_BREAKOUT",          _score_breakout),
        ("T_PULLBACK_EMA",      _score_pullback_ema),
        ("T_SUPPORT_BOUNCE",    _score_support_bounce),
        ("T_OVERSOLD_RECOVERY", _score_oversold_recovery),
        ("T_RANGE_BREAK",       _score_range_break),
        ("T_MOMENTUM_CONT",     _score_momentum_cont),
    ]

    best_type = "T_NO_SETUP"
    best_score = 0.0
    best_reasons: list[str] = []

    all_risks: list[str] = avoid_risks.copy()
    all_scores: list[tuple[str, float]] = []

    for stype, fn in detectors:
        try:
            s, r = fn(df)
            all_scores.append((stype, s))
            if s > best_score:
                best_score = s
                best_type  = stype
                best_reasons = r
        except Exception as e:
            log.debug(f"T+ detector {stype} error: {e}")

    # ── 3. Apply T+2.5 score boost ────────────────────────────────────────────
    t25_score  = float((t25_result or {}).get("t25_score") or 0.0)
    t25_signal = str((t25_result or {}).get("t25_signal", ""))
    if t25_signal == "T25_BUY" and best_score > 3.0:
        best_score = min(10.0, best_score + 1.5)
        best_reasons.append(f"T+2.5 score xác nhận ({t25_score:.0f}/100)")
    elif t25_signal == "T25_AVOID":
        best_score = max(0.0, best_score - 2.0)

    # ── 4. Pattern bonus ──────────────────────────────────────────────────────
    if pattern_result:
        best_pat = pattern_result.get("best_pattern", "NONE")
        candle_pts = int(pattern_result.get("candle_pts", 0))
        if candle_pts > 0:
            best_score = min(10.0, best_score + 0.5 * candle_pts)
            best_reasons.append(f"Mô hình nến: {best_pat}")

    # ── 5. No-setup guard ─────────────────────────────────────────────────────
    if best_score < 3.0:
        result = _empty.copy()
        result["risks"] = all_risks
        return result

    # ── 6. Compute targets ────────────────────────────────────────────────────
    close = _f(df, "close") or 0.0
    target_t25, target_t5, stop_loss = _compute_targets(df, close, best_type)
    entry_low, entry_high = _entry_zone(df, close, best_type)

    if close <= 0 or stop_loss >= close:
        result = _empty.copy()
        result["risks"] = all_risks + ["Không xác định được mức stop hợp lệ"]
        return result

    expected_return = (target_t25 - close) / close * 100 if target_t25 > close else 0.0
    risk_pct        = (close - stop_loss) / close * 100 if stop_loss < close else 0.0
    rr_ratio        = round(expected_return / max(risk_pct, 0.1), 2)

    # ── 7. Confidence from score ──────────────────────────────────────────────
    confidence = min(95.0, best_score / 10.0 * 100)

    # ── 8. Verdict ────────────────────────────────────────────────────────────
    if best_score >= 7.5 and t25_signal in ("T25_BUY", "T25_WATCH"):
        verdict = "MUA_NGAY"
    elif best_score >= 5.5:
        verdict = "MUA_NGAY" if t25_signal == "T25_BUY" else "CHO_XAC_NHAN"
    elif best_score >= 3.0:
        verdict = "THEO_DOI"
    else:
        verdict = "THEO_DOI"

    # RR filter — if RR < 1.2 downgrade verdict
    if rr_ratio < 1.2 and verdict == "MUA_NGAY":
        verdict = "CHO_XAC_NHAN"
        all_risks.append(f"Tỷ lệ R:R {rr_ratio:.1f} chưa đạt 1.2 — chưa đủ điều kiện vào")

    # Distribution warning (soft) → add risk but don't escalate to AVOID
    if dist_warning in ("WATCH", "CAUTION"):
        all_risks.append(f"Cảnh báo phân phối nhẹ ({dist_warning}) — theo dõi khối lượng")

    session_key = _session_advice(best_type, t25_signal)
    trigger_vi  = _entry_trigger_vi(best_type, df)

    return {
        "setup_type":     best_type,
        "setup_vi":       _SETUP_VI.get(best_type, best_type),
        "entry_trigger":  trigger_vi,
        "entry_zone_low": entry_low,
        "entry_zone_high":entry_high,
        "target_t25":     target_t25,
        "target_t5":      target_t5,
        "stop_loss":      stop_loss,
        "expected_return_pct": round(expected_return, 2),
        "risk_pct":       round(risk_pct, 2),
        "rr_ratio":       rr_ratio,
        "session":        session_key,
        "session_vi":     _SESSION_VI.get(session_key, ""),
        "confidence":     round(confidence, 1),
        "reasons":        best_reasons[:6],
        "risks":          all_risks[:5],
        "verdict":        verdict,
        "verdict_vi":     _VERDICT_VI.get(verdict, ""),
        "t25_score_used": t25_score,
    }
