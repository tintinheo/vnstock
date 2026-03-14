"""
Captain Seventh Quant Terminal — Configuration
Edit this file to point to your portfolio folder and set preferences.
"""
import os
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────
# Folder where portfolio Excel files are stored.
# The app auto-detects the latest SSI iBoard export in this folder.
PORTFOLIO_DIR = Path.home() / "Documents" / "quant_terminal" / "portfolio"
TRADE_LOG_DIR = Path.home() / "Documents" / "quant_terminal" / "trade_log"
CACHE_DIR     = Path.home() / "Documents" / "quant_terminal" / ".cache"

# Create dirs if they don't exist
for d in [PORTFOLIO_DIR, TRADE_LOG_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── SSI API ──────────────────────────────────────────────────────────────────
# SSI iBoard credentials (optional — used only for real-time WebSocket feed)
# If not set, the app falls back to vnstock delayed data (still very useful)
SSI_USER     = os.getenv("SSI_USER", "")
SSI_PASSWORD = os.getenv("SSI_PASSWORD", "")
SSI_CLIENT_ID     = os.getenv("SSI_CLIENT_ID", "")
SSI_CLIENT_SECRET = os.getenv("SSI_CLIENT_SECRET", "")

# Primary data source: VCI | TCBS | KBS | MSN | FMP  (SSI is NOT supported by vnstock)
DATA_SOURCE = "VCI"

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
