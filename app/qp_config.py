"""
qp_config.py — Quant Profiler configuration constants.
Edit this file to tune screening thresholds without touching logic.

Vietnam market calibration notes
─────────────────────────────────
• CANSLIM EPS / ROE thresholds are *lower* than the US originals because:
  - Only ~15-20 VN stocks sustain EPS growth ≥ 25 % consistently
  - Semi-annual reporting creates 6-month data lags
• PIVOT_BARS=50 daily bars ≈ 10 trading weeks (O'Neil: 7-65 week bases)
• VOL_CONFIRM_X=1.4 matches observed HOSE breakout volume characteristics
"""

# ── CANSLIM thresholds (VN-adjusted) ─────────────────────────────────────────
CANSLIM_EPS_GROWTH_MIN  : float = 0.15   # min YoY EPS growth (US orig: 0.25)
CANSLIM_ROE_MIN         : float = 0.12   # min ROE fraction   (US orig: 0.17)
CANSLIM_PIVOT_BARS      : int   = 50     # bars for pivot lookback (~10 weeks daily)
CANSLIM_VOL_CONFIRM_X   : float = 1.4   # breakout volume multiplier vs 50-bar avg

# ── Manipulation / pump-dump detection ───────────────────────────────────────
MANIP_VOL_ZSCORE_THRESH : float = 3.0   # volume Z-score for pump flag
MANIP_REVERSAL_BARS     : int   = 2     # sessions within which reversal = dump signal

# ── VWAP divergence ───────────────────────────────────────────────────────────
VWAP_DIV_SWING_WINDOW   : int   = 5     # half-window for swing-pivot detection (bars)
VWAP_INTRADAY_RESOLUTION: str   = "5"  # SSI chart resolution for intraday VWAP

# ── T+2.5 window (Vietnam, local ICT = UTC+7) ─────────────────────────────────
# The critical 13:00 session: T+0 asset release creates predictable volatility.
T25_WINDOW_START        : tuple = (12, 45)   # 12:45 local
T25_WINDOW_END          : tuple = (13, 15)   # 13:15 local
