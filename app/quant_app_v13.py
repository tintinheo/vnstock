"""
╔══════════════════════════════════════════════════════════════════╗
║   Captain Seventh QUANT TERMINAL  v20.0                         ║
║   Vietnam Stock Market Analysis & AI Forecasting Platform       ║
╠══════════════════════════════════════════════════════════════════╣
║  CHANGELOG v19 → v20:                                           ║
║  FIX-19: RESOLVED Signal Divergence (Scanner BUY vs Profiler   ║
║    SELL for same ticker):                                        ║
║    Root cause: Scanner = pure technical SHORT-TERM (T+2),       ║
║    Profiler = fundamental+valuation LONG-TERM (6-24M).          ║
║    Both can be TRUE simultaneously for different horizons.       ║
║    Fix: Timeframe labels on all signals; Profiler S6 now shows  ║
║    BOTH technical (scanner) AND fundamental signals with        ║
║    explicit horizon labels; conflict detection banner; unified   ║
║    blended recommendation with transparent weighting.           ║
║  ENH-15: Scanner — added Horizon column (Short-term T+2)       ║
║  ENH-16: Profiler S6 — Dual-signal view: Tech vs Fundamental   ║
║  ENH-17: Conflict Detection — warns when Tech ≠ Fundamental    ║
║  ENH-18: Unified Blended Recommendation in Profiler            ║
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
    page_title="Captain Seventh QUANT TERMINAL v20.0",
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
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v20.0",
    "sidebar_hdr":     "⚙️ Tùy Chỉnh Chiến Lược",
    "lang_label":      "🌐 Ngôn ngữ / Language",
    "trend_filter":    "Lọc Xu hướng (Giá > SMA50)",
    "liq_filter":      "Lọc Thanh khoản (>1 tỷ/ngày)",
    "rsi_buy":         "Ngưỡng RSI Mua:",
    "rsi_sell":        "Ngưỡng RSI Bán:",
    "pipeline_lbl":    "📡 7 Sources: DNSE→SSI→CafeF→TCBS→VNDir",
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
    "tab12": "🧬 Hồ Sơ Cổ Phiếu",
    # Stock Profiler labels
    "sp_title":         "🧬 Hồ Sơ & Phân Tích Sâu Cổ Phiếu",
    "sp_ticker_input":  "Nhập mã cổ phiếu",
    "sp_analyse_btn":   "🔬 Phân Tích Ngay",
    "sp_overview":      "📋 Tổng Quan Công Ty",
    "sp_financials":    "📊 Báo Cáo Tài Chính",
    "sp_ratios":        "📐 Chỉ Số Tài Chính",
    "sp_valuation":     "💎 Định Giá",
    "sp_risk":          "⚠️ Phân Tích Rủi Ro",
    "sp_recommendation":"🎯 Khuyến Nghị",
    "sp_income":        "Kết Quả Kinh Doanh",
    "sp_balance":       "Bảng Cân Đối Kế Toán",
    "sp_cashflow":      "Lưu Chuyển Tiền Tệ",
    "sp_quarterly":     "Quý",
    "sp_yearly":        "Năm",
    "sp_loading":       "Đang tải dữ liệu...",
    "sp_no_data":       "Không có dữ liệu từ TCBS/VNDirect",
    "sp_dcf_label":     "🏗️ Định giá DCF",
    "sp_pe_label":      "📊 Định giá P/E so sánh",
    "sp_pb_label":      "📚 Định giá P/B",
    "sp_graham_label":  "🔢 Công thức Graham",
    "sp_fair_value":    "Giá trị hợp lý",
    "sp_upside":        "Tiềm năng tăng",
    "sp_current_price": "Giá hiện tại",
    "sp_rec_strong_buy":"✅ KHUYẾN NGHỊ MẠNH: MUA",
    "sp_rec_buy":       "🟢 KHUYẾN NGHỊ: MUA",
    "sp_rec_hold":      "🟡 KHUYẾN NGHỊ: NẮM GIỮ",
    "sp_rec_sell":      "🔴 KHUYẾN NGHỊ: BÁN",
    "sp_rec_strong_sell":"❌ KHUYẾN NGHỊ MẠNH: BÁN",
    "sp_score_label":   "Điểm tổng hợp",
    "sp_risk_debt":     "Rủi ro Nợ vay",
    "sp_risk_liq":      "Rủi ro Thanh khoản",
    "sp_risk_profit":   "Rủi ro Lợi nhuận",
    "sp_risk_growth":   "Rủi ro Tăng trưởng",
    "sp_risk_valuation":"Rủi ro Định giá",
    "sp_source_tcbs":   "Nguồn: TCBS tcanalysis API",
    "sp_source_vnd":    "Nguồn: VNDirect FINFO API",
    "sp_peer_compare":  "🏭 So sánh ngành",
    "sp_ttm_label":     "Trailing 12M",
    # Dual-signal / timeframe labels (ENH-15/16/17/18)
    "signal_tech":      "📈 Tín hiệu Kỹ thuật",
    "signal_fund":      "📊 Tín hiệu Cơ bản",
    "signal_unified":   "🎯 Khuyến Nghị Tổng Hợp",
    "horizon_short":    "Ngắn hạn (T+2, 1-5 ngày)",
    "horizon_long":     "Dài hạn (6-24 tháng)",
    "horizon_unified":  "Tổng hợp",
    "conflict_title":   "⚡ Tín hiệu Phân Kỳ — Giải thích",
    "conflict_body_vi": (
        "**Tại sao Scanner nói MUA trong khi Profiler nói BÁN (hoặc ngược lại)?**\n\n"
        "Đây **KHÔNG phải lỗi** — đây là hai góc nhìn hoàn toàn khác nhau về cùng một cổ phiếu:\n\n"
        "| Chiều đo | Market Scanner | Stock Profiler |\n"
        "|----------|---------------|----------------|\n"
        "| **Phương pháp** | Phân tích kỹ thuật thuần túy | Cơ bản + Định giá |\n"
        "| **Tín hiệu** | RSI quá bán + Giá dưới BB Lower | DCF / P/E / P/B / Graham |\n"
        "| **Chân trời** | 1–5 phiên giao dịch (T+2) | 6–24 tháng |\n"
        "| **Câu hỏi** | 'Giá có hồi phục ngắn hạn?' | 'Cổ phiếu có đang bị định giá đúng?' |\n\n"
        "**Ví dụ thực tế:** MWG có thể vừa quá bán kỹ thuật (cơ hội bounce ngắn hạn) "
        "vừa giao dịch trên giá trị nội tại DCF/Graham (không hấp dẫn dài hạn). "
        "Cả hai đều đúng — chỉ khác mục tiêu đầu tư."
    ),
    "scanner_horizon_label": "⏱️ T+2 (Kỹ thuật)",
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
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v20.0",
    "sidebar_hdr":     "⚙️ Strategy Settings",
    "lang_label":      "🌐 Language / Ngôn ngữ",
    "trend_filter":    "Trend Filter (Price > SMA50)",
    "liq_filter":      "Liquidity Filter (>1B VND/day)",
    "rsi_buy":         "RSI Buy Threshold:",
    "rsi_sell":        "RSI Sell Threshold:",
    "pipeline_lbl":    "📡 7 Sources: DNSE→SSI→CafeF→TCBS→VNDir",
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
    "tab12": "🧬 Stock Profiler",
    # Stock Profiler labels
    "sp_title":         "🧬 Stock Profile & Deep Analysis",
    "sp_ticker_input":  "Enter ticker symbol",
    "sp_analyse_btn":   "🔬 Analyse Now",
    "sp_overview":      "📋 Company Overview",
    "sp_financials":    "📊 Financial Statements",
    "sp_ratios":        "📐 Financial Ratios",
    "sp_valuation":     "💎 Valuation",
    "sp_risk":          "⚠️ Risk Analysis",
    "sp_recommendation":"🎯 Recommendation",
    "sp_income":        "Income Statement",
    "sp_balance":       "Balance Sheet",
    "sp_cashflow":      "Cash Flow Statement",
    "sp_quarterly":     "Quarterly",
    "sp_yearly":        "Annual",
    "sp_loading":       "Loading data...",
    "sp_no_data":       "No data from TCBS/VNDirect",
    "sp_dcf_label":     "🏗️ DCF Valuation",
    "sp_pe_label":      "📊 P/E Relative Valuation",
    "sp_pb_label":      "📚 P/B Valuation",
    "sp_graham_label":  "🔢 Graham Formula",
    "sp_fair_value":    "Fair Value",
    "sp_upside":        "Upside Potential",
    "sp_current_price": "Current Price",
    "sp_rec_strong_buy":"✅ STRONG BUY",
    "sp_rec_buy":       "🟢 BUY",
    "sp_rec_hold":      "🟡 HOLD",
    "sp_rec_sell":      "🔴 SELL",
    "sp_rec_strong_sell":"❌ STRONG SELL",
    "sp_score_label":   "Composite Score",
    "sp_risk_debt":     "Debt Risk",
    "sp_risk_liq":      "Liquidity Risk",
    "sp_risk_profit":   "Profitability Risk",
    "sp_risk_growth":   "Growth Risk",
    "sp_risk_valuation":"Valuation Risk",
    "sp_source_tcbs":   "Source: TCBS tcanalysis API",
    "sp_source_vnd":    "Source: VNDirect FINFO API",
    "sp_peer_compare":  "🏭 Sector Comparison",
    "sp_ttm_label":     "Trailing 12M",
    # Dual-signal / timeframe labels (ENH-15/16/17/18)
    "signal_tech":      "📈 Technical Signal",
    "signal_fund":      "📊 Fundamental Signal",
    "signal_unified":   "🎯 Unified Recommendation",
    "horizon_short":    "Short-term (T+2, 1-5 days)",
    "horizon_long":     "Long-term (6-24 months)",
    "horizon_unified":  "Blended",
    "conflict_title":   "⚡ Signal Divergence — Explained",
    "conflict_body_vi": (
        "**Why does Scanner say BUY while Profiler says SELL (or vice versa)?**\n\n"
        "This is **NOT a bug** — these are two fundamentally different perspectives on the same stock:\n\n"
        "| Dimension | Market Scanner | Stock Profiler |\n"
        "|-----------|---------------|----------------|\n"
        "| **Method** | Pure technical analysis | Fundamental + Valuation |\n"
        "| **Signal** | RSI oversold + Price < BB Lower | DCF / P/E / P/B / Graham |\n"
        "| **Horizon** | 1–5 trading sessions (T+2) | 6–24 months |\n"
        "| **Question** | 'Will price bounce short-term?' | 'Is the stock fairly valued?' |\n\n"
        "**Real example:** MWG can be simultaneously technically oversold (short-term bounce opportunity) "
        "and trading above its DCF/Graham intrinsic value (unattractive for long-term). "
        "Both are correct — they serve different investment objectives."
    ),
    "scanner_horizon_label": "⏱️ T+2 (Technical)",
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
def get_price_limits(ticker: str, ref_price: float) -> dict:
    """
    ENH-25: Vietnam exchange price limits (Giá trần/sàn/tham chiếu).
    HOSE: ±7% | HNX: ±10% | UPCOM: ±15%
    ref_price: prior day close (GiaThamChieu from CafeF)
    """
    exch = TICKER_EXCHANGE.get(ticker, "HOSE")
    pct  = {"HOSE": 0.07, "HNX": 0.10, "UPCOM": 0.15}.get(exch, 0.07)
    if ref_price <= 0:
        return {}
    # Round to nearest 100 VND (HOSE) or 100 VND (HNX/UPCOM)
    ceiling = round(ref_price * (1 + pct) / 100) * 100
    floor   = round(ref_price * (1 - pct) / 100) * 100
    return {
        "ceiling":   ceiling,
        "floor":     floor,
        "reference": ref_price,
        "exchange":  exch,
        "band_pct":  pct * 100,
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
sb.caption(f"📡 Pipeline: DNSE→SSI→CafeF→TCBS→VNDir→yF")
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
    P1: DNSE — api.dnse.com.vn/chart-api/v2  (FIX-16: confirmed working 2026-03-08)
    Confirmed working: api.dnse.com.vn, resolution=1D (247 rows for FCN verified).
    services.entrade.com.vn → DEAD (replaced in v17).
    Returns TradingView UDF format: {t, o, h, l, c, v, s}
    ✓ No auth  ✓ HOSE+HNX+UPCOM  ✓ Full history
    """
    import traceback
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = (f"https://api.dnse.com.vn/chart-api/v2/ohlcs/stock"
           f"?symbol={symbol}&resolution=1D&from={from_ts}&to={to_ts}")
    try:
        r = _HTTP.get(url, timeout=API_TIMEOUT)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, dict):
            _log.debug(f"DNSE {symbol}: unexpected response type {type(raw)}")
            return pd.DataFrame()
        df = _parse_udf(raw, source=f"DNSE({symbol})")
        if not df.empty:
            _log.info(f"DNSE ✅ {symbol}: {len(df)} rows, close={df['Close'].iloc[-1]:,.0f}")
        return df
    except requests.exceptions.HTTPError as e:
        _log.warning(f"DNSE HTTP error {symbol}: {e}")
    except requests.exceptions.ConnectionError as e:
        _log.warning(f"DNSE connection error {symbol}: {e}")
    except requests.exceptions.Timeout:
        _log.warning(f"DNSE timeout {symbol}")
    except ValueError as e:
        _log.warning(f"DNSE JSON decode error {symbol}: {e}")
    except Exception as e:
        _log.error(f"DNSE unexpected error {symbol}: {e}"); _log.debug(traceback.format_exc())
    return pd.DataFrame()


def _parse_ssi_response(raw: dict, symbol: str) -> pd.DataFrame:
    """
    Parse SSI iboard-api response which can come in multiple formats:
    Format A: {"data": {"t":[...],"o":[...],"h":[...],"l":[...],"c":[...],"v":[...]}}
    Format B: flat TradingView UDF {"t":[...],"c":[...],...}
    Format C: {"data": [{"time":...,"open":...,"high":...,"low":...,"close":...,"volume":...},...]}
    """
    if not raw:
        return pd.DataFrame()
    # Unwrap nested "data" key if present
    inner = raw.get("data", raw)
    # Format C: list of dicts
    if isinstance(inner, list) and inner:
        rows = []
        for it in inner:
            try:
                ts = it.get("time", it.get("t", it.get("date", None)))
                cl = it.get("close", it.get("c", it.get("Close", None)))
                if ts is None or cl is None: continue
                # ts may be Unix timestamp or ISO string
                try:
                    dt = pd.Timestamp(ts, unit="s") if isinstance(ts, (int,float)) else pd.Timestamp(ts)
                except Exception:
                    continue
                rows.append({
                    "Date":  dt,
                    "Open":  float(it.get("open",  it.get("o", cl)) or cl),
                    "High":  float(it.get("high",  it.get("h", cl)) or cl),
                    "Low":   float(it.get("low",   it.get("l", cl)) or cl),
                    "Close": float(cl),
                    "Volume":float(it.get("volume",it.get("v",  0))  or 0),
                })
            except Exception:
                continue
        if rows:
            df = pd.DataFrame(rows).set_index("Date").sort_index()
            df = df[~df.index.duplicated(keep="last")]
            if not df.empty and df["Close"].dropna().median() < 500:
                for c in ["Open","High","Low","Close"]: df[c] *= 1000
            return df
    # Format A/B: UDF dict with arrays
    if isinstance(inner, dict):
        return _parse_udf(inner, source=f"SSI({symbol})")
    return pd.DataFrame()


