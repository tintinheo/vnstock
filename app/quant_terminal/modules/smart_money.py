"""
Smart Money Detection Module — VSA (Wyckoff) + VN-MFI + BiLSTM Weekly Forecast.

Implements the "Smart Money Detection & Weekly Trading Strategy" proposal (March 2026).
All three subsystems are merged here and wired into Quant Terminal's analysis pipeline.

Design decisions vs original proposal:
  • VSA: 5 patterns (proposal had 2), all fully vectorized (proposal had O(n) loop)
  • MFI: vectorized (proposal had syntax error + for-loop)
  • BiLSTM: complete architecture (proposal had empty Sequential()); auto-trains on first run,
    saved to CACHE_DIR for reuse; gracefully falls back to heuristic if TF not installed.
  • "99% accuracy" claim NOT used — confidence % shown instead (that claim reflects overfitting).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

_log = logging.getLogger("smart_money")

# ── Optional TensorFlow / Keras ───────────────────────────────────────────────
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model  # type: ignore
    from tensorflow.keras.layers import LSTM, Dense, Bidirectional, Dropout  # type: ignore
    from tensorflow.keras.callbacks import EarlyStopping  # type: ignore
    _TF_AVAILABLE = True
except Exception:
    _TF_AVAILABLE = False

# ── Cache dir (CACHE_DIR from config, fallback to home) ───────────────────────
try:
    from config import CACHE_DIR as _CACHE_DIR_RAW  # type: ignore
    _CACHE_DIR = Path(_CACHE_DIR_RAW)
except Exception:
    _CACHE_DIR = Path.home() / ".quant_terminal_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── BiLSTM hyperparams ────────────────────────────────────────────────────────
_LOOKBACK_SEQ    = 20   # input sequence length (20 trading days ≈ 1 month)
_FORECAST_HORIZ  = 5    # predict 5-session forward direction
_FEATURE_COLS    = ["close_ret", "mfi_norm", "obv_norm", "vol_ratio", "atr_norm"]


# ══════════════════════════════════════════════════════════════════════════════
# A. VSA — VOLUME SPREAD ANALYSIS (Wyckoff)
# ══════════════════════════════════════════════════════════════════════════════

def detect_vsa_patterns(df: pd.DataFrame) -> dict:
    """
    Vectorized Wyckoff VSA pattern detection on OHLCV data.

    Detects 5 patterns on each bar:
      SPRING        — shakeout below support, closes back inside  (bullish +1)
      NO_SUPPLY     — narrow spread + low volume + weak close     (bullish +1)
      UPTHRUST      — false breakout above resistance             (bearish −1)
      BCLX          — buying climax at 20-bar high                (bearish −1)
      SCLX          — selling climax at 20-bar low                (bullish +1)

    Input columns: high, low, close, volume  (lowercase, prices in thousands-VND).

    Returns
    -------
    dict with keys:
      label       str  — primary pattern name on latest bar
      label_vi    str  — Vietnamese display name
      signal_dir  int  — +1 bullish | −1 bearish | 0 neutral
      detail      str  — plain-language explanation
      patterns_df DataFrame — full bar-level annotations
    """
    _EMPTY = {
        "label":       "NEUTRAL",
        "label_vi":    "Trung tính",
        "signal_dir":  0,
        "detail":      "Không đủ dữ liệu VSA.",
        "patterns_df": pd.DataFrame(),
    }
    if df is None or df.empty or len(df) < 30:
        return _EMPTY
    required = ("high", "low", "close", "volume")
    if not all(c in df.columns for c in required):
        return _EMPTY

    df = df.copy()
    c = pd.to_numeric(df["close"],  errors="coerce")
    h = pd.to_numeric(df["high"],   errors="coerce")
    l = pd.to_numeric(df["low"],    errors="coerce")
    v = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    o = pd.to_numeric(df.get("open", c), errors="coerce")

    spread     = (h - l).clip(lower=0)
    avg_spread = spread.rolling(20, min_periods=10).mean()
    avg_vol    = v.rolling(20, min_periods=10).mean().replace(0, 1.0)

    # 50-bar shifted extremes (must exclude current bar for a valid breakout test)
    support_50    = l.rolling(50, min_periods=20).min().shift(1)
    resistance_50 = h.rolling(50, min_periods=20).max().shift(1)
    high_20       = h.rolling(20, min_periods=10).max()
    low_20        = l.rolling(20, min_periods=10).min()

    # ── Pattern 1: SPRING ──────────────────────────────────────────────────────
    spring = (
        l.notna() & support_50.notna() &
        (l < support_50) &
        (c > support_50) &
        (v > avg_vol * 1.4)
    )

    # ── Pattern 2: NO SUPPLY TEST ─────────────────────────────────────────────
    no_supply = (
        avg_spread.notna() &
        (spread < avg_spread * 0.70) &
        (v < avg_vol * 0.80) &
        (c <= (l + spread * 0.50))
    )

    # ── Pattern 3: UPTHRUST ───────────────────────────────────────────────────
    upthrust = (
        h.notna() & resistance_50.notna() &
        (h > resistance_50) &
        (c < resistance_50 - spread * 0.30) &
        (v > avg_vol * 1.30)
    )

    # ── Pattern 4: BUYING CLIMAX (BCLX) ──────────────────────────────────────
    buying_climax = (
        avg_spread.notna() & high_20.notna() &
        (c > o) &
        (spread > avg_spread * 1.80) &
        (v > avg_vol * 2.00) &
        (h >= high_20 - spread * 0.10)
    )

    # ── Pattern 5: SELLING CLIMAX (SCLX) ─────────────────────────────────────
    selling_climax = (
        avg_spread.notna() & low_20.notna() &
        (c < o) &
        (spread > avg_spread * 1.80) &
        (v > avg_vol * 2.00) &
        (l <= low_20 + spread * 0.10)
    )

    df["vsa_spring"]         = spring.fillna(False)
    df["vsa_no_supply"]      = no_supply.fillna(False)
    df["vsa_upthrust"]       = upthrust.fillna(False)
    df["vsa_buying_climax"]  = buying_climax.fillna(False)
    df["vsa_selling_climax"] = selling_climax.fillna(False)

    # Priority order: Spring > Upthrust > BCLX > SCLX > No Supply > Neutral
    _labels_vi = {
        "SPRING":    "Spring (Shakeout)",
        "UPTHRUST":  "Upthrust (Bẫy tăng)",
        "BCLX":      "Buying Climax (Mua đỉnh)",
        "SCLX":      "Selling Climax (Bán đáy)",
        "NO_SUPPLY": "No Supply Test",
        "NEUTRAL":   "Trung tính",
    }
    _dir_map = {
        "SPRING": +1, "NO_SUPPLY": +1, "SCLX": +1,
        "UPTHRUST": -1, "BCLX": -1,
        "NEUTRAL": 0,
    }

    def _resolve(row):
        if row["vsa_spring"]:         return "SPRING"
        if row["vsa_upthrust"]:       return "UPTHRUST"
        if row["vsa_buying_climax"]:  return "BCLX"
        if row["vsa_selling_climax"]: return "SCLX"
        if row["vsa_no_supply"]:      return "NO_SUPPLY"
        return "NEUTRAL"

    _flag_cols = ["vsa_spring", "vsa_no_supply", "vsa_upthrust",
                  "vsa_buying_climax", "vsa_selling_climax"]
    df["vsa_label"]    = df[_flag_cols].apply(_resolve, axis=1)
    df["vsa_label_vi"] = df["vsa_label"].map(_labels_vi)
    df["vsa_dir"]      = df["vsa_label"].map(_dir_map).fillna(0).astype(int)

    last   = df.iloc[-1]
    lbl    = str(last["vsa_label"])
    lbl_vi = str(last["vsa_label_vi"])
    dirn   = int(last["vsa_dir"])

    _detail_map = {
        "SPRING":
            "Giá thủng hỗ trợ 50 phiên rồi hồi phục trên hỗ trợ + KL cao "
            "→ Shakeout Wyckoff, thường báo giai đoạn Markup sắp tới.",
        "NO_SUPPLY":
            "Biên độ hẹp + KL thấp + đóng cửa nửa dưới "
            "→ Cạn cung, xu hướng tăng có thể tiếp tục nếu không bứt phá.",
        "UPTHRUST":
            "Phá kháng cự 50 phiên nhưng không giữ được + KL cao "
            "→ Bẫy tăng Wyckoff, rủi ro đảo chiều giảm.",
        "BCLX":
            "Nến tăng rộng + KL cực cao tại đỉnh 20 phiên "
            "→ Tín hiệu phân phối, tay to đang xả hàng.",
        "SCLX":
            "Nến giảm rộng + KL cực cao tại đáy 20 phiên "
            "→ Bán hoảng loạn, thường tiệm cận vùng đáy ngắn hạn.",
        "NEUTRAL":
            "Không phát hiện mẫu hình VSA nổi bật trên nến mới nhất.",
    }

    return {
        "label":       lbl,
        "label_vi":    lbl_vi,
        "signal_dir":  dirn,
        "detail":      _detail_map.get(lbl, ""),
        "patterns_df": df,
    }


# ══════════════════════════════════════════════════════════════════════════════
# B. MONEY FLOW INDEX (VN-MFI)
# ══════════════════════════════════════════════════════════════════════════════

def compute_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Vectorized Money Flow Index (0–100).

    Fixes the proposal's two bugs:
      1. Missing initialisation  (positive_flow = / negative_flow =)
      2. O(n) for-loop          (replaced with .where() + .rolling().sum())

    Input columns: high, low, close, volume.
    Returns pd.Series aligned to df.index, NaN filled with 50 (neutral).
    """
    _empty = pd.Series(dtype=float, index=df.index if df is not None else None)
    if df is None or df.empty:
        return _empty
    if not all(c in df.columns for c in ("high", "low", "close", "volume")):
        return pd.Series(50.0, index=df.index)

    h  = pd.to_numeric(df["high"],   errors="coerce")
    l  = pd.to_numeric(df["low"],    errors="coerce")
    c  = pd.to_numeric(df["close"],  errors="coerce")
    v  = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    tp     = (h + l + c) / 3.0
    mf     = tp * v                                     # raw money flow
    up_mf  = mf.where(tp > tp.shift(1), 0.0)          # positive money flow
    dn_mf  = mf.where(tp <= tp.shift(1), 0.0)         # negative money flow

    min_p  = max(1, period // 2)
    pos    = up_mf.rolling(period, min_periods=min_p).sum()
    neg    = dn_mf.rolling(period, min_periods=min_p).sum()

    mfi    = 100.0 - (100.0 / (1.0 + pos / neg.replace(0, np.nan)))
    return mfi.fillna(50.0)


# ══════════════════════════════════════════════════════════════════════════════
# C. SMART MONEY INDEX (Composite)
# ══════════════════════════════════════════════════════════════════════════════

def compute_smart_money_index(df: pd.DataFrame, period: int = 14) -> dict:
    """
    Composite Smart Money Index score in range [−100, +100].

    Components and weights:
      MFI signal       ±25 pts
      VSA pattern      Spring: +30 | No Supply: +15 | SCLX: +20 | Upthrust: −30 | BCLX: −20
      OBV slope        ±10 pts  (10-bar linear regression slope, normalized)
      UV/DV vol ratio  ±10 pts  (last 5 bars up-volume vs down-volume)

    Returns
    -------
    dict: smi_score, smi_label, smi_color, mfi_latest, wyckoff_phase, components
    """
    _EMPTY = {
        "smi_score": 0, "smi_label": "N/A", "smi_color": "#6B7280",
        "mfi_latest": 50.0, "wyckoff_phase": "UNKNOWN", "components": {},
    }
    if df is None or df.empty or len(df) < 20:
        return _EMPTY

    score      = 0
    components: dict[str, tuple[str, int]] = {}

    # ── MFI signal ────────────────────────────────────────────────────────────
    mfi_series = compute_mfi(df, period)
    mfi_latest = float(mfi_series.iloc[-1]) if not mfi_series.empty else 50.0
    mfi_prev   = float(mfi_series.iloc[-2]) if len(mfi_series) >= 2 else mfi_latest

    if mfi_latest > 70:
        mfi_pts = +25 if mfi_latest >= mfi_prev else +12
        components["MFI"] = (f"Dòng tiền mạnh MFI={mfi_latest:.1f}", mfi_pts)
    elif mfi_latest > 55:
        mfi_pts = +10
        components["MFI"] = (f"MFI khá tốt {mfi_latest:.1f}", mfi_pts)
    elif mfi_latest < 30:
        mfi_pts = -25 if mfi_latest <= mfi_prev else -12
        components["MFI"] = (f"Dòng tiền yếu MFI={mfi_latest:.1f}", mfi_pts)
    elif mfi_latest < 45:
        mfi_pts = -10
        components["MFI"] = (f"MFI kém {mfi_latest:.1f}", mfi_pts)
    else:
        mfi_pts = 0
        components["MFI"] = (f"MFI trung tính {mfi_latest:.1f}", 0)
    score += mfi_pts

    # ── VSA pattern ───────────────────────────────────────────────────────────
    vsa = detect_vsa_patterns(df)
    _vsa_pts: dict[str, int] = {
        "SPRING":    +30,
        "NO_SUPPLY": +15,
        "SCLX":      +20,
        "UPTHRUST":  -30,
        "BCLX":      -20,
        "NEUTRAL":    0,
    }
    vsa_pts = _vsa_pts.get(vsa["label"], 0)
    score  += vsa_pts
    if vsa_pts != 0:
        components["VSA"] = (vsa["label_vi"], vsa_pts)

    # ── OBV 10-bar slope ──────────────────────────────────────────────────────
    try:
        v_arr  = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        c_arr  = pd.to_numeric(df["close"],  errors="coerce")
        obv    = (np.sign(c_arr.diff().fillna(0)) * v_arr).cumsum()
        obv_10 = obv.tail(10).values
        if len(obv_10) >= 5:
            slope     = float(np.polyfit(range(len(obv_10)), obv_10, 1)[0])
            norm_denom = float(np.abs(obv_10).mean()) or 1.0
            obv_pts   = int(np.clip(slope / norm_denom * 20, -10, 10))
            score    += obv_pts
            if abs(obv_pts) >= 3:
                lbl_obv = f"OBV slope {'↑' if obv_pts > 0 else '↓'}"
                components["OBV"] = (lbl_obv, obv_pts)
    except Exception:
        pass

    # ── Up-vol vs Down-vol ratio (5 bars) ────────────────────────────────────
    try:
        tail5 = df.tail(5)
        c5    = pd.to_numeric(tail5["close"],  errors="coerce")
        v5    = pd.to_numeric(tail5["volume"], errors="coerce").fillna(0)
        is_up = c5 >= c5.shift(1).fillna(c5)
        up_v  = v5[is_up].sum()
        dn_v  = v5[~is_up].sum()
        if dn_v > 0:
            ratio = up_v / dn_v
            if ratio > 1.6:
                uv_pts = +10; uv_lbl = f"UV/DV={ratio:.1f}× tích lũy"
            elif ratio > 1.2:
                uv_pts = +5;  uv_lbl = f"UV/DV={ratio:.1f}× khá tốt"
            elif ratio < 0.6:
                uv_pts = -10; uv_lbl = f"UV/DV={ratio:.1f}× xả hàng"
            elif ratio < 0.8:
                uv_pts = -5;  uv_lbl = f"UV/DV={ratio:.1f}× yếu"
            else:
                uv_pts = 0;   uv_lbl = ""
            score += uv_pts
            if uv_pts != 0:
                components["UV/DV"] = (uv_lbl, uv_pts)
    except Exception:
        pass

    # ── Clamp + label ─────────────────────────────────────────────────────────
    score = int(np.clip(score, -100, 100))
    if   score >= 50:  lbl = "Tích lũy mạnh"; col = "#15803D"
    elif score >= 20:  lbl = "Tích lũy";      col = "#16A34A"
    elif score >= 5:   lbl = "Hơi bullish";   col = "#86EFAC"
    elif score >= -5:  lbl = "Trung tính";    col = "#6B7280"
    elif score >= -20: lbl = "Hơi bearish";   col = "#FCA5A5"
    elif score >= -50: lbl = "Phân phối";     col = "#DC2626"
    else:              lbl = "Phân phối mạnh";col = "#7F1D1D"

    phase = detect_wyckoff_phase(df, _vsa_label=vsa["label"], _mfi=mfi_latest)
    return {
        "smi_score":     score,
        "smi_label":     lbl,
        "smi_color":     col,
        "mfi_latest":    round(mfi_latest, 1),
        "wyckoff_phase": phase["phase"],
        "components":    components,
    }


# ══════════════════════════════════════════════════════════════════════════════
# D. WYCKOFF PHASE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_wyckoff_phase(
    df: pd.DataFrame,
    _vsa_label: str = "",
    _mfi: float = 50.0,
) -> dict:
    """
    Classify the current Wyckoff market phase.

    Priority: VSA pattern overrides (SPRING / UPTHRUST) take precedence,
    then EMA alignment + OBV trend + MFI + price-range compression.

    Phases: ACCUMULATION | MARKUP | DISTRIBUTION | MARKDOWN |
            SPRING | UPTHRUST_PHASE | UNKNOWN
    """
    _EMPTY = {
        "phase": "UNKNOWN", "label_vi": "Không xác định",
        "color": "#6B7280", "direction": 0, "detail": "",
    }
    if df is None or df.empty or len(df) < 20:
        return _EMPTY
    if "close" not in df.columns:
        return _EMPTY

    c = pd.to_numeric(df["close"], errors="coerce").dropna()
    if len(c) < 10:
        return _EMPTY

    # VSA short-circuit
    if _vsa_label == "SPRING":
        return {
            "phase": "SPRING", "label_vi": "Spring — Rũ bỏ (Wyckoff)",
            "color": "#16A34A", "direction": +1,
            "detail": "Shakeout điển hình pha C Wyckoff — thường là điểm mua thuận lợi.",
        }
    if _vsa_label == "UPTHRUST":
        return {
            "phase": "UPTHRUST_PHASE", "label_vi": "Upthrust — Bẫy tăng (Wyckoff)",
            "color": "#DC2626", "direction": -1,
            "detail": "Phân phối pha B/C — giá không giữ kháng cự, áp lực bán mạnh.",
        }

    # EMA alignment
    ema20    = c.ewm(span=20, adjust=False).mean()
    ema50    = c.ewm(span=50, adjust=False).mean()
    last_c   = float(c.iloc[-1])
    last_e20 = float(ema20.iloc[-1])
    last_e50 = float(ema50.iloc[-1])

    # OBV slope (20 bars)
    obv_slope_sign = 0
    try:
        v_arr  = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        obv    = (np.sign(c.diff().fillna(0)) * v_arr).cumsum()
        obv_20 = obv.tail(20).values
        if len(obv_20) >= 5:
            obv_slope_sign = int(
                np.sign(np.polyfit(range(len(obv_20)), obv_20, 1)[0])
            )
    except Exception:
        pass

    # Price range compression (accumulation / distribution indicator)
    pr20 = float(c.tail(20).max() - c.tail(20).min())
    pr60 = float(c.tail(60).max() - c.tail(60).min()) if len(c) >= 60 else pr20 * 3.0
    is_compressed = pr20 < pr60 * 0.40 if pr60 > 0 else False

    # Phase logic
    if last_c > last_e20 > last_e50 and obv_slope_sign >= 0 and _mfi > 50:
        return {
            "phase": "MARKUP", "label_vi": "Markup — Xu hướng tăng",
            "color": "#16A34A", "direction": +1,
            "detail": "Giá trên EMA20 > EMA50, OBV tích cực, MFI > 50 — pha tăng Wyckoff.",
        }
    if last_c < last_e20 < last_e50 and obv_slope_sign <= 0 and _mfi < 50:
        return {
            "phase": "MARKDOWN", "label_vi": "Markdown — Xu hướng giảm",
            "color": "#DC2626", "direction": -1,
            "detail": "Giá dưới EMA20 < EMA50, OBV suy yếu, MFI < 50 — pha giảm Wyckoff.",
        }
    if is_compressed and obv_slope_sign >= 0 and _mfi < 60:
        return {
            "phase": "ACCUMULATION", "label_vi": "Tích lũy (Wyckoff)",
            "color": "#2563EB", "direction": +1,
            "detail": "Giá giao dịch trong vùng hẹp với OBV tăng — tay to đang gom hàng.",
        }
    if is_compressed and obv_slope_sign <= 0 and _mfi > 40:
        return {
            "phase": "DISTRIBUTION", "label_vi": "Phân phối (Wyckoff)",
            "color": "#F59E0B", "direction": -1,
            "detail": "Giá phân phối trong vùng hẹp với OBV giảm — tay to đang xả hàng.",
        }
    if last_c > last_e20:
        return {
            "phase": "MARKUP", "label_vi": "Markup — Trên EMA20",
            "color": "#86EFAC", "direction": +1,
            "detail": "Giá trên EMA20 — xu hướng ngắn hạn tích cực.",
        }
    if last_c < last_e20:
        return {
            "phase": "MARKDOWN", "label_vi": "Markdown — Dưới EMA20",
            "color": "#FCA5A5", "direction": -1,
            "detail": "Giá dưới EMA20 — xu hướng ngắn hạn tiêu cực.",
        }
    return _EMPTY


