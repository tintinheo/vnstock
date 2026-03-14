"""
Captain Seventh Quant Terminal — Configuration
Edit this file to point to your portfolio folder and set preferences.
"""
import os
import datetime as dt
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────
# Folder where portfolio Excel files are stored.
# The app auto-detects the latest SSI iBoard export in this folder.
PORTFOLIO_DIR = Path.home() / "Documents" / "quant_terminal" / "portfolio"
TRADE_LOG_DIR = Path.home() / "Documents" / "quant_terminal" / "trade_log"
CACHE_DIR      = Path.home() / "Documents" / "quant_terminal" / ".cache"
ERROR_LOG_FILE = Path.home() / "Documents" / "quant_terminal" / "ERROR_LOG.txt"

# Create dirs if they don't exist
for d in [PORTFOLIO_DIR, TRADE_LOG_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── SSI API ──────────────────────────────────────────────────────────────────
# SSI iBoard credentials (optional — used only for real-time WebSocket feed)
# SSI iBoard is the sole data source for all real-time and historical data.
SSI_USER     = os.getenv("SSI_USER", "")
SSI_PASSWORD = os.getenv("SSI_PASSWORD", "")
SSI_CLIENT_ID     = os.getenv("SSI_CLIENT_ID", "")
SSI_CLIENT_SECRET = os.getenv("SSI_CLIENT_SECRET", "")

# ─── TRADING PARAMETERS ───────────────────────────────────────────────────────
HOSE_TICK           = 0.05         # Minimum price step on HOSE in thousands-VND (= 50 VND raw)
MAX_RISK_PER_TRADE  = 0.02         # 2% portfolio at risk per trade
PRICE_BAND          = 0.07         # ±7% daily price band on HOSE
SETTLEMENT_DAYS     = 2            # T+2 settlement

# ─── REFRESH ──────────────────────────────────────────────────────────────────
PRICE_REFRESH_SECONDS = 30         # How often to refresh live prices
SIGNAL_REFRESH_SECONDS = 300       # How often to recompute technical signals

# ─── UNIVERSE ─────────────────────────────────────────────────────────────────
# These stocks get pre-loaded in Market Overview even if not in portfolio
WATCHLIST_DEFAULT = [
    "VNINDEX", "VN30",
    "HPG", "VIC", "VHM", "FPT", "VCB", "TCB", "MBB", "ACB",
    "GAS", "SAB", "PLX", "POW", "PVD",
]

# ─── UI ───────────────────────────────────────────────────────────────────────
APP_TITLE   = "Captain Seventh Quant Terminal"
APP_ICON    = "📊"
THEME_COLOR = "#1A3A5C"

# ─── SCENARIO DEFAULTS ────────────────────────────────────────────────────────
SCENARIO_PROBABILITIES = {"bull": 0.30, "base": 0.45, "bear": 0.25}

# Analyst consensus source — used for target price in Stock Analysis
# Options: "SSI" | "VCSC" | "manual"
ANALYST_SOURCE = "SSI"

# ─── KELLY CRITERION ──────────────────────────────────────────────────────────
KELLY_FRACTION = 0.25   # Use 1/4 Kelly for safety (reduces variance)
MAX_POSITION_PCT = 0.20  # No single position > 20% of portfolio

# ─── VERSION ──────────────────────────────────────────────────────────────────
APP_VERSION  = "2.0.2"
RELEASE_DATE = "2026-03-14"

# ─── CATALYST CALENDAR ───────────────────────────────────────────────────────
# Static per-symbol upcoming events — edit here to update the UI.
# Format: {SYMBOL: [{"date":"DD/MM/YYYY", "event":str, "type":str}]}
CATALYST_CALENDAR: dict = {
    "HPG": [
        {"date": "01/04/2026", "event": "Công bố KQKD Q1/2026",      "type": "Earnings"},
        {"date": "25/04/2026", "event": "ĐHCĐ thường niên 2026",       "type": "AGM"},
    ],
    "FPT": [
        {"date": "10/04/2026", "event": "KQKD Q1/2026 dự kiến",        "type": "Earnings"},
        {"date": "22/04/2026", "event": "ĐHCĐ thường niên 2026",        "type": "AGM"},
    ],
    "VCB": [
        {"date": "20/04/2026", "event": "KQKD Q1 & cổ tức dự kiến",     "type": "Dividend"},
    ],
    "TCB": [
        {"date": "15/04/2026", "event": "Công bố KQKD Q1/2026",         "type": "Earnings"},
    ],
    "MBB": [
        {"date": "18/04/2026", "event": "KQKD Q1/2026",                  "type": "Earnings"},
    ],
}


# ─── VN MARKET RULES ─────────────────────────────────────────────────────────

def hose_tick(price_thousands: float) -> float:
    """Tiered HOSE tick in thousands-VND.  <10→10VND, 10-50→50VND, ≥50→100VND"""
    if price_thousands < 10.0:
        return 0.01
    if price_thousands < 50.0:
        return 0.05
    return 0.10


def round_price_exchange(price: float, exchange: str = "HOSE") -> float:
    """
    Round price to minimum tick for the given exchange (H-02 fix).
    HOSE: tiered 10/50/100 VND ticks.
    HNX / UPCOM: 100 VND flat tick.
    price is in thousands-VND.
    """
    exchange = exchange.upper()
    if exchange in ("HNX", "UPCOM"):
        tick = 0.1   # 100 VND flat
    else:
        tick = hose_tick(price)
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 3)