def _fetch_ssi(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P2: SSI iBoard API — multiple endpoints tried in order.
    Confirmed working endpoint (user-verified 2026-03-08):
      iboard-api.ssi.com.vn/statistics/charts/history
    Also tries iboard-query.ssi.com.vn as secondary.
    ✓ HOSE/HNX/UPCOM  ✓ Real-time  ✓ No auth required
    """
    import traceback
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    
    # Endpoint list — iboard-api first (confirmed working), then fallbacks
    endpoints = [
        # ① Confirmed working 2026-03 (user verified)
        (f"https://iboard-api.ssi.com.vn/statistics/charts/history"
         f"?resolution=1D&symbol={symbol}&from={from_ts}&to={to_ts}",
         {"User-Agent":"Mozilla/5.0","Accept":"application/json",
          "Referer":"https://iboard.ssi.com.vn/","Origin":"https://iboard.ssi.com.vn"}),
        # ② Legacy iboard-query (may return 404 on /v2 but /stock/ohlc may still work)
        (f"https://iboard-query.ssi.com.vn/stock/ohlc"
         f"?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
         {"User-Agent":"Mozilla/5.0","Referer":"https://iboard.ssi.com.vn/"}),
        # ③ fc-data subdomain
        (f"https://fc-data.ssi.com.vn/api/v2/stock/ohlc"
         f"?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
         {"User-Agent":"Mozilla/5.0","Referer":"https://iboard.ssi.com.vn/"}),
    ]
    
    for url, hdrs in endpoints:
        try:
            r = requests.get(url, headers=hdrs, timeout=API_TIMEOUT)
            r.raise_for_status()
            raw = r.json()
            df = _parse_ssi_response(raw, symbol)
            if not df.empty and len(df) >= 5:
                _log.info(f"SSI ✅ {symbol}: {len(df)} rows via {url[:70]}")
                return df
            else:
                _log.debug(f"SSI {symbol}: empty/short response from {url[:70]}")
        except requests.exceptions.HTTPError as e:
            _log.warning(f"SSI HTTP error {symbol} [{url[:60]}]: {e}")
        except requests.exceptions.ConnectionError as e:
            _log.warning(f"SSI connection error {symbol}: {e}")
        except requests.exceptions.Timeout:
            _log.warning(f"SSI timeout {symbol} [{url[:60]}]")
        except ValueError as e:
            _log.warning(f"SSI JSON decode error {symbol}: {e}")
        except Exception as e:
            _log.error(f"SSI unexpected error {symbol}: {e}"); _log.debug(traceback.format_exc())
    
    return pd.DataFrame()


def _parse_cafef_table(html_text: str, symbol: str) -> pd.DataFrame:
    """Parse CafeF HTML tables — tries multiple column naming conventions."""
    try:
        dfs = pd.read_html(io.StringIO(html_text), flavor="lxml")
        if not dfs:
            return pd.DataFrame()
        # Try each table (last one is usually the data table)
        for df in reversed(dfs):
            col_rename = {}
            for col in df.columns:
                cl = str(col).lower().strip()
                if any(x in cl for x in ["ngày","ngay","date","thời gian"]): col_rename[col] = "Date"
                elif "đóng cửa" in cl or "close" in cl or "giá đóng" in cl: col_rename[col] = "Close"
                elif "mở cửa"  in cl or "open"  in cl or "giá mở"  in cl: col_rename[col] = "Open"
                elif "cao nhất" in cl or "high" in cl: col_rename[col] = "High"
                elif "thấp nhất" in cl or "low"  in cl: col_rename[col] = "Low"
                elif "khối lượng" in cl or "volume" in cl or "klgd" in cl: col_rename[col] = "Volume"
            if "Date" in col_rename.values() and "Close" in col_rename.values():
                df = df.rename(columns=col_rename)
                for c in ["Open","High","Low","Close","Volume"]:
                    if c in df.columns:
                        df[c] = pd.to_numeric(
                            df[c].astype(str).str.replace(r"[,\s]","",regex=True).str.replace("x","",regex=False),
                            errors="coerce").fillna(0)
                    else:
                        df[c] = df.get("Close", 0)
                df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
                out = df.set_index("Date")[["Open","High","Low","Close","Volume"]].copy()
                out = out.dropna(subset=["Close"]).sort_index()
                out = out[~out.index.duplicated(keep="last")]
                out = out[out["Close"] > 0]
                if not out.empty and out["Close"].dropna().median() < 500:
                    for c in ["Open","High","Low","Close"]: out[c] *= 1000
                if not out.empty:
                    _log.info(f"CafeF-HTML ✅ {symbol}: {len(out)} rows, close={out['Close'].iloc[-1]:,.0f}")
                    return out
    except Exception as e:
        _log.debug(f"CafeF HTML parse error {symbol}: {e}")
    return pd.DataFrame()


def _fetch_cafef(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P3: CafeF historical price — multiple endpoint strategies.
    Endpoints tried in order:
      A) s.cafef.vn/ajax/PageNew.aspx/HisDanhMuc (AJAX JSON — most reliable)
      B) s.cafef.vn/HisDanhMuc/{sym}.chn (JSON page)
      C) historial.cafef.vn/api/histdata/GetListHist (REST API)
      D) s.cafef.vn/LichSuGia/LichSuGia.aspx (HTML scrape, legacy)
    Covers ALL exchanges (HOSE/HNX/UPCOM) including OIL, IDC, ACV, PVS, VNA.
    """
    import traceback
    hdrs_ajax = {
        "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
        "Accept":       "application/json, text/javascript, */*",
        "Content-Type": "application/json; charset=UTF-8",
        "Referer":      f"https://cafef.vn/du-lieu-lich-su-giao-dich-{symbol.lower()}.chn",
        "Origin":       "https://cafef.vn",
        "X-Requested-With": "XMLHttpRequest",
    }
    hdrs_html = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":     "text/html,application/xhtml+xml,*/*",
        "Referer":    "https://cafef.vn/",
    }
    end_date   = datetime.now().strftime("%Y/%m/%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    page_size  = min(days, 500)

    # ─── Strategy A: historial.cafef.vn REST API ───────────────────
    try:
        url_a = (f"https://historial.cafef.vn/api/histdata/GetListHist"
                 f"?symbol={symbol}&startDate={start_date}&endDate={end_date}&pageIndex=1&pageSize={page_size}")
        r = requests.get(url_a, headers=hdrs_ajax, timeout=10)
        if r.ok:
            data = r.json()
            items = data.get("Data", data.get("data", data.get("items", [])))
            if items:
                rows = []
                for it in items:
                    try:
                        rows.append({
                            "Date":   pd.to_datetime(it.get("TradingDate", it.get("tradingDate", it.get("date",""))), errors="coerce"),
                            "Open":   float(it.get("OpenPrice",  it.get("openPrice",  it.get("open",  0))) or 0),
                            "High":   float(it.get("MaxPrice",   it.get("maxPrice",   it.get("high",  0))) or 0),
                            "Low":    float(it.get("MinPrice",   it.get("minPrice",   it.get("low",   0))) or 0),
                            "Close":  float(it.get("ClosePrice", it.get("closePrice", it.get("close", 0))) or 0),
                            "Volume": float(it.get("Volume",     it.get("volume",     it.get("vol",   0))) or 0),
                        })
                    except Exception: continue
                if rows:
                    df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
                    df = df[df["Close"] > 0].set_index("Date").sort_index()
                    df = df[~df.index.duplicated(keep="last")]
                    if not df.empty and df["Close"].dropna().median() < 500:
                        for c in ["Open","High","Low","Close"]: df[c] *= 1000
                    if len(df) >= 5:
                        _log.info(f"CafeF-historial ✅ {symbol}: {len(df)} rows")
                        return df
    except Exception as e:
        _log.debug(f"CafeF Strategy A failed {symbol}: {e}")

    # ─── Strategy B: s.cafef.vn/ajax PageNew (AJAX JSON) ──────────
    try:
        url_b = f"https://s.cafef.vn/ajax/PageNew.aspx/HisDanhMuc"
        payload = json.dumps({"sort":"","pageSize":page_size,"pageIndex":1,"maChungKhoan":symbol})
        r = requests.post(url_b, data=payload, headers=hdrs_ajax, timeout=10)
        if r.ok:
            data = r.json()
            # Response: {"d": {"Data": [...]}} or {"Data": [...]}
            items = (data.get("d", {}).get("Data") or
                     data.get("d", {}).get("data") or
                     data.get("Data") or data.get("data") or [])
            if items:
                rows = []
                for it in items:
                    try:
                        rows.append({
                            "Date":   pd.to_datetime(it.get("Ngay", it.get("date","")), dayfirst=True, errors="coerce"),
                            "Open":   float(it.get("GiaMoCua",  it.get("open",  0)) or 0),
                            "High":   float(it.get("GiaCaoNhat",it.get("high",  0)) or 0),
                            "Low":    float(it.get("GiaThapNhat",it.get("low",  0)) or 0),
                            "Close":  float(it.get("GiaDongCua",it.get("close", 0)) or 0),
                            "Volume": float(it.get("KLKhopLenh",it.get("volume",0)) or 0),
                        })
                    except Exception: continue
                if rows:
                    df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
                    df = df[df["Close"] > 0].set_index("Date").sort_index()
                    df = df[~df.index.duplicated(keep="last")]
                    if not df.empty and df["Close"].dropna().median() < 500:
                        for c in ["Open","High","Low","Close"]: df[c] *= 1000
                    if len(df) >= 5:
                        _log.info(f"CafeF-AJAX ✅ {symbol}: {len(df)} rows")
                        return df
    except Exception as e:
        _log.debug(f"CafeF Strategy B failed {symbol}: {e}")

    # ─── Strategy C: HisDanhMuc JSON page ─────────────────────────
    try:
        url_c = f"https://s.cafef.vn/HisDanhMuc/{symbol}.chn"
        r = requests.get(url_c, headers=hdrs_html, timeout=10)
        if r.ok and r.text.strip().startswith("{"):
            data = r.json()
            items = data.get("data", data.get("Data", []))
            if items:
                rows = []
                for it in items:
                    try:
                        rows.append({
                            "Date":   pd.to_datetime(it.get("Ngay", it.get("date","")), errors="coerce"),
                            "Open":   float(it.get("GiaMoCua",  it.get("open",  0)) or 0),
                            "High":   float(it.get("GiaCaoNhat",it.get("high",  0)) or 0),
                            "Low":    float(it.get("GiaThapNhat",it.get("low",  0)) or 0),
                            "Close":  float(it.get("GiaDongCua",it.get("close", 0)) or 0),
                            "Volume": float(it.get("KhopLenh",  it.get("volume",0)) or 0),
                        })
                    except Exception: continue
                if rows:
                    df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
                    df = df[df["Close"] > 0].set_index("Date").sort_index()
                    df = df[~df.index.duplicated(keep="last")]
                    if not df.empty and df["Close"].dropna().median() < 500:
                        for c in ["Open","High","Low","Close"]: df[c] *= 1000
                    if len(df) >= 5:
                        _log.info(f"CafeF-HisDM ✅ {symbol}: {len(df)} rows")
                        return df
    except Exception as e:
        _log.debug(f"CafeF Strategy C failed {symbol}: {e}")

    # ─── Strategy D: LichSuGia.aspx HTML scrape (legacy fallback) ─
    try:
        url_d = f"https://s.cafef.vn/LichSuGia/LichSuGia.aspx?symbol={symbol}&PageIndex=1&PageSize={page_size}"
        r = requests.get(url_d, headers=hdrs_html, timeout=12)
        if r.ok and "Không có dữ liệu" not in r.text:
            df = _parse_cafef_table(r.text, symbol)
            if len(df) >= 5:
                return df
    except Exception as e:
        _log.debug(f"CafeF Strategy D failed {symbol}: {e}")

    _log.warning(f"CafeF ❌ {symbol}: all strategies failed")
    return pd.DataFrame()


def _fetch_cafef_v2(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    CafeF JSON API v2 — api.cafef.vn (may be blocked on some networks).
    Short timeout to fail fast if connection refused.
    """
    import traceback
    try:
        url = f"https://api.cafef.vn/api/historyprice/{symbol}?type=5&count={min(days, 500)}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        r.raise_for_status()
        data = r.json()
        items = data.get("Data", data.get("data", []))
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            try:
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
            except Exception: continue
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
        df = df[df["Close"] > 0].set_index("Date").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        if not df.empty and df["Close"].dropna().median() < 500:
            for c in ["Open","High","Low","Close"]: df[c] *= 1000
        if len(df) >= 5:
            _log.info(f"CafeF-JSON ✅ {symbol}: {len(df)} rows")
        return df
    except requests.exceptions.ConnectionError as e:
        _log.warning(f"CafeF-v2 connection refused {symbol}: {e}")
    except requests.exceptions.Timeout:
        _log.warning(f"CafeF-v2 timeout {symbol}")
    except Exception as e:
        _log.debug(f"CafeF-v2 error {symbol}: {e}")
    return pd.DataFrame()


def _fetch_tcbs(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P4: TCBS Public API — apipubaws.tcbs.com.vn (no auth, excellent coverage)
    ✓ HOSE/HNX/UPCOM  ✓ Adjusted prices  ✓ High reliability
    URL: /stock-insight/v1/stock/ohlc?ticker=X&type=stock&resolution=D&from=X&to=Y
    """
    import traceback
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = (f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/ohlc"
           f"?ticker={symbol}&type=stock&resolution=D&from={from_ts}&to={to_ts}")
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":     "application/json",
        "Referer":    "https://tcinvest.tcbs.com.vn/",
        "Origin":     "https://tcinvest.tcbs.com.vn",
        "DNT":        "1",
    }
    try:
        r = requests.get(url, headers=hdrs, timeout=API_TIMEOUT)
        r.raise_for_status()
        raw = r.json()
        # Response: {"data": [{"tradingDate":..., "open":..., "high":..., "low":..., "close":..., "volume":...},...]}
        items = raw.get("data", raw.get("Data", []))
        if not items:
            _log.debug(f"TCBS {symbol}: empty response")
            return pd.DataFrame()
        rows = []
        for it in items:
            try:
                # tradingDate may be Unix ms, Unix s, or ISO string
                td = it.get("tradingDate", it.get("TradingDate", it.get("date", None)))
                if td is None: continue
                if isinstance(td, (int, float)):
                    # Check if milliseconds
                    ts = td/1000 if td > 1e10 else td
                    dt = pd.Timestamp(ts, unit="s")
                else:
                    dt = pd.Timestamp(str(td))
                rows.append({
                    "Date":   dt,
                    "Open":   float(it.get("open",  it.get("Open",  0)) or 0),
                    "High":   float(it.get("high",  it.get("High",  0)) or 0),
                    "Low":    float(it.get("low",   it.get("Low",   0)) or 0),
                    "Close":  float(it.get("close", it.get("Close", 0)) or 0),
                    "Volume": float(it.get("volume",it.get("Volume",0)) or 0),
                })
            except Exception as e:
                _log.debug(f"TCBS {symbol} row error: {e}"); continue
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
        df = df[df["Close"] > 0].set_index("Date").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        if not df.empty and df["Close"].dropna().median() < 500:
            for c in ["Open","High","Low","Close"]: df[c] *= 1000
        if len(df) >= 5:
            _log.info(f"TCBS ✅ {symbol}: {len(df)} rows, close={df['Close'].iloc[-1]:,.0f}")
        return df
    except requests.exceptions.HTTPError as e:
        _log.warning(f"TCBS HTTP error {symbol}: {e}")
    except requests.exceptions.ConnectionError as e:
        _log.warning(f"TCBS connection error {symbol}: {e}")
    except requests.exceptions.Timeout:
        _log.warning(f"TCBS timeout {symbol}")
    except Exception as e:
        _log.error(f"TCBS unexpected error {symbol}: {e}"); _log.debug(traceback.format_exc())
    return pd.DataFrame()


def _fetch_vndirect_price(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    P5b: VNDirect FINFO price history — finfo-api.vndirect.com.vn
    Uses the same VNDirect API already in use for fundamentals.
    ✓ Reliable  ✓ HOSE/HNX/UPCOM  ✓ Adjusted close available
    """
    import traceback
    try:
        end_date   = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        url = f"{VND_BASE}/priceHistory"
        params = {
            "code":      symbol,
            "startDate": start_date,
            "endDate":   end_date,
            "type":      "stock",
        }
        r = requests.get(url, params=params, headers=VND_HEADERS, timeout=API_TIMEOUT)
        r.raise_for_status()
        raw = r.json()
        items = raw.get("data", [])
        if not items:
            _log.debug(f"VNDirect price {symbol}: empty response")
            return pd.DataFrame()
        rows = []
        for it in items:
            try:
                rows.append({
                    "Date":   pd.to_datetime(it.get("tradingDate", it.get("date","")), errors="coerce"),
                    "Open":   float(it.get("openPrice",    it.get("open",  0)) or 0),
                    "High":   float(it.get("highPrice",    it.get("high",  0)) or 0),
                    "Low":    float(it.get("lowPrice",     it.get("low",   0)) or 0),
                    "Close":  float(it.get("closePrice",   it.get("close", 0)) or 0),
                    "Volume": float(it.get("nmVolume",     it.get("volume",0)) or 0),
                })
            except Exception: continue
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["Close","Date"])
        df = df[df["Close"] > 0].set_index("Date").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        if not df.empty and df["Close"].dropna().median() < 500:
            for c in ["Open","High","Low","Close"]: df[c] *= 1000
        if len(df) >= 5:
            _log.info(f"VNDirect-price ✅ {symbol}: {len(df)} rows")
        return df
    except Exception as e:
        _log.debug(f"VNDirect price error {symbol}: {e}")
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
    Data pipeline v17.0: 7-source cascade
    1. DNSE Entrade     (api.dnse.com.vn/chart-api/v2  — FIX-16 confirmed working)
    2. SSI iboard-api   (iboard-api.ssi.com.vn/statistics/charts/history)
    3. CafeF multi      (historial + AJAX + HisDanhMuc + LichSuGia HTML)
    4. TCBS             (apipubaws.tcbs.com.vn/stock-insight — no auth)
    5. CafeF JSON       (api.cafef.vn — may be blocked)
    6. VNDirect price   (finfo-api.vndirect.com.vn/v4/priceHistory)
    7. yFinance         ({symbol}.VN — global fallback)
    Returns: (DataFrame, source_name, error_message)
    """
    import traceback
    symbol = symbol.strip().upper()
    error_detail = {}

    # FIX-20: per-source min rows; FIX-21: skip VNDirect for UPCOM
    _SRC_MIN = {
        "DNSE": min_rows, "SSI": min(min_rows, 20), "CafeF": min_rows,
        "TCBS": min_rows, "CafeF-JSON": min_rows, "VNDirect": min_rows,
        "yFinance": min(min_rows, 20),
    }
    exch = TICKER_EXCHANGE.get(symbol, "HOSE")
    _PIPELINE = [
        ("DNSE",       _fetch_dnse),
        ("SSI",      _fetch_ssi),
        ("CafeF",    _fetch_cafef),
        ("TCBS",     _fetch_tcbs),
        ("CafeF-JSON", _fetch_cafef_v2),
        ("VNDirect", _fetch_vndirect_price),
        ("yFinance", _fetch_yfinance),
    ]

    for src_name, fetch_fn in _PIPELINE:
        if src_name == "VNDirect" and exch == "UPCOM":
            error_detail[src_name] = "skipped(UPCOM)"; continue
        try:
            df = fetch_fn(symbol, days)
            src_min = _SRC_MIN.get(src_name, min_rows)
            if len(df) >= src_min:
                _log.info(f"✅ {src_name} {symbol}: {len(df)} rows")
                return df, src_name, None
            error_detail[src_name] = f"{len(df)} rows"
        except Exception as e:
            error_detail[src_name] = str(e)[:80]
            _log.error(f"{src_name} exception {symbol}: {e}"); _log.debug(traceback.format_exc())

    detail_str = " | ".join([f"{k}:{v}" for k,v in error_detail.items()])
    msg = (f"Cannot load {symbol}. Exchange:{exch}. Sources tried: {detail_str}")
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
                         headers=VND_HEADERS, timeout=6)  # FIX-21: reduced
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
    """FIX-23/24: Arrow-safe dataframe renderer with width=stretch."""
    import pandas as pd
    if isinstance(df_or_styled, pd.DataFrame):
        df = df_or_styled.copy()
        # FIX-23: coerce all object columns that contain mixed float/str to string
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(lambda x: "" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x)))
        df_or_styled = df
    try:
        st.dataframe(df_or_styled, width='stretch', key=key)
    except TypeError:
        st.dataframe(df_or_styled, width="stretch", key=key)

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
        "⏱️ Chân trời" if lang=="VI" else "⏱️ Horizon": "Ngắn hạn T+2" if lang=="VI" else "Short-term T+2",
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
#  CAFEF FUNDAMENTAL DATA  (ENH-11 — confirmed working 2026-03)
# ══════════════════════════════════════════════════════════════
_CAFEF_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://cafef.vn/",
    "Accept":     "application/json, text/plain, */*",
}

@st.cache_data(ttl=3600)
def fetch_cafef_key_ratios(ticker: str) -> dict:
    """
    CafeF ChiSoTaiChinh API — returns EPS, P/E, BVPS, P/B, mkt cap, shares.
    Confirmed working: https://cafef.vn/du-lieu/Ajax/PageNew/ChiSoTaiChinh.ashx?Symbol=fpt
    """
    sym = ticker.lower()
    url = f"https://cafef.vn/du-lieu/Ajax/PageNew/ChiSoTaiChinh.ashx?Symbol={sym}"
    try:
        r = _HTTP.get(url, headers=_CAFEF_HDR, timeout=8)
        r.raise_for_status()
        data = r.json()
        if not data.get("Success") or not data.get("Data"):
            return {}
        out = {}
        for item in data["Data"]:
            code = item.get("Code", "")
            val  = item.get("Value", "")
            if not val or val == "–":
                continue
            clean = str(val).replace(",", "").replace("%", "").strip()
            try:
                num = float(clean)
            except ValueError:
                num = None
            if code == "EPScoBan":
                out["eps"]         = num * 1000 if num and num < 100 else num
                out["eps_raw"]     = val
            elif code == "P/E":
                out["pe"]          = num
            elif code == "GiaTriSoSach":
                out["bvps"]        = num * 1000 if num and num < 100 else num
                out["bvps_raw"]    = val
            elif code == "Beta":       # CafeF uses "Beta" code for P/B
                out["pb"]          = num
            elif code == "VonHoaThiTruong":
                out["mcap_bn"]     = num   # in tỷ VNĐ
            elif code == "KlcpNY":
                out["shares_listed"]  = clean
            elif code == "KhopLenh10Phien":
                out["vol10_avg"]   = clean
            elif code == "ThoiGian":
                out["ratio_period"]= val
        return out
    except Exception as e:
        _log.warning(f"CafeF ChiSoTaiChinh {ticker}: {e}")
        return {}

@st.cache_data(ttl=900)   # 15 min for price
def fetch_cafef_price(ticker: str) -> dict:
    """
    CafeF PriceRealTimeHeader — real-time last price, reference, volume.
    Confirmed working: https://cafef.vn/du-lieu/Ajax/PageNew/PriceRealTimeHeader.ashx?Symbol=fpt
    """
    sym = ticker.lower()
    url = f"https://cafef.vn/du-lieu/Ajax/PageNew/PriceRealTimeHeader.ashx?Symbol={sym}"
    try:
        r = _HTTP.get(url, headers=_CAFEF_HDR, timeout=6)
        r.raise_for_status()
        d = r.json()
        if d.get("Success") and d.get("Data"):
            data = d["Data"]
            price_raw  = data.get("Gia", 0)
            ref_raw    = data.get("GiaThamChieu", 0)
            price = float(price_raw) * 1000 if price_raw and float(price_raw) < 1000 else float(price_raw or 0)
            ref   = float(ref_raw)   * 1000 if ref_raw   and float(ref_raw)   < 1000 else float(ref_raw   or 0)
            return {
                "price":     price,
                "reference": ref,
                "pct_change":((price - ref) / ref * 100) if ref > 0 else 0,
                "volume":    int(data.get("KhoiLuong", 0)),
                "exchange":  data.get("MaSan", 1),
            }
    except Exception as e:
        _log.warning(f"CafeF PriceRT {ticker}: {e}")
    return {}

@st.cache_data(ttl=3600)
def fetch_cafef_shareholders(ticker: str) -> dict:
    """
    CafeF CoCauSoHuu — shareholder structure (foreign %, state %, major holders).
    Confirmed working: https://cafef.vn/du-lieu/Ajax/PageNew/CoCauSoHuu.ashx?Symbol=fpt
    """
    sym = ticker.lower()
    url = f"https://cafef.vn/du-lieu/Ajax/PageNew/CoCauSoHuu.ashx?Symbol={sym}"
    try:
        r = _HTTP.get(url, headers=_CAFEF_HDR, timeout=8)
        r.raise_for_status()
        d = r.json()
        if not d.get("Success") or not d.get("Data"):
            return {}
        data = d["Data"]
        holders = []
        for h in data.get("CoDongSoHuu", [])[:10]:
            rate = h.get("AssetRate", "0").replace(",", ".")
            vol  = h.get("AssetVolume", "0").replace(".", "").replace(",", "")
            try:
                rate_f = float(rate)
            except Exception:
                rate_f = 0
            if rate_f >= 0.5:   # only show ≥0.5%
                holders.append({
                    "name":  re.sub(r"<[^>]+>", "", h.get("Name", "")),
                    "pct":   rate_f,
                    "vol":   vol,
                })
        return {
            "foreign_pct": float(data.get("NuocNgoai", 0)),
            "state_pct":   float(data.get("NhaNuoc", 0)),
            "other_pct":   float(data.get("Khac", 0)),
            "major_holders": holders,
        }
    except Exception as e:
        _log.warning(f"CafeF CoCauSoHuu {ticker}: {e}")
    return {}

@st.cache_data(ttl=86400)
def fetch_cafef_financial_reports(ticker: str) -> list:
    """
    CafeF FileBCTC Type=1 — list of quarterly/annual financial report PDFs.
    """
    sym = ticker.lower()
    url = f"https://cafef.vn/du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol={sym}&Type=1&Year=0"
    try:
        r = _HTTP.get(url, headers=_CAFEF_HDR, timeout=8)
        r.raise_for_status()
        data = r.json()
        reports = []
        for item in (data.get("Data") or [])[:12]:
            reports.append({
                "period": item.get("Time", ""),
                "name":   item.get("Name", ""),
                "link":   item.get("Link", ""),
            })
        return reports
    except Exception as e:
        _log.warning(f"CafeF FileBCTC {ticker}: {e}")
    return []

@st.cache_data(ttl=3600)
def fetch_cafef_liveboard(ticker: str, days: int = 365) -> pd.DataFrame:
    """
    CafeF Liveboard JSON — recent price history (fast CDN, no auth).
    Confirmed working: https://cafefnew.mediacdn.vn/Images/Uploaded/DuLieuDownload/Liveboard/{SYM}_PriceHistory.json
    """
    sym = ticker.upper()
    url = f"https://cafefnew.mediacdn.vn/Images/Uploaded/DuLieuDownload/Liveboard/{sym}_PriceHistory.json"
    try:
        r = _HTTP.get(url, headers=_CAFEF_HDR, timeout=8)
        r.raise_for_status()
        items = r.json()
        if not isinstance(items, list) or not items:
            return pd.DataFrame()
        rows = []
        cutoff = datetime.now() - timedelta(days=days)
        for it in items:
            try:
                dt = pd.Timestamp(it["TradeDate"])
                if dt < pd.Timestamp(cutoff):
                    continue
                cp = float(it.get("ClosePrice", 0) or 0)
                if cp <= 0:
                    continue
                # Prices in CafeF Liveboard are in thousands VND
                mult = 1000 if cp < 1000 else 1
                rows.append({
                    "Date":   dt,
                    "Open":   float(it.get("OpenPrice", cp) or cp) * mult,
                    "High":   float(it.get("HighPrice", cp) or cp) * mult,
                    "Low":    float(it.get("LowPrice",  cp) or cp) * mult,
                    "Close":  cp * mult,
                    "Volume": float(it.get("Volume", 0) or 0),
                })
            except Exception:
                continue
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
        return df
    except Exception as e:
        _log.warning(f"CafeF Liveboard {ticker}: {e}")
    return pd.DataFrame()

# ══════════════════════════════════════════════════════════════
#  SSI SSMI COMPANY DATA  (ENH-12 — with iboard headers)
# ══════════════════════════════════════════════════════════════
_SSI_SSMI_BASE = "https://iboard-api.ssi.com.vn/statistics/company/ssmi"
_SSI_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://iboard.ssi.com.vn/",
    "Origin":     "https://iboard.ssi.com.vn",
    "Accept":     "application/json",
}

def _ssi_ssmi_get(endpoint: str, params: dict = None) -> dict:
    """GET from SSI SSMI company API."""
    try:
        r = _HTTP.get(f"{_SSI_SSMI_BASE}/{endpoint}",
                      headers=_SSI_HDR, params=params, timeout=10)
        if r.status_code == 403:
            _log.debug(f"SSI SSMI {endpoint}: 403 (needs auth)")
            return {}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log.warning(f"SSI SSMI {endpoint}: {e}")
        return {}

@st.cache_data(ttl=3600)
def fetch_ssi_finance_indicator(ticker: str) -> pd.DataFrame:
    """
    SSI SSMI finance-indicator: ROE, ROA, EPS, P/E, P/B per quarter.
    Endpoint: /statistics/company/ssmi/finance-indicator?symbol=ACB&page=1&pageSize=10
    """
    raw = _ssi_ssmi_get("finance-indicator",
                         {"symbol": ticker, "page": 1, "pageSize": 20})
    items = raw.get("data", raw.get("Data", []))
    if not items or not isinstance(items, list):
        return pd.DataFrame()
    return pd.DataFrame(items)

@st.cache_data(ttl=86400)
def fetch_ssi_company_info(ticker: str) -> dict:
    """
    SSI SSMI — aggregated company info from multiple endpoints.
    Returns: overview, leadership, shareholders, cap_dividend
    """
    out = {}
    # Cap & dividend
    cap_div = _ssi_ssmi_get("cap-and-dividend", {"symbol": ticker})
    if cap_div:
        out["cap_dividend"] = cap_div.get("data", cap_div)

    # Company leaderships
    lead = _ssi_ssmi_get("company-leaderships",
                          {"symbol": ticker, "language": "vn", "page": 1, "pageSize": 20})
    if lead:
        out["leadership"] = lead.get("data", lead.get("Data", []))

    # Share holder summary
    sh_sum = _ssi_ssmi_get("share-holder-summary",
                            {"symbol": ticker, "language": "vn"})
    if sh_sum:
        out["shareholder_summary"] = sh_sum.get("data", sh_sum)

    # Corporate actions (last 12 months)
    from datetime import timedelta as _td
    today = datetime.now()
    yr_ago = today - _td(days=365)
    fmt = lambda d: d.strftime("%d/%m/%Y")
    corp = _ssi_ssmi_get("corporate-actions", {
        "symbol": ticker, "language": "vn",
        "page": 1, "pageSize": 20,
        "fromDate": fmt(yr_ago), "toDate": fmt(today),
    })
    if corp:
        out["corporate_actions"] = corp.get("data", corp.get("Data", []))

    return out

@st.cache_data(ttl=3600)
def fetch_ssi_news(ticker: str, n: int = 10) -> list:
    """SSI SSMI company news."""
    today = datetime.now()
    month_ago = today - timedelta(days=30)
    fmt = lambda d: d.strftime("%d/%m/%Y")
    raw = _ssi_ssmi_get("company-news", {
        "symbol": ticker, "pageSize": n, "page": 1,
        "fromDate": fmt(month_ago), "toDate": fmt(today),
        "language": "vn",
    })
    items = raw.get("data", raw.get("Data", []))
    if not items:
        return []
    news = []
    for it in (items if isinstance(items, list) else []):
        news.append({
            "date":    str(it.get("publishDate", it.get("PublishDate", "")))[:10],
            "title":   it.get("title", it.get("Title", "–")),
            "url":     it.get("url", it.get("Url", "")),
            "source":  it.get("source", "SSI"),
        })
    return news