# ══════════════════════════════════════════════════════════════════════════════
# E. BiLSTM MODEL (auto-train on first run, save/load from CACHE_DIR)
# ══════════════════════════════════════════════════════════════════════════════

def _prepare_bilstm_features(df: pd.DataFrame) -> tuple:
    """
    Build (X, y) arrays for BiLSTM training/inference.

    5 normalized features  ×  20-bar lookback sequences.
    Target y: 1 if close[t + 5] > close[t] else 0  (5-session forward direction).

    Returns (X: ndarray (N, 20, 5), y: ndarray (N,)) or (None, None) if data too short.
    """
    if df is None or df.empty or len(df) < _LOOKBACK_SEQ + _FORECAST_HORIZ + 5:
        return None, None

    df = df.copy()
    c  = pd.to_numeric(df["close"],  errors="coerce")
    h  = pd.to_numeric(df["high"]   if "high"   in df.columns else c, errors="coerce")
    l  = pd.to_numeric(df["low"]    if "low"    in df.columns else c, errors="coerce")
    v  = pd.to_numeric(df["volume"] if "volume" in df.columns
                       else pd.Series(np.ones(len(df)), index=df.index), errors="coerce").fillna(0)

    # Feature 1: daily return (clipped to ±10%)
    df["close_ret"] = c.pct_change().fillna(0).clip(-0.10, 0.10)

    # Feature 2: MFI normalised to [0, 1]
    df["mfi_norm"]  = compute_mfi(df).fillna(50.0) / 100.0

    # Feature 3: OBV normalised by rolling std
    obv              = (np.sign(c.diff().fillna(0)) * v).cumsum()
    obv_std          = obv.rolling(20).std().replace(0, 1.0).fillna(1.0)
    df["obv_norm"]   = (obv / obv_std).clip(-3, 3).fillna(0) / 3.0

    # Feature 4: volume ratio vs 20-day average
    vol_ma           = v.rolling(20).mean().replace(0, 1.0).fillna(1.0)
    df["vol_ratio"]  = (v / vol_ma).fillna(1.0).clip(0, 5) / 5.0

    # Feature 5: ATR normalised by price
    prev_c           = c.shift(1)
    tr               = pd.concat(
        [h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1
    ).max(axis=1)
    atr              = tr.ewm(com=13, adjust=False).mean()
    df["atr_norm"]   = (atr / c.replace(0, np.nan)).clip(0, 0.10).fillna(0) / 0.10

    df = df.dropna(subset=_FEATURE_COLS)
    if len(df) < _LOOKBACK_SEQ + _FORECAST_HORIZ:
        return None, None

    feats  = df[_FEATURE_COLS].values.astype(np.float32)
    closes = pd.to_numeric(df["close"], errors="coerce").values

    X_list, y_list = [], []
    for i in range(_LOOKBACK_SEQ, len(feats) - _FORECAST_HORIZ):
        X_list.append(feats[i - _LOOKBACK_SEQ: i])
        y_list.append(1 if closes[i + _FORECAST_HORIZ] > closes[i] else 0)

    if not X_list:
        return None, None
    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float32),
    )


