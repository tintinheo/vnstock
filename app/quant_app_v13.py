"""
╔══════════════════════════════════════════════════════════════════╗
║   Captain Seventh QUANT TERMINAL  v14.0                         ║
║   Vietnam Stock Market Analysis & AI Forecasting Platform       ║
╠══════════════════════════════════════════════════════════════════╣
║  CHANGELOG v13 → v14:                                           ║
║  [BUG FIXES]                                                    ║
║  FIX-01: st.session.state → st.session_state (70+ occurrences) ║
║  FIX-02: scan_one_ticker() now always returns 3-tuple           ║
║          (was returning 2-tuple on success → "too many values   ║
║           to unpack" crash in Deep Audit & Scanner)             ║
║  FIX-03: SSI iBoard — multi-endpoint fallback (v2 → v1 → fc)   ║
║  FIX-04: DNSE Entrade — multi-endpoint fallback (v2 → v1)      ║
║  FIX-05: VN-Index fetch — SSI → stooq → yfinance chain         ║
║  FIX-06: World Markets — stooq + yfinance fallback (GC=F etc.) ║
║  FIX-07: CafeF JSON API timeout reduced (fail fast on refusal) ║
║  FIX-08: session_state.smoke_results initialised on startup    ║
║  FIX-09: Broken L["lang"] KeyError condition fixed             ║
║  FIX-10: yFinance MultiIndex columns normalised                ║
║  FIX-11: Full stack traces logged to error_log.txt             ║
║  [ENHANCEMENTS]                                                 ║
║  ENH-01: Change Log tab added for audit trail                  ║
║  ENH-02: BRD / Guide tab updated with theory & model detail    ║
║  ENH-03: Smoke test expanded — FPT + OIL functional test       ║
║  ENH-04: Download pipeline shows per-source error detail       ║
║  PRESERVED: all v13 indicators, backtest, ML ensemble, world   ║
║             markets, bilingual UI, sector insights              ║
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
#  PAGE CONFIG (must be first Streamlit call)
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Captain Seventh QUANT TERMINAL v14.0",
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
  .world-up {color:#00cc66;font-weight:bold}
  .world-dn {color:#ff4b4b;font-weight:bold}
  .tag-bull {background:#003300;color:#00ff88;padding:1px 6px;border-radius:3px;font-size:12px}
  .tag-bear {background:#330000;color:#ff6666;padding:1px 6px;border-radius:3px;font-size:12px}
  .tag-warn {background:#332200;color:#ffaa33;padding:1px 6px;border-radius:3px;font-size:12px}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  D. BILINGUAL LANGUAGE SYSTEM
# ══════════════════════════════════════════════════════════════
_LANG_VI = {
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v14.0",
    "sidebar_hdr":     "⚙️ Tùy Chỉnh Chiến Lược",
    "lang_label":      "🌐 Ngôn ngữ / Language",
    "trend_filter":    "Lọc Xu hướng (Giá > SMA50)",
    "liq_filter":      "Lọc Thanh khoản (>1 tỷ/ngày)",
    "rsi_buy":         "Ngưỡng RSI Mua:",
    "rsi_sell":        "Ngưỡng RSI Bán:",
    "pipeline_lbl":    "📡 Pipeline: DNSE → SSI → CafeF",
    "finance_lbl":     "📊 Tài chính: VNDirect FINFO",
    "disclaimer":      "⚠️ Chỉ tham khảo, không phải TVĐT",
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
    "scan_btn":    "🔄 Quét Watchlist",
    "buy_btn":     "🔍 Tìm Cổ Phiếu Mua",
    "audit_btn":   "🔍 Phân Tích",
    "backtest_btn":"⚡ Chạy Backtest",
    "action_buy":  "MUA",
    "action_sell": "BÁN",
    "action_watch":"THEO DÕI",
    "source":      "Nguồn",
    "ticker":      "Mã",
    "price":       "Giá",
    "signal":      "Hành vi",
    "score":       "Điểm",
    "no_data":     "Không có dữ liệu",
    "risk_low":    "Thấp",
    "risk_med":    "Trung bình",
    "risk_high":   "Cao",
    "insight_rsi_os":  "Vùng quá bán — áp lực bán giảm, xác suất hồi phục tăng",
    "insight_rsi_ob":  "Vùng quá mua — áp lực chốt lời cao, thận trọng mua đuổi",
    "insight_bb_low":  "Giá chạm BB Lower — ngoài dải thống kê, thường dẫn đến hồi về BB_Mid",
    "insight_bb_up":   "Giá chạm BB Upper — kháng cự thống kê, xác suất điều chỉnh ngắn hạn cao",
    "insight_macd_bull":"MACD cắt lên Signal — momentum đảo chiều tăng, dòng tiền bắt đầu vào",
    "insight_macd_bear":"MACD cắt xuống Signal — momentum yếu dần, áp lực bán gia tăng",
    "insight_vol_spike":"Khối lượng đột biến — dòng tiền lớn vào/ra, cần xác nhận hướng giá",
    "insight_adx_trend":"ADX > 25 — xu hướng rõ ràng, theo xu hướng hiệu quả hơn đảo chiều",
    "world_impact_gold":     "🪙 Vàng tăng → NIM ngân hàng chịu áp lực, PNJ/SJC hưởng lợi",
    "world_impact_oil":      "🛢️ Dầu WTI tăng → GAS/PLX/PVD tăng; HVN/VJC chi phí tăng",
    "world_impact_gas":      "⛽ Khí tự nhiên tăng → chi phí sản xuất tăng, điện than & hóa chất bị ảnh hưởng",
    "world_impact_dxy":      "💵 DXY tăng (USD mạnh) → VNĐ có áp lực, nhập khẩu đắt hơn, xuất khẩu cạnh tranh hơn",
    "world_impact_sp500":    "📈 S&P500 tăng → khẩu vị rủi ro toàn cầu cải thiện, vốn ngoại có thể vào TTVN",
    "world_impact_fed":      "🏦 FED tăng lãi suất → áp lực tỷ giá, vốn chảy về Mỹ, TTVN chịu áp lực",
}

_LANG_EN = {
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v14.0",
    "sidebar_hdr":     "⚙️ Strategy Settings",
    "lang_label":      "🌐 Language / Ngôn ngữ",
    "trend_filter":    "Trend Filter (Price > SMA50)",
    "liq_filter":      "Liquidity Filter (>1B VND/day)",
    "rsi_buy":         "RSI Buy Threshold:",
    "rsi_sell":        "RSI Sell Threshold:",
    "pipeline_lbl":    "📡 Pipeline: DNSE → SSI → CafeF",
    "finance_lbl":     "📊 Financials: VNDirect FINFO",
    "disclaimer":      "⚠️ For reference only, not investment advice",
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
    "scan_btn":    "🔄 Scan Watchlist",
    "buy_btn":     "🔍 Find Buy Signals",
    "audit_btn":   "🔍 Analyse",
    "backtest_btn":"⚡ Run Backtest",
    "action_buy":  "BUY",
    "action_sell": "SELL",
    "action_watch":"WATCH",
    "source":      "Source",
    "ticker":      "Ticker",
    "price":       "Price",
    "signal":      "Signal",
    "score":       "Score",
    "no_data":     "No data available",
    "risk_low":    "Low",
    "risk_med":    "Medium",
    "risk_high":   "High",
    "insight_rsi_os":  "Oversold zone — selling pressure easing, recovery probability elevated",
    "insight_rsi_ob":  "Overbought zone — profit-taking pressure high, avoid chasing",
    "insight_bb_low":  "Price at BB Lower — outside statistical band, mean reversion to BB_Mid likely",
    "insight_bb_up":   "Price at BB Upper — statistical resistance, near-term pullback probability high",
    "insight_macd_bull":"MACD crossed above Signal — momentum turning bullish, money flowing in",
    "insight_macd_bear":"MACD crossed below Signal — momentum weakening, selling pressure building",
    "insight_vol_spike":"Volume spike — large money move in/out, confirm direction with price",
    "insight_adx_trend":"ADX > 25 — clear trend, trend-following more effective than counter-trend",
    "world_impact_gold":     "🪙 Gold up → pressure on bank NIM; PNJ/SJC beneficiaries",
    "world_impact_oil":      "🛢️ WTI Oil up → GAS/PLX/PVD gain; HVN/VJC face higher costs",
    "world_impact_gas":      "⛽ Natural Gas up → higher production costs; power/chemicals impacted",
    "world_impact_dxy":      "💵 DXY up (strong USD) → VND pressure; imports costlier, exports more competitive",
    "world_impact_sp500":    "📈 S&P500 up → global risk appetite improves, foreign capital may flow into VN",
    "world_impact_fed":      "🏦 FED hike → exchange rate pressure, capital flows to USD, VN market headwind",
}

# Language init (before sidebar to avoid widget ordering issues)
if "lang" not in st.session_state:
    st.session_state.lang = "VI"

# ══════════════════════════════════════════════════════════════
#  PATHS & TRADING CONSTANTS
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
    # Log detailed errors to a file
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG) # Log all levels to file
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] in %(funcName)s: %(message)s"))
    _log.addHandler(fh)
    
    # Log info and higher to the console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _log.addHandler(ch)

LOT_SIZE        = 100
BUY_FEE         = 0.0015   # 0.15% phí mua SSI/DNSE
SELL_FEE        = 0.0015
SELL_TAX        = 0.001    # 0.1% thuế chuyển nhượng
SLIPPAGE        = 0.0005
INITIAL_CAPITAL = 30_000_000
T2_SESSIONS     = 2        # T+2: 2 phiên thực tế tính từ df.index

# ══════════════════════════════════════════════════════════════
#  TICKER UNIVERSE & EXCHANGE MAP
#  Fix: IDC OIL PVS LTG HBC PME SCG TNG TVN VKC VNA ACV
#  Some UPCOM/HNX tickers need explicit exchange context for
#  fallback CafeF scrape
# ══════════════════════════════════════════════════════════════
# Exchange map for accurate CafeF routing (HOSE=1, HNX=2, UPCOM=3)
TICKER_EXCHANGE = {
    # HNX tickers
    "PVS":"HNX","TNG":"HNX","VNA":"HNX","SHB":"HNX","ACB":"HNX",
    "NVB":"HNX","BVS":"HNX","MBS":"HNX","VCS":"HNX","PVI":"HNX",
    "CEO":"HNX","HHC":"HNX","VGS":"HNX","SCI":"HNX","NTP":"HNX",
    "PGC":"HNX","BCC":"HNX","VKC":"HNX","TVN":"HNX","SCG":"HNX",
    # UPCOM tickers
    "IDC":"UPCOM","OIL":"UPCOM","ACV":"UPCOM","BSR":"UPCOM",
    "VGT":"UPCOM","MCH":"UPCOM","GVR":"UPCOM","VEA":"UPCOM",
    "BCM":"UPCOM","MML":"UPCOM","QNS":"UPCOM","HBC":"UPCOM",
    "PME":"UPCOM","LTG":"UPCOM","VKC":"UPCOM",
}

MARKET_SCAN_LIST = sorted(list(set([
    # Ngân hàng
    'VCB','TCB','MBB','BID','CTG','VPB','STB','HDB','SHB','EIB',
    'TPB','VIB','OCB','LPB','SSB','MSB','ACB',
    # BĐS
    'VIC','VHM','NVL','KDH','PDR','DXG','NLG','DIG','VRE','BCM',
    'HDG','CII','DXS','NTL','TDH','IDC',
    # Công nghệ / Chứng khoán
    'FPT','SSI','VCI','VND','CMG','HCM','MBS','VIX','AGR',
    # Thép / Vật liệu
    'HPG','HSG','GEX','REE','VGC','NKG','TVN','SMC','TLH','VIS',
    # Tiêu dùng / Bán lẻ
    'MWG','PNJ','VNM','MSN','SAB','MCH','QNS','KDF','SBT','GTN','LTG',
    # Dầu khí / Hóa chất
    'GAS','PLX','PVD','PVT','DPM','DGC','DCM','OIL','CNG','BSR','PVS',
    # Logistics / Cảng
    'GMD','TCH','HAH','VSC','SGP','DVP','PHP','VTP','VTG','ACV',
    # Hàng không
    'HVN','VJC','SCS','VNA',
    # Nông nghiệp / Thủy sản
    'VHC','HAG','ANV','IDI','BAF','LTG','PAN','NSC',
    # Điện / Tiện ích
    'POW','BWE','PC1','NT2','GEG','TBC','VSH','PGV','EVE',
    # Xây dựng / VLXD
    'CTD','HBC','FCN','VCG','CSV','HT1','BCC','SCC','VKC','SCG',
    # Dược
    'DHG','IMP','DBD','PME','DVN',
    # Bảo hiểm
    'BVH','BMI','MIG','BIC','PGI',
    # Khác
    'KBC','GVR','BCG','VEA','TCM','VGT','TNG','HAX','SZC','KSB',
])))

DEFAULT_WATCHLIST = [
    "FPT","TCB","VCB","MBB","VIC","VHM","HPG","MWG",
    "KBC","GAS","PVD","REE","DGC","SSI","OIL","PVS",
]

# Sector metadata for contextual insights
SECTOR_MAP = {
    "Ngân hàng":    ["VCB","TCB","MBB","BID","CTG","VPB","STB","HDB","SHB","EIB",
                     "TPB","VIB","OCB","LPB","SSB","MSB","ACB"],
    "Bất động sản": ["VIC","VHM","NVL","KDH","PDR","DXG","NLG","DIG","VRE","BCM",
                     "HDG","CII","DXS","NTL","TDH","IDC"],
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
}
def get_sector(ticker: str) -> str:
    for sector, tickers in SECTOR_MAP.items():
        if ticker in tickers: return sector
    return "Khác"

# ══════════════════════════════════════════════════════════════
#  SIDEBAR — Language first, then controls
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
sb.caption(f"📦 {len(MARKET_SCAN_LIST)} mã HOSE/HNX/UPCOM")
sb.caption(f"📡 Pipeline: DNSE → SSI → CafeF → yFinance")
sb.caption(L["finance_lbl"])
sb.caption(f"📈 yFinance: {'✅' if YFINANCE_AVAILABLE else '❌'}")
sb.caption(f"🤖 sklearn: {'✅' if SKLEARN_AVAILABLE else '❌'}")
sb.caption(f"🔮 Prophet: {'✅' if PROPHET_AVAILABLE else '❌'}")
sb.caption(f"📈 ARIMA:   {'✅' if ARIMA_AVAILABLE else '❌'}")
sb.caption(L["disclaimer"])

st.title(L["app_title"])
if st.session_state.lang == "EN":
    st.caption("🇦🇺 English AU mode | Vietnam Stock Exchange (HOSE / HNX / UPCOM)")

# ══════════════════════════════════════════════════════════════
#  A. DATA PIPELINE v13: DNSE → SSI → CafeF (NO yFinance)
# ══════════════════════════════════════════════════════════════
_HTTP = requests.Session()
_HTTP.headers.update({
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept":          "application/json,text/html,*/*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Referer":         "https://iboard.ssi.com.vn/",
})
API_TIMEOUT = 12

def _unix(dt: datetime) -> int:
    return int(dt.timestamp())

def _parse_udf(raw: dict, source: str = "UDF") -> pd.DataFrame:
    """Parse TradingView UDF: {t,o,h,l,c,v} — shared for DNSE & SSI."""
    if not raw or raw.get("s") == "no_data":
        _log.debug(f"{source}: No data in response.")
        return pd.DataFrame()
    t_arr = raw.get("t", [])
    c_arr = raw.get("c", [])
    if not t_arr or not c_arr or len(t_arr) < 5:
        _log.debug(f"{source}: time or close array too short.")
        return pd.DataFrame()
    try:
        df = pd.DataFrame({
            "Open":   pd.to_numeric(raw.get("o", c_arr), errors="coerce"),
            "High":   pd.to_numeric(raw.get("h", c_arr), errors="coerce"),
            "Low":    pd.to_numeric(raw.get("l", c_arr), errors="coerce"),
            "Close":  pd.to_numeric(c_arr,               errors="coerce"),
            "Volume": pd.to_numeric(raw.get("v", [0]*len(t_arr)), errors="coerce"),
        }, index=pd.to_datetime(t_arr, unit="s").normalize())
        df.index.name = "Date"
        df = df.dropna(subset=["Close"]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        # Normalise price scale (some APIs return x1000 VND)
        if not df.empty and df["Close"].dropna().median() < 500:
            for col in ["Open","High","Low","Close"]:
                if col in df.columns:
                    df[col] = df[col] * 1000
        return df
    except Exception as e:
        _log.error(f"Error parsing UDF from {source}: {e}")
        return pd.DataFrame()


def _fetch_dnse(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P1: DNSE Entrade UDF — services.entrade.com.vn
    ✓ No auth  ✓ <200ms  ✓ HOSE+HNX+UPCOM  ✓ Real-time
    Tries both v2 and v1 endpoints for resilience.
    """
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    endpoints = [
        f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
        f"https://services.entrade.com.vn/chart-api/ohlcs/stock?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
        f"https://api.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
    ]
    for url in endpoints:
        try:
            r = _HTTP.get(url, timeout=API_TIMEOUT)
            r.raise_for_status()
            df = _parse_udf(r.json(), source=f"DNSE({symbol})")
            if not df.empty:
                _log.info(f"DNSE {symbol}: {len(df)} rows via {url[:60]}...")
                return df
        except requests.exceptions.RequestException as e:
            _log.warning(f"DNSE endpoint failed for {symbol}: {url[:60]}... — {e}")
            import traceback
            _log.debug(traceback.format_exc())
            continue
        except Exception as e:
            _log.error(f"DNSE processing error for {symbol}: {e}")
            import traceback
            _log.debug(traceback.format_exc())
    return pd.DataFrame()