# ══════════════════════════════════════════════════════════════
#  DNSE OHLC TECHNICAL ANALYSIS  (ENH-13)
#  Used as fundamental proxy when TCBS/VNDirect unavailable
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800)
def fetch_dnse_ohlc_analysis(ticker: str) -> dict:
    """
    Fetch 2 years of OHLC from corrected DNSE endpoint (api.dnse.com.vn)
    and compute technical indicators to serve as valuation proxy
    when fundamental financial data is unavailable.
    Returns a structured dict with technicals, price levels, risk scores.
    """
    df, src, err = download_data(ticker, days=730, min_rows=40)
    if df is None or df.empty or "Close" in df.columns is False:
        return {"error": "No OHLC data available"}

    # Ensure indicators are computed
    try:
        df = calculate_indicators(df)
    except Exception as e:
        _log.warning(f"DNSE OHLC analysis calc error {ticker}: {e}")

    closes = df["Close"].dropna().values.astype(float)
    highs  = df["High"].dropna().values.astype(float)  if "High"   in df.columns else closes
    lows   = df["Low"].dropna().values.astype(float)   if "Low"    in df.columns else closes
    vols   = df["Volume"].fillna(0).values.astype(float) if "Volume" in df.columns else np.zeros(len(closes))

    price = float(closes[-1])
    high52 = float(highs[-252:].max()) if len(highs) >= 252 else float(highs.max())
    low52  = float(lows[-252:].min())  if len(lows)  >= 252 else float(lows.min())
    avg_vol20 = float(vols[-20:].mean()) if len(vols) >= 20 else float(vols.mean())
    avg_vol5  = float(vols[-5:].mean())  if len(vols) >= 5  else float(vols.mean())

    # Key indicator values from last row
    last = df.iloc[-1]
    rsi  = float(last.get("RSI",  50))  if "RSI"  in df.columns else 50.0
    macd = float(last.get("MACD", 0))   if "MACD" in df.columns else 0.0
    macd_sig = float(last.get("MACD_Signal", 0)) if "MACD_Signal" in df.columns else 0.0
    adx  = float(last.get("ADX",  20))  if "ADX"  in df.columns else 20.0
    bbl  = float(last.get("BB_Lower", price * 0.95)) if "BB_Lower" in df.columns else price * 0.95
    bbu  = float(last.get("BB_Upper", price * 1.05)) if "BB_Upper" in df.columns else price * 1.05
    sma20= float(last.get("SMA20", price)) if "SMA20" in df.columns else price
    sma50= float(last.get("SMA50", price)) if "SMA50" in df.columns else price

    # Trend signals
    above_sma20  = price > sma20
    above_sma50  = price > sma50
    macd_bullish = macd > macd_sig
    rsi_oversold = rsi < 35
    rsi_overbought = rsi > 70
    vol_spike    = avg_vol5 > avg_vol20 * 1.5 if avg_vol20 > 0 else False

    # 52-week position (0=at low, 1=at high)
    rng = high52 - low52
    price_percentile = (price - low52) / rng if rng > 0 else 0.5

    # Momentum: 1M, 3M returns
    ret1m = (closes[-1] / closes[-21] - 1)  if len(closes) >= 21  else 0
    ret3m = (closes[-1] / closes[-63] - 1)  if len(closes) >= 63  else 0
    ret6m = (closes[-1] / closes[-126] - 1) if len(closes) >= 126 else 0

    # Volatility (annualized)
    if len(closes) >= 20:
        log_ret = np.diff(np.log(closes[-60:]))
        volatility = float(np.std(log_ret) * np.sqrt(252))
    else:
        volatility = 0.30

    # Technical score 0–100
    tech_score = 0.0
    if above_sma20:    tech_score += 15
    if above_sma50:    tech_score += 20
    if macd_bullish:   tech_score += 15
    if rsi_oversold:   tech_score += 15
    elif not rsi_overbought: tech_score += 8
    if adx > 25:       tech_score += 10  # clear trend
    if vol_spike and macd_bullish: tech_score += 10
    if ret1m > 0:      tech_score += 7
    if ret3m > 0:      tech_score += 5
    if price_percentile < 0.35: tech_score += 5  # near 52-week low = potential value

    # Technical risk scores (for risk radar)
    momentum_risk = max(1.0, min(10.0, 5 - (tech_score - 50) / 10))
    vol_risk = max(1.0, min(10.0, volatility * 15))  # 20% vol → risk 3
    trend_risk = 1.0 if (above_sma20 and above_sma50) else (5.0 if (above_sma20 or above_sma50) else 8.0)

    # Implied EPS from sector P/E (when fundamentals unavailable)
    sector = get_sector(ticker)
    sector_pe_map = {
        "Ngân hàng": 12.0, "Bất động sản": 18.0, "Dầu khí": 10.0,
        "Thép": 8.0, "Công nghệ": 25.0, "Chứng khoán": 14.0,
        "Bán lẻ": 18.0, "Thực phẩm": 20.0, "Dược": 22.0,
        "Bảo hiểm": 16.0, "Điện": 15.0, "Xây dựng": 12.0,
        "Hàng không": 20.0, "Logistics": 16.0,
    }
    sector_pe  = sector_pe_map.get(sector, 15.0)
    implied_eps= price / sector_pe   # rough EPS from current price / sector PE
    implied_bvps = price * 0.6       # rough BVPS estimate (conservative)

    # Technical-implied fair value (sector PE applied to implied EPS, adjusted for momentum)
    momentum_adj = 1.0 + (ret3m * 0.3)  # if momentum positive, PE expands slightly
    adj_pe = sector_pe * max(0.7, min(1.3, momentum_adj))
    tech_fair_value = implied_eps * adj_pe

    # ENH-27: VWAP 20-day approximation
    df["_typical"] = (df["High"] + df["Low"] + df["Close"]) / 3
    if "Volume" in df.columns and df["Volume"].tail(20).sum() > 0:
        _vwap20 = float((df["_typical"].tail(20) * df["Volume"].tail(20)).sum() / df["Volume"].tail(20).sum())
        _vwap_sig = "BUY" if price > _vwap20 * 1.005 else ("SELL" if price < _vwap20 * 0.995 else "HOLD")
        _vwap_pct = (price - _vwap20) / _vwap20 * 100
    else:
        _vwap20, _vwap_sig, _vwap_pct = float(price), "HOLD", 0.0

    return {
        "price":           price,
        "vwap_20":         round(_vwap20, 0),
        "vwap_signal":     _vwap_sig,
        "vwap_pct":        round(_vwap_pct, 2),
        "high52":          high52,
        "low52":           low52,
        "price_percentile":price_percentile,
        "rsi":             rsi,
        "macd":            macd,
        "macd_sig":        macd_sig,
        "macd_bullish":    macd_bullish,
        "adx":             adx,
        "bb_lower":        bbl,
        "bb_upper":        bbu,
        "sma20":           sma20,
        "sma50":           sma50,
        "above_sma20":     above_sma20,
        "above_sma50":     above_sma50,
        "rsi_oversold":    rsi_oversold,
        "rsi_overbought":  rsi_overbought,
        "vol_spike":       vol_spike,
        "ret1m":           ret1m,
        "ret3m":           ret3m,
        "ret6m":           ret6m,
        "volatility":      volatility,
        "tech_score":      tech_score,
        "momentum_risk":   momentum_risk,
        "vol_risk":        vol_risk,
        "trend_risk":      trend_risk,
        "implied_eps":     implied_eps,
        "implied_bvps":    implied_bvps,
        "tech_fair_value": tech_fair_value,
        "sector_pe":       sector_pe,
        "sector":          sector,
        "source":          src,
        "n_rows":          len(df),
        "data_df":         df,   # full OHLC df for charting
    }

# ══════════════════════════════════════════════════════════════
#  TCBS FUNDAMENTAL DATA — tcanalysis API (no auth, public)
# ══════════════════════════════════════════════════════════════
TCBS_ANA = "https://apipubaws.tcbs.com.vn/tcanalysis/v1"
_TCBS_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://tcinvest.tcbs.com.vn/",
    "Origin":     "https://tcinvest.tcbs.com.vn",
    "Accept":     "application/json",
}

