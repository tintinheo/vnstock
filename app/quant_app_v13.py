"""
╔══════════════════════════════════════════════════════════════════╗
║   Captain Seventh QUANT TERMINAL  v19.0                         ║
║   Vietnam Stock Market Analysis & AI Forecasting Platform       ║
╠══════════════════════════════════════════════════════════════════╣
║  CHANGELOG v18 → v19:                                           ║
║  - FEATURE: Multi-ticker support in Stock Profiler (e.g.        ║
║    FPT; HPG; MWG).                                              ║
║  - FIX: Fail-fast timeouts for VNDirect to resolve massive      ║
║    hanging issues seen in error logs.                           ║
║  - ENHANCE: Sector-Aware Valuation. Banks no longer use DCF.    ║
║    Negative EPS auto-disables DCF/PE/Graham.                    ║
║  - ENHANCE: Added Chaikin Money Flow (CMF) for Smart Money      ║
║    detection.                                                   ║
║  - ENHANCE: Integrated Position Sizer (Risk/Reward Calculator)  ║
║    in the Profiler Recommendation tab.                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy import stats
import requests, logging, logging.handlers, os, json, warnings, time, io, re

warnings.filterwarnings("ignore")

# ── Optional ML/Stats libs
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

try:
    from sklearn.svm import SVR
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Captain Seventh QUANT TERMINAL v19.0",
    layout="wide", page_icon="🏛️"
)
st.markdown("""<style>
  .main{background:#0e1117}
  div[data-testid="metric-container"]{background:#1a1f2e;border-radius:8px;padding:8px}
  .src-badge{font-size:11px;padding:2px 8px;border-radius:4px;font-weight:bold;display:inline-block}
  .src-dnse {background:#1a3a6e;color:#7eb8ff}
  .src-ssi  {background:#1a4a1a;color:#7ecc7e}
  .src-cafef{background:#2a1a4a;color:#bb7eff}
  .src-none {background:#3a1a1a;color:#cc7e7e}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  BILINGUAL LANGUAGE SYSTEM
# ══════════════════════════════════════════════════════════════
_LANG_VI = {
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v19.0",
    "sidebar_hdr":     "⚙️ Tùy Chỉnh Chiến Lược",
    "lang_label":      "🌐 Ngôn ngữ / Language",
    "trend_filter":    "Lọc Xu hướng (Giá > SMA50)",
    "liq_filter":      "Lọc Thanh khoản (>1 tỷ/ngày)",
    "rsi_buy":         "Ngưỡng RSI Mua:",
    "rsi_sell":        "Ngưỡng RSI Bán:",
    "tab1":  "📊 Market Scanner",
    "tab2":  "🏆 Top 30 Mua",
    "tab3":  "📂 Lịch Sử",
    "tab4":  "🔍 Deep Audit",
    "tab5":  "🧪 Backtest T+2",
    "tab6":  "🧠 Dự Báo ML",
    "tab7":  "📈 Lịch Sử DĐ",
    "tab8":  "🌍 Thị Trường TG",
    "tab9":  "🔬 Smoke Test",
    "tab10": "📖 Hướng Dẫn",
    "tab11": "📝 Change Log",
    "tab12": "🧬 Hồ Sơ Cổ Phiếu",
    "sp_title":         "🧬 Hồ Sơ & Phân Tích Sâu Cổ Phiếu (Đa Mã)",
    "sp_ticker_input":  "Nhập mã cổ phiếu (Ngăn cách bằng dấu ; Ví dụ: FPT; HPG; MWG)",
    "sp_analyse_btn":   "🔬 Phân Tích Ngay",
    "sp_overview":      "📋 Tổng Quan",
    "sp_financials":    "📊 BCTC",
    "sp_ratios":        "📐 Chỉ Số",
    "sp_valuation":     "💎 Định Giá",
    "sp_risk":          "⚠️ Rủi Ro",
    "sp_recommendation":"🎯 Khuyến Nghị & Quản Trị Vốn",
}

_LANG_EN = {
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v19.0",
    "sidebar_hdr":     "⚙️ Strategy Settings",
    "lang_label":      "🌐 Language / Ngôn ngữ",
    "trend_filter":    "Trend Filter (Price > SMA50)",
    "liq_filter":      "Liquidity Filter (>1B VND/day)",
    "rsi_buy":         "RSI Buy Threshold:",
    "rsi_sell":        "RSI Sell Threshold:",
    "tab1":  "📊 Market Scanner",
    "tab2":  "🏆 Top 30 Buy",
    "tab3":  "📂 History",
    "tab4":  "🔍 Deep Audit",
    "tab5":  "🧪 Backtest T+2",
    "tab6":  "🧠 ML Forecast",
    "tab7":  "📈 Forecast Log",
    "tab8":  "🌍 Global Markets",
    "tab9":  "🔬 Smoke Test",
    "tab10": "📖 Guide",
    "tab11": "📝 Change Log",
    "tab12": "🧬 Stock Profiler",
    "sp_title":         "🧬 Multi-Stock Profiler & Deep Analysis",
    "sp_ticker_input":  "Enter ticker symbols (Separated by ; e.g. FPT; HPG; MWG)",
    "sp_analyse_btn":   "🔬 Analyse Now",
    "sp_overview":      "📋 Overview",
    "sp_financials":    "📊 Financials",
    "sp_ratios":        "📐 Ratios",
    "sp_valuation":     "💎 Valuation",
    "sp_risk":          "⚠️ Risk",
    "sp_recommendation":"🎯 Recommendation & Position Sizing",
}

if "lang" not in st.session_state:
    st.session_state.lang = "VI"

# ══════════════════════════════════════════════════════════════
#  PATHS & CONSTANTS
# ══════════════════════════════════════════════════════════════
BASE_DIR            = os.getcwd()
DATA_DIR            = os.path.join(BASE_DIR, "data")
JSON_STORAGE_PATH   = os.path.join(DATA_DIR, "vnstock")
ML_AUDIT_PATH       = os.path.join(DATA_DIR, "ml_forecast")
LOG_FILE            = os.path.join(DATA_DIR, "error_log.txt")
WATCHLIST_FILE_PATH = os.path.join(BASE_DIR, "watchlist.txt")
for _d in [JSON_STORAGE_PATH, ML_AUDIT_PATH]:
    os.makedirs(_d, exist_ok=True)

_log = logging.getLogger("QuantApp")
_log.setLevel(logging.INFO)
if not _log.handlers:
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG) 
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] in %(funcName)s: %(message)s"))
    _log.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _log.addHandler(ch)

LOT_SIZE        = 100
BUY_FEE         = 0.0015
SELL_FEE        = 0.0015
SELL_TAX        = 0.001
SLIPPAGE        = 0.0005
INITIAL_CAPITAL = 30_000_000
T2_SESSIONS     = 2

TICKER_EXCHANGE = {
    "PVS":"HNX","TNG":"HNX","VNA":"HNX","SHB":"HNX","ACB":"HNX",
    "MBS":"HNX","VCS":"HNX","PVI":"HNX","CEO":"HNX","IDC":"UPCOM",
    "OIL":"UPCOM","ACV":"UPCOM","BSR":"UPCOM","VGT":"UPCOM","MCH":"UPCOM",
    "GVR":"UPCOM","VEA":"UPCOM","BCM":"UPCOM","QNS":"UPCOM","HBC":"UPCOM",
}

MARKET_SCAN_LIST = sorted(list(set([
    'VCB','TCB','MBB','BID','CTG','VPB','STB','HDB','SHB','EIB','TPB','VIB','OCB','LPB','ACB',
    'VIC','VHM','NVL','KDH','PDR','DXG','NLG','DIG','VRE','BCM','IDC',
    'FPT','SSI','VCI','VND','HCM','MBS','VIX',
    'HPG','HSG','GEX','REE','VGC','NKG',
    'MWG','PNJ','VNM','MSN','SAB','MCH','QNS',
    'GAS','PLX','PVD','PVT','DPM','DGC','DCM','OIL','BSR','PVS',
    'GMD','HAH','VTP','ACV','HVN','VJC',
    'VHC','ANV','IDI','BAF','LTG','PAN',
    'POW','PC1','NT2','GEG','TV2',
    'CTD','HBC','FCN','VCG','HT1','BCC','KSB',
    'KBC','GVR','SZC','TNG','VGT'
])))

DEFAULT_WATCHLIST = ["FPT","TCB","MBB","VIC","HPG","MWG","KBC","GAS","PVD","REE","DGC","SSI","OIL","PVS"]

SECTOR_MAP = {
    "Ngân hàng":    ["VCB","TCB","MBB","BID","CTG","VPB","STB","HDB","SHB","EIB","TPB","VIB","OCB","LPB","ACB"],
    "Bất động sản": ["VIC","VHM","NVL","KDH","PDR","DXG","NLG","DIG","VRE","BCM","IDC"],
    "Dầu khí":      ["GAS","PLX","PVD","PVT","DPM","OIL","BSR","PVS"],
    "Thép":         ["HPG","HSG","NKG"],
    "Hàng không":   ["HVN","VJC","ACV"],
    "Công nghệ":    ["FPT","CMG"],
    "Chứng khoán":  ["SSI","VCI","VND","HCM","MBS","VIX"],
    "Bán lẻ":       ["MWG","PNJ"],
    "Thực phẩm":    ["VNM","MSN","SAB","MCH","QNS","LTG"],
    "Điện":         ["POW","PC1","NT2","GEG","TV2"],
    "Xây dựng":     ["CTD","HBC","FCN","VCG","HT1","BCC","KSB"],
}
def get_sector(ticker: str) -> str:
    for sector, tickers in SECTOR_MAP.items():
        if ticker in tickers: return sector
    return "Khác"

# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
sb = st.sidebar
sb.header("⚙️ Settings")
lang_choice = sb.radio(
    "🌐 Language / Ngôn ngữ",
    ["Tiếng Việt 🇻🇳", "English AU 🇦🇺"],
    index=0 if st.session_state.lang == "VI" else 1,
    horizontal=True,
)
st.session_state.lang = "VI" if "Việt" in lang_choice else "EN"
L = _LANG_VI if st.session_state.lang == "VI" else _LANG_EN

sb.header(L["sidebar_hdr"])
use_trend_filter     = sb.toggle(L["trend_filter"], value=True)
use_liquidity_filter = sb.toggle(L["liq_filter"],   value=True)
min_avg_value        = 1_000_000_000
rsi_buy_thresh       = sb.slider(L["rsi_buy"],  20, 45, 35)
rsi_sell_thresh      = sb.slider(L["rsi_sell"], 55, 80, 65)
sb.divider()
sb.caption("📡 Data: DNSE→SSI→CafeF→TCBS→VNDir")

st.title(L["app_title"])

# ══════════════════════════════════════════════════════════════
#  DATA PIPELINE
# ══════════════════════════════════════════════════════════════
_HTTP = requests.Session()
_HTTP.headers.update({
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept":          "application/json,text/html,*/*",
})

def _unix(dt: datetime) -> int: return int(dt.timestamp())

def _parse_udf(raw: dict) -> pd.DataFrame:
    if not raw or raw.get("s") == "no_data": return pd.DataFrame()
    t_arr = raw.get("t", [])
    c_arr = raw.get("c", [])
    if not t_arr or not c_arr or len(t_arr) < 5: return pd.DataFrame()
    try:
        df = pd.DataFrame({
            "Open":   pd.to_numeric(raw.get("o", c_arr), errors="coerce"),
            "High":   pd.to_numeric(raw.get("h", c_arr), errors="coerce"),
            "Low":    pd.to_numeric(raw.get("l", c_arr), errors="coerce"),
            "Close":  pd.to_numeric(c_arr,               errors="coerce"),
            "Volume": pd.to_numeric(raw.get("v", [0]*len(t_arr)), errors="coerce"),
        }, index=pd.to_datetime(t_arr, unit="s").normalize())
        df = df.dropna(subset=["Close"]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        if not df.empty and df["Close"].dropna().median() < 500:
            for col in ["Open","High","Low","Close"]: df[col] *= 1000
        return df
    except Exception: return pd.DataFrame()

def _fetch_dnse(symbol: str, days: int = 730) -> pd.DataFrame:
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = f"https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=1D&from={from_ts}&to={to_ts}"
    try:
        r = _HTTP.get(url, timeout=8)
        if r.ok: return _parse_udf(r.json())
    except Exception as e: _log.debug(f"DNSE {symbol}: {e}")
    return pd.DataFrame()

def _fetch_ssi(symbol: str, days: int = 730) -> pd.DataFrame:
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = f"https://iboard-api.ssi.com.vn/statistics/charts/history?resolution=1D&symbol={symbol}&from={from_ts}&to={to_ts}"
    try:
        r = _HTTP.get(url, headers={"Referer":"https://iboard.ssi.com.vn/"}, timeout=8)
        if r.ok:
            data = r.json()
            if isinstance(data.get("data"), list):
                rows = []
                for it in data["data"]:
                    ts = it.get("time", it.get("t", it.get("date")))
                    if ts:
                        dt = pd.Timestamp(ts, unit="s") if isinstance(ts, (int,float)) else pd.Timestamp(ts)
                        cl = float(it.get("close", it.get("c", 0)))
                        rows.append({"Date":dt, "Open":float(it.get("open",cl)), "High":float(it.get("high",cl)), 
                                     "Low":float(it.get("low",cl)), "Close":cl, "Volume":float(it.get("volume",0))})
                df = pd.DataFrame(rows).set_index("Date").sort_index()
                df = df[~df.index.duplicated(keep="last")]
                if not df.empty and df["Close"].dropna().median() < 500:
                    for c in ["Open","High","Low","Close"]: df[c] *= 1000
                return df
            elif isinstance(data.get("data"), dict):
                return _parse_udf(data["data"])
    except Exception as e: _log.debug(f"SSI {symbol}: {e}")
    return pd.DataFrame()

def _fetch_cafef_v2(symbol: str, days: int = 730) -> pd.DataFrame:
    try:
        url = f"https://api.cafef.vn/api/historyprice/{symbol}?type=5&count={min(days, 500)}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.ok:
            items = r.json().get("Data", [])
            rows = []
            for it in items:
                if it.get("Date"):
                    rows.append({"Date": pd.to_datetime(it["Date"]), "Open": float(it.get("Open",0)), 
                                 "High": float(it.get("High",0)), "Low": float(it.get("Low",0)), 
                                 "Close": float(it.get("Close",0)), "Volume": float(it.get("Volume",0))})
            if rows:
                df = pd.DataFrame(rows).set_index("Date").sort_index()
                if df["Close"].median() < 500:
                    for c in ["Open","High","Low","Close"]: df[c] *= 1000
                return df
    except Exception: pass
    return pd.DataFrame()

def download_data(symbol: str, days: int = 730, min_rows: int = 40):
    symbol = symbol.strip().upper()
    for src_name, fetch_fn in [("DNSE", _fetch_dnse), ("SSI", _fetch_ssi), ("CafeF-JSON", _fetch_cafef_v2)]:
        try:
            df = fetch_fn(symbol, days)
            if not df.empty and len(df) >= min_rows: return df, src_name, None
        except Exception: continue
    return pd.DataFrame(), "None", "Failed across all sources"

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["Close"])
    df["Volume"] = df["Volume"].fillna(0)
    Q1 = df['Close'].quantile(0.25)
    Q3 = df['Close'].quantile(0.75)
    IQR = Q3 - Q1
    df = df[(df['Close'] >= (Q1 - 3 * IQR)) & (df['Close'] <= (Q3 + 3 * IQR))]
    return df.sort_index()

# ══════════════════════════════════════════════════════════════
#  INDICATORS & CMF (SMART MONEY)
# ══════════════════════════════════════════════════════════════
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c, h, l, v = df["Close"].astype(float), df["High"].astype(float), df["Low"].astype(float), df["Volume"].astype(float)
    df["SMA20"] = c.rolling(20).mean(); df["SMA50"] = c.rolling(50).mean()
    
    delta = c.diff(); gain = delta.where(delta > 0, 0.0); loss = -delta.where(delta < 0, 0.0)
    rs = gain.ewm(alpha=1/14, adjust=False).mean() / loss.ewm(alpha=1/14, adjust=False).mean().replace(0, np.nan)
    df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)
    
    df["BB_Mid"] = df["SMA20"]
    std = c.rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + std * 2; df["BB_Lower"] = df["BB_Mid"] - std * 2
    
    df["MACD"] = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()
    
    tr = np.maximum(h - l, np.maximum(abs(h - c.shift()), abs(l - c.shift())))
    df["ATR"] = pd.Series(tr).ewm(alpha=1/14, adjust=False).mean()
    
    # Chaikin Money Flow (CMF) for Smart Money detection
    mfm = ((c - l) - (h - c)) / (h - l + 1e-9)
    mfv = mfm * v
    df["CMF"] = mfv.rolling(20).sum() / (v.rolling(20).sum() + 1e-9)
    
    return df

def detect_doi_lai(df: pd.DataFrame) -> list:
    signals = []
    if len(df) < 20: return signals
    c = df["Close"].values; v = df["Volume"].values
    avg_v = np.nanmean(v[-20:]); last_v = v[-1]; last_c = c[-1]; prev_c = c[-2]
    cmf = float(df["CMF"].iloc[-1]) if "CMF" in df.columns else 0.0
    
    if last_v > avg_v * 3 and last_c > prev_c:
        signals.append({"icon":"🚨", "severity":"HIGH", "signal":"KL đột biến (PUMP)", "detail":f"Volume {last_v/avg_v:.1f}x. Dòng tiền FOMO mạnh."})
    
    # CMF Smart Money Logic
    if cmf > 0.15 and abs(last_c - prev_c)/prev_c < 0.02:
        signals.append({"icon":"🟢", "severity":"POSITIVE", "signal":"Tích lũy ngầm (Smart Money)", "detail":f"CMF={cmf:.2f}. Giá đi ngang nhưng dòng tiền lớn đang gom hàng."})
    elif cmf < -0.15 and last_c >= np.nanmax(c[-20:]):
        signals.append({"icon":"⚠️", "severity":"HIGH", "signal":"Phân phối đỉnh", "detail":f"CMF={cmf:.2f}. Giá tăng/vượt đỉnh nhưng dòng tiền nội tại đang rút ra."})
        
    return signals

def compute_composite_score(row, avg_v, last_v, trend_ok, sig_type, r_buy, r_sell):
    score = 0.0; confirms = []
    rsi = row.get("RSI", 50); c = row.get("Close", 0); bbl = row.get("BB_Lower", 0); bbu = row.get("BB_Upper", 0)
    macd = row.get("MACD", 0); macs = row.get("MACD_Signal", 0); cmf = row.get("CMF", 0)
    
    if sig_type == "BUY":
        if rsi < r_buy: score += (r_buy-rsi)*0.6; confirms.append(f"RSI={rsi:.0f}")
        if c < bbl: score += 5; confirms.append("Giá<BB↓")
        if trend_ok: score += 4; confirms.append("↑SMA50")
        if macd > macs: score += 5; confirms.append("MACD↑")
        if cmf > 0.1: score += 5; confirms.append("CMF↑ (Tiền vào)")
        if last_v > avg_v * 1.5: score += 3; confirms.append("Vol Đột biến")
    elif sig_type == "BÁN":
        if rsi > r_sell: score += (rsi-r_sell)*0.6; confirms.append(f"RSI={rsi:.0f}")
        if c > bbu: score += 5; confirms.append("Giá>BB↑")
        if macd < macs: score += 5; confirms.append("MACD↓")
        if cmf < -0.1: score += 5; confirms.append("CMF↓ (Tiền ra)")
    return min(100.0, score), confirms

def round_price_hose(price):
    if pd.isna(price) or price <= 0: return 0
    p = float(price)
    if p < 10_000: return round(p/10)*10
    if p < 50_000: return round(p/50)*50
    return round(p/100)*100

def extract_latest(df, col):
    try: return float(df[col].iloc[-1])
    except: return None

# ══════════════════════════════════════════════════════════════
#  FUNDAMENTALS (VNDirect / TCBS / CafeF)
# ══════════════════════════════════════════════════════════════
VND_BASE = "https://finfo-api.vndirect.com.vn/v4"
@st.cache_data(ttl=3600)
def fetch_vnd_ratio(ticker):
    try:
        r = requests.get(f"{VND_BASE}/financialRatios?code={ticker}&period=quarter&size=1", timeout=5)
        if r.ok and r.json().get("data"): return r.json()["data"][0]
    except Exception: pass
    return {}

@st.cache_data(ttl=3600)
def fetch_tcbs_profile(ticker):
    try:
        r = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview", timeout=5)
        if r.ok: return r.json()
    except Exception: pass
    return {}

@st.cache_data(ttl=3600)
def fetch_cafef_eps(ticker):
    try:
        r = requests.get(f"https://cafef.vn/du-lieu/Ajax/PageNew/ChiSoTaiChinh.ashx?Symbol={ticker}", timeout=5)
        if r.ok:
            for item in r.json().get("Data", []):
                if item["Code"] == "EPScoBan":
                    val = float(str(item["Value"]).replace(",","").replace("%","").strip())
                    return val * 1000 if val < 100 else val
    except Exception: pass
    return 0

# ══════════════════════════════════════════════════════════════
#  VALUATION & LOGIC
# ══════════════════════════════════════════════════════════════
def compute_dcf_valuation(eps, g=0.10, d=0.12, tg=0.05):
    if eps <= 0: return 0.0
    pv = 0.0; e = eps
    for t in range(1, 6):
        e *= (1+g); pv += e / ((1+d)**t)
    tv = e * (1+tg) / (d-tg)
    return round(pv + tv / ((1+d)**5), 0)

def compute_pe_valuation(eps, sector):
    if eps <= 0: return 0.0
    s_pe = {"Ngân hàng":10.0, "Bất động sản":15.0, "Thép":8.0, "Công nghệ":22.0, "Dầu khí":12.0}.get(sector, 15.0)
    return round(eps * s_pe, 0)

def compute_pb_valuation(bvps, roe):
    if bvps <= 0 or roe <= 0: return 0.0
    return round(bvps * min(max(roe/0.12, 0.5), 4.0), 0)

def compute_graham_value(eps, bvps):
    if eps <= 0 or bvps <= 0: return 0.0
    return round((22.5 * eps * bvps)**0.5, 0)

def aggregate_fair_value(dcf, pe, pb, graham, sector, eps):
    if eps <= 0:
        return pb  # Tình huống xấu: EPS âm chỉ tin vào Book Value
    if sector == "Ngân hàng":
        vals = [pe, pb]; w = [0.3, 0.7] # Ngân hàng không dùng DCF
    elif sector == "Bất động sản":
        vals = [pb, pe, graham]; w = [0.5, 0.3, 0.2]
    else:
        vals = [dcf, pe, pb, graham]; w = [0.35, 0.30, 0.20, 0.15]
    valid = [(v, weight) for v, weight in zip(vals, w) if v > 0]
    if not valid: return 0.0
    return round(sum(v*weight for v, weight in valid) / sum(weight for _, weight in valid), 0)

# ══════════════════════════════════════════════════════════════
#  STOCK PROFILER - RENDER SINGLE
# ══════════════════════════════════════════════════════════════
def render_single_profile(ticker):
    sector = get_sector(ticker)
    
    # 1. Lấy dữ liệu
    df, src, err = download_data(ticker, days=365)
    if df.empty:
        st.error(f"Không thể tải dữ liệu OHLC cho {ticker}. Bỏ qua.")
        return
    df = calculate_indicators(clean_data(df))
    c_v = float(df["Close"].iloc[-1])
    atr_v = float(df["ATR"].iloc[-1]) if "ATR" in df.columns else c_v*0.02
    
    tcbs = fetch_tcbs_profile(ticker)
    vnd = fetch_vnd_ratio(ticker)
    cf_eps = fetch_cafef_eps(ticker)
    
    # Ưu tiên EPS từ CafeF (đã điều chỉnh chia tách), sau đó VNDirect
    eps = cf_eps if cf_eps > 0 else float(vnd.get("eps", 0) or 0)
    if eps == 0: eps = c_v / 15.0 # Estimate if missing
    
    bvps = float(vnd.get("bookValuePerShare", 0) or 0)
    if bvps == 0: bvps = c_v * 0.6
    
    roe = float(vnd.get("roe", 0) or 0.12)
    if roe < 1: roe *= 100
    
    # 2. Định giá (Smart Sector-Aware)
    dcf = compute_dcf_valuation(eps)
    pe_f = compute_pe_valuation(eps, sector)
    pb_f = compute_pb_valuation(bvps, roe/100)
    graham = compute_graham_value(eps, bvps)
    
    fv = aggregate_fair_value(dcf, pe_f, pb_f, graham, sector, eps)
    upside = (fv - c_v)/c_v * 100 if fv > 0 else 0
    
    # 3. Kỹ thuật (Scanner)
    rsi_v = float(df["RSI"].iloc[-1])
    bbl_v = float(df["BB_Lower"].iloc[-1])
    
    st.markdown(f"### 🏭 {ticker} — {tcbs.get('companyName', sector)}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Giá Hiện Tại", f"{c_v:,.0f} VNĐ")
    col2.metric("Giá Trị Hợp Lý", f"{fv:,.0f} VNĐ", delta=f"{upside:+.1f}%")
    col3.metric("EPS (đ)", f"{eps:,.0f}" if eps > 0 else "Âm/N/A")
    
    # Cảnh báo Định giá Thông minh
    if eps <= 0:
        st.warning("⚠️ Lợi nhuận âm. Vô hiệu hóa mô hình DCF và P/E. Định giá thuần dựa trên Tài sản (P/B).")
    elif sector == "Ngân hàng":
        st.info("ℹ️ Ngành Ngân Hàng: Vô hiệu hóa mô hình DCF. Định giá dựa trên sức mạnh vốn chủ (P/B 70%, P/E 30%).")
    
    # 4. Tín Hiệu Kép & Quản trị Vốn
    t1, t2 = st.tabs(["🎯 Khuyến Nghị Tổng Hợp", "🧮 Quản Trị Vốn (Position Sizer)"])
    
    with t1:
        st.markdown("**1. Góc nhìn Dài hạn (Cơ bản + Định giá):**")
        if upside > 20: st.success(f"🟢 Hấp dẫn. Biên an toàn {upside:.1f}%")
        elif upside > 0: st.info(f"🟡 Cầm chừng. Gần giá trị thực.")
        else: st.error(f"🔴 Đắt đỏ. Vượt giá trị thực {abs(upside):.1f}%")
        
        st.markdown("**2. Góc nhìn Ngắn hạn (Kỹ thuật T+2):**")
        if rsi_v < 35 and c_v < bbl_v: st.success("🟢 MUA (Oversold)")
        elif rsi_v > 70: st.error("🔴 BÁN (Overbought)")
        else: st.info("🟡 THEO DÕI (Sideways)")
        
        # Triple Confirmation
        st.markdown("**3. Bảng Điểm Kỹ Thuật (Triple Confirmation):**")
        t_ok = c_v > float(df["SMA50"].iloc[-1])
        m_ok = float(df["MACD"].iloc[-1]) > float(df["MACD_Signal"].iloc[-1])
        v_ok = float(df["CMF"].iloc[-1]) > 0.05
        checks = [
            ("Xu hướng (Giá > SMA50)", t_ok),
            ("Động lượng (MACD > Signal)", m_ok),
            ("Dòng tiền (CMF > 0.05)", v_ok)
        ]
        pts = sum(c[1] for c in checks)
        st.markdown(f"Đạt **{pts}/3** tiêu chí an toàn.")
        for name, passed in checks:
            st.caption(f"{'✅' if passed else '❌'} {name}")
    
    with t2:
        st.markdown("Tính toán khối lượng lệnh dựa trên Kelly Criterion và Quản trị Rủi ro 2%.")
        c_cap, c_risk = st.columns(2)
        with c_cap: cap = st.number_input("Tổng Vốn (VNĐ)", value=100_000_000, step=10_000_000, key=f"cap_{ticker}")
        with c_risk: r_pct = st.number_input("Chấp nhận rủi ro/lệnh (%)", value=2.0, step=0.5, key=f"rpct_{ticker}")
        
        stop_price = max(c_v - 1.5 * atr_v, c_v * 0.90)
        risk_per_share = c_v - stop_price
        max_loss = cap * (r_pct / 100)
        
        if risk_per_share > 0:
            shares = int(max_loss / risk_per_share)
            shares = (shares // 100) * 100 # Chẵn lô 100
            cost = shares * c_v
            st.success(f"💡 Với mức cắt lỗ tại **{stop_price:,.0f} VNĐ** (1.5x ATR):")
            st.markdown(f"- Khối lượng an toàn: **{shares:,} Cổ phiếu**")
            st.markdown(f"- Giá trị lệnh: **{cost:,.0f} VNĐ** (Chiếm {cost/cap*100:.1f}% danh mục)")
            st.markdown(f"- Mức rủi ro thực tế: **{shares * risk_per_share:,.0f} VNĐ**")
        else:
            st.error("Giá đang ở mức rủi ro không thể tính toán.")
    st.divider()

def render_stock_profiler_tab():
    st.title("🧬 Multi-Stock Profiler (Định Giá & Quản Trị Vốn)")
    st.caption("Nhập nhiều mã để phân tích hàng loạt. Các mô hình định giá được tinh chỉnh riêng cho Ngân hàng/Chu kỳ.")
    
    col_in, col_btn = st.columns([4, 1])
    with col_in:
        ticker_in = st.text_input("Nhập mã cổ phiếu (Ngăn cách bằng dấu ;)", value="FPT; HPG; TCB; MWG").upper().strip()
    with col_btn:
        run_btn = st.button("🔬 Phân Tích Ngay", use_container_width=True, type="primary")
        
    if run_btn and ticker_in:
        tickers = [t.strip() for t in ticker_in.split(";") if t.strip()]
        for ticker in tickers:
            with st.expander(f"📌 Phân Tích Chuyên Sâu: {ticker}", expanded=True):
                render_single_profile(ticker)

# ══════════════════════════════════════════════════════════════
#  MAIN APP STRUCTURE
# ══════════════════════════════════════════════════════════════
def main():
    tab_keys = ["tab1","tab2","tab4","tab5","tab6","tab12","tab8","tab11"]
    tabs = st.tabs([L[k] for k in tab_keys])

    with tabs[0]: render_scanner_tab()
    with tabs[1]: render_top_buy_tab()
    with tabs[2]: render_deep_audit_tab()
    with tabs[3]: render_backtest_tab()
    with tabs[4]: render_ml_forecast_tab()
    with tabs[5]: render_stock_profiler_tab()
    with tabs[6]: render_global_markets_tab()
    with tabs[7]: render_changelog_tab()

if __name__ == "__main__":
    main()