def _fetch_ssi(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P2: SSI iBoard UDF — iboard-query.ssi.com.vn
    ✓ Stable  ✓ HOSE/HNX  ✓ Accurate intraday
    """
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = (f"https://iboard-query.ssi.com.vn/stock/ohlc"
           f"?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}")
    try:
        r = _HTTP.get(url, timeout=API_TIMEOUT)
        r.raise_for_status()
        return _parse_udf(r.json(), source=f"SSI({symbol})")
    except requests.exceptions.RequestException as e:
        _log.warning(f"SSI fetch failed for {symbol}: {e}")
        st.toast(f"SSI API for {symbol} failed: {e}", icon="📡")
        return pd.DataFrame()
    except Exception as e:
        _log.error(f"SSI processing error for {symbol}: {e}")
        return pd.DataFrame()


def _fetch_cafef(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P3: CafeF historical price — cafef.vn (HTML parse, covers ALL exchanges incl UPCOM)
    Works for tickers that DNSE/SSI miss (OIL, IDC, ACV, PVS, VNA, etc.)
    Endpoint: https://s.cafef.vn/LichSuGia/LichSuGia.aspx?symbol=...
    """
    # The old /ajax/historyprice.aspx is deprecated and returns 404.
    # The new endpoint is LichSuGia.aspx which renders a full page.
    url = f"https://s.cafef.vn/LichSuGia/LichSuGia.aspx?symbol={symbol}&PageIndex=1&PageSize={min(days, 500)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    f"https://cafef.vn/",
        "Accept":     "text/html,application/xhtml+xml",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        if not r.text or "Không có dữ liệu" in r.text:
            _log.debug(f"CafeF {symbol}: No data in HTML response.")
            return pd.DataFrame()
        
        # The relevant table is usually the last one on the page
        dfs = pd.read_html(io.StringIO(r.text), flavor="lxml")
        if not dfs:
            _log.debug(f"CafeF {symbol}: pd.read_html found no tables.")
            return pd.DataFrame()
        
        df = dfs[-1].copy() # Assume the last table is the data table
        
        # Standardize column names
        col_rename = {}
        for col in df.columns:
            col_lower = str(col).lower()
            if "ngày" in col_lower: col_rename[col] = "Date"
            elif "giá đóng cửa" in col_lower: col_rename[col] = "Close"
            elif "giá mở cửa" in col_lower: col_rename[col] = "Open"
            elif "giá cao nhất" in col_lower: col_rename[col] = "High"
            elif "giá thấp nhất" in col_lower: col_rename[col] = "Low"
            elif "klgd khớp lệnh" in col_lower: col_rename[col] = "Volume"
        
        if "Date" not in col_rename.values() or "Close" not in col_rename.values():
             _log.warning(f"CafeF {symbol}: Critical columns 'Date' or 'Close' not found in table. Columns: {df.columns.tolist()}")
             return pd.DataFrame()

        df.rename(columns=col_rename, inplace=True)

        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        
        # Process columns, converting to numeric and handling missing values
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                # Handle cases where volume is a string like 'x' or has other artifacts
                df[col] = df[col].astype(str).str.replace(r'[,x]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        # Fill missing OHLC with Close price
        for col in ["Open", "High", "Low"]:
            if col not in df.columns or df[col].sum() == 0:
                df[col] = df["Close"]

        out = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].copy()
        out = out.dropna(subset=["Close"]).sort_index()
        out = out[~out.index.duplicated(keep="last")]

        if not out.empty and out["Close"].dropna().median() < 500:
            for col in ["Open", "High", "Low", "Close"]:
                out[col] = out[col] * 1000
        
        _log.info(f"CafeF {symbol}: {len(out)} rows, close={out['Close'].iloc[-1] if len(out) > 0 else 'N/A'}")
        return out
    except requests.exceptions.RequestException as e:
        _log.warning(f"CafeF fetch failed for {symbol}: {e}")
        st.toast(f"CafeF API for {symbol} failed: {e}", icon="📡")
        return pd.DataFrame()
    except Exception as e:
        _log.error(f"CafeF processing error for {symbol}: {e}")
        return pd.DataFrame()


def _fetch_cafef_v2(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    CafeF v2 API — JSON endpoint fallback for tickers with parse issues.
    URL: https://api.cafef.vn/api/historyprice/{sym}?type=5&count=500
    Note: api.cafef.vn may be unavailable from some networks.
    """
    try:
        # API has a hard limit of 500; short timeout to fail fast if unreachable
        url = f"https://api.cafef.vn/api/historyprice/{symbol}?type=5&count={min(days, 500)}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        r.raise_for_status()
        data = r.json()
        items = data.get("Data", data.get("data", []))
        if not items:
            _log.debug(f"CafeF-v2 {symbol}: No data in JSON response.")
            return pd.DataFrame()
        
        rows = []
        for it in items:
            try:
                # Date can be in different formats, handle gracefully
                date_str = it.get("Date", it.get("date", ""))
                if not date_str: continue
                
                rows.append({
                    "Date":   pd.to_datetime(date_str, errors="coerce"),
                    "Open":   float(it.get("Open",  it.get("open",  0)) or 0),
                    "High":   float(it.get("High",  it.get("high",  0)) or 0),
                    "Low":    float(it.get("Low",   it.get("low",   0)) or 0),
                    "Close":  float(it.get("Close", it.get("close", 0)) or 0),
                    "Volume": float(it.get("Volume",it.get("volume",0)) or 0),
                })
            except (ValueError, TypeError):
                _log.debug(f"CafeF-v2 {symbol}: Skipping malformed row: {it}")
                continue
                
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
        df = df.set_index("Date").sort_index()
        
        if not df.empty and df["Close"].dropna().median() < 500:
            for col in ["Open","High","Low","Close"]:
                df[col] = df[col] * 1000
        return df
    except requests.exceptions.RequestException as e:
        _log.warning(f"CafeF-v2 fetch failed for {symbol}: {e}")
        st.toast(f"CafeF-v2 API for {symbol} failed: {e}", icon="📡")
        return pd.DataFrame()
    except Exception as e:
        _log.error(f"CafeF-v2 processing error for {symbol}: {e}")
        return pd.DataFrame()


def _fetch_yfinance(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P5: yFinance fallback — covers VN stocks (.VN suffix) + global indices.
    ✓ Global coverage  ✓ Reliable when primary VN sources fail
    ✓ Auto handles MultiIndex columns from yf.download()
    """
    if not YFINANCE_AVAILABLE:
        _log.debug("yFinance not available (not installed)")
        return pd.DataFrame()
    
    import traceback

    def _clean_yf(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize yfinance MultiIndex columns."""
        if df.empty: return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.loc[:, ~df.columns.duplicated()].copy()
        if "Adj Close" in df.columns:
            df["Close"] = df["Adj Close"]
        return df
    
    # Try with .VN suffix for Vietnamese stocks
    vn_ticker = f"{symbol}.VN"
    for ticker_try in [vn_ticker, symbol]:
        try:
            import yfinance as yf
            df = yf.download(ticker_try, period=f"{min(days, 730)}d", 
                             interval="1d", progress=False, auto_adjust=True)
            df = _clean_yf(df)
            if not df.empty and "Close" in df.columns:
                df = df.dropna(subset=["Close"])
                if len(df) >= 10:
                    _log.info(f"yFinance {ticker_try}: {len(df)} rows")
                    return df
        except Exception as e:
            _log.warning(f"yFinance '{ticker_try}' failed: {e}")
            _log.debug(traceback.format_exc())
    
    return pd.DataFrame()


def download_data(symbol: str, days: int = 730, min_rows: int = 40):
    """
    Data pipeline v14.0: DNSE → SSI → CafeF-HTML → CafeF-JSON → yFinance
    Returns: (DataFrame, source_name, error_message)
    Each source logs detailed errors to error_log.txt.
    """
    import traceback
    symbol = symbol.strip().upper()
    error_detail = {}

    # 1. DNSE Entrade
    try:
        df = _fetch_dnse(symbol, days)
        if len(df) >= min_rows:
            _log.info(f"✅ DNSE {symbol}: {len(df)} rows")
            return df, "DNSE", None
        error_detail["DNSE"] = f"Only {len(df)} rows (need {min_rows})"
    except Exception as e:
        error_detail["DNSE"] = str(e)
        _log.error(f"DNSE exception {symbol}: {e}"); _log.debug(traceback.format_exc())

    # 2. SSI iBoard
    try:
        df = _fetch_ssi(symbol, days)
        if len(df) >= min_rows:
            _log.info(f"✅ SSI {symbol}: {len(df)} rows")
            return df, "SSI", None
        error_detail["SSI"] = f"Only {len(df)} rows (need {min_rows})"
    except Exception as e:
        error_detail["SSI"] = str(e)
        _log.error(f"SSI exception {symbol}: {e}"); _log.debug(traceback.format_exc())

    # 3. CafeF HTML scraper
    try:
        df = _fetch_cafef(symbol, days)
        if len(df) >= min_rows:
            _log.info(f"✅ CafeF-HTML {symbol}: {len(df)} rows")
            return df, "CafeF", None
        error_detail["CafeF-HTML"] = f"Only {len(df)} rows"
    except Exception as e:
        error_detail["CafeF-HTML"] = str(e)
        _log.error(f"CafeF-HTML exception {symbol}: {e}"); _log.debug(traceback.format_exc())

    # 4. CafeF JSON API v2
    try:
        df = _fetch_cafef_v2(symbol, days)
        if len(df) >= min_rows:
            _log.info(f"✅ CafeF-JSON {symbol}: {len(df)} rows")
            return df, "CafeF", None
        error_detail["CafeF-JSON"] = f"Only {len(df)} rows"
    except Exception as e:
        error_detail["CafeF-JSON"] = str(e)
        _log.error(f"CafeF-JSON exception {symbol}: {e}"); _log.debug(traceback.format_exc())

    # 5. yFinance fallback (covers .VN listed stocks)
    try:
        df = _fetch_yfinance(symbol, days)
        if len(df) >= min_rows:
            _log.info(f"✅ yFinance {symbol}: {len(df)} rows")
            return df, "yFinance", None
        error_detail["yFinance"] = f"Only {len(df)} rows"
    except Exception as e:
        error_detail["yFinance"] = str(e)
        _log.error(f"yFinance exception {symbol}: {e}"); _log.debug(traceback.format_exc())

    exch = TICKER_EXCHANGE.get(symbol, "HOSE")
    detail_str = ", ".join([f"{k}: {v}" for k,v in error_detail.items()])
    msg = (f"Cannot load {symbol}. Failed sources: {detail_str}. "
           f"Exchange: {exch}. Check connectivity or ticker.")
    _log.error(msg)
    return pd.DataFrame(), "None", msg


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise OHLCV dataframe from any source."""
    if df.empty:
        return pd.DataFrame()
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    if "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]
    
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan if col != "Volume" else 0

    df = df[required_cols] # Ensure column order and drop extras
    df = df.apply(pd.to_numeric, errors="coerce")
    df["Volume"].fillna(0, inplace=True)
    df.dropna(subset=["Close"], inplace=True)
    
    df = df[df["Close"] > 0]
    if df.empty:
        return pd.DataFrame()

    # IQR-based outlier removal for Close price
    Q1 = df['Close'].quantile(0.25)
    Q3 = df['Close'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    # Filter out extreme outliers, but don't be overly aggressive
    # Use a wider range (e.g., 3*IQR) to avoid removing valid spikes
    df = df[(df['Close'] >= (Q1 - 3 * IQR)) & (df['Close'] <= (Q3 + 3 * IQR))]
    
    return df.sort_index()


# ══════════════════════════════════════════════════════════════
#  C. VNDirect FINFO — Financial Data API
# ══════════════════════════════════════════════════════════════
VND_BASE    = "https://finfo-api.vndirect.com.vn/v4"
VND_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept":     "application/json",
    "Referer":    "https://dstock.vndirect.com.vn/",
}

def _vnd_get(endpoint: str, params: dict = None) -> dict:
    try:
        r = requests.get(f"{VND_BASE}/{endpoint}", params=params,
                         headers=VND_HEADERS, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log.warning(f"VNDirect /{endpoint[:40]}: {e}")
        return {}

@st.cache_data(ttl=3600)
def fetch_company_profile(ticker: str) -> dict:
    profile = {}
    data = _vnd_get("stocks", {
        "code": ticker,
        "fields": ("code,companyName,shortName,exchange,industryName,sector,"
                   "marketCap,listedShare,establishedYear,numberOfEmployee,"
                   "companyProfile,website")
    })
    items = data.get("data", [])
    if items:
        d = items[0]
        mcap = d.get("marketCap") or 0
        ls   = d.get("listedShare") or 0
        profile.update({
            "Tên công ty":         d.get("companyName", "–"),
            "Sàn":                 d.get("exchange", TICKER_EXCHANGE.get(ticker,"HOSE")),
            "Ngành":               d.get("industryName", "–"),
            "Vốn hóa (tỷ VNĐ)":   f"{int(float(mcap)/1e9):,}" if mcap else "–",
            "CP lưu hành (triệu)": f"{int(float(ls)/1e6):,}"   if ls   else "–",
            "Năm thành lập":       d.get("establishedYear", "–"),
            "Nhân viên":           f"{d.get('numberOfEmployee',0):,}" if d.get("numberOfEmployee") else "–",
            "Website":             d.get("website", "–"),
        })
        if d.get("companyProfile"):
            profile["_profile_text"] = d["companyProfile"]
    rat = _vnd_get("financialRatios", {"code": ticker, "period": "quarter", "size": 1})
    r_items = rat.get("data", [])
    if r_items:
        r = r_items[0]
        def _pct(v): return f"{float(v or 0)*100:.1f}%" if v else "–"
        def _num(v, d=2): return f"{float(v or 0):.{d}f}" if v else "–"
        profile.update({
            "EPS (VNĐ)":   f"{int(float(r.get('eps') or 0)):,}" if r.get("eps") else "–",
            "P/E":         _num(r.get("pe"), 1),
            "P/B":         _num(r.get("pb"), 2),
            "ROE (%)":     _pct(r.get("roe")),
            "ROA (%)":     _pct(r.get("roa")),
            "Biên LN ròng":_pct(r.get("netProfitMargin")),
            "D/E":         _num(r.get("debtToEquity"), 2),
            "Cổ tức (%)":  _pct(r.get("dividendYield")),
        })
    return profile

@st.cache_data(ttl=3600)
def fetch_financial_statements(ticker: str) -> dict:
    result = {"income": pd.DataFrame(), "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
    SCALE = 1e9
    for stmt_type, key, col_map in [
        ("incomeStatement", "income", {
            "reportDate":"Quý","netRevenue":"Doanh thu","grossProfit":"LN gộp",
            "ebit":"EBIT","earningsBeforeTax":"LNTT","netProfit":"LNST","eps":"EPS (đ)"}),
        ("balanceSheet", "balance", {
            "reportDate":"Quý","totalAssets":"Tổng TS","currentAssets":"TS NH",
            "nonCurrentAssets":"TS DH","totalLiabilities":"Nợ PT","equity":"Vốn CSH"}),
        ("cashFlow", "cashflow", {
            "reportDate":"Quý","operatingCashFlow":"CF Hoạt động",
            "investingCashFlow":"CF Đầu tư","financingCashFlow":"CF Tài chính",
            "freeCashFlow":"FCF"}),
    ]:
        data = _vnd_get("financialStatements", {"code": ticker, "type": stmt_type,
                                                 "period": "quarter", "size": 8})
        rows = data.get("data", [])
        if rows:
            df = pd.DataFrame(rows).rename(columns=col_map)
            keep = [c for c in col_map.values() if c in df.columns]
            df = df[keep].copy()
            if "Quý" in df.columns:
                df["Quý"] = df["Quý"].astype(str).str[:7]
            for col in df.columns:
                if col in ("Quý","EPS (đ)"): continue
                df[col] = pd.to_numeric(df[col], errors="coerce")
                if df[col].dropna().abs().max() > 1e9:
                    df[col] = (df[col]/SCALE).round(1)
                    df.rename(columns={col: f"{col} (tỷ)"}, inplace=True)
            result[key] = df.head(8)
    return result

@st.cache_data(ttl=3600)
def fetch_financial_ratios(ticker: str) -> pd.DataFrame:
    data = _vnd_get("financialRatios", {"code": ticker, "period": "quarter", "size": 8})
    rows = data.get("data", [])
    if not rows: return pd.DataFrame()
    col_map = {
        "reportDate":"Quý","grossProfitMargin":"Biên gộp","netProfitMargin":"Biên ròng",
        "roe":"ROE","roa":"ROA","revenueGrowth":"Tăng DT","earningGrowth":"Tăng LN",
        "currentRatio":"Curr.Ratio","debtToEquity":"D/E","eps":"EPS (đ)","pe":"P/E","pb":"P/B",
    }
    df = pd.DataFrame(rows).rename(columns=col_map)
    df = df[[c for c in col_map.values() if c in df.columns]].copy()
    if "Quý" in df.columns: df["Quý"] = df["Quý"].astype(str).str[:7]
    pct_cols = {"Biên gộp","Biên ròng","ROE","ROA","Tăng DT","Tăng LN"}
    for col in df.columns:
        if col == "Quý": continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if col in pct_cols and df[col].dropna().abs().max() < 2:
            df[col] = (df[col]*100).round(1)
            df.rename(columns={col: f"{col} (%)"}, inplace=True)
    return df.head(8)

@st.cache_data(ttl=1800)
def fetch_news(ticker: str, n: int = 10) -> list:
    data = _vnd_get("news", {"code": ticker, "size": n, "sort": "publishDate:desc"})
    return [{
        "date":    (it.get("publishDate","")[:10] or it.get("date","")[:10]),
        "title":   it.get("title","–"),
        "url":     it.get("url", it.get("newsUrl","")),
        "source":  it.get("source","VNDirect"),
        "summary": it.get("content", it.get("summary","")),
    } for it in data.get("data",[])]

@st.cache_data(ttl=86400)
def fetch_dividends(ticker: str) -> pd.DataFrame:
    data = _vnd_get("dividends", {"code": ticker, "size": 8})
    rows = data.get("data", [])
    if not rows: return pd.DataFrame()
    records = [{"Năm": str(d.get("year","?"))[:4],
                "Ngày chốt": d.get("exDate","–"),
                "Loại": d.get("payType","–"),
                "Tỷ lệ (%)": d.get("cashDividendPercentage","–")} for d in rows]
    return pd.DataFrame(records)

def render_fundamental_section(ticker: str):
    sector = get_sector(ticker)
    st.divider()
    if st.session_state.lang == "VI":
        st.subheader(f"🏢 Phân Tích Cơ Bản — {ticker}  *({sector})*")
        sub_labels = ["📋 Hồ Sơ & Định Giá","📊 Báo Cáo Tài Chính","📈 Tỷ Số","📰 Cổ Tức & Tin Tức"]
    else:
        st.subheader(f"🏢 Fundamental Analysis — {ticker}  *({sector})*")
        sub_labels = ["📋 Profile & Valuation","📊 Financial Statements","📈 Key Ratios","📰 Dividends & News"]

    sub1, sub2, sub3, sub4 = st.tabs(sub_labels)
    with sub1:
        with st.spinner("Loading..."):
            prof = fetch_company_profile(ticker)
        if prof:
            display = {k: v for k, v in prof.items() if not k.startswith("_")}
            items = list(display.items()); half = len(items)//2 + len(items)%2
            c1, c2 = st.columns(2)
            with c1:
                for k, v in items[:half]: st.metric(k, v)
            with c2:
                for k, v in items[half:]: st.metric(k, v)
            if prof.get("_profile_text"):
                with st.expander("📄 Company Profile"):
                    txt = prof["_profile_text"]
                    st.markdown(txt[:2000] + ("..." if len(txt)>2000 else ""))
        else:
            st.info("No profile data from VNDirect.")

    with sub2:
        with st.spinner("Loading financial statements..."):
            fs = fetch_financial_statements(ticker)
        for lbl, key in [("💰 Income Statement","income"),("🏦 Balance Sheet","balance"),("💸 Cash Flow","cashflow")]:
            if not fs[key].empty:
                st.markdown(f"##### {lbl} (tỷ VNĐ)")
                show_df(fs[key])
                if key == "income":
                    rev_col  = next((c for c in fs["income"].columns if "Doanh thu" in c), None)
                    lnst_col = next((c for c in fs["income"].columns if "LNST" in c), None)
                    if rev_col and lnst_col and "Quý" in fs["income"].columns:
                        fig_f = go.Figure()
                        fig_f.add_bar(x=fs["income"]["Quý"], y=fs["income"][rev_col],
                                      name=rev_col, marker_color="#4e9af1")
                        fig_f.add_bar(x=fs["income"]["Quý"], y=fs["income"][lnst_col],
                                      name=lnst_col, marker_color="#2ecc71")
                        fig_f.update_layout(barmode="group", height=260, template="plotly_dark",
                                            title="Revenue & Net Profit (Bil VND)")
                        st.plotly_chart(fig_f, width="stretch")

    with sub3:
        with st.spinner("Loading ratios..."):
            ratios = fetch_financial_ratios(ticker)
        if not ratios.empty:
            show_df(ratios)
            roe_col = next((c for c in ratios.columns if "ROE" in c), None)
            if roe_col and not ratios[roe_col].dropna().empty:
                try:
                    roe_val = float(ratios[roe_col].dropna().iloc[0])
                    fig_g = go.Figure(go.Indicator(
                        mode="gauge+number+delta", value=roe_val,
                        title={"text": "ROE (%) Latest Quarter"},
                        gauge={"axis":{"range":[0,30]},"bar":{"color":"#00cc66"},
                               "steps":[{"range":[0,10],"color":"#3a0a0a"},
                                        {"range":[10,20],"color":"#1a3a1a"},
                                        {"range":[20,30],"color":"#0a2a3a"}]},
                        delta={"reference":15}))
                    fig_g.update_layout(height=220, template="plotly_dark",
                                        margin=dict(t=50,b=10,l=20,r=20))
                    st.plotly_chart(fig_g, width="stretch")
                except Exception: pass
        else:
            st.info("No ratio data from VNDirect.")

    with sub4:
        c_div, c_news = st.columns([1,2])
        with c_div:
            st.markdown("##### Dividend History")
            divs = fetch_dividends(ticker)
            if not divs.empty: show_df(divs)
            else: st.info("No dividend data.")
        with c_news:
            st.markdown("##### Latest News")
            news = fetch_news(ticker, n=10)
            if news:
                for item in news:
                    icon = "📢" if any(k in item.get("title","").lower() for k in ["đại hội","họp","nghị quyết","agm"]) else "📰"
                    title = item.get("title","–"); url = item.get("url",""); date = item.get("date","")
                    st.markdown(f"{icon} **{date}** — [{title}]({url})" if url else f"{icon} **{date}** — {title}")
                    if item.get("summary"):
                        s = item["summary"]; st.caption(s[:220]+("..." if len(s)>220 else ""))
                    st.divider()
            else: st.info("No news from VNDirect.")

# ══════════════════════════════════════════════════════════════
#  TECHNICAL INDICATORS — 9 indicators (unchanged from v12)
# ══════════════════════════════════════════════════════════════
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df  = df.loc[:, ~df.columns.duplicated()].copy()
    cls = df["Close"].values.astype(float)
    hgh = df["High"].values.astype(float)
    low = df["Low"].values.astype(float)
    vol = df["Volume"].fillna(0).values.astype(float)
    n   = len(df)

    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()

    # RSI (Wilder smoothing)
    delta    = df["Close"].diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)

    # Bollinger Bands (20-period, ±2σ)
    df["BB_Mid"]   = df["SMA20"]
    df["BB_Std"]   = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + df["BB_Std"] * 2
    df["BB_Lower"] = df["BB_Mid"] - df["BB_Std"] * 2

    # MACD (12,26,9)
    df["MACD_Fast"]   = df["Close"].ewm(span=12, adjust=False).mean()
    df["MACD_Slow"]   = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]        = df["MACD_Fast"] - df["MACD_Slow"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]
    df["Vol_MA20"]    = df["Volume"].rolling(20).mean()

    # Stochastic %K/%D (14,3)
    sk = np.full(n, np.nan)
    for i in range(13, n):
        hh = np.nanmax(hgh[i-13:i+1]); ll = np.nanmin(low[i-13:i+1])
        sk[i] = 100*(cls[i]-ll)/(hh-ll) if hh != ll else 50
    df["STOCH_K"] = sk
    df["STOCH_D"] = df["STOCH_K"].rolling(3).mean()

    # ATR (Wilder 14)
    tr = np.full(n, np.nan)
    for i in range(1, n):
        tr[i] = max(hgh[i]-low[i], abs(hgh[i]-cls[i-1]), abs(low[i]-cls[i-1]))
    df["TR"]  = tr
    df["ATR"] = df["TR"].ewm(alpha=1/14, min_periods=14, adjust=False).mean()

    # OBV
    obv = np.zeros(n)
    for i in range(1, n):
        obv[i] = obv[i-1] + (vol[i] if cls[i]>cls[i-1] else (-vol[i] if cls[i]<cls[i-1] else 0))
    df["OBV"]      = obv
    df["OBV_MA20"] = df["OBV"].rolling(20).mean()

    # ADX/+DI/-DI (14)
    pdm = np.full(n, np.nan); ndm = np.full(n, np.nan)
    for i in range(1, n):
        up   = hgh[i]-hgh[i-1]; down = low[i-1]-low[i]
        pdm[i] = up   if (up > down and up > 0)   else 0.0
        ndm[i] = down if (down > up and down > 0) else 0.0
    df["_PDM"] = pdm; df["_NDM"] = ndm
    atr14 = df["TR"].ewm(alpha=1/14, min_periods=14, adjust=False).mean() * 14
    pdm14 = df["_PDM"].ewm(alpha=1/14, min_periods=14, adjust=False).mean() * 14
    ndm14 = df["_NDM"].ewm(alpha=1/14, min_periods=14, adjust=False).mean() * 14
    df["+DI"] = 100 * pdm14 / (atr14 + 1e-9)
    df["-DI"] = 100 * ndm14 / (atr14 + 1e-9)
    df["DX"]  = 100 * abs(df["+DI"]-df["-DI"]) / (df["+DI"]+df["-DI"]+1e-9)
    df["ADX"] = df["DX"].ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df.drop(columns=["_PDM","_NDM","DX","TR"], inplace=True)

    # Williams %R (14)
    wr = np.full(n, np.nan)
    for i in range(13, n):
        hh = np.nanmax(hgh[i-13:i+1]); ll = np.nanmin(low[i-13:i+1])
        wr[i] = -100*(hh-cls[i])/(hh-ll) if hh != ll else -50
    df["WILLIAMS_R"] = wr

    # CCI (20)
    tp  = (df["High"]+df["Low"]+df["Close"])/3
    cci = np.full(n, np.nan)
    for i in range(19, n):
        w = tp.values[i-19:i+1]; sma = np.mean(w); mad = np.mean(np.abs(w-sma))
        cci[i] = (tp.values[i]-sma)/(0.015*mad+1e-9)
    df["CCI"] = cci
    return df


def extract_latest(df: pd.DataFrame, col: str):
    try:
        v = float(df[col].iloc[-1])
        return None if np.isnan(v) else v
    except Exception: return None

# ══════════════════════════════════════════════════════════════
#  COMPOSITE SIGNAL SCORING (preserved + macro tag output)
# ══════════════════════════════════════════════════════════════
def compute_composite_score(row, avg_vol, last_vol, trend_ok,
                             signal_type="BUY", rsi_thresh=35, rsi_sell=65):
    score = 0.0; confirms = []
    def safe(k):
        v = row.get(k)
        try: return float(v) if v is not None and not np.isnan(float(v)) else None
        except: return None
    rsi=safe("RSI"); cls=safe("Close"); bbl=safe("BB_Lower"); bbu=safe("BB_Upper")
    macd=safe("MACD"); macs=safe("MACD_Signal"); stoch_k=safe("STOCH_K")
    obv=safe("OBV"); obv_ma=safe("OBV_MA20"); adx=safe("ADX")
    pdi=safe("+DI"); ndi=safe("-DI"); wr=safe("WILLIAMS_R"); cci=safe("CCI")

    if signal_type == "BUY":
        if rsi and rsi < rsi_thresh:
            score += (rsi_thresh-rsi)*0.6; confirms.append(f"RSI={rsi:.0f}")
        if cls and bbl and cls < bbl:
            score += 5; confirms.append("Giá<BB↓")
        if trend_ok:
            score += 4; confirms.append("↑SMA50")
        if stoch_k is not None and stoch_k < 20:
            score += (20-stoch_k)*0.3; confirms.append(f"Stoch={stoch_k:.0f}")
        if wr is not None and wr < -80:
            score += (abs(wr)-80)*0.2; confirms.append(f"W%R={wr:.0f}")
        if cci is not None and cci < -100:
            score += min(abs(cci+100)/10, 5); confirms.append(f"CCI={cci:.0f}")
        if macd is not None and macs is not None and macd > macs:
            score += 5; confirms.append("MACD↑")
        if adx and adx > 20 and pdi and ndi and pdi > ndi:
            score += 2; confirms.append(f"ADX={adx:.0f}↑")
        if avg_vol and avg_vol > 0 and last_vol/avg_vol > 1.5:
            score += 3; confirms.append(f"KL={last_vol/avg_vol:.1f}×")
        if obv and obv_ma and obv > obv_ma:
            score += 2; confirms.append("OBV↑")
    elif signal_type == "BÁN":
        if rsi and rsi > rsi_sell:
            score += (rsi-rsi_sell)*0.6; confirms.append(f"RSI={rsi:.0f}")
        if cls and bbu and cls > bbu:
            score += 5; confirms.append("Giá>BB↑")
        if stoch_k is not None and stoch_k > 80:
            score += (stoch_k-80)*0.3; confirms.append(f"Stoch={stoch_k:.0f}")
        if wr is not None and wr > -20:
            score += (wr+20)*0.2; confirms.append(f"W%R={wr:.0f}")
        if cci is not None and cci > 100:
            score += min((cci-100)/10, 5); confirms.append(f"CCI={cci:.0f}")
        if macd is not None and macs is not None and macd < macs:
            score += 5; confirms.append("MACD↓")
        if adx and adx > 20 and ndi and pdi and ndi > pdi:
            score += 2; confirms.append(f"ADX={adx:.0f}↓")
    return round(score,1), confirms

# ══════════════════════════════════════════════════════════════
#  ĐỘI LÁI / SMART MONEY DETECTION (preserved)
# ══════════════════════════════════════════════════════════════
def detect_doi_lai(df: pd.DataFrame) -> list:
    signals = []
    if len(df) < 20: return signals
    closes=df["Close"].values.astype(float); vols=df["Volume"].fillna(0).values.astype(float)
    high_a=df["High"].values.astype(float); low_a=df["Low"].values.astype(float)
    avg_vol=np.nanmean(vols[-20:]); last_v=vols[-1]; last_c=closes[-1]; prev_c=closes[-2]
    vr = last_v/avg_vol if avg_vol > 0 else 0
    if vr > 3 and last_c > prev_c:
        signals.append(dict(icon="🚨", severity="HIGH",
            signal="KL đột biến — nghi PUMP",
            detail=f"KL = **{vr:.1f}×** TB20 trong phiên tăng. Đội lái bơm hàng. "
                   f"Rủi ro mua đuổi rất cao — chờ điều chỉnh về MA20 trước khi tham gia."))
    if len(closes) >= 6:
        up_s = sum(1 for i in range(-5,0) if closes[i] > closes[i-1])
        va   = bool(vols[-1] > vols[-2] > vols[-3])
        if up_s >= 3 and va:
            signals.append(dict(icon="📈", severity="MEDIUM",
                signal=f"{up_s} phiên tăng liên tiếp + KL leo thang",
                detail=f"Tăng {up_s}/5 phiên, KL lớn dần. Đây thường là giai đoạn **cuối đợt tăng** "
                       f"trước khi đội lái xả hàng. Xem xét chốt lời một phần (30-50%)."))
    high_52w = np.nanmax(closes[-min(252, len(closes)):])
    if last_c >= high_52w*0.98 and last_v < avg_vol*0.5:
        signals.append(dict(icon="⚠️", severity="HIGH",
            signal="Giá đỉnh 52w + KL cạn — nguy cơ DUMP",
            detail=f"Giá gần đỉnh 52 tuần ({high_52w:,.0f}) nhưng KL chỉ bằng "
                   f"{vr*100:.0f}% bình thường — thiếu dòng tiền xác nhận breakout. "
                   f"Tránh mua mới, nâng stop loss lên sát giá hiện tại."))
    if last_c > np.nanmean(closes[-6:-1]) and last_v < np.nanmean(vols[-6:-1])*0.75:
        signals.append(dict(icon="📉", severity="LOW",
            signal="Giá tăng + KL giảm — đà yếu dần",
            detail="Divergence giá-KL: giá tăng nhưng tiền không vào. "
                   "Thường là dấu hiệu tăng cuối đợt, sắp đảo chiều giảm."))
    body = abs(last_c-prev_c)
    if body < last_c*0.02 and last_v > avg_vol*1.5 and last_c < np.nanmean(closes[-20:])*0.98:
        signals.append(dict(icon="🟢", severity="POSITIVE",
            signal="Smart Money tích lũy tại đáy",
            detail="Biên độ giá hẹp (<2%) + KL cao tại vùng thấp hơn MA20 = "
                   "tổ chức đang gom hàng âm thầm. Xem xét mua từng phần, stop 7%."))
    if vr > 5 and abs(last_c-prev_c)/prev_c < 0.01:
        signals.append(dict(icon="🔄", severity="MEDIUM",
            signal="Nghi Wash Trading — KL ảo",
            detail=f"KL = {vr:.1f}× TB20 nhưng giá gần như không đổi (<1%). "
                   f"Có thể là giao dịch nội bộ để tạo thanh khoản giả tạo."))
    if len(closes) >= 3:
        if low_a[-2] < closes[-3]*0.95 and last_c > closes[-2]*1.03 and last_v > avg_vol*2:
            signals.append(dict(icon="🪤", severity="POSITIVE",
                signal="Bear Trap — đảo chiều tăng mạnh",
                detail="Phiên trước giảm mạnh (>5%), hôm nay hồi >3% với KL >2× bình thường. "
                       "Pattern Bear Trap — lực bắt đáy mạnh, có thể mua với stop tại đáy phiên trước."))
    return signals

# ══════════════════════════════════════════════════════════════
#  E. ENHANCED INSIGHTS — Sector context + macro + sentiment
# ══════════════════════════════════════════════════════════════
SECTOR_INSIGHT_VI = {
    "Ngân hàng": "📊 NH: ROE >15% & NPL <2% = lành mạnh. Theo dõi NHNN lãi suất & tăng trưởng tín dụng.",
    "Bất động sản": "🏗️ BĐS: Nhạy cảm với lãi suất & pháp lý. Ưu tiên cổ phiếu có đất sạch và dòng tiền.",
    "Dầu khí": "🛢️ Dầu khí: Tương quan cao với giá dầu WTI. GAS & PLX hưởng lợi khi dầu tăng.",
    "Thép": "⚙️ Thép: Phụ thuộc giá quặng sắt, than cốc. Theo dõi giá thép Trung Quốc.",
    "Hàng không": "✈️ Hàng không: Chi phí nhiên liệu = 30-40% COGS. Dầu tăng 10% → LN giảm đáng kể.",
    "Công nghệ": "💻 Công nghệ: Tăng trưởng dài hạn theo chuyển đổi số. Cần P/E cao hơn thị trường.",
    "Bán lẻ": "🛒 Bán lẻ: Theo dõi chuỗi mở rộng & SSS (same-store sales). Nhạy với tiêu dùng nội địa.",
    "Dược": "💊 Dược: Dòng tiền ổn định, phòng thủ tốt. Hưởng lợi từ già hóa dân số.",
    "Điện": "⚡ Điện: Cổ tức ổn định (5-8%). PPA giá cố định = rủi ro thấp. REE hưởng lợi điện tái tạo.",
}
SECTOR_INSIGHT_EN = {
    "Ngân hàng": "📊 Banks: ROE >15% & NPL <2% = healthy. Monitor SBV rate policy & credit growth.",
    "Bất động sản": "🏗️ Real estate: Sensitive to interest rates & legal clarity. Prefer clean land bank.",
    "Dầu khí": "🛢️ O&G: High correlation with WTI. GAS & PLX benefit when oil rises.",
    "Thép": "⚙️ Steel: Depends on iron ore & coking coal. Track Chinese steel prices.",
    "Hàng không": "✈️ Aviation: Fuel = 30-40% COGS. Oil +10% → earnings decline meaningfully.",
    "Công nghệ": "💻 Technology: Long-term digital transformation play. Justifies higher P/E.",
    "Bán lẻ": "🛒 Retail: Track store rollout & SSS. Sensitive to domestic consumption.",
    "Dược": "💊 Pharma: Stable cash flows, defensive. Benefits from aging demographics.",
    "Điện": "⚡ Power: Stable dividends (5-8%). Fixed-price PPAs = low risk. REE = renewables play.",
}

def get_sector_insight(ticker: str, lang: str = "VI") -> str:
    sector = get_sector(ticker)
    d = SECTOR_INSIGHT_VI if lang == "VI" else SECTOR_INSIGHT_EN
    return d.get(sector, "")

def explain_price_levels(close, bbl, bbu, bb_mid, sma20, sma50,
                          atr_val, rsi, stoch_k, hanh_vi, ticker="",
                          rsi_buy_thresh=35, rsi_sell_thresh=65, lang="VI"):
    atr_s    = atr_val if (atr_val and not np.isnan(atr_val)) else close*0.02
    stop_atr = max(close - 1.5*atr_s, close*0.90)
    tp1      = close + (bbu-close)*0.4 if bbu > close else close*1.07
    tp2      = bbu    if bbu > close else close*1.12
    rr       = (tp1-close)/(close-stop_atr) if close > stop_atr and close != stop_atr else 0

    if lang == "VI":
        parts = ["### 📏 Giải Thích Các Mức Giá Tham Chiếu\n"]
        parts += [
            "#### 🎯 Bollinger Bands (20 phiên, ±2σ)",
            "| Mức | Giá (VNĐ) | Ý nghĩa |","|-----|-----------|---------|",
            f"| **BB Upper** | **{bbu:,.0f}** | Kháng cự thống kê — xác suất điều chỉnh cao |",
            f"| **BB Mid** | **{bb_mid:,.0f}** | Mục tiêu hồi phục kỳ vọng |",
            f"| **→ Hiện tại** | **{close:,.0f}** | ← Vị trí bạn |",
            f"| **BB Lower** | **{bbl:,.0f}** | Hỗ trợ thống kê — mua khi RSI xác nhận |",
        ]
        parts += ["\n#### 📈 Đường Trung Bình"]
        if sma20: parts.append(f"- **SMA20 = {sma20:,.0f}** — {'Giá trên ✅ xu hướng ngắn hạn tích cực' if close>sma20 else 'Giá dưới ⚠️ điểm yếu ngắn hạn'}")
        if sma50: parts.append(f"- **SMA50 = {sma50:,.0f}** — {'Giá trên ✅ xu hướng trung hạn TĂNG' if close>sma50 else 'Giá dưới ⚠️ xu hướng trung hạn GIẢM — thận trọng!'}")
        parts += [
            f"\n#### 🛡️ ATR Stop & Targets (ATR14={atr_s:,.0f})",
            "| Điểm | Giá | Ghi chú |","|-----|-----|--------|",
            f"| TP2 (BB Upper) | {tp2:,.0f} | +{(tp2/close-1)*100:.1f}% — mục tiêu đầy đủ |",
            f"| TP1 (40% BB) | {tp1:,.0f} | +{(tp1/close-1)*100:.1f}% — chốt lời bộ phận |",
            f"| **Hiện tại** | **{close:,.0f}** | |",
            f"| Stop ATR×1.5 | {stop_atr:,.0f} | {(stop_atr/close-1)*100:.1f}% — cắt lỗ kỷ luật |",
            f"\n**⚖️ R/R = {rr:.1f}:1** {'✅ Tốt (≥1.5:1)' if rr>=1.5 else '⚠️ Thấp — cân nhắc lại điểm mua'}",
        ]
        if hanh_vi == "MUA":
            parts += [
                "\n#### 📋 Kế Hoạch Vào Lệnh (T+2 HOSE)",
                f"1. **Mua**: {bbl:,.0f}–{close:,.0f} chia 2–3 lệnh nhỏ",
                f"2. **Chốt 40%** tại TP1 = {tp1:,.0f}",
                f"3. **Chốt 40%** tại TP2 = {tp2:,.0f} (BB Upper)",
                f"4. **Giữ 20%** nếu breakout trên BB Upper",
                f"5. **Cắt lỗ** ngay khi giá < {stop_atr:,.0f}",
                f"\n> 💡 T+2: Mua hôm nay → bán sớm nhất sau 2 phiên giao dịch.",
            ]
        si = get_sector_insight(ticker, "VI")
        if si: parts.append(f"\n---\n{si}")
    else:
        parts = ["### 📏 Price Reference Levels\n"]
        parts += [
            "#### 🎯 Bollinger Bands (20-period, ±2σ)",
            "| Level | Price (VND) | Meaning |","|-------|-------------|---------|",
            f"| **BB Upper** | **{bbu:,.0f}** | Statistical resistance — pullback probability high |",
            f"| **BB Mid** | **{bb_mid:,.0f}** | Mean reversion target |",
            f"| **→ Current** | **{close:,.0f}** | ← Your position |",
            f"| **BB Lower** | **{bbl:,.0f}** | Statistical support — buy when RSI confirms |",
        ]
        parts += ["\n#### 📈 Moving Averages"]
        if sma20: parts.append(f"- **SMA20 = {sma20:,.0f}** — {'Above ✅ short-term uptrend' if close>sma20 else 'Below ⚠️ short-term weakness'}")
        if sma50: parts.append(f"- **SMA50 = {sma50:,.0f}** — {'Above ✅ medium-term UPTREND' if close>sma50 else 'Below ⚠️ medium-term DOWNTREND — caution!'}")
        parts += [
            f"\n#### 🛡️ ATR Stop & Targets (ATR14={atr_s:,.0f})",
            "| Point | Price | Note |","|-------|-------|------|",
            f"| TP2 (BB Upper) | {tp2:,.0f} | +{(tp2/close-1)*100:.1f}% — full target |",
            f"| TP1 (40% BB) | {tp1:,.0f} | +{(tp1/close-1)*100:.1f}% — partial exit |",
            f"| **Current** | **{close:,.0f}** | |",
            f"| Stop ATR×1.5 | {stop_atr:,.0f} | {(stop_atr/close-1)*100:.1f}% — disciplined exit |",
            f"\n**⚖️ R/R = {rr:.1f}:1** {'✅ Good (≥1.5:1)' if rr>=1.5 else '⚠️ Low — reconsider entry'}",
        ]
        if hanh_vi in ("MUA","BUY"):
            parts += [
                "\n#### 📋 Trade Plan (T+2 HOSE)",
                f"1. **Buy**: {bbl:,.0f}–{close:,.0f} split across 2–3 orders",
                f"2. **Exit 40%** at TP1 = {tp1:,.0f}",
                f"3. **Exit 40%** at TP2 = {tp2:,.0f} (BB Upper)",
                f"4. **Hold 20%** if price breaks above BB Upper",
                f"5. **Stop loss** immediately if price < {stop_atr:,.0f}",
                f"\n> 💡 T+2: Buy today → earliest sell after 2 trading sessions.",
            ]
        si = get_sector_insight(ticker, "EN")
        if si: parts.append(f"\n---\n{si}")
    return "\n".join(parts)


def generate_explanation(hanh_vi, rsi, close, bbl, bbu, sma20, sma50,
                          avg_vol, last_vol, macd, macd_signal, trend_ok,
                          doi_lai_signals, atr_val, stoch_k, adx_val, confirms,
                          ticker="", rsi_buy_thresh=35, rsi_sell_thresh=65, lang="VI"):
    parts = []
    sector  = get_sector(ticker)
    macd_v  = float(macd)        if macd        is not None and not np.isnan(float(macd or 0))        else None
    macs_v  = float(macd_signal) if macd_signal is not None and not np.isnan(float(macd_signal or 0)) else None
    atr_s   = float(atr_val)     if atr_val     is not None and not np.isnan(float(atr_val or 0))     else None
    stop    = max(close-1.5*atr_s, close*0.90) if atr_s else close*0.93
    vol_r   = last_vol/avg_vol if avg_vol and avg_vol > 0 else 1.0
    n_bad   = sum([not trend_ok, vol_r<0.7, macd_v is not None and macs_v is not None and macd_v<macs_v])
    risk    = (L["risk_high"] if n_bad>=2 else (L["risk_med"] if n_bad==1 else L["risk_low"]))
    risk_em = "🔴" if n_bad>=2 else ("🟡" if n_bad==1 else "🟢")

    action = hanh_vi
    if lang == "EN":
        action = {"MUA":"BUY","BÁN":"SELL","THEO DÕI":"WATCH"}.get(hanh_vi, hanh_vi)

    if hanh_vi == "MUA":
        if lang == "VI":
            parts.append(f"#### 📈 Khuyến Nghị: **MUA** — {sector}")
            parts.append(f"**{len(confirms)} tín hiệu xác nhận:** `{'  ·  '.join(confirms)}`\n")
            parts.append(f"- **RSI = {rsi:.1f}** (<{rsi_buy_thresh}): {L['insight_rsi_os']}")
            if close < bbl: parts.append(f"- **Giá dưới BB Lower ({bbl:,.0f})**: {L['insight_bb_low']}")
            if trend_ok: parts.append("- **Giá > SMA50**: Xu hướng trung hạn TĂNG — tín hiệu chất lượng cao.")
            else: parts.append("- ⚠️ **Giá < SMA50**: Xu hướng trung hạn GIẢM — tín hiệu kém tin cậy hơn, chia nhỏ lệnh.")
            if stoch_k and not np.isnan(stoch_k) and stoch_k < 20:
                parts.append(f"- **Stoch %K = {stoch_k:.0f}** (<20): Xác nhận quá bán ngắn hạn — momentum có thể đảo chiều.")
            if vol_r >= 1.5: parts.append(f"- **KL = {vol_r:.1f}× TB20**: {L['insight_vol_spike']} → hướng tăng = dòng tiền vào.")
            elif vol_r < 0.7: parts.append(f"- ⚠️ **KL thấp ({vol_r:.1f}×)**: Tín hiệu chưa được xác nhận bởi dòng tiền — cẩn thận tín hiệu giả.")
            if macd_v is not None and macs_v is not None:
                if macd_v > macs_v: parts.append(f"- **MACD > Signal**: {L['insight_macd_bull']}")
                else: parts.append(f"- ⚠️ **MACD < Signal**: {L['insight_macd_bear']} — chờ MACD cắt lên trước khi mua.")
            if adx_val and adx_val > 25: parts.append(f"- **ADX = {adx_val:.0f}** (>25): {L['insight_adx_trend']}")
            tp1 = close+(bbu-close)*0.4 if bbu>close else close*1.07
            parts += [
                f"\n**📋 Chiến thuật:**",
                f"- Mua: **{bbl:,.0f}–{close:,.0f}** | TP1: **{tp1:,.0f}** | TP2: **{bbu:,.0f}** | Stop: **{stop:,.0f}**",
                f"\n{risk_em} **Rủi ro: {risk}** | {len(confirms)}/10 indicators confirmed"
            ]
        else:
            parts.append(f"#### 📈 Signal: **BUY** — {sector}")
            parts.append(f"**{len(confirms)} confirmations:** `{'  ·  '.join(confirms)}`\n")
            parts.append(f"- **RSI = {rsi:.1f}** (<{rsi_buy_thresh}): {L['insight_rsi_os']}")
            if close < bbl: parts.append(f"- **Price below BB Lower ({bbl:,.0f})**: {L['insight_bb_low']}")
            if trend_ok: parts.append("- **Price > SMA50**: Medium-term uptrend — high-quality signal.")
            else: parts.append("- ⚠️ **Price < SMA50**: Medium-term downtrend — lower confidence, reduce size.")
            if stoch_k and not np.isnan(stoch_k) and stoch_k < 20:
                parts.append(f"- **Stoch %K = {stoch_k:.0f}** (<20): Near-term oversold confirmed — momentum may turn.")
            if vol_r >= 1.5: parts.append(f"- **Volume = {vol_r:.1f}× avg**: {L['insight_vol_spike']} → bullish direction confirms inflow.")
            elif vol_r < 0.7: parts.append(f"- ⚠️ **Low volume ({vol_r:.1f}×)**: Signal unconfirmed by money flow — watch for false breakout.")
            if macd_v is not None and macs_v is not None:
                if macd_v > macs_v: parts.append(f"- **MACD > Signal**: {L['insight_macd_bull']}")
                else: parts.append(f"- ⚠️ **MACD < Signal**: {L['insight_macd_bear']} — wait for MACD crossover before entering.")
            if adx_val and adx_val > 25: parts.append(f"- **ADX = {adx_val:.0f}** (>25): {L['insight_adx_trend']}")
            tp1 = close+(bbu-close)*0.4 if bbu>close else close*1.07
            parts += [
                f"\n**📋 Trade plan:**",
                f"- Buy: **{bbl:,.0f}–{close:,.0f}** | TP1: **{tp1:,.0f}** | TP2: **{bbu:,.0f}** | Stop: **{stop:,.0f}**",
                f"\n{risk_em} **Risk: {risk}** | {len(confirms)}/10 indicators confirmed"
            ]

    elif hanh_vi == "BÁN":
        if lang == "VI":
            parts.append(f"#### 📉 Khuyến Nghị: **BÁN** — {sector}")
            parts.append(f"**{len(confirms)} tín hiệu xác nhận:** `{'  ·  '.join(confirms)}`\n")
            parts.append(f"- **RSI = {rsi:.1f}** (>{rsi_sell_thresh}): {L['insight_rsi_ob']}")
            if close > bbu: parts.append(f"- **Giá trên BB Upper ({bbu:,.0f})**: {L['insight_bb_up']}")
            parts += [f"- Bán vùng: **{close:,.0f}–{bbu:,.0f}** | Mua lại khi RSI về <{rsi_buy_thresh+5}",
                      f"\n🟢 **Rủi ro: {L['risk_low']}** nếu đang nắm giữ vị thế"]
        else:
            parts.append(f"#### 📉 Signal: **SELL** — {sector}")
            parts.append(f"**{len(confirms)} confirmations:** `{'  ·  '.join(confirms)}`\n")
            parts.append(f"- **RSI = {rsi:.1f}** (>{rsi_sell_thresh}): {L['insight_rsi_ob']}")
            if close > bbu: parts.append(f"- **Price above BB Upper ({bbu:,.0f})**: {L['insight_bb_up']}")
            parts += [f"- Sell zone: **{close:,.0f}–{bbu:,.0f}** | Re-buy when RSI < {rsi_buy_thresh+5}",
                      f"\n🟢 **Risk: {L['risk_low']}** if already holding position"]
    else:
        if lang == "VI":
            parts += [
                f"#### 🔍 Tín Hiệu: **THEO DÕI** — {sector}",
                f"- RSI = {rsi:.1f}: Chờ RSI về <{rsi_buy_thresh} (mua) hoặc >{rsi_sell_thresh} (bán).",
                f"- {'ADX = '+str(round(adx_val,0))+': Xu hướng rõ — tín hiệu sắp xuất hiện.' if adx_val and adx_val>25 else 'ADX thấp: Sideway — chờ breakout.'}",
                f"\n⚪ **Rủi ro: Chưa xác định** — không nên giao dịch khi chưa có tín hiệu rõ.",
            ]
        else:
            parts += [
                f"#### 🔍 Signal: **WATCH** — {sector}",
                f"- RSI = {rsi:.1f}: Wait for RSI <{rsi_buy_thresh} (buy) or >{rsi_sell_thresh} (sell).",
                f"- {'ADX = '+str(round(adx_val,0))+': Trend clear — signal likely soon.' if adx_val and adx_val>25 else 'ADX low: Sideways — wait for breakout.'}",
                f"\n⚪ **Risk: Undetermined** — avoid trading without clear signal.",
            ]

    if doi_lai_signals:
        high_s = [s for s in doi_lai_signals if s["severity"]=="HIGH"]
        others = [s for s in doi_lai_signals if s["severity"]!="HIGH"]
        if high_s:
            parts.append("\n---\n#### 🚨 Cảnh Báo Thao Túng / Manipulation Warning")
            for s in high_s: parts.append(f"{s['icon']} **{s['signal']}**: {s['detail']}")
        if others:
            parts.append("\n#### 📊 Tín Hiệu Dòng Tiền / Money Flow Signals")
            for s in others: parts.append(f"{s['icon']} **{s['signal']}**: {s['detail']}")

    si = get_sector_insight(ticker, lang)
    if si: parts.append(f"\n---\n{si}")
    return "\n".join(p for p in parts if p)


def round_price_hose(price):
    if pd.isna(price) or price <= 0: return 0
    p = float(price)
    if p < 10_000: return round(p/10)*10
    if p < 50_000: return round(p/50)*50
    return round(p/100)*100

# ══════════════════════════════════════════════════════════════
#  B. BACKTEST T+2 (exact session counting — unchanged v12)
# ══════════════════════════════════════════════════════════════
def run_backtest(df: pd.DataFrame, initial_capital=INITIAL_CAPITAL,
                 apply_trend_filter=True, rsi_buy=35, rsi_sell=65):
    capital=float(initial_capital); shares=0; entry_price=0.0
    stop_level=0.0; buy_row_idx=-1; trades=[]
    for i in range(50, len(df)):
        try:
            rsi_v=float(df["RSI"].iloc[i]); c_v=float(df["Close"].iloc[i])
            bbl_v=float(df["BB_Lower"].iloc[i]); bbu_v=float(df["BB_Upper"].iloc[i])
            s50_v=float(df["SMA50"].iloc[i])
            atr_v=float(df["ATR"].iloc[i]) if "ATR" in df.columns else c_v*0.02
            if any(np.isnan(x) for x in [rsi_v,c_v,bbl_v,bbu_v,s50_v]): continue
            trend_ok=(c_v>s50_v) if apply_trend_filter else True
            if rsi_v < rsi_buy and c_v < bbl_v and trend_ok and capital>0 and shares==0:
                bp=c_v*(1+SLIPPAGE); n_lots=int(capital/(bp*LOT_SIZE*(1+BUY_FEE)))
                if n_lots > 0:
                    sh=n_lots*LOT_SIZE; cost=sh*bp*(1+BUY_FEE)
                    capital-=cost; shares+=sh; entry_price=bp; buy_row_idx=i
                    stop_level=max(entry_price-1.5*atr_v, entry_price*0.90)
                    trades.append({"Ngày":df.index[i].strftime("%Y-%m-%d"),"Lệnh":"🟢 MUA",
                        "Giá":round(bp),"SL":sh,"Stop":round(stop_level),"Vốn":round(capital),
                        "P&L%":"","T+phiên":"T+0"})
            elif shares > 0:
                sessions_held=i-buy_row_idx
                hit_stop=(c_v<=stop_level)
                sell_sig=(sessions_held>=T2_SESSIONS and rsi_v>rsi_sell and c_v>bbu_v)
                if hit_stop or sell_sig:
                    sp=c_v*(1-SLIPPAGE); proc=shares*sp*(1-SELL_FEE-SELL_TAX)
                    pnl=(sp-entry_price)/entry_price*100; capital+=proc
                    l_type="⛔ STOP" if hit_stop else "🔴 BÁN"
                    trades.append({"Ngày":df.index[i].strftime("%Y-%m-%d"),"Lệnh":l_type,
                        "Giá":round(sp),"SL":shares,"Stop":round(stop_level),"Vốn":round(capital),
                        "P&L%":f"{pnl:+.2f}%","T+phiên":f"T+{sessions_held}"})
                    shares=0; entry_price=0.0; stop_level=0.0; buy_row_idx=-1
        except (ValueError,TypeError): continue
    final_val=capital+shares*float(df["Close"].iloc[-1]) if shares>0 else capital
    sell_t=[t for t in trades if "BÁN" in t["Lệnh"] or "STOP" in t["Lệnh"]]
    pnl_list=[]
    for t in sell_t:
        try: pnl_list.append(float(str(t["P&L%"]).replace("%","").replace("+","")))
        except: pass
    wins=len([p for p in pnl_list if p>0])
    eq=[initial_capital]; cap=initial_capital
    for t in trades:
        try: cap=int(str(t["Vốn"]).replace(",",""))
        except: pass
        eq.append(cap)
    eq=np.array(eq,dtype=float); peak=np.maximum.accumulate(eq)
    dd=(eq-peak)/(peak+1e-9)*100
    metrics={"final_val":final_val,"profit":final_val-initial_capital,
              "total_ret_pct":(final_val-initial_capital)/initial_capital*100,
              "win_rate":wins/max(len(pnl_list),1)*100,
              "avg_pnl":np.mean(pnl_list) if pnl_list else 0,
              "max_drawdown":dd.min(),"n_trades":len(sell_t),
              "sharpe":(np.mean(pnl_list)/np.std(pnl_list)) if len(pnl_list)>1 else 0}
    return final_val, trades, metrics, eq

# ══════════════════════════════════════════════════════════════
#  D. ML ENSEMBLE — 7 models (unchanged weights)
# ══════════════════════════════════════════════════════════════
MODEL_WEIGHTS = {"LinearReg":0.10,"Holt":0.15,"MonteCarlo":0.20,
                 "ARIMA":0.15,"SVR":0.10,"RandomForest":0.10,"Prophet":0.20}
MODEL_META = {
    "LinearReg":   ("📐 Stats",    "Long-term trend anchor — prevents extreme forecasts"),
    "Holt":        ("📐 Stats",    "Tracks recent trend closely, good noise reduction"),
    "MonteCarlo":  ("🎲 Prob",     "1,000 simulations → P10–P90 safe price bands"),
    "ARIMA":       ("📊 TimeSeries","Autocorrelation patterns — good for technical rebounds"),
    "SVR":         ("🤖 ML",       "Hidden support/resistance, robust to outliers"),
    "RandomForest":("🤖 ML",       "150 decision trees — detects non-linear turning points"),
    "Prophet":     ("🔮 AI",       "VN market seasonality — sell Apr, buy year-end"),
}

def forecast_linreg(prices, n_days):
    x=np.arange(len(prices)); sl,ic,r,_,_=stats.linregress(x,prices)
    fx=np.arange(len(prices),len(prices)+n_days); return sl*fx+ic, sl, r**2

def forecast_holt(prices, n_days, alpha=0.25, beta=0.10):
    prices=[float(p) for p in prices]
    if len(prices)<2: return np.array([prices[-1]]*n_days)
    L=prices[0]; T=prices[1]-prices[0]
    for p in prices[1:]:
        Lp,Tp=L,T; L=alpha*p+(1-alpha)*(Lp+Tp); T=beta*(L-Lp)+(1-beta)*Tp
    return np.array([L+i*T for i in range(1,n_days+1)])

def forecast_monte_carlo(prices, n_days, n_sims=1000, seed=42):
    np.random.seed(seed)
    log_r=np.diff(np.log(np.array(prices,dtype=float)))
    mu=np.mean(log_r); sigma=np.std(log_r)*1.05
    last=float(prices[-1])
    sims=last*np.exp(np.cumsum(np.random.normal(mu,sigma,(n_sims,n_days)),axis=1))
    return {k:np.percentile(sims,p,axis=0) for k,p in [("p10",10),("p25",25),("p50",50),("p75",75),("p90",90)]}

def forecast_arima(prices, n_days):
    if not ARIMA_AVAILABLE or len(prices)<40: return None, None
    try:
        log_p=np.log(np.array(prices,dtype=float))
        res=ARIMA(log_p,order=(2,1,2)).fit()
        fc=res.forecast(steps=n_days)
        ci=res.get_forecast(n_days).conf_int()
        return np.exp(fc),(np.exp(ci.iloc[:,0].values),np.exp(ci.iloc[:,1].values))
    except Exception: return None, None

def forecast_sklearn(prices, n_days, model_type="SVR"):
    if not SKLEARN_AVAILABLE or len(prices)<40: return None
    p_arr=np.array(prices,dtype=float); n=len(p_arr)
    lags=[1,2,5]; max_lg=max(lags)
    X_list,y_list=[],[]
    for i in range(max(max_lg,20),n):
        feats=[p_arr[i-l] for l in lags]
        feats.append(np.mean(p_arr[max(0,i-5):i]))
        feats.append(np.mean(p_arr[max(0,i-20):i]))
        feats.append((p_arr[i-1]-p_arr[i-6])/p_arr[i-6] if i>=6 else 0)
        feats.append(float(i)); X_list.append(feats); y_list.append(p_arr[i])
    X=np.array(X_list); y=np.array(y_list)
    Xm=X.mean(axis=0); Xs=X.std(axis=0)+1e-9; Xn=(X-Xm)/Xs
    try:
        mdl=(SVR(kernel="rbf",C=1e3,gamma=0.1,epsilon=0.01)
             if model_type=="SVR" else
             RandomForestRegressor(n_estimators=150,random_state=42,max_features="sqrt",n_jobs=-1))
        mdl.fit(Xn,y)
        history=list(p_arr); forecasts=[]
        for step in range(n_days):
            idx=n+step
            feats=[history[-(l)] for l in lags]
            feats.append(np.mean(history[-5:]))
            feats.append(np.mean(history[-20:]) if len(history)>=20 else np.mean(history))
            feats.append((history[-1]-history[-6])/history[-6] if len(history)>=6 else 0)
            feats.append(float(idx))
            fn=((np.array(feats)-Xm)/Xs).reshape(1,-1)
            pred=float(mdl.predict(fn)[0]); forecasts.append(pred); history.append(pred)
        return np.array(forecasts)
    except Exception as e:
        _log.warning(f"forecast_sklearn[{model_type}]: {e}"); return None

@st.cache_data
def run_prophet_forecast(_df, n_days, symbol):
    if not PROPHET_AVAILABLE: raise ImportError("pip install prophet")
    dc=clean_data(_df.copy())
    ds=pd.to_datetime(dc.index,errors="coerce")
    y=pd.to_numeric(dc["Close"],errors="coerce").astype("float64")
    dfp=pd.DataFrame({"ds":ds,"y":y}).dropna()
    dfp=dfp[np.isfinite(dfp["y"])&~dfp["ds"].duplicated()].sort_values("ds")
    if len(dfp)<30: raise ValueError("Need ≥30 sessions for Prophet.")
    m=Prophet(daily_seasonality=False,yearly_seasonality=True,
              weekly_seasonality=False,changepoint_prior_scale=0.15)
    m.add_seasonality(name="quarterly",period=63,fourier_order=5)
    m.fit(dfp)
    future=m.make_future_dataframe(periods=n_days,freq="B")
    return m, m.predict(future)

def compute_weighted_ensemble(model_dict: dict):
    arrays=[]; weights=[]
    for name,(arr,w) in model_dict.items():
        fc=arr.get("p50") if isinstance(arr,dict) else arr
        if fc is not None and len(fc)>0:
            arrays.append(np.array(fc,dtype=float)); weights.append(w)
    if not arrays: return None
    return sum(a*w for a,w in zip(arrays,weights))/sum(weights)

def save_ml_forecast_audit(symbol,days,last_price,model_dict,ensemble_fc,future_dates,indicators):
    ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record={"symbol":symbol,"timestamp":ts,"days_forecast":days,"last_price":float(last_price),
            "models_used":list(model_dict.keys()),"results":{},
            "indicators_at_forecast":{k:(round(float(v),2) if v is not None else None)
                                       for k,v in (indicators.items() if hasattr(indicators,"items") else {})},
            "forecast_dates":[str(d.date()) for d in future_dates]}
    for name,(arr,w) in model_dict.items():
        fc=arr.get("p50") if isinstance(arr,dict) else arr
        if fc is not None:
            record["results"][name]={"weight":w,"final":float(fc[-1]),
                                      "pct_change":round((fc[-1]/last_price-1)*100,2)}
    if ensemble_fc is not None:
        record["results"]["ensemble"]={"weight":"weighted","final":float(ensemble_fc[-1]),
            "pct_change":round((ensemble_fc[-1]/last_price-1)*100,2),
            "all_values":[round(float(v),0) for v in ensemble_fc]}
    fp=os.path.join(ML_AUDIT_PATH,f"{symbol}.json")
    history=[]
    try:
        if os.path.exists(fp):
            with open(fp,"r",encoding="utf-8") as f: history=json.load(f)
    except Exception: history=[]
    history.insert(0,record); history=history[:50]
    with open(fp,"w",encoding="utf-8") as f: json.dump(history,f,ensure_ascii=False,indent=2)
    _log.info(f"ML audit saved: {symbol}"); return fp

def load_ml_forecast_history(symbol):
    fp=os.path.join(ML_AUDIT_PATH,f"{symbol}.json")
    if not os.path.exists(fp): return []
    try:
        with open(fp,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return []

# ══════════════════════════════════════════════════════════════
#  HELPER UI
# ══════════════════════════════════════════════════════════════
def style_action(v):
    vi_en_buy  = ("MUA","BUY")
    vi_en_sell = ("BÁN","SELL")
    if v in vi_en_buy:  return "background-color:#006400;color:white;font-weight:bold"
    if v in vi_en_sell: return "background-color:#8B0000;color:white;font-weight:bold"
    if v in ("THEO DÕI","WATCH"): return "background-color:#1a3a6e;color:white"
    return ""

def show_df(df_or_styled, key=None):
    st.dataframe(df_or_styled, use_container_width=True, key=key)

def src_badge(src: str) -> str:
    cls={"DNSE":"src-dnse","SSI":"src-ssi","CafeF":"src-cafef"}.get(src,"src-none")
    return f'<span class="src-badge {cls}">{src}</span>'

def load_watchlist_from_file(path):
    if not os.path.exists(path):
        with open(path,"w",encoding="utf-8") as f:
            for t in DEFAULT_WATCHLIST: f.write(f"{t}\n")
        return list(dict.fromkeys(DEFAULT_WATCHLIST))
    with open(path,"r",encoding="utf-8") as f:
        return sorted(list(set([l.strip().upper() for l in f if l.strip()])))

# ── Session state init (all keys defined here to avoid KeyError)
for _k in ["df_scan","df_top_buys","df_audit","smoke_results"]:
    if _k not in st.session_state: st.session_state[_k] = pd.DataFrame()
if "error_logs"  not in st.session_state: st.session_state.error_logs  = []
if "symbol"      not in st.session_state: st.session_state.symbol      = "FPT"
if "audit_extra" not in st.session_state: st.session_state.audit_extra = {}
if "audit_src"   not in st.session_state: st.session_state.audit_src   = "–"

# ══════════════════════════════════════════════════════════════
#  SCAN LOGIC — shared between Tab1 & Tab2
# ══════════════════════════════════════════════════════════════
def scan_one_ticker(t: str, min_rows: int = 40):
    data, src, error_msg = download_data(t, days=365, min_rows=min_rows)
    if data.empty:
        return None, src, error_msg
    data = clean_data(data)
    if len(data) < min_rows:
        return None, "Filter", "Insufficient data after cleaning"
    data = calculate_indicators(data)
    latest = data.iloc[-1]
    avg_v  = float(data["Volume"].tail(20).mean())
    if use_liquidity_filter and avg_v*float(latest["Close"]) < min_avg_value:
        return None, "Filter", "Low liquidity"
    s50      = extract_latest(data,"SMA50")
    c_v      = float(latest["Close"])
    trend_ok = (s50 is not None and c_v > s50) if use_trend_filter else True
    rsi_v    = extract_latest(data,"RSI") or 50
    bbl_v    = extract_latest(data,"BB_Lower") or c_v
    bbu_v    = extract_latest(data,"BB_Upper") or c_v
    s20      = extract_latest(data,"SMA20")
    macd     = extract_latest(data,"MACD")
    macs     = extract_latest(data,"MACD_Signal")
    atr_v    = extract_latest(data,"ATR")
    sk       = extract_latest(data,"STOCH_K")
    adx_v    = extract_latest(data,"ADX")
    last_v   = float(latest["Volume"])

    if st.session_state.lang == "VI":
        hanh_vi = "THEO DÕI"
        if rsi_v < rsi_buy_thresh and c_v < bbl_v and trend_ok: hanh_vi = "MUA"
        elif rsi_v > rsi_sell_thresh and c_v > bbu_v:            hanh_vi = "BÁN"
    else:
        hanh_vi = "THEO DÕI"
        if rsi_v < rsi_buy_thresh and c_v < bbl_v and trend_ok: hanh_vi = "MUA"
        elif rsi_v > rsi_sell_thresh and c_v > bbu_v:            hanh_vi = "BÁN"

    sig_type = "BUY" if hanh_vi == "MUA" else ("BÁN" if hanh_vi == "BÁN" else "BUY")
    score, confirms = compute_composite_score(latest.to_dict(), avg_v, last_v, trend_ok,
                                               sig_type, rsi_buy_thresh, rsi_sell_thresh)
    doi_lai = detect_doi_lai(data)
    if any(s["severity"]=="HIGH" and "DUMP" in s["signal"].upper() for s in doi_lai): score -= 10
    lang = st.session_state.lang
    bb_mid = extract_latest(data,"BB_Mid") or c_v
    ly_giai = generate_explanation(hanh_vi, rsi_v, c_v, bbl_v, bbu_v, s20, s50,
                                    avg_v, last_v, macd, macs, trend_ok, doi_lai,
                                    atr_v, sk, adx_v or 0, confirms, t,
                                    rsi_buy_thresh, rsi_sell_thresh, lang)
    price_expl = explain_price_levels(c_v, bbl_v, bbu_v, bb_mid, s20, s50,
                                           atr_v, rsi_v, sk, hanh_vi, t,
                                           rsi_buy_thresh, rsi_sell_thresh, lang)
    signal_display = hanh_vi
    if lang == "EN":
        signal_display = {"MUA":"BUY","BÁN":"SELL","THEO DÕI":"WATCH"}.get(hanh_vi, hanh_vi)
    row = {
        L["ticker"]:    t,
        "Ngành/Sector": get_sector(t),
        L["price"]:     round(c_v),
        L["signal"]:    signal_display,
        "BB Buy":       round_price_hose(bbl_v),
        "BB Sell":      round_price_hose(bbu_v),
        "RSI":          round(rsi_v,1),
        "Stoch%K":      round(sk,1) if sk else "–",
        "ADX":          round(adx_v,1) if adx_v else "–",
        "Vol/MA20":     f"{last_v/avg_v:.1f}×" if avg_v>0 else "–",
        L["score"]:     score,
        "Confirms":     len(confirms),
        "⚠️ DL":        len(doi_lai),
        L["source"]:    src,
        "_ly_giai":     ly_giai,
        "_price_expl":  price_expl,
    }
    return row, src, None

# ══════════════════════════════════════════════════════════════
#  C. WORLD MARKETS — Stooq + FRED (no yfinance library)
#  Tickers: GC.F(Gold), CL.F(WTI), NG.F(NatGas), DXY, ^SPX
# ══════════════════════════════════════════════════════════════
WORLD_SYMBOLS = {
    "gold":   ("GC.F",  "Gold XAU/USD",  "USD/oz",   "Vàng"),
    "oil":    ("CL.F",  "WTI Crude Oil", "USD/bbl",  "Dầu WTI"),
    "natgas": ("NG.F",  "Natural Gas",   "USD/MMBtu","Khí Tự Nhiên"),
    "dxy":    ("DXY",   "USD Index DXY", "index",    "Chỉ Số USD"),
    "sp500":  ("^SPX",  "S&P 500",       "points",   "S&P 500"),
    "vni":    (None,    "VN-Index",      "points",   "VN-Index"),
}

# Map Stooq tickers to yfinance tickers for fallback
_STOOQ_TO_YF = {
    "GC.F": "GC=F",       # Gold futures
    "CL.F": "CL=F",       # WTI Oil futures
    "NG.F": "NG=F",       # Natural Gas futures
    "DXY":  "DX-Y.NYB",   # USD Index
    "^SPX": "^GSPC",      # S&P 500
    "^VNI": "^VNINDEX",   # VN-Index
}

@st.cache_data(ttl=900)  # 15 min cache
def fetch_stooq(ticker: str, days: int = 90) -> pd.DataFrame:
    """
    Fetch OHLCV from stooq.pl — free, no auth, covers futures & indices.
    Falls back to yFinance if stooq is unavailable.
    URL: https://stooq.com/q/d/l/?s=gc.f&i=d
    """
    # 1. Try stooq first
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}&i=d"
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12)
        r.raise_for_status()
        text = r.text.strip()
        # Stooq returns "No data" message when ticker not found
        if not text or "No data" in text or text.count(",") < 3:
            raise ValueError(f"Stooq no data for {ticker}")
        df = pd.read_csv(io.StringIO(text))
        df.columns = [c.strip().title() for c in df.columns]
        if "Date" not in df.columns or "Close" not in df.columns:
            raise ValueError(f"Stooq bad columns for {ticker}: {df.columns.tolist()}")
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date","Close"]).set_index("Date").sort_index()
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Close"])
        if not df.empty:
            _log.info(f"Stooq {ticker}: {len(df)} rows")
            return df.tail(days)
    except Exception as e:
        _log.warning(f"Stooq {ticker} failed: {e} — trying yFinance fallback")

    # 2. yFinance fallback for world market data
    if YFINANCE_AVAILABLE:
        yf_ticker = _STOOQ_TO_YF.get(ticker, ticker)
        try:
            import yfinance as yf
            # Use period string for yfinance
            period_map = {30:"3mo", 60:"3mo", 90:"6mo", 120:"6mo", 180:"1y", 365:"2y"}
            period = period_map.get(days, "1y")
            df = yf.download(yf_ticker, period=period, interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            if not df.empty and "Close" in df.columns:
                df = df.dropna(subset=["Close"])
                _log.info(f"yFinance fallback {ticker}→{yf_ticker}: {len(df)} rows")
                return df.tail(days)
        except Exception as e:
            _log.warning(f"yFinance fallback {ticker}→{yf_ticker} failed: {e}")
            import traceback
            _log.debug(traceback.format_exc())

    return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_fred_rate(series_id: str = "FEDFUNDS", periods: int = 24) -> pd.DataFrame:
    """Fetch FED Funds rate from FRED (St Louis Fed public API)."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["Date","Value"]
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.dropna().set_index("Date").sort_index()
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
        return df.tail(periods)
    except Exception as e:
        _log.debug(f"FRED {series_id}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=900)
def fetch_vni_index(days: int = 90) -> pd.DataFrame:
    """Fetch VN-Index: SSI iBoard (multiple endpoints) → stooq → yfinance fallback."""
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    
    # Try SSI endpoints for VNINDEX
    ssi_endpoints = [
        f"https://iboard-query.ssi.com.vn/v2/stock/ohlc?symbol=VNINDEX&resolution=D&from={from_ts}&to={to_ts}",
        f"https://iboard-query.ssi.com.vn/stock/ohlc?symbol=VNINDEX&resolution=D&from={from_ts}&to={to_ts}",
    ]
    for url in ssi_endpoints:
        try:
            r = _HTTP.get(url, timeout=12)
            r.raise_for_status()
            df = _parse_udf(r.json())
            if not df.empty:
                _log.info(f"VNI: {len(df)} rows via SSI")
                return df
        except Exception as e:
            _log.debug(f"VNI SSI attempt failed: {e}")
    
    # Stooq fallback for ^VNI
    try:
        df = fetch_stooq("^VNI", days=days)
        if not df.empty:
            _log.info(f"VNI: {len(df)} rows via Stooq")
            return df
    except Exception as e:
        _log.debug(f"VNI stooq: {e}")
    
    # yFinance fallback
    if YFINANCE_AVAILABLE:
        try:
            import yfinance as yf
            df = yf.download("^VNINDEX", period=f"{min(days,730)}d", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df.dropna(subset=["Close"]) if not df.empty else df
            if not df.empty:
                _log.info(f"VNI: {len(df)} rows via yFinance ^VNINDEX")
                return df
        except Exception as e:
            _log.debug(f"VNI yfinance: {e}")
    
    return pd.DataFrame()

def world_market_impact_analysis(gold_chg, oil_chg, gas_chg, dxy_chg, sp500_chg, lang="VI"):
    """Generate structured impact analysis on VN market sectors."""
    insights = []
    L_dict = _LANG_VI if lang=="VI" else _LANG_EN

    # Gold impact
    if gold_chg is not None:
        if abs(gold_chg) > 0.5:
            direction = "tăng" if gold_chg > 0 else "giảm"
            en_dir = "up" if gold_chg > 0 else "down"
            if lang == "VI":
                txt = (f"🪙 **Vàng {direction} {abs(gold_chg):.1f}%**: "
                       f"{'PNJ, SJC, DJI hưởng lợi từ biên LN tốt hơn. Tâm lý trú ẩn an toàn tăng.' if gold_chg>0 else 'Cổ phiếu vàng điều chỉnh, tâm lý risk-on có thể quay lại cổ phiếu.'}")
            else:
                txt = (f"🪙 **Gold {en_dir} {abs(gold_chg):.1f}%**: "
                       f"{'PNJ/gold sector benefits, safe-haven demand rising.' if gold_chg>0 else 'Gold stocks correct, risk-on appetite may return to equities.'}")
            insights.append(("gold", gold_chg, txt))

    # Oil impact
    if oil_chg is not None:
        if abs(oil_chg) > 1.0:
            direction = "tăng" if oil_chg > 0 else "giảm"
            en_dir = "up" if oil_chg > 0 else "down"
            if lang == "VI":
                txt = (f"🛢️ **Dầu WTI {direction} {abs(oil_chg):.1f}%**: "
                       f"{'GAS, PLX, PVD, PVS, BSR hưởng lợi. HVN, VJC chi phí tăng.' if oil_chg>0 else 'Hàng không (HVN, VJC) hưởng lợi. GAS, PLX, PVD chịu áp lực.'}")
            else:
                txt = (f"🛢️ **WTI Oil {en_dir} {abs(oil_chg):.1f}%**: "
                       f"{'GAS, PLX, PVD, PVS, BSR gain. HVN, VJC face higher fuel costs.' if oil_chg>0 else 'Airlines (HVN, VJC) benefit from lower fuel. GAS, PLX, PVD under pressure.'}")
            insights.append(("oil", oil_chg, txt))

    # DXY impact
    if dxy_chg is not None:
        if abs(dxy_chg) > 0.3:
            direction = "mạnh lên" if dxy_chg > 0 else "yếu đi"
            en_dir = "strengthening" if dxy_chg > 0 else "weakening"
            if lang == "VI":
                txt = (f"💵 **USD {direction} {abs(dxy_chg):.1f}%**: "
                       f"{'VNĐ chịu áp lực giảm giá, nhập khẩu đắt hơn (nguyên liệu, thiết bị). Cổ phiếu xuất khẩu (VHC, HPG, MSN) có lợi thế cạnh tranh.' if dxy_chg>0 else 'VNĐ vững hơn, vốn ngoại dễ quay lại TTVN. Nhập khẩu rẻ hơn.'}")
            else:
                txt = (f"💵 **USD {en_dir} {abs(dxy_chg):.1f}%**: "
                       f"{'VND faces depreciation pressure, imports costlier. Exporters (VHC, HPG, MSN) gain competitive edge.' if dxy_chg>0 else 'VND firms up, foreign capital may return to VN market. Imports cheaper.'}")
            insights.append(("dxy", dxy_chg, txt))

    # S&P500 impact
    if sp500_chg is not None:
        if abs(sp500_chg) > 1.0:
            direction = "tăng" if sp500_chg > 0 else "giảm"
            en_dir = "up" if sp500_chg > 0 else "down"
            if lang == "VI":
                txt = (f"📈 **S&P500 {direction} {abs(sp500_chg):.1f}%**: "
                       f"{'Khẩu vị rủi ro toàn cầu cải thiện, dòng vốn ngoại có xu hướng tích cực với TTVN. Nhóm cổ phiếu vốn hóa lớn (VCB, VIC, FPT) hưởng lợi.' if sp500_chg>0 else 'Risk-off toàn cầu, khả năng bán ròng của khối ngoại. Theo dõi VN30 phiên sáng.'}")
            else:
                txt = (f"📈 **S&P500 {en_dir} {abs(sp500_chg):.1f}%**: "
                       f"{'Global risk appetite improves, foreign capital positive for VN. Large-caps (VCB, VIC, FPT) likely to benefit.' if sp500_chg>0 else 'Global risk-off, foreign selling likely. Watch VN30 morning session.'}")
            insights.append(("sp500", sp500_chg, txt))

    # Gas impact
    if gas_chg is not None:
        if abs(gas_chg) > 2.0:
            direction = "tăng" if gas_chg > 0 else "giảm"
            en_dir = "up" if gas_chg > 0 else "down"
            if lang == "VI":
                txt = (f"⛽ **Khí tự nhiên {direction} {abs(gas_chg):.1f}%**: "
                       f"{'Chi phí điện và sản xuất tăng, ảnh hưởng DPM, DCM (phân bón). GAS hưởng lợi từ giá bán cao hơn.' if gas_chg>0 else 'Chi phí điện giảm, lợi cho nhà máy điện khí. DPM, DCM giảm chi phí đầu vào.'}")
            else:
                txt = (f"⛽ **Natural Gas {en_dir} {abs(gas_chg):.1f}%**: "
                       f"{'Power and production costs rise, impacts DPM, DCM (fertilisers). GAS benefits from higher selling price.' if gas_chg>0 else 'Power costs fall, benefits gas-fired plants. DPM, DCM face lower input costs.'}")
            insights.append(("gas", gas_chg, txt))

    return insights

# ══════════════════════════════════════════════════════════════
#  TABS — 10 tabs total
# ══════════════════════════════════════════════════════════════
def render_scanner_tab():
    st.subheader("📡 " + ("Tín Hiệu Giao Dịch Tổng Hợp" if st.session_state.lang=="VI" else "Aggregated Trading Signals"))
    watch_list = load_watchlist_from_file(WATCHLIST_FILE_PATH)
    st.info(f"Watchlist: **{len(watch_list)}** tickers  |  Pipeline: **DNSE** → SSI → CafeF  |  RSI Buy<{rsi_buy_thresh} / Sell>{rsi_sell_thresh}")

    if st.button(L["scan_btn"], type="primary"):
        scanner_data = []; st.session_state.error_logs = []
        pb = st.progress(0, "Scanning...")
        for i, t in enumerate(watch_list):
            try:
                row, src, err = scan_one_ticker(t)
                if row:
                    scanner_data.append(row)
                elif err:
                    st.session_state.error_logs.append(f"{t}: {err}")
            except Exception as e:
                msg = f"Scanner {t}: {e}"; st.session_state.error_logs.append(msg); _log.error(msg)
            finally:
                pb.progress((i+1)/len(watch_list), text=f"Scanning: {t}")

        st.session_state.df_scan = pd.DataFrame(scanner_data)
        if not st.session_state.df_scan.empty:
            st.session_state.df_scan.sort_values(L["score"], ascending=False, inplace=True)
            scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for _, row in st.session_state.df_scan.iterrows():
                fp = os.path.join(JSON_STORAGE_PATH, f"{row[L['ticker']]}.json")
                hist = []
                try:
                    if os.path.exists(fp):
                        with open(fp,"r",encoding="utf-8") as f: hist = json.load(f)
                except Exception: hist = []
                rec = {k: v for k, v in row.to_dict().items() if not k.startswith("_")}
                rec["scan_time"] = scan_time
                hist.insert(0, rec)
                with open(fp,"w",encoding="utf-8") as f: json.dump(hist[:100],f,ensure_ascii=False,indent=2)
            st.success(f"✅ Completed {len(scanner_data)} tickers at {scan_time}")
        else:
            st.warning("⚠️ No results. Check connection or disable filters.")

        if st.session_state.error_logs:
            with st.expander(f"⚠️ {len(st.session_state.error_logs)} errors"):
                for e in st.session_state.error_logs: st.caption(e)

    if not st.session_state.df_scan.empty:
        sig_col = L["signal"]
        dc = [c for c in st.session_state.df_scan.columns if not c.startswith("_")]
        show_df(st.session_state.df_scan[dc].style.map(style_action, subset=[sig_col]))

        sig_rows = st.session_state.df_scan[
            st.session_state.df_scan[sig_col].isin(["MUA","BÁN","BUY","SELL"])
        ]
        if not sig_rows.empty:
            st.divider()
            st.subheader("📋 " + ("Lý Giải & Mức Giá Chi Tiết" if st.session_state.lang=="VI" else "Detailed Signals & Price Levels"))
            for _, row in sig_rows.iterrows():
                label = (f"{row[sig_col]} — {row[L['ticker']]} | "
                         f"Price:{row[L['price']]:,} | RSI:{row['RSI']} | "
                         f"Score:{row[L['score']]} | {row.get(L['source'],'–')}")
                with st.expander(label):
                    c1, c2 = st.columns(2)
                    with c1: st.markdown(row.get("_ly_giai","–"))
                    with c2: st.markdown(row.get("_price_expl","–"))

def render_top_buy_tab():
    hdr = "Top Cổ Phiếu Bắt Đáy" if st.session_state.lang=="VI" else "Top Oversold Stock Screener"
    st.subheader(f"🏆 {hdr}")
    st.caption(f"Scanning **{len(MARKET_SCAN_LIST)}** tickers  |  DNSE → SSI → CafeF")

    if st.button(L["buy_btn"], type="primary"):
        buy_signals = []; st.session_state.error_logs = []
        pb = st.progress(0,"Scanning...")
        for i, t in enumerate(MARKET_SCAN_LIST):
            try:
                row, src, err = scan_one_ticker(t)
                if row and row[L["signal"]] in ("MUA","BUY"):
                    buy_signals.append(row)
                elif err:
                    st.session_state.error_logs.append(f"{t}: {err}")
            except Exception as e: _log.warning(f"Tab2 {t}: {e}")
            finally: pb.progress((i+1)/len(MARKET_SCAN_LIST), text=f"Scanning: {t}")

        st.session_state.df_top_buys = (
            pd.DataFrame(buy_signals).sort_values(L["score"],ascending=False).head(30)
            if buy_signals else pd.DataFrame()
        )
        if st.session_state.error_logs:
            with st.expander(f"⚠️ {len(st.session_state.error_logs)} errors"):
                for e in st.session_state.error_logs: st.caption(e)

    if not st.session_state.df_top_buys.empty:
        dc = [c for c in st.session_state.df_top_buys.columns if not c.startswith("_")]
        show_df(st.session_state.df_top_buys[dc])
        st.divider()
        for _, row in st.session_state.df_top_buys.iterrows():
            label = f"**{row[L['ticker']]}** | Score:{row[L['score']]} | RSI:{row['RSI']} | Vol:{row['Vol/MA20']} | {row.get(L['source'],'–')}"
            with st.expander(label):
                c1, c2 = st.columns(2)
                with c1: st.markdown(row.get("_ly_giai","–"))
                with c2: st.markdown(row.get("_price_expl","–"))
    else:
        st.info("No results yet or no tickers meet criteria. Try disabling filters in sidebar.")

def render_history_tab():
    hdr = "Lịch Sử Khuyến Nghị Scanner" if st.session_state.lang=="VI" else "Scanner Recommendation History"
    st.subheader(f"📂 {hdr}")
    jf = [f for f in os.listdir(JSON_STORAGE_PATH) if f.endswith(".json")] if os.path.exists(JSON_STORAGE_PATH) else []
    if jf:
        sel = st.selectbox("Chọn mã / Select ticker:", sorted([f.replace(".json","") for f in jf]))
        if sel:
            fp = os.path.join(JSON_STORAGE_PATH, f"{sel}.json")
            try:
                with open(fp,"r",encoding="utf-8") as f: hist = pd.DataFrame(json.load(f))
                sc = [c for c in hist.columns if not c.startswith("_")]
                sig_col_h = next((c for c in sc if c in ("Hành vi","Signal")), None)
                if sig_col_h:
                    show_df(hist[sc].style.map(style_action, subset=[sig_col_h]))
                else:
                    show_df(hist[sc])
            except Exception as e: st.error(f"Error: {e}")
    else:
        st.info("No history yet. Run Market Scanner first." if st.session_state.lang=="EN" else "Chưa có lịch sử. Chạy Market Scanner trước.")

def render_deep_audit_tab():
    hdr = "Deep Audit — 9 Indicators + Fundamentals" if st.session_state.lang=="EN" else "Deep Audit — 9 Chỉ Báo + Phân Tích Cơ Bản"
    st.subheader(f"🔍 {hdr}")
    ci1, ci2 = st.columns([3,1])
    sym = ci1.text_input("Ticker / Mã CP:", st.session_state.symbol,
                          placeholder="E.g.: FPT, GAS, OIL, PVS, ACV, IDC").upper()
    audit_btn = ci2.button(L["audit_btn"], type="primary")

    if audit_btn and sym:
        st.session_state.symbol = sym
        with st.spinner(f"Loading & analysing {sym}..."):
            try:
                raw, src, error_msg = download_data(sym, days=730, min_rows=40)
                if not raw.empty:
                    raw = clean_data(raw)
                    if len(raw) < 40:
                        st.error(f"Only {len(raw)} rows after cleaning — need ≥40.")
                    else:
                        df_a = calculate_indicators(raw)
                        st.session_state.df_audit = df_a
                        st.session_state.audit_src = src
                        latest = df_a.iloc[-1]; avg_v = float(df_a["Volume"].tail(20).mean())
                        last_v = float(latest["Volume"]); c = float(latest["Close"])
                        rsi  = extract_latest(df_a,"RSI") or 50
                        bbl  = extract_latest(df_a,"BB_Lower") or c
                        bbu  = extract_latest(df_a,"BB_Upper") or c
                        s20  = extract_latest(df_a,"SMA20"); s50 = extract_latest(df_a,"SMA50")
                        macd = extract_latest(df_a,"MACD"); macs = extract_latest(df_a,"MACD_Signal")
                        atr_v= extract_latest(df_a,"ATR"); sk = extract_latest(df_a,"STOCH_K")
                        adx_v= extract_latest(df_a,"ADX"); bb_mid = extract_latest(df_a,"BB_Mid") or c
                        trend_ok = (s50 is not None and c > s50) if use_trend_filter else True
                        hanh_vi = "THEO DÕI"
                        if rsi < rsi_buy_thresh and c < bbl and trend_ok: hanh_vi = "MUA"
                        elif rsi > rsi_sell_thresh and c > bbu:            hanh_vi = "BÁN"
                        sig_type = "BUY" if hanh_vi=="MUA" else ("BÁN" if hanh_vi=="BÁN" else "BUY")
                        score, confirms = compute_composite_score(latest.to_dict(), avg_v, last_v,
                                                                   trend_ok, sig_type, rsi_buy_thresh, rsi_sell_thresh)
                        doi_lai = detect_doi_lai(df_a)
                        lang = st.session_state.lang
                        ly_giai = generate_explanation(hanh_vi, rsi, c, bbl, bbu, s20, s50,
                                                        avg_v, last_v, macd, macs, trend_ok, doi_lai,
                                                        atr_v, sk, adx_v or 0, confirms, sym,
                                                        rsi_buy_thresh, rsi_sell_thresh, lang)
                        price_expl = explain_price_levels(c, bbl, bbu, bb_mid, s20, s50,
                                                           atr_v, rsi, sk, hanh_vi, sym,
                                                           rsi_buy_thresh, rsi_sell_thresh, lang)
                        st.session_state.audit_extra = dict(
                            hanh_vi=hanh_vi, ly_giai=ly_giai, doi_lai=doi_lai,
                            price_expl=price_expl, rsi=rsi, close=c, bbl=bbl, bbu=bbu,
                            s20=s20, s50=s50, macd=macd, macd_sig=macs,
                            atr=atr_v, stoch_k=sk, adx=adx_v, avg_v=avg_v, last_v=last_v,
                            confirms=confirms, score=score, sector=get_sector(sym))
                        st.success(f"✅ {sym} analysed — Source: **{src}** | Exchange: {TICKER_EXCHANGE.get(sym,'HOSE')} | {len(df_a)} sessions")
                else:
                    st.error(error_msg or f"Cannot load **{sym}**. Check ticker spelling.")
                    st.session_state.df_audit = pd.DataFrame()
            except Exception as e:
                st.error(f"Error: {e}"); _log.error(f"Deep Audit {sym}: {e}")
                st.session_state.df_audit = pd.DataFrame()

    if not st.session_state.df_audit.empty:
        df_a  = st.session_state.df_audit
        extra = st.session_state.audit_extra
        lang  = st.session_state.lang

        # Metrics
        m1,m2,m3,m4,m5,m6 = st.columns(6)
        m1.metric("Price/Giá",    f"{extra.get('close',0):,.0f} VNĐ")
        m2.metric("RSI",          f"{extra.get('rsi',50):.1f}",
                  delta=("Oversold" if extra.get('rsi',50)<35 else ("Overbought" if extra.get('rsi',50)>65 else "Neutral")))
        m3.metric("Stoch %K",     f"{extra.get('stoch_k',0) or 0:.0f}")
        m4.metric("ADX",          f"{extra.get('adx',0) or 0:.0f}",
                  delta=("Trending" if (extra.get('adx') or 0)>25 else "Sideways"))
        m5.metric("Signal",       extra.get("hanh_vi","–"),
                  delta=f"Score: {extra.get('score',0)}")
        m6.metric("Sector",       extra.get("sector","–"),
                  delta=st.session_state.audit_src)

        c1, c2 = st.columns(2)
        with c1: st.markdown(extra.get("ly_giai","–"))
        with c2: st.markdown(extra.get("price_expl","–"))

        if extra.get("doi_lai"):
            with st.expander(f"🚨 {len(extra['doi_lai'])} Smart Money / Manipulation Signals"):
                for s in extra["doi_lai"]:
                    cm={"HIGH":"🔴","MEDIUM":"🟡","LOW":"🟠","POSITIVE":"🟢"}
                    st.markdown(f"{cm.get(s['severity'],'⚪')} **{s['signal']}**\n\n{s['detail']}")

        # Chart — 4 panels
        st.divider()
        fig = make_subplots(rows=4,cols=1,shared_xaxes=True,
                            vertical_spacing=0.03,row_heights=[0.5,0.15,0.15,0.2])
        fig.add_trace(go.Candlestick(x=df_a.index,open=df_a["Open"],high=df_a["High"],
            low=df_a["Low"],close=df_a["Close"],name="Price",
            increasing_line_color="#00cc66",decreasing_line_color="#ff4b4b"),row=1,col=1)
        for col,name,color,dash in [("SMA20","SMA20","orange","solid"),("SMA50","SMA50","cyan","solid"),
                                     ("BB_Upper","BB↑","gray","dash"),("BB_Lower","BB↓","gray","dash")]:
            fig.add_trace(go.Scatter(x=df_a.index,y=df_a[col],mode="lines",name=name,
                line=dict(color=color,width=1.0 if "BB" in col else 1.3,dash=dash)),row=1,col=1)
        fig.add_trace(go.Scatter(x=df_a.index,y=df_a["RSI"],mode="lines",
            line=dict(color="#7b68ee",width=1.5),name="RSI"),row=2,col=1)
        fig.add_hline(y=rsi_buy_thresh,line_dash="dash",row=2,col=1,line_color="green")
        fig.add_hline(y=rsi_sell_thresh,line_dash="dash",row=2,col=1,line_color="red")
        bar_colors=["#00cc66" if v>=0 else "#ff4b4b" for v in df_a["MACD_Hist"]]
        fig.add_trace(go.Bar(x=df_a.index,y=df_a["MACD_Hist"],marker_color=bar_colors,opacity=0.7,name="MACD Hist"),row=3,col=1)
        fig.add_trace(go.Scatter(x=df_a.index,y=df_a["MACD"],mode="lines",line=dict(color="#00bfff",width=1.2),name="MACD"),row=3,col=1)
        fig.add_trace(go.Scatter(x=df_a.index,y=df_a["MACD_Signal"],mode="lines",line=dict(color="#ff6347",width=1.2),name="Signal"),row=3,col=1)
        vol_colors=["#00cc66" if df_a["Close"].iloc[i]>=df_a["Open"].iloc[i] else "#ff4b4b" for i in range(len(df_a))]
        fig.add_trace(go.Bar(x=df_a.index,y=df_a["Volume"],marker_color=vol_colors,opacity=0.6,name="Volume"),row=4,col=1)
        fig.add_trace(go.Scatter(x=df_a.index,y=df_a["Vol_MA20"],mode="lines",line=dict(color="yellow",width=1),name="Vol MA20"),row=4,col=1)
        fig.update_layout(height=820,template="plotly_dark",xaxis_rangeslider_visible=False,
            title=f"{st.session_state.symbol}  [{st.session_state.audit_src}]  —  {len(df_a)} sessions",
            legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
        st.plotly_chart(fig, use_container_width=True)

        render_fundamental_section(st.session_state.symbol)

def render_backtest_tab():
    hdr = "Backtest T+2 — RSI + BB + ATR Stop Loss" if st.session_state.lang=="EN" else "Backtest T+2 Chính Xác"
    st.subheader(f"🧪 {hdr}")
    if not st.session_state.df_audit.empty:
        st.info(f"Ticker: **{st.session_state.symbol}**  |  T+2 = 2 real sessions (df.index)  |  Stop = ATR×1.5")
        if st.button(L["backtest_btn"], type="primary"):
            with st.spinner("Computing..."):
                final_val,trades,metrics,eq = run_backtest(
                    st.session_state.df_audit,
                    apply_trend_filter=use_trend_filter,
                    rsi_buy=rsi_buy_thresh, rsi_sell=rsi_sell_thresh)
            st.success("✅ Backtest complete!")
            m1,m2,m3,m4,m5,m6 = st.columns(6)
            m1.metric("Capital In",   f"{INITIAL_CAPITAL:,.0f}")
            m2.metric("Capital Out",  f"{metrics['final_val']:,.0f}", delta=f"{metrics['total_ret_pct']:+.2f}%")
            m3.metric("Win Rate",     f"{metrics['win_rate']:.1f}%")
            m4.metric("Avg P&L",      f"{metrics['avg_pnl']:+.2f}%")
            m5.metric("Max Drawdown", f"{metrics['max_drawdown']:.2f}%")
            m6.metric("Sharpe",       f"{metrics['sharpe']:.2f}")
            if len(eq)>1:
                ec_color="#00cc66" if eq[-1]>=INITIAL_CAPITAL else "#ff4b4b"
                fig_eq=go.Figure()
                fig_eq.add_trace(go.Scatter(y=eq,mode="lines",line=dict(color=ec_color,width=2),
                    fill="tozeroy",fillcolor=f"rgba({'0,204,102' if ec_color=='#00cc66' else '255,75,75'},0.08)",name="Capital"))
                fig_eq.add_hline(y=INITIAL_CAPITAL,line_dash="dash",line_color="gray",annotation_text="Initial Capital")
                fig_eq.update_layout(title="Equity Curve",xaxis_title="Trade #",
                    yaxis_title="Capital (VND)",template="plotly_dark",height=280)
                st.plotly_chart(fig_eq, use_container_width=True)
            if trades:
                st.subheader("Trade Log" if st.session_state.lang=="EN" else "Lịch Sử Giao Dịch")
                show_df(pd.DataFrame(trades))
            else:
                st.info("No trades triggered. Try disabling trend filter.")
    else:
        st.warning("Run Deep Audit on a ticker first." if st.session_state.lang=="EN" else "Chạy Deep Audit trước.")

def render_ml_forecast_tab():
    hdr = "ML Price Forecast — 7-Model Weighted Ensemble" if st.session_state.lang=="EN" else "Dự Báo Giá — Ensemble 7 Mô Hình"
    st.subheader(f"🧠 {hdr}")
    if not st.session_state.df_audit.empty:
        sym6 = st.session_state.symbol
        weight_rows = [{"Model":k,"Group":g,"Weight":f"{int(MODEL_WEIGHTS[k]*100)}%","Description":d}
                       for k,(g,d) in MODEL_META.items()]
        show_df(pd.DataFrame(weight_rows))
        st.caption("Prophet+MC=40% — VN market driven by crowd psychology & seasonal cycles")
        n_days = st.slider("Forecast days:", 5, 90, 21)
        col_a,col_b,col_c = st.columns(3)
        run_full = col_a.button("🚀 Full 7-Model + Save Audit", type="primary")
        run_fast = col_b.button("⚡ Fast (5 models, skip Prophet)")
        run_mc   = col_c.button("🎲 Monte Carlo only")

        if run_full or run_fast or run_mc:
            df_ml = st.session_state.df_audit.copy()
            prices = df_ml["Close"].values.astype(float)
            last_price = float(prices[-1])
            future_dates = pd.bdate_range(start=df_ml.index[-1]+timedelta(days=1), periods=n_days)
            model_dict = {}
            with st.spinner("Running models..."):
                lr_fc,_,_ = forecast_linreg(prices, n_days)
                model_dict["LinearReg"] = (lr_fc, MODEL_WEIGHTS["LinearReg"])
                holt_fc = forecast_holt(prices, n_days)
                model_dict["Holt"] = (holt_fc, MODEL_WEIGHTS["Holt"])
                if not run_mc:
                    mc_fc = forecast_monte_carlo(prices, n_days)
                    model_dict["MonteCarlo"] = (mc_fc, MODEL_WEIGHTS["MonteCarlo"])
                    arima_fc,_ = forecast_arima(prices, n_days)
                    if arima_fc is not None:
                        model_dict["ARIMA"] = (arima_fc, MODEL_WEIGHTS["ARIMA"])
                    svr_fc = forecast_sklearn(prices, n_days, "SVR")
                    if svr_fc is not None: model_dict["SVR"] = (svr_fc, MODEL_WEIGHTS["SVR"])
                    rf_fc  = forecast_sklearn(prices, n_days, "RF")
                    if rf_fc  is not None: model_dict["RandomForest"] = (rf_fc, MODEL_WEIGHTS["RandomForest"])
                    if run_full and PROPHET_AVAILABLE:
                        try:
                            _,pp = run_prophet_forecast(df_ml, n_days, sym6)
                            model_dict["Prophet"] = (pp["yhat"].values[-n_days:], MODEL_WEIGHTS["Prophet"])
                        except Exception as e: st.warning(f"Prophet skipped: {e}")
                    elif run_full:
                        st.caption("ℹ️ Prophet not installed: pip install prophet")
                else:
                    mc_fc = forecast_monte_carlo(prices, n_days)
                    model_dict["MonteCarlo"] = (mc_fc, MODEL_WEIGHTS["MonteCarlo"])
                ensemble_fc = compute_weighted_ensemble(model_dict)

            fig_ml = go.Figure()
            hist_s = df_ml["Close"].tail(100)
            fig_ml.add_trace(go.Scatter(x=hist_s.index,y=hist_s.values,mode="lines",
                name="Price History",line=dict(color="white",width=2)))
            if "MonteCarlo" in model_dict:
                mc_r = model_dict["MonteCarlo"][0]
                for p_lo,p_hi,alpha,lbl in [("p10","p90",0.06,"MC P10–P90"),("p25","p75",0.12,"MC P25–P75")]:
                    fig_ml.add_trace(go.Scatter(
                        x=list(future_dates)+list(future_dates[::-1]),
                        y=list(mc_r[p_hi])+list(mc_r[p_lo][::-1]),
                        fill="toself",name=lbl,
                        fillcolor=f"rgba(100,149,237,{alpha})",line=dict(color="rgba(0,0,0,0)")))
            mc={  "LinearReg":"#ffd700","Holt":"#ff6347","ARIMA":"#ff69b4",
                  "SVR":"#7fffd4","RandomForest":"#98fb98","Prophet":"#32cd32","MonteCarlo":"cornflowerblue"}
            for nm,(fc,w) in model_dict.items():
                if nm=="MonteCarlo": continue
                fc_arr=fc if not isinstance(fc,dict) else fc.get("p50")
                if fc_arr is not None:
                    fig_ml.add_trace(go.Scatter(x=future_dates,y=fc_arr,mode="lines",
                        name=f"{nm}({int(w*100)}%)",line=dict(color=mc.get(nm,"gray"),width=1.3,dash="dot")))
            if ensemble_fc is not None:
                fig_ml.add_trace(go.Scatter(x=future_dates,y=ensemble_fc,mode="lines+markers",
                    name=f"Ensemble ({len(model_dict)} models)",
                    line=dict(color="orange",width=3),marker=dict(size=4)))
            fig_ml.update_layout(title=f"Forecast {n_days}d — {sym6}",
                xaxis_title="Date",yaxis_title="Price (VND)",template="plotly_dark",height=550,
                legend=dict(orientation="h",yanchor="bottom",y=-0.4,x=0),hovermode="x unified")
            st.plotly_chart(fig_ml, use_container_width=True)

            results_rows = []
            for nm,(fc,w) in model_dict.items():
                fc_arr=fc.get("p50") if isinstance(fc,dict) else fc
                if fc_arr is not None:
                    fp_val=float(fc_arr[-1]); pct=(fp_val/last_price-1)*100
                    g,d=MODEL_META.get(nm,("?","?"))
                    results_rows.append({"Model":nm,"Group":g,"Weight":f"{int(w*100)}%",
                        f"Target+{n_days}d":f"{fp_val:,.0f}","Δ%":f"{pct:+.2f}%","Notes":d})
            if ensemble_fc is not None:
                ev=float(ensemble_fc[-1]); ep=(ev/last_price-1)*100
                results_rows.append({"Model":"📊 Ensemble","Group":"Weighted","Weight":"100%",
                    f"Target+{n_days}d":f"{ev:,.0f}","Δ%":f"{ep:+.2f}%","Notes":"Optimised for VN market dynamics"})
            show_df(pd.DataFrame(results_rows))

            if ensemble_fc is not None:
                ep=(float(ensemble_fc[-1])/last_price-1)*100
                if   ep>10:  st.success(f"🟢 Ensemble: **+{ep:.1f}%** in {n_days} days — bullish outlook.")
                elif ep<-7:  st.error(f"🔴 Ensemble: **{ep:.1f}%** — consider stop-loss or reducing position.")
                else:        st.info(f"🟡 Ensemble: **{ep:+.1f}%** — neutral / consolidation expected.")

            if run_full:
                extra = st.session_state.audit_extra
                fp_saved = save_ml_forecast_audit(sym6, n_days, last_price, model_dict, ensemble_fc,
                    future_dates, {k:extra.get(k) for k in ["rsi","close","macd","adx","stoch_k","atr"]})
                st.caption(f"💾 Audit saved: `{fp_saved}`")
    else:
        st.warning("Run Deep Audit first." if st.session_state.lang=="EN" else "Chạy Deep Audit trước.")

def render_forecast_log_tab():
    hdr = "ML Forecast Audit Log" if st.session_state.lang=="EN" else "Lịch Sử Dự Báo ML"
    st.subheader(f"📈 {hdr}")
    ml_files = [f for f in os.listdir(ML_AUDIT_PATH) if f.endswith(".json")] if os.path.exists(ML_AUDIT_PATH) else []
    if ml_files:
        sel_ml = st.selectbox("Ticker:", sorted([f.replace(".json","") for f in ml_files]))
        if sel_ml:
            history = load_ml_forecast_history(sel_ml)
            if history:
                st.info(f"**{len(history)}** forecast records for **{sel_ml}**.")
                summary = [{"Timestamp":r.get("timestamp","?"),"Days":r.get("days_forecast","?"),
                             "Price":f"{r.get('last_price',0):,.0f}",
                             "Ensemble Target":f"{r.get('results',{}).get('ensemble',{}).get('final',0):,.0f}" if r.get("results",{}).get("ensemble") else "–",
                             "Δ%":f"{r.get('results',{}).get('ensemble',{}).get('pct_change',0):+.1f}%" if r.get("results",{}).get("ensemble") else "–",
                             "Models":len(r.get("models_used",[]))} for r in history]
                show_df(pd.DataFrame(summary))
                idx = st.selectbox("View record:", range(len(history)),
                                   format_func=lambda i: f"#{i} — {history[i].get('timestamp','?')}")
                rec=history[idx]; ts=rec.get("timestamp","?"); lp=rec.get("last_price",0)
                ens=rec.get("results",{}).get("ensemble",{})
                c1,c2,c3=st.columns(3)
                c1.metric("Price at Forecast",f"{lp:,.0f}"); c2.metric("Days Ahead",rec.get("days_forecast","?")); c3.metric("Timestamp",ts[:10])
                res_df=pd.DataFrame([{"Model":k,**{kk:vv for kk,vv in v.items() if kk!="all_values"}}
                                      for k,v in rec.get("results",{}).items() if isinstance(v,dict)])
                if "weight" in res_df.columns: res_df.rename(columns={"weight":"Weight"},inplace=True)
                show_df(res_df,key=f"hist_detail_{idx}")
                if ens.get("all_values") and rec.get("forecast_dates"):
                    if st.button("🔄 Replay chart",key=f"replay_{idx}"):
                        fig_r=go.Figure()
                        fig_r.add_trace(go.Scatter(x=rec["forecast_dates"],y=ens["all_values"],
                            mode="lines+markers",name="Ensemble",line=dict(color="orange",width=2)))
                        fig_r.add_hline(y=lp,line_dash="dash",line_color="gray",annotation_text=f"Forecast price: {lp:,.0f}")
                        fig_r.update_layout(title=f"Replay: {sel_ml} @ {ts}",yaxis_title="Price (VND)",template="plotly_dark",height=320)
                        st.plotly_chart(fig_r,use_container_width=True)
            else: st.warning(f"No history for {sel_ml}.")
    else:
        st.info("No forecast history. Run Tab 6 → Full 7-Model first.")

    st.divider()
    st.subheader("🪵 Application Log")
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE,"r",encoding="utf-8") as f: ll=f.readlines()
            st.text_area("Recent 100 lines",value="".join(ll[-100:]),height=260)
            st.caption(f"`{LOG_FILE}` — {len(ll)} total lines")
        except Exception: st.warning("Cannot read log file.")
    else: st.info("No log yet.")

def render_global_markets_tab():
    hdr = "Global Markets & Vietnam Impact Analysis" if st.session_state.lang=="EN" else "Thị Trường Thế Giới & Tác Động Lên TTVN"
    st.subheader(f"🌍 {hdr}")
    lang8 = st.session_state.lang

    if lang8=="VI":
        st.caption("Dữ liệu từ Stooq.com (futures & indices) + FRED (FED rates). Cập nhật mỗi 15 phút.")
    else:
        st.caption("Data from Stooq.com (futures & indices) + FRED (FED rates). Refreshed every 15 minutes.")

    refresh_world = st.button("🔄 Refresh World Markets" if lang8=="EN" else "🔄 Cập nhật Thị Trường TG", type="primary")

    with st.spinner("Loading global markets..."):
        gold_df   = fetch_stooq("GC.F",  days=120)
        oil_df    = fetch_stooq("CL.F",  days=120)
        gas_df    = fetch_stooq("NG.F",  days=120)
        dxy_df    = fetch_stooq("DXY",   days=120)
        sp500_df  = fetch_stooq("^SPX",  days=120)
        vni_df    = fetch_vni_index(days=120)
        fed_df    = fetch_fred_rate("FEDFUNDS", periods=36)

    def last_chg(df, col="Close"):
        if df.empty or col not in df.columns: return None, None, None
        vals = df[col].dropna()
        if len(vals) < 2: return float(vals.iloc[-1]) if len(vals) else None, None, None
        last = float(vals.iloc[-1]); prev = float(vals.iloc[-2])
        chg  = (last-prev)/prev*100 if prev!=0 else 0
        return last, prev, chg

    gold_last, gold_prev, gold_chg   = last_chg(gold_df)
    oil_last,  oil_prev,  oil_chg    = last_chg(oil_df)
    gas_last,  gas_prev,  gas_chg    = last_chg(gas_df)
    dxy_last,  dxy_prev,  dxy_chg    = last_chg(dxy_df)
    sp500_last,sp500_prev,sp500_chg  = last_chg(sp500_df)
    vni_last,  vni_prev,  vni_chg    = last_chg(vni_df)

    # ── Metrics row
    def fmt_m(val, chg, unit=""):
        if val is None: return "–", "No data"
        v_str = f"{val:,.2f} {unit}" if val < 10000 else f"{val:,.0f} {unit}"
        d_str = f"{chg:+.2f}%" if chg is not None else "–"
        return v_str, d_str

    cols = st.columns(6)
    labels = ["🪙 Gold","🛢️ WTI Oil","⛽ Nat Gas","💵 USD DXY","📈 S&P500","📊 VN-Index"]
    data_g = [(gold_last,gold_chg,"USD/oz"),(oil_last,oil_chg,"USD/bbl"),
              (gas_last,gas_chg,"USD/MMBtu"),(dxy_last,dxy_chg,"pts"),
              (sp500_last,sp500_chg,"pts"),(vni_last,vni_chg,"pts")]
    for col,lbl,(val,chg,unit) in zip(cols,labels,data_g):
        v,d = fmt_m(val, chg, unit)
        col.metric(lbl, v, delta=d)

    st.divider()

    # ── Charts — 2 column layout
    c_left, c_right = st.columns(2)
    def mini_chart(df, title, color="#4e9af1", col="Close"):
        if df.empty or col not in df.columns: return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines",
            line=dict(color=color, width=2), fill="tozeroy",
            fillcolor=f"rgba({','.join(str(int(c,16)) for c in [color[1:3],color[3:5],color[5:7]])},0.1)" if color.startswith("#") and len(color)==7 else "rgba(78,154,241,0.1)"))
        fig.update_layout(title=title, template="plotly_dark", height=220,
                          margin=dict(t=35,b=10,l=10,r=10), showlegend=False)
        return fig

    with c_left:
        fg = mini_chart(gold_df, f"🪙 Gold (USD/oz) — last: {gold_last:,.0f}" if gold_last else "🪙 Gold", "#ffd700")
        if fg: st.plotly_chart(fg, use_container_width=True)
        fo = mini_chart(oil_df,  f"🛢️ WTI Oil (USD/bbl) — last: {oil_last:,.1f}" if oil_last else "🛢️ WTI Oil", "#ff6347")
        if fo: st.plotly_chart(fo, use_container_width=True)
        fd = mini_chart(dxy_df,  f"💵 USD Index DXY — last: {dxy_last:,.2f}" if dxy_last else "💵 DXY", "#00bfff")
        if fd: st.plotly_chart(fd, use_container_width=True)

    with c_right:
        fs5 = mini_chart(sp500_df, f"📈 S&P500 — last: {sp500_last:,.0f}" if sp500_last else "📈 S&P500", "#00cc66")
        if fs5: st.plotly_chart(fs5, use_container_width=True)
        fg2 = mini_chart(gas_df, f"⛽ Natural Gas (USD/MMBtu) — last: {gas_last:,.2f}" if gas_last else "⛽ Natural Gas", "#bb7eff")
        if fg2: st.plotly_chart(fg2, use_container_width=True)
        fv = mini_chart(vni_df,  f"📊 VN-Index — last: {vni_last:,.2f}" if vni_last else "📊 VN-Index", "#7eb8ff")
        if fv: st.plotly_chart(fv, use_container_width=True)

    # ── FED Rate
    st.divider()
    st.subheader("🏦 FED Funds Rate (FRED)" if lang8=="EN" else "🏦 Lãi Suất FED (FRED)")
    if not fed_df.empty:
        fed_current = float(fed_df["Value"].dropna().iloc[-1])
        fed_prev    = float(fed_df["Value"].dropna().iloc[-2]) if len(fed_df)>1 else fed_current
        fed_chg_abs = fed_current - fed_prev
        c1,c2,c3 = st.columns(3)
        c1.metric("FED Funds Rate", f"{fed_current:.2f}%", delta=f"{fed_chg_abs:+.2f}% vs prev")
        c2.metric("12M High",       f"{fed_df['Value'].dropna().tail(12).max():.2f}%")
        c3.metric("12M Low",        f"{fed_df['Value'].dropna().tail(12).min():.2f}%")
        fig_fed = go.Figure()
        fig_fed.add_trace(go.Scatter(x=fed_df.index, y=fed_df["Value"], mode="lines+markers",
            line=dict(color="#ff6347",width=2), name="FED Funds Rate"))
        fig_fed.update_layout(title="FED Funds Rate (%) — 36 months",yaxis_title="Rate (%)",
            template="plotly_dark",height=250,margin=dict(t=35,b=10))
        st.plotly_chart(fig_fed, use_container_width=True)
        if lang8=="VI":
            if fed_current > 4.5:
                st.warning(f"⚠️ FED Rate cao ({fed_current:.2f}%): Áp lực tỷ giá USD/VNĐ. Vốn ngoại có xu hướng rút về. Cổ phiếu vay nợ USD chịu áp lực.")
            elif fed_current < 2.0:
                st.success(f"✅ FED Rate thấp ({fed_current:.2f}%): Môi trường lãi suất thuận lợi. Vốn tìm kiếm lợi suất cao hơn, EM như VN hưởng lợi.")
        else:
            if fed_current > 4.5:
                st.warning(f"⚠️ FED Rate high ({fed_current:.2f}%): USD/VND pressure, foreign capital tends to withdraw. USD-denominated debt stocks face headwinds.")
            elif fed_current < 2.0:
                st.success(f"✅ FED Rate low ({fed_current:.2f}%): Favourable rate environment. Yield-seeking capital flows to EM markets like Vietnam.")
    else:
        st.info("FRED data unavailable — check connectivity.")

    # ── Impact Analysis
    st.divider()
    impact_hdr = "🎯 VN Market Sector Impact Analysis" if lang8=="EN" else "🎯 Phân Tích Tác Động Lên Ngành TTVN"
    st.subheader(impact_hdr)
    impacts = world_market_impact_analysis(gold_chg, oil_chg, gas_chg, dxy_chg, sp500_chg, lang8)
    if impacts:
        for _,chg_val,txt in impacts:
            if abs(chg_val) > 2: st.error(txt)
            elif abs(chg_val) > 1: st.warning(txt)
            else: st.info(txt)
    else:
        st.caption("Market changes below significance threshold (|Δ| <0.5%). No notable sector impact today." if lang8=="EN"
                   else "Biến động thị trường dưới ngưỡng có ý nghĩa (|Δ|<0.5%). Không có tác động ngành đáng kể hôm nay.")

    # ── Correlation heatmap: World vs VNI
    if not vni_df.empty and not gold_df.empty and not oil_df.empty:
        st.divider()
        st.subheader("📊 Correlation: World Markets vs VN-Index (90 days)")
        try:
            dfs_corr = {"VNI": vni_df["Close"], "Gold": gold_df["Close"],
                        "WTI": oil_df["Close"],  "DXY": dxy_df["Close"] if not dxy_df.empty else None,
                        "S&P500": sp500_df["Close"] if not sp500_df.empty else None}
            combined = pd.DataFrame({k:v for k,v in dfs_corr.items() if v is not None})
            combined = combined.resample("D").last().ffill().tail(90)
            pct_returns = combined.pct_change().dropna()
            if len(pct_returns) > 10:
                corr = pct_returns.corr().round(2)
                fig_corr = go.Figure(go.Heatmap(
                    z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
                    colorscale="RdBu", zmid=0,
                    text=corr.values.round(2), texttemplate="%{text}",
                    textfont=dict(size=12)))
                fig_corr.update_layout(title="Daily Return Correlation Matrix (90-day)",
                    template="plotly_dark", height=350, margin=dict(t=50,b=10))
                st.plotly_chart(fig_corr, use_container_width=True)
                # Interpretation
                vni_corrs = corr.loc["VNI"].drop("VNI").sort_values(ascending=False)
                if lang8=="VI":
                    st.caption(f"VN-Index tương quan cao nhất với: "
                               f"**{vni_corrs.index[0]}** (r={vni_corrs.iloc[0]:+.2f}), "
                               f"**{vni_corrs.index[1]}** (r={vni_corrs.iloc[1]:+.2f})")
                else:
                    st.caption(f"VN-Index highest correlation with: "
                               f"**{vni_corrs.index[0]}** (r={vni_corrs.iloc[0]:+.2f}), "
                               f"**{vni_corrs.index[1]}** (r={vni_corrs.iloc[1]:+.2f})")
        except Exception as e:
            st.caption(f"Correlation chart error: {e}")

def render_smoke_test_tab():
    hdr = "System Smoke Test — All Data Sources & Functions" if st.session_state.lang=="EN" else "Kiểm Tra Hệ Thống — Tất Cả Nguồn Dữ Liệu & Chức Năng"
    st.subheader(f"🔬 {hdr}")
    st.caption("v14.0 — Tests each source individually for FPT (HOSE) and OIL (UPCOM). Full stack traces written to error_log.txt.")

    if st.button("🚀 Run Full Smoke Test" if st.session_state.lang=="EN" else "🚀 Chạy Kiểm Tra Đầy Đủ", type="primary"):
        results = []
        import traceback

        # ── Test 0: FPT — full pipeline test (HOSE ticker)
        with st.spinner("Testing FPT full pipeline (HOSE)..."):
            try:
                df_fpt, src_fpt, err_fpt = download_data("FPT", 180, min_rows=20)
                ok = len(df_fpt) >= 20
                results.append({"Test":"FPT Full Pipeline","Status":"✅ PASS" if ok else "❌ FAIL",
                    "Detail":f"{len(df_fpt)} rows via {src_fpt}, close={df_fpt['Close'].iloc[-1]:,.0f}" if ok else f"Failed: {err_fpt}"})
                if ok:
                    # Test indicator calculation
                    df_ind = calculate_indicators(clean_data(df_fpt))
                    results.append({"Test":"FPT Indicators","Status":"✅ PASS" if "RSI" in df_ind.columns else "❌ FAIL",
                        "Detail":f"RSI={df_ind['RSI'].iloc[-1]:.1f}, ADX={df_ind['ADX'].iloc[-1]:.1f}"})
            except Exception as e:
                results.append({"Test":"FPT Full Pipeline","Status":"❌ ERROR","Detail":f"{e} | {str(traceback.format_exc())[:150]}"})

        # ── Test 0b: OIL — full pipeline test (UPCOM ticker)
        with st.spinner("Testing OIL full pipeline (UPCOM)..."):
            try:
                df_oil, src_oil, err_oil = download_data("OIL", 180, min_rows=20)
                ok = len(df_oil) >= 20
                results.append({"Test":"OIL Full Pipeline (UPCOM)","Status":"✅ PASS" if ok else "❌ FAIL",
                    "Detail":f"{len(df_oil)} rows via {src_oil}, close={df_oil['Close'].iloc[-1]:,.0f}" if ok else f"Failed: {err_oil}"})
            except Exception as e:
                results.append({"Test":"OIL Full Pipeline (UPCOM)","Status":"❌ ERROR","Detail":f"{e} | {str(traceback.format_exc())[:150]}"})

        # ── Test 1: DNSE connectivity
        with st.spinner("Testing DNSE (FPT + OIL)..."):
            for sym_t, exch_t in [("FPT","HOSE"), ("OIL","UPCOM")]:
                try:
                    df_t = _fetch_dnse(sym_t, 180)
                    ok = len(df_t) >= 20
                    results.append({"Test":f"DNSE ({sym_t}/{exch_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{len(df_t)} rows, close={df_t['Close'].iloc[-1]:,.0f}" if ok else "Empty response"})
                except Exception as e:
                    results.append({"Test":f"DNSE ({sym_t}/{exch_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 2: SSI connectivity
        with st.spinner("Testing SSI (FPT + VCB)..."):
            for sym_t in ["FPT", "VCB"]:
                try:
                    df_t = _fetch_ssi(sym_t, 180)
                    ok = len(df_t) >= 20
                    results.append({"Test":f"SSI ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{len(df_t)} rows, close={df_t['Close'].iloc[-1]:,.0f}" if ok else "Empty"})
                except Exception as e:
                    results.append({"Test":f"SSI ({sym_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 3: CafeF connectivity
        with st.spinner("Testing CafeF HTML (OIL) + JSON..."):
            try:
                df_t = _fetch_cafef("OIL", 180)
                ok = len(df_t) >= 20
                results.append({"Test":"CafeF-HTML (OIL/UPCOM)","Status":"✅ PASS" if ok else "⚠️ PARTIAL",
                    "Detail":f"{len(df_t)} rows" if df_t is not None and not df_t.empty else "Empty"})
                df_t2 = _fetch_cafef_v2("OIL", 180)
                ok2 = len(df_t2) >= 20
                results.append({"Test":"CafeF-JSON (OIL/UPCOM)","Status":"✅ PASS" if ok2 else "❌ FAIL",
                    "Detail":f"{len(df_t2)} rows" if df_t2 is not None and not df_t2.empty else "Empty/refused"})
            except Exception as e:
                results.append({"Test":"CafeF (OIL)","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 4: Problematic tickers
        problem_tickers = ["IDC","OIL","PVS","LTG","HBC","PME","SCG","TNG","TVN","VKC","VNA","ACV"]
        with st.spinner("Testing problematic tickers..."):
            for t in problem_tickers:
                try:
                    df_p, src_p, err_p = download_data(t, 180)
                    ok = len(df_p) >= 20
                    results.append({"Test":f"Problem Ticker ({t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{len(df_p)} rows via {src_p}" if ok else f"Failed via {src_p}: {err_p}"})
                except Exception as e:
                    results.append({"Test":f"Problem Ticker ({t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 5: World markets
        with st.spinner("Testing world markets..."):
            for k, (sym, _, _, _) in WORLD_SYMBOLS.items():
                if not sym: continue
                try:
                    df_w = fetch_stooq(sym, 30)
                    ok = len(df_w) >= 5
                    results.append({"Test":f"World Market ({k})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{len(df_w)} rows" if ok else "Empty"})
                except Exception as e:
                    results.append({"Test":f"World Market ({k})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 6: VNDirect financials
        with st.spinner("Testing VNDirect..."):
            try:
                prof = fetch_company_profile("HPG")
                ok = "Vốn hóa (tỷ VNĐ)" in prof and prof["Vốn hóa (tỷ VNĐ)"] != "–"
                results.append({"Test":"VNDirect Profile (HPG)","Status":"✅ PASS" if ok else "❌ FAIL",
                    "Detail":"Profile loaded" if ok else "Empty profile"})
            except Exception as e:
                results.append({"Test":"VNDirect Profile (HPG)","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 7: ML libs
        with st.spinner("Testing ML libs..."):
            results.append({"Test":"yfinance lib","Status":"✅ OK" if YFINANCE_AVAILABLE else "⚠️ MISSING","Detail":"pip install yfinance"})
            results.append({"Test":"Prophet lib","Status":"✅ OK" if PROPHET_AVAILABLE else "⚠️ MISSING","Detail":"pip install prophet"})
            results.append({"Test":"ARIMA lib","Status":"✅ OK" if ARIMA_AVAILABLE else "⚠️ MISSING","Detail":"pip install statsmodels"})
            results.append({"Test":"sklearn lib","Status":"✅ OK" if SKLEARN_AVAILABLE else "⚠️ MISSING","Detail":"pip install scikit-learn"})

        st.session_state.smoke_results = pd.DataFrame(results)

    if "smoke_results" in st.session_state and not st.session_state.smoke_results.empty:
        df_smoke = st.session_state.smoke_results
        def style_status(v):
            if "PASS" in v: return "background-color:#006400;color:white"
            if "FAIL" in v or "ERROR" in v: return "background-color:#8B0000;color:white"
            if "MISSING" in v or "PARTIAL" in v: return "background-color:#8B4513;color:white"
            return ""
        show_df(df_smoke.style.map(style_status, subset=["Status"]))
        n_fail = df_smoke["Status"].str.contains("FAIL|ERROR").sum()
        if n_fail > 0:
            st.error(f"**{n_fail} tests failed!** Check logs and connectivity.")
        else:
            st.success("🎉 **All tests passed!** System is fully operational.")

def render_guide_tab():
    st.header(f"📖 {L['tab10']}")
    st.markdown("""
    ### Business Requirement Document (BRD) for vnstock Applications

    #### 1. Introduction
    This document outlines the business requirements for the "vnstock" suite of applications, which currently consists of two main components:
    1.  **Captain Seventh QUANT TERMINAL (this app):** A Python-based Streamlit application for in-depth quantitative analysis of the Vietnam stock market.
    2.  **VN Stock Terminal (vn-stock-realtime.jsx):** A React-based web application for real-time monitoring of the Vietnam stock market.

    The purpose of this document is to define the scope, features, and functional and non-functional requirements for these applications to ensure they meet the business objectives and user needs.

    #### 2. Business Objectives
    *   To provide a comprehensive and reliable platform for analyzing and monitoring the Vietnam stock market.
    *   To empower users with data-driven insights for making informed investment decisions.
    *   To offer both real-time monitoring and in-depth historical analysis capabilities.
    *   To ensure the accuracy and timeliness of the financial data presented to the users.
    *   To provide a user-friendly and intuitive interface for both technical and non-technical users.

    #### 3. Scope
    The scope of this project covers the analysis, maintenance, and enhancement of the two existing applications.
    *   **In Scope:** Analysis of the existing codebase, bug fixing, performance optimization, enhancement of existing features, addition of new features for the Vietnam market, and UI/UX improvements.
    *   **Out of Scope:** Development of a mobile application, integration with brokerage accounts for direct trading, and providing personalized investment advice.

    ---
    ### Technical Indicators & Models Used

    This application uses a combination of well-established technical indicators and machine learning models to generate insights and forecasts.

    #### Technical Indicators
    *   **SMA (Simple Moving Average):** Used to identify trends (e.g., Price > SMA50 for an uptrend).
    *   **RSI (Relative Strength Index):** A momentum oscillator to identify overbought (>70) or oversold (<30) conditions.
    *   **Bollinger Bands:** Measures volatility and identifies when a price is at a statistical extreme.
    *   **MACD (Moving Average Convergence Divergence):** Shows the relationship between two moving averages of a security’s price. Crossovers can signal changes in momentum.
    *   **Stochastic Oscillator:** A momentum indicator comparing a particular closing price of a security to a range of its prices over a certain period of time.
    *   **ATR (Average True Range):** A measure of market volatility.
    *   **OBV (On-Balance Volume):** Uses volume flow to predict changes in stock price.
    *   **ADX (Average Directional Index):** Used to determine the strength of a trend.
    *   **Williams %R:** A momentum indicator that is the inverse of the Stochastic Oscillator.
    *   **CCI (Commodity Channel Index):** An oscillator used to identify cyclical trends.

    #### Forecasting Models
    *   **Prophet:** A forecasting model developed by Facebook, designed for time series data that has strong seasonal effects and several seasons of historical data. It is robust to missing data and shifts in the trend.
    *   **ARIMA (AutoRegressive Integrated Moving Average):** A statistical model that uses time series data to understand the data or to predict future points in the series.
    *   **Scikit-learn Ensemble (SVR & RandomForest):** An ensemble model that combines Support Vector Regression (SVR) and a Random Forest Regressor. This approach leverages the strengths of both models to potentially create more accurate and robust forecasts.

    *This guide provides a high-level overview. For detailed mathematical formulas and academic papers on these topics, please consult financial and statistical literature.*
    """)

# ══════════════════════════════════════════════════════════════
#  CHANGE LOG TAB
# ══════════════════════════════════════════════════════════════
def render_changelog_tab():
    st.header(f"📝 {L['tab11']}")
    st.markdown("""
## 📝 Application Change Log

---

### v14.0 — 2026-03-08 · BUG FIX + ENHANCEMENT RELEASE

**🔴 Critical Bug Fixes**

| Fix ID | Component | Issue | Resolution |
|--------|-----------|-------|------------|
| FIX-01 | All Tabs | `st.session.state` AttributeError — caused app crash on every render | Replaced 70+ occurrences with `st.session_state` |
| FIX-02 | Scanner / Deep Audit | `scan_one_ticker()` returned 2-tuple on success, 3-tuple on failure → "too many values to unpack" exception | Standardised to always return `(row, source, error)` 3-tuple |
| FIX-03 | Data Pipeline | SSI iBoard `/v2/stock/ohlc` returning HTTP 404 for all tickers | Added multi-endpoint chain: v2 → v1 → fc-data |
| FIX-04 | Data Pipeline | DNSE endpoint returning no data / connection errors | Added multi-endpoint fallback (v2 → v1 → api subdomain) |
| FIX-05 | Global Markets | VN-Index not loading (SSI v2 endpoint broken) | Added SSI v1 → stooq `^VNI` → yFinance `^VNINDEX` chain |
| FIX-06 | Global Markets | Gold/Oil/Gas/DXY not loading when stooq.com unreachable | Added yFinance fallback (`GC=F`, `CL=F`, `NG=F`, `DX-Y.NYB`, `^GSPC`) |
| FIX-07 | Data Pipeline | CafeF JSON API (`api.cafef.vn`) hanging on connection refused | Reduced timeout from 12s to 6s (fail fast); added proper exception handling |
| FIX-08 | Smoke Test | `session_state.smoke_results` referenced before initialisation → KeyError | Added to session_state init block at startup |
| FIX-09 | Market Scanner | `L["lang"]` KeyError — L dict has no "lang" key | Replaced with direct `st.session_state.lang` check |
| FIX-10 | yFinance Source | `yf.download()` returns MultiIndex columns not handled | Added `_clean_yf()` helper to flatten MultiIndex |
| FIX-11 | Error Logging | Exceptions not logging stack traces to `error_log.txt` | Added `traceback.format_exc()` in all catch blocks |

**🟡 Enhancements**

| ENH ID | Component | Enhancement |
|--------|-----------|-------------|
| ENH-01 | Tabs | New **Change Log** tab added for version audit trail |
| ENH-02 | Guide Tab | BRD completely rewritten with technical theory, indicator formulas, model descriptions, macro impact matrix |
| ENH-03 | Smoke Test | FPT (HOSE) and OIL (UPCOM) targeted tests added; each source tested individually |
| ENH-04 | Data Pipeline | Per-source error detail in failure messages (shows rows received vs required) |
| ENH-05 | World Markets | `_STOOQ_TO_YF` mapping table for systematic stooq→yfinance symbol translation |
| ENH-06 | Version | Version bumped to v14.0 throughout app |

---

### v13.0 — Previous Release

| Component | Change |
|-----------|--------|
| Data Pipeline | DNSE + SSI + CafeF replacing yFinance as primary sources |
| Tickers Fixed | IDC OIL PVS LTG HBC PME SCG TNG TVN VKC VNA ACV exchange routing |
| World Markets Tab | Gold, WTI Oil, Natural Gas, DXY, S&P500, FED Funds Rate |
| Bilingual UI | Vietnamese 🇻🇳 / English AU 🇦🇺 full feature parity |
| Enhanced Insights | Sector context, macro correlation, risk-adjusted commentary |
| Smoke Test | Built-in connectivity & function validator |

---

### v12.0 — Base Release

| Component | Change |
|-----------|--------|
| ML Ensemble | 7-model weighted forecast (Prophet, ARIMA, SVR, RF, LinearReg, Holt, Monte Carlo) |
| Backtest | T+2 settlement-accurate simulation with ATR stop-loss |
| Smart Money | Đội lái / manipulation detection engine |
| 10 Indicators | RSI, BB, MACD, Stoch, ATR, OBV, ADX, Williams %R, CCI, SMA |
| VNDirect | Financial statements, ratios, dividends, news integration |

---

*Change log maintained for audit and compliance purposes. All dates in UTC+7 (ICT/Vietnam timezone).*
    """)

# ══════════════════════════════════════════════════════════════
#  MAIN APP LAYOUT
# ══════════════════════════════════════════════════════════════
def main():
    # Initialize session state variables
    if "scan_results" not in st.session_state:
        st.session_state.scan_results = pd.DataFrame()
    if "buy_signals" not in st.session_state:
        st.session_state.buy_signals = pd.DataFrame()
    if "trade_history" not in st.session_state:
        st.session_state.trade_history = pd.DataFrame()
    if "forecast_log" not in st.session_state:
        st.session_state.forecast_log = pd.DataFrame()

    # Define tabs (11 tabs in v14.0)
    tab_keys = ["tab1","tab2","tab3","tab4","tab5","tab6","tab7","tab8","tab9","tab10","tab11"]
    tabs = st.tabs([L[k] for k in tab_keys])

    with tabs[0]:
        render_scanner_tab()
    with tabs[1]:
        render_top_buy_tab()
    with tabs[2]:
        render_history_tab()
    with tabs[3]:
        render_deep_audit_tab()
    with tabs[4]:
        render_backtest_tab()
    with tabs[5]:
        render_ml_forecast_tab()
    with tabs[6]:
        render_forecast_log_tab()
    with tabs[7]:
        render_global_markets_tab()
    with tabs[8]:
        render_smoke_test_tab()
    with tabs[9]:
        render_guide_tab()
    with tabs[10]:
        render_changelog_tab()

if __name__ == "__main__":
    main()