def _tcbs_get(path: str, params: dict = None) -> dict:
    """GET from TCBS tcanalysis with timeout+error handling."""
    try:
        r = requests.get(f"{TCBS_ANA}/{path}", params=params,
                         headers=_TCBS_HDR, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log.warning(f"TCBS tcanalysis {path}: {e}")
        return {}

@st.cache_data(ttl=3600)
def fetch_tcbs_overview(ticker: str) -> dict:
    """Company overview: name, exchange, industry, executives, shareholders."""
    raw = _tcbs_get(f"ticker/{ticker}/overview")
    if not raw:
        return {}
    out = {}
    for k, label_vi, label_en in [
        ("companyName",     "Tên công ty",      "Company"),
        ("exchange",        "Sàn",              "Exchange"),
        ("industry",        "Ngành",            "Industry"),
        ("establishedYear", "Năm thành lập",    "Est. Year"),
        ("numberOfEmployee","Nhân viên",        "Employees"),
        ("website",         "Website",          "Website"),
        ("companyProfile",  "_profile",         "_profile"),
    ]:
        v = raw.get(k)
        if v is not None:
            out[label_vi] = v
            out[f"_en_{label_vi}"] = label_en
    # Market cap & shares from ticker info
    ticker_info = _tcbs_get(f"ticker/{ticker}/price-to-earnings")
    if ticker_info:
        out["_pe_data"] = ticker_info
    return out

@st.cache_data(ttl=3600)
def fetch_tcbs_financials(ticker: str, report_type: str = "incomestatement",
                          yearly: int = 0) -> pd.DataFrame:
    """Fetch TCBS financial statement.
    report_type: incomestatement | balancesheet | cashflow
    yearly: 0=quarterly, 1=annual
    """
    raw = _tcbs_get(f"finance/{ticker}/{report_type}",
                    {"yearly": yearly, "isAll": 0})
    data = raw.get("listFinancialRatio", raw.get("listFinancialReport",
           raw.get("data", [])))
    if not data:
        # Try alternate key structures
        for key in raw:
            if isinstance(raw[key], list) and len(raw[key]) > 0:
                data = raw[key]
                break
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    # Standardize period column
    for pcol in ["quarter", "year", "period", "reportDate"]:
        if pcol in df.columns:
            df = df.rename(columns={pcol: "period"})
            break
    return df

@st.cache_data(ttl=3600)
def fetch_tcbs_ratio(ticker: str, yearly: int = 0) -> pd.DataFrame:
    """Fetch TCBS financial ratios (ROE, ROA, margins, PE, PB etc)."""
    raw = _tcbs_get(f"finance/{ticker}/financialratio",
                    {"yearly": yearly, "isAll": 0})
    data = raw.get("listFinancialRatio", raw.get("data", []))
    if not data:
        for key in raw:
            if isinstance(raw[key], list) and len(raw[key]) > 0:
                data = raw[key]
                break
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def fetch_tcbs_price_latest(ticker: str) -> dict:
    """Get latest price + basic valuation metrics from TCBS."""
    raw = _tcbs_get(f"ticker/{ticker}/info")
    if not raw:
        raw = _tcbs_get(f"ticker/{ticker}")
    return raw if isinstance(raw, dict) else {}

# ── Column name maps for TCBS financial statements ──
_INCOME_MAP = {
    "revenue":             "Doanh thu",
    "netRevenue":          "Doanh thu thuần",
    "grossProfit":         "Lợi nhuận gộp",
    "operationProfit":     "LN từ HĐKD",
    "ebit":                "EBIT",
    "preTaxProfit":        "LNTT",
    "postTaxProfit":       "LNST",
    "netProfit":           "LNST",
    "eps":                 "EPS (đ)",
}
_INCOME_MAP_EN = {k: v.replace("Doanh thu","Revenue").replace("Lợi nhuận gộp","Gross Profit")
                   .replace("LN từ HĐKD","Operating Profit").replace("LNTT","Pre-tax Profit")
                   .replace("LNST","Net Profit").replace("EPS (đ)","EPS (đ)")
                   for k, v in _INCOME_MAP.items()}

_BALANCE_MAP = {
    "asset":               "Tổng tài sản",
    "shortAsset":          "Tài sản ngắn hạn",
    "longAsset":           "Tài sản dài hạn",
    "cash":                "Tiền & tương đương",
    "liability":           "Nợ phải trả",
    "shortLiability":      "Nợ ngắn hạn",
    "longLiability":       "Nợ dài hạn",
    "equity":              "Vốn chủ sở hữu",
    "payableOnEquity":     "D/E",
    "debt":                "Tổng nợ vay",
}
_BALANCE_MAP_EN = {
    "asset": "Total Assets", "shortAsset": "Current Assets",
    "longAsset": "Non-current Assets", "cash": "Cash & Equiv",
    "liability": "Total Liabilities", "shortLiability": "Current Liabilities",
    "longLiability": "Long-term Liabilities", "equity": "Equity",
    "payableOnEquity": "D/E", "debt": "Total Debt",
}

_CF_MAP = {
    "operationCashFlow":   "CF Hoạt động",
    "investingCashFlow":   "CF Đầu tư",
    "financingCashFlow":   "CF Tài chính",
    "freeCashFlow":        "Dòng tiền tự do",
}
_CF_MAP_EN = {
    "operationCashFlow": "Operating CF", "investingCashFlow": "Investing CF",
    "financingCashFlow": "Financing CF", "freeCashFlow": "Free Cash Flow",
}

_RATIO_MAP = {
    "roe":                 "ROE (%)",
    "roa":                 "ROA (%)",
    "roic":                "ROIC (%)",
    "grossProfitMargin":   "Biên gộp (%)",
    "ebitdaOnRevenue":     "Biên EBITDA (%)",
    "netProfitMargin":     "Biên ròng (%)",
    "currentPayment":      "Curr. Ratio",
    "quickPayment":        "Quick Ratio",
    "payableOnEquity":     "D/E",
    "ebitOnInterest":      "ICR",
    "revenueOnWorkCapital":"Asset Turnover",
    "priceToEarning":      "P/E",
    "priceToBook":         "P/B",
    "priceToSales":        "P/S",
    "dividendYield":       "Div. Yield (%)",
    "eps":                 "EPS (đ)",
    "bookValuePerShare":   "BVPS (đ)",
}
_RATIO_MAP_EN = _RATIO_MAP.copy()  # already mostly English

def _build_stmt_df(df: pd.DataFrame, col_map: dict, lang: str = "VI",
                   scale: float = 1e9) -> pd.DataFrame:
    """Extract and label columns from a TCBS financial DataFrame."""
    if df.empty:
        return pd.DataFrame()
    col_map_use = col_map if lang == "VI" else (
        _INCOME_MAP_EN if col_map is _INCOME_MAP else
        _BALANCE_MAP_EN if col_map is _BALANCE_MAP else
        _CF_MAP_EN if col_map is _CF_MAP else col_map
    )
    available = {k: v for k, v in col_map_use.items() if k in df.columns}
    if not available:
        return pd.DataFrame()
    out = pd.DataFrame()
    if "period" in df.columns:
        out["Kỳ" if lang == "VI" else "Period"] = df["period"].astype(str).str[:7]
    for src_col, label in available.items():
        col = pd.to_numeric(df[src_col], errors="coerce")
        if abs(col.dropna()).max() > 1e9 if len(col.dropna()) > 0 else False:
            out[f"{label} (tỷ)" if "đ" not in label and "%" not in label
                and label not in ("D/E","Curr. Ratio","Quick Ratio","ICR","P/E","P/B","P/S","Asset Turnover")
                else label] = (col / scale).round(2)
        else:
            out[label] = col.round(3) if col.dropna().abs().max() < 100 else col.round(0)
    return out

# ══════════════════════════════════════════════════════════════
#  VALUATION MODELS
# ══════════════════════════════════════════════════════════════
# ENH-20/24: Sector-aware valuation — research-calibrated March 2026
# Sources: SSI Research, VCSC, VPBankS, Mirae Asset Vietnam

# Updated sector P/E from SSI/VCSC benchmarks (ENH-24)
SECTOR_PE_BENCH = {
    "Ngân hàng":    12.0,  # P/B+DDM preferred; DCF/PE invalid for banks
    "Bất động sản": 20.0,
    "Dầu khí":      10.0,
    "Thép":          9.0,  # cyclical — use normalized EPS
    "Công nghệ":    28.0,  # FPT premium for >20% EPS growth
    "Chứng khoán":  14.0,
    "Bán lẻ":       18.0,
    "Thực phẩm":    22.0,
    "Dược":         24.0,
    "Bảo hiểm":     16.0,
    "Điện":         15.0,
    "Xây dựng":     11.0,
    "Hàng không":   18.0,
    "Logistics":    16.0,
    "Đa ngành":     14.0,  # Conglomerates — SOTP holdco discount ~20%
}
_BANKING_SECTOR  = {"Ngân hàng", "Bảo hiểm"}
_CYCLICAL_SECTOR = {"Thép", "Dầu khí", "Hàng không", "Xây dựng"}
_IMPORT_HEAVY    = {"Thép", "Dầu khí", "Hàng không", "Bán lẻ", "Thực phẩm", "Dược"}

def get_valuation_method(sector: str, eps_ttm: float, current_pe: float = 0) -> dict:
    """
    ENH-20: Returns sector-appropriate valuation method.
    Banking/Insurance → P/B + DDM (no DCF/PE).
    Cyclicals → normalize EPS to avoid cycle-peak/trough trap.
    Negative EPS → disable DCF+PE, show warning.
    Conglomerates → SOTP note.
    """
    result = {
        "use_dcf": True, "use_pe": True, "use_pb": True,
        "use_graham": True, "use_ddm": False, "normalize_eps": False,
        "warning": None, "note": None,
        "method_label": "DCF · P/E · P/B · Graham",
    }
    if sector in _BANKING_SECTOR:
        result.update({
            "use_dcf": False, "use_pe": False, "use_ddm": True,
            "method_label": "P/B + DDM (Banking Standard)",
            "note": ("⚠️ DCF và P/E không phù hợp với ngân hàng/bảo hiểm. "
                     "Áp dụng P/B + DDM (Chiết khấu cổ tức)."),
        })
    elif sector in _CYCLICAL_SECTOR:
        result.update({
            "normalize_eps": True,
            "method_label": "P/E chuẩn hóa · P/B (Cyclical — 5Y Avg EPS)",
            "note": ("📊 Ngành chu kỳ: dùng EPS bình quân 5 năm thay EPS spot. "
                     "P/E thấp tại đỉnh chu kỳ = tín hiệu BÁN, không phải MUA."),
        })
    if eps_ttm <= 0 or current_pe > 80:
        result.update({
            "use_dcf": False, "use_pe": False, "use_graham": False,
            "method_label": "P/B (EPS âm — DCF/PE vô nghĩa)",
            "warning": ("❌ EPS âm hoặc P/E > 80× — DCF và P/E trả về kết quả vô nghĩa. "
                        "Định giá chỉ dựa trên P/B. "
                        "Xem xét khả năng phục hồi lợi nhuận trước khi đầu tư."),
        })
    return result

def compute_dcf_valuation(eps_ttm: float, eps_growth_rate: float,
                           discount_rate: float = 0.12,
                           terminal_growth: float = 0.05,
                           years: int = 5) -> float:
    """DCF: Ke=12% (Rf~5%+ERP~7% Vietnam 2026). Returns 0 for negative EPS."""
    if eps_ttm <= 0:
        return 0.0
    g = min(eps_growth_rate, 0.35)
    pv, eps = 0.0, eps_ttm
    for t in range(1, years + 1):
        eps = eps * (1 + g)
        pv += eps / (1 + discount_rate) ** t
    terminal_eps = eps * (1 + terminal_growth)
    if discount_rate <= terminal_growth:
        return 0.0
    tv = terminal_eps / (discount_rate - terminal_growth)
    return round(pv + tv / (1 + discount_rate) ** years, 0)

def compute_pe_valuation(eps_ttm: float, sector: str,
                          market_avg_pe: float = 15.0) -> float:
    """P/E valuation using research-calibrated sector multiples (ENH-24)."""
    pe = SECTOR_PE_BENCH.get(sector, market_avg_pe)
    return round(eps_ttm * pe, 0) if eps_ttm > 0 else 0.0

def compute_pb_valuation(bvps: float, roe: float) -> float:
    """P/B justified by ROE. CoE=12% (Vietnam 2026 calibration)."""
    if bvps <= 0 or roe <= 0:
        return 0.0
    coe = 0.12
    justified_pb = min(max(roe / coe, 0.5), 6.0)
    return round(bvps * justified_pb, 0)

def compute_ddm_valuation(dps: float, roe: float, payout_ratio: float = 0.40,
                            cost_of_equity: float = 0.12) -> float:
    """
    ENH-20: Dividend Discount Model for Banking/Insurance.
    DDM = DPS / (Ke - g), g = ROE × (1 - payout). Standard for VN banks (SSI Research).
    """
    if dps <= 0 or roe <= 0:
        return 0.0
    g = min(roe * (1 - payout_ratio), 0.08)
    if cost_of_equity <= g:
        return 0.0
    return round(dps / (cost_of_equity - g), 0)

def compute_graham_value(eps_ttm: float, bvps: float) -> float:
    """Benjamin Graham: sqrt(22.5 × EPS × BVPS)."""
    if eps_ttm <= 0 or bvps <= 0:
        return 0.0
    return round((22.5 * eps_ttm * bvps) ** 0.5, 0)

def aggregate_fair_value(dcf: float, pe: float, pb: float, graham: float,
                          weights=(0.35, 0.30, 0.20, 0.15)) -> float:
    """Weighted average of valuation models (only includes models with value > 0)."""
    vals = [dcf, pe, pb, graham]
    valid = [(v, w) for v, w in zip(vals, weights) if v > 0]
    if not valid:
        return 0.0
    total_w = sum(w for _, w in valid)
    return round(sum(v * w for v, w in valid) / total_w, 0)

# ══════════════════════════════════════════════════════════════
#  RISK SCORING ENGINE
# ══════════════════════════════════════════════════════════════
def score_fundamental_risk(ratio_df: pd.DataFrame,
                            income_df: pd.DataFrame,
                            balance_df: pd.DataFrame) -> dict:
    """
    Returns risk scores 0-10 (10 = highest risk) for 5 dimensions.
    Also returns a composite fundamental score 0-100 (100 = best).
    """
    scores = {
        "debt":       5.0,
        "liquidity":  5.0,
        "profitability": 5.0,
        "growth":     5.0,
        "valuation":  5.0,
    }

    if ratio_df.empty:
        return scores

    def _latest(df, col):
        for c in df.columns:
            if col.lower() in c.lower():
                vals = pd.to_numeric(df[c], errors="coerce").dropna()
                return float(vals.iloc[0]) if len(vals) > 0 else None
        return None

    # ── Debt risk (0=safe, 10=dangerous)
    de = _latest(ratio_df, "payableOnEquity") or _latest(ratio_df, "D/E")
    if de is not None:
        if de < 0.5:   scores["debt"] = 1.0
        elif de < 1.0: scores["debt"] = 3.0
        elif de < 2.0: scores["debt"] = 5.0
        elif de < 3.0: scores["debt"] = 7.0
        else:          scores["debt"] = 9.0

    icr = _latest(ratio_df, "ebitOnInterest") or _latest(ratio_df, "ICR")
    if icr is not None:
        if icr > 5:    scores["debt"] = max(1.0, scores["debt"] - 2)
        elif icr < 1:  scores["debt"] = min(10.0, scores["debt"] + 2)

    # ── Liquidity risk
    cr = _latest(ratio_df, "currentPayment") or _latest(ratio_df, "Curr")
    if cr is not None:
        if cr > 2.5:   scores["liquidity"] = 1.0
        elif cr > 1.5: scores["liquidity"] = 3.0
        elif cr > 1.0: scores["liquidity"] = 6.0
        else:          scores["liquidity"] = 9.0

    # ── Profitability risk
    roe = _latest(ratio_df, "roe") or _latest(ratio_df, "ROE")
    if roe is not None:
        roe_pct = roe * 100 if roe < 1 else roe
        if roe_pct > 20:   scores["profitability"] = 1.0
        elif roe_pct > 12: scores["profitability"] = 3.0
        elif roe_pct > 5:  scores["profitability"] = 5.0
        elif roe_pct > 0:  scores["profitability"] = 7.0
        else:              scores["profitability"] = 10.0

    npm = _latest(ratio_df, "netProfitMargin") or _latest(ratio_df, "Biên ròng")
    if npm is not None:
        npm_pct = npm * 100 if npm < 1 else npm
        adj = 0 if npm_pct > 10 else (2 if npm_pct < 3 else 1)
        scores["profitability"] = min(10.0, scores["profitability"] + adj)

    # ── Growth risk (based on revenue trend)
    if not income_df.empty:
        rev_col = next((c for c in income_df.columns
                        if any(k in c for k in ["revenue","Revenue","Doanh thu"])), None)
        if rev_col:
            revs = pd.to_numeric(income_df[rev_col], errors="coerce").dropna()
            if len(revs) >= 4:
                recent = revs.iloc[:4].mean()
                older  = revs.iloc[4:8].mean() if len(revs) >= 8 else revs.iloc[-4:].mean()
                growth = (recent - older) / abs(older) if older != 0 else 0
                if growth > 0.20:   scores["growth"] = 1.0
                elif growth > 0.10: scores["growth"] = 3.0
                elif growth > 0:    scores["growth"] = 5.0
                elif growth > -0.1: scores["growth"] = 7.0
                else:               scores["growth"] = 9.0

    # ── Valuation risk
    pe = _latest(ratio_df, "priceToEarning") or _latest(ratio_df, "P/E")
    if pe is not None and pe > 0:
        if pe < 8:     scores["valuation"] = 2.0
        elif pe < 15:  scores["valuation"] = 3.0
        elif pe < 25:  scores["valuation"] = 5.0
        elif pe < 40:  scores["valuation"] = 7.0
        else:          scores["valuation"] = 9.0

    return scores

def compute_composite_fundamental_score(risk_scores: dict,
                                         upside_pct: float,
                                         tech_score: float = None,
                                         dxy_level: float = None,
                                         sector: str = "") -> float:
    """
    Converts risk scores → fundamental quality score 0–100.
    ENH-23: DXY Macro Overlay — DXY>106 penalises import-heavy sectors.
    Research (Strategy 2026): "DXY >106 → trừ 5–10 điểm với ngành nhập khẩu nặng".
    """
    risk_keys = ["profitability","growth","debt","liquidity"]
    avg_risk = sum(risk_scores.get(k, 5.0) for k in risk_keys) / len(risk_keys)
    fund_quality = ((10 - avg_risk) / 10) * 60  # max 60 pts
    upside_score = min(max(upside_pct / 50 * 25, 0), 25)  # max 25 pts
    tech_pts = 0.0
    if tech_score is not None:
        tech_pts = min(max(tech_score / 100 * 15, 0), 15)
    total = fund_quality + upside_score + tech_pts
    # ENH-23: DXY macro overlay penalty
    if dxy_level is not None and dxy_level > 106 and sector in _IMPORT_HEAVY:
        penalty = 5 if dxy_level < 108 else 10
        total = max(0.0, total - penalty)
    return round(total, 1)

def generate_expert_commentary(
        ticker: str, sector: str, current_price: float,
        eps: float, pe: float, pb: float, roe: float, roa: float, npm: float,
        ohlc_ana: dict, fair_val: float, upside_pct: float,
        risk_sc: dict, composite_score: float, is_vi: bool = True) -> str:
    """
    ENH-26: Rule-based expert analyst commentary (SSI Research style).
    Generates paragraph commentary from indicators. Used in Deep Audit, Profiler S6.
    """
    lines = []
    vi = is_vi
    ohlc_ok = "error" not in ohlc_ana

    # 1. Valuation assessment
    if fair_val > 0 and current_price > 0:
        if upside_pct > 25:
            lines.append(
                f"**{'Định giá: CHIẾT KHẤU MẠNH' if vi else 'Valuation: DEEP DISCOUNT'}** — "
                f"{'Mức giá hiện tại thấp hơn giá trị hợp lý ước tính' if vi else 'Current price trades well below estimated fair value'} "
                f"({upside_pct:+.1f}%). {'Đây là vùng giá hấp dẫn để tích lũy dài hạn.' if vi else 'Attractive accumulation zone for long-term investors.'}"
            )
        elif upside_pct > 10:
            lines.append(
                f"**{'Định giá: CHIẾT KHẤU VỪA PHẢI' if vi else 'Valuation: MODERATE DISCOUNT'}** — "
                f"{'Cổ phiếu giao dịch dưới giá trị hợp lý' if vi else 'Stock trading below fair value'} "
                f"({upside_pct:+.1f}%). {'Tiềm năng tăng giá trong trung hạn.' if vi else 'Upside potential over medium term.'}"
            )
        elif upside_pct > -10:
            lines.append(
                f"**{'Định giá: HỢP LÝ' if vi else 'Valuation: FAIR VALUE'}** — "
                f"{'Giá thị trường phản ánh đầy đủ giá trị cơ bản' if vi else 'Market price fully reflects fundamental value'} "
                f"({upside_pct:+.1f}%). {'Nên chờ đợt pullback để có giá tốt hơn.' if vi else 'Wait for pullback for better entry.'}"
            )
        else:
            lines.append(
                f"**{'Định giá: ĐẮTQUA' if vi else 'Valuation: OVERVALUED'}** — "
                f"{'Cổ phiếu đang giao dịch trên giá trị hợp lý' if vi else 'Stock trading above fair value'} "
                f"({upside_pct:+.1f}%). {'Áp lực điều chỉnh cao, hạn chế mua mới.' if vi else 'High correction risk, limit new buys.'}"
            )

    # 2. Quality assessment
    quality_flags = []
    if roe and roe > 18:
        quality_flags.append("ROE cao (>18%)" if vi else "High ROE (>18%)")
    if roa and roa > 10:
        quality_flags.append("ROA mạnh (>10%)" if vi else "Strong ROA (>10%)")
    if npm and npm > 15:
        quality_flags.append("Biên lợi nhuận tốt (>15%)" if vi else "Good margin (>15%)")
    if quality_flags:
        lines.append(
            ("**Chất lượng kinh doanh:** " if vi else "**Business Quality:** ") +
            ", ".join(quality_flags) + ".")

    # 3. Technical signal
    if ohlc_ok:
        rsi = ohlc_ana.get("rsi", 50)
        tech_score = ohlc_ana.get("tech_score", 50)
        macd_bull = ohlc_ana.get("macd_bull", False)
        bb_pos = ohlc_ana.get("bb_position", 0.5)
        trend_up = ohlc_ana.get("above_sma50", False)

        tech_parts = []
        if rsi < 35:
            tech_parts.append(f"RSI={rsi:.0f} {'(vùng quá bán — tiềm năng bật)' if vi else '(oversold — bounce potential)'}")
        elif rsi > 70:
            tech_parts.append(f"RSI={rsi:.0f} {'(vùng quá mua — thận trọng)' if vi else '(overbought — caution)'}")
        else:
            tech_parts.append(f"RSI={rsi:.0f} {'(trung tính)' if vi else '(neutral)'}")

        if macd_bull:
            tech_parts.append("MACD " + ("cắt lên" if vi else "bullish cross"))
        if trend_up:
            tech_parts.append("Xu hướng tăng (trên SMA50)" if vi else "Uptrend (above SMA50)")

        if tech_parts:
            lines.append(
                ("**Kỹ thuật:** " if vi else "**Technical:** ") + " | ".join(tech_parts) + ".")

    # 4. Golden Window timing advice
    if ohlc_ok:
        rsi = ohlc_ana.get("rsi", 50)
        atr = ohlc_ana.get("atr", 0)
        if atr > 0 and current_price > 0:
            atr_pct = atr / current_price * 100
            timing_msg = []
            if 35 <= rsi <= 55 and ohlc_ana.get("above_sma50", False):
                timing_msg.append(
                    "⏰ " + ("Cửa sổ vàng 13:00–14:00 VN phù hợp để tích lũy. "
                              "Vào lệnh khi giá giữ trên vùng hỗ trợ SMA20."
                              if vi else
                              "Golden Window 13:00–14:00 VN suitable for entry. "
                              "Enter when price holds above SMA20 support."))
            elif rsi < 35:
                timing_msg.append(
                    "⏰ " + ("Cổ phiếu trong vùng quá bán — chờ tín hiệu xác nhận đảo chiều "
                              "trước khi vào lệnh trong khung 13:00–14:30."
                              if vi else
                              "Stock in oversold zone — wait for reversal confirmation "
                              "before entering in 13:00–14:30 window."))
            if timing_msg:
                lines.append(timing_msg[0])

    # 5. Risk summary
    avg_risk = sum(risk_sc.get(k, 5) for k in ["profitability","growth","debt","liquidity"]) / 4
    if avg_risk < 3:
        lines.append("🟢 " + ("Rủi ro THẤP — hồ sơ tài chính vững chắc." if vi else "LOW RISK — solid financial profile."))
    elif avg_risk < 6:
        lines.append("🟡 " + ("Rủi ro TRUNG BÌNH — theo dõi biến động dòng tiền." if vi else "MEDIUM RISK — monitor cash flow changes."))
    else:
        lines.append("🔴 " + ("Rủi ro CAO — cần thẩm định sâu trước khi đầu tư." if vi else "HIGH RISK — requires deep due diligence."))

    # 6. Composite score summary
    lines.append(
        ("**Điểm Tổng Hợp: **" if vi else "**Composite Score: **") +
        f"**{composite_score:.0f}/100**" +
        (f" — {'Tốt (mua/hold)' if composite_score >= 65 else ('Trung bình' if composite_score >= 45 else 'Yếu (thận trọng)')}" if vi
         else f" — {'Good (buy/hold)' if composite_score >= 65 else ('Neutral' if composite_score >= 45 else 'Weak (caution)')}")
    )

    return "\n\n".join(lines)


def get_recommendation(composite_score: float, upside_pct: float,
                        risk_scores: dict, lang: str = "VI") -> tuple:
    """
    Returns (label_key, color, rationale_vi, rationale_en).
    """
    max_risk = max(risk_scores.values())

    if composite_score >= 75 and upside_pct > 20 and max_risk < 7:
        key = "sp_rec_strong_buy"; color = "#00cc44"
    elif composite_score >= 60 and upside_pct > 5:
        key = "sp_rec_buy"; color = "#44bb22"
    elif composite_score >= 40 or (upside_pct > -10 and max_risk < 7):
        key = "sp_rec_hold"; color = "#ffaa00"
    elif composite_score >= 25 or upside_pct > -25:
        key = "sp_rec_sell"; color = "#ff5500"
    else:
        key = "sp_rec_strong_sell"; color = "#cc0000"

    # Build rationale
    vi_parts, en_parts = [], []
    # Valuation
    if upside_pct > 20:
        vi_parts.append(f"✅ Cổ phiếu đang giao dịch dưới giá trị hợp lý ~{upside_pct:.0f}%")
        en_parts.append(f"✅ Stock trading ~{upside_pct:.0f}% below fair value")
    elif upside_pct < -15:
        vi_parts.append(f"⚠️ Cổ phiếu đang giao dịch cao hơn giá trị ~{abs(upside_pct):.0f}%")
        en_parts.append(f"⚠️ Stock trading ~{abs(upside_pct):.0f}% above fair value")
    # Profitability
    p_risk = risk_scores.get("profitability", 5)
    if p_risk <= 3:
        vi_parts.append("✅ Khả năng sinh lời tốt (ROE/margin cao)")
        en_parts.append("✅ Strong profitability (high ROE/margins)")
    elif p_risk >= 8:
        vi_parts.append("❌ Khả năng sinh lời yếu, cần theo dõi")
        en_parts.append("❌ Weak profitability, monitor closely")
    # Debt
    d_risk = risk_scores.get("debt", 5)
    if d_risk <= 3:
        vi_parts.append("✅ Cấu trúc vốn lành mạnh, nợ vay thấp")
        en_parts.append("✅ Healthy capital structure, low leverage")
    elif d_risk >= 7:
        vi_parts.append("⚠️ Đòn bẩy tài chính cao, rủi ro lãi suất")
        en_parts.append("⚠️ High financial leverage, interest rate risk")
    # Growth
    g_risk = risk_scores.get("growth", 5)
    if g_risk <= 3:
        vi_parts.append("✅ Tăng trưởng doanh thu/lợi nhuận mạnh")
        en_parts.append("✅ Strong revenue/earnings growth trajectory")
    elif g_risk >= 7:
        vi_parts.append("⚠️ Tăng trưởng chậm hoặc suy giảm")
        en_parts.append("⚠️ Slowing or declining growth")

    rationale = "\n\n".join(vi_parts) if lang == "VI" else "\n\n".join(en_parts)
    return key, color, rationale

# ══════════════════════════════════════════════════════════════
#  UNIFIED SIGNAL ENGINE  (FIX-19 / ENH-16/17/18)
#  Bridges Market Scanner (technical) ↔ Stock Profiler (fundamental)
#  Resolves apparent divergence by showing BOTH with horizon labels
# ══════════════════════════════════════════════════════════════
def get_scanner_signal_for_profiler(ticker: str) -> dict:
    """
    Runs the EXACT same logic as scan_one_ticker() for a single ticker
    and returns a structured dict for display in the Stock Profiler.
    This ensures the Profiler always shows the same technical signal
    as the Market Scanner — eliminating any perception of inconsistency.
    """
    try:
        df, src, err = download_data(ticker, days=365, min_rows=40)
        if df is None or df.empty or len(df) < 40:
            return {"error": err or "No price data", "signal": "–", "score": 0}

        df = clean_data(df)
        df = calculate_indicators(df)
        if df.empty:
            return {"error": "Indicator calculation failed", "signal": "–", "score": 0}

        latest  = df.iloc[-1]
        avg_v   = float(df["Volume"].tail(20).mean()) if "Volume" in df.columns else 0
        last_v  = float(latest.get("Volume", 0))

        def _safe(col):
            v = latest.get(col)
            try: return float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else None
            except: return None

        rsi_v  = _safe("RSI")  or 50.0
        bbl_v  = _safe("BB_Lower") or float(latest["Close"])
        bbu_v  = _safe("BB_Upper") or float(latest["Close"])
        sma20  = _safe("SMA20")
        sma50  = _safe("SMA50")
        macd   = _safe("MACD")
        macs   = _safe("MACD_Signal")
        adx_v  = _safe("ADX")  or 0.0
        sk     = _safe("STOCH_K")
        c_v    = float(latest["Close"])

        # Use SAME signal logic as scan_one_ticker — filters OFF (profiler doesn't apply filters)
        trend_ok = True  # profiler always shows raw signal without filter bias
        hanh_vi  = "THEO DÕI"
        if rsi_v < rsi_buy_thresh  and c_v < bbl_v:  hanh_vi = "MUA"
        elif rsi_v > rsi_sell_thresh and c_v > bbu_v: hanh_vi = "BÁN"

        sig_type = "BUY" if hanh_vi == "MUA" else ("BÁN" if hanh_vi == "BÁN" else "BUY")
        score, confirms = compute_composite_score(
            latest.to_dict(), avg_v, last_v, trend_ok,
            sig_type, rsi_buy_thresh, rsi_sell_thresh)

        # Detailed trigger reasons
        trigger_reasons = []
        if hanh_vi == "MUA":
            if rsi_v < rsi_buy_thresh:
                trigger_reasons.append(f"RSI={rsi_v:.1f} < {rsi_buy_thresh} (quá bán)")
            if c_v < bbl_v:
                trigger_reasons.append(f"Giá={c_v:,.0f} < BB↓={bbl_v:,.0f}")
            if macd and macs and macd > macs:
                trigger_reasons.append("MACD > Signal ↑")
        elif hanh_vi == "BÁN":
            if rsi_v > rsi_sell_thresh:
                trigger_reasons.append(f"RSI={rsi_v:.1f} > {rsi_sell_thresh} (quá mua)")
            if c_v > bbu_v:
                trigger_reasons.append(f"Giá={c_v:,.0f} > BB↑={bbu_v:,.0f}")
            if macd and macs and macd < macs:
                trigger_reasons.append("MACD < Signal ↓")
        else:
            trigger_reasons.append(f"RSI={rsi_v:.1f} (trung tính)")
            trigger_reasons.append(f"Giá trong dải BB [{bbl_v:,.0f}–{bbu_v:,.0f}]")

        # SMA context
        if sma50:
            above50 = c_v > sma50
            trigger_reasons.append(f"{'↑' if above50 else '↓'} SMA50={sma50:,.0f}")

        signal_en = {"MUA": "BUY", "BÁN": "SELL", "THEO DÕI": "WATCH"}.get(hanh_vi, hanh_vi)
        color = "#00cc44" if hanh_vi == "MUA" else ("#ff4444" if hanh_vi == "BÁN" else "#ffaa00")

        return {
            "signal_vi":    hanh_vi,
            "signal_en":    signal_en,
            "score":        score,
            "confirms":     confirms,
            "trigger_reasons": trigger_reasons,
            "rsi":          rsi_v,
            "bbl":          bbl_v,
            "bbu":          bbu_v,
            "sma20":        sma20,
            "sma50":        sma50,
            "macd":         macd,
            "macd_sig":     macs,
            "adx":          adx_v,
            "price":        c_v,
            "color":        color,
            "source":       src,
            "n_rows":       len(df),
            "horizon":      "Short-term T+2 (1–5 sessions)",
        }
    except Exception as e:
        _log.warning(f"get_scanner_signal_for_profiler {ticker}: {e}")
        return {"error": str(e), "signal": "–", "score": 0}


def get_unified_recommendation(tech_signal: dict, fund_composite: float,
                                fund_rec_key: str, upside_pct: float,
                                lang: str = "VI") -> dict:
    """
    Blends technical short-term signal with fundamental long-term signal
    into a single unified view. Uses different weights based on data quality.

    Returns: {label, color, weight_tech, weight_fund, explanation}
    """
    is_vi = lang == "VI"

    # Map signals to numeric: STRONG_BUY=2, BUY=1, WATCH=0, SELL=-1, STRONG_SELL=-2
    tech_sig = tech_signal.get("signal_vi", "THEO DÕI")
    tech_num = {"MUA": 1, "THEO DÕI": 0, "BÁN": -1}.get(tech_sig, 0)

    fund_map = {
        "sp_rec_strong_buy": 2, "sp_rec_buy": 1,
        "sp_rec_hold": 0, "sp_rec_sell": -1, "sp_rec_strong_sell": -2
    }
    fund_num = fund_map.get(fund_rec_key, 0)

    # Weight: technical = 30%, fundamental = 70% (default)
    # If no fundamental data (fund_composite between 28-35 range = default), raise tech weight
    data_quality_score = fund_composite
    if 28 <= data_quality_score <= 42:  # near default (missing fundamental data)
        w_tech, w_fund = 0.60, 0.40
        quality_note_vi = "⚠️ Dữ liệu cơ bản hạn chế — trọng số kỹ thuật tăng (60%)"
        quality_note_en = "⚠️ Limited fundamental data — technical weight increased (60%)"
    else:
        w_tech, w_fund = 0.30, 0.70
        quality_note_vi = "Trọng số: Cơ bản 70% + Kỹ thuật 30%"
        quality_note_en = "Weights: Fundamental 70% + Technical 30%"

    # Blended score
    blended = tech_num * w_tech + fund_num * w_fund

    # Map blended to label
    if blended >= 1.5:
        label_vi, label_en, color = "✅ KHUYẾN NGHỊ MẠNH: MUA", "✅ STRONG BUY", "#00cc44"
    elif blended >= 0.5:
        label_vi, label_en, color = "🟢 KHUYẾN NGHỊ: MUA", "🟢 BUY", "#44bb22"
    elif blended >= -0.3:
        label_vi, label_en, color = "🟡 KHUYẾN NGHỊ: NẮM GIỮ", "🟡 HOLD", "#ffaa00"
    elif blended >= -1.0:
        label_vi, label_en, color = "🔴 KHUYẾN NGHỊ: BÁN", "🔴 SELL", "#ff5500"
    else:
        label_vi, label_en, color = "❌ KHUYẾN NGHỊ MẠNH: BÁN", "❌ STRONG SELL", "#cc0000"

    # Conflict detection
    conflict = (tech_num > 0 and fund_num < 0) or (tech_num < 0 and fund_num > 0)

    label = label_vi if is_vi else label_en
    quality_note = quality_note_vi if is_vi else quality_note_en

    return {
        "label":        label,
        "color":        color,
        "blended":      blended,
        "w_tech":       w_tech,
        "w_fund":       w_fund,
        "conflict":     conflict,
        "quality_note": quality_note,
        "tech_num":     tech_num,
        "fund_num":     fund_num,
    }

# ══════════════════════════════════════════════════════════════
#  STOCK PROFILER TAB — render function  (v18 — dual-signal)
# ══════════════════════════════════════════════════════════════
def render_stock_profiler_tab():
    L = _LANG_VI if st.session_state.lang == "VI" else _LANG_EN
    st.title(L["sp_title"])
    is_vi = st.session_state.lang == "VI"

    # ── Ticker input — ENH-19: multi-ticker support (separate by ";") ──
    col_in, col_btn, col_period = st.columns([3, 1, 1])
    with col_in:
        ticker_raw = st.text_input(
            ("🔍 Mã cổ phiếu — nhiều mã cách bởi ';' (vd: FPT;MWG;HPG)" if is_vi
             else "🔍 Ticker(s) — separate by ';'  e.g. FPT;MWG;HPG"),
            value="FCN", key="profiler_ticker")
    with col_btn:
        run_btn = st.button(L["sp_analyse_btn"], key="profiler_run",
                            width="stretch")
    with col_period:
        period_opt = st.radio("Period", [L["sp_quarterly"], L["sp_yearly"]],
                              horizontal=True, key="profiler_period")

    yearly = 1 if period_opt == L["sp_yearly"] else 0

    if "profiler_result" not in st.session_state:
        st.session_state.profiler_result = {}

    if run_btn and ticker_raw.strip():
        raw_tickers = [t.strip().upper() for t in ticker_raw.replace(",", ";").split(";") if t.strip()]
        st.session_state.profiler_result = {"tickers": raw_tickers, "yearly": yearly}

    result       = st.session_state.profiler_result
    saved_tickers = result.get("tickers", [])
    if not saved_tickers:
        st.info("👈 " + ("Nhập mã cổ phiếu (nhiều mã cách bởi ';') và nhấn Phân Tích Ngay" if is_vi
                          else "Enter ticker(s) separated by ';' and click Analyse Now"))
        return

    # ── ENH-19: multi-ticker comparison dashboard ──
    if len(saved_tickers) > 1:
        st.markdown("### 📊 " + (f"So sánh {len(saved_tickers)} cổ phiếu" if is_vi
                                   else f"Comparing {len(saved_tickers)} tickers"))
        compare_rows = []
        for _t in saved_tickers:
            try:
                _cf  = fetch_cafef_key_ratios(_t)
                _cfp = fetch_cafef_price(_t)
                _oa  = fetch_dnse_ohlc_analysis(_t)
                _oa_ok = "error" not in _oa
                _price = _cfp.get("price", _oa.get("price", 0) if _oa_ok else 0)
                _eps   = _cf.get("eps", 0)
                _pe    = _cf.get("pe", 0)
                _pb    = _cf.get("pb", 0)
                _sec   = get_sector(_t)
                _vm    = get_valuation_method(_sec, _eps, _pe)
                _dcf   = compute_dcf_valuation(_eps, 0.10) if _vm["use_dcf"] and _eps > 0 else 0
                _pef   = compute_pe_valuation(_eps, _sec)  if _vm["use_pe"]  and _eps > 0 else 0
                _bvps  = _cf.get("bvps", _price * 0.6)
                _roe   = _cf.get("roe", 12.0)
                _pbf   = compute_pb_valuation(_bvps, _roe / 100 if _roe > 1 else _roe)
                _fv    = aggregate_fair_value(_dcf, _pef, _pbf, 0)
                _up    = ((_fv - _price) / _price * 100) if _fv > 0 and _price > 0 else 0
                compare_rows.append({
                    "Mã" if is_vi else "Ticker": _t,
                    "Ngành" if is_vi else "Sector": _sec,
                    "Giá" if is_vi else "Price": f"{_price:,.0f}" if _price > 0 else "–",
                    "EPS": f"{_eps:,.0f}" if _eps > 0 else "–",
                    "P/E": f"{_pe:.1f}×" if _pe > 0 else "–",
                    "P/B": f"{_pb:.2f}×" if _pb > 0 else "–",
                    "Fair Value": f"{_fv:,.0f}" if _fv > 0 else "–",
                    "Upside %": f"{_up:+.1f}%" if _fv > 0 else "–",
                    "RSI": f"{_oa.get('rsi', 0):.1f}" if _oa_ok and _oa.get('rsi') else "–",
                    "Method": _vm["method_label"],
                })
            except Exception as _e:
                compare_rows.append({"Mã" if is_vi else "Ticker": _t,
                                      "Error": str(_e)[:60]})
        show_df(pd.DataFrame(compare_rows))
        st.markdown("---")
        st.markdown("### 🔍 " + ("Chi tiết từng mã (chọn tab)" if is_vi else "Per-ticker Deep Dive (select tab)"))
        _ticker_tabs = st.tabs([f"🏢 {_t}" for _t in saved_tickers])
        for _tab_obj, _ticker_single in zip(_ticker_tabs, saved_tickers):
            with _tab_obj:
                # Inline single-ticker analysis for each tab
                _profiler_ticker_key = f"_profiler_inline_{_ticker_single}"
                if st.button(f"▶ Analyse {_ticker_single}", key=f"btn_{_ticker_single}"):
                    st.session_state[_profiler_ticker_key] = True
                if st.session_state.get(_profiler_ticker_key):
                    st.session_state.profiler_result = {"tickers": [_ticker_single], "yearly": yearly}
                    st.rerun()
                else:
                    st.info(f"Click '▶ Analyse {_ticker_single}' to load full deep-dive for this ticker.")
        return

    # Single ticker mode
    ticker = saved_tickers[0]

    # ──────────────────────────────────────────────────────────
    # STEP 1: Load all data sources in cascade
    # Priority: TCBS → CafeF → SSI → DNSE OHLC (always works)
    # ──────────────────────────────────────────────────────────
    with st.spinner(L["sp_loading"]):
        # A) TCBS tcanalysis (may return 404)
        income_raw  = fetch_tcbs_financials(ticker, "incomestatement", yearly)
        balance_raw = fetch_tcbs_financials(ticker, "balancesheet",    yearly)
        cf_raw      = fetch_tcbs_financials(ticker, "cashflow",        yearly)
        ratio_raw   = fetch_tcbs_ratio(ticker, yearly)
        tcbs_ok     = not ratio_raw.empty

        # B) VNDirect financial statements — DISABLED (consistently times out, FIX-26)
        # SSI Finance-Indicator (ssi_ratios_df) provides ROA/ROE/Margin/D/E reliably
        vnd_stmts, vnd_ratios, vnd_ok = {}, pd.DataFrame(), False

        # C) CafeF — always reliable for key ratios & price
        cafef_ratios    = fetch_cafef_key_ratios(ticker)
        cafef_price_d   = fetch_cafef_price(ticker)
        cafef_sh        = fetch_cafef_shareholders(ticker)
        cafef_reports   = fetch_cafef_financial_reports(ticker)
        cafef_ok        = bool(cafef_ratios)

        # D) SSI company info
        ssi_info        = fetch_ssi_company_info(ticker)
        ssi_ratios_df   = fetch_ssi_finance_indicator(ticker)
        ssi_news        = fetch_ssi_news(ticker)

        # E) VNDirect company profile
        vnd_profile     = fetch_company_profile(ticker)

        # F) DNSE OHLC analysis — ALWAYS available as ultimate fallback
        ohlc_ana        = fetch_dnse_ohlc_analysis(ticker)
        ohlc_ok         = "error" not in ohlc_ana

        # Determine current price (priority: CafeF live → DNSE OHLC → VNDirect profile)
        if cafef_price_d.get("price", 0) > 0:
            current_price = cafef_price_d["price"]
            pct_chg       = cafef_price_d.get("pct_change", 0)
        elif ohlc_ok:
            current_price = ohlc_ana["price"]
            pct_chg       = ohlc_ana.get("ret1m", 0) * 100
        else:
            current_price = 0.0
            pct_chg       = 0.0

        # Build unified ratio dict (priority: TCBS → VNDirect → CafeF → OHLC implied)
        def _unified_val(tcbs_key, vnd_col, cafef_key, fallback=None):
            """FIX-25: Extract best value — TCBS > SSI > VNDirect > CafeF."""
            # P1: TCBS tcanalysis
            if tcbs_ok and not ratio_raw.empty and tcbs_key in ratio_raw.columns:
                v = pd.to_numeric(ratio_raw[tcbs_key], errors="coerce").dropna()
                if len(v) > 0:
                    return float(v.iloc[0])
            # P2: SSI Finance-Indicator (ROA, ROE, netProfitMargin, D/E always here)
            if not ssi_ratios_df.empty:
                _ssi_aliases = {
                    "roa":             ["roa","returnOnAsset","returnOnAssets"],
                    "roe":             ["roe","returnOnEquity"],
                    "netProfitMargin": ["netProfitMargin","profitMargin","netMargin"],
                    "payableOnEquity": ["payableOnEquity","debtToEquity","de"],
                    "currentPayment":  ["currentPayment","currentRatio"],
                    "eps":             ["eps","earningPerShare"],
                    "priceToEarning":  ["priceToEarning","pe"],
                    "priceToBook":     ["priceToBook","pb"],
                    "bookValuePerShare":["bookValuePerShare","bvps"],
                }
                for alias in _ssi_aliases.get(tcbs_key, [tcbs_key]):
                    for col in ssi_ratios_df.columns:
                        if alias.lower() == col.lower():
                            v = pd.to_numeric(ssi_ratios_df[col], errors="coerce").dropna()
                            if len(v) > 0:
                                return float(v.iloc[0])
            # P3: VNDirect
            if vnd_ok and not vnd_ratios.empty and vnd_col:
                for c in vnd_ratios.columns:
                    if vnd_col.lower() in c.lower():
                        v = pd.to_numeric(vnd_ratios[c], errors="coerce").dropna()
                        if len(v) > 0:
                            return float(v.iloc[0])
            # P4: CafeF key ratios
            if cafef_key and cafef_ratios.get(cafef_key) is not None:
                return float(cafef_ratios[cafef_key])
            return fallback

        eps_raw  = _unified_val("eps",            "EPS",   "eps",  ohlc_ana.get("implied_eps", 0) if ohlc_ok else 0)
        pe_val   = _unified_val("priceToEarning", "P/E",   "pe",   ohlc_ana.get("sector_pe", 15) if ohlc_ok else 15)
        pb_val   = _unified_val("priceToBook",    "P/B",   "pb",   None)
        roe_raw  = _unified_val("roe",            "ROE",   None,   None)
        roa_raw  = _unified_val("roa",            "ROA",   None,   None)
        npm_raw  = _unified_val("netProfitMargin","Biên ròng", None, None)
        de_raw   = _unified_val("payableOnEquity","D/E",   None,   None)
        cr_raw   = _unified_val("currentPayment", "Curr",  None,   None)
        bvps_raw = _unified_val("bookValuePerShare","BVPS","bvps", ohlc_ana.get("implied_bvps", 0) if ohlc_ok else 0)

        # Normalise pct fields (TCBS often stores as fraction 0–1)
        def _to_pct(v):
            if v is None: return None
            return v * 100 if abs(v) < 2 else v

        roe  = _to_pct(roe_raw)
        roa  = _to_pct(roa_raw)
        npm  = _to_pct(npm_raw)
        eps  = (eps_raw * 1000) if eps_raw and 0 < eps_raw < 100 else (eps_raw or 0)
        bvps = (bvps_raw * 1000) if bvps_raw and 0 < bvps_raw < 100 else (bvps_raw or 0)

        sector = get_sector(ticker)

        # Build display DataFrames
        income_df  = (_build_stmt_df(income_raw,  _INCOME_MAP,  st.session_state.lang)
                      if not income_raw.empty
                      else vnd_stmts.get("income", pd.DataFrame()))
        balance_df = (_build_stmt_df(balance_raw, _BALANCE_MAP, st.session_state.lang)
                      if not balance_raw.empty
                      else vnd_stmts.get("balance", pd.DataFrame()))
        cf_df      = (_build_stmt_df(cf_raw,      _CF_MAP,      st.session_state.lang)
                      if not cf_raw.empty
                      else vnd_stmts.get("cashflow", pd.DataFrame()))

        # Determine data source label
        if tcbs_ok:
            data_source = L["sp_source_tcbs"]
        elif vnd_ok:
            data_source = L["sp_source_vnd"]
        elif cafef_ok:
            data_source = "Nguồn: CafeF API" if is_vi else "Source: CafeF API"
        elif ohlc_ok:
            data_source = f"Nguồn: DNSE OHLC ({ohlc_ana.get('source','')}) — kỹ thuật" if is_vi else f"Source: DNSE OHLC ({ohlc_ana.get('source','')}) — technical"
        else:
            data_source = "⚠️ " + ("Dữ liệu hạn chế" if is_vi else "Limited data")

    # ── Status bar ──
    chg_color = "#00cc44" if pct_chg >= 0 else "#ff4444"
    # ENH-25: Ceiling / Floor / Reference price
    _ref_price = cafef_price_d.get("reference", 0) or (current_price if current_price > 0 else 0)
    _lims = get_price_limits(ticker, _ref_price)
    _ceil = _lims.get("ceiling", 0)
    _floor = _lims.get("floor", 0)
    _band  = _lims.get("band_pct", 7)
    _exch_lbl = _lims.get("exchange", TICKER_EXCHANGE.get(ticker, "HOSE"))
    if _ceil > 0:
        st.markdown(
            f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:8px;"
            f"padding:8px 14px;margin-bottom:8px;display:flex;gap:20px;align-items:center'>"
            f"<span style='color:#888;font-size:11px'>📊 {_exch_lbl} ±{_band:.0f}%</span>"
            f"&nbsp;|&nbsp;"
            f"<span style='color:#888;font-size:11px'>{'Tham chiếu' if is_vi else 'Reference'}:</span>"
            f" <b style='color:#f0f6fc'>{_ref_price:,.0f}</b>"
            f"&nbsp;|&nbsp;"
            f"<span style='color:#888;font-size:11px'>{'Giá trần' if is_vi else 'Ceiling'}:</span>"
            f" <b style='color:#ff4444'>{_ceil:,.0f}</b>"
            f"&nbsp;|&nbsp;"
            f"<span style='color:#888;font-size:11px'>{'Giá sàn' if is_vi else 'Floor'}:</span>"
            f" <b style='color:#00cc44'>{_floor:,.0f}</b>"
            f"</div>",
            unsafe_allow_html=True)
    st.markdown(f"""
<span style="font-size:13px;color:#888">{data_source} &nbsp;|&nbsp;
<b style="color:#4e9af1;font-size:15px">{current_price:,.0f} VNĐ</b>
<span style="color:{chg_color};font-size:13px"> {pct_chg:+.2f}%</span>
&nbsp;|&nbsp; Ngành/Sector: <b>{sector}</b>
&nbsp;|&nbsp; TCBS: {'✅' if tcbs_ok else '❌'} CafeF: {'✅' if cafef_ok else '❌'} OHLC: {'✅' if ohlc_ok else '❌'}
</span>""", unsafe_allow_html=True)

    # ── 6 Sub-tabs ──
    sub_labels = [L["sp_overview"], L["sp_financials"], L["sp_ratios"],
                  L["sp_valuation"], L["sp_risk"], L["sp_recommendation"]]
    s1, s2, s3, s4, s5, s6 = st.tabs(sub_labels)

    # ════════════ S1: COMPANY OVERVIEW ════════════
    with s1:
        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.markdown(f"### 🏢 {ticker} — {sector}")
            # Aggregate overview from best source
            overview_items = []
            if vnd_profile:
                for k, v in vnd_profile.items():
                    if not k.startswith("_") and v and v != "–":
                        overview_items.append((k, str(v)[:80]))
            # Add CafeF data
            if cafef_ratios.get("mcap_bn"):
                label = "Vốn hóa (tỷ)" if is_vi else "Mkt Cap (bn)"
                overview_items.append((label, f"{cafef_ratios['mcap_bn']:,.0f}"))
            if cafef_ratios.get("shares_listed"):
                label = "CP niêm yết" if is_vi else "Listed Shares"
                overview_items.append((label, cafef_ratios["shares_listed"]))
            if cafef_ratios.get("ratio_period"):
                overview_items.append(("EPS period", cafef_ratios["ratio_period"]))

            if overview_items:
                for k, v in overview_items[:10]:
                    st.metric(k, v)
            else:
                st.info(L["sp_no_data"])

            # ENH-29: Catalyst Tracker — dividends, AGM, FTSE upgrade events
            corp_actions = ssi_info.get("corporate_actions", [])
            if corp_actions and isinstance(corp_actions, list):
                st.markdown("---")
                st.markdown("**📅 " + ("Sự kiện & Xúc tác (Catalyst Tracker)" if is_vi else "Events & Catalysts (Catalyst Tracker)") + "**")
                _keyword_vi = {"Cổ tức":"💵","Thưởng":"🎁","ĐHCĐ":"🏛️","Phát hành":"📊","Niêm yết":"📋",
                                "FTSE":"⭐","Chia tách":"✂️","Thưởng cổ phiếu":"🎁"}
                for act in corp_actions[:5]:
                    _title = act.get("title", act.get("eventName", "–"))
                    _date  = act.get("date", act.get("eventDate", ""))
                    _icon  = "📌"
                    for kw, ico in _keyword_vi.items():
                        if kw.lower() in _title.lower():
                            _icon = ico; break
                    st.markdown(f"{_icon} **{_date}** — {_title[:80]}")
            cap_div = ssi_info.get("cap_dividend", {})
            if cap_div and isinstance(cap_div, dict):
                _divrate = cap_div.get("dividendRate", cap_div.get("DividendRate", 0))
                _divtype = cap_div.get("dividendType", cap_div.get("DividendType", ""))
                if _divrate:
                    st.info(f"💵 " + ("Cổ tức gần nhất: " if is_vi else "Last dividend: ") +
                            f"**{_divrate}%** ({_divtype})")

            # Shareholder structure
            sh = cafef_sh or {}
            if sh:
                st.markdown("---")
                st.markdown("**" + ("Cơ cấu cổ đông" if is_vi else "Ownership Structure") + "**")
                c_f, c_s, c_o = st.columns(3)
                with c_f: st.metric("🌐 " + ("Nước ngoài" if is_vi else "Foreign"),
                                     f"{sh.get('foreign_pct', 0):.1f}%")
                with c_s: st.metric("🏛️ " + ("Nhà nước" if is_vi else "State"),
                                     f"{sh.get('state_pct', 0):.1f}%")
                with c_o: st.metric("👥 " + ("Khác" if is_vi else "Other"),
                                     f"{sh.get('other_pct', 0):.1f}%")
                major = sh.get("major_holders", [])
                if major:
                    st.markdown("**" + ("Cổ đông lớn" if is_vi else "Major Holders") + "**")
                    for h in major[:5]:
                        st.markdown(f"• {h['name']} — **{h['pct']:.2f}%**")

        with c_right:
            # KPI strip
            kpi_data = [
                ("EPS (đ)",          f"{eps:,.0f}"              if eps  else "–"),
                ("P/E",              f"{pe_val:.1f}"            if pe_val else "–"),
                ("P/B",              f"{pb_val:.2f}"            if pb_val else "–"),
                ("ROE (%)",          f"{roe:.1f}%"              if roe  else "–"),
                ("ROA (%)",          f"{roa:.1f}%"              if roa  else "–"),
                ("Biên ròng (%)" if is_vi else "Net Margin (%)",
                                     f"{npm:.1f}%"              if npm  else "–"),
                ("D/E",              f"{de_raw:.2f}"            if de_raw else "–"),
                ("BVPS (đ)",         f"{bvps:,.0f}"             if bvps else "–"),
            ]
            for row_kpis in [kpi_data[:4], kpi_data[4:]]:
                kpi_cols = st.columns(len(row_kpis))
                for (label, val), col in zip(row_kpis, kpi_cols):
                    with col: st.metric(label, val)

            # OHLC 52-week range
            if ohlc_ok:
                st.markdown("---")
                col52a, col52b, col52c, col52d = st.columns(4)
                with col52a: st.metric("52W High", f"{ohlc_ana['high52']:,.0f}")
                with col52b: st.metric("52W Low",  f"{ohlc_ana['low52']:,.0f}")
                pct52 = ohlc_ana.get("price_percentile", 0)
                with col52c: st.metric("52W Pos", f"{pct52*100:.0f}%",
                                       help="0%=at 52W low, 100%=at 52W high")
                # ENH-27: VWAP signal
                _vwap_sig = ohlc_ana.get("vwap_signal", "HOLD")
                _vwap_20  = ohlc_ana.get("vwap_20", 0)
                _vwap_pct = ohlc_ana.get("vwap_pct", 0)
                _vwap_color = "#00cc44" if _vwap_sig == "BUY" else ("#ff4444" if _vwap_sig == "SELL" else "#ffaa00")
                with col52d:
                    st.metric("VWAP(20)",
                               f"{_vwap_20:,.0f}" if _vwap_20 > 0 else "–",
                               delta=f"{_vwap_pct:+.1f}% vs VWAP",
                               help="20-day VWAP approximation. BUY if price > VWAP×1.005")
                # Momentum returns
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1: st.metric("1M Return", f"{ohlc_ana['ret1m']*100:+.1f}%")
                with col_m2: st.metric("3M Return", f"{ohlc_ana['ret3m']*100:+.1f}%")
                with col_m3: st.metric("6M Return", f"{ohlc_ana['ret6m']*100:+.1f}%")

            # Company profile text
            profile_text = vnd_profile.get("_profile_text", "")
            if profile_text:
                with st.expander("📄 " + ("Giới thiệu công ty" if is_vi else "Company Profile")):
                    st.markdown(str(profile_text)[:3000])

            # Leadership from SSI
            leadership = ssi_info.get("leadership", [])
            if leadership and isinstance(leadership, list):
                with st.expander("👤 " + ("Ban lãnh đạo" if is_vi else "Leadership")):
                    for person in leadership[:8]:
                        name  = person.get("fullName", person.get("name", ""))
                        pos   = person.get("positionName", person.get("position", ""))
                        if name:
                            st.markdown(f"• **{name}** — {pos}")

            # CafeF financial report links
            if cafef_reports:
                with st.expander("📄 " + ("Báo cáo tài chính" if is_vi else "Financial Report PDFs")):
                    for rpt in cafef_reports[:6]:
                        lnk = rpt.get("link", "")
                        nm  = rpt.get("name", rpt.get("period", ""))
                        if lnk:
                            st.markdown(f"[📥 {nm}]({lnk})")

    # ════════════ S2: FINANCIAL STATEMENTS ════════════
    with s2:
        fs_period_lbl = L["sp_quarterly"] if yearly == 0 else L["sp_yearly"]
        has_stmts = not (income_df.empty and balance_df.empty and cf_df.empty)

        if has_stmts:
            for stmt_lbl, df in [
                (f"💰 {L['sp_income']} ({fs_period_lbl})",   income_df),
                (f"🏦 {L['sp_balance']} ({fs_period_lbl})",  balance_df),
                (f"💸 {L['sp_cashflow']} ({fs_period_lbl})", cf_df),
            ]:
                if df is not None and not df.empty:
                    with st.expander(stmt_lbl, expanded=(stmt_lbl.startswith("💰"))):
                        show_df(df.astype({c: str for c in df.select_dtypes("object").columns}))
                        # Revenue + Net Profit bar chart for income
                        if "income" in stmt_lbl.lower() or "kinh doanh" in stmt_lbl.lower():
                            period_col = next((c for c in df.columns if c in ("Kỳ","Period")), None)
                            rev_col  = next((c for c in df.columns if any(k in c for k in ["Doanh thu","Revenue"])), None)
                            lnst_col = next((c for c in df.columns if any(k in c for k in ["LNST","Net Profit"])), None)
                            if period_col and rev_col and lnst_col:
                                fig = go.Figure()
                                fig.add_bar(x=df[period_col].astype(str), y=df[rev_col],
                                            name=rev_col, marker_color="#4e9af1")
                                fig.add_bar(x=df[period_col].astype(str), y=df[lnst_col],
                                            name=lnst_col, marker_color="#2ecc71")
                                fig.update_layout(barmode="group", height=260,
                                                  template="plotly_dark",
                                                  legend=dict(orientation="h"),
                                                  margin=dict(t=30,b=20,l=20,r=20))
                                st.plotly_chart(fig, width="stretch")
        else:
            # Fallback: show DNSE OHLC price chart + CafeF liveboard
            st.warning("⚠️ " + ("Không có BCTC từ TCBS (404) và VNDirect (timeout). "
                                    "Hiển thị dữ liệu kỹ thuật OHLC. "
                                    "Điểm rủi ro được ước tính từ phân tích kỹ thuật."
                                    if is_vi else
                                    "No financial statements: TCBS (404) + VNDirect (timeout). "
                                    "Displaying OHLC technical data. "
                                    "Risk scores estimated from technical analysis."))
            st.caption("ℹ️ " + ("SSI Finance-Indicator đang được thử — có thể có dữ liệu ROA/ROE/Margin từ SSI bên dưới."
                                  if is_vi else
                                  "SSI Finance-Indicator is being tried — ROA/ROE/Margin may still be available from SSI below."))
            ohlc_df = ohlc_ana.get("data_df") if ohlc_ok else None
            if ohlc_df is not None and not ohlc_df.empty:
                fig_ohlc = go.Figure(go.Candlestick(
                    x=ohlc_df.index if isinstance(ohlc_df.index, pd.DatetimeIndex)
                      else ohlc_df.get("Date", ohlc_df.index),
                    open=ohlc_df["Open"], high=ohlc_df["High"],
                    low=ohlc_df["Low"],  close=ohlc_df["Close"],
                    name=ticker, increasing_line_color="#00cc66",
                    decreasing_line_color="#ff4444",
                ))
                fig_ohlc.update_layout(height=350, template="plotly_dark",
                                        title=f"{ticker} — 2Y Price History",
                                        xaxis_rangeslider_visible=False,
                                        margin=dict(t=40,b=20,l=20,r=20))
                st.plotly_chart(fig_ohlc, width="stretch")

        # Corporate actions from SSI
        corp_acts = ssi_info.get("corporate_actions", [])
        if corp_acts and isinstance(corp_acts, list):
            with st.expander("📅 " + ("Sự kiện doanh nghiệp" if is_vi else "Corporate Actions")):
                for act in corp_acts[:10]:
                    date = act.get("effectDate", act.get("ExEffectiveDate",""))[:10] if act.get("effectDate") or act.get("ExEffectiveDate") else ""
                    name = act.get("eventName", act.get("EventName", str(act)))
                    st.markdown(f"• **{date}** — {name}")

    # ════════════ S3: FINANCIAL RATIOS ════════════
    with s3:
        # Priority: TCBS ratios → VNDirect ratios → CafeF key ratios → SSI ratios
        ratio_display = ratio_raw if tcbs_ok else vnd_ratios

        if not ratio_display.empty:
            # Map raw columns to display labels
            disp_df = pd.DataFrame()
            src_map = _RATIO_MAP
            for src_k, label in src_map.items():
                if src_k in ratio_display.columns:
                    col = pd.to_numeric(ratio_display[src_k], errors="coerce")
                    pct_labels = {"ROE (%)","ROA (%)","ROIC (%)","Biên gộp (%)","Biên EBITDA (%)","Biên ròng (%)","Div. Yield (%)"}
                    if label in pct_labels and col.dropna().abs().max() <= 2:
                        col = (col * 100).round(2)
                    else:
                        col = col.round(3)
                    disp_df[label] = col
            if "period" in ratio_display.columns:
                disp_df.insert(0, "Kỳ" if is_vi else "Period",
                               ratio_display["period"].astype(str).str[:7])
            if not disp_df.empty:
                show_df(disp_df.head(8).astype({c: str for c in disp_df.select_dtypes("object").columns}))

            # Trend charts
            period_col = "Kỳ" if is_vi else "Period"
            if period_col in disp_df.columns and len(disp_df) > 1:
                x = disp_df[period_col].astype(str)
                trend_pairs = [
                    ("ROE (%)", "ROA (%)", "#00cc66", "#4e9af1"),
                    ("Biên gộp (%)", "Biên ròng (%)", "#f1a84e", "#a84ef1"),
                    ("P/E", "P/B", "#f1e74e", "#4ef1a8"),
                ]
                fig_trend = make_subplots(rows=1, cols=3,
                    subplot_titles=["ROE vs ROA","Margins","P/E vs P/B"])
                for i, (c1_lbl, c2_lbl, col1, col2) in enumerate(trend_pairs, 1):
                    if c1_lbl in disp_df.columns:
                        fig_trend.add_scatter(x=x, y=disp_df[c1_lbl], name=c1_lbl,
                                              line=dict(color=col1, width=2), row=1, col=i)
                    if c2_lbl in disp_df.columns:
                        fig_trend.add_scatter(x=x, y=disp_df[c2_lbl], name=c2_lbl,
                                              line=dict(color=col2, width=2, dash="dash"), row=1, col=i)
                fig_trend.update_layout(height=280, template="plotly_dark",
                                        showlegend=True,
                                        legend=dict(orientation="h", y=-0.2),
                                        margin=dict(t=40,b=40,l=20,r=20))
                st.plotly_chart(fig_trend, width="stretch")
        else:
            # Show CafeF summary + SSI ratios
            st.subheader("📊 " + ("Chỉ số tài chính từ CafeF" if is_vi else "Financial Ratios from CafeF"))
            if cafef_ratios:
                kv_data = []
                label_map = {
                    "eps": "EPS (đ)", "pe": "P/E", "bvps": "BVPS (đ)",
                    "pb": "P/B", "mcap_bn": "Vốn hóa (tỷ)" if is_vi else "Mkt Cap (bn)",
                    "ratio_period": "Kỳ số liệu" if is_vi else "Ratio Period",
                }
                for k, lbl in label_map.items():
                    v = cafef_ratios.get(k)
                    if v is not None:
                        kv_data.append({"Chỉ số" if is_vi else "Metric": lbl,
                                        "Giá trị" if is_vi else "Value": str(v)})
                if kv_data:
                    show_df(pd.DataFrame(kv_data))

            if not ssi_ratios_df.empty:
                st.markdown("---")
                st.markdown("**SSI Finance Indicators**")
                show_df(ssi_ratios_df.head(8).astype(str))

            # OHLC technical indicators
            if ohlc_ok:
                st.markdown("---")
                st.subheader("📈 " + ("Phân tích kỹ thuật (từ dữ liệu giá)" if is_vi else "Technical Analysis (from price data)"))
                tech_data = {
                    "Chỉ số" if is_vi else "Indicator": ["RSI(14)", "MACD", "ADX", "52W Position", "Vol Trend", "Tech Score"],
                    "Giá trị" if is_vi else "Value": [
                        f"{ohlc_ana['rsi']:.1f}",
                        f"{'Tăng↑' if ohlc_ana['macd_bullish'] else 'Giảm↓'}  ({ohlc_ana['macd']:+.2f})",
                        f"{ohlc_ana['adx']:.1f}" + (" (Xu hướng rõ)" if ohlc_ana["adx"] > 25 else " (Đi ngang)"),
                        f"{ohlc_ana['price_percentile']*100:.0f}% (52W)",
                        "Tích lũy ↑" if ohlc_ana["vol_spike"] and ohlc_ana["macd_bullish"] else "Bình thường",
                        f"{ohlc_ana['tech_score']:.0f}/100",
                    ],
                    "Nhận định" if is_vi else "Signal": [
                        "Quá bán" if ohlc_ana["rsi_oversold"] else ("Quá mua" if ohlc_ana["rsi_overbought"] else "Trung tính"),
                        "BUY signal" if ohlc_ana["macd_bullish"] else "SELL signal",
                        "Trending" if ohlc_ana["adx"] > 25 else "Ranging",
                        "Vùng thấp" if ohlc_ana["price_percentile"] < 0.35 else ("Vùng cao" if ohlc_ana["price_percentile"] > 0.75 else "Trung bình"),
                        "Bullish vol" if (ohlc_ana["vol_spike"] and ohlc_ana["macd_bullish"]) else "–",
                        "Mạnh" if ohlc_ana["tech_score"] > 65 else ("Yếu" if ohlc_ana["tech_score"] < 35 else "Trung bình"),
                    ]
                }
                show_df(pd.DataFrame(tech_data))

    # ════════════ S4: VALUATION (v19 — Sector-Aware ENH-20) ════════════
    with s4:
        if current_price <= 0:
            st.warning("⚠️ " + ("Không có giá hiện tại" if is_vi else "No current price available"))
        else:
            # EPS growth from income trend
            eps_growth = 0.10
            if not income_raw.empty and "postTaxProfit" in income_raw.columns:
                profits = pd.to_numeric(income_raw["postTaxProfit"], errors="coerce").dropna()
                if len(profits) >= 4:
                    recent = profits.iloc[:4].sum()
                    older  = profits.iloc[4:8].sum() if len(profits) >= 8 else profits.iloc[-4:].sum()
                    eps_growth = max(-0.20, min(0.35, (recent - older) / abs(older))) if older != 0 else 0.10
            elif ohlc_ok:
                eps_growth = max(-0.20, min(0.30, ohlc_ana.get("ret3m", 0.10) * 1.5))

            eps_eff  = eps  if eps  > 0 else ohlc_ana.get("implied_eps", current_price / 15) if ohlc_ok else current_price / 15
            bvps_eff = bvps if bvps > 0 else ohlc_ana.get("implied_bvps", current_price * 0.6) if ohlc_ok else current_price * 0.6
            roe_eff  = roe  if roe  else 12.0
            pe_curr  = current_price / eps_eff if eps_eff > 0 else 0

            # ENH-20: Sector-aware valuation method selection
            val_method = get_valuation_method(sector, eps_eff, pe_curr)

            # ENH-20: Cyclical sectors — normalize EPS to 5Y average to avoid cycle traps
            if val_method["normalize_eps"] and eps_eff > 0:
                if not income_raw.empty and "postTaxProfit" in income_raw.columns:
                    profits_all = pd.to_numeric(income_raw["postTaxProfit"], errors="coerce").dropna()
                    shares_est = max(1e9, current_price / max(eps_eff, 1))
                    if len(profits_all) >= 4:
                        eps_normalized = float((profits_all.iloc[:min(20, len(profits_all))] / shares_est).mean())
                        eps_eff = max(eps_normalized, eps_eff * 0.5)
                else:
                    eps_eff = eps_eff * 0.85  # conservative cyclical discount

            # Compute models based on sector flags
            dcf_val    = compute_dcf_valuation(eps_eff, eps_growth) if val_method["use_dcf"] else 0
            pe_fair    = compute_pe_valuation(eps_eff, sector)       if val_method["use_pe"]  else 0
            pb_fair    = compute_pb_valuation(bvps_eff, roe_eff / 100 if roe_eff > 1 else roe_eff)
            graham_val = compute_graham_value(eps_eff, bvps_eff)     if val_method["use_graham"] else 0
            ddm_val    = 0
            if val_method["use_ddm"]:
                ddm_val = compute_ddm_valuation(eps_eff * 0.35, roe_eff / 100 if roe_eff > 1 else roe_eff)

            if val_method["use_ddm"]:
                fair_val = aggregate_fair_value(ddm_val, 0, pb_fair, 0, weights=(0.55, 0, 0.45, 0))
            else:
                fair_val = aggregate_fair_value(dcf_val, pe_fair, pb_fair, graham_val)

            upside_pct = ((fair_val - current_price) / current_price * 100
                          if fair_val > 0 and current_price > 0 else 0)
            tech_fv    = ohlc_ana.get("tech_fair_value", 0) if ohlc_ok else 0

            st.session_state["_profiler_fair_val"]    = fair_val
            st.session_state["_profiler_upside"]      = upside_pct
            st.session_state["_profiler_eps_eff"]     = eps_eff
            st.session_state["_profiler_bvps_eff"]    = bvps_eff
            st.session_state["_profiler_eps_growth"]   = eps_growth
            st.session_state["_profiler_current_price"]= current_price

            # ENH-20: Method badge
            mc = ("#4e9af1" if val_method["use_ddm"] else
                  "#f1a84e" if val_method["normalize_eps"] else
                  "#ff5500" if not val_method["use_dcf"] and not val_method["use_ddm"] else "#88cc44")
            st.markdown(f"<span style='background:{mc}22;border:1px solid {mc};border-radius:6px;"
                        f"padding:4px 10px;font-size:12px;color:{mc}'>📐 {val_method['method_label']}</span>",
                        unsafe_allow_html=True)
            if val_method.get("warning"):
                st.error(val_method["warning"])
            if val_method.get("note"):
                st.info(val_method["note"])

            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            with mc1: st.metric(L["sp_current_price"], f"{current_price:,.0f}")
            with mc2: st.metric(L["sp_fair_value"],    f"{fair_val:,.0f}" if fair_val > 0 else "–")
            with mc3:
                delta_s = f"{upside_pct:+.1f}%" if fair_val > 0 else "–"
                st.metric(L["sp_upside"], delta_s, delta=delta_s if fair_val > 0 else None)
            with mc4: st.metric("EPS (đ)", f"{eps_eff:,.0f}" if eps_eff > 0 else "–")
            with mc5: st.metric("BVPS (đ)", f"{bvps_eff:,.0f}" if bvps_eff > 0 else "–")

            if eps == 0:
                st.caption("ℹ️ EPS/BVPS ước tính từ giá thị trường / P/E ngành (thiếu dữ liệu tài chính).")

            # Model cards — only show active models
            if val_method["use_ddm"]:
                active = [("🏦 DDM (Banking)", ddm_val, "55%"),
                           (L["sp_pb_label"], pb_fair, "45%")]
            else:
                active = [(lbl, val, wt) for lbl, val, wt in [
                    (L["sp_dcf_label"],    dcf_val,   "35%" if val_method["use_dcf"] else None),
                    (L["sp_pe_label"],     pe_fair,   "30%" if val_method["use_pe"]  else None),
                    (L["sp_pb_label"],     pb_fair,   "20%"),
                    (L["sp_graham_label"], graham_val,"15%" if val_method["use_graham"] else None),
                ] if wt is not None]
            if tech_fv > 0:
                active.append(("📈 Technical", tech_fv, "REF"))

            vm_cols = st.columns(max(len(active), 1))
            for col, (lbl, val, wt) in zip(vm_cols, active):
                with col:
                    up = ((val - current_price) / current_price * 100) if val > 0 and current_price > 0 else 0
                    color = "#00cc44" if up > 10 else "#ff5500" if up < -10 else "#ffaa00"
                    st.markdown(f"""
<div style="background:#1a1f2e;border-radius:8px;padding:10px;text-align:center">
  <div style="font-size:11px;color:#888">{lbl}<br><span style="font-size:10px">Weight {wt}</span></div>
  <div style="font-size:20px;font-weight:bold;color:#fff">{f'{val:,.0f}' if val > 0 else 'N/A'}</div>
  <div style="font-size:13px;color:{color}">{f'{up:+.1f}%' if val > 0 else '–'}</div>
</div>""", unsafe_allow_html=True)

            st.markdown("---")
            # Bar chart: only include non-zero models
            _bar_data = [(nm, vl, cl) for nm, vl, cl in [
                ("DDM",     ddm_val,       "#4e9af1"),
                ("DCF",     dcf_val,       "#5599ff"),
                ("P/E",     pe_fair,       "#f1a84e"),
                ("P/B",     pb_fair,       "#a84ef1"),
                ("Graham",  graham_val,    "#4ef1a8"),
                ("Weighted",fair_val,      "#ffffff"),
                ("Tech",    tech_fv,       "#ff9922"),
                ("Current", current_price, "#f1f14e"),
            ] if vl > 0]
            fig_val = go.Figure(go.Bar(
                x=[n for n,v,c in _bar_data], y=[v for n,v,c in _bar_data],
                marker_color=[c for n,v,c in _bar_data],
                text=[f"{v:,.0f}" for n,v,c in _bar_data], textposition="outside"))
            fig_val.add_hline(y=current_price, line_dash="dash", line_color="#f1f14e",
                              annotation_text="Current", annotation_position="top right")
            fig_val.update_layout(
                title="📊 " + ("So sánh mô hình định giá (VNĐ/CP)" if is_vi
                                else "Valuation Model Comparison (VND/share)"),
                height=340, template="plotly_dark", yaxis_title="VNĐ",
                margin=dict(t=50,b=30,l=20,r=20))
            st.plotly_chart(fig_val, width="stretch")

            # Adjustable assumptions expander
            if val_method["use_dcf"] and eps_eff > 0:
                with st.expander("⚙️ " + ("Điều chỉnh DCF" if is_vi else "Adjust DCF Assumptions")):
                    cg, cd, ctg = st.columns(3)
                    with cg:  g_pct  = st.slider("EPS Growth %", -20, 40, int(eps_growth*100), key="dcf_g") / 100
                    with cd:  d_pct  = st.slider("Discount Rate %", 8, 20, 12, key="dcf_d") / 100
                    with ctg: tg_pct = st.slider("Terminal Growth %", 2, 8, 5, key="dcf_tg") / 100
                    custom_dcf = compute_dcf_valuation(eps_eff, g_pct, d_pct, tg_pct)
                    if custom_dcf > 0:
                        st.metric("Custom DCF", f"{custom_dcf:,.0f} VNĐ",
                                  delta=f"{(custom_dcf-current_price)/current_price*100:+.1f}%"
                                  if current_price > 0 else None)
            elif val_method["use_ddm"]:
                with st.expander("⚙️ " + ("Điều chỉnh DDM" if is_vi else "Adjust DDM Assumptions")):
                    cp1, cp2, cp3 = st.columns(3)
                    with cp1: dps_inp = st.number_input("DPS (đ)", value=float(max(0, eps_eff*0.35)), step=100.0, key="ddm_dps")
                    with cp2: roe_inp = st.slider("ROE %", 5, 35, int(roe_eff), key="ddm_roe") / 100
                    with cp3: ke_inp  = st.slider("Ke %", 8, 18, 12, key="ddm_ke") / 100
                    custom_ddm = compute_ddm_valuation(dps_inp, roe_inp, cost_of_equity=ke_inp)
                    if custom_ddm > 0:
                        st.metric("Custom DDM", f"{custom_ddm:,.0f} VNĐ",
                                  delta=f"{(custom_ddm-current_price)/current_price*100:+.1f}%"
                                  if current_price > 0 else None)
    # ════════════ S5: RISK ANALYSIS ════════════
    with s5:
        # Build scoring ratio df from best available source
        scoring_ratio = ratio_raw if tcbs_ok else vnd_ratios

        risk_scores = score_fundamental_risk(scoring_ratio, income_raw, balance_raw)

        # Override with OHLC-derived risk when fundamentals absent
        if not tcbs_ok and not vnd_ok and ohlc_ok:
            risk_scores["valuation"]   = max(1.0, min(10.0, (1 - ohlc_ana["price_percentile"]) * 10))
            risk_scores["growth"]      = max(1.0, min(10.0, 5 - ohlc_ana["ret3m"] * 10))
            risk_scores["debt"]        = 5.0  # unknown without balance sheet
            risk_scores["liquidity"]   = 5.0
            risk_scores["profitability"] = max(1.0, min(10.0, 10 - ohlc_ana["tech_score"] / 10))

        # Add volatility risk dimension (extra)
        if ohlc_ok:
            risk_scores["volatility"] = max(1.0, min(10.0, ohlc_ana["volatility"] * 20))

        st.session_state["_profiler_risk"] = risk_scores

        risk_labels_vi = {
            "debt":          L["sp_risk_debt"],
            "liquidity":     L["sp_risk_liq"],
            "profitability": L["sp_risk_profit"],
            "growth":        L["sp_risk_growth"],
            "valuation":     L["sp_risk_valuation"],
        }
        risk_labels_en = {
            "debt": "Debt Risk", "liquidity": "Liquidity Risk",
            "profitability": "Profitability Risk", "growth": "Growth Risk",
            "valuation": "Valuation Risk",
        }
        if ohlc_ok and "volatility" in risk_scores:
            risk_labels_vi["volatility"] = "Rủi ro Biến động"
            risk_labels_en["volatility"] = "Volatility Risk"

        rl = risk_labels_vi if is_vi else risk_labels_en

        # Risk meter cards
        cols_r = st.columns(len(rl))
        for i, (key, label) in enumerate(rl.items()):
            score = risk_scores.get(key, 5.0)
            color = "#00cc44" if score <= 3 else "#ffaa00" if score <= 6 else "#ff4444"
            risk_txt = L["risk_low"] if score <= 3 else (L["risk_med"] if score <= 6 else L["risk_high"])
            with cols_r[i]:
                st.markdown(f"""
<div style="background:#1a1f2e;border-radius:8px;padding:12px;text-align:center">
  <div style="font-size:11px;color:#888">{label}</div>
  <div style="font-size:26px;font-weight:bold;color:{color}">{score:.0f}/10</div>
  <div style="font-size:11px;color:{color}">{risk_txt}</div>
</div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Radar chart
        categories = list(rl.values())
        values     = [risk_scores.get(k, 5.0) for k in rl.keys()]
        val_closed = values + [values[0]]
        cat_closed = categories + [categories[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=val_closed, theta=cat_closed, fill="toself",
            fillcolor="rgba(255,80,80,0.2)",
            line=dict(color="#ff5050", width=2), name="Risk Score"))
        fig_radar.add_trace(go.Scatterpolar(
            r=[3] * len(val_closed), theta=cat_closed,
            line=dict(color="#00cc44", width=1, dash="dash"),
            name="Safe Zone", fill="none"))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 10]),
                       angularaxis=dict(tickfont=dict(size=11))),
            title="⚠️ " + ("Biểu đồ Rủi Ro" if is_vi else "Risk Radar"),
            height=350, template="plotly_dark",
            legend=dict(orientation="h", y=-0.1),
            margin=dict(t=50,b=50,l=30,r=30))
        st.plotly_chart(fig_radar, width="stretch")

        # Data source caveat
        if not tcbs_ok and not vnd_ok:
            st.info("ℹ️ " + ("Điểm rủi ro ước tính từ phân tích kỹ thuật OHLC (thiếu dữ liệu BCTC). SSI Finance-Indicator cũng được kiểm tra nhưng có thể không có đủ dữ liệu." if is_vi
                              else "Risk scores estimated from technical (OHLC) analysis due to missing financial statements."))

        # Risk narrative
        st.markdown("### 📝 " + ("Phân tích chi tiết" if is_vi else "Detailed Risk Analysis"))
        risk_narratives = {
            "debt": {
                "vi": {1: "✅ Cấu trúc vốn an toàn.", 5: "⚠️ Nợ ở mức trung bình.", 9: "❌ Đòn bẩy tài chính cao, rủi ro lãi suất."},
                "en": {1: "✅ Safe capital structure.", 5: "⚠️ Moderate leverage.", 9: "❌ High leverage, interest rate risk."},
            },
            "liquidity": {
                "vi": {1: "✅ Thanh khoản tốt.", 5: "⚠️ Thanh khoản trung bình.", 9: "❌ Thanh khoản kém, nguy cơ vỡ nợ ngắn hạn."},
                "en": {1: "✅ Good short-term liquidity.", 5: "⚠️ Moderate liquidity.", 9: "❌ Poor liquidity, short-term default risk."},
            },
            "profitability": {
                "vi": {1: "✅ Sinh lời xuất sắc.", 5: "⚠️ Sinh lời ở mức trung bình.", 9: "❌ Biên lợi nhuận thấp hoặc thua lỗ."},
                "en": {1: "✅ Excellent profitability.", 5: "⚠️ Average profitability.", 9: "❌ Low or negative margins."},
            },
            "growth": {
                "vi": {1: "✅ Tăng trưởng mạnh và bền vững.", 5: "⚠️ Tăng trưởng ổn định.", 9: "❌ Suy giảm doanh thu/lợi nhuận."},
                "en": {1: "✅ Strong sustainable growth.", 5: "⚠️ Steady growth.", 9: "❌ Declining revenue/earnings."},
            },
            "valuation": {
                "vi": {1: "✅ Định giá hấp dẫn, P/E thấp.", 5: "⚠️ Định giá công bằng.", 9: "❌ Đắt, P/E cao hơn trung bình ngành."},
                "en": {1: "✅ Attractive valuation, low P/E.", 5: "⚠️ Fair valued.", 9: "❌ Expensive, P/E above sector avg."},
            },
            "volatility": {
                "vi": {1: "✅ Giá ổn định, biến động thấp.", 5: "⚠️ Biến động bình thường.", 9: "❌ Biến động cao, rủi ro ngắn hạn lớn."},
                "en": {1: "✅ Stable price, low volatility.", 5: "⚠️ Normal volatility.", 9: "❌ High volatility, significant short-term risk."},
            },
        }
        for key, label in rl.items():
            score = risk_scores.get(key, 5.0)
            narr  = risk_narratives.get(key, {})
            lang_narr = narr.get("vi" if is_vi else "en", {})
            if score <= 3:   txt = lang_narr.get(1, "")
            elif score <= 6: txt = lang_narr.get(5, "")
            else:            txt = lang_narr.get(9, "")
            if txt:
                st.markdown(f"**{label} ({score:.0f}/10):** {txt}")

    # ════════════ S6: RECOMMENDATION (v18 — Dual-Signal + Unified) ════════════
    with s6:
        fair_val   = st.session_state.get("_profiler_fair_val",      0)
        upside_pct = st.session_state.get("_profiler_upside",        0)
        risk_sc    = st.session_state.get("_profiler_risk",          risk_scores)
        current_p  = st.session_state.get("_profiler_current_price", current_price)
        tech_score = ohlc_ana.get("tech_score", None) if ohlc_ok else None

        if fair_val == 0 and ohlc_ok:
            fair_val   = ohlc_ana.get("tech_fair_value", 0)
            upside_pct = ((fair_val - current_p) / current_p * 100
                          if fair_val > 0 and current_p > 0 else 0)

        # ── Fundamental signal (Profiler)
        dxy_level = st.session_state.get("_world_dxy_level", None)  # ENH-23
        fund_composite = compute_composite_fundamental_score(risk_sc, upside_pct, tech_score,
                                                             dxy_level=dxy_level, sector=sector)
        fund_rec_key, fund_color, fund_rationale = get_recommendation(
            fund_composite, upside_pct, risk_sc, st.session_state.lang)
        fund_label = L.get(fund_rec_key, fund_rec_key)

        # ── Technical signal (same engine as Market Scanner)
        with st.spinner("🔄 " + ("Đang lấy tín hiệu kỹ thuật từ Scanner..." if is_vi
                                  else "Fetching technical signal from Scanner...")):
            scanner_sig = get_scanner_signal_for_profiler(ticker)

        tech_sig_vi = scanner_sig.get("signal_vi", "THEO DÕI")
        tech_sig_en = scanner_sig.get("signal_en", "WATCH")
        tech_label  = tech_sig_vi if is_vi else tech_sig_en
        tech_color  = scanner_sig.get("color", "#ffaa00")

        # ── Unified blended recommendation
        unified = get_unified_recommendation(
            scanner_sig, fund_composite, fund_rec_key, upside_pct, st.session_state.lang)

        # ══ SECTION A: Side-by-side dual signal cards ══
        st.markdown("### " + ("🔍 Hai góc nhìn — Một cổ phiếu" if is_vi
                               else "🔍 Two Perspectives — One Stock"))

        col_tech, col_divider, col_fund = st.columns([5, 1, 5])

        with col_tech:
            st.markdown(f"""
<div style="background:{tech_color}18;border:2px solid {tech_color};
     border-radius:10px;padding:16px;text-align:center;height:180px">
  <div style="font-size:12px;color:#aaa;margin-bottom:4px">
    📈 {'Tín hiệu Kỹ thuật' if is_vi else 'Technical Signal'}<br>
    <span style="font-size:10px;color:#888">⏱️ {'Ngắn hạn: T+2 (1–5 phiên)' if is_vi else 'Short-term: T+2 (1–5 sessions)'}</span>
  </div>
  <div style="font-size:30px;font-weight:bold;color:{tech_color};margin:8px 0">{tech_label}</div>
  <div style="font-size:12px;color:#ccc">
    RSI: <b>{scanner_sig.get('rsi', 0):.1f}</b> &nbsp;|&nbsp;
    Score: <b>{scanner_sig.get('score', 0):.0f}</b>
  </div>
  <div style="font-size:10px;color:#888;margin-top:4px">
    {'RSI + BB Bollinger + MACD + ADX + Stoch' if is_vi else 'RSI · BB Bollinger · MACD · ADX · Stoch'}
  </div>
</div>""", unsafe_allow_html=True)
            if scanner_sig.get("trigger_reasons"):
                for reason in scanner_sig["trigger_reasons"][:4]:
                    st.markdown(f"<div style='font-size:11px;color:#bbb;margin-top:3px'>• {reason}</div>",
                                unsafe_allow_html=True)

        with col_divider:
            st.markdown("""
<div style="text-align:center;padding-top:60px;font-size:22px;color:#555">
  ≠
</div>""", unsafe_allow_html=True)

        with col_fund:
            st.markdown(f"""
<div style="background:{fund_color}18;border:2px solid {fund_color};
     border-radius:10px;padding:16px;text-align:center;height:180px">
  <div style="font-size:12px;color:#aaa;margin-bottom:4px">
    📊 {'Tín hiệu Cơ bản + Định giá' if is_vi else 'Fundamental + Valuation Signal'}<br>
    <span style="font-size:10px;color:#888">📅 {'Dài hạn: 6–24 tháng' if is_vi else 'Long-term: 6–24 months'}</span>
  </div>
  <div style="font-size:30px;font-weight:bold;color:{fund_color};margin:8px 0">{fund_label}</div>
  <div style="font-size:12px;color:#ccc">
    {'Upside' if not is_vi else 'Tiềm năng'}: <b>{f'{upside_pct:+.1f}%' if fair_val > 0 else 'N/A'}</b>
    &nbsp;|&nbsp; Score: <b>{fund_composite:.0f}/100</b>
  </div>
  <div style="font-size:10px;color:#888;margin-top:4px">
    {'DCF · P/E · P/B · Graham · Risk Scoring' if not is_vi else 'DCF · P/E · P/B · Graham · Đánh giá rủi ro'}
  </div>
</div>""", unsafe_allow_html=True)
            if fund_rationale:
                for line in fund_rationale.split("\n\n")[:2]:
                    if line.strip():
                        st.markdown(f"<div style='font-size:11px;color:#bbb;margin-top:3px'>{line[:100]}</div>",
                                    unsafe_allow_html=True)

        # ══ SECTION B: Conflict explanation (only if signals diverge) ══
        if unified["conflict"]:
            st.markdown("---")
            with st.expander(f"⚡ {'Tại sao hai tín hiệu khác nhau? (Không phải lỗi — bấm để xem giải thích)' if is_vi else 'Why do the signals diverge? (Not a bug — click to see explanation)'}", expanded=True):
                # Comparison table
                if is_vi:
                    st.markdown("""
| Chiều đo | 📈 Market Scanner | 📊 Stock Profiler |
|----------|------------------|------------------|
| **Phương pháp** | Phân tích kỹ thuật thuần túy | Cơ bản + Định giá nội tại |
| **Tín hiệu** | RSI quá bán + Giá < BB Lower | DCF / P/E / P/B / Graham |
| **Chân trời thời gian** | **1–5 phiên (T+2 ngắn hạn)** | **6–24 tháng (dài hạn)** |
| **Câu hỏi trả lời** | *"Giá có thể hồi phục ngắn hạn?"* | *"Cổ phiếu có được định giá hợp lý?"* |
| **SMA50 filter** | Tắt → tín hiệu dễ kích hoạt hơn | Không áp dụng SMA50 filter |

**Cả hai tín hiệu đều hợp lệ — chúng trả lời hai câu hỏi hoàn toàn khác nhau.**

> 📌 **Ví dụ với MWG:** Cổ phiếu có thể vừa *quá bán kỹ thuật* (áp lực bán giảm, xác suất bounce ngắn hạn cao) vừa *giao dịch trên giá trị nội tại DCF/Graham* (P/E cao hơn ngưỡng ngành, không hấp dẫn để tích lũy dài hạn). Nhà đầu cơ ngắn hạn và nhà đầu tư dài hạn sẽ hành động khác nhau.
""")
                else:
                    st.markdown("""
| Dimension | 📈 Market Scanner | 📊 Stock Profiler |
|-----------|------------------|------------------|
| **Method** | Pure technical analysis | Fundamental + Intrinsic valuation |
| **Signal triggers** | RSI oversold + Price < BB Lower | DCF / P/E / P/B / Graham formula |
| **Time horizon** | **1–5 sessions (T+2 short-term)** | **6–24 months (long-term)** |
| **Question answered** | *"Can price bounce short-term?"* | *"Is the stock fairly priced?"* |
| **SMA50 filter** | Off → signal fires more easily | SMA filter not applied |

**Both signals are valid — they answer two completely different questions.**

> 📌 **Example with MWG:** The stock can simultaneously be *technically oversold* (selling pressure easing, short-term bounce probable) and *trading above its DCF/Graham intrinsic value* (P/E above sector average, unattractive for long-term accumulation). Short-term traders and long-term investors will act differently.
""")

        # ══ SECTION C: Unified blended recommendation ══
        st.markdown("---")
        st.markdown("### 🎯 " + ("Khuyến Nghị Tổng Hợp (Blended)" if is_vi else "Unified Blended Recommendation"))

        u_color = unified["color"]
        w_tech_pct = int(unified["w_tech"] * 100)
        w_fund_pct = int(unified["w_fund"] * 100)

        st.markdown(f"""
<div style="background:{u_color}22;border:3px solid {u_color};
     border-radius:12px;padding:24px;text-align:center;margin:12px 0">
  <div style="font-size:36px;font-weight:bold;color:{u_color}">{unified['label']}</div>
  <div style="font-size:14px;color:#aaa;margin-top:8px">
    {ticker} &nbsp;|&nbsp;
    {'Trọng số' if is_vi else 'Weights'}: {'Cơ bản' if is_vi else 'Fundamental'} {w_fund_pct}%
    + {'Kỹ thuật' if is_vi else 'Technical'} {w_tech_pct}%
  </div>
  <div style="font-size:12px;color:#888;margin-top:4px">{unified['quality_note']}</div>
</div>""", unsafe_allow_html=True)

        # Weight explanation
        if unified["w_tech"] > 0.4:
            note = ("⚠️ Trọng số kỹ thuật tăng vì dữ liệu tài chính cơ bản hạn chế (TCBS/VNDirect không khả dụng)."
                    if is_vi else
                    "⚠️ Technical weight increased because fundamental financial data is limited (TCBS/VNDirect unavailable).")
            st.info(note)

        # Gauge showing blended score mapped to 0–100
        blended_display = (unified["blended"] + 2) / 4 * 100  # map -2..+2 → 0..100
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=fund_composite,
            delta={"reference": 50, "valueformat": ".0f"},
            title={"text": ("Điểm Cơ Bản" if is_vi else "Fundamental Score") + " /100"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar":  {"color": fund_color},
                "steps": [
                    {"range": [0,  25], "color": "#3a0808"},
                    {"range": [25, 50], "color": "#3a2008"},
                    {"range": [50, 75], "color": "#1a3a08"},
                    {"range": [75,100], "color": "#083a20"},
                ],
                "threshold": {"line": {"color": tech_color, "width": 3},
                              "thickness": 0.75,
                              "value": min(100, max(0, scanner_sig.get("score", 0) * 5))},
            }
        ))
        fig_gauge.update_layout(height=240, template="plotly_dark",
                                 margin=dict(t=40,b=10,l=20,r=20))

        # Score breakdown table (both signals side by side)
        c_gauge, c_detail = st.columns([1, 2])
        with c_gauge:
            st.plotly_chart(fig_gauge, width="stretch")
            st.caption("🟡 Bar = Fundamental score | 🔸 Threshold = Technical score (scaled)")

        with c_detail:
            fund_pts = round(((10 - sum(risk_sc.get(k, 5) for k in
                               ["profitability","growth","debt","liquidity"]) / 4) / 10) * 60, 1)
            val_pts  = round(min(max(upside_pct / 50 * 25, 0), 25), 1)
            tech_pts = round(min(max((tech_score or 0) / 100 * 15, 0), 15), 1)

            st.markdown("**" + ("Cấu thành điểm Cơ bản:" if is_vi else "Fundamental Score Breakdown:") + "**")
            comp_df = pd.DataFrame({
                "Yếu tố" if is_vi else "Component": [
                    "🏭 " + ("Chất lượng cơ bản" if is_vi else "Fundamental Quality"),
                    "💰 " + ("Tiềm năng tăng giá" if is_vi else "Valuation Upside"),
                    "📈 " + ("Kỹ thuật (OHLC)" if is_vi else "Technical (OHLC)"),
                    "📊 TOTAL",
                ],
                "Điểm" if is_vi else "Score": [fund_pts, val_pts, tech_pts, fund_composite],
                "Max": [60, 25, 15, 100],
                "%": [f"{fund_pts/60*100:.0f}%", f"{val_pts/25*100:.0f}%",
                      f"{tech_pts/15*100:.0f}%", f"{fund_composite:.0f}%"],
            })
            show_df(comp_df)

            st.markdown("**" + ("Tín hiệu Scanner (kỹ thuật ngắn hạn):" if is_vi else "Scanner Signal (short-term technical):") + "**")
            scan_df = pd.DataFrame({
                "Chỉ số" if is_vi else "Indicator": ["RSI(14)", "BB Position", "MACD", "ADX", "Score"],
                "Giá trị" if is_vi else "Value": [
                    f"{scanner_sig.get('rsi', 0):.1f}",
                    ("Dưới BB Lower ↓" if (scanner_sig.get("price",0) < scanner_sig.get("bbl",0) and scanner_sig.get("bbl",0) > 0)
                     else "Trên BB Upper ↑" if (scanner_sig.get("price",0) > scanner_sig.get("bbu",0) and scanner_sig.get("bbu",0) > 0)
                     else "Trong dải BB"),
                    ("Bullish ↑" if (scanner_sig.get("macd") and scanner_sig.get("macd_sig") and
                                     scanner_sig["macd"] > scanner_sig["macd_sig"])
                     else "Bearish ↓"),
                    f"{scanner_sig.get('adx', 0):.1f}",
                    f"{scanner_sig.get('score', 0):.1f}",
                ],
            })
            show_df(scan_df)

        # Investment thesis (fundamental)
        if fund_rationale:
            st.markdown("---")
            st.markdown("### 📝 " + ("Luận điểm Cơ bản (Dài hạn)" if is_vi else "Fundamental Thesis (Long-term)"))
            for line in fund_rationale.split("\n\n"):
                if line.strip():
                    st.markdown(line)

        # Technical thesis (short-term)
        if ohlc_ok:
            with st.expander("📈 " + ("Chi tiết Phân tích Kỹ thuật (Ngắn hạn T+2)" if is_vi
                                       else "Technical Analysis Detail (Short-term T+2)"), expanded=False):
                tech_bullets = []
                above50 = ohlc_ana.get("above_sma50", False)
                tech_bullets.append(
                    ("✅ Giá TRÊN SMA50 → xu hướng tăng trung hạn" if above50
                     else "⚠️ Giá DƯỚI SMA50 → xu hướng giảm trung hạn") if is_vi else
                    ("✅ Price ABOVE SMA50 → medium-term uptrend" if above50
                     else "⚠️ Price BELOW SMA50 → medium-term downtrend")
                )
                if ohlc_ana.get("rsi_oversold"):
                    tech_bullets.append("✅ RSI < 35 → " + ("Vùng quá bán — bounce ngắn hạn khả thi" if is_vi else "Oversold — short-term bounce probable"))
                elif ohlc_ana.get("rsi_overbought"):
                    tech_bullets.append("⚠️ RSI > 70 → " + ("Vùng quá mua — thận trọng mua đuổi" if is_vi else "Overbought — avoid chasing"))
                else:
                    tech_bullets.append(f"➡️ RSI = {ohlc_ana.get('rsi',50):.1f} → " + ("Vùng trung tính" if is_vi else "Neutral zone"))
                if ohlc_ana.get("macd_bullish"):
                    tech_bullets.append("✅ MACD > Signal → " + ("Momentum tăng" if is_vi else "Bullish momentum"))
                else:
                    tech_bullets.append("⚠️ MACD < Signal → " + ("Momentum giảm" if is_vi else "Bearish momentum"))
                pp = ohlc_ana.get("price_percentile", 0.5)
                if pp < 0.3:
                    tech_bullets.append("✅ " + (f"Giá ở mức {pp*100:.0f}% vùng 52W — vùng giá trị thấp" if is_vi
                                                  else f"Price at {pp*100:.0f}% of 52W range — low value zone"))
                elif pp > 0.75:
                    tech_bullets.append("⚠️ " + (f"Giá ở mức {pp*100:.0f}% vùng 52W — gần đỉnh 52 tuần" if is_vi
                                                   else f"Price at {pp*100:.0f}% of 52W range — near 52W high"))
                for b in tech_bullets:
                    st.markdown(b)

                ret1m = ohlc_ana.get("ret1m", 0)
                ret3m = ohlc_ana.get("ret3m", 0)
                st.markdown(f"**{'Momentum:' if not is_vi else 'Momentum:'}** "
                             f"1M: `{ret1m*100:+.1f}%`  3M: `{ret3m*100:+.1f}%`  "
                             f"Volatility: `{ohlc_ana.get('volatility',0)*100:.1f}%`/yr")

        # News
        # ENH-26: Expert Analyst Commentary
        st.markdown("---")
        with st.expander("🔬 " + ("Phân tích Chuyên gia (SSI Research Style)" if is_vi
                                   else "Expert Analyst Commentary (SSI Research Style)"), expanded=True):
            _roa_s6  = roa   if roa   else None
            _npm_s6  = npm   if npm   else None
            _roe_s6  = roe   if roe   else None
            _expert_text = generate_expert_commentary(
                ticker=ticker, sector=sector, current_price=current_p,
                eps=st.session_state.get("_profiler_eps_eff", 0),
                pe=pe_val or 0, pb=pb_val or 0,
                roe=_roe_s6 or 0, roa=_roa_s6 or 0, npm=_npm_s6 or 0,
                ohlc_ana=ohlc_ana, fair_val=fair_val, upside_pct=upside_pct,
                risk_sc=risk_sc, composite_score=fund_composite, is_vi=is_vi,
            )
            st.markdown(_expert_text)

        all_news = ssi_news or fetch_news(ticker, n=8)
        if all_news:
            st.markdown("---")
            st.markdown("### 📰 " + ("Tin tức mới nhất" if is_vi else "Latest News"))
            for item in all_news[:6]:
                title = item.get("title","–"); url = item.get("url",""); date = item.get("date","")
                st.markdown(f"📰 **{date}** — [{title}]({url})" if url else f"📰 **{date}** — {title}")

        st.caption("⚠️ " + (
            "Khuyến nghị dựa trên phân tích định lượng tự động. Không phải tư vấn đầu tư chuyên nghiệp."
            if is_vi else
            "Recommendation based on automated quantitative analysis. Not professional financial advice."
        ))


# ══════════════════════════════════════════════════════════════
#  TABS — 12 tabs total
# ══════════════════════════════════════════════════════════════
def render_sector_heatmap():
    """ENH-28: Sector Rotation Heatmap — money flow tracking per sector."""
    is_vi = st.session_state.lang == "VI"
    st.subheader("🗺️ " + ("Bản đồ Luân chuyển Ngành" if is_vi else "Sector Rotation Heatmap"))
    st.caption("📊 " + ("Màu xanh = ngành dẫn dắt | Màu đỏ = ngành phân phối | Dữ liệu 3 mã đại diện/ngành" if is_vi
                          else "Green = leading | Red = distributing | Based on 3 representative tickers/sector"))

    SECTOR_REPS = {
        "Ngân hàng":    ["VCB","TCB","MBB"],
        "Bất động sản": ["VHM","NVL","DXG"],
        "Công nghệ":    ["FPT","CMG","VGI"],
        "Thép":         ["HPG","HSG","NKG"],
        "Dầu khí":      ["GAS","PLX","PVD"],
        "Bán lẻ":       ["MWG","PNJ","FRT"],
        "Thực phẩm":    ["VNM","MSN","SAB"],
        "Chứng khoán":  ["SSI","VCI","HCM"],
        "Điện":         ["POW","GEG","VSH"],
        "Xây dựng":     ["CTD","HBC","FCN"],
        "Dược":         ["IMP","DHG","PME"],
    }

    @st.cache_data(ttl=3600)
    def _get_sector_data(sector_name: str, rep_tickers: list):
        chgs, vols = [], []
        for t in rep_tickers:
            try:
                _df, _, _ = download_data(t, days=45, min_rows=5)
                if not _df.empty and len(_df) >= 2:
                    _df = clean_data(_df)
                    c = _df["Close"].dropna()
                    if len(c) >= 2:
                        chgs.append((float(c.iloc[-1]) - float(c.iloc[-2])) / float(c.iloc[-2]) * 100)
                    if "Volume" in _df.columns and len(_df) >= 20:
                        v5  = _df["Volume"].tail(5).mean()
                        v20 = _df["Volume"].tail(20).mean()
                        if v20 > 0: vols.append(v5 / v20)
            except Exception:
                pass
        return {
            "chg":       round(sum(chgs) / len(chgs), 3) if chgs else 0,
            "vol_ratio": round(sum(vols) / len(vols), 2) if vols else 1.0,
        }

    with st.spinner("⏳ " + ("Đang tải dữ liệu ngành..." if is_vi else "Loading sector data...")):
        rows = []
        for sector, reps in SECTOR_REPS.items():
            stats = _get_sector_data(sector, reps)
            chg = stats["chg"]; vol = stats["vol_ratio"]
            if chg > 0.5 and vol > 1.2:
                sig = "🔥 " + ("Dẫn dắt" if is_vi else "Leading")
            elif chg > 0.1:
                sig = "📈 " + ("Tăng nhẹ" if is_vi else "Mild gain")
            elif chg < -0.5 and vol > 1.2:
                sig = "💸 " + ("Phân phối" if is_vi else "Distribution")
            elif chg < -0.1:
                sig = "📉 " + ("Giảm nhẹ" if is_vi else "Mild loss")
            else:
                sig = "➡️ " + ("Đi ngang" if is_vi else "Sideways")
            rows.append({
                "Ngành" if is_vi else "Sector":  sector,
                "% Thay đổi" if is_vi else "% Change": f"{chg:+.2f}%",
                "KL/TB(20)" if is_vi else "Vol/Avg":  f"{vol:.2f}×",
                "Tín hiệu" if is_vi else "Signal": sig,
            })

    df_heat = pd.DataFrame(rows).sort_values("% Thay đổi" if is_vi else "% Change", ascending=False)

    def _style_chg(val):
        try:
            v = float(str(val).replace("%","").replace("+",""))
        except Exception:
            return ""
        if v > 1.0:  return "background-color:#002a00;color:#00ff88;font-weight:bold"
        if v > 0.1:  return "background-color:#001500;color:#88ee88"
        if v < -1.0: return "background-color:#2a0000;color:#ff4444;font-weight:bold"
        if v < -0.1: return "background-color:#150000;color:#ee8888"
        return "color:#aaaaaa"

    col_chg = "% Thay đổi" if is_vi else "% Change"
    styled = df_heat.style.applymap(_style_chg, subset=[col_chg])
    show_df(styled)

    leaders = [r["Ngành" if is_vi else "Sector"] for r in rows
               if r["Tín hiệu" if is_vi else "Signal"].startswith("🔥")]
    if leaders:
        st.success("🔥 " + ("Ngành dẫn dắt: " if is_vi else "Leading sectors: ") + ", ".join(leaders))
        st.caption("💡 " + ("Chiến lược: Ưu tiên cổ phiếu trong ngành dẫn dắt, kết hợp tín hiệu kỹ thuật."
                             if is_vi else "Strategy: Prioritize stocks in leading sectors with good technical setups."))


def render_scanner_tab():
    st.subheader("📡 " + ("Tín Hiệu Giao Dịch Tổng Hợp" if st.session_state.lang=="VI" else "Aggregated Trading Signals"))
    watch_list = load_watchlist_from_file(WATCHLIST_FILE_PATH)
    st.info(f"Watchlist: **{len(watch_list)}** tickers  |  Pipeline: **DNSE** → SSI → CafeF  |  RSI Buy<{rsi_buy_thresh} / Sell>{rsi_sell_thresh}")
    st.caption("⏱️ " + ("Tín hiệu Scanner là **kỹ thuật ngắn hạn T+2 (1–5 phiên)**. Khác với Hồ Sơ Cổ Phiếu (cơ bản dài hạn 6–24 tháng) — hai góc nhìn bổ sung nhau, không mâu thuẫn."
                         if st.session_state.lang=="VI" else
                         "Scanner signals are **short-term technical T+2 (1–5 sessions)**. Different from Stock Profiler (long-term fundamental 6–24 months) — complementary views, not contradictions."))

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

    # ENH-28: Sector Heatmap at bottom of Scanner tab
    with st.expander("🗺️ " + ("Bản đồ Luân chuyển Ngành (Sector Rotation)" if st.session_state.lang=="VI"
                                else "Sector Rotation Heatmap"), expanded=False):
        render_sector_heatmap()


def render_top_buy_tab():
    hdr = "Top Cổ Phiếu Bắt Đáy" if st.session_state.lang=="VI" else "Top Oversold Stock Screener"
    st.subheader(f"🏆 {hdr}")
    st.caption(f"Scanning **{len(MARKET_SCAN_LIST)}** tickers  |  DNSE → SSI → CafeF")
    st.caption("⏱️ " + ("Tín hiệu **kỹ thuật ngắn hạn T+2**. Dùng tab 🧬 Hồ Sơ Cổ Phiếu để phân tích dài hạn cơ bản."
                         if st.session_state.lang=="VI" else
                         "**Short-term technical T+2** signals. Use the 🧬 Stock Profiler tab for long-term fundamental analysis."))

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
        st.plotly_chart(fig, width="stretch")

        render_fundamental_section(st.session_state.symbol)

        # ══════════════════════════════════════════════════════
        # ENH-21: POSITION SIZING CALCULATOR
        # ENH-22: SWING TRADE SETUP GENERATOR
        # Research: Swing Trading Vietnam EN + Strategy 2026
        # ══════════════════════════════════════════════════════
        st.markdown("---")
        _is_vi_da = st.session_state.lang == "VI"
        _da_tabs = st.tabs([
            "💰 " + ("Tính Vị Thế" if _is_vi_da else "Position Sizing"),
            "🎯 " + ("Thiết Lập Swing" if _is_vi_da else "Swing Setup"),
        ])

        # ── ENH-21: Position Sizing Calculator ──────────────────────────
        with _da_tabs[0]:
            st.subheader("💰 " + ("Tính Khối Lượng — Kelly Criterion T+2.5" if _is_vi_da
                                    else "Position Sizing — Kelly Criterion T+2.5"))
            st.caption("📚 " + ("Quy tắc quản trị vốn: Rủi ro ≤ 2% mỗi lệnh, R:R ≥ 2×" if _is_vi_da
                                  else "Capital rules: Max 2% risk/trade, R:R ≥ 2×"))
            _ps1, _ps2 = st.columns(2)
            _extra  = st.session_state.get("audit_extra", {})
            _close  = _extra.get("close", 50000)
            _atr_ps = _extra.get("atr", 0) or (_close * 0.02)
            with _ps1:
                _capital = st.number_input("💵 " + ("Tổng vốn (VNĐ)" if _is_vi_da else "Capital (VND)"),
                    min_value=1_000_000, value=100_000_000, step=10_000_000, format="%d", key="ps_capital")
                _risk_pct = st.slider("⚠️ " + ("Rủi ro/lệnh (%)" if _is_vi_da else "Risk per trade (%)"),
                    0.5, 5.0, 2.0, 0.5, key="ps_risk") / 100
                _entry = st.number_input("📍 " + ("Giá vào lệnh" if _is_vi_da else "Entry Price"),
                    min_value=1000, value=int(_close), step=100, format="%d", key="ps_entry")
            with _ps2:
                _def_sl = max(1000, int(_entry - 1.5 * _atr_ps))
                _sl = st.number_input("🛑 " + ("Giá cắt lỗ" if _is_vi_da else "Stop Loss"),
                    min_value=1000, value=_def_sl, step=100, format="%d", key="ps_sl")
                _tp1_pct = st.slider("🎯 TP1 (%)", 3, 30, 10, key="ps_tp1")
                _tp2_pct = st.slider("🎯 TP2 (%)", 5, 50, 20, key="ps_tp2")
            if _entry > _sl > 0:
                _rps   = _entry - _sl
                _ra    = _capital * _risk_pct
                _lots  = max(1, round(_ra / _rps / 100)) * 100
                _deploy= _lots * _entry
                _cpct  = _deploy / _capital * 100
                _tp1p  = _entry * (1 + _tp1_pct / 100)
                _tp2p  = _entry * (1 + _tp2_pct / 100)
                _rr1   = (_tp1p - _entry) / _rps
                _rr2   = (_tp2p - _entry) / _rps
                _rrc1  = "#00cc44" if _rr1 >= 2 else "#ff5500"
                _rrc2  = "#00cc44" if _rr2 >= 3 else "#ffaa00"
                st.markdown(f"""
<div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:14px;margin-top:10px">
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px">
    <div style="text-align:center">
      <div style="color:#8b949e;font-size:11px">{"Số lượng CP" if _is_vi_da else "Shares"}</div>
      <div style="color:#58a6ff;font-size:22px;font-weight:bold">{_lots:,}</div>
    </div>
    <div style="text-align:center">
      <div style="color:#8b949e;font-size:11px">{"Vốn triển khai" if _is_vi_da else "Capital Deploy"}</div>
      <div style="color:#f0883e;font-size:22px;font-weight:bold">{_deploy/1e6:.1f}M</div>
      <div style="color:#8b949e;font-size:10px">({_cpct:.1f}%)</div>
    </div>
    <div style="text-align:center">
      <div style="color:#8b949e;font-size:11px">{"Lỗ tối đa" if _is_vi_da else "Max Loss"}</div>
      <div style="color:#f85149;font-size:22px;font-weight:bold">-{_ra/1e6:.2f}M</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <div style="background:#0d1f0d;border-radius:6px;padding:8px;text-align:center">
      <div style="color:#8b949e;font-size:11px">TP1 {_tp1_pct}% → {_tp1p:,.0f}đ</div>
      <div style="color:#3fb950;font-size:18px;font-weight:bold">+{(_tp1p-_entry)*_lots/1e6:.2f}M</div>
      <div style="color:{_rrc1};font-size:12px">R:R = {_rr1:.1f}× {"✅" if _rr1>=2 else "⚠️"}</div>
    </div>
    <div style="background:#0d1f0d;border-radius:6px;padding:8px;text-align:center">
      <div style="color:#8b949e;font-size:11px">TP2 {_tp2_pct}% → {_tp2p:,.0f}đ</div>
      <div style="color:#3fb950;font-size:18px;font-weight:bold">+{(_tp2p-_entry)*_lots/1e6:.2f}M</div>
      <div style="color:{_rrc2};font-size:12px">R:R = {_rr2:.1f}× {"✅" if _rr2>=3 else "⚠️"}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
                if _rr1 < 2.0:
                    st.warning("⚠️ " + ("R:R < 2× tại TP1. Nghiên cứu khuyến nghị chỉ vào lệnh khi R:R ≥ 2×." if _is_vi_da
                                         else "R:R < 2× at TP1. Research recommends only trading when R:R ≥ 2×."))
                if _cpct > 30:
                    st.warning("⚠️ " + ("Vị thế > 30% vốn — rủi ro tập trung cao trong T+2.5. Cân nhắc chia 40/40/20." if _is_vi_da
                                         else "Position > 30% capital — high concentration risk in T+2.5. Consider splitting 40/40/20."))
            else:
                st.info("ℹ️ " + ("Nhập giá vào lệnh > giá cắt lỗ để tính toán." if _is_vi_da
                                   else "Entry price must be greater than Stop Loss to calculate."))

        # ── ENH-22: Swing Trade Setup Generator ─────────────────────────
        with _da_tabs[1]:
            st.subheader("🎯 " + ("Thiết Lập Giao Dịch Swing" if _is_vi_da else "Swing Trade Setup Generator"))
            st.caption("📚 " + ("6 chiến lược từ nghiên cứu Swing Trading Việt Nam 2026" if _is_vi_da
                                  else "Based on 6 strategies from Vietnam Swing Trading Research 2026"))
            _sym_da  = st.session_state.symbol
            _extra2  = st.session_state.get("audit_extra", {})
            _cv      = _extra2.get("close", 0)
            _bbl2    = _extra2.get("bbl", 0)
            _bbu2    = _extra2.get("bbu", 0)
            _s20_2   = _extra2.get("s20", 0)
            _s50_2   = _extra2.get("s50", 0)
            _atr2    = _extra2.get("atr", 0) or (_cv * 0.02)
            _rsi2    = _extra2.get("rsi", 50)
            _macd2   = _extra2.get("macd", 0)
            _macds2  = _extra2.get("macd_sig", 0)
            _avgv2   = _extra2.get("avg_v", 0)
            _lastv2  = _extra2.get("last_v", 0)
            _setups  = []
            # Strategy 1: Pullback Buy in Uptrend (win rate 65-70%)
            if _s50_2 and _cv > _s50_2 and _s20_2 and abs(_cv - _s20_2) / max(_s20_2, 1) < 0.025 and 35 <= _rsi2 <= 55:
                _e = _cv; _sl_ = _e - 1.5*_atr2; _t1 = _e + 2*_atr2; _t2 = _e + 4*_atr2
                _rr_ = (_t1-_e)/max(_e-_sl_,1)
                _setups.append({"Strategy":"1️⃣ Pullback (Uptrend)","Win Rate":"65–70%",
                                 "Entry":f"{_e:,.0f}","SL":f"{_sl_:,.0f}",
                                 "TP1":f"{_t1:,.0f}","TP2":f"{_t2:,.0f}",
                                 "R:R":f"{_rr_:.1f}×","Trigger":f"Giá≈SMA20, RSI={_rsi2:.0f}"})
            # Strategy 2: Breakout with volume (win rate 55-65%)
            if _bbu2 and _cv > _bbu2 * 0.99 and _avgv2 > 0 and _lastv2 / max(_avgv2, 1) > 1.5:
                _e = _bbu2*1.005; _sl_ = _bbu2-_atr2; _t1 = _e+2.5*_atr2; _t2 = _e+5*_atr2
                _rr_ = (_t1-_e)/max(_e-_sl_,1)
                _setups.append({"Strategy":"2️⃣ Breakout (Volume Surge)","Win Rate":"55–65%",
                                 "Entry":f"{_e:,.0f}","SL":f"{_sl_:,.0f}",
                                 "TP1":f"{_t1:,.0f}","TP2":f"{_t2:,.0f}",
                                 "R:R":f"{_rr_:.1f}×","Trigger":f"Giá>BB↑, Vol={_lastv2/_avgv2:.1f}×"})
            # Strategy 3: Oversold Mean Reversion (win rate 60-70%)
            if _rsi2 < 35 and _bbl2 and _cv < _bbl2 * 1.01:
                _e = _cv; _sl_ = _cv-2*_atr2; _t1 = _bbl2+_atr2; _t2 = _s20_2 if _s20_2 else _bbl2+3*_atr2
                _rr_ = (_t1-_e)/max(_e-_sl_,1)
                _setups.append({"Strategy":"3️⃣ Oversold Reversion (RSI<35)","Win Rate":"60–70%",
                                 "Entry":f"{_e:,.0f}","SL":f"{_sl_:,.0f}",
                                 "TP1":f"{_t1:,.0f}","TP2":f"{_t2:,.0f}",
                                 "R:R":f"{_rr_:.1f}×","Trigger":f"RSI={_rsi2:.0f}, Giá<BB↓"})
            # Strategy 4: MACD Cross (win rate 50-60%)
            if _macd2 and _macds2 and _macd2 > _macds2 and _rsi2 < 65:
                _e = _cv; _sl_ = _e-1.8*_atr2; _t1 = _e+2.2*_atr2; _t2 = _e+4*_atr2
                _rr_ = (_t1-_e)/max(_e-_sl_,1)
                _setups.append({"Strategy":"4️⃣ MACD Cross + Momentum","Win Rate":"50–60%",
                                 "Entry":f"{_e:,.0f}","SL":f"{_sl_:,.0f}",
                                 "TP1":f"{_t1:,.0f}","TP2":f"{_t2:,.0f}",
                                 "R:R":f"{_rr_:.1f}×","Trigger":f"MACD cross, RSI={_rsi2:.0f}"})
            if _setups:
                st.success(f"✅ {len(_setups)} " + ("thiết lập tìm thấy cho" if _is_vi_da else "setups found for") + f" **{_sym_da}**")
                show_df(pd.DataFrame(_setups))
                st.caption("⚠️ " + ("Mức giá tính từ ATR+BB. Luôn xác nhận với biến động thực. R:R ≥ 2× là bắt buộc." if _is_vi_da
                                      else "Prices from ATR+BB. Confirm with live price action. R:R ≥ 2× is mandatory."))
                with st.expander("📋 " + ("Hệ thống Xác nhận 3 lớp" if _is_vi_da else "Triple Confirmation Checklist")):
                    _checklist_vi = (
                        "**1. Xu hướng:** VN-Index > SMA50? Cổ phiếu > SMA50?\n\n"
                        "**2. Động lượng:** RSI tăng từ vùng quá bán? MACD cắt lên?\n\n"
                        "**3. Khối lượng:** Volume ≥ 150% trung bình 20 phiên?\n\n"
                        "**Quy tắc vàng:** Chỉ vào lệnh khi R:R ≥ 2×."
                    )
                    _checklist_en = (
                        "**1. Trend:** VN-Index > SMA50? Stock > SMA50?\n\n"
                        "**2. Momentum:** RSI rising from oversold? MACD crossing up?\n\n"
                        "**3. Volume:** Volume ≥ 150% of 20-session average?\n\n"
                        "**Golden Rule:** Only enter when R:R ≥ 2×."
                    )
                    st.markdown(_checklist_vi if _is_vi_da else _checklist_en)
            else:
                st.info("ℹ️ " + (f"Không có thiết lập swing rõ ràng cho **{_sym_da}** hiện tại. "
                                   "Chờ tín hiệu xác nhận (RSI, BB, Volume)." if _is_vi_da else
                                   f"No clear swing setups for **{_sym_da}** currently. "
                                   "Wait for confirmation (RSI, BB, Volume)."))


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
                st.plotly_chart(fig_eq, width="stretch")
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
            st.plotly_chart(fig_ml, width="stretch")

            results_rows = []
            for nm,(fc,w) in model_dict.items():
                fc_arr=fc.get("p50") if isinstance(fc,dict) else fc
                if fc_arr is not None:
                    fp_val=float(fc_arr[-1]); pct=(fp_val/last_price-1)*100
                    g,d=MODEL_META.get(nm,("?","?"))
                    results_rows.append({"Model":nm,"Group":g,"Wt%":f"{int(w*100)}%",
                        f"Target+{n_days}d":f"{fp_val:,.0f}","Δ%":f"{pct:+.2f}%","Notes":d})
            if ensemble_fc is not None:
                ev=float(ensemble_fc[-1]); ep=(ev/last_price-1)*100
                results_rows.append({"Model":"📊 Ensemble","Group":"Weighted","Wt%":"100%",
                    f"Target+{n_days}d":f"{ev:,.0f}","Δ%":f"{ep:+.2f}%","Notes":"Optimised for VN market dynamics"})
            # Use string dtype explicitly to avoid pyarrow conversion error
            df_res = pd.DataFrame(results_rows)
            for col in df_res.columns:
                if df_res[col].dtype == object:
                    df_res[col] = df_res[col].astype(str)
            show_df(df_res)

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
                res_df=pd.DataFrame([{"Model":k,**{kk:str(vv) for kk,vv in v.items() if kk!="all_values"}}
                                      for k,v in rec.get("results",{}).items() if isinstance(v,dict)])
                if "weight" in res_df.columns: res_df.rename(columns={"weight":"Wt%"},inplace=True)
                # Ensure all columns are string to avoid pyarrow type errors
                for col in res_df.columns:
                    if res_df[col].dtype == object:
                        res_df[col] = res_df[col].astype(str)
                show_df(res_df,key=f"hist_detail_{idx}")
                if ens.get("all_values") and rec.get("forecast_dates"):
                    if st.button("🔄 Replay chart",key=f"replay_{idx}"):
                        fig_r=go.Figure()
                        fig_r.add_trace(go.Scatter(x=rec["forecast_dates"],y=ens["all_values"],
                            mode="lines+markers",name="Ensemble",line=dict(color="orange",width=2)))
                        fig_r.add_hline(y=lp,line_dash="dash",line_color="gray",annotation_text=f"Forecast price: {lp:,.0f}")
                        fig_r.update_layout(title=f"Replay: {sel_ml} @ {ts}",yaxis_title="Price (VND)",template="plotly_dark",height=320)
                        st.plotly_chart(fig_r,width="stretch")
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
        if fg: st.plotly_chart(fg, width="stretch")
        fo = mini_chart(oil_df,  f"🛢️ WTI Oil (USD/bbl) — last: {oil_last:,.1f}" if oil_last else "🛢️ WTI Oil", "#ff6347")
        if fo: st.plotly_chart(fo, width="stretch")
        fd = mini_chart(dxy_df,  f"💵 USD Index DXY — last: {dxy_last:,.2f}" if dxy_last else "💵 DXY", "#00bfff")
        if fd: st.plotly_chart(fd, width="stretch")

    with c_right:
        fs5 = mini_chart(sp500_df, f"📈 S&P500 — last: {sp500_last:,.0f}" if sp500_last else "📈 S&P500", "#00cc66")
        if fs5: st.plotly_chart(fs5, width="stretch")
        fg2 = mini_chart(gas_df, f"⛽ Natural Gas (USD/MMBtu) — last: {gas_last:,.2f}" if gas_last else "⛽ Natural Gas", "#bb7eff")
        if fg2: st.plotly_chart(fg2, width="stretch")
        fv = mini_chart(vni_df,  f"📊 VN-Index — last: {vni_last:,.2f}" if vni_last else "📊 VN-Index", "#7eb8ff")
        if fv: st.plotly_chart(fv, width="stretch")

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
        st.plotly_chart(fig_fed, width="stretch")
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
    # ENH-23: store current DXY level so Profiler can apply macro overlay
    if dxy_last is not None and dxy_last > 0:
        st.session_state["_world_dxy_level"] = float(dxy_last)
        if float(dxy_last) > 106:
            st.warning(f"⚠️ DXY = **{dxy_last:.1f}** > 106 — " + (
                "Ứng dụng tự động trừ 5–10 điểm Composite Score cho ngành thâm dụng nhập khẩu "
                "(Thép, Dầu khí, Hàng không, Bán lẻ). Xem tab Hồ Sơ Cổ Phiếu."
                if lang8 == "VI" else
                "App auto-deducts 5–10 pts from Composite Score for import-heavy sectors "
                "(Steel, Oil, Airlines, Retail). See Stock Profiler tab."))
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
                st.plotly_chart(fig_corr, width="stretch")
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
    st.caption("v17.0 — Tests each source individually for FPT (HOSE), REE (HOSE), OIL (UPCOM). DNSE endpoint fix verified. Full stack traces written to error_log.txt.")

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
                    df_ind = calculate_indicators(clean_data(df_fpt))
                    results.append({"Test":"FPT Indicators","Status":"✅ PASS" if "RSI" in df_ind.columns else "❌ FAIL",
                        "Detail":f"RSI={df_ind['RSI'].iloc[-1]:.1f}, ADX={df_ind['ADX'].iloc[-1]:.1f}"})
            except Exception as e:
                results.append({"Test":"FPT Full Pipeline","Status":"❌ ERROR","Detail":f"{e} | {str(traceback.format_exc())[:150]}"})

        # ── Test 0b: REE — full pipeline test (HOSE ticker)
        with st.spinner("Testing REE full pipeline (HOSE)..."):
            try:
                df_ree, src_ree, err_ree = download_data("REE", 180, min_rows=20)
                ok = len(df_ree) >= 20
                results.append({"Test":"REE Full Pipeline (HOSE)","Status":"✅ PASS" if ok else "❌ FAIL",
                    "Detail":f"{len(df_ree)} rows via {src_ree}, close={df_ree['Close'].iloc[-1]:,.0f}" if ok else f"Failed: {err_ree}"})
                if ok:
                    df_ree_ind = calculate_indicators(clean_data(df_ree))
                    results.append({"Test":"REE Indicators","Status":"✅ PASS" if "RSI" in df_ree_ind.columns else "❌ FAIL",
                        "Detail":f"RSI={df_ree_ind['RSI'].iloc[-1]:.1f}"})
            except Exception as e:
                results.append({"Test":"REE Full Pipeline","Status":"❌ ERROR","Detail":f"{e} | {str(traceback.format_exc())[:150]}"})

        # ── Test 0c: OIL — full pipeline test (UPCOM ticker)
        with st.spinner("Testing OIL full pipeline (UPCOM)..."):
            try:
                df_oil, src_oil, err_oil = download_data("OIL", 180, min_rows=20)
                ok = len(df_oil) >= 20
                results.append({"Test":"OIL Full Pipeline (UPCOM)","Status":"✅ PASS" if ok else "❌ FAIL",
                    "Detail":f"{len(df_oil)} rows via {src_oil}, close={df_oil['Close'].iloc[-1]:,.0f}" if ok else f"Failed: {err_oil}"})
            except Exception as e:
                results.append({"Test":"OIL Full Pipeline (UPCOM)","Status":"❌ ERROR","Detail":f"{e} | {str(traceback.format_exc())[:150]}"})

        # ── Test 1: DNSE connectivity (FIX-16: api.dnse.com.vn)
        with st.spinner("Testing DNSE api.dnse.com.vn (FPT + REE + OIL)..."):
            for sym_t, exch_t in [("FPT","HOSE"), ("REE","HOSE"), ("OIL","UPCOM")]:
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

        # ── Test 7: CafeF Fundamentals (ENH-11)
        with st.spinner("Testing CafeF fundamental APIs (FPT + REE)..."):
            for sym_t in ["FPT", "REE"]:
                try:
                    cf_r = fetch_cafef_key_ratios(sym_t)
                    ok = bool(cf_r.get("eps") or cf_r.get("pe"))
                    results.append({"Test":f"CafeF ChiSoTaiChinh ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"EPS={cf_r.get('eps','?')} P/E={cf_r.get('pe','?')} P/B={cf_r.get('pb','?')}" if ok else "No ratio data"})
                except Exception as e:
                    results.append({"Test":f"CafeF ChiSoTaiChinh ({sym_t})","Status":"❌ ERROR","Detail":str(e)})
            for sym_t in ["FPT", "OIL"]:
                try:
                    cf_p = fetch_cafef_price(sym_t)
                    ok = cf_p.get("price", 0) > 0
                    results.append({"Test":f"CafeF PriceRT ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"Price={cf_p.get('price',0):,.0f}, {cf_p.get('pct_change',0):+.2f}%" if ok else "No price data"})
                except Exception as e:
                    results.append({"Test":f"CafeF PriceRT ({sym_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 8: DNSE OHLC Analysis (ENH-13)
        with st.spinner("Testing DNSE OHLC Analysis (FPT + REE + OIL)..."):
            for sym_t in ["FPT", "REE", "OIL"]:
                try:
                    ana = fetch_dnse_ohlc_analysis(sym_t)
                    ok = "error" not in ana and ana.get("n_rows", 0) >= 20
                    results.append({"Test":f"DNSE OHLC Analysis ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{ana.get('n_rows',0)} rows, RSI={ana.get('rsi',0):.1f}, TechScore={ana.get('tech_score',0):.0f}/100" if ok else ana.get("error","Failed")})
                except Exception as e:
                    results.append({"Test":f"DNSE OHLC Analysis ({sym_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 9: Stock Profiler Recommendation (FPT, REE, OIL)
        with st.spinner("Testing Stock Profiler recommendation engine (FPT + REE + OIL)..."):
            for sym_t in ["FPT", "REE", "OIL"]:
                try:
                    ana = fetch_dnse_ohlc_analysis(sym_t)
                    if "error" in ana:
                        results.append({"Test":f"Profiler Recommendation ({sym_t})","Status":"❌ FAIL","Detail":"No OHLC data"})
                        continue
                    cf_r = fetch_cafef_key_ratios(sym_t)
                    cf_p = fetch_cafef_price(sym_t)
                    price = cf_p.get("price", ana.get("price", 0))
                    eps   = cf_r.get("eps", ana.get("implied_eps", price / 15))
                    bvps  = cf_r.get("bvps", ana.get("implied_bvps", price * 0.6))
                    sector = get_sector(sym_t)
                    dcf  = compute_dcf_valuation(eps, 0.10)
                    pe_f = compute_pe_valuation(eps, sector)
                    pb_f = compute_pb_valuation(bvps, 0.12)
                    gval = compute_graham_value(eps, bvps)
                    fv   = aggregate_fair_value(dcf, pe_f, pb_f, gval)
                    if fv == 0: fv = ana.get("tech_fair_value", 0)
                    upside = (fv - price) / price * 100 if fv > 0 and price > 0 else 0
                    mock_risk = {"debt":5,"liquidity":5,"profitability":5,"growth":5,"valuation":5}
                    composite = compute_composite_fundamental_score(mock_risk, upside, ana.get("tech_score"))
                    rec_key, _, _ = get_recommendation(composite, upside, mock_risk, "VI")
                    rec_label = _LANG_VI.get(rec_key, rec_key)
                    ok = composite > 0
                    results.append({"Test":f"Profiler Rec. ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"Price={price:,.0f} FV={fv:,.0f} Upside={upside:+.1f}% Score={composite:.0f} → {rec_label}"})
                except Exception as e:
                    results.append({"Test":f"Profiler Rec. ({sym_t})","Status":"❌ ERROR","Detail":str(e)[:120]})

        # ── Test 10: ML libs
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

### v20.0 — 2026-03-09 · FIXES + RESEARCH-BACKED IMPROVEMENTS

**Bugs fixed from error_log.txt:**

| ID | Fix |
|----|-----|
| FIX-20 | SSI 24-row UPCOM: per-source `min_rows` — SSI/yFinance accept ≥20 rows. Fixes IDC, OIL, PME, LTG, VKC, FCN etc. |
| FIX-21 | VNDirect timeout 12s→6s; UPCOM tickers auto-skip VNDirect (eliminated 162 timeouts in log) |

**Research-backed improvements (Swing Trading VN + Valuation Proposal + Strategy 2026):**

| ID | Feature |
|----|---------|
| ENH-19 | Multi-ticker Stock Profiler — separate tickers by ";", get comparison table + per-ticker deep dive |
| ENH-20 | Sector-Aware Valuation: Banking=P/B+DDM, Cyclicals=normalized 5Y EPS, NegEPS→disable DCF+PE |
| ENH-21 | Position Sizing Calculator (Kelly Criterion, T+2.5 lots, R:R) in Deep Audit tab |
| ENH-22 | Swing Trade Setup Generator (4 strategies, auto Entry/SL/TP1/TP2/R:R) in Deep Audit tab |
| ENH-23 | DXY Macro Overlay: DXY>106 auto-deducts 5–10pts Composite Score for import-heavy sectors |
| ENH-24 | SECTOR_PE_BENCH updated from SSI Research/VCSC (Tech: 25→28×, Steel: 8→9×, RE: 18→20×) |

---

### v18.0 — 2026-03-08 · SIGNAL DIVERGENCE RESOLVED

**Root Cause Analysis — Scanner BUY vs Profiler SELL for same ticker (e.g. MWG)**

| Aspect | Market Scanner | Stock Profiler |
|--------|---------------|----------------|
| Method | Pure technical | Fundamental + DCF/Graham valuation |
| Horizon | **Short-term T+2 (1–5 sessions)** | **Long-term 6–24 months** |
| Signal triggers | RSI < 35 + Price < BB Lower | Composite score from risk + upside |
| SMA50 filter OFF | More signals fire (trend ignored) | Not affected |
| Question answered | "Will price bounce in 1–5 days?" | "Is this stock fairly valued?" |

**Both can be simultaneously correct — they serve different investment horizons.**

| Fix/ENH ID | Component | Change |
|-----------|-----------|--------|
| FIX-19 | Signal Divergence | Not a bug — documented + resolved with dual-signal view |
| ENH-15 | Market Scanner | Added ⏱️ Horizon column ("Ngắn hạn T+2") to scan results table |
| ENH-15 | Scanner/Top Buy | Caption note: "T+2 short-term technical signal" |
| ENH-16 | Profiler S6 | **Dual-signal card view**: Tech (T+2) vs Fundamental (6–24M) shown side-by-side |
| ENH-17 | Profiler S6 | **Conflict detection banner** with comparison table — auto-expands when signals diverge |
| ENH-18 | Profiler S6 | **Unified blended recommendation**: Fundamental 70% + Technical 30% (60/40 when no fundamentals) |
| ENH-18 | Profiler S6 | `get_scanner_signal_for_profiler()` runs exact same Scanner logic → guarantees consistency |
| ENH-18 | Profiler S6 | `get_unified_recommendation()` — transparent blending with weight display |

---

### v17.0 — 2026-03-08 · DATA PIPELINE FIX + PROFILER OVERHAUL

**🔴 v17.0 Critical Bug Fixes**

| Fix ID | Component | Issue | Resolution |
|--------|-----------|-------|------------|
| FIX-16 | DNSE | `services.entrade.com.vn` dead (empty data) | Switched to `api.dnse.com.vn/chart-api/v2/ohlcs/stock`, resolution `D→1D`. Confirmed 247 rows for FCN. Fixes entire data pipeline (Scanner, Backtest, ML). |
| FIX-17 | Stock Profiler | TCBS 404 + VNDirect timeout → default 5/5 scores, meaningless HOLD | Full cascade: TCBS → VNDirect → **CafeF** → **SSI** → **DNSE OHLC** (always succeeds). Profiler now ALWAYS produces valid recommendation. |

**🟢 v17.0 New Features**

| ENH ID | Component | Details |
|--------|-----------|---------|
| ENH-11 | CafeF APIs | `ChiSoTaiChinh` (EPS/PE/PB/MarketCap), `PriceRealTimeHeader` (live price), `CoCauSoHuu` (shareholder %, major holders), `FileBCTC` (financial report PDF links), Liveboard JSON (CDN price history) |
| ENH-12 | SSI SSMI APIs | `finance-indicator`, `company-leaderships`, `share-holder-summary`, `corporate-actions`, `company-news` — with proper iboard headers |
| ENH-13 | DNSE OHLC Analysis | `fetch_dnse_ohlc_analysis()` — computes RSI, MACD, ADX, BB, SMA20/50, 52W range, momentum returns (1M/3M/6M), volatility, volume trends. Used as ultimate fallback for profiler. |
| ENH-14 | Valuation Guarantee | When fundamentals absent: EPS estimated from price/sector PE, BVPS from price×0.6. Technical momentum used as EPS growth proxy. 4 valuation models + technical implied value always computed. |
| FIX-18 | Smoke Test | Added REE (HOSE) test cases. Tests now cover FPT+REE+OIL across all sources. Added CafeF fundamentals, DNSE OHLC Analysis, and Profiler Recommendation smoke tests (Tests 7–9). |

**🧬 Stock Profiler Data Cascade (v17)**

```
Source Priority:
1. TCBS tcanalysis    → financial statements, quarterly ratios
2. VNDirect FINFO     → financial statements fallback  
3. CafeF              → EPS, P/E, P/B, live price, shareholders, PDF reports
4. SSI SSMI           → leadership, corporate actions, news
5. DNSE OHLC (api.dnse.com.vn) → ALWAYS succeeds → technical analysis,
                                   implied EPS/BVPS, tech fair value
```

**Recommendation Score Formula:**
```
Composite (0–100) = Fundamental Quality (0–60) + Valuation Upside (0–25) + Technical (0–15)
→ ≥75: STRONG BUY  ≥60: BUY  ≥40: HOLD  ≥25: SELL  <25: STRONG SELL
```

---

### v16.0 — 2026-03-08

NEW TAB: 🧬 Stock Profiler. TCBS tcanalysis API. DCF/P/E/P/B/Graham valuation. Risk radar chart. Recommendation engine. Full bilingual VI/EN.

---

### v15.0 — 2026-03-08

FIX-12: DNSE /v2. FIX-13: SSI iboard-api. FIX-14: CafeF 4-strategy. FIX-15: PyArrow. ENH-05: TCBS price. ENH-06: VNDirect price. ENH-07: 7-source pipeline.

---

### v14.0 / v13.0 — Previous Releases

session_state fix, scan 3-tuple, SSI 404, DNSE multi, stooq fallback, Change Log tab.

""")



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

    # Define tabs (12 tabs in v16.0)
    tab_keys = ["tab1","tab2","tab3","tab4","tab5","tab6","tab7","tab8","tab9","tab10","tab11","tab12"]
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
    with tabs[11]:
        render_stock_profiler_tab()

if __name__ == "__main__":
    main()