def build_bilstm_model(input_shape: tuple):
    """
    Build the BiLSTM model for weekly direction prediction.

    Fixes the proposal's empty Sequential() — adds all layers and compiles.
    Returns a compiled Keras model, or None if TensorFlow is not installed.
    """
    if not _TF_AVAILABLE:
        _log.warning("TensorFlow not available — BiLSTM model cannot be built.")
        return None
    model = Sequential([
        Bidirectional(LSTM(64, return_sequences=True), input_shape=input_shape),
        Dropout(0.20),
        Bidirectional(LSTM(32)),
        Dropout(0.20),
        Dense(16, activation="relu"),
        Dense(1,  activation="sigmoid"),
    ])
    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model


def get_or_train_bilstm(symbol: str, df: pd.DataFrame):
    """
    Return a trained BiLSTM model for the given symbol.

    On first call: trains from scratch and saves to CACHE_DIR/bilstm_{symbol}.keras.
    Subsequent calls: loads the saved model from disk (fast).
    Returns None if TF unavailable or insufficient training data.
    """
    if not _TF_AVAILABLE:
        return None

    model_path = _CACHE_DIR / f"bilstm_{symbol.upper()}.keras"

    # Try loading a previously saved model
    if model_path.exists():
        try:
            return load_model(str(model_path))
        except Exception as e:
            _log.warning("Cannot load saved BiLSTM for %s: %s — retraining.", symbol, e)
            model_path.unlink(missing_ok=True)

    # Prepare training data
    X, y = _prepare_bilstm_features(df)
    if X is None or len(X) < 50:
        _log.info(
            "Insufficient data to train BiLSTM for %s (%d samples).",
            symbol, 0 if X is None else len(X),
        )
        return None

    model = build_bilstm_model(input_shape=(X.shape[1], X.shape[2]))
    if model is None:
        return None

    # 80/20 chronological train/val split
    n_train = int(len(X) * 0.80)
    X_tr, X_val = X[:n_train], X[n_train:]
    y_tr, y_val = y[:n_train], y[n_train:]

    cb = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
    try:
        model.fit(
            X_tr, y_tr,
            validation_data=(X_val, y_val),
            epochs=30,
            batch_size=16,
            callbacks=[cb],
            verbose=0,
        )
        model.save(str(model_path))
        _log.info("BiLSTM trained and saved for %s.", symbol)
    except Exception as e:
        _log.warning("BiLSTM training failed for %s: %s", symbol, e)
        return None

    return model


