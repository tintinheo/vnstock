"""
config.py — NewTradingOS v14.0
All constants, universe definitions, timeframe configurations.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────
# TRADING COSTS (VN-specific, T+2 settlement)
# ─────────────────────────────────────────────────────────────
BUY_FEE      = 0.0015   # 0.15% broker fee (SSI/DNSE standard)
SELL_FEE     = 0.0015
SELL_TAX     = 0.001    # 0.1% securities transfer tax
SLIPPAGE     = 0.0005   # 0.05% slippage estimate
BUY_TOTAL    = BUY_FEE  + SLIPPAGE
SELL_TOTAL   = SELL_FEE + SELL_TAX + SLIPPAGE

INITIAL_CAPITAL  = 100_000_000   # 100M VND default
LOT_SIZE         = 100           # Minimum lot size VN
VN_SESSIONS_YEAR = 240           # ~240 trading sessions/year

# ─────────────────────────────────────────────────────────────
# API CONSTANTS
# ─────────────────────────────────────────────────────────────
API_TIMEOUT  = 12   # seconds
CACHE_TTL    = 300  # seconds (5-minute cache for price data)

DNSE_URL  = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
SSI_URL   = "https://iboard-query.ssi.com.vn/v2/stock/ohlc"
CAFEF_URL = "https://s.cafef.vn/ajax/historyprice.aspx"
VND_BASE  = "https://finfo-api.vndirect.com.vn/v4"
TCBS_BASE = "https://analysis.tcbs.com.vn/api/v1/stock"

# World markets via Yahoo Finance chart API
WORLD_SYMBOLS = {
    "Gold (XAU/USD)":  "GC=F",
    "WTI Oil":         "CL=F",
    "Natural Gas":     "NG=F",
    "DXY (USD Index)": "DX-Y.NYB",
    "S&P 500":         "^GSPC",
    "VIX":             "^VIX",
    "CSI 300 (CN)":    "000300.SS",
    "Nikkei 225":      "^N225",
}

# ─────────────────────────────────────────────────────────────
# EXCHANGE MAP  (tickers NOT on HOSE → explicit routing)
# ─────────────────────────────────────────────────────────────
TICKER_EXCHANGE: dict[str, str] = {
    # HNX
    "PVS":"HNX","TNG":"HNX","VNA":"HNX","SHB":"HNX","ACB":"HNX",
    "NVB":"HNX","BVS":"HNX","MBS":"HNX","VCS":"HNX","PVI":"HNX",
    "CEO":"HNX","HHC":"HNX","VGS":"HNX","SCI":"HNX","NTP":"HNX",
    "PGC":"HNX","BCC":"HNX","VKC":"HNX","TVN":"HNX","SCG":"HNX",
    # UPCOM
    "IDC":"UPCOM","OIL":"UPCOM","ACV":"UPCOM","BSR":"UPCOM",
    "VGT":"UPCOM","MCH":"UPCOM","GVR":"UPCOM","VEA":"UPCOM",
    "BCM":"UPCOM","MML":"UPCOM","QNS":"UPCOM","HBC":"UPCOM",
    "PME":"UPCOM","LTG":"UPCOM","DVN":"UPCOM",
}

# ─────────────────────────────────────────────────────────────
# SECTOR MAP
# ─────────────────────────────────────────────────────────────
SECTOR_MAP: dict[str, list[str]] = {
    "Ngân hàng":    ["VCB","TCB","MBB","BID","CTG","VPB","STB","HDB",
                     "SHB","EIB","TPB","VIB","OCB","LPB","SSB","MSB","ACB"],
    "Bất động sản": ["VIC","VHM","NVL","KDH","PDR","DXG","NLG","DIG",
                     "VRE","BCM","HDG","CII","DXS","NTL","TDH","IDC"],
    "Dầu khí":      ["GAS","PLX","PVD","PVT","DPM","OIL","CNG","BSR","PVS"],
    "Thép":         ["HPG","HSG","NKG","TVN","SMC","TLH","VIS"],
    "Hàng không":   ["HVN","VJC","SCS","VNA","ACV"],
    "Công nghệ":    ["FPT","CMG"],
    "Chứng khoán":  ["SSI","VCI","VND","HCM","MBS","VIX","AGR"],
    "Bán lẻ":       ["MWG","PNJ"],
    "Thực phẩm":    ["VNM","MSN","SAB","MCH","QNS","KDF","SBT","GTN","LTG"],
    "Dược":         ["DHG","IMP","DBD","PME","DVN"],
    "Bảo hiểm":     ["BVH","BMI","MIG","BIC","PGI"],
    "Điện":         ["POW","BWE","PC1","NT2","GEG","TBC","VSH","PGV","EVE"],
    "Xây dựng":     ["CTD","HBC","FCN","VCG","CSV","HT1","BCC","SCC","VKC","SCG"],
    "Hóa chất":     ["DGC","DCM","CSV","BMP","DAG"],
    "Logistics":    ["GMD","TCH","HAH","VSC","DVP","PHP","VTP","ACV"],
    "Nông nghiệp":  ["VHC","HAG","ANV","IDI","BAF","PAN","NSC"],
    "Vật liệu XD":  ["VGC","REE","GEX","NKG","VIS"],
    "Khác":         ["KBC","GVR","BCG","VEA","TCM","VGT","HAX","SZC","KSB"],
}

def get_sector(ticker: str) -> str:
    for sec, tks in SECTOR_MAP.items():
        if ticker in tks:
            return sec
    return "Khác"

# ─────────────────────────────────────────────────────────────
# MARKET SCAN UNIVERSE
# ─────────────────────────────────────────────────────────────
MARKET_SCAN_LIST: list[str] = sorted(set(
    t for tks in SECTOR_MAP.values() for t in tks
))

DEFAULT_WATCHLIST: list[str] = [
    "FPT","TCB","VCB","MBB","VIC","VHM","HPG","MWG",
    "KBC","GAS","PVD","REE","DGC","SSI","OIL","PVS",
]

# ─────────────────────────────────────────────────────────────
# EXCHANGE-BASED UNIVERSE LISTS
# ─────────────────────────────────────────────────────────────
# HOSE = all SECTOR_MAP tickers NOT in HNX / UPCOM
HOSE_LIST: list[str] = sorted(set(
    t for tks in SECTOR_MAP.values() for t in tks
    if t not in TICKER_EXCHANGE
))

# HNX = all tickers explicitly routed to HNX
HNX_LIST: list[str] = sorted(t for t, ex in TICKER_EXCHANGE.items() if ex == "HNX")

# VN30 — approximate current index constituents (HOSE only)
VN30_LIST: list[str] = [
    "VCB","BID","CTG","TCB","MBB","VPB","HDB","STB",
    "FPT","VIC","VHM","HPG","GAS","PLX","VNM","MSN",
    "SAB","MWG","PNJ","VJC","POW","VRE","SSI","VCI",
    "REE","EIB","NVL","KDH","PDR","BVH",
]

# VN100 = VN30 + next ~70 liquid HOSE stocks
VN100_LIST: list[str] = sorted(set(
    VN30_LIST + [t for t in HOSE_LIST if t not in VN30_LIST][:70]
))

# ─────────────────────────────────────────────────────────────
# MULTI-TIMEFRAME CONFIGURATION
# ─────────────────────────────────────────────────────────────
TIMEFRAME_CONFIG: dict[str, dict] = {
    "1W": {
        "label":          "Tuần (~5 phiên)",
        "label_en":       "Weekly (~5 sessions)",
        "hold_sessions":  5,
        "lookback_days":  180,
        "sma_fast":       5,
        "sma_slow":       20,
        "ema_fast":       5,
        "ema_slow":       20,
        "rsi_period":     9,
        "bb_period":      10,
        "bb_std":         2.0,
        "atr_period":     7,
        "macd_fast":      6,
        "macd_slow":      13,
        "macd_signal":    4,
        "volume_ma":      5,
        "adx_period":     7,
        "stop_atr_mult":  1.0,
        "target_rr":      1.5,
        "min_score":      68,
        "position_pct":   0.10,
        "max_positions":  3,
        "regime_filter":  ["bull"],
        "ml_weights": {
            "lstm":      0.30,
            "xgb":       0.25,
            "rf":        0.25,
            "prophet":   0.10,
            "arima":     0.05,
            "mc":        0.05,
        },
    },
    "2W": {
        "label":          "2 Tuần (~10 phiên)",
        "label_en":       "Bi-weekly (~10 sessions)",
        "hold_sessions":  10,
        "lookback_days":  365,
        "sma_fast":       10,
        "sma_slow":       30,
        "ema_fast":       8,
        "ema_slow":       21,
        "rsi_period":     14,
        "bb_period":      14,
        "bb_std":         2.0,
        "atr_period":     10,
        "macd_fast":      8,
        "macd_slow":      17,
        "macd_signal":    6,
        "volume_ma":      10,
        "adx_period":     10,
        "stop_atr_mult":  1.2,
        "target_rr":      2.0,
        "min_score":      62,
        "position_pct":   0.12,
        "max_positions":  4,
        "regime_filter":  ["bull", "sideways"],
        "ml_weights": {
            "lstm":      0.25,
            "xgb":       0.20,
            "rf":        0.25,
            "prophet":   0.15,
            "arima":     0.10,
            "mc":        0.05,
        },
    },
    "1M": {
        "label":          "1 Tháng (~22 phiên)",
        "label_en":       "Monthly (~22 sessions)",
        "hold_sessions":  22,
        "lookback_days":  548,
        "sma_fast":       20,
        "sma_slow":       50,
        "ema_fast":       12,
        "ema_slow":       26,
        "rsi_period":     14,
        "bb_period":      20,
        "bb_std":         2.0,
        "atr_period":     14,
        "macd_fast":      12,
        "macd_slow":      26,
        "macd_signal":    9,
        "volume_ma":      20,
        "adx_period":     14,
        "stop_atr_mult":  1.5,
        "target_rr":      2.5,
        "min_score":      58,
        "position_pct":   0.15,
        "max_positions":  5,
        "regime_filter":  ["bull", "sideways"],
        "ml_weights": {
            "lstm":      0.20,
            "xgb":       0.15,
            "rf":        0.20,
            "prophet":   0.20,
            "arima":     0.15,
            "mc":        0.10,
        },
    },
    "3M": {
        "label":          "3 Tháng (~66 phiên)",
        "label_en":       "Quarterly (~66 sessions)",
        "hold_sessions":  66,
        "lookback_days":  730,
        "sma_fast":       50,
        "sma_slow":       100,
        "ema_fast":       20,
        "ema_slow":       50,
        "rsi_period":     21,
        "bb_period":      20,
        "bb_std":         2.0,
        "atr_period":     21,
        "macd_fast":      12,
        "macd_slow":      26,
        "macd_signal":    9,
        "volume_ma":      20,
        "adx_period":     21,
        "stop_atr_mult":  2.0,
        "target_rr":      3.0,
        "min_score":      52,
        "position_pct":   0.20,
        "max_positions":  6,
        "regime_filter":  ["bull", "sideways", "bear"],
        "ml_weights": {
            "lstm":      0.15,
            "xgb":       0.10,
            "rf":        0.20,
            "prophet":   0.25,
            "arima":     0.15,
            "mc":        0.15,
        },
    },
    "5M": {
        "label":          "5 Tháng (~110 phiên)",
        "label_en":       "5-Month (~110 sessions)",
        "hold_sessions":  110,
        "lookback_days":  1095,
        "sma_fast":       50,
        "sma_slow":       200,
        "ema_fast":       26,
        "ema_slow":       50,
        "rsi_period":     21,
        "bb_period":      20,
        "bb_std":         2.0,
        "atr_period":     21,
        "macd_fast":      12,
        "macd_slow":      26,
        "macd_signal":    9,
        "volume_ma":      20,
        "adx_period":     21,
        "stop_atr_mult":  2.5,
        "target_rr":      4.0,
        "min_score":      48,
        "position_pct":   0.25,
        "max_positions":  6,
        "regime_filter":  ["bull", "sideways", "bear"],
        "ml_weights": {
            "lstm":      0.10,
            "xgb":       0.10,
            "rf":        0.15,
            "prophet":   0.30,
            "arima":     0.20,
            "mc":        0.15,
        },
    },
}

TIMEFRAMES = list(TIMEFRAME_CONFIG.keys())  # ['1W','2W','1M','3M','5M']

# ─────────────────────────────────────────────────────────────
# PORTFOLIO PROFILES
# ─────────────────────────────────────────────────────────────
PORTFOLIO_PROFILES: dict[str, dict] = {
    "aggressive": {
        "label":    "🔥 Tích cực",
        "alloc":    {"1W": 0.20, "2W": 0.20, "1M": 0.25, "3M": 0.20, "5M": 0.15},
        "cash_min": 0.00,
    },
    "balanced": {
        "label":    "⚖️ Cân bằng",
        "alloc":    {"1W": 0.10, "2W": 0.15, "1M": 0.25, "3M": 0.25, "5M": 0.15},
        "cash_min": 0.10,
    },
    "conservative": {
        "label":    "🛡️ Thận trọng",
        "alloc":    {"1W": 0.05, "2W": 0.10, "1M": 0.20, "3M": 0.30, "5M": 0.25},
        "cash_min": 0.10,
    },
}

# ─────────────────────────────────────────────────────────────
# SCORE THRESHOLDS → ACTION
# ─────────────────────────────────────────────────────────────
SCORE_TO_ACTION = {
    (80, 100): "STRONG BUY",
    (65, 80):  "BUY",
    (45, 65):  "HOLD",
    (30, 45):  "WATCH",
    (0,  30):  "SELL",
}

def score_to_action(score: float) -> str:
    for (lo, hi), action in SCORE_TO_ACTION.items():
        if lo <= score <= hi:
            return action
    return "HOLD"

# ─────────────────────────────────────────────────────────────
# MANIPULATION DETECTION THRESHOLDS
# ─────────────────────────────────────────────────────────────
PUMP_VOLUME_SPIKE   = 3.0   # Volume/SMA20 > 3x
PUMP_PRICE_MOVE_5D  = 0.15  # >15% in 5 sessions
ATC_RATIO_THRESH    = 0.40  # ATC volume > 40% of day volume

# ─────────────────────────────────────────────────────────────
# WORLD MARKET IMPACT DESCRIPTIONS
# ─────────────────────────────────────────────────────────────
WORLD_IMPACT_VI = {
    "Gold (XAU/USD)":  "🪙 Vàng tăng → PNJ/SJC hưởng lợi; áp lực NIM ngân hàng",
    "WTI Oil":         "🛢️ Dầu tăng → GAS/PLX/PVD/BSR tăng; HVN/VJC chi phí tăng",
    "Natural Gas":     "⛽ Khí tăng → chi phí sản xuất điện/hóa chất tăng",
    "DXY (USD Index)": "💵 DXY tăng → VNĐ áp lực, nhập khẩu đắt, xuất khẩu cạnh tranh",
    "S&P 500":         "📈 S&P tăng → khẩu vị rủi ro toàn cầu tốt, vốn ngoại vào VN",
    "VIX":             "😨 VIX tăng → sợ hãi toàn cầu, bán tháo thị trường mới nổi",
    "CSI 300 (CN)":    "🇨🇳 CSI tăng → hàng hóa VN cạnh tranh với TQ; tâm lý khu vực",
    "Nikkei 225":      "🇯🇵 Nikkei tăng → FDI Nhật Bản vào VN tích cực hơn",
}

WORLD_IMPACT_EN = {
    "Gold (XAU/USD)":  "🪙 Gold up → PNJ/SJC benefit; bank NIM pressure",
    "WTI Oil":         "🛢️ Oil up → GAS/PLX/PVD/BSR gain; HVN/VJC cost pressure",
    "Natural Gas":     "⛽ Gas up → higher power/chemical production costs",
    "DXY (USD Index)": "💵 DXY up → VND pressure, costlier imports, competitive exports",
    "S&P 500":         "📈 S&P up → global risk appetite improves, foreign inflow to VN",
    "VIX":             "😨 VIX up → global fear, EM selloff risk",
    "CSI 300 (CN)":    "🇨🇳 CSI up → VN goods compete with China; regional sentiment",
    "Nikkei 225":      "🇯🇵 Nikkei up → Japanese FDI sentiment positive for VN",
}