# Preserved alias for backward compatibility
def round_price_hose(price: float) -> float:
    return round_price_exchange(price, "HOSE")


PRICE_BAND_BY_EXCHANGE = {"HOSE": 0.07, "HNX": 0.10, "UPCOM": 0.15}

SSI_MIN_BROKERAGE    = 17        # thousands-VND (= 17,000 VND minimum per order at SSI)
SELL_TAX_RATE        = 0.001     # 0.1% withholding tax on gross sell value
BUY_COMMISSION_RATE  = 0.0015    # 0.15% SSI online buy commission (H-10)


def compute_true_breakeven(avg_cost: float) -> float:
    """
    True break-even sell price including 0.1% sell tax (H-10 fix).
    SSI's 'Giá vốn bình quân' already includes buy-side commission.
    Sell break-even = avg_cost / (1 - SELL_TAX_RATE).
    Price in thousands-VND.
    """
    if avg_cost <= 0:
        return 0.0
    return round(avg_cost / (1.0 - SELL_TAX_RATE), 3)


# Graham Number multiplier calibrated for Vietnam market 2024-2026 (C-05)
# P/E ~13× × P/B ~1.75× = 22.75 ≈ 22.5 — coincidentally close to Graham's original
# NOTE: Graham's original formula was designed for US markets circa 1960s.
# Review when market P/E or P/B regime changes significantly.
VN_GRAHAM_MULTIPLIER = 22.5


# VN public holidays 2025–2027 (source: MoLISA official decrees)
VN_PUBLIC_HOLIDAYS: set = {
    # 2025 — Tết Ất Tỵ + statutory
    dt.date(2025, 1, 1),
    dt.date(2025, 1, 27), dt.date(2025, 1, 28), dt.date(2025, 1, 29),
    dt.date(2025, 1, 30), dt.date(2025, 1, 31),
    dt.date(2025, 4, 7),
    dt.date(2025, 4, 30), dt.date(2025, 5, 1),
    dt.date(2025, 9, 2),
    # 2026 — Tết Bính Ngọ + statutory
    dt.date(2026, 1, 1),
    dt.date(2026, 2, 16), dt.date(2026, 2, 17), dt.date(2026, 2, 18),
    dt.date(2026, 2, 19), dt.date(2026, 2, 20),
    dt.date(2026, 4, 27),   # Giỗ Tổ Hùng Vương 2026 (đúng ngày 10/3 âm lịch Bính Ngọ)
    dt.date(2026, 4, 30), dt.date(2026, 5, 1),
    dt.date(2026, 9, 2),
    # 2027 — Tết Đinh Mùi + statutory
    dt.date(2027, 1, 1),
    dt.date(2027, 2, 5), dt.date(2027, 2, 6), dt.date(2027, 2, 7),
    dt.date(2027, 2, 8), dt.date(2027, 2, 9),
    dt.date(2027, 4, 19),
    dt.date(2027, 4, 30), dt.date(2027, 5, 1),
    dt.date(2027, 9, 2),
}


def compute_price_limits(ref_price: float, exchange: str = "HOSE") -> tuple:
    """Return (ceiling, floor) for ref_price (thousands-VND) on given exchange."""
    band = PRICE_BAND_BY_EXCHANGE.get(exchange.upper(), 0.07)
    exch = exchange.upper()
    if exch in ("HNX", "UPCOM"):
        tick = 0.1
    else:
        tick = hose_tick(ref_price)
    ceil_p  = round(round(ref_price * (1 + band) / tick) * tick, 2)
    floor_p = round(round(ref_price * (1 - band) / tick) * tick, 2)
    return ceil_p, floor_p


MACRO_EVENTS = [
    ("18/03/2026", "HPG",     "Công bố KQKD Q4/2025",                    "🔴 Catalyst cao"),
    ("18/03/2026", "FED",     "FOMC Minutes — định hướng lãi suất",       "🟡 Macro"),
    ("31/03/2026", "BCTC",    "Deadline nộp BCTC kiểm toán 2025",         "🔵 Toàn thị trường"),
    ("Hàng ngày",  "Dầu thô", "WTI Crude Oil — ảnh hưởng HVN, POW, PVD", "🟡 Macro"),
]