# ══════════════════════════════════════════════════════════════════════════════
# F. WEEKLY DIRECTION FORECAST
# ══════════════════════════════════════════════════════════════════════════════

def forecast_weekly_direction(
    df: pd.DataFrame,
    signal_score: int = 0,
    symbol: str = "",
) -> dict:
    """
    Forecast next-week price direction using a 4-factor heuristic blended
    with an optional BiLSTM model (when TF is installed and model is trained).

    Heuristic weights
    -----------------
      40%  Wyckoff phase direction
      30%  Smart Money Index (SMI score)
      20%  Technical signal score (RSI / MACD / EMA composite)
      10%  5-bar close momentum

    When BiLSTM is available the final output is an additional blend:
      60% heuristic + 40% BiLSTM sigmoid probability.

    Returns
    -------
    dict with keys:
      direction       str   — BULLISH | BEARISH | NEUTRAL
      confidence_pct  int   — 0–100
      target_pct      float — estimated upside move (ATR-based)
      stop_pct        float — suggested stop loss (− ATR-based)
      bilstm_prob     float | None
      bilstm_status   str   — ACTIVE | TRAINING | FALLBACK | UNAVAILABLE
      rationale       list[str]
    """
    _EMPTY = {
        "direction":     "NEUTRAL",
        "confidence_pct": 0,
        "target_pct":     0.0,
        "stop_pct":      -2.0,
        "bilstm_prob":    None,
        "bilstm_status":  "UNAVAILABLE",
        "rationale":      ["Không đủ dữ liệu dự báo."],
    }
    if df is None or df.empty or len(df) < 20:
        return _EMPTY

    c = pd.to_numeric(df["close"], errors="coerce").dropna()
    if len(c) < 10:
        return _EMPTY

    rationale: list[str] = []
    raw_score = 0.0   # range −1 .. +1

    # ── Weight 1 (40%): Wyckoff phase ─────────────────────────────────────────
    mfi_s  = compute_mfi(df)
    mfi_v  = float(mfi_s.iloc[-1]) if not mfi_s.empty else 50.0
    vsa_r  = detect_vsa_patterns(df)
    phase  = detect_wyckoff_phase(df, _vsa_label=vsa_r["label"], _mfi=mfi_v)
    raw_score += phase["direction"] * 0.40
    if phase["direction"] != 0:
        sign = "+" if phase["direction"] > 0 else ""
        rationale.append(
            f"Pha Wyckoff: **{phase['label_vi']}** ({sign}{phase['direction']*40:.0f}%)"
        )

    # ── Weight 2 (30%): SMI score ─────────────────────────────────────────────
    smi_r  = compute_smart_money_index(df)
    smi_n  = smi_r["smi_score"] / 100.0
    raw_score += smi_n * 0.30
    if abs(smi_r["smi_score"]) > 10:
        rationale.append(
            f"Smart Money Index: **{smi_r['smi_score']:+d}** → {smi_r['smi_label']}"
        )

    # ── Weight 3 (20%): Technical signal score ────────────────────────────────
    sig_n  = (signal_score / 100.0) * 0.20
    raw_score += sig_n
    if abs(signal_score) > 15:
        label_dir = "tích cực" if signal_score > 0 else "tiêu cực"
        rationale.append(f"Kỹ thuật tổng hợp: **{signal_score:+d}** ({label_dir})")

    # ── Weight 4 (10%): 5-bar momentum ────────────────────────────────────────
    if len(c) >= 6:
        mom = float(c.iloc[-1] / c.iloc[-6] - 1)
        mom_n = float(np.clip(mom / 0.05, -1.0, 1.0)) * 0.10
        raw_score += mom_n
        if abs(mom) > 0.01:
            rationale.append(f"Momentum 5 phiên: **{mom * 100:+.2f}%**")

    # ── BiLSTM inference (optional — blends 60/40 with heuristic) ─────────────
    bilstm_prob   = None
    bilstm_status = "UNAVAILABLE"

    if _TF_AVAILABLE and symbol:
        bilstm_status = "TRAINING"   # default while attempting
        try:
            model = get_or_train_bilstm(symbol, df)
            if model is not None:
                X, _ = _prepare_bilstm_features(df)
                if X is not None and len(X) > 0:
                    x_latest    = X[-1:].reshape(1, _LOOKBACK_SEQ, len(_FEATURE_COLS))
                    bilstm_prob = float(model.predict(x_latest, verbose=0)[0][0])
                    bilstm_status = "ACTIVE"
                    bilstm_n    = (bilstm_prob - 0.5) * 2.0   # [0,1] → [−1,+1]
                    raw_score   = raw_score * 0.60 + bilstm_n * 0.40
                    conf_s      = f"{bilstm_prob * 100:.0f}%"
                    sign_s      = "BUY" if bilstm_n > 0 else "SELL"
                    rationale.append(
                        f"BiLSTM ({sign_s}): xác suất tăng **{conf_s}** (trọng số 40%)"
                    )
            else:
                bilstm_status = "FALLBACK"
        except Exception as e:
            _log.warning("BiLSTM inference error for %s: %s", symbol, e)
            bilstm_status = "FALLBACK"
    elif _TF_AVAILABLE:
        bilstm_status = "TRAINING"

    # ── Map raw_score → direction + confidence ────────────────────────────────
    raw_score      = float(np.clip(raw_score, -1.0, 1.0))
    confidence_pct = int(abs(raw_score) * 100)

    if   raw_score >= 0.15:  direction = "BULLISH"
    elif raw_score <= -0.15: direction = "BEARISH"
    else:                    direction = "NEUTRAL"

    # ── ATR-based target / stop estimate ─────────────────────────────────────
    target_pct = 3.0 if direction != "BEARISH" else -3.0
    stop_pct   = -2.0
    try:
        h_arr  = pd.to_numeric(df.get("high",  df["close"]), errors="coerce")
        l_arr  = pd.to_numeric(df.get("low",   df["close"]), errors="coerce")
        prev_c = c.shift(1)
        tr     = pd.concat(
            [h_arr - l_arr, (h_arr - prev_c).abs(), (l_arr - prev_c).abs()], axis=1
        ).max(axis=1)
        atr      = float(tr.ewm(com=13, adjust=False).mean().iloc[-1])
        price    = float(c.iloc[-1])
        atr_pct  = atr / price * 100 if price > 0 else 2.0
        target_pct = round(atr_pct * 2.5 * (1 if direction != "BEARISH" else -1), 2)
        stop_pct   = round(-atr_pct * 1.2, 2)
    except Exception:
        pass

    if not rationale:
        rationale.append("Tín hiệu hỗn hợp — không có phán đoán rõ ràng.")

    return {
        "direction":      direction,
        "confidence_pct": confidence_pct,
        "target_pct":     target_pct,
        "stop_pct":       stop_pct,
        "bilstm_prob":    bilstm_prob,
        "bilstm_status":  bilstm_status,
        "rationale":      rationale,
    }
