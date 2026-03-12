"""
╔══════════════════════════════════════════════════════════════════╗
║   Captain Seventh QUANT TERMINAL  v28.0                         ║
║   Vietnam Stock Market Analysis & AI Forecasting Platform       ║
╠══════════════════════════════════════════════════════════════════╣
║  CHANGELOG v27 → v28:                                           ║
║  ENH-42: Deep Scan tab — full per-ticker intelligence module:   ║
║    SSI real-time price · Price forecasts (5d/10d/1M/2M/3M/6M)  ║
║    via LinReg+Holt+Monte-Carlo ensemble · Intrinsic value via   ║
║    sector P/E · DCF (tech-implied) · Graham proxy ·            ║
║    Whale/MM accumulation/distribution detection · Swing-trade   ║
║    risk level (Low/Med/High) · Entry + Exit + Stop prices ·    ║
║    Bilingual BUY/SELL/HOLD/WATCH recommendation with reasoning  ║
╠══════════════════════════════════════════════════════════════════╣
║  CHANGELOG v26 → v27:                                           ║
║  ENH-40: Market Scanner — Custom ticker input (comma-separated) ║
║    with fallback to Watchlist file when left blank; info bar    ║
║    shows source (Custom N tickers vs Watchlist N tickers).      ║
║  ENH-41: Scanner expanders — full Technical Indicators panel:   ║
║    SSI-RT live price, BB bands, RSI, MACD, ADX, Stochastic,    ║
║    ATR, Volume/MA, SMA/EMA crossovers + Price Derivation table  ║
║    showing exact formula used for each recommended price level. ║
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
    page_title="Captain Seventh QUANT TERMINAL v28.0",
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

  /* ENH-36 (v24): Bilingual tooltip — hover any .tt element to see translation */
  .tt {
    position:relative; cursor:help;
    border-bottom: 1px dotted #aaa;
    display:inline;
  }
  .tt::after {
    content: attr(data-tip);
    position:absolute; left:50%; transform:translateX(-50%);
    bottom:calc(100% + 6px);
    background:#1e2d3e; color:#e0e0ff;
    border:1px solid #3a5a8a; border-radius:6px;
    padding:5px 10px; font-size:12px; white-space:nowrap;
    opacity:0; pointer-events:none;
    transition:opacity 0.2s; z-index:9999;
  }
  .tt:hover::after { opacity:1; }

  /* Signal color tags */
  .sig-buy  {background:#004400;color:#44ff88;padding:2px 8px;border-radius:4px;font-weight:bold}
  .sig-sell {background:#440000;color:#ff6644;padding:2px 8px;border-radius:4px;font-weight:bold}
  .sig-watch{background:#222200;color:#ffcc44;padding:2px 8px;border-radius:4px}
  .sig-accum{background:#003322;color:#44ffcc;padding:2px 8px;border-radius:4px}
  .sig-dist {background:#330011;color:#ff44aa;padding:2px 8px;border-radius:4px}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  D. BILINGUAL LANGUAGE SYSTEM
# ══════════════════════════════════════════════════════════════
_LANG_VI = {
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v28.0",
    "sidebar_hdr":     "⚙️ Tùy Chỉnh Chiến Lược",
    "lang_label":      "🌐 Ngôn ngữ / Language",
    "trend_filter":    "Lọc Xu hướng (Giá > SMA50)",
    "liq_filter":      "Lọc Thanh khoản (>1 tỷ/ngày)",
    "rsi_buy":         "Ngưỡng RSI Mua:",
    "rsi_sell":        "Ngưỡng RSI Bán:",
    "pipeline_lbl":    "📡 7 Sources: DNSE→SSI→CafeF→TCBS→VNDir",
    "finance_lbl":     "📊 Tài chính: VNDirect FINFO",
    "disclaimer":      "⚠️ Chỉ tham khảo, không phải TVĐT",
    # VI labels — reorganized v24 menu
    "tab1":  "📊 Quét Thị Trường",
    "tab2":  "🎯 Tín Hiệu Thông Minh",
    "tab3":  "🧬 Hồ Sơ Cổ Phiếu",
    "tab4":  "🔍 Deep Audit",
    "tab5":  "💼 Danh Mục Mẫu",
    "tab6":  "🧠 Dự Báo ML",
    "tab7":  "🌍 Thị Trường TG",
    "tab8":  "🧪 Backtest T+2",
    "tab9":  "📂 Lịch Sử",
    "tab10": "📖 Hướng Dẫn",
    "tab11": "📝 Change Log",
    "tab12": "🔬 Smoke Test",
    "tab15": "📋 Nhật Ký Audit",
    "tab13": "📈 Lịch Sử Dự Báo",
    "tab14": "🔮 Top Forecast",
    "tab16": "🧭 Deep Scan",
    "tab17": "📡 Bảng Giá SSI Live",
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
    "app_title":       "🏛️ Captain Seventh QUANT TERMINAL v28.0",
    "sidebar_hdr":     "⚙️ Strategy Settings",
    "lang_label":      "🌐 Language / Ngôn ngữ",
    "trend_filter":    "Trend Filter (Price > SMA50)",
    "liq_filter":      "Liquidity Filter (>1B VND/day)",
    "rsi_buy":         "RSI Buy Threshold:",
    "rsi_sell":        "RSI Sell Threshold:",
    "pipeline_lbl":    "📡 7 Sources: DNSE→SSI→CafeF→TCBS→VNDir",
    "finance_lbl":     "📊 Financials: VNDirect FINFO",
    "disclaimer":      "⚠️ For reference only, not investment advice",
    # EN labels — reorganized v24 menu
    "tab1":  "📊 Market Scanner",
    "tab2":  "🎯 Smart Signals",
    "tab3":  "🧬 Stock Profiler",
    "tab4":  "🔍 Deep Audit",
    "tab5":  "💼 Model Portfolios",
    "tab6":  "🧠 ML Forecast",
    "tab7":  "🌍 Global Markets",
    "tab8":  "🧪 Backtest T+2",
    "tab9":  "📂 History",
    "tab10": "📖 Guide",
    "tab11": "📝 Change Log",
    "tab12": "🔬 Smoke Test",
    "tab15": "📋 Audit Log",
    "tab13": "📈 Forecast Log",
    "tab14": "🔮 Top Forecast",
    "tab16": "🧭 Deep Scan",
    "tab17": "📡 SSI Live Board",
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
#  ENH-V25: TOOLTIP CSS + AUDIT INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════

TOOLTIP_CSS = """
<style>
.q-tip { position:relative; display:inline-block; border-bottom:1px dotted #aaa; cursor:help; color:inherit; }
.q-tip .q-tip-text {
    visibility:hidden; opacity:0; background:#1a2035; color:#e8e8e8;
    border:1px solid #4e9af1; border-radius:8px; padding:10px 14px;
    font-size:12px; line-height:1.5; width:280px;
    position:absolute; z-index:9999; bottom:125%; left:50%; transform:translateX(-50%);
    transition:opacity .25s; pointer-events:none; box-shadow:0 4px 20px rgba(0,0,0,.5);
}
.q-tip .q-tip-text::after { content:""; position:absolute; top:100%; left:50%;
    transform:translateX(-50%); border:6px solid transparent; border-top-color:#4e9af1; }
.q-tip:hover .q-tip-text { visibility:visible; opacity:1; }
.audit-entry { background:#111827; border-left:3px solid #4e9af1; border-radius:6px;
    padding:10px 14px; margin:6px 0; font-size:12px; line-height:1.6; }
.audit-entry.buy  { border-color:#00cc44; }
.audit-entry.sell { border-color:#ff4444; }
.audit-entry.warn { border-color:#ffaa00; }
.insight-card { background:linear-gradient(135deg,#0f172a,#1e293b);
    border:1px solid #334155; border-radius:12px; padding:16px 20px; margin:8px 0; }
.insight-card h4 { margin:0 0 6px; color:#93c5fd; font-size:14px; }
.insight-card p  { margin:0; color:#cbd5e1; font-size:13px; line-height:1.5; }
</style>
"""

TOOLTIPS = {
    "RSI":{
        "VI": "RSI: Đo lường vận tốc thay đổi giá.<br>• &lt;35: Quá bán — tìm tín hiệu hồi phục<br>• &gt;65: Quá mua — rủi ro điều chỉnh<br>• 40–60: Trung tính",
        "EN": "RSI: Measures price momentum.<br>• &lt;35: Oversold — watch for bounce<br>• &gt;65: Overbought — correction risk<br>• 40–60: Neutral",
    },
    "MACD":{
        "VI": "MACD: So sánh EMA12 vs EMA26.<br>• MACD &gt; Signal: Momentum tăng<br>• Histogram mở rộng: Xu hướng mạnh thêm<br>• MACD &lt; Signal: Cảnh báo giảm",
        "EN": "MACD: Compares EMA12 vs EMA26.<br>• MACD &gt; Signal: Bullish momentum<br>• Expanding histogram: Trend strengthening<br>• MACD &lt; Signal: Bearish caution",
    },
    "SMA50":{
        "VI": "SMA50: Ngưỡng xác nhận xu hướng quan trọng nhất.<br>• Giá &gt; SMA50: Xu hướng TĂNG trung hạn ✅<br>• Giá &lt; SMA50: Xu hướng GIẢM — chia nhỏ lệnh",
        "EN": "SMA50: Most important trend confirmation.<br>• Price &gt; SMA50: Medium-term UPTREND ✅<br>• Price &lt; SMA50: DOWNTREND — scale in carefully",
    },
    "EMA200":{
        "VI": "EMA200: Xu hướng dài hạn.<br>• Golden Cross (EMA50&gt;EMA200): Tăng giá dài hạn ✅<br>• Death Cross (EMA50&lt;EMA200): Giảm giá dài hạn ⚠️",
        "EN": "EMA200: Long-term trend line.<br>• Golden Cross (EMA50&gt;EMA200): Long-term bullish ✅<br>• Death Cross (EMA50&lt;EMA200): Long-term bearish ⚠️",
    },
    "BB":{
        "VI": "Bollinger Bands (20 ngày ±2σ).<br>• Giá &lt; BB Lower: Ngoài dải — xác suất hồi phục cao<br>• Giá &gt; BB Upper: Cảnh báo điều chỉnh<br>• BB thắt: Sắp đột phá",
        "EN": "Bollinger Bands (20-day ±2σ).<br>• Price &lt; BB Lower: Mean reversion likely<br>• Price &gt; BB Upper: Correction warning<br>• BB squeeze: Breakout imminent",
    },
    "ADX":{
        "VI": "ADX: Sức mạnh xu hướng (không phân biệt tăng/giảm).<br>• &lt;15: Đi ngang — tránh lệnh xu hướng<br>• 15–25: Xu hướng hình thành<br>• &gt;25: Xu hướng rõ ràng ✅",
        "EN": "ADX: Trend strength (direction-agnostic).<br>• &lt;15: Sideways — avoid trend entries<br>• 15–25: Trend forming<br>• &gt;25: Clear trend ✅",
    },
    "VWAP":{
        "VI": "VWAP 20 ngày: Giá bình quân theo khối lượng.<br>• Giá &gt; VWAP: Mua ròng chiếm ưu thế ✅<br>• Giá &lt; VWAP: Bán ròng — thận trọng",
        "EN": "VWAP 20-day: Volume-weighted average price.<br>• Price &gt; VWAP: Net buying dominates ✅<br>• Price &lt; VWAP: Net selling — caution",
    },
    "ROE":{
        "VI": "ROE: Hiệu quả vốn cổ đông.<br>• &gt;20%: Tốt<br>• 12–20%: Khá<br>• &lt;10%: Yếu",
        "EN": "ROE: Shareholder capital efficiency.<br>• &gt;20%: Excellent<br>• 12–20%: Good<br>• &lt;10%: Weak",
    },
    "PE":{
        "VI": "P/E: Bội số thu nhập. KHÔNG dùng cho Ngân hàng (dùng P/B).<br>• &lt; P/E ngành: Có thể đang rẻ<br>• &gt; P/E ngành: Kỳ vọng cao hoặc đắt",
        "EN": "P/E: Earnings multiple. NOT for Banking (use P/B).<br>• Below sector P/E: Potentially cheap<br>• Above sector P/E: High growth priced in or expensive",
    },
    "composite_score":{
        "VI": "Điểm Tổng Hợp (0–100): Kết hợp kỹ thuật + cơ bản + rủi ro.<br>• 70–100: Tốt, rủi ro thấp<br>• 50–70: Trung bình, cần xác nhận thêm<br>• &lt;50: Yếu, thận trọng",
        "EN": "Composite Score (0–100): Technical + fundamental + risk blend.<br>• 70–100: Strong, low risk<br>• 50–70: Moderate, needs confirmation<br>• &lt;50: Weak, exercise caution",
    },
    "ATR":{
        "VI": "ATR: Biên độ biến động bình quân 14 ngày.<br>• Dùng để tính Stop-Loss (SL = Giá - 1.5×ATR)<br>• ATR lớn: Biến động cao — tăng khoảng cách SL",
        "EN": "ATR: 14-day average true range (volatility).<br>• Used for Stop-Loss (SL = Price - 1.5×ATR)<br>• High ATR: High volatility — widen SL distance",
    },
}

def tip(label: str, key: str, lang: str = "VI") -> str:
    tt = TOOLTIPS.get(key, {})
    text = tt.get(lang, tt.get("VI", ""))
    if not text: return label
    return f'<span class="q-tip">{label}<span class="q-tip-text">{text}</span></span>'


# Audit category constants (used by render_audit_log_tab filter)
AUDIT_CATEGORIES = [
    "SCANNER", "PROFILER", "DEEP_AUDIT", "ML_FORECAST",
    "TOP_FORECAST", "PORTFOLIO", "BACKTEST", "MANUAL",
]

# ─── Universal Audit Log ──────────────────────────────────────
def append_audit(category: str, action: str, ticker: str, signal: str,
                 score: float, details: dict, lang: str = "VI"):
    """Append structured audit entry. Called from every analysis action."""
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = []
    entry = {
        "ts":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date":     datetime.now().strftime("%Y-%m-%d"),
        "time":     datetime.now().strftime("%H:%M:%S"),
        "category": category,
        "action":   action,
        "ticker":   ticker,
        "signal":   signal,
        "score":    round(float(score or 0), 2),
        "details":  details,
        "lang":     lang,
    }
    st.session_state.audit_log.insert(0, entry)
    if len(st.session_state.audit_log) > 3000:
        st.session_state.audit_log = st.session_state.audit_log[:3000]
    try:
        import json as _json
        _apath = os.path.join(DATA_DIR, "audit_log.jsonl")
        with open(_apath, "a", encoding="utf-8") as _f:
            _f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_audit_from_disk() -> list:
    """Load audit log from JSONL file on disk."""
    import json as _json
    _apath = os.path.join(DATA_DIR, "audit_log.jsonl")
    entries = []
    if not os.path.exists(_apath): return entries
    try:
        with open(_apath, "r", encoding="utf-8") as _f:
            for line in _f:
                line = line.strip()
                if line:
                    try: entries.append(_json.loads(line))
                    except: pass
        entries.sort(key=lambda x: x.get("ts", ""), reverse=True)
    except Exception:
        pass
    return entries[:5000]


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


# ── ENH-37/38/39 (v26): Unified Recommended Price Engine ─────────
def compute_recommended_prices(
    close: float,
    bbl: float,
    bbu: float,
    atr: float,
    signal: str,
    rt_price: float = 0.0,
    floor_p: float = 0.0,
    ceil_p: float = 0.0,
) -> dict:
    """
    v26 ENH-39: Compute recommended Buy & Sell prices from live data.

    Logic:
      BUY  → Entry near BB Lower (confirmed bounce zone); TP1/TP2 = ATR targets
      SELL → Sell near current price (at/above BB Upper); re-entry at BB Lower
      WATCH→ Show potential entry at BB Lower; TP targets still valid

    Data priority: rt_price (SSI-RT / CafeF-RT) → close (OHLCV)
    All prices rounded to nearest 100 VND (HOSE standard).
    """
    _atr  = max(atr or 0, close * 0.015)   # floor ATR at 1.5% of price
    live  = rt_price if rt_price and rt_price > 0 else close
    _bbl  = bbl if bbl and bbl > 0 else live * 0.97
    _bbu  = bbu if bbu and bbu > 0 else live * 1.03

    if signal in ("MUA", "BUY"):
        # Best entry: slightly above BB Lower as bounce confirmation
        ideal   = _bbl + _atr * 0.30
        # Don't recommend buying above the current live price
        rec_buy = round_price_hose(min(live, ideal) if ideal < live * 1.01 else live)
        if live <= _bbl:
            # Price already below BB Lower — safest entry is live + small buffer
            rec_buy = round_price_hose(live * 1.002)
        # Enforce exchange floor (never below floor price)
        if floor_p > 0:
            rec_buy = max(rec_buy, floor_p)

        rec_sell_tp1 = round_price_hose(live + 2.0 * _atr)
        rec_sell_tp2 = round_price_hose(live + 3.5 * _atr)
        rec_stop     = round_price_hose(max(live - 1.5 * _atr, live * 0.90))
        if ceil_p > 0:
            rec_sell_tp2 = min(rec_sell_tp2, ceil_p)

    elif signal in ("BÁN", "SELL"):
        # Already holding — exit zone: at/near current price (below BB Upper)
        rec_buy      = round_price_hose(_bbl)          # re-entry if price pulls back
        rec_sell_tp1 = round_price_hose(min(live, _bbu * 0.995))
        rec_sell_tp2 = round_price_hose(_bbu)
        rec_stop     = round_price_hose(live + 1.5 * _atr)  # protective stop for shorts

    else:  # THEO DÕI / WATCH
        rec_buy      = round_price_hose(_bbl)
        rec_sell_tp1 = round_price_hose(live + 2.0 * _atr)
        rec_sell_tp2 = round_price_hose(_bbu)
        rec_stop     = round_price_hose(max(live - 1.5 * _atr, live * 0.90))

    ref          = live if live > 0 else close
    pct_upside   = round((rec_sell_tp1 - ref) / ref * 100, 1) if ref > 0 else 0.0
    pct_risk     = round((ref - rec_stop) / ref * 100, 1)     if ref > 0 else 0.0
    rr           = round(pct_upside / pct_risk, 2)            if pct_risk > 0 else 0.0

    return {
        "rec_buy":      rec_buy,
        "rec_sell_tp1": rec_sell_tp1,
        "rec_sell_tp2": rec_sell_tp2,
        "rec_stop":     rec_stop,
        "pct_upside":   pct_upside,
        "pct_risk":     pct_risk,
        "rr":           rr,
        "live_price":   live,
    }



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

# ENH-32 (v24): SMA trend filter options
sb.markdown("**📐 " + ("Bộ lọc đường MA" if st.session_state.lang=="VI" else "MA Trend Filter") + "**")
_sma_options = {"SMA5":5,"SMA7":7,"SMA10":10,"SMA20":20,"SMA50":50}
_sma_default = ["SMA50"]
sma_filter_choices = sb.multiselect(
    ("Lọc xu hướng theo MA" if st.session_state.lang=="VI" else "Filter by MA (price must be above)"),
    options=list(_sma_options.keys()),
    default=_sma_default,
    help=("Chọn các đường MA mà giá phải ở trên để tính là xu hướng tăng" if st.session_state.lang=="VI"
          else "Price must be above ALL selected MAs to count as uptrend"),
)
sma_filter_periods = [_sma_options[k] for k in sma_filter_choices if k in _sma_options]

sb.divider()
sb.caption(f"📦 {len(MARKET_SCAN_LIST)} mã HOSE/HNX/UPCOM")
sb.caption(f"📡 Pipeline: SSI→DNSE→CafeF→TCBS→VNDir→yF")
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
    # ENH-33 (v24): SSI is now first priority in pipeline
    _PIPELINE = [
        ("SSI",        _fetch_ssi),
        ("DNSE",       _fetch_dnse),
        ("CafeF",      _fetch_cafef),
        ("TCBS",       _fetch_tcbs),
        ("CafeF-JSON", _fetch_cafef_v2),
        ("VNDirect",   _fetch_vndirect_price),
        ("yFinance",   _fetch_yfinance),
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

    # ENH-31: Full SMA suite 5/10/20/30/50/100/200
    for _p in [5, 10, 20, 30, 50, 100, 200]:
        df[f"SMA{_p}"] = df["Close"].rolling(_p).mean()

    # ENH-31: EMA suite 9/21/50/200
    for _p in [9, 21, 50, 200]:
        df[f"EMA{_p}"] = df["Close"].ewm(span=_p, adjust=False).mean()

    # Golden/Death Cross signals (EMA50 vs EMA200)
    df["GoldenCross"]  = (df["EMA50"] > df["EMA200"]) & (df["EMA50"].shift(1) <= df["EMA200"].shift(1))
    df["DeathCross"]   = (df["EMA50"] < df["EMA200"]) & (df["EMA50"].shift(1) >= df["EMA200"].shift(1))
    # EMA21 cross EMA9 (short-term momentum)
    df["EMA_Bull"] = df["EMA9"] > df["EMA21"]

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
    # FIX-22: Extract EMA/SMA from row (were undefined — NameError in v21)
    ema200=safe("EMA200"); sma200=safe("SMA200"); sma100=safe("SMA100")
    ema9=safe("EMA9"); ema21=safe("EMA21"); sma5=safe("SMA5"); sma10=safe("SMA10")

    if signal_type == "BUY":
        if rsi and rsi < rsi_thresh:
            score += (rsi_thresh-rsi)*0.6; confirms.append(f"RSI={rsi:.0f}")
        if cls and bbl and cls < bbl:
            score += 5; confirms.append("Giá<BB↓")
        if trend_ok:
            score += 4; confirms.append("↑SMA50")
        # ENH-31: EMA/SMA cascade confirmations (FIX-22: now properly extracted)
        if cls and ema200 and cls > ema200:  score += 3; confirms.append("↑EMA200")
        if cls and sma200 and cls > sma200:  score += 2; confirms.append("↑SMA200")
        if cls and sma100 and cls > sma100:  score += 2; confirms.append("↑SMA100")
        if ema9 and ema21 and ema9 > ema21:  score += 3; confirms.append("EMA9>21↑")
        if cls and sma5  and cls > sma5:     score += 1; confirms.append("↑SMA5")
        if cls and sma10 and cls > sma10:    score += 1; confirms.append("↑SMA10")
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
    """FIX-26 (v23): Arrow-safe dataframe renderer. Converts mixed-type columns to str
    to prevent pyarrow.lib.ArrowTypeError on columns like Stoch%K, ADX, SMA* etc."""
    import pandas as pd
    if isinstance(df_or_styled, pd.DataFrame):
        df = df_or_styled.copy()
        # FIX-26: For every column that has mixed float+str, cast entire column to str
        # This fixes: "Expected bytes, got a 'float' object" for Stoch%K and similar
        for col in df.columns:
            col_series = df[col]
            if col_series.dtype == object:
                # Check if any value is a float/int alongside strings
                types = set(type(v).__name__ for v in col_series.dropna())
                if len(types) > 1 or ('float' in types or 'int' in types):
                    df[col] = col_series.apply(
                        lambda x: "" if x is None or (isinstance(x, float) and np.isnan(x))
                        else (f"{x:,.1f}" if isinstance(x, float) else str(x))
                    )
                else:
                    df[col] = col_series.apply(
                        lambda x: "" if x is None else str(x)
                    )
        df_or_styled = df
    try:
        st.dataframe(df_or_styled, width='stretch', key=key)
    except TypeError:
        st.dataframe(df_or_styled, key=key)

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
    # ENH-32 (v24): Multi-SMA trend filter from sidebar
    if use_trend_filter and sma_filter_periods:
        trend_ok = all(
            (extract_latest(data, f"SMA{p}") is not None and c_v > extract_latest(data, f"SMA{p}"))
            for p in sma_filter_periods
        )
    elif use_trend_filter:
        trend_ok = (s50 is not None and c_v > s50)
    else:
        trend_ok = True
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
    # ENH-31: Extract extra SMA/EMA values for row
    sma5_v   = extract_latest(data, "SMA5")
    sma10_v  = extract_latest(data, "SMA10")
    sma30_v  = extract_latest(data, "SMA30")
    sma100_v = extract_latest(data, "SMA100")
    sma200_v = extract_latest(data, "SMA200")
    ema9_v   = extract_latest(data, "EMA9")
    ema21_v  = extract_latest(data, "EMA21")
    ema50_v  = extract_latest(data, "EMA50")
    ema200_v = extract_latest(data, "EMA200")

    # ENH-32: Foreign investor room (from CafeF)
    try:
        _sh_d = fetch_cafef_shareholder_structure(t)
        _foreign_pct = _sh_d.get("foreign_pct", 0)
    except Exception:
        _foreign_pct = 0

    # ENH-33: Auto Stop/TP from ATR
    _atr = atr_v or (c_v * 0.02)
    _stop_loss = round_price_hose(c_v - 1.5 * _atr)
    _tp1       = round_price_hose(c_v + 2.0 * _atr)
    _tp2       = round_price_hose(c_v + 3.5 * _atr)
    _rr1       = round((c_v + 2.0*_atr - c_v) / (c_v - c_v + 1.5*_atr), 2) if _atr > 0 else 0
    _rr2       = round((3.5*_atr) / (1.5*_atr), 2) if _atr > 0 else 0

    # Price limits (ENH-25)
    _lims = get_price_limits(t, c_v)
    _ceil_p = _lims.get("ceiling", 0)
    _floor_p = _lims.get("floor", 0)

    # FIX-30: Fetch SSI real-time price to override OHLCV close (fixes BSR & other stale prices)
    # Priority: SSI iboard live → CafeF live → OHLCV close
    _rt_price = c_v; _rt_ref = 0; _rt_src = src
    try:
        _ssi_rt = fetch_ssi_realtime_price(t)
        if _ssi_rt.get("price", 0) > 0:
            _rt_price = _ssi_rt["price"]
            _rt_ref   = _ssi_rt.get("reference", 0)
            _rt_src   = "SSI-RT"
            # Recompute limits based on live reference price if available
            if _rt_ref > 0:
                _lims2   = get_price_limits(t, _rt_ref)
                _ceil_p  = _lims2.get("ceiling", _ceil_p)
                _floor_p = _lims2.get("floor", _floor_p)
        else:
            # Fallback to CafeF live price
            try:
                _cfp = fetch_cafef_price(t)
                if _cfp.get("price", 0) > 0:
                    _rt_price = _cfp["price"]
                    _rt_ref   = _cfp.get("reference", 0)
                    _rt_src   = "CafeF-RT"
            except Exception:
                pass
    except Exception:
        pass

    # ENH-39 (v26): Compute recommended buy/sell prices from live data
    _rec = compute_recommended_prices(
        close=c_v, bbl=bbl_v, bbu=bbu_v, atr=_atr,
        signal=hanh_vi, rt_price=_rt_price,
        floor_p=_floor_p, ceil_p=_ceil_p,
    )

    row = {
        L["ticker"]:    t,
        "Ngành/Sector": get_sector(t),
        L["price"]:     round(_rt_price),      # FIX-30: live price, not OHLCV close
        L["signal"]:    signal_display,
        "⏱️ Chân trời" if lang=="VI" else "⏱️ Horizon": "Ngắn hạn T+2" if lang=="VI" else "Short-term T+2",
        # ── ENH-37 (v26): Recommended Buy & Sell prices ──────────
        "💰 Mua KN":    _rec["rec_buy"],
        "🎯 Bán TP1":   _rec["rec_sell_tp1"],
        "🎯 Bán TP2":   _rec["rec_sell_tp2"],
        "🛑 Cắt Lỗ":   _rec["rec_stop"],
        # ─────────────────────────────────────────────────────────
        "BB Buy":       round_price_hose(bbl_v),
        "BB Sell":      round_price_hose(bbu_v),
        "SMA5":         round(sma5_v)  if sma5_v  else "–",
        "SMA20":        round(s20)     if s20      else "–",
        "SMA50":        round(s50)     if s50      else "–",
        "SMA200":       round(sma200_v) if sma200_v else "–",
        "EMA9":         round(ema9_v)  if ema9_v  else "–",
        "EMA21":        round(ema21_v) if ema21_v else "–",
        "RSI":          round(rsi_v,1),
        "Stoch%K":      round(sk,1) if sk else "–",
        "ADX":          round(adx_v,1) if adx_v else "–",
        "Vol/MA20":     f"{last_v/avg_v:.1f}×" if avg_v>0 else "–",
        "🌐 NN%":       f"{_foreign_pct:.1f}%" if _foreign_pct else "–",
        "SL":           _stop_loss,
        "TP1":          _tp1,
        "TP2":          _tp2,
        "R:R1":         f"1:{_rr1}",
        "Trần" if lang=="VI" else "Ceil": _ceil_p or "–",
        "Sàn" if lang=="VI" else "Floor": _floor_p or "–",
        L["score"]:     score,
        "Confirms":     len(confirms),
        "⚠️ DL":        len(doi_lai),
        L["source"]:    _rt_src,   # FIX-30: show actual price source (SSI-RT / CafeF-RT / OHLCV)
        "_ly_giai":     ly_giai,
        "_price_expl":  price_expl,
        "_sma5":        sma5_v,  "_sma10": sma10_v, "_sma20": s20,
        "_sma30":       sma30_v, "_sma50": s50,     "_sma100": sma100_v, "_sma200": sma200_v,
        "_ema9":        ema9_v,  "_ema21": ema21_v, "_ema50": ema50_v, "_ema200": ema200_v,
        "_atr":         _atr,    "_stop":  _stop_loss, "_tp1": _tp1, "_tp2": _tp2,
        # Internal recommended prices (used by Smart Signals cards)
        "_rec_buy":       _rec["rec_buy"],
        "_rec_sell_tp1":  _rec["rec_sell_tp1"],
        "_rec_sell_tp2":  _rec["rec_sell_tp2"],
        "_rec_stop":      _rec["rec_stop"],
        "_pct_upside":    _rec["pct_upside"],
        "_pct_risk":      _rec["pct_risk"],
        "_rec_rr":        _rec["rr"],
    }
    # ENH-V25: Audit log
    try:
        append_audit("SCANNER", "SCAN_TICKER", t, hanh_vi, score, {
            "close": c_v, "rsi": round(rsi_v,1), "adx": round(adx_v,1) if adx_v else 0,
            "sma50": round(s50) if s50 else None, "atr": round(_atr,0),
            "stop_loss": _stop_loss, "tp1": _tp1, "tp2": _tp2,
            "confirms": len(confirms), "src": src, "sector": get_sector(t),
        }, lang)
    except Exception: pass
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

@st.cache_data(ttl=60)
def fetch_ssi_realtime_price(ticker: str) -> dict:
    """
    ENH-28 (v24.0): SSI iboard-query real-time price + Ceiling/Floor/Reference.
    Endpoint: iboard-query.ssi.com.vn/stock/{ticker}?boardId=MAIN
    Returns: {price, ceiling, floor, reference, pct_change, volume, exchange}
    """
    try:
        url = f"https://iboard-query.ssi.com.vn/stock/{ticker.upper()}?boardId=MAIN"
        r = requests.get(url, headers=_SSI_HDR, timeout=8)
        if r.status_code == 403:
            _log.debug(f"SSI iboard-query {ticker}: 403 forbidden (auth required)")
            return {}
        r.raise_for_status()
        raw = r.json()
        # SSI iboard-query response format: top-level or nested "data"
        d = raw if isinstance(raw, dict) else {}
        data = d.get("data", d)
        if not data: return {}
        def _f(k, fallback=0):
            v = data.get(k, fallback)
            try: return float(v or 0)
            except: return float(fallback)
        # price fields: "matchedPrice" or "close" or "lastPrice"
        price   = _f("matchedPrice") or _f("close") or _f("lastPrice")
        ref     = _f("referencePrice") or _f("priorClosePrice")
        ceiling = _f("ceilingPrice")
        floor   = _f("floorPrice")
        vol     = _f("matchedVolume") or _f("totalVolume")
        pct     = ((price - ref) / ref * 100) if ref > 0 and price > 0 else 0
        # Normalise: SSI sometimes returns prices in thousands VND
        for val in [price, ref, ceiling, floor]:
            if 0 < val < 500:
                price    *= 1000
                ref      *= 1000
                ceiling  *= 1000
                floor    *= 1000
                break
        if price <= 0: return {}
        _log.info(f"SSI iboard-query ✅ {ticker}: price={price:,.0f} ref={ref:,.0f} ceil={ceiling:,.0f} floor={floor:,.0f}")
        return {"price": price, "reference": ref, "ceiling": ceiling, "floor": floor,
                "pct_change": pct, "volume": vol, "source": "SSI-iboard"}
    except Exception as e:
        _log.debug(f"SSI iboard-query {ticker}: {e}")
        return {}


@st.cache_data(ttl=3600)
def fetch_ssi_news(ticker: str, n: int = 10) -> list:
    """SSI SSMI company news. FIX-25: Restored function def that was lost in v22."""
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
#  SSI LIVE MARKET DATA  (ENH-43 v29.0)
#  Sources:
#    /stock/group/{group}    — bulk real-time quote for entire group
#    /le-table/stock/{sym}   — recent matched order log (intraday)
#    /system/time            — server timestamp / session check
# ══════════════════════════════════════════════════════════════

# Supported SSI market groups and their display labels
SSI_MARKET_GROUPS = {
    "VN30":    ("VN30",    30),
    "VN100":   ("VN100",  100),
    "VNX50":   ("VNX50",   50),
    "HNX30":   ("HNX30",   30),
    "HNXIndex":("HNX All", None),
}

@st.cache_data(ttl=30)   # 30-second cache — near-real-time
def fetch_ssi_market_group(group: str = "VN30") -> pd.DataFrame:
    """
    ENH-43: Fetch all stocks in a named SSI market group in a single API call.
    Endpoint: iboard-query.ssi.com.vn/stock/group/{group}
    Returns DataFrame with full real-time OHLCV + order-book top-of-book.

    Fields extracted:
      stockSymbol, exchange, matchedPrice, priceChange, priceChangePercent,
      refPrice, openPrice, highest, lowest,
      nmTotalTradedQty, nmTotalTradedValue,
      stockBUVol, stockSDVol,
      buyForeignQtty, sellForeignQtty, remainForeignQtty,
      best1Bid, best1BidVol, best1Offer, best1OfferVol,
      ceiling, floor, session, companyNameVi
    """
    url = f"https://iboard-query.ssi.com.vn/stock/group/{group}"
    try:
        r = requests.get(url, headers=_SSI_HDR, timeout=10)
        if r.status_code == 403:
            _log.warning(f"SSI group/{group}: 403 — auth required")
            return pd.DataFrame()
        r.raise_for_status()
        items = r.json().get("data", [])
        if not isinstance(items, list) or not items:
            return pd.DataFrame()
        rows = []
        for d in items:
            def _fv(k, fb=0):
                v = d.get(k, fb)
                try:    return float(v or 0)
                except: return float(fb)
            price = _fv("matchedPrice") or _fv("expectedMatchedPrice")
            ref   = _fv("refPrice") or _fv("priorClosePrice")
            pct   = _fv("priceChangePercent")
            if price <= 0 and ref > 0:
                price = ref
            # Normalise: prices returned in VND (already full, not thousands)
            rows.append({
                "Mã":           d.get("stockSymbol", ""),
                "Sàn":          d.get("exchange", "").upper(),
                "Tên":          d.get("companyNameVi", ""),
                "Giá":          price,
                "±":            _fv("priceChange"),
                "±%":           pct,
                "TC":           ref,
                "Mở":           _fv("openPrice"),
                "Cao":          _fv("highest"),
                "Thấp":         _fv("lowest"),
                "KL":           int(_fv("nmTotalTradedQty")),
                "GT(B)":        round(_fv("nmTotalTradedValue") / 1e9, 1),
                "KL Mua":       int(_fv("stockBUVol")),
                "KL Bán":       int(_fv("stockSDVol")),
                "NN Mua":       int(_fv("buyForeignQtty")),
                "NN Bán":       int(_fv("sellForeignQtty")),
                "NN Còn":       int(_fv("remainForeignQtty")),
                "Bid1":         _fv("best1Bid"),
                "BidV1":        int(_fv("best1BidVol")),
                "Ask1":         _fv("best1Offer"),
                "AskV1":        int(_fv("best1OfferVol")),
                "Trần":         _fv("ceiling"),
                "Sàn giá":      _fv("floor"),
                "Phiên":        d.get("session", ""),
            })
        df = pd.DataFrame(rows)
        df = df[df["Mã"].str.len() > 0]
        _log.info(f"SSI group/{group}: {len(df)} tickers loaded")
        return df
    except Exception as e:
        _log.warning(f"SSI group/{group} error: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=10)   # 10-second cache for transaction log
def fetch_ssi_le_table(ticker: str, page_size: int = 30) -> pd.DataFrame:
    """
    ENH-43: Fetch recent matched orders for a single ticker.
    Endpoint: iboard-query.ssi.com.vn/le-table/stock/{ticker}?pageSize=N
    Returns DataFrame: price, vol, side, time, accumulatedVol, priceChange %.
    """
    url = f"https://iboard-query.ssi.com.vn/le-table/stock/{ticker.upper()}?pageSize={page_size}"
    try:
        r = requests.get(url, headers=_SSI_HDR, timeout=8)
        if r.status_code == 403:
            return pd.DataFrame()
        r.raise_for_status()
        inner = r.json().get("data", {})
        items = inner.get("items", []) if isinstance(inner, dict) else []
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            side_raw = it.get("side", "e")
            side_map = {"bu": "Mua↑", "sd": "Bán↓", "e": "Khớp="}
            rows.append({
                "Giờ":       it.get("time", ""),
                "Giá":       float(it.get("price", 0) or 0),
                "±%":        round(float(it.get("priceChangePercent", 0) or 0), 2),
                "KL Khớp":   int(it.get("vol", 0) or 0),
                "KL Tích Lũy": int(it.get("accumulatedVol", 0) or 0),
                "GT (tỷ)":   round(float(it.get("accumulatedVal", 0) or 0) / 1e9, 2),
                "Chiều":    side_map.get(side_raw, side_raw),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        _log.debug(f"SSI le-table {ticker}: {e}")
        return pd.DataFrame()


def _ssi_session_label(session_code: str, lang: str = "VI") -> str:
    """Map SSI session code to human-readable label."""
    _map_vi = {
        "ATO": "🌅 ATO (Khớp lệnh mở cửa)",
        "LO":  "🟢 LO (Khớp lệnh liên tục)",
        "ATC": "🔔 ATC (Khớp lệnh đóng cửa)",
        "PT":  "🔄 PT (Thoả thuận sau giờ)",
        "PTR": "✅ PTR (Kết thúc thoả thuận)",
        "C":   "🔴 C (Đóng cửa)",
        "":    "⏳ Chờ mở cửa",
    }
    _map_en = {
        "ATO": "🌅 ATO (Opening call auction)",
        "LO":  "🟢 LO (Continuous trading)",
        "ATC": "🔔 ATC (Closing call auction)",
        "PT":  "🔄 PT (Put-through after hours)",
        "PTR": "✅ PTR (Put-through closed)",
        "C":   "🔴 C (Market closed)",
        "":    "⏳ Pre-market",
    }
    d = _map_vi if lang == "VI" else _map_en
    return d.get(session_code, session_code)


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

    # Build human-readable explanation for each dimension
    explanations = {}
    de_val = _latest(ratio_df, "payableOnEquity") or _latest(ratio_df, "D/E")
    roe_val = _latest(ratio_df, "roe") or _latest(ratio_df, "ROE")
    npm_val = _latest(ratio_df, "netProfitMargin") or _latest(ratio_df, "Biên ròng")
    cr_val  = _latest(ratio_df, "currentPayment") or _latest(ratio_df, "Curr")
    pe_val  = _latest(ratio_df, "priceToEarning") or _latest(ratio_df, "P/E")

    # Debt explanation
    if de_val is not None:
        if de_val < 0.5:
            explanations["debt"] = {
                "VI": f"D/E = {de_val:.2f} — Rất thấp (<0.5). Cấu trúc vốn cực kỳ an toàn, không phụ thuộc vào nợ vay. Rủi ro tài chính tối thiểu.",
                "EN": f"D/E = {de_val:.2f} — Very low (<0.5). Extremely safe capital structure, minimal financial risk.",
            }
        elif de_val < 1.0:
            explanations["debt"] = {
                "VI": f"D/E = {de_val:.2f} — Thấp (0.5–1.0). Nợ vay được quản lý tốt, cấu trúc vốn lành mạnh.",
                "EN": f"D/E = {de_val:.2f} — Low (0.5–1.0). Well-managed debt, healthy capital structure.",
            }
        elif de_val < 2.0:
            explanations["debt"] = {
                "VI": f"D/E = {de_val:.2f} — Trung bình (1–2). Mức nợ chấp nhận được, cần theo dõi chi phí lãi vay.",
                "EN": f"D/E = {de_val:.2f} — Moderate (1–2). Acceptable leverage, monitor interest costs.",
            }
        elif de_val < 3.0:
            explanations["debt"] = {
                "VI": f"D/E = {de_val:.2f} — Cao (2–3). Gánh nặng nợ đáng kể, dễ bị tổn thương khi lãi suất tăng.",
                "EN": f"D/E = {de_val:.2f} — High (2–3). Significant debt burden, vulnerable to rising rates.",
            }
        else:
            explanations["debt"] = {
                "VI": f"D/E = {de_val:.2f} — Rất cao (>3). Cấu trúc vốn nguy hiểm, rủi ro mất khả năng thanh toán.",
                "EN": f"D/E = {de_val:.2f} — Very high (>3). Dangerous capital structure, solvency risk.",
            }
    else:
        explanations["debt"] = {"VI": "Không có dữ liệu D/E từ nguồn hiện tại.", "EN": "D/E data unavailable from current source."}

    # Liquidity explanation
    if cr_val is not None:
        if cr_val > 2.5:
            explanations["liquidity"] = {
                "VI": f"Hệ số hiện thời = {cr_val:.2f} — Tốt (>2.5). Khả năng thanh toán ngắn hạn rất mạnh.",
                "EN": f"Current Ratio = {cr_val:.2f} — Good (>2.5). Strong short-term liquidity.",
            }
        elif cr_val > 1.5:
            explanations["liquidity"] = {
                "VI": f"Hệ số hiện thời = {cr_val:.2f} — Khá (1.5–2.5). Thanh khoản ngắn hạn ổn định.",
                "EN": f"Current Ratio = {cr_val:.2f} — Fair (1.5–2.5). Adequate short-term liquidity.",
            }
        elif cr_val > 1.0:
            explanations["liquidity"] = {
                "VI": f"Hệ số hiện thời = {cr_val:.2f} — Thấp (1–1.5). Thanh khoản tương đối chặt chẽ, cần theo dõi dòng tiền.",
                "EN": f"Current Ratio = {cr_val:.2f} — Low (1–1.5). Tight liquidity, monitor cash flow.",
            }
        else:
            explanations["liquidity"] = {
                "VI": f"Hệ số hiện thời = {cr_val:.2f} — Rủi ro cao (<1). Nợ ngắn hạn vượt tài sản ngắn hạn.",
                "EN": f"Current Ratio = {cr_val:.2f} — High risk (<1). Short-term liabilities exceed current assets.",
            }
    else:
        explanations["liquidity"] = {"VI": "Không có dữ liệu hệ số thanh khoản.", "EN": "Liquidity ratio data unavailable."}

    # Profitability explanation
    if roe_val is not None:
        roe_p = roe_val * 100 if roe_val < 1 else roe_val
        npm_p = (npm_val * 100 if npm_val and npm_val < 1 else npm_val) if npm_val else None
        npm_str = f", Biên ròng={npm_p:.1f}%" if npm_p else ""
        if roe_p > 20:
            explanations["profitability"] = {
                "VI": f"ROE = {roe_p:.1f}%{npm_str} — Xuất sắc (>20%). Doanh nghiệp tạo giá trị vượt trội cho cổ đông. Lợi thế cạnh tranh bền vững.",
                "EN": f"ROE = {roe_p:.1f}%{npm_str} — Excellent (>20%). Outstanding value creation. Sustainable competitive advantage.",
            }
        elif roe_p > 12:
            explanations["profitability"] = {
                "VI": f"ROE = {roe_p:.1f}%{npm_str} — Tốt (12–20%). Khả năng sinh lời trên mức trung bình, quản lý hiệu quả.",
                "EN": f"ROE = {roe_p:.1f}%{npm_str} — Good (12–20%). Above-average profitability, efficient management.",
            }
        elif roe_p > 5:
            explanations["profitability"] = {
                "VI": f"ROE = {roe_p:.1f}%{npm_str} — Trung bình (5–12%). Khả năng sinh lời ở mức tương đối thấp. Cần cải thiện hiệu quả.",
                "EN": f"ROE = {roe_p:.1f}%{npm_str} — Average (5–12%). Below-average profitability, efficiency improvement needed.",
            }
        elif roe_p > 0:
            explanations["profitability"] = {
                "VI": f"ROE = {roe_p:.1f}%{npm_str} — Yếu (0–5%). Lợi nhuận thấp, đặt câu hỏi về lợi thế cạnh tranh.",
                "EN": f"ROE = {roe_p:.1f}%{npm_str} — Weak (0–5%). Low profitability, competitive advantage in question.",
            }
        else:
            explanations["profitability"] = {
                "VI": f"ROE = {roe_p:.1f}%{npm_str} — Thua lỗ. Doanh nghiệp đang phá huỷ giá trị cổ đông.",
                "EN": f"ROE = {roe_p:.1f}%{npm_str} — Loss-making. Destroying shareholder value.",
            }
    else:
        explanations["profitability"] = {"VI": "Không có dữ liệu ROE.", "EN": "ROE data unavailable."}

    # Growth explanation (from income_df)
    if not income_df.empty:
        rev_col = next((c for c in income_df.columns
                        if any(k in c for k in ["revenue","Revenue","Doanh thu"])), None)
        if rev_col:
            revs = pd.to_numeric(income_df[rev_col], errors="coerce").dropna()
            if len(revs) >= 4:
                recent = revs.iloc[:4].mean(); older = revs.iloc[4:8].mean() if len(revs) >= 8 else revs.iloc[-4:].mean()
                growth = (recent - older) / abs(older) if older != 0 else 0
                g_pct = growth * 100
                if g_pct > 20:
                    explanations["growth"] = {
                        "VI": f"Tăng trưởng doanh thu = +{g_pct:.1f}%/năm — Tăng trưởng cao. Doanh nghiệp đang mở rộng quy mô nhanh.",
                        "EN": f"Revenue growth = +{g_pct:.1f}%/yr — High growth. Business rapidly scaling.",
                    }
                elif g_pct > 10:
                    explanations["growth"] = {
                        "VI": f"Tăng trưởng doanh thu = +{g_pct:.1f}%/năm — Tốt. Doanh nghiệp tăng trưởng ổn định.",
                        "EN": f"Revenue growth = +{g_pct:.1f}%/yr — Good. Stable, consistent growth.",
                    }
                elif g_pct > 0:
                    explanations["growth"] = {
                        "VI": f"Tăng trưởng doanh thu = +{g_pct:.1f}%/năm — Yếu. Tăng trưởng nhỏ, gần như đình trệ.",
                        "EN": f"Revenue growth = +{g_pct:.1f}%/yr — Weak. Barely growing, near stagnation.",
                    }
                elif g_pct > -10:
                    explanations["growth"] = {
                        "VI": f"Tăng trưởng doanh thu = {g_pct:.1f}%/năm — Suy giảm nhẹ. Cần theo dõi xu hướng dài hạn.",
                        "EN": f"Revenue growth = {g_pct:.1f}%/yr — Slight decline. Monitor long-term trend.",
                    }
                else:
                    explanations["growth"] = {
                        "VI": f"Tăng trưởng doanh thu = {g_pct:.1f}%/năm — Suy giảm mạnh. Tín hiệu cảnh báo cơ bản đáng lo ngại.",
                        "EN": f"Revenue growth = {g_pct:.1f}%/yr — Sharp decline. Concerning fundamental warning sign.",
                    }
    if "growth" not in explanations:
        explanations["growth"] = {"VI": "Không đủ dữ liệu doanh thu để đánh giá tăng trưởng.", "EN": "Insufficient revenue data to assess growth."}

    # Valuation explanation
    if pe_val is not None and pe_val > 0:
        if pe_val < 8:
            explanations["valuation"] = {
                "VI": f"P/E = {pe_val:.1f} — Rất rẻ (<8). Có thể bị định giá thấp hoặc thị trường lo ngại về chất lượng lợi nhuận.",
                "EN": f"P/E = {pe_val:.1f} — Very cheap (<8). May be undervalued or market concerned about earnings quality.",
            }
        elif pe_val < 15:
            explanations["valuation"] = {
                "VI": f"P/E = {pe_val:.1f} — Hợp lý (8–15). Định giá thị trường phản ánh giá trị hợp lý.",
                "EN": f"P/E = {pe_val:.1f} — Fair (8–15). Market price reflects reasonable value.",
            }
        elif pe_val < 25:
            explanations["valuation"] = {
                "VI": f"P/E = {pe_val:.1f} — Đắt vừa (15–25). Thị trường kỳ vọng tăng trưởng; cần kiểm tra xem có cơ sở không.",
                "EN": f"P/E = {pe_val:.1f} — Moderately expensive (15–25). Growth expectations priced in; verify if justified.",
            }
        elif pe_val < 40:
            explanations["valuation"] = {
                "VI": f"P/E = {pe_val:.1f} — Đắt (25–40). Định giá cao, cần tăng trưởng mạnh để biện hộ.",
                "EN": f"P/E = {pe_val:.1f} — Expensive (25–40). High valuation requires strong growth justification.",
            }
        else:
            explanations["valuation"] = {
                "VI": f"P/E = {pe_val:.1f} — Rất đắt (>40). Rủi ro định giá cao, dễ điều chỉnh mạnh nếu tăng trưởng không đạt kỳ vọng.",
                "EN": f"P/E = {pe_val:.1f} — Very expensive (>40). High valuation risk; sharp correction if growth disappoints.",
            }
    else:
        explanations["valuation"] = {"VI": "Không có dữ liệu P/E.", "EN": "P/E data unavailable."}

    scores["_explanations"] = explanations
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
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
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
        # Pre-log profiler run
        for _t in raw_tickers:
            append_audit("PROFILER", "PROFILER_RUN", _t, "ANALYSING", 0,
                         {"yearly": yearly, "n_tickers": len(raw_tickers)}, st.session_state.lang)

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
                # ENH-34 (FIX): Banking P/B weight > 70% per SSI Research standard
                # P/B = 70%, DDM = 30% (DDM is secondary confirmation)
                fair_val = aggregate_fair_value(ddm_val, 0, pb_fair, 0, weights=(0.30, 0, 0.70, 0))
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

            # ENH-V25: Valuation explanation
            if fair_val > 0:
                up = upside_pct
                if up > 25:
                    expl_color_v, expl_icon = "#00cc44", "🟢"
                    expl_vi = f"**Chiết khấu sâu ({up:+.1f}%)**: Giá thị trường đang thấp hơn giá trị hợp lý ước tính {abs(up):.0f}%. Đây là vùng tích lũy hấp dẫn cho nhà đầu tư dài hạn. Phương pháp định giá: {val_method.get('method_label','')}"
                    expl_en = f"**Deep discount ({up:+.1f}%)**: Market price is {abs(up):.0f}% below estimated fair value. Attractive accumulation zone for long-term investors. Method: {val_method.get('method_label','')}"
                elif up > 10:
                    expl_color_v, expl_icon = "#88cc44", "🟩"
                    expl_vi = f"**Chiết khấu vừa phải ({up:+.1f}%)**: Cổ phiếu giao dịch dưới giá trị hợp lý, tiềm năng tăng giá trung hạn. Phương pháp: {val_method.get('method_label','')}"
                    expl_en = f"**Moderate discount ({up:+.1f}%)**: Stock below fair value, medium-term upside potential. Method: {val_method.get('method_label','')}"
                elif up > -10:
                    expl_color_v, expl_icon = "#ffaa00", "🟡"
                    expl_vi = f"**Định giá hợp lý ({up:+.1f}%)**: Giá thị trường phản ánh gần đúng giá trị cơ bản. Chờ pullback để có điểm vào tốt hơn. Phương pháp: {val_method.get('method_label','')}"
                    expl_en = f"**Fair value ({up:+.1f}%)**: Market price reflects fundamentals accurately. Wait for pullback for better entry. Method: {val_method.get('method_label','')}"
                else:
                    expl_color_v, expl_icon = "#ff4444", "🔴"
                    expl_vi = f"**Định giá đắt ({up:+.1f}%)**: Giá thị trường vượt giá trị hợp lý ước tính {abs(up):.0f}%. Rủi ro điều chỉnh cao. Phương pháp: {val_method.get('method_label','')}"
                    expl_en = f"**Overvalued ({up:+.1f}%)**: Market price exceeds fair value by {abs(up):.0f}%. High correction risk. Method: {val_method.get('method_label','')}"
                st.markdown(
                    f'<div style="background:{expl_color_v}15;border-left:3px solid {expl_color_v};'
                    f'border-radius:6px;padding:8px 14px;margin:6px 0;font-size:12px">'
                    f'{expl_icon} {expl_vi if is_vi else expl_en}'
                    f'<br><span style="color:#888;font-size:11px">'
                    f'{"DCF: " + (str(round(dcf_val)) if dcf_val else "N/A") + " | PE: " + (str(round(pe_fair)) if pe_fair else "N/A") + " | PB: " + (str(round(pb_fair)) if pb_fair else "N/A")}'
                    f'</span></div>', unsafe_allow_html=True)

            if eps == 0:
                st.caption("ℹ️ EPS/BVPS ước tính từ giá thị trường / P/E ngành (thiếu dữ liệu tài chính).")

            # Model cards — only show active models
            if val_method["use_ddm"]:
                # ENH-34: P/B 70%, DDM 30% for banks (SSI Research standard)
                active = [(L["sp_pb_label"], pb_fair, "70% (Banking P/B)"),
                           ("🏦 DDM (Confirmation)", ddm_val, "30%")]
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

        # ENH-V25: Show per-dimension explanations
        risk_expl = risk_scores.get("_explanations", {})
        if risk_expl:
            st.markdown("**" + ("📝 Giải thích chi tiết từng chiều rủi ro:" if is_vi else "📝 Per-dimension risk explanations:") + "**")
            for key, label in rl.items():
                if key in risk_expl:
                    expl_dict = risk_expl[key]
                    expl_text = expl_dict.get("VI" if is_vi else "EN", "")
                    if expl_text:
                        score_v = risk_scores.get(key, 5.0)
                        color_e = "#00cc44" if score_v <= 3 else "#ffaa00" if score_v <= 6 else "#ff4444"
                        st.markdown(
                            f'<div style="background:#111827;border-left:3px solid {color_e};'
                            f'border-radius:6px;padding:8px 12px;margin:3px 0;font-size:12px">'
                            f'<b style="color:{color_e}">{label} ({score_v:.0f}/10)</b><br>'
                            f'<span style="color:#ccc">{expl_text}</span></div>',
                            unsafe_allow_html=True)

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

# ══════════════════════════════════════════════════════════════
#  ENH-35: GEOPOLITICAL & MACRO CONTEXT ENGINE
# ══════════════════════════════════════════════════════════════
_GEO_RISK_KEYWORDS = {
    "trade_war":     {"score": -15, "affected": ["Xuất khẩu", "Công nghệ", "Thép", "Dệt may"]},
    "usd_strong":    {"score": -8,  "affected": ["Dầu khí", "Thép", "Dược", "Bán lẻ"]},
    "china_slowdown":{"score": -12, "affected": ["Thép", "Dầu khí", "Logistics"]},
    "fed_hike":      {"score": -10, "affected": ["Ngân hàng", "Bất động sản", "Chứng khoán"]},
    "fed_cut":       {"score": +10, "affected": ["Ngân hàng", "Bất động sản", "Chứng khoán"]},
    "vn_upgrade":    {"score": +15, "affected": ["Ngân hàng", "Bất động sản", "Chứng khoán"]},
    "oil_spike":     {"score": -5,  "affected": ["Hàng không", "Vận tải", "Phân bón"]},
    "oil_drop":      {"score": -3,  "affected": ["Dầu khí", "PVD", "GAS"]},
    "risk_off":      {"score": -8,  "affected": ["Toàn thị trường"]},
    "risk_on":       {"score": +8,  "affected": ["Toàn thị trường"]},
}

def get_geopolitical_context(sector: str = None) -> dict:
    """
    ENH-35 (v24): Comprehensive macro context including:
    - World markets (DXY, S&P500, Oil, Gold)
    - AI economy impact on sectors
    - Vietnam-specific market characteristics
    - VN stock money flow (retail-dominated, T+2, margin call pressure)
    """
    score_adj = 0
    reasons = []

    # DXY signal
    dxy_lvl   = st.session_state.get("_world_dxy_level", None)
    sp500_chg = st.session_state.get("_world_sp500_chg", 0)
    oil_chg   = st.session_state.get("_world_oil_chg", 0)
    gold_chg  = st.session_state.get("_world_gold_chg", 0)

    if dxy_lvl:
        if dxy_lvl >= 108:
            score_adj -= 10
            reasons.append(f"🔴 DXY={dxy_lvl:.1f} (Rất cao ≥108) — VNĐ yếu, dòng vốn ngoại rút khỏi EM")
        elif dxy_lvl >= 105:
            score_adj -= 5
            reasons.append(f"🟡 DXY={dxy_lvl:.1f} (Cao ≥105) — Áp lực nhẹ lên VNĐ")
        elif dxy_lvl <= 100:
            score_adj += 5
            reasons.append(f"🟢 DXY={dxy_lvl:.1f} (Thấp ≤100) — VNĐ được hỗ trợ, dòng vốn ngoại tích cực")

    if sp500_chg:
        if sp500_chg > 1.5:
            score_adj += 5
            reasons.append(f"🟢 S&P500 +{sp500_chg:.1f}% — Khẩu vị rủi ro tốt, vốn ngoại có thể vào VN")
        elif sp500_chg < -1.5:
            score_adj -= 5
            reasons.append(f"🔴 S&P500 {sp500_chg:.1f}% — Risk-off toàn cầu, áp lực bán ngoại")

    if oil_chg:
        if oil_chg > 3:
            score_adj -= 3
            reasons.append(f"🟡 Dầu +{oil_chg:.1f}% — Chi phí logistics/sản xuất tăng")
        elif oil_chg < -3:
            score_adj -= 2
            reasons.append(f"🟡 Dầu {oil_chg:.1f}% — Ngành dầu khí (GAS/PVD) bất lợi")

    if gold_chg and gold_chg > 2:
        score_adj -= 3
        reasons.append(f"🟡 Vàng +{gold_chg:.1f}% — Tín hiệu risk-off, nhà đầu tư trú ẩn an toàn")

    # ── ENH-35 v24: AI Economy Impact ─────────────────────────────────
    _ai_sectors_benefit = {"Công nghệ", "Chứng khoán"}
    _ai_sectors_disrupt  = {"Bán lẻ", "Thực phẩm", "Dược", "Bảo hiểm"}
    if sector in _ai_sectors_benefit:
        score_adj += 4
        reasons.append(f"🤖 AI Economy: Ngành {sector} hưởng lợi trực tiếp từ làn sóng chuyển đổi AI (FPT AI Lab, fintech AI)")
    elif sector in _ai_sectors_disrupt:
        reasons.append(f"⚙️ AI Economy: Ngành {sector} đang chuyển đổi mô hình kinh doanh — rủi ro gián đoạn trung hạn")

    # ── ENH-35 v24: Vietnam-Specific Market Characteristics ───────────
    # VN market: 95%+ retail-dominated → high volatility, herding, momentum-driven
    reasons.append("🇻🇳 TTCK VN: Thị trường nhà đầu tư cá nhân (~95%) — biến động cao, tâm lý bầy đàn mạnh, momentum đóng vai trò lớn")

    # T+2 and margin dynamics
    reasons.append("📅 T+2: Thanh toán sau 2 phiên → áp lực margin call cuối tuần (Thứ 5/6 thường biến động)")

    # Foreign ownership room
    reasons.append("🌐 Room ngoại: Kiểm tra % sở hữu nước ngoài — khi gần đầy room, cổ phiếu trở nên khan hiếm với khối ngoại")

    # Credit growth and liquidity
    reasons.append("💧 Thanh khoản: Tăng trưởng tín dụng 2025–2026 mục tiêu 14-16% → hỗ trợ dòng tiền vào BĐS, NH")

    # VN economic fundamentals 2025–2026
    reasons.append("📊 Kinh tế VN: GDP 2025 dự báo 6.5–7.5%, FDI >15tỷ USD — nền tảng vĩ mô tích cực")
    reasons.append("🏭 Xuất khẩu: Điện tử, dệt may, gỗ — phụ thuộc kinh tế Mỹ/EU. Rủi ro thuế quan Mỹ cần theo dõi")

    # Sector-specific adjustments
    if sector:
        _IMPORT_HEAVY = {"Thép", "Dầu khí", "Hàng không", "Bán lẻ", "Thực phẩm", "Dược"}
        _BANK = {"Ngân hàng", "Bảo hiểm"}
        _EXPORT = {"Công nghệ", "Thép", "Xây dựng"}
        if dxy_lvl and dxy_lvl > 106 and sector in _IMPORT_HEAVY:
            score_adj -= 5
            reasons.append(f"🔴 USD mạnh đặc biệt bất lợi cho ngành {sector} (nhập khẩu nhiều)")
        if sp500_chg and sp500_chg < -2 and sector in _BANK:
            score_adj -= 3
            reasons.append(f"🔴 Risk-off toàn cầu bất lợi cho {sector}")
        if sector in _EXPORT:
            reasons.append(f"📦 Ngành {sector}: Hưởng lợi từ tăng trưởng xuất khẩu — theo dõi đơn hàng quý tới")

    return {
        "score_adj": score_adj,
        "reasons": reasons,
        "summary": ("⚠️ Môi trường vĩ mô bất lợi" if score_adj < -8
                    else "✅ Môi trường vĩ mô thuận lợi" if score_adj > 5
                    else "➡️ Môi trường vĩ mô trung tính"),
    }



# ══════════════════════════════════════════════════════════════
#  ENH-V25: MARKET INSIGHTS — Daily briefing on app open
# ══════════════════════════════════════════════════════════════
def render_market_insights_panel():
    """
    ENH-V25: Auto market insights displayed every time the app opens.
    Combines VN-Index level, global macro context, and session guidance.
    """
    is_vi = st.session_state.lang == "VI"
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)

    # Only show once per session (collapse if already shown)
    if "insights_shown" not in st.session_state:
        st.session_state.insights_shown = False

    expanded_default = not st.session_state.insights_shown

    with st.expander(
        "🌅 " + ("Nhận định Thị trường Hôm nay — " if is_vi else "Today's Market Insights — ") +
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        expanded=expanded_default):

        st.session_state.insights_shown = True

        geo = get_geopolitical_context()
        dxy_lvl   = st.session_state.get("_world_dxy_level", None)
        sp500_chg = st.session_state.get("_world_sp500_chg", 0) or 0
        oil_chg   = st.session_state.get("_world_oil_chg", 0)   or 0
        gold_chg  = st.session_state.get("_world_gold_chg", 0)  or 0
        vni_chg   = st.session_state.get("_world_vni_chg", 0)   or 0

        # Overall sentiment
        macro_score = geo["score_adj"]
        if macro_score >= 8:
            sentiment_vi = "🟢 Tích cực — Dòng tiền ngoại thuận lợi, khẩu vị rủi ro tốt"
            sentiment_en = "🟢 Positive — Favourable foreign flows, good risk appetite"
            snt_color = "#00cc44"
        elif macro_score >= 2:
            sentiment_vi = "🟡 Thận trọng — Môi trường hỗn hợp, chọn lọc ngành"
            sentiment_en = "🟡 Cautious — Mixed environment, be selective"
            snt_color = "#ffaa00"
        elif macro_score >= -5:
            sentiment_vi = "🟠 Trung tính — Không có tín hiệu rõ ràng, giảm tỷ trọng"
            sentiment_en = "🟠 Neutral — No clear signal, reduce exposure"
            snt_color = "#ff8800"
        else:
            sentiment_vi = "🔴 Tiêu cực — Áp lực bán từ ngoại, risk-off toàn cầu"
            sentiment_en = "🔴 Negative — Foreign selling pressure, global risk-off"
            snt_color = "#ff4444"

        st.markdown(
            f'<div class="insight-card">'
            f'<h4>{"Tâm lý thị trường tổng thể" if is_vi else "Overall Market Sentiment"}</h4>'
            f'<p style="color:{snt_color};font-size:15px;font-weight:bold">'
            f'{sentiment_vi if is_vi else sentiment_en}</p>'
            f'<p style="color:#888;font-size:11px">Macro Score: {macro_score:+.0f} | '
            f'{datetime.now().strftime("%A, %d %B %Y")}</p>'
            f'</div>', unsafe_allow_html=True)

        # Individual macro indicators
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            dxy_str = f"{dxy_lvl:.1f}" if dxy_lvl else "N/A"
            dxy_color = "#ff4444" if (dxy_lvl and dxy_lvl >= 106) else ("#ffaa00" if dxy_lvl and dxy_lvl >= 103 else "#00cc44")
            st.markdown(
                f'<div class="insight-card">'
                f'<h4>💵 DXY (USD Index)</h4>'
                f'<p style="color:{dxy_color};font-size:18px;font-weight:bold">{dxy_str}</p>'
                f'<p>{"≥106: Bất lợi mạnh cho EM" if dxy_lvl and dxy_lvl >= 106 else ("103–106: Áp lực vừa" if dxy_lvl and dxy_lvl >= 103 else "≤103: Thuận lợi cho VN") if dxy_lvl else ""}</p>'
                f'</div>', unsafe_allow_html=True)

        with col2:
            sp_color = "#00cc44" if sp500_chg > 0.5 else ("#ff4444" if sp500_chg < -0.5 else "#888")
            st.markdown(
                f'<div class="insight-card">'
                f'<h4>📈 S&P500</h4>'
                f'<p style="color:{sp_color};font-size:18px;font-weight:bold">{sp500_chg:+.1f}%</p>'
                f'<p>{"Tốt — risk appetite tăng" if sp500_chg > 1 else ("Xấu — risk-off" if sp500_chg < -1 else "Trung tính") if is_vi else ("Good — risk-on" if sp500_chg > 1 else ("Bad — risk-off" if sp500_chg < -1 else "Neutral"))}</p>'
                f'</div>', unsafe_allow_html=True)

        with col3:
            oil_color = "#ffaa00" if abs(oil_chg) > 2 else "#888"
            st.markdown(
                f'<div class="insight-card">'
                f'<h4>🛢️ {"Dầu WTI" if is_vi else "WTI Oil"}</h4>'
                f'<p style="color:{oil_color};font-size:18px;font-weight:bold">{oil_chg:+.1f}%</p>'
                f'<p>{"GAS/PVD tăng" if oil_chg > 2 else ("HVN/VJC chi phí tăng" if oil_chg > 0 else "Dầu khí chịu áp lực") if is_vi else ("GAS/PVD benefit" if oil_chg > 2 else ("HVN/VJC cost pressure" if oil_chg > 0 else "Oil sector pressured"))}</p>'
                f'</div>', unsafe_allow_html=True)

        with col4:
            gold_color = "#ffaa00" if gold_chg > 1.5 else "#00cc44" if gold_chg < 0 else "#888"
            st.markdown(
                f'<div class="insight-card">'
                f'<h4>🪙 {"Vàng" if is_vi else "Gold"}</h4>'
                f'<p style="color:{gold_color};font-size:18px;font-weight:bold">{gold_chg:+.1f}%</p>'
                f'<p>{"PNJ/SJC hưởng lợi" if gold_chg > 1 else ("Rủi ro risk-off" if gold_chg > 2 else "Ổn định") if is_vi else ("PNJ/SJC benefit" if gold_chg > 1 else ("Risk-off warning" if gold_chg > 2 else "Stable"))}</p>'
                f'</div>', unsafe_allow_html=True)

        # Geo-political detailed reasons
        if geo["reasons"]:
            st.markdown("**" + ("🌍 Các yếu tố vĩ mô chi tiết:" if is_vi else "🌍 Macro Detail:") + "**")
            for r in geo["reasons"]:
                st.caption(r)

        # Session strategy
        now_h = datetime.now().hour
        now_m = datetime.now().minute
        now_total = now_h * 60 + now_m

        st.markdown("---")
        st.markdown("**" + ("⏰ Chiến lược theo khung giờ:" if is_vi else "⏰ Session Strategy:") + "**")
        if 9 * 60 <= now_total < 9 * 60 + 15:
            session_txt_vi = "🔔 Mở cửa ATO — Spread rộng, biến động cao. Tránh vào lệnh ngay. Quan sát tín hiệu 30 phút đầu."
            session_txt_en = "🔔 ATO Open — Wide spread, high volatility. Avoid entry. Observe first 30 minutes."
        elif 9 * 60 + 15 <= now_total < 11 * 60 + 30:
            session_txt_vi = "📊 Phiên sáng (9:15–11:30) — Quan sát và chờ tín hiệu xác nhận. Không mua đuổi."
            session_txt_en = "📊 Morning session (9:15–11:30) — Observe and wait for confirmation. Don't chase."
        elif 11 * 60 + 30 <= now_total < 13 * 60:
            session_txt_vi = "⏸️ Nghỉ trưa — Thời gian tốt để phân tích và chuẩn bị lệnh buổi chiều."
            session_txt_en = "⏸️ Lunch break — Good time to analyse and prepare afternoon orders."
        elif 13 * 60 <= now_total <= 14 * 60:
            session_txt_vi = "⭐ CỬA SỔ VÀNG (13:00–14:00) — Biến động giảm, khối lượng xác nhận. Thời điểm tốt nhất để vào lệnh."
            session_txt_en = "⭐ GOLDEN WINDOW (13:00–14:00) — Volatility subsides, volume confirms. Best entry window."
        elif 14 * 60 < now_total <= 14 * 60 + 30:
            session_txt_vi = "💰 Chốt lời (14:00–14:30) — Cân nhắc bán nếu đã đạt TP1. Đặt lệnh ATC nếu cần."
            session_txt_en = "💰 Profit-taking (14:00–14:30) — Consider selling if TP1 reached. Place ATC if needed."
        elif now_total > 14 * 60 + 30:
            session_txt_vi = "🔒 Sau ATC — Phiên đã đóng. Phân tích kết quả và chuẩn bị cho phiên kế tiếp."
            session_txt_en = "🔒 Post-ATC — Session closed. Analyse results and prepare for next session."
        else:
            session_txt_vi = "⏳ Trước giờ mở cửa — Phân tích thị trường quốc tế, chuẩn bị danh sách theo dõi."
            session_txt_en = "⏳ Pre-market — Analyse global markets, prepare watchlist."

        st.info(session_txt_vi if is_vi else session_txt_en)

        # Top sector recommendation
        sector_recs_vi = []
        sector_recs_en = []
        if sp500_chg > 1:
            sector_recs_vi.append("✅ Ngân hàng, Chứng khoán — hưởng lợi từ risk-on toàn cầu")
            sector_recs_en.append("✅ Banking, Securities — benefit from global risk-on")
        if oil_chg > 2:
            sector_recs_vi.append("✅ Dầu khí (GAS, PVD, PVS) — dầu tăng hỗ trợ")
            sector_recs_en.append("✅ Oil & Gas (GAS, PVD, PVS) — supported by oil price")
        if dxy_lvl and dxy_lvl >= 106:
            sector_recs_vi.append("⚠️ Giảm tỷ trọng ngành nhập khẩu nhiều (Thép, Dược, Bán lẻ)")
            sector_recs_en.append("⚠️ Reduce import-heavy sectors (Steel, Pharma, Retail)")
        if gold_chg > 1.5:
            sector_recs_vi.append("✅ PNJ, SJC — vàng tăng hỗ trợ")
            sector_recs_en.append("✅ PNJ, SJC — gold price supportive")
        if sector_recs_vi or sector_recs_en:
            recs = sector_recs_vi if is_vi else sector_recs_en
            st.markdown("**" + ("📌 Khuyến nghị ngành hôm nay:" if is_vi else "📌 Sector recommendations today:") + "**")
            for r in recs: st.caption(r)


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



# ══════════════════════════════════════════════════════════════
#  ENH-36: MODEL PORTFOLIOS (iFollow-style)
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  ENH-V25: UNIVERSAL AUDIT LOG TAB
# ══════════════════════════════════════════════════════════════
def render_audit_log_tab():
    """
    ENH-V25: Comprehensive audit log for ALL app actions.
    Shows every scan, profiler run, forecast, portfolio, ML run etc.
    Enables comparison of recommendations vs actual market outcomes.
    """
    is_vi = st.session_state.lang == "VI"
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
    st.header("📋 " + ("Nhật Ký Toàn Diện — Audit Log" if is_vi else "Universal Audit Log"))
    st.caption("📌 " + (
        "Ghi lại MỌI hành động phân tích: scan, profiler, dự báo, danh mục, ML — "
        "để audit, so sánh khuyến nghị với diễn biến thực tế."
        if is_vi else
        "Records EVERY analysis action: scans, profiler, forecasts, portfolios, ML — "
        "for audit and comparison of recommendations against actual market outcomes."))

    # Load from session + disk
    mem_log = st.session_state.get("audit_log", [])
    if not mem_log:
        disk_log = load_audit_from_disk()
        if disk_log:
            st.session_state.audit_log = disk_log
            mem_log = disk_log

    # ── Filters ──────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        cat_filter = st.selectbox("📂 " + ("Loại" if is_vi else "Category"),
                                   ["ALL"] + AUDIT_CATEGORIES)
    with col_f2:
        sig_filter = st.selectbox("🎯 " + ("Tín hiệu" if is_vi else "Signal"),
                                   ["ALL", "MUA", "BUY", "BÁN", "SELL", "THEO DÕI", "WATCH", "UP", "DOWN"])
    with col_f3:
        ticker_filter = st.text_input("🔍 Ticker", "").upper()
    with col_f4:
        date_filter = st.text_input("📅 " + ("Ngày (YYYY-MM-DD)" if is_vi else "Date (YYYY-MM-DD)"), "")

    # ── Stats summary ────────────────────────────────────────
    total = len(mem_log)
    buy_ct  = sum(1 for e in mem_log if e.get("signal") in ("MUA","BUY","UP"))
    sell_ct = sum(1 for e in mem_log if e.get("signal") in ("BÁN","SELL","DOWN"))
    cat_ct  = len(set(e.get("category","") for e in mem_log))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📊 " + ("Tổng ghi" if is_vi else "Total entries"), total)
    m2.metric("🟢 " + ("Khuyến nghị MUA/UP" if is_vi else "BUY/UP recs"), buy_ct)
    m3.metric("🔴 " + ("Khuyến nghị BÁN/DOWN" if is_vi else "SELL/DOWN recs"), sell_ct)
    m4.metric("📂 " + ("Loại hoạt động" if is_vi else "Action categories"), cat_ct)
    m5.metric("💾 " + ("Lưu đĩa" if is_vi else "On disk"), "✅" if os.path.exists(os.path.join(DATA_DIR, "audit_log.jsonl")) else "❌")

    # ── Filter application ───────────────────────────────────
    filtered = mem_log
    if cat_filter != "ALL":
        filtered = [e for e in filtered if e.get("category") == cat_filter]
    if sig_filter != "ALL":
        filtered = [e for e in filtered if e.get("signal","").upper() == sig_filter.upper()]
    if ticker_filter:
        filtered = [e for e in filtered if ticker_filter in e.get("ticker","").upper()]
    if date_filter:
        filtered = [e for e in filtered if e.get("date","").startswith(date_filter)]

    st.caption(f"🔎 {len(filtered)}/{total} " + ("mục sau lọc" if is_vi else "entries after filter"))

    # ── Download buttons ─────────────────────────────────────
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if filtered:
            import json as _json
            dl_rows = []
            for e in filtered[:1000]:
                row = {k: v for k, v in e.items() if k != "details"}
                details = e.get("details", {})
                # Flatten important details
                for dk in ["confirms", "score", "rsi", "adx", "sma50", "ema50", "atr",
                            "stop_loss", "tp1", "tp2", "fair_val", "upside_pct",
                            "composite_score", "mom_score"]:
                    if dk in details:
                        row[f"detail_{dk}"] = details[dk]
                dl_rows.append(row)
            df_dl = pd.DataFrame(dl_rows)
            csv = df_dl.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 " + ("Tải CSV (đầy đủ)" if is_vi else "Download CSV (full)"),
                csv,
                f"audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
    with col_dl2:
        if st.button("🗑️ " + ("Xoá log phiên" if is_vi else "Clear session log")):
            st.session_state.audit_log = []
            st.success("✅ " + ("Đã xoá log phiên (file đĩa giữ nguyên)" if is_vi else "Session log cleared (disk file preserved)"))
            st.rerun()

    st.markdown("---")

    # ── Entry display ────────────────────────────────────────
    if not filtered:
        st.info("📭 " + ("Chưa có mục nào. Chạy quét / phân tích để tạo audit entries." if is_vi
                          else "No entries yet. Run scans/analyses to generate audit entries."))
        st.markdown("**" + ("Các nguồn tạo audit log:" if is_vi else "Sources that generate audit entries:") + "**")
        sources = [
            "📊 Scanner — mỗi lần quét watchlist",
            "🧬 Profiler — mỗi lần phân tích mã",
            "🔬 Full Analysis — Deep Audit",
            "🔮 Top Forecast — mỗi lần chạy dự báo",
            "💼 Model Portfolios — mỗi lần xây danh mục",
            "🧠 ML Forecast — mỗi lần chạy mô hình",
        ] if is_vi else [
            "📊 Scanner — every watchlist scan",
            "🧬 Profiler — every ticker analysis",
            "🔬 Full Analysis — Deep Audit",
            "🔮 Top Forecast — every forecast run",
            "💼 Model Portfolios — every portfolio build",
            "🧠 ML Forecast — every model run",
        ]
        for s in sources: st.caption(s)
        return

    # Paginate
    PAGE_SIZE = 30
    total_pages = max(1, (len(filtered) - 1) // PAGE_SIZE + 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1) - 1
    page_entries = filtered[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    for entry in page_entries:
        sig  = entry.get("signal", "")
        css_cls = ("buy"  if sig in ("MUA","BUY","UP")    else
                   "sell" if sig in ("BÁN","SELL","DOWN") else "info")
        cat  = entry.get("category", "")
        tick = entry.get("ticker", "")
        ts   = entry.get("ts", "")
        sc   = entry.get("score", 0)
        details = entry.get("details", {})

        # Quick metrics from details
        detail_str_parts = []
        for dk, dlbl in [("rsi","RSI"), ("adx","ADX"), ("composite_score","CmpScore"),
                          ("mom_score","MomScore"), ("fair_val","FairVal"),
                          ("upside_pct","Upside"), ("stop_loss","SL"), ("tp1","TP1"),
                          ("confirms","Confirms")]:
            if dk in details and details[dk] is not None:
                v = details[dk]
                if isinstance(v, float): detail_str_parts.append(f"{dlbl}:{v:.1f}")
                else: detail_str_parts.append(f"{dlbl}:{v}")
        detail_inline = " | ".join(detail_str_parts[:6]) if detail_str_parts else "–"

        sig_icon = {"MUA":"🟢","BUY":"🟢","UP":"🟢","BÁN":"🔴","SELL":"🔴","DOWN":"🔴"}.get(sig,"🟡")

        st.markdown(
            f'<div class="audit-entry {css_cls}">'
            f'<b style="color:#ddd">[{ts}]</b> '
            f'<span style="color:#4e9af1">[{cat}]</span> '
            f'<b style="font-size:14px">{tick}</b> '
            f'{sig_icon} <b style="color:{"#00cc44" if css_cls=="buy" else "#ff4444" if css_cls=="sell" else "#888"}">{sig}</b>'
            f' | Score: {sc:.0f}'
            f'<br><span style="color:#888;font-size:11px">{detail_inline}</span>'
            f'</div>', unsafe_allow_html=True)

        # Full detail expander
        with st.expander(f"🔍 {'Chi tiết' if is_vi else 'Details'}: {tick} @ {ts[:16]}", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**" + ("Thông tin cơ bản:" if is_vi else "Basic Info:") + "**")
                st.write({k: v for k, v in entry.items() if k != "details"})
            with col_b:
                if details:
                    st.markdown("**" + ("Chi tiết phân tích:" if is_vi else "Analysis Details:") + "**")
                    # Show details in a readable format
                    for dk, dv in sorted(details.items()):
                        if isinstance(dv, (int, float)):
                            st.write(f"• **{dk}**: {dv:,.2f}" if isinstance(dv, float) else f"• **{dk}**: {dv}")
                        elif isinstance(dv, str) and len(dv) < 200:
                            st.write(f"• **{dk}**: {dv}")
                        elif isinstance(dv, list) and len(dv) <= 10:
                            st.write(f"• **{dk}**: {', '.join(str(x) for x in dv[:5])}")

    # ── Audit comparison section ─────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 " + ("So sánh Khuyến nghị vs Thực tế" if is_vi else "Recommendation vs Actual Comparison"))
    st.caption("ℹ️ " + (
        "Nhập giá thực tế để tính hiệu quả khuyến nghị. Dùng để đánh giá độ chính xác dự báo."
        if is_vi else
        "Enter actual prices to calculate recommendation effectiveness. Used to evaluate forecast accuracy."))

    ticker_cmp = st.text_input("🎯 " + ("Mã để so sánh:" if is_vi else "Ticker to compare:"), key="audit_cmp_ticker").upper()
    if ticker_cmp:
        matching = [e for e in mem_log if e.get("ticker") == ticker_cmp]
        if matching:
            st.write(f"Found {len(matching)} audit entries for {ticker_cmp}")
            cmp_cols = st.columns(min(len(matching[:5]), 5))
            for i, e in enumerate(matching[:5]):
                with cmp_cols[i % 5]:
                    e_price = e.get("details", {}).get("close") or e.get("details", {}).get("price")
                    e_sig   = e.get("signal", "")
                    e_tp1   = e.get("details", {}).get("tp1")
                    st.metric(
                        f"{e_sig} @ {e.get('ts','')[:10]}",
                        f"{e_price:,.0f}" if e_price else "N/A",
                        f"TP1: {e_tp1:,.0f}" if e_tp1 else None)
        else:
            st.info(f"No audit entries for {ticker_cmp}")


def render_model_portfolios_tab():
    """
    ENH-36: iFollow-style Model Portfolios.
    Auto-suggest portfolios based on risk profile (Growth/Balanced/Defensive/Dividend).
    SSI iBoard-inspired: copy-trading concept with quant scoring.
    """
    is_vi = st.session_state.lang == "VI"
    st.header("💼 " + ("Model Portfolios — Danh Mục Mẫu (iFollow Style)" if is_vi
                        else "Model Portfolios (iFollow Style)"))
    st.caption("📌 " + ("Lấy cảm hứng từ SSI iFollow: Khuyến nghị danh mục tự động dựa trên khẩu vị rủi ro."
                          if is_vi else
                          "Inspired by SSI iFollow: Auto-recommended portfolios based on risk appetite."))

    # Portfolio definitions
    PORTFOLIOS = {
        "🚀 " + ("Tăng trưởng" if is_vi else "Growth"): {
            "desc": "Ưu tiên cổ phiếu tăng trưởng cao, P/E ≤ ngành, ROE > 15%" if is_vi
                    else "High growth stocks, P/E ≤ sector, ROE > 15%",
            "risk": "Cao" if is_vi else "High",
            "horizon": "12–24 tháng" if is_vi else "12–24 months",
            "sectors": ["Công nghệ", "Bán lẻ", "Bất động sản"],
            "criteria": {"min_roe": 15, "max_pe": 25, "min_score": 60, "avoid_sectors": []},
            "color": "#ff6622",
            "allocation": {"Cổ phiếu" if is_vi else "Equities": 90,
                           "Tiền mặt" if is_vi else "Cash": 10},
        },
        "⚖️ " + ("Cân bằng" if is_vi else "Balanced"): {
            "desc": "Kết hợp cổ tức và tăng trưởng, phân tán ngành rộng" if is_vi
                    else "Mix of dividend and growth, broad sector diversification",
            "risk": "Trung bình" if is_vi else "Medium",
            "horizon": "6–12 tháng" if is_vi else "6–12 months",
            "sectors": ["Ngân hàng", "Công nghệ", "Thực phẩm", "Điện"],
            "criteria": {"min_roe": 10, "max_pe": 20, "min_score": 50, "avoid_sectors": []},
            "color": "#4e9af1",
            "allocation": {"Cổ phiếu" if is_vi else "Equities": 70,
                           "Trái phiếu/CK" if is_vi else "Bonds/MM": 20,
                           "Tiền mặt" if is_vi else "Cash": 10},
        },
        "🛡️ " + ("An toàn" if is_vi else "Defensive"): {
            "desc": "Cổ phiếu vốn hóa lớn, ổn định, beta thấp" if is_vi
                    else "Large-cap, stable, low-beta stocks",
            "risk": "Thấp" if is_vi else "Low",
            "horizon": "3–6 tháng" if is_vi else "3–6 months",
            "sectors": ["Ngân hàng", "Thực phẩm", "Điện", "Dược"],
            "criteria": {"min_roe": 8, "max_pe": 18, "min_score": 40, "avoid_sectors": ["Bất động sản", "Dầu khí"]},
            "color": "#44cc88",
            "allocation": {"Cổ phiếu" if is_vi else "Equities": 50,
                           "Trái phiếu" if is_vi else "Bonds": 30,
                           "Tiền mặt" if is_vi else "Cash": 20},
        },
        "💵 " + ("Cổ tức" if is_vi else "Dividend"): {
            "desc": "Ưu tiên cổ phiếu trả cổ tức cao, ổn định thu nhập" if is_vi
                    else "High dividend yield, stable income generation",
            "risk": "Thấp–Trung bình" if is_vi else "Low–Medium",
            "horizon": "1–3 năm" if is_vi else "1–3 years",
            "sectors": ["Ngân hàng", "Điện", "Dầu khí", "Thực phẩm"],
            "criteria": {"min_roe": 10, "max_pe": 15, "min_score": 45, "avoid_sectors": ["Bất động sản"]},
            "color": "#f1a84e",
            "allocation": {"Cổ phiếu cổ tức" if is_vi else "Dividend stocks": 80,
                           "Tiền mặt" if is_vi else "Cash": 20},
        },
    }

    # Capital input
    st.markdown("### 💰 " + ("Thông tin vốn đầu tư" if is_vi else "Investment Capital"))
    col_cap, col_risk = st.columns(2)
    with col_cap:
        capital = st.number_input(
            "💰 " + ("Vốn đầu tư (VNĐ)" if is_vi else "Capital (VND)"),
            min_value=30_000_000, max_value=10_000_000_000,
            value=100_000_000, step=10_000_000, format="%d")
    with col_risk:
        pf_choice = st.selectbox(
            "🎯 " + ("Khẩu vị rủi ro" if is_vi else "Risk Profile"),
            list(PORTFOLIOS.keys()))

    pf = PORTFOLIOS[pf_choice]
    geo = get_geopolitical_context()

    # Portfolio summary card
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.markdown(f"""
<div style="background:{pf['color']}15;border:1px solid {pf['color']};border-radius:10px;padding:16px">
<h4 style="color:{pf['color']};margin:0">{pf_choice}</h4>
<p style="color:#ccc;margin:4px 0">{pf['desc']}</p>
<p style="color:#aaa;font-size:12px">
  ⚠️ {'Rủi ro' if is_vi else 'Risk'}: <b>{pf['risk']}</b> &nbsp;|&nbsp;
  ⏱️ {'Chân trời' if is_vi else 'Horizon'}: <b>{pf['horizon']}</b> &nbsp;|&nbsp;
  💰 {'Vốn tối thiểu 30M VNĐ' if is_vi else 'Min capital 30M VND'}
</p>
</div>""", unsafe_allow_html=True)

    with col_r:
        if geo["reasons"]:
            st.markdown("**🌍 " + ("Bối cảnh vĩ mô:" if is_vi else "Macro Context:") + "**")
            for r in geo["reasons"][:3]:
                st.caption(r)
        geo_adj = geo["score_adj"]
        if geo_adj < -5:
            st.warning("⚠️ " + ("Môi trường vĩ mô bất lợi — Giảm tỷ trọng CP" if is_vi
                                  else "Adverse macro — Reduce equity weighting"))

    # Allocation pie
    st.markdown("### 📊 " + ("Phân bổ tài sản đề xuất" if is_vi else "Suggested Asset Allocation"))
    alloc_cols = st.columns(len(pf["allocation"]))
    total_alloc = sum(pf["allocation"].values())
    for col, (asset, pct) in zip(alloc_cols, pf["allocation"].items()):
        with col:
            amt = capital * (pct / 100)
            st.metric(asset, f"{pct}%", f"{amt:,.0f} VNĐ")

    # Stock scanner for portfolio
    st.markdown("### 🔍 " + ("Quét cổ phiếu phù hợp" if is_vi else "Scan Matching Stocks"))
    crit = pf["criteria"]

    if st.button("▶️ " + ("Quét & Tạo Danh Mục" if is_vi else "Scan & Build Portfolio"), type="primary"):
        watch_list = load_watchlist_from_file(WATCHLIST_FILE_PATH)
        candidates = []
        avoid_sectors = crit["avoid_sectors"]
        # FIX-27: Use relaxed min_score (40% of original) for initial pass
        relaxed_score = max(crit["min_score"] * 0.4, 10)

        with st.spinner("⏳ " + ("Đang quét tín hiệu..." if is_vi else "Scanning signals...")):
            pb = st.progress(0)
            for i, ticker in enumerate(watch_list):
                pb.progress((i+1)/len(watch_list), f"Scanning {ticker}...")
                try:
                    row, src, err = scan_one_ticker(ticker)
                    if not row: continue
                    sec = get_sector(ticker)
                    # FIX-27: Don't hard-filter by sector — use it as a preference score boost
                    if sec in avoid_sectors: continue
                    score = row.get(L["score"], 0) or 0
                    # FIX-27: Accept stocks in preferred sectors with relaxed score,
                    # or any sector with the original min_score
                    in_preferred = bool(pf["sectors"]) and sec in pf["sectors"]
                    effective_min = relaxed_score if in_preferred else crit["min_score"]
                    if score < effective_min: continue
                    # Try to get fundamental data (non-blocking)
                    try:
                        _ratios = fetch_cafef_key_ratios(ticker)
                    except Exception:
                        _ratios = {}
                    candidates.append({
                        "Ticker": ticker,
                        "Ngành" if is_vi else "Sector": sec,
                        "Preferred": "✅" if in_preferred else "–",
                        "Giá" if is_vi else "Price": row.get(L["price"], 0),
                        "Tín hiệu" if is_vi else "Signal": row.get(L["signal"], "–"),
                        "Score": score,
                        "RSI": row.get("RSI", "–"),
                        "ADX": row.get("ADX", "–"),
                        "SL": row.get("_stop", 0),
                        "TP1": row.get("_tp1", 0),
                        "TP2": row.get("_tp2", 0),
                        "R:R": row.get("R:R1", "–"),
                        "🌐 NN%": row.get("🌐 NN%", "–"),
                    })
                except Exception as e:
                    _log.debug(f"Portfolio scan {ticker}: {e}")
            pb.empty()

        # FIX-27: If still no results, loosen to any positive score stock in any sector
        if not candidates:
            st.info("⏳ " + ("Không tìm thấy mã khớp điều kiện chặt — Thử quét rộng hơn..." if is_vi
                              else "No stocks matched strict criteria — trying broader scan..."))
            for ticker in watch_list:
                try:
                    row, src, err = scan_one_ticker(ticker)
                    if not row: continue
                    sec = get_sector(ticker)
                    if sec in avoid_sectors: continue
                    score = row.get(L["score"], 0) or 0
                    if score < 5: continue  # minimum signal
                    candidates.append({
                        "Ticker": ticker,
                        "Ngành" if is_vi else "Sector": sec,
                        "Preferred": "✅" if (pf["sectors"] and sec in pf["sectors"]) else "–",
                        "Giá" if is_vi else "Price": row.get(L["price"], 0),
                        "Tín hiệu" if is_vi else "Signal": row.get(L["signal"], "–"),
                        "Score": score,
                        "RSI": row.get("RSI", "–"),
                        "ADX": row.get("ADX", "–"),
                        "SL": row.get("_stop", 0),
                        "TP1": row.get("_tp1", 0),
                        "TP2": row.get("_tp2", 0),
                        "R:R": row.get("R:R1", "–"),
                        "🌐 NN%": row.get("🌐 NN%", "–"),
                    })
                except Exception:
                    pass

        if not candidates:
            st.warning("⚠️ " + ("Không tìm thấy cổ phiếu phù hợp với tiêu chí." if is_vi
                                  else "No stocks match the portfolio criteria."))
        else:
            candidates.sort(key=lambda x: x["Score"], reverse=True)
            top_n = min(10, len(candidates))
            st.success(f"✅ " + (f"Tìm thấy {len(candidates)} mã — Hiển thị top {top_n}" if is_vi
                                   else f"Found {len(candidates)} tickers — Showing top {top_n}"))

            # Position sizing
            equity_pct = [v for k, v in pf["allocation"].items()
                           if "CP" in k.upper() or "EQUIT" in k.upper() or "CỔ" in k.upper()]
            equity_capital = capital * (equity_pct[0] / 100) if equity_pct else capital * 0.7
            per_stock = equity_capital / top_n

            df_pf = pd.DataFrame(candidates[:top_n])
            df_pf["Vốn/mã" if is_vi else "Capital/stock"] = f"{per_stock:,.0f}"
            df_pf["Lô (100cp)" if is_vi else "Lot(100s)"] = (
                df_pf["Giá" if is_vi else "Price"].apply(
                    lambda p: int(per_stock / (p * 100)) if p > 0 else 0))
            show_df(df_pf)

            st.caption("⚠️ " + ("Đây là gợi ý định lượng tự động, không phải tư vấn đầu tư. "
                                  "Vốn tối thiểu iFollow SSI: 30M VNĐ."
                                  if is_vi else
                                  "Automated quantitative suggestion, not financial advice. "
                                  "SSI iFollow minimum: 30M VND."))

    # Strategy explanation
    with st.expander("📚 " + ("Phương pháp lựa chọn" if is_vi else "Selection Methodology"), expanded=False):
        if is_vi:
            st.markdown("""
**Các tiêu chí lựa chọn:**
1. **Điểm Composite Score ≥ ngưỡng** — Dựa trên RSI, Bollinger Band, MACD, ADX, Stochastic, OBV
2. **Lọc ngành** — Theo khẩu vị rủi ro (Tăng trưởng → Tech/Retail, An toàn → Banks/Food)
3. **Position Sizing** — Vốn cổ phiếu ÷ số mã (phân bổ đều)
4. **Stop-Loss** = Giá - 1.5 × ATR | **TP1** = Giá + 2 × ATR | **TP2** = Giá + 3.5 × ATR

**Hệ thống 7 lệnh điều kiện (SSI):**
- Stop Loss: Đặt tại cột SL
- Take Profit 1 (TP1): Đặt tại cột TP1 — Chốt 50% vị thế
- Take Profit 2 (TP2): Đặt tại cột TP2 — Chốt 50% còn lại
- Trailing Stop: Điều chỉnh SL lên TP1 khi đạt TP1
""")
        else:
            st.markdown("""
**Selection criteria:**
1. **Composite Score ≥ threshold** — Based on RSI, Bollinger Band, MACD, ADX, Stochastic, OBV
2. **Sector filter** — Per risk appetite (Growth → Tech/Retail, Defensive → Banks/Food)
3. **Position Sizing** — Equity capital ÷ number of stocks (equal-weight)
4. **Stop-Loss** = Price - 1.5 × ATR | **TP1** = Price + 2 × ATR | **TP2** = Price + 3.5 × ATR

**7 Conditional Order Types (SSI-style):**
- Stop Loss: Set at SL column
- Take Profit 1 (TP1): Set at TP1 — Close 50% position
- Take Profit 2 (TP2): Set at TP2 — Close remaining 50%
- Trailing Stop: Move SL up to TP1 once TP1 is reached
""")


def _render_scanner_tech_panel(row: dict, is_vi: bool) -> None:
    """
    ENH-41 (v27): Render Technical Indicators & Price Derivation panel
    inside a scanner signal expander.  All data comes from the scan row dict.
    """
    # ── pull values ──────────────────────────────────────────────────────
    live      = row.get(L["price"], 0) or 0
    src_lbl   = row.get(L["source"], "–")
    rsi_v     = row.get("RSI", 0) or 0
    adx_v     = row.get("ADX", 0) or 0
    stoch_v   = row.get("Stoch%K", 0)
    vol_ratio = row.get("Vol/MA20", "–")
    bb_buy    = row.get("BB Buy", 0) or 0
    bb_sell   = row.get("BB Sell", 0) or 0
    sma5      = row.get("SMA5", "–")
    sma20     = row.get("SMA20", "–")
    sma50     = row.get("SMA50", "–")
    sma200    = row.get("SMA200", "–")
    ema9      = row.get("EMA9", "–")
    ema21     = row.get("EMA21", "–")
    atr_v     = row.get("_atr", 0) or 0
    _rb       = row.get("_rec_buy", 0) or 0
    _rt1      = row.get("_rec_sell_tp1", 0) or 0
    _rt2      = row.get("_rec_sell_tp2", 0) or 0
    _rst      = row.get("_rec_stop", 0) or 0
    ceil_v    = row.get("Trần" if is_vi else "Ceil", "–")
    floor_v   = row.get("Sàn" if is_vi else "Floor", "–")
    sig       = row.get(L["signal"], "WATCH")
    confirms  = row.get("Confirms", 0)
    nn_pct    = row.get("🌐 NN%", "–")
    atr_pct   = round(atr_v / live * 100, 2) if live > 0 and atr_v > 0 else 0

    # ── RSI colour helper ────────────────────────────────────────────────
    def rsi_color(r):
        if r < 30: return "#00cc66"
        if r < 40: return "#66cc88"
        if r > 70: return "#ff4444"
        if r > 60: return "#ffaa44"
        return "#aaaaaa"

    # ── ADX helper ───────────────────────────────────────────────────────
    def adx_label(a):
        if a >= 40: return ("Xu hướng rất mạnh 🔥" if is_vi else "Very Strong Trend 🔥")
        if a >= 25: return ("Xu hướng rõ ràng 📈"   if is_vi else "Clear Trend 📈")
        if a >= 15: return ("Tích lũy / yếu"         if is_vi else "Accumulation / Weak")
        return ("Sideway / không xu hướng" if is_vi else "Sideways / No Trend")

    # ── BB band position ────────────────────────────────────────────────
    bb_range   = (bb_sell - bb_buy) if (bb_sell > bb_buy) else 1
    bb_pos_pct = round((live - bb_buy) / bb_range * 100, 1) if bb_range > 0 else 50
    if bb_pos_pct < 20:
        bb_zone = ("⬇️ Vùng quá bán BB" if is_vi else "⬇️ BB Oversold Zone")
        bb_col  = "#00cc66"
    elif bb_pos_pct > 80:
        bb_zone = ("⬆️ Vùng quá mua BB" if is_vi else "⬆️ BB Overbought Zone")
        bb_col  = "#ff4444"
    else:
        bb_zone = ("↔️ Giữa dải BB" if is_vi else "↔️ Mid BB Band")
        bb_col  = "#aaaaaa"

    # ── EMA9 vs EMA21 crossover ──────────────────────────────────────────
    ema_cross = "–"
    try:
        e9n = float(str(ema9).replace("–","") or 0)
        e21n = float(str(ema21).replace("–","") or 0)
        if e9n > 0 and e21n > 0:
            ema_cross = ("🟢 EMA9 > EMA21 (Bullish)" if e9n > e21n
                         else "🔴 EMA9 < EMA21 (Bearish)")
    except Exception:
        pass

    # ── SMA50 vs SMA200 (Golden / Death Cross) ───────────────────────────
    sma_cross = "–"
    try:
        s50n  = float(str(sma50).replace("–","")  or 0)
        s200n = float(str(sma200).replace("–","") or 0)
        if s50n > 0 and s200n > 0:
            sma_cross = ("🥇 Golden Cross: SMA50 > SMA200" if s50n > s200n
                         else "💀 Death Cross: SMA50 < SMA200")
    except Exception:
        pass

    # ── Price vs SMA50 ────────────────────────────────────────────────────
    price_vs_sma50 = "–"
    try:
        s50n = float(str(sma50).replace("–","") or 0)
        if s50n > 0:
            diff = round((live - s50n) / s50n * 100, 1)
            price_vs_sma50 = (f"{'▲' if diff>=0 else '▼'} {abs(diff)}% {'trên' if is_vi else 'above'} SMA50"
                              if diff >= 0 else
                              f"▼ {abs(diff)}% {'dưới' if is_vi else 'below'} SMA50")
    except Exception:
        pass

    # ── Price Derivation formulas ─────────────────────────────────────────
    if sig in ("MUA", "BUY"):
        deriv_buy  = f"BB Lower ({bb_buy:,.0f}) + 30% × ATR ({atr_v:,.0f}) = capped at Live ({live:,.0f})"
        deriv_tp1  = f"Live ({live:,.0f}) + 2.0 × ATR ({atr_v:,.0f})"
        deriv_tp2  = f"Live ({live:,.0f}) + 3.5 × ATR ({atr_v:,.0f})"
        deriv_stop = f"Live ({live:,.0f}) − 1.5 × ATR ({atr_v:,.0f})  [floor: 90% of Live]"
    elif sig in ("BÁN", "SELL"):
        deriv_buy  = f"BB Lower ({bb_buy:,.0f}) — Re-entry if price pulls back"
        deriv_tp1  = f"min(Live {live:,.0f}, BB Upper×0.995 {round(bb_sell*0.995):,.0f})"
        deriv_tp2  = f"BB Upper ({bb_sell:,.0f})"
        deriv_stop = f"Live ({live:,.0f}) + 1.5 × ATR ({atr_v:,.0f})  [protective short stop]"
    else:
        deriv_buy  = f"BB Lower ({bb_buy:,.0f}) — Potential entry on pullback"
        deriv_tp1  = f"Live ({live:,.0f}) + 2.0 × ATR ({atr_v:,.0f})"
        deriv_tp2  = f"BB Upper ({bb_sell:,.0f})"
        deriv_stop = f"Live ({live:,.0f}) − 1.5 × ATR ({atr_v:,.0f})  [floor: 90% of Live]"

    hdr_tc  = "📊 CHỈ SỐ KỸ THUẬT"   if is_vi else "📊 TECHNICAL INDICATORS"
    hdr_pd  = "🧮 PHÂN TÍCH GIÁ KHUYẾN NGHỊ" if is_vi else "🧮 PRICE RECOMMENDATION DERIVATION"
    lbl_src = "📡 Giá thực (SSI-RT)"   if is_vi else "📡 Live Price (SSI-RT)"
    lbl_bb  = "📉 Dải Bollinger"       if is_vi else "📉 Bollinger Bands"
    lbl_rsi = "💹 RSI (14)"
    lbl_adx = "📐 ADX (Xu hướng)"      if is_vi else "📐 ADX (Trend Strength)"
    lbl_stc = "🎯 Stochastic %K"
    lbl_vol = "📦 Volume / MA20"
    lbl_ema = "⚡ EMA Cross"
    lbl_sma = "📊 SMA Cross (GT/TC)"   if is_vi else "📊 SMA Cross (Golden/Death)"
    lbl_atr = "📏 ATR (14) — Cơ sở tính giá" if is_vi else "📏 ATR (14) — Price Calc Basis"
    lbl_nn  = "🌐 Tỷ lệ NĐTNN"         if is_vi else "🌐 Foreign Room"
    lbl_cf  = "✅ Xác nhận tín hiệu"   if is_vi else "✅ Signal Confirmations"
    lbl_lim = "🚧 Trần / Sàn sàn GD"  if is_vi else "🚧 Exchange Ceiling / Floor"

    st.markdown(f"**{hdr_tc}**")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_src}</div>'
            f'<div style="color:#7eb8ff;font-size:15px;font-weight:bold">{live:,.0f} VNĐ</div>'
            f'<div style="color:#666;font-size:11px">source: {src_lbl}</div>'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_rsi}</div>'
            f'<div style="color:{rsi_color(rsi_v)};font-size:15px;font-weight:bold">{rsi_v}</div>'
            f'<div style="color:#666;font-size:11px">'
            f'{"Quá bán 🟢" if rsi_v<35 else ("Quá mua 🔴" if rsi_v>65 else "Trung tính") if is_vi else ("Oversold 🟢" if rsi_v<35 else ("Overbought 🔴" if rsi_v>65 else "Neutral"))}'
            f'</div></div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_stc}</div>'
            f'<div style="color:#bbaaff;font-size:15px;font-weight:bold">{stoch_v}</div>'
            f'<div style="color:#666;font-size:11px">'
            f'{"<20 = quá bán | >80 = quá mua" if is_vi else "<20 = oversold | >80 = overbought"}'
            f'</div></div>',
            unsafe_allow_html=True)

    with col_b:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_bb}</div>'
            f'<div style="color:{bb_col};font-size:13px;font-weight:bold">{bb_zone}</div>'
            f'<div style="color:#666;font-size:11px">'
            f'Lower: {bb_buy:,.0f}  |  Upper: {bb_sell:,.0f}  |  Pos: {bb_pos_pct}%'
            f'</div></div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_adx}</div>'
            f'<div style="color:#ffcc44;font-size:15px;font-weight:bold">{adx_v}</div>'
            f'<div style="color:#666;font-size:11px">{adx_label(float(adx_v) if adx_v and str(adx_v)!="–" else 0)}</div>'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_vol}</div>'
            f'<div style="color:#66ccff;font-size:15px;font-weight:bold">{vol_ratio}</div>'
            f'<div style="color:#666;font-size:11px">'
            f'{">1.5× = dòng tiền mạnh" if is_vi else ">1.5× = strong money flow"}'
            f'</div></div>',
            unsafe_allow_html=True)

    with col_c:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_atr}</div>'
            f'<div style="color:#ffaa55;font-size:15px;font-weight:bold">{atr_v:,.0f} VNĐ</div>'
            f'<div style="color:#666;font-size:11px">≈ {atr_pct}% {"của giá" if is_vi else "of price"}</div>'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_ema}</div>'
            f'<div style="color:#cccccc;font-size:12px;font-weight:bold">{ema_cross}</div>'
            f'<div style="color:#666;font-size:11px">EMA9: {ema9}  |  EMA21: {ema21}</div>'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
            f'<div style="color:#888;font-size:11px">{lbl_sma}</div>'
            f'<div style="color:#cccccc;font-size:12px;font-weight:bold">{sma_cross}</div>'
            f'<div style="color:#666;font-size:11px">'
            f'SMA5:{sma5} · SMA20:{sma20} · SMA50:{sma50} · SMA200:{sma200}</div>'
            f'</div>',
            unsafe_allow_html=True)

    # ── Extra meta row ────────────────────────────────────────────────────
    meta_a, meta_b, meta_c = st.columns(3)
    with meta_a:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:8px 12px;margin-bottom:6px">'
            f'<div style="color:#888;font-size:11px">{lbl_cf}</div>'
            f'<div style="color:#aaffaa;font-size:14px;font-weight:bold">{confirms} / 9</div>'
            f'</div>', unsafe_allow_html=True)
    with meta_b:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:8px 12px;margin-bottom:6px">'
            f'<div style="color:#888;font-size:11px">{lbl_nn}</div>'
            f'<div style="color:#ccaaff;font-size:14px;font-weight:bold">{nn_pct}</div>'
            f'</div>', unsafe_allow_html=True)
    with meta_c:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:8px 12px;margin-bottom:6px">'
            f'<div style="color:#888;font-size:11px">{lbl_lim}</div>'
            f'<div style="color:#ffccaa;font-size:12px">'
            f'⬆️ {ceil_v:,.0f}  |  ⬇️ {floor_v:,.0f}'
            f'</div></div>',
            unsafe_allow_html=True) if (isinstance(ceil_v, (int,float)) and ceil_v > 0) else \
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:8px 12px;margin-bottom:6px">'
            f'<div style="color:#888;font-size:11px">{lbl_lim}</div>'
            f'<div style="color:#666;font-size:12px">{ceil_v} / {floor_v}</div>'
            f'</div>', unsafe_allow_html=True)

    # ── Price Derivation Table ────────────────────────────────────────────
    st.markdown(f"**{hdr_pd}**")
    lbl_entry  = "💰 Giá Mua KN"          if is_vi else "💰 Recommended Buy"
    lbl_tp1    = "🎯 Chốt lãi TP1"        if is_vi else "🎯 Take Profit TP1"
    lbl_tp2    = "🎯 Chốt lãi TP2"        if is_vi else "🎯 Take Profit TP2"
    lbl_sl     = "🛑 Cắt lỗ Stop"         if is_vi else "🛑 Stop Loss"
    lbl_level  = "Mức giá (VNĐ)"          if is_vi else "Price Level (VND)"
    lbl_basis  = "Công thức tính"          if is_vi else "Formula"
    lbl_pct    = "% từ Giá RT"             if is_vi else "% from Live"
    rows_deriv = [
        (lbl_entry, f"{_rb:,.0f}",  deriv_buy,  f"{round((_rb-live)/live*100,1):+.1f}%" if live>0 else "–", "#00cc66"),
        (lbl_tp1,   f"{_rt1:,.0f}", deriv_tp1,  f"{round((_rt1-live)/live*100,1):+.1f}%" if live>0 else "–", "#ffcc44"),
        (lbl_tp2,   f"{_rt2:,.0f}", deriv_tp2,  f"{round((_rt2-live)/live*100,1):+.1f}%" if live>0 else "–", "#ffaa22"),
        (lbl_sl,    f"{_rst:,.0f}", deriv_stop, f"{round((_rst-live)/live*100,1):+.1f}%" if live>0 else "–", "#ff6644"),
    ]
    tbl_html = (
        f'<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px">'
        f'<thead><tr style="background:#1e2235;color:#aaa">'
        f'<th style="padding:6px 10px;text-align:left">{lbl_level[:6] if is_vi else "Level"}</th>'
        f'<th style="padding:6px 10px;text-align:right">{lbl_level}</th>'
        f'<th style="padding:6px 10px;text-align:right">{lbl_pct}</th>'
        f'<th style="padding:6px 10px;text-align:left">{lbl_basis}</th>'
        f'</tr></thead><tbody>'
    )
    for lbl, px, formula, pct, col in rows_deriv:
        tbl_html += (
            f'<tr style="border-bottom:1px solid #2a2f45">'
            f'<td style="padding:5px 10px;color:{col};font-weight:bold">{lbl}</td>'
            f'<td style="padding:5px 10px;text-align:right;color:{col};font-weight:bold">{px}</td>'
            f'<td style="padding:5px 10px;text-align:right;color:#ccc">{pct}</td>'
            f'<td style="padding:5px 10px;color:#888;font-family:monospace">{formula}</td>'
            f'</tr>'
        )
    tbl_html += (
        f'<tr style="background:#0e1117;color:#666;font-size:11px">'
        f'<td colspan="4" style="padding:5px 10px">'
        f'{'ATR = True Range bình quân 14 phiên; BB = Bollinger Band 20 chu kỳ ±2σ; Giá RT = SSI iboard real-time' if is_vi else 'ATR = 14-period Average True Range; BB = Bollinger Bands 20-period ±2σ; Live = SSI iboard real-time price'}'
        f'</td></tr></tbody></table>'
    )
    st.markdown(tbl_html, unsafe_allow_html=True)
    # ── price vs SMA50 note ──────────────────────────────────────────────
    if price_vs_sma50 != "–":
        st.caption(f"📌 {price_vs_sma50}")


def render_scanner_tab():
    """
    ENH-40 (v27): Custom ticker input (comma-separated). Blank = scan full watchlist.
    ENH-41 (v27): Full Technical Indicators + Price Derivation panel per signal.
    """
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
    is_vi = st.session_state.lang == "VI"
    st.subheader("📡 " + ("Tín Hiệu Giao Dịch Tổng Hợp" if is_vi else "Aggregated Trading Signals"))
    render_market_insights_panel()

    # ── ENH-40: Custom ticker input ──────────────────────────────────────
    watch_list = load_watchlist_from_file(WATCHLIST_FILE_PATH)
    st.markdown("---")
    _inp_label = ("🎯 Nhập mã cổ phiếu (cách nhau bằng dấu phẩy) — Để trống để quét toàn bộ Watchlist"
                  if is_vi else
                  "🎯 Enter ticker symbols (comma-separated) — Leave blank to scan full Watchlist")
    _inp_placeholder = ("VD: FPT, VCB, SHB, MWG — hoặc để trống" if is_vi
                        else "e.g. FPT, VCB, SHB, MWG — or leave blank for watchlist")
    custom_input = st.text_input(
        _inp_label,
        value="",
        placeholder=_inp_placeholder,
        key="scanner_custom_tickers",
        help=("Nhập các mã cổ phiếu HOSE/HNX/UPCOM, cách nhau bằng dấu phẩy. "
              "Để trống = quét tất cả mã trong Watchlist hiện tại."
              if is_vi else
              "Enter HOSE/HNX/UPCOM ticker symbols separated by commas. "
              "Leave blank to scan all tickers from the current Watchlist file."),
    )

    # Parse custom input → deduplicated uppercase list
    if custom_input and custom_input.strip():
        raw_tokens = [t.strip().upper() for t in custom_input.replace(";",",").split(",")]
        scan_list  = list(dict.fromkeys(t for t in raw_tokens if t and t.isalpha()))
        _src_label = (f"Custom: **{len(scan_list)}** mã" if is_vi
                      else f"Custom: **{len(scan_list)}** tickers")
        if scan_list:
            st.info(
                f"{'🎯 Quét theo danh sách tuỳ chỉnh' if is_vi else '🎯 Custom ticker scan'}  |  "
                f"{_src_label}  |  `{'  ·  '.join(scan_list)}`  |  "
                f"Pipeline: **SSI-RT** → DNSE → CafeF  |  "
                f"RSI Buy<{rsi_buy_thresh} / Sell>{rsi_sell_thresh}"
            )
        else:
            st.warning("⚠️ " + ("Không nhận ra mã nào — quét Watchlist mặc định." if is_vi
                                 else "No valid tickers recognised — falling back to Watchlist."))
            scan_list = watch_list
    else:
        scan_list  = watch_list
        st.info(
            f"{'📋 Watchlist' if is_vi else '📋 Watchlist'}: **{len(scan_list)}** tickers  |  "
            f"Pipeline: **SSI-RT** → DNSE → CafeF  |  "
            f"RSI Buy<{rsi_buy_thresh} / Sell>{rsi_sell_thresh}  |  "
            f"{'Nhập mã ở trên để quét nhanh mã tuỳ chọn ↑' if is_vi else 'Type tickers above for a custom scan ↑'}"
        )

    st.caption("⏱️ " + ("Tín hiệu Scanner là **kỹ thuật ngắn hạn T+2 (1–5 phiên)**. "
                         "Giá thực-time từ SSI iboard. Khác với Hồ Sơ Cổ Phiếu (cơ bản dài hạn 6–24 tháng)."
                         if is_vi else
                         "Scanner signals are **short-term technical T+2 (1–5 sessions)**. "
                         "Real-time prices from SSI iboard. Different from Stock Profiler (long-term fundamental 6–24 months)."))

    # ── Scan button ───────────────────────────────────────────────────────
    _btn_label = (f"🔄 Quét {len(scan_list)} mã" if is_vi else f"🔄 Scan {len(scan_list)} Tickers")
    if st.button(_btn_label, type="primary"):
        scanner_data = []; st.session_state.error_logs = []
        pb = st.progress(0, "Scanning...")
        for i, t in enumerate(scan_list):
            try:
                row, src, err = scan_one_ticker(t)
                if row:
                    scanner_data.append(row)
                elif err:
                    st.session_state.error_logs.append(f"{t}: {err}")
            except Exception as e:
                msg = f"Scanner {t}: {e}"; st.session_state.error_logs.append(msg); _log.error(msg)
            finally:
                pb.progress((i+1)/len(scan_list), text=f"Scanning: {t}")

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
            st.success(f"✅ " + (f"Hoàn tất {len(scanner_data)} mã lúc {scan_time}" if is_vi
                                  else f"Completed {len(scanner_data)} tickers at {scan_time}"))
        else:
            st.warning("⚠️ " + ("Không có kết quả. Kiểm tra kết nối hoặc tắt bộ lọc."
                                  if is_vi else "No results. Check connection or disable filters."))

        if st.session_state.error_logs:
            with st.expander(f"⚠️ {len(st.session_state.error_logs)} errors"):
                for e in st.session_state.error_logs: st.caption(e)

    # ── Results table ─────────────────────────────────────────────────────
    if not st.session_state.df_scan.empty:
        sig_col = L["signal"]
        dc = [c for c in st.session_state.df_scan.columns if not c.startswith("_")]
        show_df(st.session_state.df_scan[dc].style.map(style_action, subset=[sig_col]))

        sig_rows = st.session_state.df_scan[
            st.session_state.df_scan[sig_col].isin(["MUA","BÁN","BUY","SELL"])
        ]
        if not sig_rows.empty:
            st.divider()
            st.subheader("📋 " + ("Lý Giải & Mức Giá Chi Tiết" if is_vi else "Detailed Signals & Price Levels"))
            for _, row in sig_rows.iterrows():
                _sig  = row[sig_col]
                _tkr  = row[L['ticker']]
                _px   = row[L['price']]
                _rsi  = row['RSI']
                _sc   = row[L['score']]
                _src  = row.get(L['source'], '–')
                _rb   = row.get("_rec_buy", 0)
                _rt1  = row.get("_rec_sell_tp1", 0)
                _rt2  = row.get("_rec_sell_tp2", 0)
                _rst  = row.get("_rec_stop", 0)
                _up   = row.get("_pct_upside", 0)
                _risk = row.get("_pct_risk", 0)
                _rr   = row.get("_rec_rr", 0)
                is_buy = _sig in ("MUA", "BUY")
                _color = "#00cc44" if is_buy else "#ff4444"
                label = (f"{_sig} — {_tkr} | "
                         f"Price:{_px:,} | RSI:{_rsi} | "
                         f"Score:{_sc} | {_src}")
                with st.expander(label):
                    # ── ENH-37 (v26): Prominent Recommended Price Card ────
                    if is_vi:
                        _buy_lbl  = "💰 GIÁ MUA KHUYẾN NGHỊ"
                        _sell_lbl = "🎯 GIÁ BÁN KHUYẾN NGHỊ"
                        _stop_lbl = "🛑 GIÁ CẮT LỖ"
                        _up_lbl   = "📈 Tiềm năng tăng"
                        _risk_lbl = "⚠️ Rủi ro"
                        _rr_lbl   = "⚖️ R:R"
                    else:
                        _buy_lbl  = "💰 RECOMMENDED BUY PRICE"
                        _sell_lbl = "🎯 RECOMMENDED SELL PRICE"
                        _stop_lbl = "🛑 STOP LOSS PRICE"
                        _up_lbl   = "📈 Upside"
                        _risk_lbl = "⚠️ Risk"
                        _rr_lbl   = "⚖️ R:R"
                    st.markdown(
                        f'<div style="background:{"#002200" if is_buy else "#220000"};'
                        f'border:2px solid {_color};border-radius:10px;'
                        f'padding:12px 16px;margin-bottom:10px">'
                        f'<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center">'
                        f'<div><div style="color:#888;font-size:11px">{_buy_lbl}</div>'
                        f'<div style="color:#00ff88;font-size:22px;font-weight:bold">'
                        f'{_rb:,.0f} VNĐ</div></div>'
                        f'<div><div style="color:#888;font-size:11px">{_sell_lbl} (TP1 / TP2)</div>'
                        f'<div style="color:#ffcc44;font-size:18px;font-weight:bold">'
                        f'{_rt1:,.0f} <span style="color:#888;font-size:13px">→</span> '
                        f'{_rt2:,.0f}</div></div>'
                        f'<div><div style="color:#888;font-size:11px">{_stop_lbl}</div>'
                        f'<div style="color:#ff6644;font-size:18px;font-weight:bold">'
                        f'{_rst:,.0f}</div></div>'
                        f'<div style="border-left:1px solid #444;padding-left:16px">'
                        f'<div style="color:#888;font-size:11px">{_up_lbl} / {_risk_lbl} / {_rr_lbl}</div>'
                        f'<div style="color:#ccc;font-size:13px">'
                        f'<span style="color:#00cc66">+{_up}%</span> / '
                        f'<span style="color:#ff6644">-{_risk}%</span> / '
                        f'<span style="color:#ffcc44">{_rr}:1</span></div></div>'
                        f'</div></div>',
                        unsafe_allow_html=True)

                    # ── ENH-41 (v27): Technical Indicators + Derivation ───
                    st.divider()
                    _render_scanner_tech_panel(row.to_dict(), is_vi)

                    # ── Existing signal explanation columns ───────────────
                    st.divider()
                    c1, c2 = st.columns(2)
                    with c1: st.markdown(row.get("_ly_giai","–"))
                    with c2: st.markdown(row.get("_price_expl","–"))

    # ENH-28: Sector Heatmap at bottom of Scanner tab
    with st.expander("🗺️ " + ("Bản đồ Luân chuyển Ngành (Sector Rotation)" if is_vi
                                else "Sector Rotation Heatmap"), expanded=False):
        render_sector_heatmap()


def render_smart_signals_tab():
    """
    ENH-34 (v24): Smart Signals — unified tab with:
    - Top 30 BUY signals + full reasoning
    - Top 30 SELL signals + full reasoning
    - Accumulation (whale/shark gom hàng) list
    - Distribution (whale/shark xả hàng) list
    - Daily investment recommendations
    """
    is_vi = st.session_state.lang == "VI"
    st.header("🎯 " + ("Tín Hiệu Thông Minh — Smart Signals" if is_vi else "Smart Signals — Daily Intelligence"))
    st.caption(
        "📡 SSI-RT → DNSE → CafeF | " +
        ("Quét **%d** mã | T+2 kỹ thuật ngắn hạn + Phát hiện dòng tiền cá mập" % len(MARKET_SCAN_LIST) if is_vi
         else "Scanning **%d** tickers | Short-term T+2 technical + Whale money flow detection" % len(MARKET_SCAN_LIST))
    )

    # ── RUN SCAN ─────────────────────────────────────────────────────────
    scan_btn = st.button(
        "▶️ " + ("Quét Toàn Bộ & Tạo Tín Hiệu" if is_vi else "Run Full Scan & Generate Signals"),
        type="primary", use_container_width=True
    )

    if scan_btn:
        buy_sigs = []; sell_sigs = []; accum_sigs = []; dist_sigs = []
        st.session_state.error_logs = []
        pb = st.progress(0, "Scanning...")

        for i, t in enumerate(MARKET_SCAN_LIST):
            pb.progress((i + 1) / len(MARKET_SCAN_LIST), text=f"⚡ Scanning {t} …")
            try:
                row, src, err = scan_one_ticker(t)
                if not row:
                    if err: st.session_state.error_logs.append(f"{t}: {err}")
                    continue

                sig = row.get(L["signal"], "")

                # ── Buy / Sell buckets
                if sig in ("MUA", "BUY"):
                    buy_sigs.append(row)
                elif sig in ("BÁN", "SELL"):
                    sell_sigs.append(row)

                # ── Accumulation / Distribution from doi_lai (re-derive from scan row)
                # We stored the explanation, but we need to re-run detect_doi_lai
                # Use the existing row's score and _ly_giai metadata for signal detection
                _score = row.get(L["score"], 0) or 0
                _rsi   = row.get("RSI", 50) or 50
                _adx   = row.get("ADX", 0) or 0
                _price = row.get(L["price"], 0) or 0

                # Quick whale-signal detection using the cached explanation text
                _ly = str(row.get("_ly_giai", "")).lower()
                if any(kw in _ly for kw in ["tích lũy", "accumul", "gom hàng", "smart money", "bear trap"]):
                    accum_sigs.append(row)
                elif any(kw in _ly for kw in ["xả hàng", "distribut", "dump", "đội lái xả", "pump"]):
                    dist_sigs.append(row)

            except Exception as e:
                _log.debug(f"SmartSignals {t}: {e}")

        pb.empty()

        # Sort by score
        buy_sigs.sort(key=lambda x: x.get(L["score"], 0) or 0, reverse=True)
        sell_sigs.sort(key=lambda x: x.get(L["score"], 0) or 0, reverse=False)

        st.session_state["ss_buy"]   = buy_sigs[:30]
        st.session_state["ss_sell"]  = sell_sigs[:30]
        st.session_state["ss_accum"] = accum_sigs[:20]
        st.session_state["ss_dist"]  = dist_sigs[:20]
        st.session_state["ss_ran"]   = True

        if st.session_state.error_logs:
            with st.expander(f"⚠️ {len(st.session_state.error_logs)} errors"):
                for e in st.session_state.error_logs[:20]: st.caption(e)

    # ── INIT SESSION KEYS ────────────────────────────────────────────────
    for _k in ["ss_buy","ss_sell","ss_accum","ss_dist","ss_ran"]:
        if _k not in st.session_state:
            st.session_state[_k] = [] if _k != "ss_ran" else False

    if not st.session_state.get("ss_ran"):
        st.info("👆 " + ("Nhấn nút phía trên để bắt đầu quét." if is_vi else "Click the button above to start scanning."))
        return

    buy_list   = st.session_state["ss_buy"]
    sell_list  = st.session_state["ss_sell"]
    accum_list = st.session_state["ss_accum"]
    dist_list  = st.session_state["ss_dist"]

    # ── DAILY RECOMMENDATION BANNER ─────────────────────────────────────
    geo = get_geopolitical_context()
    geo_adj = geo.get("score_adj", 0)
    today_str = datetime.now().strftime("%d/%m/%Y")

    # Build market sentiment summary
    n_buy  = len(buy_list)
    n_sell = len(sell_list)
    n_accum = len(accum_list)
    n_dist  = len(dist_list)
    market_mood = "BULLISH" if n_buy > n_sell * 1.5 else ("BEARISH" if n_sell > n_buy * 1.5 else "MIXED")
    mood_color  = {"BULLISH":"#00cc66","BEARISH":"#ff4b4b","MIXED":"#f1a84e"}[market_mood]
    mood_emoji  = {"BULLISH":"📈","BEARISH":"📉","MIXED":"🔀"}[market_mood]

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0d1b2a,#1a2d4a);border:1px solid {mood_color};
     border-radius:12px;padding:16px 20px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <span style="color:{mood_color};font-size:18px;font-weight:bold">{mood_emoji} {"Khuyến Nghị Ngày" if is_vi else "Daily Recommendation"} — {today_str}</span><br>
      <span style="color:#aaa;font-size:13px">
        {"Tâm lý thị trường" if is_vi else "Market Mood"}: 
        <b style="color:{mood_color}">{market_mood}</b> &nbsp;|&nbsp;
        🟢 {n_buy} {"mua" if is_vi else "buys"} &nbsp;|&nbsp;
        🔴 {n_sell} {"bán" if is_vi else "sells"} &nbsp;|&nbsp;
        🐋 {n_accum} {"gom" if is_vi else "accum"} &nbsp;|&nbsp;
        🦈 {n_dist} {"xả" if is_vi else "dist"}
      </span>
    </div>
    <div style="text-align:right;color:#aaa;font-size:12px">
      {"Điều chỉnh vĩ mô" if is_vi else "Macro adj"}: <b style="color:{'#ff4b4b' if geo_adj<0 else '#00cc66'}">{geo_adj:+.0f} pts</b>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # Daily strategic advice
    _advice_vi = []
    _advice_en = []
    if market_mood == "BULLISH":
        _advice_vi += [
            f"✅ **{n_buy} tín hiệu MUA** xuất hiện — thị trường đang trong giai đoạn tích cực.",
            "🎯 **Chiến lược:** Ưu tiên các mã có Score cao nhất + Vol/MA20 > 1.5× + RSI < 50.",
            "💰 **Vị thế:** Không quá 30% vốn/mã. Đặt stop loss theo ATR.",
        ]
        _advice_en += [
            f"✅ **{n_buy} BUY signals** — market in positive phase.",
            "🎯 **Strategy:** Prioritise highest-score tickers with Vol/MA20 > 1.5× and RSI < 50.",
            "💰 **Position:** Max 30% capital per ticker. Set ATR-based stops.",
        ]
    elif market_mood == "BEARISH":
        _advice_vi += [
            f"⚠️ **{n_sell} tín hiệu BÁN** nổi bật — thị trường đang trong giai đoạn phân phối.",
            "🛡️ **Chiến lược:** Giảm tỷ trọng, giữ tiền mặt, tránh mua đuổi.",
            "🔎 **Cơ hội:** Chỉ xem xét các mã trong danh sách Gom Hàng (cá mập đang mua đáy).",
        ]
        _advice_en += [
            f"⚠️ **{n_sell} SELL signals** dominate — market in distribution phase.",
            "🛡️ **Strategy:** Reduce exposure, hold cash, avoid chasing.",
            "🔎 **Opportunity:** Only consider tickers in the Accumulation (whale bottom-fishing) list.",
        ]
    else:
        _advice_vi += [
            "🔀 **Thị trường hỗn hợp** — tín hiệu mua và bán cân bằng nhau.",
            "🎯 **Chiến lược:** Giao dịch chọn lọc, ưu tiên ngành dẫn dắt (Ngân hàng, Công nghệ).",
            "📊 **Lưu ý:** Kiểm tra bối cảnh vĩ mô trước khi vào lệnh.",
        ]
        _advice_en += [
            "🔀 **Mixed market** — buy and sell signals balanced.",
            "🎯 **Strategy:** Selective trading, prioritise leading sectors (Banking, Tech).",
            "📊 **Note:** Check macro context before entering positions.",
        ]

    if geo_adj < -5:
        _advice_vi.append("🌍 **Rủi ro vĩ mô:** Môi trường địa chính trị bất lợi — giảm kỳ vọng lợi nhuận 10–15%.")
        _advice_en.append("🌍 **Macro risk:** Adverse geopolitical environment — reduce return expectations 10–15%.")

    if n_accum > 3:
        _advice_vi.append(f"🐋 **{n_accum} mã có dấu hiệu gom hàng** — xem tab Gom Hàng bên dưới.")
        _advice_en.append(f"🐋 **{n_accum} tickers showing accumulation** — see Accumulation tab below.")

    advice_list = _advice_vi if is_vi else _advice_en
    for a in advice_list:
        st.markdown(a)

    st.divider()

    # ── 5 SUB-TABS ───────────────────────────────────────────────────────
    tab_labels = [
        "🟢 " + ("Top 30 Mua" if is_vi else "Top 30 Buy"),
        "🔴 " + ("Top 30 Bán" if is_vi else "Top 30 Sell"),
        "🐋 " + ("Gom Hàng" if is_vi else "Accumulation"),
        "🦈 " + ("Xả Hàng" if is_vi else "Distribution"),
    ]
    sub_tabs = st.tabs(tab_labels)

    # ── Helper: render signal list ────────────────────────────────────────
    def _render_signal_list(sig_list, sig_type="BUY"):
        if not sig_list:
            st.info("🤷 " + ("Không tìm thấy tín hiệu phù hợp." if is_vi else "No matching signals found."))
            return
        display_rows = []
        for row in sig_list:
            display_rows.append({
                "Mã" if is_vi else "Ticker":   row.get(L["ticker"], ""),
                "Ngành" if is_vi else "Sector": row.get("Ngành/Sector", "–"),
                "Giá RT" if is_vi else "Live Price":   row.get(L["price"], 0),
                "Tín hiệu" if is_vi else "Signal": row.get(L["signal"], "–"),
                "💰 Mua KN" if is_vi else "💰 Rec Buy": row.get("_rec_buy", 0),
                "🎯 Bán TP1" if is_vi else "🎯 Sell TP1": row.get("_rec_sell_tp1", 0),
                "🎯 Bán TP2" if is_vi else "🎯 Sell TP2": row.get("_rec_sell_tp2", 0),
                "🛑 SL":    row.get("_rec_stop", 0),
                "📈 Upside%": f"+{row.get('_pct_upside', 0):.1f}%",
                "Score":    row.get(L["score"], 0),
                "RSI":      row.get("RSI", "–"),
                "ADX":      row.get("ADX", "–"),
                "Vol/MA20": row.get("Vol/MA20", "–"),
                "R:R":      f"{row.get('_rec_rr', 0):.2f}:1",
                "🌐 NN%":   row.get("🌐 NN%", "–"),
                "Nguồn" if is_vi else "Src":  row.get(L["source"], "–"),
            })
        df_disp = pd.DataFrame(display_rows)
        sig_col_d = "Tín hiệu" if is_vi else "Signal"
        show_df(df_disp.style.map(style_action, subset=[sig_col_d]))

        st.divider()
        if is_vi:
            st.markdown(f"### 📋 Lý Do Chi Tiết Từng Mã ({len(sig_list)} mã)")
        else:
            st.markdown(f"### 📋 Detailed Reasoning Per Ticker ({len(sig_list)} tickers)")

        for rank, row in enumerate(sig_list, 1):
            tkr    = row.get(L["ticker"], "")
            score  = row.get(L["score"], 0)
            rsi_v  = row.get("RSI", "–")
            sig_v  = row.get(L["signal"], "")
            sector = row.get("Ngành/Sector", "–")
            _rb    = row.get("_rec_buy", 0)
            _rt1   = row.get("_rec_sell_tp1", 0)
            _rt2   = row.get("_rec_sell_tp2", 0)
            _rst   = row.get("_rec_stop", 0)
            _up    = row.get("_pct_upside", 0)
            _risk  = row.get("_pct_risk", 0)
            _rr    = row.get("_rec_rr", 0)
            _px    = row.get(L["price"], 0)
            color  = "#00cc66" if sig_type == "BUY" else "#ff4b4b"
            is_buy = sig_type == "BUY"
            label  = (
                f"{'🟢' if sig_type=='BUY' else '🔴'} **#{rank} {tkr}** — "
                f"Score: **{score}** | RSI: {rsi_v} | {sector} | {row.get(L['source'],'–')}"
            )
            with st.expander(label):
                # ── ENH-38 (v26): Recommended Price Card at top ──────────
                if is_vi:
                    _buy_lbl  = "💰 GIÁ MUA KHUYẾN NGHỊ"
                    _sell_lbl = "🎯 GIÁ BÁN (TP1 → TP2)"
                    _stop_lbl = "🛑 CẮT LỖ"
                else:
                    _buy_lbl  = "💰 RECOMMENDED BUY"
                    _sell_lbl = "🎯 SELL TARGETS (TP1 → TP2)"
                    _stop_lbl = "🛑 STOP LOSS"

                st.markdown(
                    f'<div style="background:{"#001a00" if is_buy else "#1a0000"};'
                    f'border:2px solid {color};border-radius:10px;'
                    f'padding:12px 18px;margin-bottom:12px">'
                    f'<div style="color:{color};font-size:13px;font-weight:bold;margin-bottom:8px">'
                    f'{"🟢 LỆNH MUA — " if is_buy else "🔴 LỆNH BÁN — "}{tkr} @ {_px:,.0f} VNĐ (RT)</div>'
                    f'<div style="display:flex;gap:20px;flex-wrap:wrap">'
                    f'<div><div style="color:#888;font-size:10px">{_buy_lbl}</div>'
                    f'<div style="color:#00ff88;font-size:20px;font-weight:bold">{_rb:,.0f}</div></div>'
                    f'<div><div style="color:#888;font-size:10px">{_sell_lbl}</div>'
                    f'<div style="color:#ffcc44;font-size:18px;font-weight:bold">'
                    f'{_rt1:,.0f} <span style="color:#888">→</span> {_rt2:,.0f}</div></div>'
                    f'<div><div style="color:#888;font-size:10px">{_stop_lbl}</div>'
                    f'<div style="color:#ff6644;font-size:18px;font-weight:bold">{_rst:,.0f}</div></div>'
                    f'<div style="border-left:1px solid #333;padding-left:14px">'
                    f'<div style="color:#888;font-size:10px">📈+{_up}% / ⚠️-{_risk}% / ⚖️R:R</div>'
                    f'<div style="color:#{"00cc66" if _rr >= 2 else "ffcc44" if _rr >= 1.5 else "ff6644"};'
                    f'font-size:16px;font-weight:bold">{_rr:.2f}:1 '
                    f'{"✅" if _rr >= 2 else "⚠️" if _rr >= 1.5 else "❌"}</div></div>'
                    f'</div></div>',
                    unsafe_allow_html=True)

                # ── Existing signal explanation ───────────────────────────
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"<div style='border-left:3px solid {color};padding-left:8px'>", unsafe_allow_html=True)
                    st.markdown(row.get("_ly_giai", "–"))
                    st.markdown("</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(row.get("_price_expl", "–"))
                # Position sizing quick calc
                st.markdown("**📐 " + ("Vị Thế Nhanh" if is_vi else "Quick Position") + "**")
                _price = row.get(L["price"], 0) or 0
                _atr   = row.get("_atr", _price * 0.02) or (_price * 0.02)
                _sl    = row.get("_stop", 0)
                _tp1   = row.get("_tp1", 0)
                _tp2   = row.get("_tp2", 0)
                if _price > 0 and _sl > 0:
                    risk_per_share = _price - _sl
                    risk_10m = 10_000_000  # 10M VND risk
                    qty_10m  = int(risk_10m / max(risk_per_share, 1) / 100) * 100
                    pc1, pc2, pc3, pc4 = st.columns(4)
                    pc1.metric("SL", f"{_sl:,.0f}")
                    pc2.metric("TP1", f"{_tp1:,.0f}")
                    pc3.metric("TP2", f"{_tp2:,.0f}")
                    pc4.metric("KL/10M rủi ro" if is_vi else "Shares/10M risk", f"{qty_10m:,}")

    # ── Helper: render whale signals ──────────────────────────────────────
    def _render_whale_list(whale_list, whale_type="ACCUM"):
        if not whale_list:
            st.info("🤷 " + ("Không phát hiện tín hiệu." if is_vi else "No signals detected."))
            if is_vi:
                st.caption("Lưu ý: Tín hiệu gom/xả cần có trong lý giải kỹ thuật. Nếu không có, hãy tắt bộ lọc xu hướng trong sidebar để quét rộng hơn.")
            else:
                st.caption("Note: Accumulation/distribution signals require specific keyword patterns in technical explanation. Try disabling trend filter in sidebar for broader scan.")
            return

        color  = "#00cc66" if whale_type == "ACCUM" else "#ff4b4b"
        emoji  = "🐋" if whale_type == "ACCUM" else "🦈"
        hdr_vi = "Gom Hàng (Cá Mập / Đội Lái Mua)" if whale_type=="ACCUM" else "Xả Hàng (Cá Mập / Đội Lái Bán)"
        hdr_en = "Smart Money Accumulation" if whale_type=="ACCUM" else "Smart Money Distribution"
        if is_vi:
            st.markdown(f"### {emoji} {hdr_vi} — {len(whale_list)} mã")
        else:
            st.markdown(f"### {emoji} {hdr_en} — {len(whale_list)} tickers")

        display_rows = []
        for row in whale_list:
            display_rows.append({
                "Mã" if is_vi else "Ticker":    row.get(L["ticker"], ""),
                "Ngành" if is_vi else "Sector":  row.get("Ngành/Sector", "–"),
                "Giá" if is_vi else "Price":    row.get(L["price"], 0),
                "Tín hiệu" if is_vi else "Signal": row.get(L["signal"], "–"),
                "Score":  row.get(L["score"], 0),
                "RSI":    row.get("RSI", "–"),
                "Vol/MA20": row.get("Vol/MA20", "–"),
                "SL":     row.get("_stop", 0),
                "TP1":    row.get("_tp1", 0),
            })
        df_w = pd.DataFrame(display_rows)
        show_df(df_w)

        st.divider()
        for rank, row in enumerate(whale_list, 1):
            tkr  = row.get(L["ticker"], "")
            sec  = row.get("Ngành/Sector", "–")
            sc   = row.get(L["score"], 0)
            with st.expander(f"{emoji} **#{rank} {tkr}** — {sec} | Score:{sc}"):
                st.markdown(row.get("_ly_giai", "–"))

    # ── Render sub-tabs ────────────────────────────────────────────────────
    with sub_tabs[0]:
        if is_vi:
            st.info(f"🟢 Tìm thấy **{len(buy_list)}** tín hiệu MUA | Top 30 theo điểm composite")
        else:
            st.info(f"🟢 Found **{len(buy_list)}** BUY signals | Top 30 by composite score")
        _render_signal_list(buy_list, "BUY")

    with sub_tabs[1]:
        if is_vi:
            st.info(f"🔴 Tìm thấy **{len(sell_list)}** tín hiệu BÁN | Top 30 theo nguy cơ giảm")
            st.warning("⚠️ **Lưu ý:** Tín hiệu BÁN dựa trên kỹ thuật ngắn hạn T+2. Tham khảo thêm phân tích cơ bản trước khi quyết định bán toàn bộ vị thế.")
        else:
            st.info(f"🔴 Found **{len(sell_list)}** SELL signals | Top 30 by downside risk")
            st.warning("⚠️ **Note:** SELL signals are based on short-term T+2 technicals. Check fundamentals before exiting full positions.")
        _render_signal_list(sell_list, "SELL")

    with sub_tabs[2]:
        if is_vi:
            st.markdown("""
> 🐋 **Gom Hàng** = dấu hiệu tổ chức/cá mập đang mua vào âm thầm:
> - Biên độ giá hẹp + KL cao ở vùng thấp hơn MA20 (Smart Money tích lũy)
> - Bear Trap: phiên trước giảm mạnh >5%, phiên này hồi >3% với KL >2× bình thường
> - Lý giải kỹ thuật chứa từ khóa "tích lũy", "gom hàng", "bear trap", "smart money"
""")
        else:
            st.markdown("""
> 🐋 **Accumulation** = signs of institutional / whale quiet buying:
> - Narrow price range + high volume below MA20 (Smart Money accumulating)
> - Bear Trap: previous session fell >5%, today recovered >3% with 2× normal volume
> - Technical explanation contains keywords "accumulate", "bear trap", "smart money"
""")
        _render_whale_list(accum_list, "ACCUM")

    with sub_tabs[3]:
        if is_vi:
            st.markdown("""
> 🦈 **Xả Hàng** = dấu hiệu tổ chức/cá mập đang bán ra:
> - KL đột biến >3× trong phiên tăng (nghi PUMP để xả)
> - Tăng ≥3/5 phiên liên tiếp + KL leo thang (giai đoạn cuối đợt tăng trước khi xả)
> - Giá gần đỉnh 52 tuần + KL thấp (thiếu dòng tiền xác nhận, nguy cơ dump)
""")
        else:
            st.markdown("""
> 🦈 **Distribution** = signs of institutional / whale quiet selling:
> - Volume spike >3× on an up session (suspected PUMP before dump)
> - 3+ consecutive up sessions with rising volume (late-stage rally before distribution)
> - Price near 52-week high + low volume (no money confirmation, dump risk)
""")
        _render_whale_list(dist_list, "DIST")


def render_top_buy_tab():
    """Legacy — now redirects to Smart Signals tab."""
    render_smart_signals_tab()


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
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
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
                        # ENH-31: Extra SMAs/EMAs for audit
                        _s5=extract_latest(df_a,"SMA5"); _s10=extract_latest(df_a,"SMA10")
                        _s30=extract_latest(df_a,"SMA30"); _s100=extract_latest(df_a,"SMA100")
                        _s200=extract_latest(df_a,"SMA200")
                        _e9=extract_latest(df_a,"EMA9"); _e21=extract_latest(df_a,"EMA21")
                        _e50=extract_latest(df_a,"EMA50"); _e200=extract_latest(df_a,"EMA200")
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
                            confirms=confirms, score=score, sector=get_sector(sym),
                            # FIX-28: Include all EMA/SMA values so SMA/EMA grid works
                            sma5=_s5, sma10=_s10, sma30=_s30, sma100=_s100, sma200=_s200,
                            ema9=_e9, ema21=_e21, ema50=_e50, ema200=_e200,
                        )
                        # FIX-29: Fetch SSI real-time price for display (non-blocking)
                        ssi_rt = {}
                        try: ssi_rt = fetch_ssi_realtime_price(sym)
                        except Exception: pass
                        if ssi_rt.get("price", 0) > 0:
                            rt_price = ssi_rt["price"]
                            rt_ref   = ssi_rt.get("reference", 0)
                            rt_ceil  = ssi_rt.get("ceiling", 0)
                            rt_floor = ssi_rt.get("floor", 0)
                            st.session_state.audit_extra.update(
                                rt_price=rt_price, rt_ref=rt_ref,
                                rt_ceil=rt_ceil, rt_floor=rt_floor, rt_src="SSI"
                            )
                        # ENH-V25: Audit deep audit action
                        try:
                            append_audit("DEEP_AUDIT", "AUDIT_TICKER", sym, hanh_vi, score, {
                                "close": c, "rsi": round(rsi,1), "adx": round(adx_v,1) if adx_v else 0,
                                "sma50": round(s50) if s50 else None, "atr": round(atr_v,0) if atr_v else 0,
                                "confirms": len(confirms), "score": round(score,1),
                                "sector": get_sector(sym), "src": src,
                                "stop_loss": round(c - 1.5*(atr_v or c*0.02), 0),
                                "tp1": round(c + 2*(atr_v or c*0.02), 0),
                                "tp2": round(c + 3.5*(atr_v or c*0.02), 0),
                            }, lang)
                        except Exception: pass
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
        # FIX-29: Show RT price from SSI if available, else OHLCV close
        _display_price = extra.get("rt_price") or extra.get("close", 0)
        _price_src     = extra.get("rt_src", "OHLCV")
        m1.metric("Price/Giá",    f"{_display_price:,.0f} VNĐ",
                  delta=f"Src:{_price_src}" if extra.get("rt_src") else None)
        m2.metric("RSI",          f"{extra.get('rsi',50):.1f}",
                  delta=("Oversold" if extra.get('rsi',50)<35 else ("Overbought" if extra.get('rsi',50)>65 else "Neutral")))
        m3.metric("Stoch %K",     f"{extra.get('stoch_k',0) or 0:.0f}")
        m4.metric("ADX",          f"{extra.get('adx',0) or 0:.0f}",
                  delta=("Trending" if (extra.get('adx') or 0)>25 else "Sideways"))
        m5.metric("Signal",       extra.get("hanh_vi","–"),
                  delta=f"Score: {extra.get('score',0)}")
        m6.metric("Sector",       extra.get("sector","–"),
                  delta=st.session_state.audit_src)

        # FIX-29: Real-time price flow: Ceiling / Floor / Reference / Current
        if extra.get("rt_ceil", 0) > 0:
            lang_rt = st.session_state.lang
            rt_c, rt_f, rt_r, rt_p = (extra["rt_ceil"], extra.get("rt_floor",0),
                                       extra.get("rt_ref",0), extra["rt_price"])
            _exch = TICKER_EXCHANGE.get(st.session_state.symbol, "HOSE")
            _band = {"HOSE":"±7%","HNX":"±10%","UPCOM":"±15%"}.get(_exch,"±7%")
            pf_cols = st.columns(4)
            pf_cols[0].metric("🔴 " + ("Trần" if lang_rt=="VI" else "Ceiling"),
                              f"{rt_c:,.0f}", delta=f"{_exch} {_band}")
            pf_cols[1].metric("🟡 " + ("Tham chiếu" if lang_rt=="VI" else "Reference"),
                              f"{rt_r:,.0f}")
            pf_cols[2].metric("💚 " + ("Giá hiện tại" if lang_rt=="VI" else "Live Price"),
                              f"{rt_p:,.0f}",
                              delta=f"{(rt_p-rt_r)/rt_r*100:+.2f}%" if rt_r > 0 else None)
            pf_cols[3].metric("🔵 " + ("Sàn" if lang_rt=="VI" else "Floor"),
                              f"{rt_f:,.0f}")
        elif extra.get("close", 0) > 0:
            # Fallback: compute from OHLCV close
            _lims = get_price_limits(st.session_state.symbol, extra["close"])
            if _lims:
                _exch = _lims.get("exchange","HOSE")
                _band = {"HOSE":"±7%","HNX":"±10%","UPCOM":"±15%"}.get(_exch,"±7%")
                pf_cols2 = st.columns(4)
                pf_cols2[0].metric("🔴 " + ("Trần (Ước tính)" if st.session_state.lang=="VI" else "Ceiling (Est.)"),
                                   f"{_lims['ceiling']:,.0f}", delta=f"{_exch} {_band}")
                pf_cols2[1].metric("🟡 " + ("TC (Ước tính)" if st.session_state.lang=="VI" else "Ref (Est.)"),
                                   f"{_lims['reference']:,.0f}")
                pf_cols2[2].metric("💚 " + ("Giá đóng cửa" if st.session_state.lang=="VI" else "Close Price"),
                                   f"{extra['close']:,.0f}")
                pf_cols2[3].metric("🔵 " + ("Sàn (Ước tính)" if st.session_state.lang=="VI" else "Floor (Est.)"),
                                   f"{_lims['floor']:,.0f}")

        # ENH-31: SMA/EMA grid display
        with st.expander("📐 " + ("SMA & EMA Đầy Đủ" if lang=="VI" else "Full SMA & EMA Levels"), expanded=False):
            _sma_cols = st.columns(7)
            _sma_labels = [("SMA5","sma5"),("SMA10","sma10"),("SMA20","s20"),("SMA30","sma30"),
                           ("SMA50","s50"),("SMA100","sma100"),("SMA200","sma200")]
            _close = extra.get("close", 0)
            for col, (lbl, key) in zip(_sma_cols, _sma_labels):
                v = extra.get(key) or extra.get(lbl.lower())
                if v and _close:
                    delta = f"{(_close-v)/v*100:+.1f}%"
                    col.metric(lbl, f"{v:,.0f}", delta=delta)
                else:
                    col.metric(lbl, "–")
            _ema_cols = st.columns(4)
            for col, (lbl, key) in zip(_ema_cols, [("EMA9","ema9"),("EMA21","ema21"),("EMA50","ema50"),("EMA200","ema200")]):
                v = extra.get(key)
                if v and _close:
                    delta = f"{(_close-v)/v*100:+.1f}%"
                    col.metric(lbl, f"{v:,.0f}", delta=delta)
                else:
                    col.metric(lbl, "–")
            # Golden/Death Cross
            _e50 = extra.get("ema50"); _e200 = extra.get("ema200")
            if _e50 and _e200:
                cross_msg = ("🌟 Golden Cross (EMA50 > EMA200) — Xu hướng tăng dài hạn ✅"
                             if _e50 > _e200 else
                             "💀 Death Cross (EMA50 < EMA200) — Xu hướng giảm dài hạn ⚠️") if lang=="VI" else (
                             "🌟 Golden Cross (EMA50 > EMA200) — Long-term uptrend ✅"
                             if _e50 > _e200 else
                             "💀 Death Cross (EMA50 < EMA200) — Long-term downtrend ⚠️")
                st.caption(cross_msg)

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
        for col,name,color,dash in [
                ("SMA5","SMA5","#ffaa00","dot"),("SMA10","SMA10","#ffcc00","dash"),
                ("SMA20","SMA20","orange","solid"),("SMA30","SMA30","#ff8800","dash"),
                ("SMA50","SMA50","cyan","solid"),("SMA100","SMA100","#00aaff","dash"),
                ("SMA200","SMA200","#0088ff","solid"),
                ("EMA9","EMA9","#ff44ff","dot"),("EMA21","EMA21","#ff00ff","dash"),
                ("EMA50","EMA50","#cc00cc","solid"),("EMA200","EMA200","#ff22cc","solid"),
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
    # ENH-35: Show geopolitical context in ML tab
    _geo_ml = get_geopolitical_context()
    if _geo_ml["reasons"]:
        is_vi_ml = st.session_state.lang == "VI"
        with st.expander("🌍 " + ("Bối cảnh Vĩ mô & Địa chính trị (ảnh hưởng đến dự báo)" if is_vi_ml
                                   else "Macro & Geopolitical Context (affects forecast)"), expanded=False):
            st.markdown(f"**{_geo_ml['summary']}** (Score: {_geo_ml['score_adj']:+.0f})")
            for r in _geo_ml["reasons"]:
                st.caption(r)
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
    st.caption("v25.0 — Mandatory smoke test: OIL (UPCOM), FPT (HOSE), GAS (HOSE), TCB (HOSE), VIC (HOSE). Detects and auto-reports issues. Full traces → error_log.txt.")

    if st.button("🚀 Run Full Smoke Test" if st.session_state.lang=="EN" else "🚀 Chạy Kiểm Tra Đầy Đủ", type="primary"):
        results = []
        import traceback

        # ── v24.0 MANDATORY TICKERS: OIL, FPT, GAS, TCB, VIC ──────────────
        mandatory_smoke = [
            ("OIL",  "UPCOM", "Dầu thực vật / Oil commodity ticker — UPCOM, min 20 rows"),
            ("FPT",  "HOSE",  "Tech blue-chip — benchmark for DNSE/SSI reliability"),
            ("GAS",  "HOSE",  "PetroVietnam Gas — Dầu khí sector, HOSE blue-chip"),
            ("TCB",  "HOSE",  "Techcombank — Banking sector, HOSE large-cap"),
            ("VIC",  "HOSE",  "Vingroup — Real-estate sector, VN30 component"),
        ]
        st.info(f"{'🔍 Testing mandatory tickers: OIL, FPT, GAS, TCB, VIC + extended suite...' if st.session_state.lang=='EN' else '🔍 Kiểm tra bắt buộc: OIL, FPT, GAS, TCB, VIC + bộ test mở rộng...'}")

        for sym_m, exch_m, desc_m in mandatory_smoke:
            with st.spinner(f"Testing {sym_m} ({exch_m}) — {desc_m[:40]}..."):
                try:
                    df_m, src_m, err_m = download_data(sym_m, 180, min_rows=20)
                    ok = len(df_m) >= 20
                    close_val = df_m['Close'].iloc[-1] if ok else 0
                    detail = f"{len(df_m)} rows via {src_m}, close={close_val:,.0f}" if ok else f"FAILED: {err_m}"
                    results.append({"Test":f"[MANDATORY] {sym_m} ({exch_m})", "Status":"✅ PASS" if ok else "❌ FAIL", "Detail":detail})
                    if ok:
                        df_ind_m = calculate_indicators(clean_data(df_m))
                        ind_ok = "RSI" in df_ind_m.columns and not df_ind_m["RSI"].isna().all()
                        rsi_val = df_ind_m["RSI"].iloc[-1] if ind_ok else float("nan")
                        adx_val = df_ind_m["ADX"].iloc[-1] if "ADX" in df_ind_m.columns else float("nan")
                        sma50_val = df_ind_m["SMA50"].iloc[-1] if "SMA50" in df_ind_m.columns else float("nan")
                        ema200_val = df_ind_m["EMA200"].iloc[-1] if "EMA200" in df_ind_m.columns else float("nan")
                        results.append({"Test":f"  ↳ {sym_m} Indicators","Status":"✅ PASS" if ind_ok else "❌ FAIL",
                            "Detail":f"RSI={rsi_val:.1f}, ADX={adx_val:.1f}, SMA50={sma50_val:,.0f}, EMA200={ema200_val:,.0f}"})
                        # Validate price flow: Ceiling/Floor/Reference/Current
                        cf_price = fetch_cafef_price(sym_m)
                        ref_price = cf_price.get("reference", close_val)
                        limits = get_price_limits(sym_m, ref_price)
                        if limits:
                            price_ok = limits["floor"] <= close_val <= limits["ceiling"]
                            results.append({"Test":f"  ↳ {sym_m} Price Flow",
                                "Status":"✅ PASS" if price_ok else "⚠️ CHECK",
                                "Detail":f"Ref={ref_price:,.0f} Ceil={limits['ceiling']:,.0f} Floor={limits['floor']:,.0f} Cur={close_val:,.0f} Exch={limits['exchange']}"})
                        # Composite score smoke
                        row_dict = df_ind_m.iloc[-1].to_dict()
                        avg_v = df_m["Volume"].tail(20).mean()
                        last_v = df_m["Volume"].iloc[-1]
                        trend_ok_m = close_val > sma50_val if not np.isnan(sma50_val) else False
                        sc, cfs = compute_composite_score(row_dict, avg_v, last_v, trend_ok_m, "BUY", 35, 65)
                        results.append({"Test":f"  ↳ {sym_m} CompositeScore",
                            "Status":"✅ PASS" if sc >= 0 else "❌ FAIL",
                            "Detail":f"Score={sc:.1f}, Confirms={len(cfs)}: {', '.join(cfs[:4])}"})
                except Exception as e:
                    results.append({"Test":f"[MANDATORY] {sym_m}","Status":"❌ ERROR","Detail":f"{e} | {str(traceback.format_exc())[:200]}"})

        # ── Test 1: DNSE connectivity (FIX-16: api.dnse.com.vn)
        with st.spinner("Testing DNSE api.dnse.com.vn (FPT + GAS + OIL + TCB + VIC)..."):
            for sym_t, exch_t in [("FPT","HOSE"), ("GAS","HOSE"), ("OIL","UPCOM"), ("TCB","HOSE"), ("VIC","HOSE")]:
                try:
                    df_t = _fetch_dnse(sym_t, 180)
                    ok = len(df_t) >= 20
                    results.append({"Test":f"DNSE ({sym_t}/{exch_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{len(df_t)} rows, close={df_t['Close'].iloc[-1]:,.0f}" if ok else "Empty response"})
                except Exception as e:
                    results.append({"Test":f"DNSE ({sym_t}/{exch_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 2: SSI connectivity
        with st.spinner("Testing SSI (FPT + GAS + TCB + VIC + OIL)..."):
            for sym_t in ["FPT", "GAS", "TCB", "VIC", "OIL"]:
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
        with st.spinner("Testing CafeF fundamental APIs (FPT + GAS + TCB)..."):
            for sym_t in ["FPT", "GAS", "TCB"]:
                try:
                    cf_r = fetch_cafef_key_ratios(sym_t)
                    ok = bool(cf_r.get("eps") or cf_r.get("pe"))
                    results.append({"Test":f"CafeF ChiSoTaiChinh ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"EPS={cf_r.get('eps','?')} P/E={cf_r.get('pe','?')} P/B={cf_r.get('pb','?')}" if ok else "No ratio data"})
                except Exception as e:
                    results.append({"Test":f"CafeF ChiSoTaiChinh ({sym_t})","Status":"❌ ERROR","Detail":str(e)})
            for sym_t in ["FPT", "GAS", "TCB", "VIC", "OIL"]:
                try:
                    cf_p = fetch_cafef_price(sym_t)
                    ok = cf_p.get("price", 0) > 0
                    results.append({"Test":f"CafeF PriceRT ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"Price={cf_p.get('price',0):,.0f}, {cf_p.get('pct_change',0):+.2f}%" if ok else "No price data"})
                except Exception as e:
                    results.append({"Test":f"CafeF PriceRT ({sym_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 7b: SSI Real-time Price (ENH-28, v24.0)
        with st.spinner("Testing SSI iboard-query real-time price (GAS + TCB + VIC)..."):
            for sym_t in ["GAS", "TCB", "VIC"]:
                try:
                    ssi_rt = fetch_ssi_realtime_price(sym_t)
                    ok = ssi_rt.get("price", 0) > 0
                    results.append({"Test":f"SSI RT Price ({sym_t})","Status":"✅ PASS" if ok else "⚠️ PARTIAL",
                        "Detail":f"Price={ssi_rt.get('price',0):,.0f} Ref={ssi_rt.get('reference',0):,.0f} Ceil={ssi_rt.get('ceiling',0):,.0f} Floor={ssi_rt.get('floor',0):,.0f}" if ok else "Not available (auth required)"})
                except Exception as e:
                    results.append({"Test":f"SSI RT Price ({sym_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 8: DNSE OHLC Analysis (ENH-13)
        with st.spinner("Testing DNSE OHLC Analysis (FPT + GAS + TCB + VIC + OIL)..."):
            for sym_t in ["FPT", "GAS", "TCB", "VIC", "OIL"]:
                try:
                    ana = fetch_dnse_ohlc_analysis(sym_t)
                    ok = "error" not in ana and ana.get("n_rows", 0) >= 20
                    results.append({"Test":f"DNSE OHLC Analysis ({sym_t})","Status":"✅ PASS" if ok else "❌ FAIL",
                        "Detail":f"{ana.get('n_rows',0)} rows, RSI={ana.get('rsi',0):.1f}, TechScore={ana.get('tech_score',0):.0f}/100" if ok else ana.get("error","Failed")})
                except Exception as e:
                    results.append({"Test":f"DNSE OHLC Analysis ({sym_t})","Status":"❌ ERROR","Detail":str(e)})

        # ── Test 9: Stock Profiler Recommendation (FPT + GAS + TCB + VIC + OIL)
        with st.spinner("Testing Stock Profiler recommendation engine (FPT + GAS + TCB + VIC + OIL)..."):
            for sym_t in ["FPT", "GAS", "TCB", "VIC", "OIL"]:
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
    """ENH-38/V25: Comprehensive bilingual (VI/EN AU) user guide for all features — v25.0 BRD."""
    is_vi = st.session_state.lang == "VI"
    st.header(f"📖 {L['tab10']}")

    lang_badge = "🇻🇳 Tiếng Việt" if is_vi else "🇦🇺 English (AU)"
    st.caption(f"📌 {lang_badge} | Captain Seventh QUANT TERMINAL v25.0 | 15 tabs | Business Requirements Document (BRD)")

    tabs_guide = st.tabs([
        "🚀 " + ("Bắt đầu" if is_vi else "Getting Started"),
        "📊 " + ("Tabs 1–7" if is_vi else "Tabs 1–7"),
        "🌍 " + ("Tabs 8–14" if is_vi else "Tabs 8–14"),
        "📐 " + ("Chỉ số KT" if is_vi else "Indicators"),
        "💡 " + ("Chiến lược" if is_vi else "Strategy"),
        "🏗️ BRD",
        "❓ FAQ",
    ])

    with tabs_guide[0]:
        if is_vi:
            st.markdown("""
## 🚀 Hướng Dẫn Nhanh — Bắt Đầu Sử Dụng

### Cài đặt (nếu chạy local)
```bash
pip install streamlit pandas numpy requests plotly scikit-learn prophet yfinance
streamlit run quant_app.py
```

### Giao diện chính
- **14 tab** ở trên cùng điều hướng tất cả tính năng
- **Sidebar** (⬅️): Chọn ngôn ngữ (VI/EN), ngưỡng RSI, bộ lọc xu hướng, bộ lọc thanh khoản
- **Watchlist**: Lưu trong `watchlist.txt` — mỗi mã một dòng (VD: FPT, VCB, HPG)

### Luồng làm việc đề xuất
| Bước | Tab | Mục đích |
|------|-----|---------|
| 1 | 📊 Market Scanner | Quét toàn watchlist → xác định tín hiệu MUA/BÁN |
| 2 | 🏆 Top 30 Mua | Xem top 30 mã điểm cao nhất |
| 3 | 🔬 Stock Profiler | Phân tích sâu từng mã: tài chính, định giá, khuyến nghị |
| 4 | 🔍 Deep Audit | Kỹ thuật + tính vị thế + phát hiện thao túng |
| 5 | 💼 Model Portfolios | Xây danh mục theo khẩu vị rủi ro |
| 6 | 🧠 ML Forecast | Dự báo giá 7/14/21/30 ngày |

### Giải thích tín hiệu
| Tín hiệu | Màu | Ý nghĩa | Điều kiện kích hoạt |
|----------|-----|---------|-------------------|
| **MUA** | 🟢 | Cơ hội mua ngắn hạn T+2 | RSI < ngưỡng MUA **VÀ** Giá < BB Lower **VÀ** Giá > SMA50 |
| **BÁN** | 🔴 | Tín hiệu bán ngắn hạn | RSI > ngưỡng BÁN **VÀ** Giá > BB Upper |
| **THEO DÕI** | 🟡 | Chưa đủ điều kiện | Không thỏa mãn MUA hoặc BÁN |

> **Điều chỉnh sidebar:** Mặc định RSI Mua < 35, RSI Bán > 65. Thị trường sideway có thể cần nới lỏng lên 40/60.

### Điểm Composite Score — Cách tính
Điểm tổng hợp (0–100) được tính từ nhiều tín hiệu:

| Nguồn điểm | Điểm tối đa |
|-----------|------------|
| RSI dưới ngưỡng mua | 15 pts |
| Giá dưới BB Lower | 5 pts |
| Xu hướng (Giá > SMA50) | 4 pts |
| Giá > EMA200 (dài hạn) | 3 pts |
| EMA9 > EMA21 (momentum) | 3 pts |
| Giá > SMA200 | 2 pts |
| Giá > SMA100 | 2 pts |
| MACD trên đường tín hiệu | 5 pts |
| Stochastic < 20 (quá bán) | 4 pts |
| ADX > 25 (xu hướng mạnh) | 3 pts |
| CCI < -100 | 2 pts |
| Williams %R < -80 | 2 pts |
| Khối lượng giao dịch cao (> 1.5× TB20) | 5 pts |
| Trừ điểm: Tín hiệu Đội Lái HIGH DUMP | −10 pts |

### Giá Thời Gian Thực (v24.0 — FIX-30)
- Giá hiển thị trong Scanner và Deep Audit là **giá live từ SSI iboard**
- Nếu SSI không trả về (ngoài giờ GD), tự động fallback → CafeF → OHLCV đóng cửa
- Cột **Nguồn/Source** sẽ hiển thị `SSI-RT`, `CafeF-RT`, hoặc tên nguồn OHLCV

### Cảnh báo quan trọng
> ⚠️ Mọi tín hiệu Scanner đều là **ngắn hạn T+2 (1–5 phiên)** — không phải đầu tư dài hạn  
> ⚠️ Scanner (kỹ thuật) ≠ Profiler (cơ bản) — hai khung thời gian khác nhau — cả hai đều đúng  
> ⚠️ **Không phải tư vấn đầu tư chuyên nghiệp** — luôn tự nghiên cứu thêm  
> ⚠️ T+2 VN: Mua hôm nay → Nhận cổ phiếu sau 2 phiên → Chỉ bán được sau khi nhận
""")
        else:
            st.markdown("""
## 🚀 Quick Start Guide — Captain Seventh QUANT TERMINAL v24.0

### Installation (if running locally)
```bash
pip install streamlit pandas numpy requests plotly scikit-learn prophet yfinance
streamlit run quant_app.py
```

### Main Interface
- **14 tabs** at the top navigate all features
- **Sidebar** (⬅️): Language (VI/EN), RSI thresholds, trend filter, liquidity filter
- **Watchlist**: Saved in `watchlist.txt` — one ticker per line (e.g. FPT, VCB, HPG)

### Recommended Workflow
| Step | Tab | Purpose |
|------|-----|---------|
| 1 | 📊 Market Scanner | Scan full watchlist → find BUY/SELL signals |
| 2 | 🏆 Top 30 Buy | View 30 highest-scoring tickers |
| 3 | 🔬 Stock Profiler | Deep-dive: financials, valuation, recommendation |
| 4 | 🔍 Deep Audit | Technical + position sizing + manipulation detection |
| 5 | 💼 Model Portfolios | Build portfolio by risk profile |
| 6 | 🧠 ML Forecast | Price forecast 7/14/21/30 days |

### Signal Explanation
| Signal | Colour | Meaning | Trigger Conditions |
|--------|--------|---------|-------------------|
| **BUY** | 🟢 | Short-term T+2 opportunity | RSI < BUY threshold **AND** Price < BB Lower **AND** Price > SMA50 |
| **SELL** | 🔴 | Short-term sell signal | RSI > SELL threshold **AND** Price > BB Upper |
| **WATCH** | 🟡 | No strong signal | Neither BUY nor SELL conditions met |

> **Sidebar tuning:** Default RSI Buy < 35, Sell > 65. In sideways markets try relaxing to 40/60.

### Composite Score — How It's Calculated
The composite score (0–100) aggregates multiple confirming signals:

| Signal Source | Max Points |
|--------------|-----------|
| RSI below buy threshold | 15 pts |
| Price below BB Lower | 5 pts |
| Trend filter (Price > SMA50) | 4 pts |
| Price > EMA200 (long-term bullish) | 3 pts |
| EMA9 > EMA21 (short-term momentum) | 3 pts |
| Price > SMA200 | 2 pts |
| Price > SMA100 | 2 pts |
| MACD above signal line | 5 pts |
| Stochastic < 20 (oversold) | 4 pts |
| ADX > 25 (strong trend) | 3 pts |
| CCI < −100 | 2 pts |
| Williams %R < −80 | 2 pts |
| High volume (> 1.5× 20-day avg) | 5 pts |
| Penalty: HIGH DUMP manipulation signal | −10 pts |

### Real-Time Price (v24.0 — FIX-30)
- Prices shown in Scanner and Deep Audit are **live prices from SSI iboard**
- If SSI unavailable (outside trading hours), auto-falls back → CafeF → OHLCV close
- The **Source** column shows `SSI-RT`, `CafeF-RT`, or the OHLCV source name

### Important Warnings
> ⚠️ All Scanner signals are **short-term T+2 (1–5 sessions)** — not long-term investing  
> ⚠️ Scanner (technical) ≠ Profiler (fundamental) — different horizons — both can be correct  
> ⚠️ **Not professional financial advice** — always conduct your own research  
> ⚠️ T+2 Vietnam: Buy today → Receive shares after 2 sessions → Can only sell after receipt
""")

    with tabs_guide[1]:
        if is_vi:
            st.markdown("""
## 📊 Hướng Dẫn Chi Tiết Tabs 1–7

### Tab 1 — 📊 Market Scanner
**Mục đích:** Quét nhanh toàn bộ watchlist, xác định cơ hội giao dịch ngắn hạn T+2.

**Cách dùng:**
1. Đặt ngưỡng RSI trong sidebar (mặc định: Mua < 35, Bán > 65)
2. Bật/tắt bộ lọc xu hướng (Trend Filter: Giá > SMA50)
3. Nhấn **🔍 Scan Watchlist** → Chờ kết quả
4. Xem bảng kết quả với cột: Giá, Tín hiệu, SMA5/20/50/200, EMA9/21, RSI, ADX, SL, TP1, TP2
5. Mở rộng **🗺️ Bản đồ Ngành** để xem luân chuyển vốn

**Các cột quan trọng:**
- **SL** = Stop Loss (Giá - 1.5 × ATR) → Nhập vào app chứng khoán
- **TP1** = Take Profit 1 (Giá + 2 × ATR) → Chốt 50% vị thế
- **TP2** = Take Profit 2 (Giá + 3.5 × ATR) → Chốt 50% còn lại
- **🌐 NN%** = Tỷ lệ sở hữu nước ngoài
- **Trần/Sàn** = Giá trần/sàn phiên (HOSE ±7%, HNX ±10%, UPCOM ±15%)

---

### Tab 2 — 🏆 Top 30 Mua
**Mục đích:** Hiển thị 30 mã có điểm composite cao nhất, được lọc để tối ưu xác suất thành công.

**Triple Confirmation Framework:**
- Tối thiểu 2/3 xác nhận: Xu hướng (Giá > SMA50) + Momentum (RSI 40–65) + Khối lượng (Vol > 120% TB)

---

### Tab 3 — 📂 Lịch Sử
**Mục đích:** Lưu và xem lại lịch sử scan để theo dõi tín hiệu theo thời gian.

**Lưu ý:** Nhấn **💾 Lưu kết quả scan** trong Tab 1 hoặc Tab 2 để lưu vào lịch sử.

---

### Tab 4 — 🔍 Deep Audit
**Mục đích:** Phân tích kỹ thuật chuyên sâu một mã cụ thể.

**Các sub-tab:**
- **📊 Phân tích OHLC**: Biểu đồ nến + tất cả chỉ số kỹ thuật
- **💰 Tính Vị Thế**: Nhập vốn → Tính khối lượng, rủi ro, P&L
- **🎯 Thiết Lập Swing**: Các chiến lược swing trade kèm SL/TP
- **🔬 Phát hiện Đội lái**: Cảnh báo thao túng giá/khối lượng bất thường

**SMA/EMA nào đáng chú ý:**
- **SMA5**: Momentum rất ngắn (2–3 ngày)
- **SMA20**: Bollinger Band middle, xu hướng ngắn hạn
- **SMA50**: Xác nhận xu hướng trung hạn (quan trọng nhất)
- **SMA100/200**: Xu hướng dài hạn
- **EMA9**: Trigger vào lệnh ngắn hạn
- **EMA21**: Hỗ trợ/kháng cự dynamic
- **EMA50/200**: Golden Cross / Death Cross tín hiệu dài hạn

---

### Tab 5 — 🧪 Backtest T+2
**Mục đích:** Test chiến lược trading (RSI < X + Giá < BB Lower) trên dữ liệu lịch sử.

---

### Tab 6 — 🧠 Dự Báo ML
**Mục đích:** Dự báo giá bằng Prophet/ARIMA/Ensemble ML.

**Lưu ý khi đọc dự báo:**
- Dự báo ML không dự đoán được sự kiện đột xuất
- Kết hợp với phân tích kỹ thuật và bối cảnh vĩ mô (Tab 8)
- Cân nhắc yếu tố địa chính trị hiển thị trong header

---

### Tab 7 — 📈 Lịch Sử Dự Báo ML
**Mục đích:** Xem và audit lại các lần chạy dự báo ML trước đây.
""")
        else:
            st.markdown("""
## 📊 Detailed Guide — Tabs 1–7

### Tab 1 — 📊 Market Scanner
**Purpose:** Quickly scan the full watchlist and identify short-term T+2 trading opportunities.

**How to use:**
1. Set RSI thresholds in the sidebar (default: Buy < 35, Sell > 65)
2. Toggle trend filter (Price > SMA50)
3. Click **🔍 Scan Watchlist** → wait for results
4. View table with columns: Price, Signal, SMA5/20/50/200, EMA9/21, RSI, ADX, SL, TP1, TP2
5. Expand **🗺️ Sector Map** to see capital rotation

**Key columns:**
- **SL** = Stop Loss (Price − 1.5 × ATR) → Enter into your brokerage app
- **TP1** = Take Profit 1 (Price + 2 × ATR) → Close 50% of position
- **TP2** = Take Profit 2 (Price + 3.5 × ATR) → Close remaining 50%
- **🌐 NN%** = Foreign ownership percentage
- **Ceil/Floor** = Daily price limit (HOSE ±7%, HNX ±10%, UPCOM ±15%)

---

### Tab 2 — 🏆 Top 30 Buy
**Purpose:** Display the 30 highest composite-score tickers filtered for maximum win probability.

**Triple Confirmation Framework:**
- Min 2/3 confirmations: Trend (Price > SMA50) + Momentum (RSI 40–65) + Volume (> 120% avg)

---

### Tab 3 — 📂 History
**Purpose:** Save and review scan history to track signals over time.

**Note:** Click **💾 Save scan results** in Tab 1 or Tab 2 to save to history.

---

### Tab 4 — 🔍 Deep Audit
**Purpose:** Deep technical analysis of a specific ticker.

**Sub-tabs:**
- **📊 OHLC Analysis**: Candlestick chart + all technical indicators
- **💰 Position Sizing**: Input capital → Calculate shares, risk, P&L
- **🎯 Swing Setup**: Swing trade strategies with SL/TP
- **🔬 Manipulation Detection**: Alerts for unusual price/volume patterns

**Key SMA/EMA values:**
- **SMA5**: Very short momentum (2–3 days)
- **SMA20**: Bollinger Band middle, short-term trend
- **SMA50**: Medium-term trend confirmation (most important)
- **SMA100/200**: Long-term trend
- **EMA9**: Short-term entry trigger
- **EMA21**: Dynamic support/resistance
- **EMA50/200**: Golden Cross / Death Cross signals

---

### Tab 5 — 🧪 Backtest T+2
**Purpose:** Test the RSI < X + Price < BB Lower strategy on historical data.

---

### Tab 6 — 🧠 ML Forecast
**Purpose:** Price forecasting using Prophet/ARIMA/Ensemble ML models.

**Notes when reading forecasts:**
- ML forecasts cannot predict unexpected events
- Combine with technical analysis and macro context (Tab 8)
- Consider geopolitical factors shown in the header

---

### Tab 7 — 📈 ML Forecast Log
**Purpose:** View and audit previous ML forecast runs.
""")

    with tabs_guide[2]:
        if is_vi:
            st.markdown("""
## 🌍 Hướng Dẫn Chi Tiết Tabs 8–14

### Tab 8 — 🌍 Thị Trường Thế Giới
**Mục đích:** Theo dõi tác động thị trường toàn cầu (Vàng, Dầu, DXY, S&P500) lên TTCK Việt Nam.

**Cách đọc:**
- **DXY > 106**: USD mạnh → áp lực VNĐ → khối ngoại có xu hướng rút vốn EM
- **S&P500 ↑ > 1.5%**: Risk-on toàn cầu → dòng vốn ngoại tích cực
- **Vàng ↑ mạnh**: Tín hiệu risk-off → thận trọng

---

### Tab 9 — 🔬 Smoke Test
**Mục đích:** Kiểm tra kết nối và độ ổn định các nguồn dữ liệu.

---

### Tab 12 — 🧬 Hồ Sơ Cổ Phiếu (Stock Profiler)
**Mục đích:** Phân tích toàn diện một hoặc nhiều mã (nhập FPT;MWG;TCB).

**6 Sub-tabs:**
- **S1 Tổng quan**: Giá, giá trần/sàn/tham chiếu, VWAP, thông tin doanh nghiệp, sự kiện
- **S2 Tài chính**: BCTC (Doanh thu, Lợi nhuận, Dòng tiền)
- **S3 Chỉ số**: ROE, ROA, Biên ròng, D/E, EPS, P/E, P/B
- **S4 Định giá**: DCF + P/E + P/B + Graham → Giá trị hợp lý
- **S5 Rủi ro**: Điểm rủi ro 5 chiều
- **S6 Khuyến nghị**: Tín hiệu kép (Kỹ thuật + Cơ bản) + Commentary chuyên gia

**Lưu ý định giá theo ngành:**
- **Ngân hàng**: P/B chiếm 70% + DDM 30% (không dùng P/E/DCF)
- **Thép/Dầu khí (chu kỳ)**: EPS chuẩn hóa 5 năm
- **EPS âm**: Tắt DCF/P/E/Graham, hiển thị cảnh báo

---

### Tab 13 — 💼 Model Portfolios (iFollow Style)
**Mục đích:** Tự động gợi ý danh mục cổ phiếu theo khẩu vị rủi ro.

**4 chiến lược:**
| Chiến lược | Rủi ro | Ngành ưu tiên |
|-----------|--------|--------------|
| 🚀 Tăng trưởng | Cao | Công nghệ, Bán lẻ, BĐS |
| ⚖️ Cân bằng | TB | Ngân hàng, Tech, Thực phẩm |
| 🛡️ An toàn | Thấp | Ngân hàng, Điện, Dược |
| 💵 Cổ tức | Thấp–TB | Ngân hàng, Điện, Dầu khí |

**Sử dụng 7 lệnh điều kiện (SSI-style):**
1. Vào kết quả → Copy SL/TP1/TP2 từ bảng
2. Mở app SSI → Đặt lệnh Stop-Loss tại cột SL
3. Đặt Take-Profit tại TP1 (50% vị thế), TP2 (50% còn lại)

---

### Tab 14 — 🔮 Top Forecast
**Mục đích:** Dự báo top 10 mã tăng và giảm trong 7/14/21/30 ngày.

**Phương pháp:**
- Tổng hợp tín hiệu: SMA/EMA trend + MACD momentum + RSI + ADX + OBV
- Bổ sung bối cảnh vĩ mô từ DXY/S&P500/Dầu
- Lịch sử dự báo được lưu tự động mỗi lần chạy (dùng để audit sau)

**Đọc kết quả:**
- **Mom Score > 0**: Xu hướng tăng, càng cao càng mạnh
- **Mom Score < 0**: Xu hướng giảm
- **SL/TP1/TP2**: Copy vào app chứng khoán
""")
        else:
            st.markdown("""
## 🌍 Detailed Guide — Tabs 8–14

### Tab 8 — 🌍 Global Markets
**Purpose:** Track global market impact (Gold, Oil, DXY, S&P500) on Vietnamese stocks.

**Reading guide:**
- **DXY > 106**: Strong USD → VND pressure → foreign capital tends to exit EM
- **S&P500 ↑ > 1.5%**: Global risk-on → positive foreign inflow
- **Gold surging**: Risk-off signal → exercise caution

---

### Tab 9 — 🔬 Smoke Test
**Purpose:** Test connectivity and stability of data sources.

---

### Tab 12 — 🧬 Stock Profiler
**Purpose:** Comprehensive analysis of one or multiple tickers (enter FPT;MWG;TCB).

**6 Sub-tabs:**
- **S1 Overview**: Price, ceiling/floor/reference, VWAP, company info, events
- **S2 Financials**: Income statement, balance sheet, cash flow
- **S3 Ratios**: ROE, ROA, Net Margin, D/E, EPS, P/E, P/B
- **S4 Valuation**: DCF + P/E + P/B + Graham → Fair value
- **S5 Risk**: 5-dimension risk scoring
- **S6 Recommendation**: Dual signal (Technical + Fundamental) + Expert commentary

**Sector-specific valuation notes:**
- **Banking**: P/B = 70% + DDM = 30% (P/E/DCF not used)
- **Steel/Oil (cyclicals)**: 5-year normalised EPS
- **Negative EPS**: DCF/P/E/Graham disabled, warning shown

---

### Tab 13 — 💼 Model Portfolios (iFollow Style)
**Purpose:** Auto-suggest stock portfolios by risk appetite.

**4 strategies:**
| Strategy | Risk | Priority sectors |
|---------|------|-----------------|
| 🚀 Growth | High | Technology, Retail, Real Estate |
| ⚖️ Balanced | Medium | Banking, Tech, Food |
| 🛡️ Defensive | Low | Banking, Utilities, Pharma |
| 💵 Dividend | Low–Medium | Banking, Utilities, Oil & Gas |

**Using 7 conditional order types (SSI-style):**
1. Get results → Copy SL/TP1/TP2 from table
2. Open SSI app → Place Stop-Loss at SL column
3. Place Take-Profit at TP1 (50% position), TP2 (remaining 50%)

---

### Tab 14 — 🔮 Top Forecast
**Purpose:** Predict top 10 gaining and declining tickers over 7/14/21/30 days.

**Methodology:**
- Multi-signal synthesis: SMA/EMA trend + MACD momentum + RSI + ADX + OBV
- Macro overlay from DXY/S&P500/Oil
- Forecast history auto-saved each run (for audit purposes)

**Reading results:**
- **Mom Score > 0**: Upward trend, higher = stronger
- **Mom Score < 0**: Downward trend
- **SL/TP1/TP2**: Copy directly into your brokerage app
""")

    with tabs_guide[3]:
        if is_vi:
            st.markdown("""
## 📐 Chỉ Số Kỹ Thuật — Giải Thích Chi Tiết

### 📈 Đường Trung Bình (MA)
| Chỉ số | Chu kỳ | Ý nghĩa | Ứng dụng |
|--------|--------|---------|---------|
| SMA5 | 5 ngày | Momentum cực ngắn | Trigger vào lệnh ngày |
| SMA10 | 10 ngày | Xu hướng ngắn 2 tuần | Hỗ trợ/kháng cự ngắn |
| SMA20 | 20 ngày | BB middle, ~1 tháng | Bollinger Band trung tâm |
| SMA30 | 30 ngày | 1.5 tháng | Xu hướng ngắn–trung |
| SMA50 | 50 ngày | ~2.5 tháng | **Xác nhận xu hướng quan trọng nhất** |
| SMA100 | 100 ngày | 5 tháng | Xu hướng trung–dài |
| SMA200 | 200 ngày | 10 tháng | **Xu hướng dài hạn** |
| EMA9 | 9 ngày EWM | Phản ứng nhanh | Trigger mua/bán ngắn hạn |
| EMA21 | 21 ngày EWM | Dynamic support | Hỗ trợ/kháng cự linh hoạt |
| EMA50 | 50 ngày EWM | Xu hướng trung hạn | Phân tích institutional |
| EMA200 | 200 ngày EWM | **Golden/Death Cross** | Tín hiệu dài hạn quan trọng |

**Golden Cross:** EMA50 vượt lên trên EMA200 → Tín hiệu tăng giá dài hạn ✅
**Death Cross:** EMA50 cắt xuống EMA200 → Tín hiệu giảm giá dài hạn ⚠️

### 📊 Oscillators
| Chỉ số | Vùng mua | Vùng bán | Ghi chú |
|--------|---------|---------|---------|
| RSI(14) | < 35 | > 65 | Điều chỉnh trong sidebar |
| Stochastic %K | < 20 | > 80 | Momentum ngắn hạn |
| Williams %R | < -80 | > -20 | Inverse của Stochastic |
| CCI(20) | < -100 | > +100 | Chu kỳ giá |

### 📦 Volume/Momentum
| Chỉ số | Tín hiệu tăng | Tín hiệu giảm |
|--------|-------------|-------------|
| MACD | MACD > Signal | MACD < Signal |
| OBV | OBV > OBV_MA20 | OBV < OBV_MA20 |
| ADX | > 25: xu hướng mạnh | < 15: đi ngang |
| ATR | Cao: biến động lớn | Thấp: tích lũy |
| VWAP(20) | Giá > VWAP → BUY | Giá < VWAP → SELL |

### 📉 Bollinger Bands (20, ±2σ)
- **Giá < BB Lower + RSI < 35**: Tín hiệu mua mạnh (oversold bounce)
- **Giá > BB Upper + RSI > 65**: Tín hiệu bán (overbought)
- **BB thắt chặt**: Sắp có biến động lớn
""")
        else:
            st.markdown("""
## 📐 Technical Indicators — Detailed Explanation

### 📈 Moving Averages
| Indicator | Period | Meaning | Application |
|-----------|--------|---------|-------------|
| SMA5 | 5-day | Ultra-short momentum | Intraday entry trigger |
| SMA10 | 10-day | 2-week short trend | Short support/resistance |
| SMA20 | 20-day | BB middle, ~1 month | Bollinger Band centre |
| SMA30 | 30-day | 1.5 months | Short–medium trend |
| SMA50 | 50-day | ~2.5 months | **Most important trend confirmation** |
| SMA100 | 100-day | 5 months | Medium–long trend |
| SMA200 | 200-day | 10 months | **Long-term trend** |
| EMA9 | 9-day EWM | Fast reaction | Short-term entry/exit trigger |
| EMA21 | 21-day EWM | Dynamic support | Flexible support/resistance |
| EMA50 | 50-day EWM | Medium-term trend | Institutional analysis |
| EMA200 | 200-day EWM | **Golden/Death Cross** | Major long-term signal |

**Golden Cross:** EMA50 crosses above EMA200 → Long-term bullish signal ✅
**Death Cross:** EMA50 crosses below EMA200 → Long-term bearish signal ⚠️

### 📊 Oscillators
| Indicator | Buy Zone | Sell Zone | Notes |
|-----------|----------|-----------|-------|
| RSI(14) | < 35 | > 65 | Adjustable in sidebar |
| Stochastic %K | < 20 | > 80 | Short-term momentum |
| Williams %R | < -80 | > -20 | Inverse of Stochastic |
| CCI(20) | < -100 | > +100 | Price cycles |

### 📦 Volume/Momentum
| Indicator | Bullish Signal | Bearish Signal |
|-----------|---------------|----------------|
| MACD | MACD > Signal | MACD < Signal |
| OBV | OBV > OBV_MA20 | OBV < OBV_MA20 |
| ADX | > 25: strong trend | < 15: sideways |
| ATR | High: high volatility | Low: consolidation |
| VWAP(20) | Price > VWAP → BUY | Price < VWAP → SELL |

### 📉 Bollinger Bands (20, ±2σ)
- **Price < BB Lower + RSI < 35**: Strong buy signal (oversold bounce)
- **Price > BB Upper + RSI > 65**: Sell signal (overbought)
- **BB squeeze**: Significant move imminent
""")

    with tabs_guide[4]:
        if is_vi:
            st.markdown("""
## 💡 Chiến Lược Đầu Tư & Thời Điểm Vào Lệnh

### ⏰ Cửa Sổ Vàng (Golden Window)
Dựa trên nghiên cứu hành vi thị trường VN:

| Khung giờ | Đặc điểm | Khuyến nghị |
|-----------|---------|------------|
| ATO (9:00) | Biến động cao, spread rộng | ⚠️ Tránh, trừ mua mạnh |
| 9:00–11:30 | Sáng — thường theo trend ngày trước | Quan sát, chờ xác nhận |
| **13:00–14:00** | **Cửa sổ vàng** — volatility giảm, volume xác nhận | **✅ Vào lệnh nếu điều kiện tốt** |
| 14:00–14:30 | Tốt để chốt lợi nhuận | Bán nếu đạt TP1 |
| ATC (14:30) | Khớp lệnh đóng cửa | ✅ Chốt lời cuối ngày |

### 🛡️ Quản Lý Rủi Ro (2% Rule)
- **Không bao giờ rủi ro quá 2% tổng vốn** cho mỗi lệnh
- Công thức: `Khối lượng = (Vốn × 2%) / (Giá vào − SL)`
- Tab 4 (Deep Audit → Tính Vị Thế) tự động tính toán này

### 🔢 Triple Confirmation Framework
Chỉ vào lệnh khi có ít nhất **2/3 xác nhận**:
1. ✅ **Xu hướng**: Giá > SMA50 (xu hướng trung hạn tăng)
2. ✅ **Momentum**: RSI trong vùng 40–65 (không quá mua hay bán)
3. ✅ **Khối lượng**: Volume phiên ≥ 120% trung bình 20 phiên

### 📊 T+2 Management (VN Market Specific)
- T+0: Mua → Tiền bị phong toả
- T+2: Nhận cổ phiếu → Có thể bán
- **Chiến lược**: Chỉ mua tại vùng hỗ trợ SMA50 hoặc Fibonacci 38.2%
- **Không trung bình giá** khi thua lỗ > 7%

### 📐 Định Giá Theo Ngành (SSI Standard)
| Ngành | Phương pháp ưu tiên | Ghi chú |
|-------|-------------------|---------|
| **Ngân hàng** | P/B 70% + DDM 30% | Không dùng P/E/DCF |
| Thép/Dầu khí | EV/EBITDA + EPS chuẩn hóa | Điều chỉnh theo chu kỳ |
| Công nghệ | P/E + DCF dài hạn | Tăng trưởng cao → PE cao hơn |
| Bất động sản | P/B + NAV discount | Phụ thuộc tài sản |
| Tiêu dùng | P/E + DCF | Ổn định nhất |

### 🌍 Bối Cảnh Vĩ Mô & Địa Chính Trị
Các yếu tố ảnh hưởng lớn đến TTCK VN:

| Yếu tố | Tác động tích cực | Tác động tiêu cực |
|--------|------------------|------------------|
| DXY | ≤ 100: Tích cực | ≥ 108: Tiêu cực mạnh |
| Fed Rate | Giảm lãi suất | Tăng lãi suất |
| S&P500 | Tăng > 1.5% | Giảm > 1.5% |
| Giá dầu | Ổn định | Tăng đột biến > 3% |
| Vàng | — | Tăng mạnh (risk-off) |
| FTSE Upgrade VN | **+15 điểm** | — |
| Trade War | — | Ngành xuất khẩu |
""")
        else:
            st.markdown("""
## 💡 Investment Strategy & Entry Timing

### ⏰ Golden Window
Based on VN market behaviour research:

| Time Window | Characteristics | Recommendation |
|-------------|----------------|----------------|
| ATO (9:00) | High volatility, wide spread | ⚠️ Avoid unless strong conviction |
| 9:00–11:30 | Morning — often follows prior day trend | Observe, wait for confirmation |
| **13:00–14:00** | **Golden Window** — volatility subsides, volume confirms | **✅ Enter if conditions are good** |
| 14:00–14:30 | Good for profit-taking | Sell if TP1 reached |
| ATC (14:30) | Closing auction | ✅ End-of-day profit taking |

### 🛡️ Risk Management (2% Rule)
- **Never risk more than 2% of total capital** per trade
- Formula: `Shares = (Capital × 2%) / (Entry Price − Stop Loss)`
- Tab 4 (Deep Audit → Position Sizing) calculates this automatically

### 🔢 Triple Confirmation Framework
Only enter when at least **2/3 confirmations** align:
1. ✅ **Trend**: Price > SMA50 (medium-term uptrend)
2. ✅ **Momentum**: RSI in 40–65 range (neither overbought nor oversold)
3. ✅ **Volume**: Session volume ≥ 120% of 20-session average

### 📊 T+2 Management (VN Market Specific)
- T+0: Buy → Funds locked
- T+2: Receive shares → Can sell
- **Strategy**: Only buy at SMA50 support or 38.2% Fibonacci levels
- **Never average down** when loss exceeds 7%

### 📐 Sector-Specific Valuation (SSI Standard)
| Sector | Priority method | Notes |
|--------|----------------|-------|
| **Banking** | P/B 70% + DDM 30% | P/E/DCF not applicable |
| Steel/Oil | EV/EBITDA + normalised EPS | Adjust for cycles |
| Technology | P/E + long-term DCF | High growth → higher PE |
| Real Estate | P/B + NAV discount | Asset-dependent |
| Consumer | P/E + DCF | Most stable |

### 🌍 Macro & Geopolitical Context
Key factors affecting the VN market:

| Factor | Positive impact | Negative impact |
|--------|----------------|----------------|
| DXY | ≤ 100: Positive | ≥ 108: Strongly negative |
| Fed Rate | Rate cuts | Rate hikes |
| S&P500 | Up > 1.5% | Down > 1.5% |
| Oil price | Stable | Spike > 3% |
| Gold | — | Strong rise (risk-off) |
| FTSE VN Upgrade | **+15 points** | — |
| Trade War | — | Export sectors |
""")

    with tabs_guide[5]:
        if is_vi:
            st.markdown("""
## ❓ Câu Hỏi Thường Gặp (FAQ)

**Q: Tại sao Scanner nói MUA nhưng Profiler nói THEO DÕI?**
A: Hai tín hiệu trả lời hai câu hỏi khác nhau:
- Scanner: "Giá có thể hồi phục 1–5 phiên không?" (kỹ thuật ngắn hạn T+2)
- Profiler: "Cổ phiếu có được định giá hợp lý dài hạn không?" (6–24 tháng)
Cả hai đều đúng — bổ sung nhau chứ không mâu thuẫn.

**Q: Tại sao ROA/Biên ròng/D/E hiển thị "–"?**
A: TCBS 404 (API không trả dữ liệu) + VNDirect timeout. App sẽ thử SSI Finance-Indicator.
Một số mã ít thanh khoản (UPCOM) không có đủ dữ liệu BCTC công khai.

**Q: Dữ liệu giá từ nguồn nào?**
A: Thứ tự ưu tiên: DNSE (api.dnse.com.vn) → SSI → CafeF → TCBS → VNDirect → yFinance.
Nguồn thành công được ghi ở cột "Source" trong scanner.

**Q: Làm thế nào để thêm/bớt mã trong watchlist?**
A: Chỉnh sửa file `watchlist.txt` (mỗi mã một dòng). App tự reload.

**Q: Model Portfolio gợi ý vốn tối thiểu bao nhiêu?**
A: 30 triệu VNĐ (tương đương SSI iFollow minimum). Nhập vốn thực tế của bạn.

**Q: Dự báo ML có chính xác không?**
A: ML dự báo dựa trên mẫu lịch sử — không thể dự đoán sự kiện đột xuất.
Độ chính xác ~55–65% trong điều kiện thị trường bình thường. Luôn kết hợp với kỹ thuật.

**Q: Giá trần/sàn tính thế nào?**
A: HOSE: ±7% | HNX: ±10% | UPCOM: ±15% từ giá tham chiếu (giá đóng cửa phiên trước).
App lấy giá tham chiếu từ CafeF PriceRealTimeHeader API.

**Q: Tại sao một số mã không hiện trong Scanner?**
A: Bị lọc bởi: thanh khoản thấp (giá trị giao dịch TB < ngưỡng) HOẶC không đủ dữ liệu lịch sử.
""")
        else:
            st.markdown("""
## ❓ Frequently Asked Questions (FAQ)

**Q: Why does Scanner say BUY but Profiler says WATCH?**
A: The two signals answer different questions:
- Scanner: "Can the price recover in 1–5 sessions?" (short-term technical T+2)
- Profiler: "Is the stock fairly priced long-term?" (6–24 months)
Both are correct — they complement rather than contradict each other.

**Q: Why are ROA/Net Margin/D/E showing "–"?**
A: TCBS 404 (API not returning data) + VNDirect timeout. App tries SSI Finance-Indicator.
Some low-liquidity stocks (UPCOM) lack sufficient publicly available financial data.

**Q: Where does price data come from?**
A: Priority order: DNSE (api.dnse.com.vn) → SSI → CafeF → TCBS → VNDirect → yFinance.
Successful source is shown in the "Source" column in the scanner.

**Q: How do I add/remove tickers from the watchlist?**
A: Edit `watchlist.txt` (one ticker per line). App auto-reloads.

**Q: What is the minimum capital for Model Portfolios?**
A: 30 million VND (equivalent to SSI iFollow minimum). Enter your actual capital.

**Q: How accurate are ML forecasts?**
A: ML forecasts based on historical patterns — cannot predict unexpected events.
Accuracy ~55–65% in normal market conditions. Always combine with technical analysis.

**Q: How are ceiling/floor prices calculated?**
A: HOSE: ±7% | HNX: ±10% | UPCOM: ±15% from reference price (prior session close).
App fetches reference price from CafeF PriceRealTimeHeader API.

**Q: Why are some tickers missing from Scanner results?**
A: Filtered out by: low liquidity (avg trading value < threshold) OR insufficient historical data.
""")

    # ─── BRD TAB (new in v24.0) ──────────────────────────────────────────────
    with tabs_guide[6]:
        if is_vi:
            st.markdown("""
# 🏗️ Tài Liệu Yêu Cầu Nghiệp Vụ (BRD) — v24.0
**Captain Seventh QUANT TERMINAL · Vietnam Stock Exchange**

---

## 1. Mục Tiêu Hệ Thống

| Mục tiêu | Mô tả |
|----------|-------|
| **Tính toàn vẹn dữ liệu** | Pipeline 7 nguồn (DNSE→SSI→CafeF→TCBS→VNDirect→yFinance) đảm bảo giá khớp thống nhất (Trần/Sàn/TC/Hiện tại) trên tất cả tab |
| **Định giá ngành** | PE/PB/DCF/DDM thích ứng theo ngành; Ngân hàng dùng P/B+DDM; Chu kỳ dùng EPS bình quân 5 năm |
| **Kỹ thuật chính xác** | SMA (5,10,20,30,50,100,200) + EMA (9,21,50,200) + RSI/MACD/BB/ADX/Stoch/ATR/OBV |
| **Dự báo ML** | Prophet + ARIMA + SVR + RF + Ensemble cho 7/14/21/30 ngày; kiểm toán đầy đủ |
| **Vĩ mô tích hợp** | DXY/FED/Gold/WTI làm điều chỉnh điểm ngành tự động |
| **T+2 chính xác** | Mọi backtest đếm phiên giao dịch thực tế (không dùng ngày dương lịch) |

---

## 2. Pipeline Dữ Liệu SSI iBoard

### Các endpoint SSI đã xác minh (từ HAR logs 09/03/2026):

| Endpoint | Params | Mục đích |
|----------|--------|----------|
| `iboard-api.ssi.com.vn/statistics/charts/history` | `symbol, resolution=1D, from, to` | Dữ liệu OHLCV lịch sử |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/finance-indicator` | `symbol, page=1, pageSize=20` | ROE, ROA, EPS, P/E, P/B theo quý |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/company-news` | `symbol, fromDate, pageSize=10` | Tin tức công ty |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/corporate-actions` | `symbol, fromDate, language=vn` | Sự kiện (ĐHCĐ, cổ tức, phát hành) |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/share-holder-summary` | `symbol, language=vn` | Cơ cấu cổ đông |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/cap-and-dividend` | `symbol` | Vốn hóa & lịch sử cổ tức |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/company-leaderships` | `symbol, language=vn` | Ban lãnh đạo |
| `iboard-query.ssi.com.vn/stock/{symbol}` | `boardId=MAIN` | Giá real-time + Trần/Sàn/TC |
| `iboard-query.ssi.com.vn/market-stat/exchange/hose` | — | Thống kê thị trường |

**Headers bắt buộc:** `Origin: https://iboard.ssi.com.vn` | `Referer: https://iboard.ssi.com.vn/`

---

## 3. Mô Hình Định Giá

### 3.1 Định Giá Chung (Non-Banking)

| Model | Công thức | Trọng số |
|-------|-----------|---------|
| **DCF** | `EPS × (1+g)^n / (r-g)` · g=10%, r=15%, n=5 | 40% |
| **P/E so sánh ngành** | `EPS × Median_PE_Sector` | 30% |
| **P/B** | `BVPS × Target_PB_ROE_Adjusted` | 20% |
| **Graham** | `√(22.5 × EPS × BVPS)` | 10% |

### 3.2 Định Giá Ngân Hàng (Sector-Aware)

| Model | Lý do | Trọng số |
|-------|-------|---------|
| **P/B** | ROE ngân hàng ổn định; P/B=1.2–2.5× là hợp lý | 70% |
| **DDM** | Cổ tức tiền mặt ổn định ~2–4% | 30% |
| ~~DCF~~ | Không áp dụng — dòng tiền ngân hàng khó tách biệt | 0% |

### 3.3 Ngành Chu Kỳ (Thép/Dầu Khí/Xây Dựng)

- **EPS chuẩn hóa**: Bình quân EPS 5 năm thay vì TTM → loại bỏ biến động chu kỳ
- **EPS âm**: Tắt DCF/P/E, dùng P/B + Tech Fair Value từ DNSE

### 3.4 Sector P/E Benchmarks (SSI Research 2025)

| Ngành | P/E median | Nguồn |
|-------|-----------|-------|
| Công nghệ | 28× | SSI/VCSC 2025 |
| Ngân hàng | 11× | P/B ưu tiên |
| Bất động sản | 20× | VCSC |
| Thép | 9× | VCSC |
| Dược | 22× | SSI |
| Điện | 18× | SSI |
| Dầu khí | 14× | SSI |
| Bán lẻ | 25× | VCSC |
| Hàng không | 16× | SSI |
| Khác | 14× | VCSC median |

---

## 4. Chỉ Số Kỹ Thuật & Lý Thuyết

### 4.1 Moving Averages
| Chỉ số | Chu kỳ | Lý thuyết | Ứng dụng |
|--------|--------|-----------|----------|
| SMA5 | 5 ngày | Momentum ngắn nhất | Entry/exit filter |
| SMA10 | 10 ngày | 2 tuần giao dịch | Trend ngắn hạn |
| SMA20 | 20 ngày | 1 tháng giao dịch | BB Middle, trend ngắn |
| SMA30 | 30 ngày | 6 tuần | Confirmation |
| SMA50 | 50 ngày | ~2.5 tháng | **Bộ lọc xu hướng chính** |
| SMA100 | 100 ngày | ~5 tháng | Trend trung dài hạn |
| SMA200 | 200 ngày | ~1 năm | Golden/Death Cross tham chiếu |
| EMA9 | 9 ngày | Phản ứng nhanh | Trigger vào lệnh |
| EMA21 | 21 ngày | 1 tháng dương lịch | Support/Resistance động |
| EMA50 | 50 ngày | Trend trung hạn | Golden Cross với EMA200 |
| EMA200 | 200 ngày | Trend dài hạn | Phân định Bull/Bear market |

### 4.2 RSI (Relative Strength Index)
- **Wilder smoothing**: `RSI = 100 – 100/(1 + RS)` · RS = AvgGain(14)/AvgLoss(14)
- Ngưỡng: <35 = oversold (mua), >65 = overbought (bán); Có thể tùy chỉnh sidebar

### 4.3 Bollinger Bands
- `BB_Upper = SMA20 + 2σ` · `BB_Lower = SMA20 – 2σ`
- Giá chạm BB_Lower + RSI oversold = tín hiệu mua mạnh

### 4.4 MACD (12,26,9)
- `MACD = EMA12 – EMA26` · `Signal = EMA9(MACD)` · `Hist = MACD – Signal`
- Golden cross (MACD > Signal) = momentum tăng; Death cross = giảm

### 4.5 ADX (Average Directional Index, 14)
- ADX > 25 = xu hướng rõ; < 20 = sideway
- +DI > -DI = xu hướng tăng; -DI > +DI = xu hướng giảm

### 4.6 ATR (Average True Range, 14)
- `TR = max(H-L, |H-Prev_C|, |L-Prev_C|)` · ATR = Wilder(TR, 14)
- Stop Loss = Price – 1.5×ATR | TP1 = Price + 2×ATR | TP2 = Price + 3.5×ATR

---

## 5. Mô Hình Dự Báo ML

| Model | Thư viện | Đặc điểm | Trọng số Ensemble |
|-------|---------|----------|-----------------|
| **Prophet** | Meta/Facebook | Xử lý seasonality, holiday | 30% |
| **ARIMA** | statsmodels | Chuỗi thời gian cổ điển | 20% |
| **Linear Regression** | scikit-learn | Baseline tuyến tính | 10% |
| **SVR** | scikit-learn | Support Vector Regression | 15% |
| **Random Forest** | scikit-learn | Ensemble trees, feature importance | 15% |
| **Gradient Boosting** | scikit-learn | XGBoost-like, high accuracy | 10% |
| **Ensemble** | Weighted avg | Tổng hợp tất cả | 100% |

**Chân trời:** 7, 14, 21, 30 ngày  
**Điều chỉnh vĩ mô:** DXY > 106 → -5 đến -10 điểm cho ngành nhập khẩu; FED hike → -5 cho toàn thị trường

---

## 6. Quản Trị Rủi Ro & T+2

### 6.1 Position Sizing (Kelly Criterion)
```
Kelly% = (W × R – (1–W)) / R
W = Tỷ lệ thắng lịch sử | R = R/R ratio
Áp dụng: Không dùng quá 50% Kelly (Half-Kelly)
Lot size HOSE = 100 CP | Phí mua: 0.15% | Phí bán: 0.25% + 0.1% thuế
```

### 6.2 T+2 Settlement
- Mua phiên T → bán sớm nhất phiên T+2
- Backtest đếm phiên giao dịch thực tế (không tính ngày lễ/cuối tuần)
- `T2_SESSIONS = 2` trong constants

### 6.3 7 Loại Lệnh Điều Kiện (SSI-style)
| # | Loại | Điều kiện | Ứng dụng |
|---|------|----------|---------|
| 1 | Lệnh giới hạn (LO) | Giá = mức đặt | Mua tại BB Lower |
| 2 | Lệnh thị trường (MP/ATO/ATC) | Khớp ngay | Entry/Exit nhanh |
| 3 | Stop Loss | Giá ≤ SL | Cắt lỗ tự động |
| 4 | Take Profit | Giá ≥ TP | Chốt lời tự động |
| 5 | Trailing Stop | SL di động theo giá | Bảo vệ lợi nhuận |
| 6 | OCO (One-Cancel-Other) | SL + TP đặt đồng thời | Quản lý rủi ro |
| 7 | Bracket Order | Entry + SL + TP cùng lúc | Hoàn chỉnh nhất |

---

## 7. Phân Tích Dòng Vốn Ngoại (Foreign Flow)

- **Nguồn:** SSI share-holder-summary (% sở hữu NN) + CafeF CoCauSoHuu
- **Tín hiệu tích cực:** NN tăng mua ròng + DXY < 104 + S&P500 risk-on
- **Tín hiệu tiêu cực:** NN bán ròng liên tục + DXY > 106 + FED hawkish

---

## 8. Danh Mục Mẫu (iFollow)

| Danh mục | Mục tiêu | Max DD | Ngành trọng tâm |
|---------|---------|--------|----------------|
| 🚀 Risk-On Growth | +20%+/năm | -15% | Tech, BĐS, Bán lẻ |
| ⚖️ Balanced | +12–18%/năm | -10% | NH, Tech, Thực phẩm |
| 🛡️ Safe-Haven | +8–12%/năm | -7% | NH, Điện, Dược |
| 💵 Dividend | +6–10%/năm (cổ tức) | -5% | NH, Điện, Dầu khí |

---

## 9. Kiểm Tra Hệ Thống (Smoke Test — v24.0)

### Bộ test bắt buộc mỗi lần chạy:
| Ticker | Sàn | Lý do chọn |
|--------|-----|------------|
| OIL | UPCOM | UPCOM ticker nhỏ — test độ bền pipeline |
| FPT | HOSE | Blue-chip công nghệ — benchmark chính |
| GAS | HOSE | Dầu khí lớn — test ngành cyclical |
| TCB | HOSE | Ngân hàng — test sector banking |
| VIC | HOSE | VN30 component, BĐS — test sector RE |

### Điều kiện PASS:
- ≥ 20 dòng dữ liệu OHLCV
- RSI được tính (không NaN)
- Giá nằm trong [Sàn, Trần] hợp lệ
- CompositeScore ≥ 0 (không lỗi NameError)
""")
        else:
            st.markdown("""
# 🏗️ Business Requirements Document (BRD) — v24.0
**Captain Seventh QUANT TERMINAL · Vietnam Stock Exchange**

---

## 1. System Objectives

| Objective | Description |
|-----------|-------------|
| **Data Integrity** | 7-source pipeline (DNSE→SSI→CafeF→TCBS→VNDirect→yFinance) ensures unified price flow (Ceiling/Floor/Reference/Current) across all tabs |
| **Sector Valuation** | Adaptive P/E/P/B/DCF/DDM benchmarks; Banking = P/B+DDM; Cyclicals = 5Y normalised EPS |
| **Precision Technicals** | SMA (5,10,20,30,50,100,200) + EMA (9,21,50,200) + RSI/MACD/BB/ADX/Stoch/ATR/OBV |
| **ML Forecasting** | Prophet + ARIMA + SVR + RF + Ensemble for 7/14/21/30 day horizons; full audit trail |
| **Macro Integration** | DXY/FED/Gold/WTI auto-adjust sector scores |
| **Accurate T+2** | All backtests count actual trading sessions (not calendar days) |

---

## 2. SSI iBoard Data Pipeline

### Confirmed SSI Endpoints (from HAR logs 09/03/2026):

| Endpoint | Params | Purpose |
|----------|--------|---------|
| `iboard-api.ssi.com.vn/statistics/charts/history` | `symbol, resolution=1D, from, to` | Historical OHLCV |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/finance-indicator` | `symbol, page=1, pageSize=20` | ROE, ROA, EPS, P/E, P/B per quarter |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/company-news` | `symbol, fromDate, pageSize=10` | Company news |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/corporate-actions` | `symbol, fromDate, language=vn` | Events (AGM, dividends, issues) |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/share-holder-summary` | `symbol, language=vn` | Shareholder structure |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/cap-and-dividend` | `symbol` | Market cap & dividend history |
| `iboard-api.ssi.com.vn/statistics/company/ssmi/company-leaderships` | `symbol, language=vn` | Board of directors |
| `iboard-query.ssi.com.vn/stock/{symbol}` | `boardId=MAIN` | Real-time price + Ceiling/Floor/Ref |
| `iboard-query.ssi.com.vn/market-stat/exchange/hose` | — | Market statistics |

**Required headers:** `Origin: https://iboard.ssi.com.vn` | `Referer: https://iboard.ssi.com.vn/`

---

## 3. Valuation Models

### 3.1 General Valuation (Non-Banking)

| Model | Formula | Weight |
|-------|---------|--------|
| **DCF** | `EPS × (1+g)^n / (r-g)` · g=10%, r=15%, n=5 | 40% |
| **P/E Relative** | `EPS × Median_PE_Sector` | 30% |
| **P/B** | `BVPS × Target_PB_ROE_Adjusted` | 20% |
| **Graham** | `√(22.5 × EPS × BVPS)` | 10% |

### 3.2 Banking Valuation (Sector-Aware)

| Model | Rationale | Weight |
|-------|-----------|--------|
| **P/B** | Stable ROE; P/B=1.2–2.5× is reasonable | 70% |
| **DDM** | Steady cash dividend ~2–4% | 30% |
| ~~DCF~~ | Not applicable — bank cash flows hard to isolate | 0% |

### 3.3 Cyclical Sectors (Steel/Oil & Gas/Construction)

- **Normalised EPS**: Average EPS over 5 years instead of TTM → removes cycle volatility
- **Negative EPS**: DCF/P/E disabled; use P/B + Tech Fair Value from DNSE

### 3.4 Sector P/E Benchmarks (SSI Research 2025)

| Sector | Median P/E | Source |
|--------|-----------|--------|
| Technology | 28× | SSI/VCSC 2025 |
| Banking | 11× | P/B preferred |
| Real Estate | 20× | VCSC |
| Steel | 9× | VCSC |
| Pharma | 22× | SSI |
| Utilities/Power | 18× | SSI |
| Oil & Gas | 14× | SSI |
| Retail | 25× | VCSC |
| Aviation | 16× | SSI |
| Other | 14× | VCSC median |

---

## 4. Technical Indicators & Theory

### 4.1 Moving Averages
| Indicator | Period | Theory | Application |
|-----------|--------|--------|-------------|
| SMA5 | 5d | Shortest momentum | Entry/exit filter |
| SMA10 | 10d | 2 trading weeks | Short-term trend |
| SMA20 | 20d | 1 trading month | BB Middle, short-trend |
| SMA30 | 30d | 6 weeks | Confirmation |
| SMA50 | 50d | ~2.5 months | **Primary trend filter** |
| SMA100 | 100d | ~5 months | Medium-long trend |
| SMA200 | 200d | ~1 year | Golden/Death Cross reference |
| EMA9 | 9d | Fast response | Short-term entry trigger |
| EMA21 | 21d | 1 calendar month | Dynamic support/resistance |
| EMA50 | 50d | Medium trend | Golden Cross with EMA200 |
| EMA200 | 200d | Long trend | Bull/Bear market delimiter |

### 4.2 RSI (Relative Strength Index)
- **Wilder smoothing**: `RSI = 100 – 100/(1 + RS)` · RS = AvgGain(14)/AvgLoss(14)
- Thresholds: <35 = oversold (buy), >65 = overbought (sell); customisable in sidebar

### 4.3 Bollinger Bands
- `BB_Upper = SMA20 + 2σ` · `BB_Lower = SMA20 – 2σ`
- Price at BB_Lower + RSI oversold = strong buy signal

### 4.4 MACD (12,26,9)
- `MACD = EMA12 – EMA26` · `Signal = EMA9(MACD)` · `Hist = MACD – Signal`
- Golden cross (MACD > Signal) = increasing momentum; Death cross = decreasing

### 4.5 ADX (Average Directional Index, 14)
- ADX > 25 = clear trend; < 20 = sideways
- +DI > -DI = uptrend; -DI > +DI = downtrend

### 4.6 ATR (Average True Range, 14)
- `TR = max(H-L, |H-Prev_C|, |L-Prev_C|)` · ATR = Wilder(TR, 14)
- Stop Loss = Price – 1.5×ATR | TP1 = Price + 2×ATR | TP2 = Price + 3.5×ATR

---

## 5. ML Forecasting Models

| Model | Library | Characteristics | Ensemble Weight |
|-------|---------|----------------|----------------|
| **Prophet** | Meta/Facebook | Handles seasonality, holidays | 30% |
| **ARIMA** | statsmodels | Classical time-series | 20% |
| **Linear Regression** | scikit-learn | Linear baseline | 10% |
| **SVR** | scikit-learn | Support Vector Regression | 15% |
| **Random Forest** | scikit-learn | Ensemble trees, feature importance | 15% |
| **Gradient Boosting** | scikit-learn | XGBoost-like, high accuracy | 10% |
| **Ensemble** | Weighted avg | Aggregate all models | 100% |

**Horizons:** 7, 14, 21, 30 days  
**Macro adjustment:** DXY > 106 → -5 to -10 pts for import-heavy sectors; FED hike → -5 market-wide

---

## 6. Risk Management & T+2

### 6.1 Position Sizing (Kelly Criterion)
```
Kelly% = (W × R – (1–W)) / R
W = Historical win rate | R = R/R ratio
Applied: Never exceed 50% Kelly (Half-Kelly)
Lot size HOSE = 100 shares | Buy fee: 0.15% | Sell fee: 0.25% + 0.1% tax
```

### 6.2 T+2 Settlement
- Buy session T → earliest sell session T+2
- Backtest counts actual trading sessions (excludes holidays/weekends)
- `T2_SESSIONS = 2` in trading constants

### 6.3 7 Conditional Order Types (SSI-style)
| # | Type | Condition | Use Case |
|---|------|----------|---------|
| 1 | Limit Order (LO) | Price = specified level | Buy at BB Lower |
| 2 | Market Order (MP/ATO/ATC) | Immediate fill | Fast entry/exit |
| 3 | Stop Loss | Price ≤ SL | Automated loss cut |
| 4 | Take Profit | Price ≥ TP | Automated profit lock |
| 5 | Trailing Stop | Mobile SL following price | Profit protection |
| 6 | OCO (One-Cancel-Other) | SL + TP placed simultaneously | Risk management |
| 7 | Bracket Order | Entry + SL + TP at once | Most complete |

---

## 7. Foreign Investment Flow Analysis

- **Source:** SSI share-holder-summary (% foreign ownership) + CafeF CoCauSoHuu
- **Positive signal:** Net foreign buying + DXY < 104 + S&P500 risk-on
- **Negative signal:** Continuous net foreign selling + DXY > 106 + FED hawkish

---

## 8. Model Portfolios (iFollow Style)

| Portfolio | Target Return | Max DD | Focus Sectors |
|-----------|--------------|--------|--------------|
| 🚀 Risk-On Growth | +20%+/yr | -15% | Tech, RE, Retail |
| ⚖️ Balanced | +12–18%/yr | -10% | Banking, Tech, Food |
| 🛡️ Safe-Haven | +8–12%/yr | -7% | Banking, Power, Pharma |
| 💵 Dividend | +6–10%/yr (income) | -5% | Banking, Power, O&G |

---

## 9. Smoke Test Suite (v24.0)

### Mandatory tickers on every run:
| Ticker | Exchange | Rationale |
|--------|----------|-----------|
| OIL | UPCOM | Small UPCOM ticker — tests pipeline robustness |
| FPT | HOSE | Tech blue-chip — primary benchmark |
| GAS | HOSE | Large O&G — tests cyclical sector |
| TCB | HOSE | Banking — tests banking sector |
| VIC | HOSE | VN30 component, RE — tests real-estate sector |

### PASS Conditions:
- ≥ 20 rows of OHLCV data
- RSI computed (not NaN)
- Price within valid [Floor, Ceiling] range
- CompositeScore ≥ 0 (no NameError)
""")


# ══════════════════════════════════════════════════════════════
#  CHANGE LOG TAB
# ══════════════════════════════════════════════════════════════
def _run_top_forecast(watch_list: list, horizon_days: int) -> tuple:
    """
    ENH-37 v25: Rich multi-factor forecast engine.
    Each factor produces a numeric contribution AND a bilingual natural language
    explanation so analysts can audit every decision step.
    Returns (gainers, decliners) with full factor breakdown.
    """
    scores = []
    lang_now = getattr(st.session_state, "lang", "VI")
    is_vi = lang_now == "VI"

    for ticker in watch_list:
        try:
            data, src, err = download_data(ticker, days=365, min_rows=40)
            if data.empty or len(data) < 40: continue
            data = clean_data(data)
            if len(data) < 40: continue
            data = calculate_indicators(data)
            last = data.iloc[-1]
            def sv(k):
                try: return float(last[k]) if pd.notna(last[k]) else None
                except: return None

            c_v = sv("Close") or 0
            if c_v <= 0: continue
            rsi     = sv("RSI") or 50
            sma5    = sv("SMA5");  sma20 = sv("SMA20"); sma50 = sv("SMA50")
            sma100  = sv("SMA100"); sma200 = sv("SMA200")
            ema9    = sv("EMA9");  ema21 = sv("EMA21"); ema50 = sv("EMA50"); ema200_v = sv("EMA200")
            macd    = sv("MACD"); macs  = sv("MACD_Signal")
            adx     = sv("ADX") or 15
            atr     = sv("ATR") or c_v * 0.02
            obv     = sv("OBV"); obv_ma = sv("OBV_MA20")
            stoch_k = sv("STOCH_K"); stoch_d = sv("STOCH_D")
            cci     = sv("CCI"); wr = sv("WILLIAMS_R")
            bb_low  = sv("BB_Lower"); bb_up = sv("BB_Upper")
            avg_v   = float(data["Volume"].tail(20).mean())
            last_v  = float(last.get("Volume", avg_v))
            sector  = get_sector(ticker)

            # ── Factor-by-factor scoring WITH explanations ──────────────
            factors = []   # list of (name_vi, name_en, contribution, explanation_vi, explanation_en)

            def add_factor(name_vi, name_en, contrib, expl_vi, expl_en):
                factors.append({
                    "name_vi": name_vi, "name_en": name_en,
                    "contrib": round(contrib, 1),
                    "expl_vi": expl_vi, "expl_en": expl_en,
                })

            # 1. RSI
            if rsi < 30:
                add_factor("RSI quá bán", "RSI Oversold", -12,
                    f"RSI={rsi:.1f} — Vùng quá bán sâu (<30). Áp lực bán đang cực kỳ cao. "
                    f"Thường xảy ra sau chuỗi giảm mạnh. Xác suất hồi phục kỹ thuật ngắn hạn tăng "
                    f"nhưng xu hướng giảm vẫn chiếm ưu thế. Điểm: -12.",
                    f"RSI={rsi:.1f} — Deep oversold zone (<30). Extreme selling pressure. "
                    f"Typically follows sharp decline. Short-term technical bounce likely "
                    f"but downtrend still dominant. Score: -12.")
            elif rsi < 45:
                add_factor("RSI yếu", "RSI Weak", -5,
                    f"RSI={rsi:.1f} — Vùng yếu (30–45). Momentum tiêu cực nhưng chưa quá bán. "
                    f"Giá đang trong quá trình điều chỉnh. Điểm: -5.",
                    f"RSI={rsi:.1f} — Weak zone (30–45). Negative momentum, not yet oversold. "
                    f"Price in correction mode. Score: -5.")
            elif rsi > 70:
                add_factor("RSI quá mua", "RSI Overbought", +12,
                    f"RSI={rsi:.1f} — Vùng quá mua (>70). Momentum rất mạnh, giá đang tăng nhanh. "
                    f"Trong kỳ hạn {horizon_days} ngày, xu hướng tăng có thể tiếp tục nhưng "
                    f"rủi ro điều chỉnh cũng tăng dần. Điểm: +12.",
                    f"RSI={rsi:.1f} — Overbought (>70). Very strong momentum, rapid price gains. "
                    f"Over {horizon_days}-day horizon, uptrend may continue but correction risk grows. Score: +12.")
            elif rsi > 55:
                add_factor("RSI tích cực", "RSI Positive", +5,
                    f"RSI={rsi:.1f} — Vùng tích cực (55–70). Momentum tốt, dòng tiền đang vào. "
                    f"Không quá mua, còn room tăng. Điểm: +5.",
                    f"RSI={rsi:.1f} — Positive zone (55–70). Good momentum, money flowing in. "
                    f"Not overbought, room to run. Score: +5.")
            else:
                add_factor("RSI trung tính", "RSI Neutral", 0,
                    f"RSI={rsi:.1f} — Trung tính (45–55). Không có tín hiệu mạnh từ RSI. "
                    f"Theo dõi các chỉ báo khác để xác định hướng. Điểm: 0.",
                    f"RSI={rsi:.1f} — Neutral (45–55). No strong RSI signal. "
                    f"Rely on other indicators for direction. Score: 0.")

            # 2. SMA trend (most important)
            sma_contrib = 0
            sma_expl_vi = []; sma_expl_en = []
            if c_v and sma20:
                if c_v > sma20:
                    sma_contrib += 6
                    sma_expl_vi.append(f"Giá ({c_v:,.0f}) > SMA20 ({sma20:,.0f}) — xu hướng ngắn hạn tích cực (+6)")
                    sma_expl_en.append(f"Price ({c_v:,.0f}) > SMA20 ({sma20:,.0f}) — positive short-term trend (+6)")
                else:
                    sma_contrib -= 6
                    sma_expl_vi.append(f"Giá ({c_v:,.0f}) < SMA20 ({sma20:,.0f}) — xu hướng ngắn hạn tiêu cực (-6)")
                    sma_expl_en.append(f"Price ({c_v:,.0f}) < SMA20 ({sma20:,.0f}) — negative short-term trend (-6)")
            if c_v and sma50:
                if c_v > sma50:
                    sma_contrib += 10
                    sma_expl_vi.append(f"Giá > SMA50 ({sma50:,.0f}) — xu hướng TĂNG trung hạn ✅ (+10)")
                    sma_expl_en.append(f"Price > SMA50 ({sma50:,.0f}) — medium-term UPTREND ✅ (+10)")
                else:
                    sma_contrib -= 10
                    sma_expl_vi.append(f"Giá < SMA50 ({sma50:,.0f}) — xu hướng GIẢM trung hạn ⚠️ (-10)")
                    sma_expl_en.append(f"Price < SMA50 ({sma50:,.0f}) — medium-term DOWNTREND ⚠️ (-10)")
            if c_v and sma200:
                if c_v > sma200:
                    sma_contrib += 8
                    sma_expl_vi.append(f"Giá > SMA200 ({sma200:,.0f}) — xu hướng TĂNG dài hạn ✅ (+8)")
                    sma_expl_en.append(f"Price > SMA200 ({sma200:,.0f}) — long-term UPTREND ✅ (+8)")
                else:
                    sma_contrib -= 8
                    sma_expl_vi.append(f"Giá < SMA200 ({sma200:,.0f}) — xu hướng GIẢM dài hạn ⚠️ (-8)")
                    sma_expl_en.append(f"Price < SMA200 ({sma200:,.0f}) — long-term DOWNTREND ⚠️ (-8)")
            add_factor("Xu hướng SMA", "SMA Trend", sma_contrib,
                "Phân tích xu hướng SMA20/50/200: " + " | ".join(sma_expl_vi) if sma_expl_vi else "Không đủ dữ liệu SMA.",
                "SMA20/50/200 trend analysis: " + " | ".join(sma_expl_en) if sma_expl_en else "Insufficient SMA data.")

            # 3. EMA cascade
            ema_contrib = 0
            ema_expl_vi = []; ema_expl_en = []
            if ema9 and ema21:
                if ema9 > ema21:
                    ema_contrib += 7
                    ema_expl_vi.append(f"EMA9 ({ema9:,.0f}) > EMA21 ({ema21:,.0f}) — momentum ngắn hạn tăng (+7)")
                    ema_expl_en.append(f"EMA9 ({ema9:,.0f}) > EMA21 ({ema21:,.0f}) — short-term bullish momentum (+7)")
                else:
                    ema_contrib -= 7
                    ema_expl_vi.append(f"EMA9 ({ema9:,.0f}) < EMA21 ({ema21:,.0f}) — momentum ngắn hạn giảm (-7)")
                    ema_expl_en.append(f"EMA9 ({ema9:,.0f}) < EMA21 ({ema21:,.0f}) — short-term bearish momentum (-7)")
            if ema50 and ema200_v:
                if ema50 > ema200_v:
                    ema_contrib += 5
                    ema_expl_vi.append(f"Golden Cross: EMA50 > EMA200 — xu hướng dài hạn tích cực (+5)")
                    ema_expl_en.append(f"Golden Cross: EMA50 > EMA200 — long-term positive trend (+5)")
                else:
                    ema_contrib -= 5
                    ema_expl_vi.append(f"Death Cross: EMA50 < EMA200 — xu hướng dài hạn tiêu cực (-5)")
                    ema_expl_en.append(f"Death Cross: EMA50 < EMA200 — long-term negative trend (-5)")
            add_factor("Phân tích EMA", "EMA Analysis", ema_contrib,
                "EMA cascade: " + " | ".join(ema_expl_vi) if ema_expl_vi else "Không đủ dữ liệu EMA.",
                "EMA cascade: " + " | ".join(ema_expl_en) if ema_expl_en else "Insufficient EMA data.")

            # 4. MACD
            if macd is not None and macs is not None:
                hist_now = macd - macs
                hist_prev = 0
                if len(data) > 2:
                    try:
                        hist_prev = float(data["MACD"].iloc[-2]) - float(data["MACD_Signal"].iloc[-2])
                    except: pass
                expanding = hist_now > hist_prev if macd > macs else hist_now < hist_prev
                if macd > macs:
                    contrib_m = 8 + (3 if expanding else 0)
                    add_factor("MACD tăng", "MACD Bullish", contrib_m,
                        f"MACD ({macd:.2f}) > Signal ({macs:.2f}) — dòng tiền đang VÀO. "
                        f"Histogram dương{' và đang mở rộng ✅ — đà tăng đang tăng tốc' if expanding else ' nhưng thu hẹp — đà tăng chậm lại'}. "
                        f"Điểm: +{contrib_m}.",
                        f"MACD ({macd:.2f}) > Signal ({macs:.2f}) — money flowing IN. "
                        f"Histogram positive{' and expanding ✅ — momentum accelerating' if expanding else ' but shrinking — momentum slowing'}. "
                        f"Score: +{contrib_m}.")
                else:
                    contrib_m = -8 - (3 if expanding else 0)
                    add_factor("MACD giảm", "MACD Bearish", contrib_m,
                        f"MACD ({macd:.2f}) < Signal ({macs:.2f}) — dòng tiền đang RA. "
                        f"Histogram âm{' và đang mở rộng ⚠️ — đà giảm tăng tốc' if expanding else ' nhưng thu hẹp — đà giảm yếu dần'}. "
                        f"Điểm: {contrib_m}.",
                        f"MACD ({macd:.2f}) < Signal ({macs:.2f}) — money flowing OUT. "
                        f"Histogram negative{' and expanding ⚠️ — bearish momentum accelerating' if expanding else ' but shrinking — bearish momentum fading'}. "
                        f"Score: {contrib_m}.")

            # 5. ADX trend strength
            if adx:
                if adx > 25:
                    direction_bias = 1 if (macd and macs and macd > macs) else -1
                    contrib_adx = 5 * direction_bias
                    add_factor("ADX xu hướng mạnh", "ADX Strong Trend", contrib_adx,
                        f"ADX = {adx:.1f} (>25) — Xu hướng RÕ RÀNG. "
                        f"Khi ADX > 25, xu hướng đang chiếm ưu thế {'tăng' if direction_bias > 0 else 'giảm'}. "
                        f"Tín hiệu xu hướng đáng tin cậy hơn khi ADX cao. Điểm: {contrib_adx:+.0f}.",
                        f"ADX = {adx:.1f} (>25) — CLEAR TREND. "
                        f"ADX above 25 confirms {'bullish' if direction_bias > 0 else 'bearish'} trend dominance. "
                        f"Trend-following signals more reliable. Score: {contrib_adx:+.0f}.")
                else:
                    add_factor("ADX thấp", "ADX Low", 0,
                        f"ADX = {adx:.1f} (<25) — Không có xu hướng rõ ràng. Thị trường đang đi ngang. "
                        f"Tránh lệnh theo xu hướng; phù hợp với chiến lược dao động. Điểm: 0.",
                        f"ADX = {adx:.1f} (<25) — No clear trend. Market is ranging/sideways. "
                        f"Avoid trend-following; oscillating strategy suits better. Score: 0.")

            # 6. OBV (money flow proxy)
            if obv is not None and obv_ma is not None:
                if obv > obv_ma:
                    add_factor("OBV dương", "OBV Positive", +6,
                        f"OBV ({obv:,.0f}) > OBV_MA20 ({obv_ma:,.0f}) — Dòng tiền tích lũy tích cực. "
                        f"Khối lượng mua tích lũy theo thời gian đang vượt trội hơn bán. "
                        f"Smart money đang tích lũy. Điểm: +6.",
                        f"OBV ({obv:,.0f}) > OBV_MA20 ({obv_ma:,.0f}) — Positive money flow accumulation. "
                        f"Cumulative buy volume exceeds sell volume. Smart money accumulating. Score: +6.")
                else:
                    add_factor("OBV âm", "OBV Negative", -6,
                        f"OBV ({obv:,.0f}) < OBV_MA20 ({obv_ma:,.0f}) — Dòng tiền phân phối. "
                        f"Khối lượng bán tích lũy đang chiếm ưu thế — dấu hiệu smart money đang thoát hàng. "
                        f"Điểm: -6.",
                        f"OBV ({obv:,.0f}) < OBV_MA20 ({obv_ma:,.0f}) — Distribution phase. "
                        f"Cumulative sell volume dominant — smart money distributing. Score: -6.")

            # 7. Volume spike
            if avg_v > 0 and last_v / avg_v > 1.5:
                add_factor("Khối lượng đột biến", "Volume Spike", +4,
                    f"Khối lượng phiên gần đây = {last_v/avg_v:.1f}× trung bình 20 phiên. "
                    f"Tăng đột biến khối lượng xác nhận sự quan tâm của dòng tiền lớn. "
                    f"Nếu đi kèm xu hướng tăng: tín hiệu tốt. Điểm: +4.",
                    f"Recent session volume = {last_v/avg_v:.1f}× 20-session average. "
                    f"Volume spike confirms institutional interest. "
                    f"If accompanied by uptrend: strong signal. Score: +4.")

            # 8. Bollinger Band position
            if bb_low and bb_up:
                if c_v < bb_low:
                    add_factor("Giá dưới BB Lower", "Price below BB Lower", -8,
                        f"Giá ({c_v:,.0f}) < BB Lower ({bb_low:,.0f}) — Giá đang ngoài dải dưới Bollinger. "
                        f"Điều này phản ánh biến động bất thường về phía giảm. "
                        f"Xác suất hồi về BB_Mid trong ngắn hạn cao, nhưng xu hướng giảm ngắn hạn đang chiếm ưu thế. Điểm: -8.",
                        f"Price ({c_v:,.0f}) < BB Lower ({bb_low:,.0f}) — Price outside lower Bollinger Band. "
                        f"Unusually high downside volatility. Mean reversion to BB_Mid likely short-term, "
                        f"but near-term downtrend dominant. Score: -8.")
                elif c_v > bb_up:
                    add_factor("Giá trên BB Upper", "Price above BB Upper", +8,
                        f"Giá ({c_v:,.0f}) > BB Upper ({bb_up:,.0f}) — Giá ngoài dải trên Bollinger. "
                        f"Momentum cực kỳ mạnh; breakout thực sự trong xu hướng tăng có thể tiếp tục. "
                        f"Tuy nhiên rủi ro điều chỉnh về BB_Mid tăng dần theo thời gian. Điểm: +8.",
                        f"Price ({c_v:,.0f}) > BB Upper ({bb_up:,.0f}) — Price outside upper Bollinger Band. "
                        f"Extreme bullish momentum; in an uptrend this can persist. "
                        f"However mean-reversion risk to BB_Mid grows with time. Score: +8.")

            # 9. Stochastic
            if stoch_k is not None and stoch_d is not None:
                if stoch_k < 20 and stoch_d < 20:
                    add_factor("Stochastic quá bán", "Stochastic Oversold", -5,
                        f"Stoch %K={stoch_k:.1f}, %D={stoch_d:.1f} — Cả hai dưới 20: Quá bán sâu. "
                        f"Tín hiệu đảo chiều tiềm năng nhưng cần xác nhận giá trước khi vào lệnh. Điểm: -5.",
                        f"Stoch %K={stoch_k:.1f}, %D={stoch_d:.1f} — Both below 20: Deep oversold. "
                        f"Potential reversal signal but needs price confirmation before entry. Score: -5.")
                elif stoch_k > 80 and stoch_d > 80:
                    add_factor("Stochastic quá mua", "Stochastic Overbought", +5,
                        f"Stoch %K={stoch_k:.1f}, %D={stoch_d:.1f} — Cả hai trên 80: Quá mua. "
                        f"Momentum mạnh, xu hướng tăng đang chiếm ưu thế. Điểm: +5.",
                        f"Stoch %K={stoch_k:.1f}, %D={stoch_d:.1f} — Both above 80: Overbought. "
                        f"Strong momentum, uptrend dominant. Score: +5.")

            # 10. Geopolitical / macro
            _geo = get_geopolitical_context(sector)
            geo_contrib = _geo["score_adj"] * (horizon_days / 30)
            if _geo["reasons"]:
                add_factor("Vĩ mô/Địa chính trị", "Macro/Geopolitical", geo_contrib,
                    f"Tác động vĩ mô đến {sector} trong {horizon_days} ngày: " +
                    " | ".join(_geo["reasons"][:3]) + f" Điểm tổng: {geo_contrib:+.1f}.",
                    f"Macro impact on {sector} over {horizon_days} days: " +
                    " | ".join(_geo["reasons"][:3]) + f" Total score: {geo_contrib:+.1f}.")

            # Total momentum
            mom = sum(f["contrib"] for f in factors)
            direction = "UP" if mom > 5 else ("DOWN" if mom < -5 else "NEUTRAL")

            # Short human summary (top 3 factors by abs contribution)
            top_factors = sorted(factors, key=lambda x: abs(x["contrib"]), reverse=True)[:3]
            summary_vi = "; ".join([f"[{f['name_vi']}: {f['contrib']:+.0f}] {f['expl_vi'][:80]}..." for f in top_factors])
            summary_en = "; ".join([f"[{f['name_en']}: {f['contrib']:+.0f}] {f['expl_en'][:80]}..." for f in top_factors])

            # Simple reasons list (for compact card display)
            reasons_vi = [f"{f['name_vi']} ({f['contrib']:+.0f})" for f in top_factors]
            reasons_en = [f"{f['name_en']} ({f['contrib']:+.0f})" for f in top_factors]

            scores.append({
                "ticker":      ticker,
                "sector":      sector,
                "price":       c_v,
                "direction":   direction,
                "mom_score":   round(mom, 1),
                "confidence":  round(min(abs(mom)/60, 1.0)*100, 1),
                "atr":         round(atr, 0),
                "stop_loss":   round(c_v - 1.5*atr, 0),
                "tp1":         round(c_v + 2*atr, 0),
                "tp2":         round(c_v + 3.5*atr, 0),
                "rsi":         round(rsi, 1),
                "adx":         round(adx, 1),
                "src":         src,
                "factors":     factors,         # full factor breakdown
                "summary_vi":  summary_vi,
                "summary_en":  summary_en,
                "reasons":     reasons_vi if is_vi else reasons_en,
            })
        except Exception as _e:
            _log.debug(f"Top forecast {ticker}: {_e}")

    gainers   = sorted([s for s in scores if s["direction"]=="UP"],   key=lambda x: x["mom_score"], reverse=True)[:10]
    decliners = sorted([s for s in scores if s["direction"]=="DOWN"],  key=lambda x: x["mom_score"])[:10]
    return gainers, decliners


def _render_forecast_card(s: dict, rank: int, is_vi: bool, card_type: str):
    """Render a rich forecast card with expandable factor breakdown."""
    color = "#00cc44" if card_type == "gain" else "#ff4444"
    arrow = "↑" if card_type == "gain" else "↓"
    reasons = s.get("reasons", [])
    reasons_str = " | ".join(reasons[:3]) if reasons else "–"
    summary = s.get("summary_vi" if is_vi else "summary_en", "")

    st.markdown(f"""
<div style="background:{color}10;border-left:3px solid {color};border-radius:6px;
     padding:10px 14px;margin:4px 0;font-size:12px">
  <b style="color:{color};font-size:15px">#{rank} {s['ticker']}</b>
  <span style="color:#aaa;margin-left:8px">{s['sector']}</span>
  <span style="float:right;color:{color};font-weight:bold">{arrow} Score:{s['mom_score']:+.0f} | {s['confidence']:.0f}%</span><br>
  <span style="color:#ddd">💰 {s['price']:,.0f} VNĐ</span>
  &nbsp;|&nbsp; <span style="color:#888">RSI:{s['rsi']}</span>
  &nbsp;|&nbsp; <span style="color:#888">ADX:{s['adx']}</span>
  &nbsp;|&nbsp; <span style="color:#ff5555">SL:{s['stop_loss']:,.0f}</span>
  &nbsp;|&nbsp; <span style="color:#4e9af1">TP1:{s['tp1']:,.0f} | TP2:{s['tp2']:,.0f}</span><br>
  <span style="color:#aaa;font-size:11px">🔑 {reasons_str}</span>
</div>""", unsafe_allow_html=True)

    # Expandable factor breakdown
    if s.get("factors"):
        with st.expander(f"🔬 {'Phân tích chi tiết' if is_vi else 'Factor breakdown'} — {s['ticker']}", expanded=False):
            if summary:
                st.caption(f"📝 {'Tóm tắt' if is_vi else 'Summary'}: {summary[:300]}")
            st.markdown("---")
            for f in s["factors"]:
                c_val = f["contrib"]
                f_color = "#00cc44" if c_val > 0 else ("#ff4444" if c_val < 0 else "#888")
                f_name = f["name_vi"] if is_vi else f["name_en"]
                f_expl = f["expl_vi"] if is_vi else f["expl_en"]
                bar_pct = min(abs(c_val)/15*100, 100)
                st.markdown(
                    f'<div style="margin:4px 0">'
                    f'<span style="color:{f_color};font-weight:bold">{c_val:+.0f}</span> '
                    f'<b style="color:#ddd">{f_name}</b>'
                    f'<div style="background:#1a1f2e;border-radius:4px;height:6px;margin:2px 0">'
                    f'<div style="width:{bar_pct:.0f}%;background:{f_color};height:6px;border-radius:4px"></div></div>'
                    f'<span style="color:#999;font-size:11px">{f_expl}</span></div>',
                    unsafe_allow_html=True)


def _show_forecast_log(is_vi: bool, fc_log_key: str):
    log = st.session_state.get(fc_log_key, [])
    if not log: return
    st.markdown("---")
    with st.expander("📜 " + ("Lịch Sử Dự Báo" if is_vi else "Forecast History"), expanded=False):
        for entry in log[:10]:
            st.markdown(f"**{entry['datetime']}** — {entry['horizon']} {'ngày' if is_vi else 'days'} | "
                        f"{entry['n_tickers']} tickers | Macro:{entry.get('geo_score',0):+.0f}")
            st.caption("📈 " + ", ".join(entry.get("top_gainers",[])[:5]))
            st.caption("📉 " + ", ".join(entry.get("top_decliners",[])[:5]))
            st.markdown("---")


def render_top_forecast_tab():
    """ENH-37: Top 10 gainers/decliners forecast with 7/14/21/30-day horizons + audit log."""
    is_vi = st.session_state.lang == "VI"
    st.header("🔮 " + ("Dự Báo Top 10 Tăng/Giảm" if is_vi else "Top 10 Gainers/Decliners Forecast"))
    st.info("📌 " + ("Dự báo kỹ thuật đa chỉ số (SMA/EMA/MACD/RSI/ADX/OBV) + bối cảnh vĩ mô. Không phải tư vấn đầu tư."
                      if is_vi else
                      "Multi-indicator technical forecast (SMA/EMA/MACD/RSI/ADX/OBV) + macro context. Not investment advice."))

    col_h, col_run = st.columns([3, 1])
    with col_h:
        horizon = st.selectbox("📅 " + ("Kỳ hạn" if is_vi else "Horizon"),
                               [7, 14, 21, 30],
                               format_func=lambda x: f"{x} " + ("ngày" if is_vi else "days"))
    with col_run:
        run_btn = st.button("🔮 " + ("Chạy Dự Báo" if is_vi else "Run Forecast"), type="primary")

    fc_key = f"_top_forecast_{horizon}"
    fc_log_key = "_top_forecast_log"

    if run_btn:
        watch_list = load_watchlist_from_file(WATCHLIST_FILE_PATH)
        geo = get_geopolitical_context()
        with st.spinner("⏳ " + (f"Đang phân tích {len(watch_list)} mã..." if is_vi
                                   else f"Analysing {len(watch_list)} tickers...")):
            gainers, decliners = _run_top_forecast(watch_list, horizon)
            st.session_state[fc_key] = (gainers, decliners)
            log_entry = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M"), "horizon": horizon,
                "n_tickers": len(watch_list), "geo_score": geo["score_adj"], "geo_summary": geo["summary"],
                "top_gainers":   [g["ticker"] for g in gainers],
                "top_decliners": [d["ticker"] for d in decliners],
            }
            if fc_log_key not in st.session_state: st.session_state[fc_log_key] = []
            st.session_state[fc_log_key].insert(0, log_entry)
            st.success("✅ " + (f"{len(gainers)} mã tăng, {len(decliners)} mã giảm" if is_vi
                                  else f"{len(gainers)} gainers, {len(decliners)} decliners"))

        # ENH-V25: Audit each forecast entry
        for g in gainers:
            append_audit("TOP_FORECAST", f"FORECAST_{horizon}D", g["ticker"], "UP",
                         g.get("mom_score", 0),
                         {"price": g["price"], "mom_score": g["mom_score"],
                          "confidence": g["confidence"], "stop_loss": g["stop_loss"],
                          "tp1": g["tp1"], "tp2": g["tp2"], "rsi": g["rsi"],
                          "adx": g["adx"], "sector": g["sector"],
                          "factors_summary": str(g.get("summary_vi",""))[:200]},
                         lang_now)
        for d in decliners:
            append_audit("TOP_FORECAST", f"FORECAST_{horizon}D", d["ticker"], "DOWN",
                         d.get("mom_score", 0),
                         {"price": d["price"], "mom_score": d["mom_score"],
                          "confidence": d["confidence"], "stop_loss": d["stop_loss"],
                          "tp1": d["tp1"], "tp2": d["tp2"], "rsi": d["rsi"],
                          "adx": d["adx"], "sector": d["sector"],
                          "factors_summary": str(d.get("summary_vi",""))[:200]},
                         lang_now)

    forecast_data = st.session_state.get(fc_key)
    if not forecast_data:
        st.markdown("▶️ " + ("Bấm **Chạy Dự Báo** để bắt đầu." if is_vi else "Press **Run Forecast** to start."))
        _show_forecast_log(is_vi, fc_log_key)
        return

    gainers, decliners = forecast_data
    geo = get_geopolitical_context()

    st.markdown("---")
    col_g, col_d = st.columns(2)
    with col_g:
        st.markdown("### 📈 " + (f"Top 10 Tăng — {horizon} ngày" if is_vi else f"Top 10 Gainers — {horizon}d"))
        for rank, s in enumerate(gainers, 1):
            _render_forecast_card(s, rank, is_vi, "gain")
    with col_d:
        st.markdown("### 📉 " + (f"Top 10 Giảm — {horizon} ngày" if is_vi else f"Top 10 Decliners — {horizon}d"))
        for rank, s in enumerate(decliners, 1):
            _render_forecast_card(s, rank, is_vi, "decline")

    # Macro context summary
    st.markdown("---")
    st.markdown("### 🌍 " + ("Bối cảnh Vĩ mô" if is_vi else "Macro Context"))
    gc1, gc2 = st.columns(2)
    with gc1: st.metric("Macro Score", f"{geo['score_adj']:+.0f}", geo["summary"])
    with gc2:
        for r in geo["reasons"][:3]: st.caption(r)

    # Download
    all_rows = ([{"Type":"Gainer","Rank":i+1,**{k:v for k,v in g.items() if k!="reasons"},
                   "Reasons": " | ".join(g["reasons"][:3])} for i,g in enumerate(gainers)] +
                [{"Type":"Decliner","Rank":i+1,**{k:v for k,v in d.items() if k!="reasons"},
                   "Reasons": " | ".join(d["reasons"][:3])} for i,d in enumerate(decliners)])
    if all_rows:
        csv = pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 CSV", csv, f"forecast_{horizon}d_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

    _show_forecast_log(is_vi, fc_log_key)




# ══════════════════════════════════════════════════════════════════════════
#  ENH-42 (v28): DEEP SCAN MODULE
#  Per-ticker intelligence: RT price · forecasts · intrinsic value ·
#  whale/MM detection · swing-trade risk · entry/exit prices ·
#  bilingual recommendation
# ══════════════════════════════════════════════════════════════════════════

def _ds_forecast_ensemble(closes: np.ndarray, horizon: int) -> np.ndarray:
    """
    Build a lightweight 3-model price-forecast ensemble for the Deep Scan.
    Returns array of length `horizon` (daily closing price predictions).
    Models: Linear Regression (35%) + Holt Double-Exp (35%) + Monte Carlo p50 (30%)
    """
    n = len(closes)
    if n < 20:
        return np.full(horizon, closes[-1])
    try:
        fc_lr, _, _ = forecast_linreg(closes, horizon)
    except Exception:
        fc_lr = np.full(horizon, closes[-1])
    try:
        fc_holt = forecast_holt(closes, horizon)
        if len(fc_holt) < horizon:
            fc_holt = np.pad(fc_holt, (0, horizon - len(fc_holt)), constant_values=fc_holt[-1])
    except Exception:
        fc_holt = np.full(horizon, closes[-1])
    try:
        mc = forecast_monte_carlo(closes, horizon)
        fc_mc = mc.get("p50", np.full(horizon, closes[-1]))
    except Exception:
        fc_mc = np.full(horizon, closes[-1])
    ensemble = fc_lr * 0.35 + fc_holt * 0.35 + fc_mc * 0.30
    return ensemble


def _ds_intrinsic_value(ticker: str, live_price: float, tech_analysis: dict) -> dict:
    """
    Compute a blended intrinsic value estimate using three complementary approaches.
    1. Sector-P/E implied fair value  (most reliable for VN stocks)
    2. DCF via implied EPS × growth    (conservative)
    3. Graham Number proxy             (value floor)

    Returns dict: {iv_pe, iv_dcf, iv_graham, iv_blended, upside_pct, method_used}
    """
    sector     = tech_analysis.get("sector", "Khác")
    tech_score = tech_analysis.get("tech_score", 50)
    ret3m      = tech_analysis.get("ret3m", 0)
    volatility = tech_analysis.get("volatility", 0.25)
    high52     = tech_analysis.get("high52", live_price * 1.2)
    low52      = tech_analysis.get("low52",  live_price * 0.8)

    # 1. Sector P/E implied (use tech_fair_value from DNSE analysis)
    iv_pe = tech_analysis.get("tech_fair_value", 0)
    if iv_pe <= 0:
        sector_pe = tech_analysis.get("sector_pe", 15.0)
        implied_eps = live_price / sector_pe
        iv_pe = round(implied_eps * sector_pe * (1 + ret3m * 0.5), 0)

    # 2. DCF with implied EPS + modest growth assumption
    sector_pe    = tech_analysis.get("sector_pe", 15.0)
    implied_eps  = live_price / max(sector_pe, 1)
    growth_rate  = max(0.05, min(0.25, ret3m * 4 + 0.08))  # annualised from 3M return, bounded
    iv_dcf       = compute_dcf_valuation(
        eps_ttm=implied_eps, eps_growth_rate=growth_rate,
        discount_rate=0.12, terminal_growth=0.05, years=5)

    # 3. Graham Number proxy (use tech-implied EPS + BVPS)
    implied_bvps = tech_analysis.get("implied_bvps", live_price * 0.6)
    iv_graham    = compute_graham_value(implied_eps, implied_bvps)

    # 4. Blended (weights: sector P/E 45% | DCF 35% | Graham 20%)
    vals = [(iv_pe, 0.45), (iv_dcf, 0.35), (iv_graham, 0.20)]
    valid = [(v, w) for v, w in vals if v > 0]
    if valid:
        total_w  = sum(w for _, w in valid)
        iv_blend = sum(v * w for v, w in valid) / total_w
    else:
        iv_blend = live_price

    iv_blend = round_price_hose(iv_blend)
    upside   = round((iv_blend - live_price) / live_price * 100, 1) if live_price > 0 else 0

    return {
        "iv_pe":       round_price_hose(iv_pe),
        "iv_dcf":      round_price_hose(iv_dcf),
        "iv_graham":   round_price_hose(iv_graham),
        "iv_blended":  iv_blend,
        "upside_pct":  upside,
        "method_used": "Sector P/E (45%) + DCF implied (35%) + Graham (20%)",
    }


def _ds_whale_summary(doi_lai: list) -> dict:
    """
    Translate detect_doi_lai signals into a structured whale/MM verdict.
    Returns: {verdict, emoji, color, signals, score}
      verdict = ACCUMULATING | DISTRIBUTING | WATCH | NEUTRAL
    """
    if not doi_lai:
        return {"verdict": "NEUTRAL", "emoji": "➖", "color": "#aaaaaa",
                "signals": [], "score": 0}

    accum_score = 0
    dist_score  = 0
    signals     = []

    for s in doi_lai:
        sig  = s.get("signal", "").lower()
        sev  = s.get("severity", "")
        icon = s.get("icon", "")
        detail = s.get("detail", "")

        if sev == "POSITIVE" or any(k in sig for k in ["tích lũy","smart money","bear trap","accumul"]):
            accum_score += 3 if sev == "POSITIVE" else 2
        elif sev == "HIGH" and any(k in sig for k in ["pump","dump","xả","dump"]):
            dist_score  += 4
        elif sev == "MEDIUM":
            dist_score  += 2
        elif sev == "LOW":
            dist_score  += 1

        signals.append({"icon": icon, "text": s.get("signal",""), "detail": detail, "sev": sev})

    net = accum_score - dist_score
    if net >= 4:
        verdict, emoji, color = "ACCUMULATING", "🐋", "#00cc66"
    elif net <= -3:
        verdict, emoji, color = "DISTRIBUTING", "🔴", "#ff4444"
    elif net >= 1:
        verdict, emoji, color = "WATCH — POSSIBLE ACCUM", "👀", "#66aaff"
    elif net <= -1:
        verdict, emoji, color = "WATCH — POSSIBLE DIST",  "⚠️", "#ffaa44"
    else:
        verdict, emoji, color = "NEUTRAL", "➖", "#aaaaaa"

    return {"verdict": verdict, "emoji": emoji, "color": color,
            "signals": signals, "score": net}


def _ds_swing_risk(tech: dict, doi_lai_summary: dict, atr_pct: float) -> dict:
    """
    Evaluate short-term swing-trade risk level:
    LOW / MEDIUM / HIGH / VERY HIGH
    Based on: volatility, ATR%, RSI zone, ADX, trend position, whale signals.
    """
    risk_score = 0  # higher = riskier

    # Volatility
    vol = tech.get("volatility", 0.25)
    if vol > 0.50:   risk_score += 4
    elif vol > 0.35: risk_score += 2
    elif vol > 0.20: risk_score += 1

    # ATR % of price
    if atr_pct > 5.0:  risk_score += 3
    elif atr_pct > 3.0: risk_score += 2
    elif atr_pct > 2.0: risk_score += 1

    # RSI
    rsi = tech.get("rsi", 50)
    if rsi > 75 or rsi < 25: risk_score += 3
    elif rsi > 65 or rsi < 35: risk_score += 1

    # ADX (low ADX = sideways = noisy)
    adx = tech.get("adx", 20)
    if adx < 15:   risk_score += 2
    elif adx > 40: risk_score += 1  # strong trend but could reverse quickly

    # Trend alignment
    above20 = tech.get("above_sma20", True)
    above50 = tech.get("above_sma50", True)
    if not above20 and not above50: risk_score += 2
    elif not above50:               risk_score += 1

    # Whale warning
    whale_score = doi_lai_summary.get("score", 0)
    if whale_score <= -3:  risk_score += 3  # distribution = high risk
    elif whale_score <= -1: risk_score += 1

    # Price near 52-week high (profit-taking risk)
    pp = tech.get("price_percentile", 0.5)
    if pp > 0.90: risk_score += 2
    elif pp > 0.75: risk_score += 1

    # Map to level
    if risk_score >= 10:
        level, color, emoji = "VERY HIGH",  "#ff1111", "🚨"
    elif risk_score >= 7:
        level, color, emoji = "HIGH",       "#ff6644", "🔴"
    elif risk_score >= 4:
        level, color, emoji = "MEDIUM",     "#ffcc44", "🟡"
    else:
        level, color, emoji = "LOW",        "#00cc66", "🟢"

    return {"level": level, "color": color, "emoji": emoji,
            "score": risk_score, "factors": {
                "volatility": round(vol * 100, 1),
                "atr_pct":    round(atr_pct, 2),
                "rsi":        round(rsi, 1),
                "adx":        round(adx, 1),
                "whale":      whale_score,
            }}


def _ds_recommendation(tech: dict, iv: dict, risk: dict,
                        whale: dict, live: float, lang: str) -> dict:
    """
    Generate a final swing-trade + investment recommendation with entry/exit prices.
    """
    is_vi    = lang == "VI"
    rsi      = tech.get("rsi", 50)
    adx      = tech.get("adx", 20)
    above50  = tech.get("above_sma50", True)
    macd_bull= tech.get("macd_bullish", False)
    vol_spike= tech.get("vol_spike", False)
    ret1m    = tech.get("ret1m", 0)
    ret3m    = tech.get("ret3m", 0)
    bbl      = tech.get("bb_lower", live * 0.97)
    bbu      = tech.get("bb_upper", live * 1.03)
    atr_pct  = risk["factors"].get("atr_pct", 2.0)
    _atr     = live * atr_pct / 100
    upside   = iv.get("upside_pct", 0)
    iv_blend = iv.get("iv_blended", live)
    whale_v  = whale.get("verdict", "NEUTRAL")

    # ── Swing signal ──────────────────────────────────────────────
    swing_bull = sum([
        rsi < 40,
        live < bbl * 1.02,
        macd_bull,
        above50,
        whale_v == "ACCUMULATING",
        vol_spike and macd_bull,
    ])
    swing_bear = sum([
        rsi > 65,
        live > bbu * 0.98,
        not macd_bull,
        whale_v == "DISTRIBUTING",
        tech.get("rsi_overbought", False),
    ])

    if swing_bull >= 3 and swing_bear < 2:
        swing_action = "MUA" if is_vi else "BUY"
        swing_color  = "#00cc44"
    elif swing_bear >= 3:
        swing_action = "BÁN" if is_vi else "SELL"
        swing_color  = "#ff4444"
    elif swing_bull >= 2:
        swing_action = "THEO DÕI — Chờ xác nhận" if is_vi else "WATCH — Await confirmation"
        swing_color  = "#66aaff"
    else:
        swing_action = "TRUNG LẬP" if is_vi else "NEUTRAL"
        swing_color  = "#aaaaaa"

    # ── Investment signal (fundamental-aligned) ───────────────────
    if upside >= 20 and ret3m > -0.15:
        inv_action = "MUA DÀI HẠN" if is_vi else "LONG-TERM BUY"
        inv_color  = "#00cc44"
    elif upside >= 10:
        inv_action = "TÍCH LŨY DẦN" if is_vi else "ACCUMULATE"
        inv_color  = "#66cc88"
    elif upside <= -15:
        inv_action = "TRÁNH / BÁN" if is_vi else "AVOID / SELL"
        inv_color  = "#ff4444"
    elif upside <= -5:
        inv_action = "NẮM GIỮ — THẬN TRỌNG" if is_vi else "HOLD — CAUTION"
        inv_color  = "#ffaa44"
    else:
        inv_action = "NẮM GIỮ" if is_vi else "HOLD"
        inv_color  = "#aaaaaa"

    # ── Entry / Exit / Stop prices ────────────────────────────────
    # Entry: near BB Lower + 20% ATR bounce confirmation
    entry_ideal = round_price_hose(bbl + _atr * 0.20)
    entry       = round_price_hose(min(live, entry_ideal) if entry_ideal < live * 1.01 else live)
    tp1         = round_price_hose(live + 2.0 * _atr)
    tp2         = round_price_hose(live + 3.5 * _atr)
    tp3_inv     = round_price_hose(max(iv_blend, live + 5.0 * _atr))  # longer-term target
    stop        = round_price_hose(max(live - 1.5 * _atr, live * 0.90))

    rr_swing = round((tp1 - entry) / (entry - stop), 2) if (entry - stop) > 0 else 0

    # ── Swing reasoning (key bullet points) ──────────────────────
    bullets_vi = []
    bullets_en = []
    if rsi < 35:
        bullets_vi.append(f"📉 RSI={rsi:.0f} quá bán — áp lực bán cạn dần, xác suất hồi phục cao")
        bullets_en.append(f"📉 RSI={rsi:.0f} oversold — selling exhaustion, bounce probability elevated")
    elif rsi > 65:
        bullets_vi.append(f"📈 RSI={rsi:.0f} quá mua — rủi ro chốt lời ngắn hạn tăng")
        bullets_en.append(f"📈 RSI={rsi:.0f} overbought — short-term profit-taking risk elevated")
    if macd_bull:
        bullets_vi.append("📊 MACD > Signal — momentum đang đảo chiều tăng")
        bullets_en.append("📊 MACD > Signal — momentum turning bullish")
    else:
        bullets_vi.append("📊 MACD < Signal — momentum yếu, thận trọng mua mới")
        bullets_en.append("📊 MACD < Signal — weak momentum, caution on new longs")
    if adx > 25:
        bullets_vi.append(f"📐 ADX={adx:.0f} — xu hướng rõ ràng, giao dịch thuận xu hướng")
        bullets_en.append(f"📐 ADX={adx:.0f} — clear trend, trade with the trend")
    if whale_v == "ACCUMULATING":
        bullets_vi.append("🐋 Smart Money đang tích lũy — dòng tiền thông minh vào")
        bullets_en.append("🐋 Smart Money accumulating — institutional inflows detected")
    elif whale_v == "DISTRIBUTING":
        bullets_vi.append("🔴 Phân phối hàng — cảnh báo đội lái xả")
        bullets_en.append("🔴 Distribution detected — market maker offloading warning")
    if vol_spike:
        bullets_vi.append("📦 Khối lượng đột biến — dòng tiền lớn đang tham gia")
        bullets_en.append("📦 Volume spike — large money flow active")
    if upside > 15:
        bullets_vi.append(f"💎 Định giá nội tại: +{upside}% tiềm năng tăng dài hạn")
        bullets_en.append(f"💎 Intrinsic value: +{upside}% long-term upside potential")
    elif upside < -10:
        bullets_vi.append(f"⚠️ Định giá nội tại: giá thị trường cao hơn giá trị {abs(upside)}%")
        bullets_en.append(f"⚠️ Intrinsic value: market price {abs(upside)}% above fair value")

    bullets = bullets_vi if is_vi else bullets_en

    return {
        "swing_action":  swing_action,
        "swing_color":   swing_color,
        "inv_action":    inv_action,
        "inv_color":     inv_color,
        "entry":         entry,
        "tp1":           tp1,
        "tp2":           tp2,
        "tp3_inv":       tp3_inv,
        "stop":          stop,
        "rr_swing":      rr_swing,
        "bullets":       bullets,
    }


@st.cache_data(ttl=300)
def deep_scan_one_ticker(t: str) -> dict | None:
    """
    ENH-42 (v28): Deep Scan — full intelligence profile for one ticker.
    Returns None if data unavailable.
    Uses SSI real-time price as primary price source.
    Cache TTL = 5 min (300 s) to avoid re-fetching on every rerender.
    """
    try:
        # ── 1. OHLCV + indicators ──────────────────────────────────
        data, src, err = download_data(t, days=730, min_rows=40)
        if data is None or data.empty:
            return None
        data = clean_data(data)
        if len(data) < 40:
            return None
        data = calculate_indicators(data)
        closes  = data["Close"].dropna().values.astype(float)
        volumes = data["Volume"].fillna(0).values.astype(float)
        highs   = data["High"].dropna().values.astype(float) if "High" in data.columns else closes
        lows    = data["Low"].dropna().values.astype(float)  if "Low"  in data.columns else closes

        # ── 2. SSI real-time price ─────────────────────────────────
        rt       = fetch_ssi_realtime_price(t)
        live     = rt.get("price", 0) or float(closes[-1])
        ref_p    = rt.get("reference", live)
        pct_chg  = rt.get("pct_change", (live / ref_p - 1) * 100 if ref_p > 0 else 0)
        rt_vol   = rt.get("volume", float(volumes[-1]) if len(volumes) else 0)
        rt_src   = rt.get("source", src) if rt.get("price", 0) > 0 else src

        # ── 3. Price limits ────────────────────────────────────────
        lims     = get_price_limits(t, ref_p if ref_p > 0 else live)
        ceil_p   = lims.get("ceiling", 0)
        floor_p  = lims.get("floor",   0)

        # ── 4. Technical analysis (reuse DNSE analysis) ───────────
        tech = fetch_dnse_ohlc_analysis(t)
        if not tech or tech.get("error"):
            # Build minimal tech dict from calculated data
            last = data.iloc[-1]
            tech = {
                "price":       live,
                "rsi":         float(last.get("RSI", 50)),
                "adx":         float(last.get("ADX", 20)),
                "macd":        float(last.get("MACD", 0)),
                "macd_sig":    float(last.get("MACD_Signal", 0)),
                "macd_bullish": float(last.get("MACD", 0)) > float(last.get("MACD_Signal", 0)),
                "bb_lower":    float(last.get("BB_Lower", live * 0.97)),
                "bb_upper":    float(last.get("BB_Upper", live * 1.03)),
                "sma20":       float(last.get("SMA20", live)),
                "sma50":       float(last.get("SMA50", live)),
                "above_sma20": live > float(last.get("SMA20", 0) or 0),
                "above_sma50": live > float(last.get("SMA50", 0) or 0),
                "rsi_oversold": float(last.get("RSI", 50)) < 35,
                "rsi_overbought": float(last.get("RSI", 50)) > 70,
                "vol_spike":   False,
                "ret1m":       (closes[-1] / closes[-22] - 1) if len(closes) >= 22 else 0,
                "ret3m":       (closes[-1] / closes[-66] - 1) if len(closes) >= 66 else 0,
                "ret6m":       (closes[-1] / closes[-126] - 1) if len(closes) >= 126 else 0,
                "volatility":  float(np.std(np.diff(np.log(closes[-60:]))) * np.sqrt(252)) if len(closes) >= 20 else 0.25,
                "tech_score":  50,
                "tech_fair_value": live,
                "sector_pe":   15.0,
                "sector":      get_sector(t),
                "high52":      float(highs[-252:].max()) if len(highs) >= 252 else float(highs.max()),
                "low52":       float(lows[-252:].min())  if len(lows) >= 252 else float(lows.min()),
                "price_percentile": 0.5,
                "implied_eps": live / 15.0,
                "implied_bvps": live * 0.6,
            }

        # ── 5. ATR ────────────────────────────────────────────────
        last     = data.iloc[-1]
        atr_v    = float(last.get("ATR", 0)) if "ATR" in data.columns else live * 0.02
        atr_v    = max(atr_v, live * 0.015)  # floor at 1.5%
        atr_pct  = atr_v / live * 100 if live > 0 else 2.0

        # ── 6. Price forecasts (ensemble) ─────────────────────────
        max_horizon = 126  # 6 months trading days
        ensemble    = _ds_forecast_ensemble(closes, max_horizon)
        horizons    = {
            1:   round_price_hose(ensemble[0]),    # 1 day
            2:   round_price_hose(ensemble[1]),    # 2 days
            3:   round_price_hose(ensemble[2]),    # 3 days
            5:   round_price_hose(ensemble[4]),    # 1 week
            10:  round_price_hose(ensemble[9]),    # 2 weeks
            21:  round_price_hose(ensemble[20]),   # ~1 month
            42:  round_price_hose(ensemble[41]),   # ~2 months
            63:  round_price_hose(ensemble[62]),   # ~3 months
            126: round_price_hose(ensemble[125]),  # ~6 months
        }

        # ── 7. Intrinsic value ────────────────────────────────────
        iv = _ds_intrinsic_value(t, live, tech)

        # ── 8. Whale / MM detection ───────────────────────────────
        doi_lai        = detect_doi_lai(data)
        whale_summary  = _ds_whale_summary(doi_lai)

        # ── 9. Swing risk ─────────────────────────────────────────
        risk = _ds_swing_risk(tech, whale_summary, atr_pct)

        # ── 10. Final recommendation ──────────────────────────────
        lang = st.session_state.lang
        rec  = _ds_recommendation(tech, iv, risk, whale_summary, live, lang)

        # ── 11. Volume context ────────────────────────────────────
        avg_vol20  = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
        vol_ratio  = (rt_vol / avg_vol20) if avg_vol20 > 0 and rt_vol > 0 else (
            float(volumes[-1]) / avg_vol20 if avg_vol20 > 0 else 1.0)

        return {
            "ticker":       t,
            "sector":       tech.get("sector", get_sector(t)),
            # ── Price
            "live":         live,
            "ref_price":    ref_p,
            "pct_chg":      round(pct_chg, 2),
            "rt_vol":       int(rt_vol) if rt_vol else int(volumes[-1]) if len(volumes) else 0,
            "vol_ratio":    round(vol_ratio, 2),
            "ceil_p":       ceil_p,
            "floor_p":      floor_p,
            "high52":       tech.get("high52", 0),
            "low52":        tech.get("low52", 0),
            "price_pct52":  round(tech.get("price_percentile", 0.5) * 100, 1),
            "rt_src":       rt_src,
            # ── Technicals
            "rsi":          round(tech.get("rsi", 50), 1),
            "adx":          round(tech.get("adx", 20), 1),
            "macd_bull":    tech.get("macd_bullish", False),
            "bb_lower":     round_price_hose(tech.get("bb_lower", 0)),
            "bb_upper":     round_price_hose(tech.get("bb_upper", 0)),
            "above_sma50":  tech.get("above_sma50", False),
            "above_sma20":  tech.get("above_sma20", False),
            "atr":          round(atr_v, 0),
            "atr_pct":      round(atr_pct, 2),
            "tech_score":   round(tech.get("tech_score", 50), 1),
            "vol_spike":    tech.get("vol_spike", False),
            "ret1m":        round(tech.get("ret1m", 0) * 100, 2),
            "ret3m":        round(tech.get("ret3m", 0) * 100, 2),
            "ret6m":        round(tech.get("ret6m", 0) * 100, 2),
            "volatility":   round(tech.get("volatility", 0.25) * 100, 1),
            # ── Forecasts (% change only — prices stored in fc dict)
            "fc":           horizons,
            "fc_1d_pct":    round((horizons[1]  - live) / live * 100, 2) if live > 0 else 0,
            "fc_2d_pct":    round((horizons[2]  - live) / live * 100, 2) if live > 0 else 0,
            "fc_3d_pct":    round((horizons[3]  - live) / live * 100, 2) if live > 0 else 0,
            "fc_5d_pct":    round((horizons[5]  - live) / live * 100, 2) if live > 0 else 0,
            "fc_10d_pct":   round((horizons[10] - live) / live * 100, 2) if live > 0 else 0,
            "fc_1m_pct":    round((horizons[21] - live) / live * 100, 2) if live > 0 else 0,
            "fc_2m_pct":    round((horizons[42] - live) / live * 100, 2) if live > 0 else 0,
            "fc_3m_pct":    round((horizons[63] - live) / live * 100, 2) if live > 0 else 0,
            "fc_6m_pct":    round((horizons[126]- live) / live * 100, 2) if live > 0 else 0,
            # ── Intrinsic value
            "iv":           iv,
            # ── Whale
            "whale":        whale_summary,
            # ── Risk
            "risk":         risk,
            # ── Recommendation
            "rec":          rec,
        }
    except Exception as e:
        _log.warning(f"deep_scan_one_ticker({t}): {e}")
        return None


def _render_deep_scan_card(result: dict, is_vi: bool) -> None:
    """
    ENH-42 (v28): Render a single-ticker Deep Scan card with all intelligence panels.
    Called once per ticker inside an st.expander.
    """
    t       = result["ticker"]
    live    = result["live"]
    pct_chg = result["pct_chg"]
    sector  = result["sector"]
    rt_src  = result["rt_src"]
    rec     = result["rec"]
    iv      = result["iv"]
    whale   = result["whale"]
    risk    = result["risk"]
    fc      = result["fc"]

    swing_a = rec["swing_action"]
    inv_a   = rec["inv_action"]
    pct_chg_color = "#00cc66" if pct_chg >= 0 else "#ff4444"
    pct_chg_sign  = "+" if pct_chg >= 0 else ""

    # ── Row 1: Price header ──────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 14px">'
            f'<div style="color:#7eb8ff;font-size:13px;font-weight:bold">📡 {"Giá RT (SSI)" if is_vi else "Live (SSI)"}</div>'
            f'<div style="color:#ffffff;font-size:22px;font-weight:bold">{live:,.0f}</div>'
            f'<div style="color:{pct_chg_color};font-size:13px">{pct_chg_sign}{pct_chg:.2f}% | {rt_src}</div>'
            f'<div style="color:#666;font-size:11px">{sector}</div>'
            f'</div>', unsafe_allow_html=True)
    with c2:
        rr = rec["rr_swing"]
        rr_col = "#00cc66" if rr >= 2 else ("#ffcc44" if rr >= 1.5 else "#ff6644")
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 14px">'
            f'<div style="color:#888;font-size:11px">{"📊 Tín hiệu Swing" if is_vi else "📊 Swing Signal"}</div>'
            f'<div style="color:{rec["swing_color"]};font-size:16px;font-weight:bold">{swing_a}</div>'
            f'<div style="color:{rec["inv_color"]};font-size:12px">{"💼 Đầu tư: " if is_vi else "💼 Invest: "}{inv_a}</div>'
            f'<div style="color:{rr_col};font-size:12px">R:R = {rr}:1</div>'
            f'</div>', unsafe_allow_html=True)
    with c3:
        risk_lvl = risk["level"]
        risk_col = risk["color"]
        risk_emo = risk["emoji"]
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 14px">'
            f'<div style="color:#888;font-size:11px">{"⚡ Rủi ro Swing" if is_vi else "⚡ Swing Risk"}</div>'
            f'<div style="color:{risk_col};font-size:16px;font-weight:bold">{risk_emo} {risk_lvl}</div>'
            f'<div style="color:#aaa;font-size:11px">Score: {risk["score"]} | '
            f'Vol: {result["volatility"]}% | ATR: {result["atr_pct"]}%</div>'
            f'<div style="color:#aaa;font-size:11px">RSI: {result["rsi"]} | ADX: {result["adx"]}</div>'
            f'</div>', unsafe_allow_html=True)
    with c4:
        whale_v   = whale["verdict"]
        whale_col = whale["color"]
        whale_emo = whale["emoji"]
        st.markdown(
            f'<div style="background:#111827;border-radius:8px;padding:10px 14px">'
            f'<div style="color:#888;font-size:11px">{"🐋 Cá mập/MM" if is_vi else "🐋 Whale/MM"}</div>'
            f'<div style="color:{whale_col};font-size:15px;font-weight:bold">{whale_emo} {whale_v}</div>'
            f'<div style="color:#aaa;font-size:11px">{"Tín hiệu dòng tiền" if is_vi else "Money flow signals"}: {len(whale["signals"])}</div>'
            f'<div style="color:#aaa;font-size:11px">{"Tích lũy" if is_vi else "Accum"} - {"Phân phối" if is_vi else "Dist"} score: {whale["score"]}</div>'
            f'</div>', unsafe_allow_html=True)

    st.markdown("<div style='margin:10px 0'></div>", unsafe_allow_html=True)

    # ── Row 2: Entry/Exit/Stop + Intrinsic Value ────────────────
    c5, c6 = st.columns(2)
    with c5:
        st.markdown(f'<div style="color:#cccccc;font-size:12px;font-weight:bold;margin-bottom:6px">{"💰 Giá Vào/Ra Khuyến Nghị" if is_vi else "💰 Entry / Exit / Stop Prices"}</div>',
                    unsafe_allow_html=True)
        entry, tp1, tp2, tp3, stop = rec["entry"], rec["tp1"], rec["tp2"], rec["tp3_inv"], rec["stop"]
        ep  = round((entry - live) / live * 100, 1) if live > 0 else 0
        p1  = round((tp1   - live) / live * 100, 1) if live > 0 else 0
        p2  = round((tp2   - live) / live * 100, 1) if live > 0 else 0
        p3  = round((tp3   - live) / live * 100, 1) if live > 0 else 0
        sp  = round((stop  - live) / live * 100, 1) if live > 0 else 0
        _ep_s = f"{ep:+.1f}%" if ep != 0 else "≈ live"
        price_html = (
            f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
            f'<tr><td style="padding:4px 8px;color:#00ff88;font-weight:bold">💰 {"Vào lệnh" if is_vi else "Entry"}</td>'
            f'<td style="padding:4px 8px;color:#00ff88;font-weight:bold;text-align:right">{entry:,.0f}</td>'
            f'<td style="padding:4px 8px;color:#666;text-align:right">{_ep_s}</td></tr>'
            f'<tr><td style="padding:4px 8px;color:#ffcc44">🎯 TP1 {"Swing" if is_vi else "Swing"}</td>'
            f'<td style="padding:4px 8px;color:#ffcc44;text-align:right">{tp1:,.0f}</td>'
            f'<td style="padding:4px 8px;color:#666;text-align:right">{p1:+.1f}%</td></tr>'
            f'<tr><td style="padding:4px 8px;color:#ffaa22">🎯 TP2 {"Swing" if is_vi else "Swing"}</td>'
            f'<td style="padding:4px 8px;color:#ffaa22;text-align:right">{tp2:,.0f}</td>'
            f'<td style="padding:4px 8px;color:#666;text-align:right">{p2:+.1f}%</td></tr>'
            f'<tr><td style="padding:4px 8px;color:#aaddff">💎 TP3 {"Dài hạn" if is_vi else "Long-term"}</td>'
            f'<td style="padding:4px 8px;color:#aaddff;text-align:right">{tp3:,.0f}</td>'
            f'<td style="padding:4px 8px;color:#666;text-align:right">{p3:+.1f}%</td></tr>'
            f'<tr style="border-top:1px solid #333">'
            f'<td style="padding:4px 8px;color:#ff6644">🛑 {"Cắt lỗ" if is_vi else "Stop Loss"}</td>'
            f'<td style="padding:4px 8px;color:#ff6644;text-align:right">{stop:,.0f}</td>'
            f'<td style="padding:4px 8px;color:#666;text-align:right">{sp:+.1f}%</td></tr>'
            f'</table>'
        )
        st.markdown(price_html, unsafe_allow_html=True)

    with c6:
        st.markdown(f'<div style="color:#cccccc;font-size:12px;font-weight:bold;margin-bottom:6px">{"💎 Giá Trị Nội Tại" if is_vi else "💎 Intrinsic Value"}</div>',
                    unsafe_allow_html=True)
        iv_pe      = iv["iv_pe"]
        iv_dcf_v   = iv["iv_dcf"]
        iv_gr      = iv["iv_graham"]
        iv_blend   = iv["iv_blended"]
        iv_upside  = iv["upside_pct"]
        upside_col = "#00cc66" if iv_upside >= 10 else ("#ffaa44" if iv_upside >= 0 else "#ff6644")
        iv_html = (
            f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
            f'<tr><td style="padding:4px 8px;color:#aaa">📊 {"P/E Ngành" if is_vi else "Sector P/E"}</td>'
            f'<td style="padding:4px 8px;color:#ccc;text-align:right">{iv_pe:,.0f}</td></tr>'
            f'<tr><td style="padding:4px 8px;color:#aaa">🏗️ DCF ({"hàm ý" if is_vi else "implied"})</td>'
            f'<td style="padding:4px 8px;color:#ccc;text-align:right">{iv_dcf_v:,.0f}</td></tr>'
            f'<tr><td style="padding:4px 8px;color:#aaa">🔢 Graham</td>'
            f'<td style="padding:4px 8px;color:#ccc;text-align:right">{iv_gr:,.0f}</td></tr>'
            f'<tr style="border-top:1px solid #333">'
            f'<td style="padding:4px 8px;color:#7eb8ff;font-weight:bold">⚖️ {"Hỗn hợp" if is_vi else "Blended"}</td>'
            f'<td style="padding:4px 8px;color:#7eb8ff;font-weight:bold;text-align:right">{iv_blend:,.0f}</td></tr>'
            f'<tr><td colspan="2" style="padding:4px 8px;color:{upside_col};font-weight:bold">'
            f'{"Tiềm năng: " if is_vi else "Upside: "}{iv_upside:+.1f}% '
            f'{"từ giá hiện tại" if is_vi else "vs current price"}</td></tr>'
            f'</table>'
            f'<div style="color:#555;font-size:10px;margin-top:4px">'
            f'{iv["method_used"]}</div>'
        )
        st.markdown(iv_html, unsafe_allow_html=True)

    # ── Row 3: Price Forecasts (% change only, colour-coded) ────────
    st.markdown(
        f'<div style="color:#cccccc;font-size:12px;font-weight:bold;margin:10px 0 6px">'
        f'{"📈 Dự Báo Giá — % thay đổi so với giá hiện tại (Ensemble: LinReg+Holt+MonteCarlo)" if is_vi else "📈 Price Forecasts — % change vs live price (Ensemble: LinReg+Holt+MonteCarlo)"}'
        f'</div>', unsafe_allow_html=True)

    def _fc_tile(horizon_lbl: str, pct: float, full_lbl: str) -> str:
        """Return HTML for one forecast tile showing only % change with colour."""
        if pct > 0.05:
            bg      = "rgba(0,180,80,0.12)"
            border  = "#00b450"
            val_col = "#00e676"
            arrow   = "▲"
        elif pct < -0.05:
            bg      = "rgba(220,50,50,0.12)"
            border  = "#cc3333"
            val_col = "#ff5252"
            arrow   = "▼"
        else:
            bg      = "rgba(100,100,120,0.12)"
            border  = "#555577"
            val_col = "#aaaacc"
            arrow   = "▬"
        sign = "+" if pct > 0 else ""
        return (
            f'<div style="background:{bg};border:1px solid {border};border-radius:8px;'
            f'padding:8px 4px;text-align:center;min-width:0">'
            f'<div style="color:#999;font-size:10px;letter-spacing:0.3px">{full_lbl}</div>'
            f'<div style="color:{val_col};font-size:17px;font-weight:700;line-height:1.2">'
            f'{arrow} {sign}{pct:.2f}%</div>'
            f'</div>'
        )

    fc_meta = [
        (result["fc_1d_pct"],  "1d",  "1 ngày"   if is_vi else "1 day"),
        (result["fc_2d_pct"],  "2d",  "2 ngày"   if is_vi else "2 days"),
        (result["fc_3d_pct"],  "3d",  "3 ngày"   if is_vi else "3 days"),
        (result["fc_5d_pct"],  "5d",  "5 ngày"   if is_vi else "5 days"),
        (result["fc_10d_pct"], "10d", "10 ngày"  if is_vi else "10 days"),
        (result["fc_1m_pct"],  "1M",  "1 tháng"  if is_vi else "1 month"),
        (result["fc_2m_pct"],  "2M",  "2 tháng"  if is_vi else "2 months"),
        (result["fc_3m_pct"],  "3M",  "3 tháng"  if is_vi else "3 months"),
        (result["fc_6m_pct"],  "6M",  "6 tháng"  if is_vi else "6 months"),
    ]
    # Split into two rows: short-term (1d–10d) then medium/long (1M–6M)
    st.markdown(
        f'<div style="color:#777;font-size:10px;margin-bottom:4px">'
        f'{"⚡ Ngắn hạn" if is_vi else "⚡ Short-term"}</div>',
        unsafe_allow_html=True)
    cols_short = st.columns(5)
    for col, (pct, lbl, full) in zip(cols_short, fc_meta[:5]):
        with col:
            st.markdown(_fc_tile(lbl, pct, full), unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:#777;font-size:10px;margin:8px 0 4px">'
        f'{"📅 Trung / Dài hạn" if is_vi else "📅 Medium / Long-term"}</div>',
        unsafe_allow_html=True)
    cols_long = st.columns(4)
    for col, (pct, lbl, full) in zip(cols_long, fc_meta[5:]):
        with col:
            st.markdown(_fc_tile(lbl, pct, full), unsafe_allow_html=True)

    # ── Row 4: Whale signals detail ──────────────────────────────
    if whale["signals"]:
        with st.expander(f'🐋 {"Chi tiết dòng tiền cá mập / MM" if is_vi else "Whale/MM Money Flow Detail"} ({len(whale["signals"])} {"tín hiệu" if is_vi else "signals"})'):
            for s in whale["signals"]:
                sev_col = {"HIGH": "#ff4444", "MEDIUM": "#ffaa44", "LOW": "#888",
                           "POSITIVE": "#00cc66"}.get(s["sev"], "#aaa")
                st.markdown(
                    f'<div style="background:#0d1525;border-left:3px solid {sev_col};'
                    f'border-radius:6px;padding:8px 12px;margin:4px 0">'
                    f'<b style="color:{sev_col}">{s["icon"]} {s["text"]}</b><br>'
                    f'<span style="color:#aaa;font-size:12px">{s["detail"]}</span>'
                    f'</div>', unsafe_allow_html=True)

    # ── Row 5: Recommendation bullets ───────────────────────────
    if rec["bullets"]:
        st.markdown(f'<div style="color:#cccccc;font-size:12px;font-weight:bold;margin:10px 0 4px">{"📋 Luận Điểm Giao Dịch" if is_vi else "📋 Trading Rationale"}</div>',
                    unsafe_allow_html=True)
        for b in rec["bullets"]:
            st.markdown(f'<div style="color:#b0b8cc;font-size:12px;padding:2px 0">{b}</div>',
                        unsafe_allow_html=True)

    # ── Row 6: 52-week + returns ─────────────────────────────────
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    r_cols = st.columns(6)
    metrics = [
        (f"52W {"Đỉnh" if is_vi else "High"}", f"{result['high52']:,.0f}"),
        (f"52W {"Đáy" if is_vi else "Low"}",  f"{result['low52']:,.0f}"),
        (f"{"Vị trí 52W" if is_vi else "52W %ile"}", f"{result['price_pct52']:.0f}%"),
        (f"1M {"Ret" if True else "Return"}", f"{result['ret1m']:+.1f}%"),
        (f"3M {"Ret" if True else "Return"}", f"{result['ret3m']:+.1f}%"),
        (f"{"Vol/MA20" if True else "Vol/MA20"}", f"{result['vol_ratio']:.1f}×"),
    ]
    for col, (lbl, val) in zip(r_cols, metrics):
        with col:
            st.metric(lbl, val)


def render_deep_scan_tab():
    """
    ENH-42 (v28): Deep Scan — scan all tickers (or custom list) and render
    a full intelligence card per ticker.
    """
    is_vi = st.session_state.lang == "VI"
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
    st.header("🧭 " + ("Deep Scan — Phân Tích Toàn Diện Từng Mã" if is_vi
                        else "Deep Scan — Full Intelligence Per Ticker"))
    st.caption(
        "📡 SSI iboard real-time · " +
        ("Dự báo giá 5d/10d/1M–6M · Giá trị nội tại · Phát hiện cá mập/MM · "
         "Rủi ro swing · Khuyến nghị vào/ra với lý giải đầy đủ. "
         "Dữ liệu giá thực từ SSI; forecasts = ensemble kỹ thuật (LinReg+Holt+MC)."
         if is_vi else
         "Price forecasts 5d/10d/1M–6M · Intrinsic value · Whale/MM detection · "
         "Swing risk · Entry/exit with full rationale. "
         "Live prices via SSI iboard; forecasts = technical ensemble (LinReg+Holt+MC).")
    )
    st.divider()

    # ── Ticker input ──────────────────────────────────────────────
    watch_list = load_watchlist_from_file(WATCHLIST_FILE_PATH)
    _inp_label = ("🎯 Nhập mã cổ phiếu (cách nhau bằng dấy phẩy) — Để trống để quét toàn bộ Watchlist"
                  if is_vi else
                  "🎯 Enter ticker symbols (comma-separated) — Leave blank to scan full Watchlist")
    custom_input = st.text_input(
        _inp_label,
        value="",
        placeholder=("VD: FPT, VCB, SHB — hoặc để trống" if is_vi
                     else "e.g. FPT, VCB, SHB — or leave blank"),
        key="deep_scan_custom_tickers",
        help=("Nhập mã HOSE/HNX/UPCOM cách nhau bằng dấu phẩy. Để trống = quét toàn bộ Watchlist."
              if is_vi else
              "Enter HOSE/HNX/UPCOM tickers separated by commas. Blank = full Watchlist scan."),
    )

    if custom_input and custom_input.strip():
        raw_tokens = [t.strip().upper() for t in custom_input.replace(";", ",").split(",")]
        scan_list  = list(dict.fromkeys(t for t in raw_tokens if t and t.isalpha()))
        if not scan_list:
            st.warning("⚠️ " + ("Không nhận ra mã nào — dùng Watchlist." if is_vi
                                  else "No valid tickers — using Watchlist."))
            scan_list = watch_list
        else:
            st.info(
                f"🎯 {'Danh sách tuỳ chỉnh' if is_vi else 'Custom scan'}:  "
                f"**{len(scan_list)}** tickers  |  `{'  ·  '.join(scan_list)}`"
            )
    else:
        scan_list = watch_list
        st.info(
            f"📋 {'Watchlist' if is_vi else 'Watchlist'}: **{len(scan_list)}** tickers  |  "
            f"{'Nhập mã ở trên để quét mã tuỳ chọn ↑' if is_vi else 'Enter tickers above for custom scan ↑'}"
        )

    # ── Filters ───────────────────────────────────────────────────
    colA, colB, colC, colD = st.columns(4)
    with colA:
        show_buy_only = st.checkbox(
            "🟢 " + ("Chỉ BUY" if is_vi else "BUY only"), value=False,
            key="ds_filter_buy")
    with colB:
        show_accum_only = st.checkbox(
            "🐋 " + ("Chỉ Tích lũy" if is_vi else "Accumulating only"), value=False,
            key="ds_filter_accum")
    with colC:
        min_risk = st.selectbox(
            ("Max rủi ro" if is_vi else "Max risk"),
            options=["ALL","LOW","MEDIUM","HIGH","VERY HIGH"],
            index=0, key="ds_risk_filter")
    with colD:
        sort_by = st.selectbox(
            ("Sắp xếp theo" if is_vi else "Sort by"),
            options=(["Tech Score", "Upside %", "Risk Score (asc)", "Ticker A-Z"]
                     if not is_vi else
                     ["Điểm kỹ thuật", "Upside %", "Rủi ro (thấp→cao)", "Mã A-Z"]),
            index=0, key="ds_sort_by")

    st.markdown("---")

    # ── Run scan ──────────────────────────────────────────────────
    _btn_lbl = (f"▶️ Quét Deep Scan {len(scan_list)} mã" if is_vi
                else f"▶️ Run Deep Scan — {len(scan_list)} Tickers")
    if st.button(_btn_lbl, type="primary", use_container_width=True):
        results = []
        errors  = []
        pb = st.progress(0, "Initialising Deep Scan…")
        status_ph = st.empty()

        for i, t in enumerate(scan_list):
            pb.progress((i + 1) / len(scan_list),
                        text=f"🔬 {'Đang quét' if is_vi else 'Scanning'}: {t} ({i+1}/{len(scan_list)})")
            status_ph.caption(f"⚡ {t}: SSI RT → OHLCV → indicators → forecast → IV…")
            try:
                r = deep_scan_one_ticker(t)
                if r:
                    results.append(r)
                else:
                    errors.append(f"{t}: No data returned")
            except Exception as e:
                errors.append(f"{t}: {e}")
                _log.warning(f"deep_scan {t}: {e}")

        pb.empty(); status_ph.empty()
        st.session_state["ds_results"] = results
        st.session_state["ds_errors"]  = errors
        st.success(
            f"✅ {'Hoàn tất' if is_vi else 'Complete'}: "
            f"{len(results)} {'mã' if is_vi else 'tickers'} | "
            f"{len(errors)} {'lỗi' if is_vi else 'errors'} | "
            f"{datetime.now().strftime('%H:%M:%S')}"
        )
        if errors:
            with st.expander(f"⚠️ {len(errors)} errors"):
                for e in errors: st.caption(e)

    # ── Display results ───────────────────────────────────────────
    raw_results = st.session_state.get("ds_results", [])
    if not raw_results:
        st.info("☝️ " + ("Nhấn nút bên trên để bắt đầu Deep Scan." if is_vi
                          else "Press the button above to start the Deep Scan."))
        return

    # Apply filters
    RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY HIGH": 3}
    filtered = raw_results
    if show_buy_only:
        filtered = [r for r in filtered if "BUY" in r["rec"]["swing_action"].upper()
                    or "MUA" in r["rec"]["swing_action"].upper()]
    if show_accum_only:
        filtered = [r for r in filtered if "ACCUM" in r["whale"]["verdict"].upper()
                    or "TÍCH LŨY" in r["whale"]["verdict"].upper()]
    if min_risk != "ALL":
        max_idx = RISK_ORDER.get(min_risk, 3)
        filtered = [r for r in filtered
                    if RISK_ORDER.get(r["risk"]["level"], 3) <= max_idx]

    # Sort
    sort_lower = sort_by.lower()
    if "tech" in sort_lower or "điểm" in sort_lower:
        filtered.sort(key=lambda r: r["tech_score"], reverse=True)
    elif "upside" in sort_lower:
        filtered.sort(key=lambda r: r["iv"]["upside_pct"], reverse=True)
    elif "risk" in sort_lower or "rủi ro" in sort_lower:
        filtered.sort(key=lambda r: r["risk"]["score"])
    else:
        filtered.sort(key=lambda r: r["ticker"])

    # ── Summary table ─────────────────────────────────────────────
    st.subheader(f"{'📊 Bảng Tổng Hợp' if is_vi else '📊 Summary Table'} — {len(filtered)}/{len(raw_results)} tickers")
    summary_rows = []
    for r in filtered:
        swing_sig  = r["rec"]["swing_action"]
        whale_vd   = r["whale"]["verdict"]
        risk_lvl   = r["risk"]["level"]
        iv_upside  = r["iv"]["upside_pct"]
        # helper: coloured pct string (plain text for table — Streamlit styled later)
        def _fp(v): return f"{'+' if v>0 else ''}{v:.2f}%"
        summary_rows.append({
            ("Mã" if is_vi else "Ticker"):                r["ticker"],
            ("Ngành" if is_vi else "Sector"):             r["sector"],
            ("Giá RT" if is_vi else "Live"):              f"{r['live']:,.0f}",
            ("% Ngày" if is_vi else "Day%"):              f"{r['pct_chg']:+.2f}%",
            ("Tín hiệu Swing" if is_vi else "Swing Signal"): swing_sig,
            "RSI":                                        r["rsi"],
            "Tech Score":                                 r["tech_score"],
            "🐋 MM":                                      r["whale"]["emoji"] + " " + whale_vd[:10],
            "Risk":                                       r["risk"]["emoji"] + " " + risk_lvl,
            "IV Upside":                                  _fp(iv_upside),
            # ── Forecast % columns (pct-only, sortable numerically via raw dict) ──
            ("FC 1d" if not is_vi else "DK 1ng"):         _fp(r["fc_1d_pct"]),
            ("FC 2d" if not is_vi else "DK 2ng"):         _fp(r["fc_2d_pct"]),
            ("FC 3d" if not is_vi else "DK 3ng"):         _fp(r["fc_3d_pct"]),
            ("FC 5d" if not is_vi else "DK 5ng"):         _fp(r["fc_5d_pct"]),
            ("FC 10d" if not is_vi else "DK 10ng"):       _fp(r["fc_10d_pct"]),
            ("FC 1M" if not is_vi else "DK 1T"):          _fp(r["fc_1m_pct"]),
            ("FC 3M" if not is_vi else "DK 3T"):          _fp(r["fc_3m_pct"]),
            ("FC 6M" if not is_vi else "DK 6T"):          _fp(r["fc_6m_pct"]),
            # ──────────────────────────────────────────────────────
            ("Vào lệnh" if is_vi else "Entry"):           f"{r['rec']['entry']:,.0f}",
            ("Cắt lỗ" if is_vi else "Stop"):              f"{r['rec']['stop']:,.0f}",
        })
    if summary_rows:
        df_sum = pd.DataFrame(summary_rows)
        sig_col = "Tín hiệu Swing" if is_vi else "Swing Signal"

        # Columns that contain signed-% strings and should be colour-coded
        _pct_cols_vi  = ["% Ngày","IV Upside","DK 1ng","DK 2ng","DK 3ng",
                          "DK 5ng","DK 10ng","DK 1T","DK 3T","DK 6T"]
        _pct_cols_en  = ["Day%","IV Upside","FC 1d","FC 2d","FC 3d",
                          "FC 5d","FC 10d","FC 1M","FC 3M","FC 6M"]
        _pct_cols     = _pct_cols_vi if is_vi else _pct_cols_en
        _pct_cols     = [c for c in _pct_cols if c in df_sum.columns]

        def _style_pct_cell(val):
            try:
                v = float(str(val).replace("%","").replace("+",""))
                if v > 0.05:   return "color:#00e676;font-weight:bold"
                elif v < -0.05: return "color:#ff5252;font-weight:bold"
                else:           return "color:#aaaacc"
            except Exception:
                return ""

        try:
            styled = df_sum.style.map(style_action, subset=[sig_col])
            if _pct_cols:
                styled = styled.map(_style_pct_cell, subset=_pct_cols)
            show_df(styled)
        except Exception:
            show_df(df_sum)

    st.divider()

    # ── Per-ticker expandable cards ───────────────────────────────
    st.subheader("🔍 " + ("Chi Tiết Từng Mã" if is_vi else "Per-Ticker Detail"))

    for r in filtered:
        t        = r["ticker"]
        swing_a  = r["rec"]["swing_action"]
        risk_emo = r["risk"]["emoji"]
        whale_emo= r["whale"]["emoji"]
        live     = r["live"]
        pct      = r["pct_chg"]
        iv_up    = r["iv"]["upside_pct"]
        pct_sign = "+" if pct >= 0 else ""
        iv_sign  = "+" if iv_up >= 0 else ""
        exp_label = (
            f"{risk_emo} {t} | {live:,.0f} ({pct_sign}{pct:.2f}%) | "
            f"{'Swing' if is_vi else 'Swing'}: {swing_a} | "
            f"{whale_emo} | IV: {iv_sign}{iv_up:.1f}% | "
            f"{'Rủi ro' if is_vi else 'Risk'}: {r['risk']['level']}"
        )
        with st.expander(exp_label, expanded=False):
            _render_deep_scan_card(r, is_vi)

    # ── Download CSV ──────────────────────────────────────────────
    if summary_rows:
        st.divider()
        try:
            csv_buf = pd.DataFrame(summary_rows).to_csv(index=False, encoding="utf-8-sig")
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="⬇️ " + ("Tải CSV" if is_vi else "Download CSV"),
                data=csv_buf,
                file_name=f"deep_scan_{ts}.csv",
                mime="text/csv",
                use_container_width=False,
            )
        except Exception:
            pass

    st.caption(
        "⚠️ " + (
            "Dự báo giá là mô hình toán học tự động, không phải dự đoán chắc chắn. "
            "Giá trị nội tại dựa trên EPS/BVPS hàm ý từ giá thị trường và P/E ngành. "
            "Không phải tư vấn đầu tư — chỉ mang tính tham khảo kỹ thuật."
            if is_vi else
            "Price forecasts are automated quantitative models, not guaranteed predictions. "
            "Intrinsic values use market-implied EPS/BVPS and sector P/E benchmarks. "
            "Not investment advice — for technical reference only."
        )
    )


# ══════════════════════════════════════════════════════════════
#  SSI LIVE MARKET BOARD TAB  (ENH-43 — v29.0)
# ══════════════════════════════════════════════════════════════
def render_ssi_realtime_tab():
    """
    ENH-43: Real-time SSI iboard market scanner tab.
    Displays live prices, top movers, order book, and transaction log
    using SSI iboard-query API (no auth required).
    """
    is_vi = st.session_state.lang == "VI"
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)

    if is_vi:
        st.header("📡 Bảng Giá SSI Live — Thời Gian Thực")
        st.caption(
            "Dữ liệu từ SSI iboard-query API · Làm mới tự động theo chu kỳ bạn chọn · "
            "Bao gồm giá, biến động, khối lượng, thông tin khối ngoại"
        )
    else:
        st.header("📡 SSI Live Market Board — Real-Time")
        st.caption(
            "Data from SSI iboard-query API · Auto-refresh at selected interval · "
            "Includes price, change, volume, foreign investor activity"
        )

    # ── Controls row ──────────────────────────────────────────
    col_grp, col_ref, col_sort = st.columns([3, 2, 3])
    with col_grp:
        group_options = list(SSI_MARKET_GROUPS.keys())
        group_labels  = [f"{SSI_MARKET_GROUPS[g][0]} ({SSI_MARKET_GROUPS[g][1] or 'All'})" for g in group_options]
        sel_group_idx = st.selectbox(
            "📊 " + ("Nhóm cổ phiếu" if is_vi else "Market group"),
            options=range(len(group_options)),
            format_func=lambda i: group_labels[i],
            index=0,
            key="ssi_rt_group",
        )
        sel_group = group_options[sel_group_idx]

    with col_ref:
        auto_refresh = st.toggle(
            "🔄 " + ("Tự làm mới" if is_vi else "Auto-refresh"),
            value=False,
            key="ssi_rt_autorefresh",
        )
        if auto_refresh:
            refresh_secs = st.select_slider(
                ("Chu kỳ (giây)" if is_vi else "Interval (sec)"),
                options=[10, 15, 30, 60, 120],
                value=30,
                key="ssi_rt_interval",
            )

    with col_sort:
        sort_col = st.selectbox(
            "↕️ " + ("Sắp xếp theo" if is_vi else "Sort by"),
            options=(
                ["±% (cao→thấp)", "±% (thấp→cao)", "KL giao dịch", "GT (tỷ)", "NN mua ròng", "Mã A-Z"]
                if is_vi else
                ["±% (high→low)", "±% (low→high)", "Volume", "Value (B)", "Net foreign buy", "Ticker A-Z"]
            ),
            index=0,
            key="ssi_rt_sort",
        )

    manual_refresh = st.button(
        "🔄 " + ("Làm Mới Ngay" if is_vi else "Refresh Now"),
        type="primary",
        key="ssi_rt_refresh",
    )

    # Auto-refresh trigger via session state counter
    if "ssi_rt_refresh_count" not in st.session_state:
        st.session_state.ssi_rt_refresh_count = 0
    if manual_refresh:
        st.session_state.ssi_rt_refresh_count += 1
        st.cache_data.clear()

    if auto_refresh:
        import time as _time
        _time.sleep(0.1)   # yield to allow UI to render
        try:
            tool_search_result = None
            # Use streamlit-autorefresh if available, otherwise use rerun
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=refresh_secs * 1000, key="ssi_rt_auto_key")
        except ImportError:
            st.info(
                "💡 " + (
                    f"Cài `pip install streamlit-autorefresh` để bật tự động làm mới. "
                    f"Hiện tại nhấn nút 🔄 để cập nhật."
                    if is_vi else
                    f"Install `pip install streamlit-autorefresh` for auto-refresh. "
                    f"Use 🔄 Refresh Now to update manually."
                )
            )

    # ── Load data ─────────────────────────────────────────────
    with st.spinner(("Đang tải dữ liệu SSI..." if is_vi else "Loading SSI live data...")):
        df = fetch_ssi_market_group(sel_group)

    if df.empty:
        st.error(
            "❌ " + (
                "Không thể tải dữ liệu từ SSI. Có thể thị trường đóng cửa hoặc API tạm thời không khả dụng."
                if is_vi else
                "Unable to load data from SSI. Market may be closed or API temporarily unavailable."
            )
        )
        return

    # Show server time
    try:
        ts_r = requests.get("https://iboard-query.ssi.com.vn/system/time",
                            headers=_SSI_HDR, timeout=4)
        if ts_r.ok:
            server_ms = ts_r.json().get("data", 0)
            server_dt = datetime.fromtimestamp(server_ms / 1000)
            st.caption(
                f"🕐 " + ("Giờ máy chủ SSI" if is_vi else "SSI server time") +
                f": **{server_dt.strftime('%H:%M:%S %d/%m/%Y')}** · "
                f"{'Phiên' if is_vi else 'Session'}: "
                f"**{_ssi_session_label(df['Phiên'].iloc[0] if 'Phiên' in df.columns and len(df) > 0 else '', lang=('VI' if is_vi else 'EN'))}**  ·  "
                f"{len(df)} {'mã' if is_vi else 'tickers'}"
            )
    except Exception:
        st.caption(f"{'Tải lúc' if is_vi else 'Loaded at'}: {datetime.now().strftime('%H:%M:%S')}  ·  {len(df)} {'mã' if is_vi else 'tickers'}")

    # ── Apply sort ────────────────────────────────────────────
    sort_lower = sort_col.lower()
    if "cao" in sort_lower or "high→" in sort_lower or "high->" in sort_lower:
        df = df.sort_values("±%", ascending=False)
    elif "thấp" in sort_lower or "low→" in sort_lower or "low->" in sort_lower:
        df = df.sort_values("±%", ascending=True)
    elif "kl giao" in sort_lower or "volume" in sort_lower:
        df = df.sort_values("KL", ascending=False)
    elif "gt" in sort_lower or "value" in sort_lower:
        df = df.sort_values("GT(B)", ascending=False)
    elif "nn" in sort_lower or "foreign" in sort_lower:
        df["_nn_net"] = df["NN Mua"] - df["NN Bán"]
        df = df.sort_values("_nn_net", ascending=False)
        df = df.drop(columns=["_nn_net"])
    else:
        df = df.sort_values("Mã")

    # ── Market overview metrics ───────────────────────────────
    up_cnt   = int((df["±%"] > 0.05).sum())
    dn_cnt   = int((df["±%"] < -0.05).sum())
    flat_cnt = int(len(df) - up_cnt - dn_cnt)
    total_val = df["GT(B)"].sum()
    total_vol = df["KL"].sum()
    nn_buy    = df["NN Mua"].sum()
    nn_sell   = df["NN Bán"].sum()
    nn_net    = nn_buy - nn_sell

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("🟢 " + ("Tăng" if is_vi else "Advancing"), up_cnt,
                  delta=f"+{up_cnt - dn_cnt} {'so bên bán' if is_vi else 'vs decliners'}")
    with m2:
        st.metric("🔴 " + ("Giảm" if is_vi else "Declining"), dn_cnt)
    with m3:
        st.metric("⚪ " + ("Đi ngang" if is_vi else "Flat"), flat_cnt)
    with m4:
        st.metric(
            "💰 " + ("Tổng GT (tỷ)" if is_vi else "Total Value (B)"),
            f"{total_val:,.1f}",
        )
    with m5:
        nn_sign = "+" if nn_net >= 0 else ""
        st.metric(
            "🌐 " + ("NN mua ròng" if is_vi else "Net Foreign Buy"),
            f"{nn_sign}{nn_net:,.0f}",
            delta="buy" if nn_net > 0 else "sell",
        )

    st.divider()

    # ── Tabs: Full Board | Top Movers | Foreign Activity | Order Book ──
    sub_labels = (
        ["📋 Bảng giá", "🏆 Top biến động", "🌐 Khối ngoại", "📖 Sổ lệnh & Lịch sử khớp"]
        if is_vi else
        ["📋 Full Board", "🏆 Top Movers", "🌐 Foreign Activity", "📖 Order Book & Trades"]
    )
    sub1, sub2, sub3, sub4 = st.tabs(sub_labels)

    # ── Sub1: Full board ──────────────────────────────────────
    with sub1:
        # Build display table
        _disp_cols = ["Mã", "Tên", "Giá", "±", "±%", "TC", "Mở", "Cao", "Thấp",
                      "KL", "GT(B)", "Bid1", "BidV1", "Ask1", "AskV1"]
        disp_df = df[[c for c in _disp_cols if c in df.columns]].copy()

        # Format numbers
        for c in ["Giá", "±", "TC", "Mở", "Cao", "Thấp", "Bid1", "Ask1"]:
            if c in disp_df.columns:
                disp_df[c] = disp_df[c].apply(
                    lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else ("–" if x == 0 else str(x))
                )
        for c in ["KL", "BidV1", "AskV1"]:
            if c in disp_df.columns:
                disp_df[c] = disp_df[c].apply(
                    lambda x: f"{int(x):,}" if isinstance(x, (int, float)) and x > 0 else "–"
                )
        if "±%" in disp_df.columns:
            disp_df["±%"] = disp_df["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
        if "GT(B)" in disp_df.columns:
            disp_df["GT(B)"] = disp_df["GT(B)"].apply(lambda x: f"{x:,.1f}" if isinstance(x, float) else str(x))

        # Style: colour ±% column
        def _style_pct(v):
            try:
                val = float(str(v).replace("%", "").replace("+", ""))
                if val > 0.05:   return "color:#00e676;font-weight:bold"
                elif val < -0.05: return "color:#ff5252;font-weight:bold"
                else:             return "color:#aaaacc"
            except Exception:
                return ""

        def _style_price(v):
            """No colour for price columns — return empty."""
            return ""

        try:
            styled = disp_df.style.map(_style_pct, subset=["±%"])
            show_df(styled)
        except Exception:
            show_df(disp_df)

        # Download CSV
        try:
            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ " + ("Tải CSV" if is_vi else "Download CSV"),
                data=csv_data,
                file_name=f"ssi_{sel_group}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        except Exception:
            pass

    # ── Sub2: Top Movers ─────────────────────────────────────
    with sub2:
        n_top = 10
        gainers = df.nlargest(n_top, "±%")
        losers  = df.nsmallest(n_top, "±%")
        most_active_vol = df.nlargest(n_top, "KL")
        most_active_val = df.nlargest(n_top, "GT(B)")

        col_g, col_l = st.columns(2)
        with col_g:
            st.subheader("🟢 " + (f"Top {n_top} Tăng" if is_vi else f"Top {n_top} Gainers"))
            _cols = ["Mã", "Giá", "±%", "KL"]
            g_disp = gainers[[c for c in _cols if c in gainers.columns]].copy()
            if "±%" in g_disp.columns:
                g_disp["±%"] = g_disp["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
            if "Giá" in g_disp.columns:
                g_disp["Giá"] = g_disp["Giá"].apply(lambda x: f"{x:,.0f}" if isinstance(x, float) and x > 0 else "–")
            if "KL" in g_disp.columns:
                g_disp["KL"] = g_disp["KL"].apply(lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else "–")
            try:
                styled_g = g_disp.style.map(_style_pct, subset=["±%"])
                show_df(styled_g)
            except Exception:
                show_df(g_disp)

        with col_l:
            st.subheader("🔴 " + (f"Top {n_top} Giảm" if is_vi else f"Top {n_top} Losers"))
            l_disp = losers[[c for c in _cols if c in losers.columns]].copy()
            if "±%" in l_disp.columns:
                l_disp["±%"] = l_disp["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
            if "Giá" in l_disp.columns:
                l_disp["Giá"] = l_disp["Giá"].apply(lambda x: f"{x:,.0f}" if isinstance(x, float) and x > 0 else "–")
            if "KL" in l_disp.columns:
                l_disp["KL"] = l_disp["KL"].apply(lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else "–")
            try:
                styled_l = l_disp.style.map(_style_pct, subset=["±%"])
                show_df(styled_l)
            except Exception:
                show_df(l_disp)

        st.divider()
        col_v, col_vv = st.columns(2)
        with col_v:
            st.subheader("📊 " + (f"Top {n_top} KL Giao Dịch" if is_vi else f"Top {n_top} by Volume"))
            v_disp = most_active_vol[["Mã", "Giá", "±%", "KL"]].copy() if all(c in most_active_vol.columns for c in ["Mã", "Giá", "±%", "KL"]) else most_active_vol.head()
            if "±%" in v_disp.columns:
                v_disp["±%"] = v_disp["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
            if "Giá" in v_disp.columns:
                v_disp["Giá"] = v_disp["Giá"].apply(lambda x: f"{x:,.0f}" if isinstance(x, float) and x > 0 else "–")
            if "KL" in v_disp.columns:
                v_disp["KL"] = v_disp["KL"].apply(lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else "–")
            try:
                styled_v = v_disp.style.map(_style_pct, subset=["±%"])
                show_df(styled_v)
            except Exception:
                show_df(v_disp)

        with col_vv:
            st.subheader("💰 " + (f"Top {n_top} GT Giao Dịch" if is_vi else f"Top {n_top} by Value"))
            vv_disp = most_active_val[["Mã", "Giá", "±%", "GT(B)"]].copy() if all(c in most_active_val.columns for c in ["Mã", "Giá", "±%", "GT(B)"]) else most_active_val.head()
            if "±%" in vv_disp.columns:
                vv_disp["±%"] = vv_disp["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
            if "Giá" in vv_disp.columns:
                vv_disp["Giá"] = vv_disp["Giá"].apply(lambda x: f"{x:,.0f}" if isinstance(x, float) and x > 0 else "–")
            try:
                styled_vv = vv_disp.style.map(_style_pct, subset=["±%"])
                show_df(styled_vv)
            except Exception:
                show_df(vv_disp)

    # ── Sub3: Foreign Activity ────────────────────────────────
    with sub3:
        if is_vi:
            st.subheader("🌐 Hoạt Động Khối Ngoại")
        else:
            st.subheader("🌐 Foreign Investor Activity")

        if "NN Mua" in df.columns and "NN Bán" in df.columns:
            df_nn = df.copy()
            df_nn["NN Ròng"] = df_nn["NN Mua"] - df_nn["NN Bán"]
            net_buy  = df_nn.nlargest(10, "NN Ròng")
            net_sell = df_nn.nsmallest(10, "NN Ròng")

            # Summary
            total_nn_buy_bn  = df_nn["NN Mua"].sum() * df_nn["Giá"].astype(float, errors="ignore").mean() / 1e9 if "Giá" in df_nn.columns else 0
            c_nb, c_ns = st.columns(2)
            with c_nb:
                st.metric(
                    "🟢 " + ("Tổng NN Mua (CP)" if is_vi else "Total Foreign Buy (shares)"),
                    f"{int(nn_buy):,}",
                )
            with c_ns:
                net_sign = "+" if nn_net >= 0 else ""
                st.metric(
                    ("🔴 Tổng NN Bán (CP)" if is_vi else "🔴 Total Foreign Sell (shares)"),
                    f"{int(nn_sell):,}",
                    delta=f"{'Ròng mua +' if nn_net >= 0 else 'Ròng bán '}{abs(int(nn_net)):,}",
                )

            st.divider()
            col_nbuy, col_nsell = st.columns(2)
            with col_nbuy:
                st.markdown("#### 🟢 " + ("NN Mua Ròng Nhiều Nhất" if is_vi else "Top Net Foreign Buy"))
                nb_disp = net_buy[["Mã", "Giá", "±%", "NN Mua", "NN Bán", "NN Ròng"]].copy()
                if "±%" in nb_disp.columns:
                    nb_disp["±%"] = nb_disp["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
                for col_ in ["NN Mua", "NN Bán", "NN Ròng"]:
                    if col_ in nb_disp.columns:
                        nb_disp[col_] = nb_disp[col_].apply(
                            lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else "–")
                try:
                    styled_nb = nb_disp.style.map(_style_pct, subset=["±%"])
                    show_df(styled_nb)
                except Exception:
                    show_df(nb_disp)

            with col_nsell:
                st.markdown("#### 🔴 " + ("NN Bán Ròng Nhiều Nhất" if is_vi else "Top Net Foreign Sell"))
                ns_disp = net_sell[["Mã", "Giá", "±%", "NN Mua", "NN Bán", "NN Ròng"]].copy()
                if "±%" in ns_disp.columns:
                    ns_disp["±%"] = ns_disp["±%"].apply(lambda x: f"{x:+.2f}%" if isinstance(x, float) else str(x))
                for col_ in ["NN Mua", "NN Bán", "NN Ròng"]:
                    if col_ in ns_disp.columns:
                        ns_disp[col_] = ns_disp[col_].apply(
                            lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else "–")
                try:
                    styled_ns = ns_disp.style.map(_style_pct, subset=["±%"])
                    show_df(styled_ns)
                except Exception:
                    show_df(ns_disp)

            # Room remaining chart
            st.divider()
            st.markdown("#### 🔓 " + ("Room Ngoại Còn Lại (Top 15)" if is_vi else "Foreign Room Remaining (Top 15)"))
            if "NN Còn" in df.columns and "Mã" in df.columns:
                room_df = df[df["NN Còn"] > 0].nlargest(15, "NN Còn")[["Mã", "NN Còn", "±%"]].copy()
                if not room_df.empty:
                    try:
                        import plotly.graph_objects as _go
                    except ImportError:
                        pass
                    try:
                        fig_room = _go.Figure(_go.Bar(
                            x=room_df["Mã"],
                            y=room_df["NN Còn"],
                            marker_color=[
                                "#00e676" if (isinstance(p, float) and p > 0) else
                                ("#ff5252" if (isinstance(p, float) and p < 0) else "#aaaacc")
                                for p in room_df["±%"]
                            ],
                            text=[f"{int(v):,}" for v in room_df["NN Còn"]],
                            textposition="outside",
                        ))
                        fig_room.update_layout(
                            height=300, template="plotly_dark",
                            title=("Số CP ngoại còn được phép mua" if is_vi else "Shares remaining for foreign purchase"),
                            margin=dict(t=40, b=20, l=10, r=10),
                            yaxis_title="Số CP",
                        )
                        st.plotly_chart(fig_room, width="stretch")
                    except Exception:
                        show_df(room_df)
        else:
            st.info("No foreign investor data in the loaded group." if not is_vi else "Không có dữ liệu khối ngoại cho nhóm đã chọn.")

    # ── Sub4: Order Book + Transaction Log ───────────────────
    with sub4:
        if is_vi:
            st.subheader("📖 Sổ Lệnh & Lịch Sử Khớp Lệnh")
        else:
            st.subheader("📖 Order Book & Trade History")

        # Ticker selector from loaded group
        available_tickers = sorted(df["Mã"].unique().tolist()) if "Mã" in df.columns else []
        if not available_tickers:
            st.info("No tickers available." if not is_vi else "Không có mã nào khả dụng.")
            return

        col_ob_sel, col_ob_load = st.columns([3, 1])
        with col_ob_sel:
            sel_ob_ticker = st.selectbox(
                "🔍 " + ("Chọn mã để xem" if is_vi else "Select ticker"),
                options=available_tickers,
                key="ssi_rt_ob_ticker",
            )
        with col_ob_load:
            st.write("")
            st.write("")
            load_ob = st.button(
                "📥 " + ("Tải sổ lệnh" if is_vi else "Load"),
                key="ssi_rt_ob_load",
            )

        if sel_ob_ticker:
            # Show live quote for this ticker from the group data
            row_data = df[df["Mã"] == sel_ob_ticker]
            if not row_data.empty:
                rr = row_data.iloc[0]
                q1, q2, q3, q4, q5, q6 = st.columns(6)
                with q1:
                    price_val = rr.get("Giá", 0)
                    pct_val   = rr.get("±%", 0)
                    pct_sign  = "+" if isinstance(pct_val, float) and pct_val >= 0 else ""
                    st.metric(
                        ("Giá Khớp" if is_vi else "Matched"), 
                        f"{price_val:,.0f}" if isinstance(price_val, (int, float)) and price_val > 0 else "–",
                        delta=f"{pct_sign}{pct_val:.2f}%" if isinstance(pct_val, float) else None,
                    )
                with q2:
                    ref_val = rr.get("TC", 0)
                    st.metric("TC", f"{ref_val:,.0f}" if isinstance(ref_val, (int, float)) and ref_val > 0 else "–")
                with q3:
                    ceil_val = rr.get("Trần", 0)
                    st.metric("🔴 " + ("Trần" if is_vi else "Ceil"), f"{ceil_val:,.0f}" if isinstance(ceil_val, (int, float)) and ceil_val > 0 else "–")
                with q4:
                    floor_val = rr.get("Sàn giá", 0)
                    st.metric("💚 " + ("Sàn" if is_vi else "Floor"), f"{floor_val:,.0f}" if isinstance(floor_val, (int, float)) and floor_val > 0 else "–")
                with q5:
                    kl_val = rr.get("KL", 0)
                    st.metric("📊 KL", f"{int(kl_val):,}" if isinstance(kl_val, (int, float)) else "–")
                with q6:
                    gt_val = rr.get("GT(B)", 0)
                    st.metric("💰 GT", f"{gt_val:,.1f}B" if isinstance(gt_val, (int, float)) else "–")

                # Order book top 3 bids/asks
                st.markdown("##### 📒 " + ("Top 3 Bid / Ask" if not is_vi else "Top 3 Giá Mua / Giá Bán"))
                ob_rows = []
                for i in range(1, 4):
                    bid_p = rr.get(f"Bid{i}" if i == 1 else f"best{i}Bid", 0) if i == 1 else df[df["Mã"] == sel_ob_ticker].iloc[0].get("Bid1", 0) if i == 1 else 0
                    ask_p = rr.get(f"Ask{i}" if i == 1 else f"best{i}Offer", 0) if i == 1 else 0

                    # Use Bid1/Ask1 from the main df columns (we have best1Bid etc. in the raw data)
                bid_data = {"Mua 1": (rr.get("Bid1", 0), rr.get("BidV1", 0))}
                ask_data = {"Bán 1": (rr.get("Ask1", 0), rr.get("AskV1", 0))}

                ob_table = {
                    ("Giá Mua" if is_vi else "Bid Price"): [f"{bid_data['Mua 1'][0]:,.0f}" if bid_data["Mua 1"][0] > 0 else "–"],
                    ("KL Mua" if is_vi else "Bid Vol"): [f"{int(bid_data['Mua 1'][1]):,}" if bid_data["Mua 1"][1] > 0 else "–"],
                    ("Giá Bán" if is_vi else "Ask Price"): [f"{ask_data['Bán 1'][0]:,.0f}" if ask_data["Bán 1"][0] > 0 else "–"],
                    ("KL Bán" if is_vi else "Ask Vol"): [f"{int(ask_data['Bán 1'][1]):,}" if ask_data["Bán 1"][1] > 0 else "–"],
                }
                show_df(pd.DataFrame(ob_table))

            # Transaction log
            st.markdown("##### 📈 " + ("Lịch Sử Khớp Lệnh Gần Nhất" if is_vi else "Recent Matched Orders"))
            le_df = fetch_ssi_le_table(sel_ob_ticker, page_size=30)
            if not le_df.empty:
                def _style_side(v):
                    if "Mua" in str(v):  return "color:#00e676;font-weight:bold"
                    if "Bán" in str(v):  return "color:#ff5252;font-weight:bold"
                    return "color:#aaaacc"
                try:
                    styled_le = le_df.style.map(_style_side, subset=["Chiều"])
                    show_df(styled_le)
                except Exception:
                    show_df(le_df)
            else:
                st.info(
                    "⚠️ " + (
                        "Không tải được lịch sử khớp lệnh. Có thể thị trường chưa mở hoặc API giới hạn."
                        if is_vi else
                        "Could not load trade history. Market may be closed or API limited."
                    )
                )

    st.caption(
        "⚠️ " + (
            "Dữ liệu từ SSI iBoard API — chỉ mang tính tham khảo, không phải khuyến nghị đầu tư. "
            "SSI iboard-query không yêu cầu xác thực nhưng có thể bị giới hạn ngoài giờ giao dịch."
            if is_vi else
            "Data from SSI iBoard API — for reference only, not investment advice. "
            "SSI iboard-query requires no auth but may be rate-limited outside trading hours."
        )
    )


def render_changelog_tab():
    # ENH-V25: Inject v25 at top
    is_vi = st.session_state.lang == "VI"
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
    v28_html = """
<div style='background:#0f172a;border:2px solid #7eb8ff;border-radius:10px;padding:16px 20px;margin:8px 0'>
<h3 style='color:#7eb8ff;margin:0 0 10px'>🆕 v28.0 — Deep Scan Module (ENH-42)</h3>
<p style='color:#cbd5e1;font-size:13px'>
<b>ENH-42</b> New <b>🧭 Deep Scan</b> tab — full per-ticker intelligence module scanning all Watchlist tickers (or a custom comma-separated list) via SSI real-time data:<br>
• <b>SSI real-time prices</b> (iboard-query) with daily % change and volume<br>
• <b>Price forecasts</b> for 5d / 10d / 1M / 2M / 3M / 6M — Ensemble of LinReg (35%) + Holt Double-Exponential (35%) + Monte Carlo p50 (30%)<br>
• <b>Intrinsic Value</b> — blended Sector P/E (45%) + implied DCF (35%) + Graham Number (20%), with upside % vs current price<br>
• <b>Entry / TP1 / TP2 / TP3 (long-term) / Stop-Loss</b> prices with % from live price<br>
• <b>Swing Risk Level</b> (Low / Medium / High / Very High) — scored from volatility, ATR, RSI, ADX, trend position, whale signals<br>
• <b>Whale / Market-Maker detection</b> — Accumulating / Distributing / Neutral verdict from detect_doi_lai analysis with detailed signals<br>
• <b>Swing + Investment recommendation</b> with full rationale bullets (bilingual VI/EN)<br>
• <b>Summary table</b> (all tickers at a glance) + per-ticker expandable cards + CSV download<br>
• <b>Filters</b>: BUY only, Accumulating only, Max risk level, Sort by Tech Score / Upside / Risk / Ticker
</p>
</div>
"""
    st.markdown(v28_html, unsafe_allow_html=True)
    v27_html = """
<div style='background:#0f172a;border:1px solid #00ff88;border-radius:10px;padding:16px 20px;margin:8px 0'>
<h3 style='color:#00ff88;margin:0 0 10px'>🆕 v27.0 — Custom Ticker Input + Technical Indicators Panel (ENH-40/41)</h3>
<p style='color:#cbd5e1;font-size:13px'>
<b>ENH-40</b> Market Scanner — Custom ticker input (comma-separated) above the scan button. Leave blank to scan the full Watchlist. Invalid entries are silently filtered. Info bar shows Custom N tickers vs Watchlist N tickers, always with SSI-RT pipeline note.<br>
<b>ENH-41</b> Scanner Expanders — Full Technical Indicators panel inside every BUY/SELL signal expander: SSI-RT live price, Bollinger Band position, RSI colour-coded, ADX trend strength, Stochastic %K, Volume/MA20, EMA9/21 crossover, SMA50/200 Golden/Death Cross, ATR as price derivation basis. Price Derivation table shows the exact formula used to calculate each recommended price level (Buy, TP1, TP2, Stop).
</p>
</div>
"""
    st.markdown(v27_html, unsafe_allow_html=True)
    v26_html = """
<div style='background:#0f172a;border:1px solid #00cc66;border-radius:10px;padding:16px 20px;margin:8px 0'>
<h3 style='color:#00cc66;margin:0 0 10px'>🆕 v26.0 — Recommended Buy & Sell Prices (ENH-37/38/39)</h3>
<p style='color:#cbd5e1;font-size:13px'>
<b>ENH-37</b> Market Scanner — added <b>💰 Mua KN</b> (Recommended Buy) and <b>🎯 Bán TP1/TP2</b> columns derived from real-time SSI/CafeF price + ATR/BB analysis. Visible at a glance in the scan table.<br>
<b>ENH-38</b> Smart Signals — prominent Recommended Price Card in every BUY/SELL signal expander, showing Entry / TP1 / TP2 / Stop-Loss / Upside% / Risk% / R:R ratio with colour coding.<br>
<b>ENH-39</b> <code>compute_recommended_prices()</code> — unified price recommendation engine: Live RT price → BB Lower/Upper → ATR cascade. Handles BUY, SELL, and WATCH signals distinctly. Enforces exchange floor/ceiling limits.
</p>
</div>
"""
    st.markdown(v26_html, unsafe_allow_html=True)
    v25_html = """
<div style='background:#0f172a;border:1px solid #4e9af1;border-radius:10px;padding:16px 20px;margin:8px 0'>
<h3 style='color:#4e9af1;margin:0 0 10px'>🚀 v25.0 — Insights, Audit & Explanations</h3>
<p style='color:#cbd5e1;font-size:13px'>
<b>ENH-V25-01</b> Bilingual Tooltip CSS — hover tooltips for RSI/MACD/SMA50/EMA200/BB/ADX/VWAP/ROE/PE/ATR trên mọi tab<br>
<b>ENH-V25-02</b> Score Explanation Detail — giải thích ngôn ngữ tự nhiên cho từng chiều rủi ro (Nợ/Thanh khoản/Lợi nhuận/Tăng trưởng/Định giá) và valuation upside/discount<br>
<b>ENH-V25-03</b> Combined Deep Audit + Stock Profiler — Tooltip CSS + risk/valuation explanations hiển thị trong cả hai tab<br>
<b>ENH-V25-04</b> Universal Audit Log (Tab 15) — Ghi lại MỌI hành động: scanner, profiler, deep audit, top forecast, ML. Export CSV, lọc theo category/signal/ticker/date, so sánh khuyến nghị vs thực tế<br>
<b>ENH-V25-05</b> Top Forecast 10-Factor Breakdown — mỗi dự báo giải thích 9–10 yếu tố (RSI, SMA trend, EMA cascade, MACD + histogram, ADX, OBV, Volume spike, BB position, Stochastic, Macro/Geo) bằng ngôn ngữ tự nhiên VI/EN với điểm đóng góp từng yếu tố<br>
<b>ENH-V25-06</b> Daily Market Insights Panel — hiển thị tự động khi mở app: tâm lý thị trường tổng thể, DXY/S&P500/Oil/Gold metrics, chiến lược theo khung giờ (ATO/Sáng/Cửa sổ vàng 13–14h/ATC), khuyến nghị ngành hôm nay
</p>
</div>
"""
    st.markdown(v25_html, unsafe_allow_html=True)

    st.header(f"📝 {L['tab11']}")
    st.markdown("""
## 📝 Application Change Log

---

### v28.0 — 2026-03-11 · DEEP SCAN MODULE

**🟢 New Tab: 🧭 Deep Scan (ENH-42)**

| ID | Feature | Details |
|----|---------|---------|
| ENH-42 | Deep Scan Tab | Full per-ticker intelligence: SSI-RT price · Forecasts 5d/10d/1M/2M/3M/6M · Intrinsic value (P/E+DCF+Graham blended) · Entry/TP1/TP2/TP3/Stop · Swing risk scoring · Whale/MM detection · Buy/Sell rationale |

**Key capabilities:**
- SSI iboard-query real-time prices with day% and volume
- Price forecast ensemble (LinReg 35% + Holt 35% + Monte Carlo 30%) for 6 horizons
- Intrinsic value: Sector P/E (45%) + implied DCF (35%) + Graham Number (20%)
- Swing risk score from 8 factors: volatility, ATR%, RSI zone, ADX, trend, whale signals, 52W position
- Whale/MM detection via detect_doi_lai: ACCUMULATING / DISTRIBUTING / NEUTRAL verdict
- Entry price near BB Lower + 20% ATR; TP1/TP2/TP3; Stop at 1.5× ATR below live
- Filters: BUY only, Accumulating only, Max risk, Sort options
- Summary table + expandable cards + CSV download

---

### v27.0 — 2026-03-11 · CUSTOM TICKER INPUT + TECHNICAL INDICATORS PANEL

**🟢 New Features:**

| ID | Feature | Details |
|----|---------|---------|
| ENH-40 | Custom Ticker Input | Comma-separated ticker box above scan button in Market Scanner. Blank = full Watchlist scan. Auto-deduplicates, uppercases, filters non-alpha. Info bar shows source (Custom vs Watchlist) + SSI-RT pipeline label. |
| ENH-41 | Technical Indicators Panel | Full per-ticker tech panel inside every BUY/SELL signal expander: SSI-RT live price, BB position%, RSI (colour-coded), ADX trend label, Stochastic %K, Volume/MA20, EMA9/21 crossover, SMA50/200 Golden/Death Cross, ATR basis. Price Derivation table shows exact formula for each price level. |

**📋 Notes:**
- Custom scan respects all sidebar filters (trend, liquidity, RSI thresholds)
- Price derivation table uses actual ATR + BB values from the scan, showing VND amounts
- Scan button dynamically shows count: "🔄 Scan N Tickers"

---

### v26.0 — 2026-03-10 · RECOMMENDED BUY & SELL PRICES

**🟢 New Features:**

| ID | Feature | Details |
|----|---------|---------|
| ENH-37 | Market Scanner Rec Prices | 💰 Mua KN + 🎯 Bán TP1/TP2 + 🛑 Cắt Lỗ columns in scan table; real-time price card in BUY/SELL expanders |
| ENH-38 | Smart Signals Price Cards | Colour-coded entry/exit card in every signal expander: Entry → TP1 → TP2 + R:R badge |
| ENH-39 | compute_recommended_prices() | Unified engine: live RT price (SSI→CafeF) → BB Lower/Upper → ATR. BUY/SELL/WATCH handled distinctly. Exchange floor/ceiling enforced. |

**📋 Audit Trail:**
- All recommended prices derived from live SSI-iboard / CafeF PriceRealTimeHeader data
- Fallback chain: SSI-RT → CafeF-RT → OHLCV close (same as FIX-30 price pipeline)
- R:R ≥ 2:1 shown in green ✅, 1.5–2 in yellow ⚠️, < 1.5 in red ❌

---

### v24.0 — 2026-03-09 · SMART SIGNALS + MENU RESTRUCTURE + AI MACRO

**🟢 New Features:**

| ID | Feature | Details |
|----|---------|---------|
| ENH-34 | 🎯 Smart Signals Tab | Replaces "Top 30 Buy" — unified tab with: **Top 30 Mua** + **Top 30 Bán** (with full per-ticker reasoning + position sizing), **Gom Hàng** (whale accumulation), **Xả Hàng** (whale distribution), **Daily Market Recommendation banner** (mood: BULLISH/BEARISH/MIXED, strategic advice, macro adj). All 4 sub-tabs + daily banner in one scan run. |
| ENH-35 | 🤖 AI Economy Context | `get_geopolitical_context()` expanded: AI economy sector impact (Công nghệ/Fintech +4pts), VN market characteristics (95% retail, T+2 margin dynamics, foreign room, credit growth 14-16%), VN GDP forecast 6.5–7.5%, export dependency risk. Used in ML Forecast reasoning + Smart Signals banner. |
| ENH-36 | 💬 Bilingual Tooltips | CSS `.tt` class — hover any `.tt`-wrapped text shows translation (VI→EN or EN→VI) via `data-tip` attribute. Applied in signal table headers and key indicator labels. |
| ENH-37 | 📐 Multi-SMA Sidebar Filter | Added SMA5/SMA7/SMA10/SMA20/SMA50 multiselect in sidebar. Trend filter now checks price > ALL selected MAs (configurable). Default: SMA50 only. |
| ENH-38 | 📡 SSI Pipeline Priority | SSI iboard-api is now **first** in the 7-source OHLCV download pipeline (was second after DNSE). All sidebar and status captions updated to `SSI→DNSE→CafeF→...`. |
| ENH-39 | 🗂️ Menu Restructure | Tabs reorganised for better UX flow: [Trading] Scanner → Smart Signals → Profiler → Deep Audit → Portfolios → ML Forecast → Global Markets | [Tools] Backtest → History → Guide → Changelog → Smoke → Forecast Log → Top Forecast. |

**📋 Audit Trail — v24.0:**
- Smoke test mandatory tickers: OIL, FPT, GAS, TCB, VIC (unchanged)
- Smart Signals tab uses same `scan_one_ticker()` as Scanner → consistent signals
- Whale detection uses `_ly_giai` keyword matching (non-blocking, reuses cached explanation)
- All v24 changes pass Python AST check (zero syntax errors)

---

### v23.0 — 2026-03-09 · LIVE PRICE + BUG FIXES (from error_log.txt)

**🔴 Critical Bug Fixes:**

| ID | Component | Issue | Fix |
|----|-----------|-------|-----|
| FIX-25 | `fetch_ssi_news` | **NameError**: Function body existed (line 2748) but `def fetch_ssi_news(ticker, n=10):` declaration was missing — orphaned docstring/body with no function name. `render_stock_profiler_tab` called `fetch_ssi_news(ticker)` → immediate crash. | Restored `@st.cache_data(ttl=3600)` decorator and `def fetch_ssi_news(ticker: str, n: int = 10) -> list:` declaration before the function body. |
| FIX-26 | `show_df` / PyArrow | **ArrowTypeError**: `Stoch%K` column in scan results contains mixed `float` + `str "–"` → PyArrow Table.from_pandas fails with `"Expected bytes, got a 'float' object"`. | Rewrote `show_df()` to detect mixed-type object columns using `set(type(v).__name__ ...)` and cast to uniform `str` before rendering. Uses `f"{x:,.1f}"` for floats. |
| FIX-27 | Model Portfolios | **Always empty**: Hard sector filter + full `min_score` together meant zero stocks ever matched. `fetch_cafef_key_ratios` called inside the loop (blocking, can raise) added further failures. | Two-pass strategy: pass 1 uses 40% relaxed score for preferred sectors; pass 2 falls back to any sector with score ≥ 5. `fetch_cafef_key_ratios` wrapped in try/except. Added `Preferred ✅` column. |
| FIX-28 | Deep Audit | `audit_extra` dict missing `sma5`, `sma10`, `sma30`, `sma100`, `sma200`, `ema9`, `ema21`, `ema50`, `ema200` → SMA/EMA grid panel showed all "–" even after audit. | Added all 9 EMA/SMA values to `audit_extra` dict (already extracted as `_s5`, `_e9` etc. — just not saved). |
| FIX-29 | Deep Audit | SSI real-time price data (Ceiling/Floor/Reference) was fetched but not displayed in metrics row. | Added RT price metrics display row (🔴Trần / 🟡TC / 💚Live / 🔵Sàn) immediately below main metrics; falls back to estimated `get_price_limits()` if SSI unavailable. |
| FIX-30 | Market Scanner | **BSR and other tickers showing stale OHLCV close price** (previous session's close, not live). Scanner always used `c_v = float(latest["Close"])` from OHLCV data — no real-time price lookup. | Added SSI iboard real-time price fetch (`fetch_ssi_realtime_price`) in `scan_one_ticker()`. Priority: SSI-RT → CafeF-RT → OHLCV. Price limits recalculated from live reference. `Source` column now shows `SSI-RT`, `CafeF-RT`, or OHLCV source name. |

**🟢 Guide Tab Enhancement:**

| ID | Feature | Details |
|----|---------|---------|
| ENH-31 | Guide v23 | Updated Getting Started sub-tab: full Composite Score breakdown table (all scoring factors with point values), real-time price flow explanation, recommended workflow table, detailed signal trigger conditions — bilingual VI/EN |

**📋 Audit Trail — v24.0:**
- Smoke test mandatory tickers: OIL (UPCOM), FPT (HOSE), GAS (HOSE), TCB (HOSE), VIC (HOSE)
- All fixes verified via Python AST check (zero syntax errors)
- FIX-30 tested: SSI-RT fetch wrapped in try/except — degrades gracefully to OHLCV when market closed

---

### v24.0 — 2026-03-09 · SMOKE TEST + BRD + CRITICAL BUG FIXES

**🔴 Critical Bug Fixes:**

| ID | Component | Issue | Fix |
|----|-----------|-------|-----|
| FIX-22 | `compute_composite_score` | **NameError**: `ema200`, `sma200`, `sma100`, `ema9`, `ema21`, `sma5`, `sma10` were referenced but never extracted from `row` → Scanner crashed silently on all EMA/SMA scoring. | Added `ema200=safe("EMA200")` etc. via `safe()` extractor — same pattern as existing `rsi`, `adx`, `cci`. All 7 EMA/SMA variables now properly extracted before use. |
| FIX-23 | Smoke Test | Test suite only covered FPT/REE/OIL — GAS, TCB, VIC were never validated. Price flow (Ceiling/Floor/Reference/Current) not verified in any test. | Added mandatory 5-ticker smoke suite (OIL/FPT/GAS/TCB/VIC) with full price-flow validation, indicator validation, and CompositeScore validation per ticker. |
| FIX-24 | SSI Smoke Test | Only tested FPT+VCB — missed GAS, TCB, VIC, OIL. | Extended SSI test to cover all 5 mandatory tickers. |

**🟢 New Features / Enhancements:**

| ID | Feature | Details |
|----|---------|---------|
| ENH-25 | Mandatory Smoke Test | Every run tests OIL (UPCOM), FPT, GAS, TCB, VIC with full pipeline + indicator + price-flow + composite-score validation |
| ENH-26 | BRD Tab in Guide | New `🏗️ BRD` sub-tab in Guide with full theory documentation: SSI iBoard endpoints, valuation models (DCF/P/E/P/B/Graham/DDM), indicator theory (SMA/EMA/RSI/MACD/BB/ADX/ATR), ML models (Prophet/ARIMA/SVR/RF/GBM/Ensemble), T+2 settlement, 7 order types, sector P/E benchmarks — bilingual VI/EN AU |
| ENH-27 | Version String | App title & all captions updated to v24.0 |

**📋 Audit Trail:**
- Smoke test: FIX-22 verified via CompositeScore sub-test in mandatory suite
- All 5 mandatory tickers run automatically when smoke test button clicked
- Price flow validation: `fetch_cafef_price()` reference → `get_price_limits()` → assert Floor ≤ Current ≤ Ceiling

---

### v21.0 — 2026-03-09 · FIXES + RESEARCH-BACKED IMPROVEMENTS

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
    if "ds_results" not in st.session_state:
        st.session_state.ds_results = []
    if "ds_errors" not in st.session_state:
        st.session_state.ds_errors  = []
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = []
        # Load from disk on first run
        try:
            _disk_audit = load_audit_from_disk()
            if _disk_audit: st.session_state.audit_log = _disk_audit
        except Exception: pass

    # v24: Reorganized 14-tab menu for better UX
    # Group: [Trading] Scanner | Smart Signals | Profiler | Deep Audit | Portfolios | ML | Global
    # Group: [Tools] Backtest | History | Guide | Changelog | Smoke | ForecastLog | TopForecast
    tab_keys = ["tab1","tab2","tab3","tab4","tab5","tab6","tab7","tab8","tab9","tab10","tab11","tab12","tab13","tab14","tab15","tab16","tab17"]
    tabs = st.tabs([L[k] for k in tab_keys])

    with tabs[0]:
        render_scanner_tab()
    with tabs[1]:
        render_smart_signals_tab()   # 🎯 Smart Signals (replaces Top 30 Buy)
    with tabs[2]:
        render_stock_profiler_tab()  # 🧬 Profiler — moved up to tab 3
    with tabs[3]:
        render_deep_audit_tab()
    with tabs[4]:
        render_model_portfolios_tab()  # 💼 moved up
    with tabs[5]:
        render_ml_forecast_tab()
    with tabs[6]:
        render_global_markets_tab()    # 🌍 moved up
    with tabs[7]:
        render_backtest_tab()          # 🧪 moved back
    with tabs[8]:
        render_history_tab()
    with tabs[9]:
        render_guide_tab()
    with tabs[10]:
        render_changelog_tab()
    with tabs[11]:
        render_smoke_test_tab()
    with tabs[12]:
        render_forecast_log_tab()
    with tabs[13]:
        render_top_forecast_tab()
    with tabs[14]:
        render_audit_log_tab()
    with tabs[15]:
        render_deep_scan_tab()
    with tabs[16]:
        render_ssi_realtime_tab()

if __name__ == "__main__":
    main()