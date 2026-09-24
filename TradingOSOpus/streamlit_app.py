"""
VN Trading OS — Streamlit Edition
Deploy: streamlit run streamlit_app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time as _time
import json, os, sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="VN Trading OS",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───
st.markdown("""
<style>
    .buy { color: #22c55e !important; font-weight: bold; }
    .sell { color: #ef4444 !important; font-weight: bold; }
    .hold { color: #eab308 !important; font-weight: bold; }
    .metric-card {
        background: #1e293b; border-radius: 12px; padding: 16px;
        border: 1px solid #334155; text-align: center;
    }
    .signal-badge {
        padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;
        display: inline-block;
    }
    .signal-BUY, .signal-WEAK_BUY { background: rgba(34,197,94,0.2); color: #22c55e; }
    .signal-SELL, .signal-WEAK_SELL { background: rgba(239,68,68,0.2); color: #ef4444; }
    .signal-HOLD { background: rgba(234,179,8,0.2); color: #eab308; }
    div[data-testid="stSidebar"] { background: #0f172a; }
    .stProgress > div > div > div { background: #6366f1; }
</style>
""", unsafe_allow_html=True)


# ─── Lazy imports with error handling ───
@st.cache_resource
def get_data_manager():
    try:
        from data.data_manager import DataManager
        return DataManager()
    except ImportError:
        return None

@st.cache_data(ttl=300)
def get_tickers(exchange):
    try:
        from data.ticker_list import get_exchange_tickers
        return get_exchange_tickers(exchange)
    except ImportError:
        # Fallback hardcoded
        if exchange == "HOSE":
            return ["AAA","ACB","BCM","BID","BVH","CTG","DGC","DPM","EIB","FPT",
                    "GAS","GVR","HDB","HDG","HPG","KDH","MBB","MSN","MWG","NVL",
                    "PNJ","POW","PLX","REE","SAB","SHB","SSI","STB","TCB","TPB",
                    "VCB","VCG","VHM","VIC","VIB","VJC","VNM","VPB","VRE"]
        elif exchange == "HNX":
            return ["BAB","BVS","CEO","DHT","HUT","IDC","MBS","NTP","PVS","SHS",
                    "TNG","VCS","VFS"]
        return []

@st.cache_data(ttl=60)
def fetch_ohlcv(ticker, start="2020-01-01"):
    dm = get_data_manager()
    if dm is None:
        return None
    try:
        return dm.get_ohlcv(ticker, start=start)
    except Exception as e:
        return None

def run_decision(ticker, capital=500_000_000):
    """Run full decision pipeline."""
    dm = get_data_manager()
    if dm is None:
        st.error("Data manager not available. Check that data/ modules exist.")
        return None
    try:
        df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
        if df is None or len(df) < 200:
            return None
        from features.technical import build_all_indicators
        from decision_engine import DecisionEngine
        featured = build_all_indicators(df)
        engine = DecisionEngine()
        result = engine.full_decision(featured, capital=capital, ticker=ticker.upper(), sentiment_score=0.0)
        result["data_source"] = dm.get_data_source(df)
        result["data_rows"] = len(df)
        result["ohlcv"] = df
        # Convert numpy types
        return _sanitize(result)
    except Exception as e:
        st.error(f"Error for {ticker}: {e}")
        return None

def _sanitize(obj):
    if isinstance(obj, dict): return {k: _sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)): return [_sanitize(v) for v in obj]
    elif isinstance(obj, (np.integer,)): return int(obj)
    elif isinstance(obj, (np.floating,)): return float(obj)
    elif isinstance(obj, np.bool_): return bool(obj)
    elif isinstance(obj, np.ndarray): return obj.tolist()
    elif isinstance(obj, pd.DataFrame): return obj  # keep DataFrames as-is
    elif hasattr(obj, 'item'): return obj.item()
    return obj

def signal_badge(action, confidence=0):
    action = action or "HOLD"
    return f'<span class="signal-badge signal-{action}">{action} {confidence:.0f}%</span>'

def fmt_vnd(v):
    if v is None or v == 0: return "-"
    return f"{v:,.0f}"


# ─── Audit helper ───
def log_audit(action, ticker, result=None):
    try:
        from audit.logger import audit
        audit.log(action, ticker, {}, result or {}, "SUCCESS", 0)
    except:
        pass


# ═══════════════════════════════════════════
# SIDEBAR NAVIGATION
# ═══════════════════════════════════════════
st.sidebar.markdown("## 📈 VN Trading OS")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", [
    "🏠 Dashboard",
    "🔍 Scanner",
    "🎯 Decision",
    "📊 Backtest",
    "🔔 Signals",
    "📋 Audit Log",
], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.caption("v4.0 • Streamlit Edition")


# ═══════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("🏠 Dashboard")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔍 Search ticker", "", key="dash_search")
    with col2:
        sig_filter = st.selectbox("Signal", ["All", "BUY", "SELL", "HOLD"], key="dash_sig")
    with col3:
        n_tickers = st.slider("# Tickers", 5, 50, 20, key="dash_n")

    tickers = get_tickers("HOSE")[:n_tickers]

    if "dash_results" not in st.session_state:
        st.session_state.dash_results = []

    if st.button("🔄 Scan Dashboard", type="primary"):
        st.session_state.dash_results = []
        bar = st.progress(0, text="Scanning...")
        for i, t in enumerate(tickers):
            bar.progress((i + 1) / len(tickers), text=f"Scanning {t}...")
            r = run_decision(t)
            if r:
                st.session_state.dash_results.append(r)
        bar.empty()

    results = st.session_state.dash_results

    # Filter results
    if search:
        results = [r for r in results if search.upper() in (r.get("ticker", "") or "")]
    if sig_filter != "All":
        results = [r for r in results if sig_filter in (r.get("signal", {}).get("action", "") or "")]

    # Summary metrics
    buys = [r for r in results if "BUY" in (r.get("signal", {}).get("action", "") or "")]
    sells = [r for r in results if "SELL" in (r.get("signal", {}).get("action", "") or "")]
    holds = len(results) - len(buys) - len(sells)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Scanned", len(results))
    c2.metric("🟢 BUY", len(buys))
    c3.metric("🔴 SELL", len(sells))
    c4.metric("🟡 HOLD", holds)

    # Results grid
    if results:
        cols_per_row = 4
        for i in range(0, len(results), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(results): break
                r = results[idx]
                sig = r.get("signal", {})
                ind = sig.get("indicators", {})
                with col:
                    action = sig.get("action", "HOLD")
                    color = "🟢" if "BUY" in action else "🔴" if "SELL" in action else "🟡"
                    st.markdown(f"**{color} {r.get('ticker', '?')}**")
                    st.markdown(f"{signal_badge(action, sig.get('confidence', 0))}", unsafe_allow_html=True)
                    st.caption(f"Price: {fmt_vnd(ind.get('price'))} | RSI: {ind.get('rsi', 0):.0f}")


# ═══════════════════════════════════════════
# PAGE: SCANNER
# ═══════════════════════════════════════════
elif page == "🔍 Scanner":
    st.title("🔍 Stock Scanner")

    # Controls
    with st.expander("⚙️ Scan Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            custom = st.text_input("Custom tickers (comma-separated)", "")
            capital = st.number_input("Capital (VND)", value=500_000_000, step=100_000_000, format="%d")
        with col2:
            exchanges = st.multiselect("Exchanges", ["HOSE", "HNX", "UPCOM"], default=["HOSE"])
            col_r1, col_r2 = st.columns(2)
            rsi_min = col_r1.number_input("RSI Min", 0, 100, 0)
            rsi_max = col_r2.number_input("RSI Max", 0, 100, 100)

    # Build ticker list
    tickers = [t.strip().upper() for t in custom.split(",") if t.strip()]
    for ex in exchanges:
        tickers = list(set(tickers + get_tickers(ex)))
    tickers = sorted(tickers)

    st.info(f"📋 **{len(tickers)} tickers** ready to scan from {', '.join(exchanges)}")

    if "scan_results" not in st.session_state:
        st.session_state.scan_results = []

    if st.button(f"🚀 Scan {len(tickers)} Tickers", type="primary"):
        st.session_state.scan_results = []
        bar = st.progress(0, text="Starting scan...")
        status = st.empty()

        for i, t in enumerate(tickers):
            bar.progress((i + 1) / len(tickers), text=f"[{i+1}/{len(tickers)}] {t}")
            r = run_decision(t, capital)
            if r:
                ind = r.get("signal", {}).get("indicators", {})
                rsi = ind.get("rsi", 50)
                if rsi_min <= rsi <= rsi_max:
                    st.session_state.scan_results.append(r)
                    log_audit("SCAN", t, r)

        bar.empty()
        status.success(f"✅ Scan complete! {len(st.session_state.scan_results)} results")

    results = st.session_state.scan_results

    if results:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            f_ticker = st.text_input("🔍 Filter ticker", "", key="scan_ft")
        with col2:
            f_signal = st.selectbox("Signal", ["All","BUY","WEAK_BUY","HOLD","WEAK_SELL","SELL"], key="scan_fs")
        with col3:
            f_sort = st.selectbox("Sort by", ["Ticker","Signal","RSI","Price","Confidence"], key="scan_sort")

        # Build dataframe
        rows = []
        for r in results:
            sig = r.get("signal", {})
            ind = sig.get("indicators", {})
            pt = r.get("price_targets", {})
            ps = r.get("position_sizing", {})
            rows.append({
                "Ticker": r.get("ticker", ""),
                "Price": ind.get("price", 0),
                "Signal": sig.get("action", "HOLD"),
                "Confidence": sig.get("confidence", 0),
                "Regime": sig.get("regime", {}).get("regime", "") if isinstance(sig.get("regime"), dict) else "",
                "RSI": ind.get("rsi", 0),
                "MACD": ind.get("macd_hist", 0),
                "Vol Ratio": ind.get("volume_ratio", 0),
                "Entry": pt.get("entry_conservative", 0),
                "Stop Loss": pt.get("stop_loss", 0),
                "Take Profit": pt.get("take_profit_2", 0),
                "Shares": ps.get("shares", 0),
                "Source": r.get("data_source", ""),
            })

        df = pd.DataFrame(rows)

        # Apply filters
        if f_ticker:
            df = df[df["Ticker"].str.contains(f_ticker.upper())]
        if f_signal != "All":
            df = df[df["Signal"] == f_signal]

        # Sort
        sort_map = {"Ticker": "Ticker", "Signal": "Signal", "RSI": "RSI", "Price": "Price", "Confidence": "Confidence"}
        asc = f_sort in ["Ticker"]
        df = df.sort_values(sort_map.get(f_sort, "Ticker"), ascending=asc)

        # Summary
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Total", len(df))
        sc2.metric("🟢 BUY", len(df[df["Signal"].str.contains("BUY")]))
        sc3.metric("🔴 SELL", len(df[df["Signal"].str.contains("SELL")]))
        sc4.metric("🟡 HOLD", len(df[~df["Signal"].str.contains("BUY|SELL")]))

        # Color signal column
        def color_signal(val):
            if "BUY" in str(val): return "color: #22c55e; font-weight: bold"
            if "SELL" in str(val): return "color: #ef4444; font-weight: bold"
            return "color: #eab308"

        styled = df.style.applymap(color_signal, subset=["Signal"])
        styled = styled.format({
            "Price": "{:,.0f}", "Entry": "{:,.0f}", "Stop Loss": "{:,.0f}",
            "Take Profit": "{:,.0f}", "RSI": "{:.0f}", "MACD": "{:.0f}",
            "Vol Ratio": "{:.1f}x", "Confidence": "{:.0f}%", "Shares": "{:,.0f}",
        })

        st.dataframe(styled, use_container_width=True, height=600)

        # Export CSV
        csv = df.to_csv(index=False)
        st.download_button("📥 Export CSV", csv, f"scan_{len(df)}.csv", "text/csv")


# ═══════════════════════════════════════════
# PAGE: DECISION
# ═══════════════════════════════════════════
elif page == "🎯 Decision":
    st.title("🎯 Decision Engine")

    col1, col2 = st.columns([2, 1])
    with col1:
        ticker = st.text_input("Ticker", "FPT").upper()
    with col2:
        capital = st.number_input("Capital (VND)", value=500_000_000, step=100_000_000, format="%d")

    if st.button("🔎 Analyze", type="primary"):
        with st.spinner(f"Analyzing {ticker}..."):
            result = run_decision(ticker, capital)

        if result:
            log_audit("DECISION", ticker, result)
            sig = result.get("signal", {})
            ind = sig.get("indicators", {})
            pt = result.get("price_targets", {})
            ps = result.get("position_sizing", {})
            regime = sig.get("regime", {})

            # Signal header
            action = sig.get("action", "HOLD")
            conf = sig.get("confidence", 0)
            st.markdown(f"## {signal_badge(action, conf)}", unsafe_allow_html=True)

            # Key metrics
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Price", fmt_vnd(ind.get("price")))
            m2.metric("RSI", f"{ind.get('rsi', 0):.1f}")
            m3.metric("MACD Hist", f"{ind.get('macd_hist', 0):.0f}")
            m4.metric("Vol Ratio", f"{ind.get('volume_ratio', 0):.1f}x")
            regime_name = regime.get("regime", "?") if isinstance(regime, dict) else str(regime)
            m5.metric("Regime", regime_name)

            st.markdown("---")

            # Price targets & position sizing
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎯 Price Targets")
                pt_data = {
                    "Target": ["Entry (Conservative)", "Entry (Aggressive)", "Stop Loss", "TP1", "TP2", "TP3"],
                    "Price (VND)": [
                        fmt_vnd(pt.get("entry_conservative")),
                        fmt_vnd(pt.get("entry_aggressive")),
                        fmt_vnd(pt.get("stop_loss")),
                        fmt_vnd(pt.get("take_profit_1")),
                        fmt_vnd(pt.get("take_profit_2")),
                        fmt_vnd(pt.get("take_profit_3")),
                    ]
                }
                st.table(pd.DataFrame(pt_data))

            with col2:
                st.subheader("📐 Position Sizing")
                st.metric("Shares", f"{ps.get('shares', 0):,}")
                st.metric("Investment", fmt_vnd(ps.get("investment")))
                st.metric("Risk Amount", fmt_vnd(ps.get("risk_amount")))
                st.metric("Risk %", f"{ps.get('risk_pct', 0):.1f}%")

            # Candlestick chart
            ohlcv = result.get("ohlcv")
            if ohlcv is not None and isinstance(ohlcv, pd.DataFrame) and len(ohlcv) > 0:
                st.subheader("📈 Price Chart")
                df_chart = ohlcv.tail(120).copy()

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                    vertical_spacing=0.03, row_heights=[0.7, 0.3],
                    subplot_titles=[f"{ticker} Price", "Volume"])

                fig.add_trace(go.Candlestick(
                    x=df_chart["date"], open=df_chart["open"], high=df_chart["high"],
                    low=df_chart["low"], close=df_chart["close"], name="OHLC",
                    increasing_line_color="#22c55e", decreasing_line_color="#ef4444",
                ), row=1, col=1)

                colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(df_chart["close"], df_chart["open"])]
                fig.add_trace(go.Bar(x=df_chart["date"], y=df_chart["volume"], marker_color=colors, name="Volume", opacity=0.5), row=2, col=1)

                # Entry/SL/TP lines
                if pt.get("entry_conservative"):
                    fig.add_hline(y=pt["entry_conservative"], line_dash="dash", line_color="#6366f1", annotation_text="Entry", row=1, col=1)
                if pt.get("stop_loss"):
                    fig.add_hline(y=pt["stop_loss"], line_dash="dash", line_color="#ef4444", annotation_text="SL", row=1, col=1)
                if pt.get("take_profit_2"):
                    fig.add_hline(y=pt["take_profit_2"], line_dash="dash", line_color="#22c55e", annotation_text="TP2", row=1, col=1)

                fig.update_layout(
                    template="plotly_dark", height=600, showlegend=False,
                    xaxis_rangeslider_visible=False,
                    paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
                )
                st.plotly_chart(fig, use_container_width=True)

            st.caption(f"Source: {result.get('data_source', '?')} | {result.get('data_rows', 0)} bars")
        else:
            st.error(f"Could not analyze {ticker}. Need 200+ trading days of data.")


# ═══════════════════════════════════════════
# PAGE: BACKTEST
# ═══════════════════════════════════════════
elif page == "📊 Backtest":
    st.title("📊 Backtest")

    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input("Ticker", "FPT", key="bt_ticker").upper()
    with col2:
        strategy = st.selectbox("Strategy", ["1W", "1M", "swing", "momentum"])

    if st.button("▶️ Run Backtest", type="primary"):
        try:
            from data.data_manager import DataManager
            from backtest.engine import BacktestEngine
            dm = DataManager()
            df = dm.get_ohlcv(ticker, start="2020-01-01")
            bt = BacktestEngine()
            result = _sanitize(bt.run(df, ticker=ticker, strategy_key=strategy))
            log_audit("BACKTEST", ticker, result)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Return", f"{result.get('total_return', 0):.1f}%")
            c2.metric("Win Rate", f"{result.get('win_rate', 0):.1f}%")
            c3.metric("Total Trades", result.get("total_trades", 0))
            c4.metric("Max Drawdown", f"{result.get('max_drawdown', 0):.1f}%")

            trades = result.get("trades", [])
            if trades:
                st.dataframe(pd.DataFrame(trades), use_container_width=True)
        except Exception as e:
            st.error(f"Backtest error: {e}")


# ═══════════════════════════════════════════
# PAGE: SIGNALS
# ═══════════════════════════════════════════
elif page == "🔔 Signals":
    st.title("🔔 Signal History")

    try:
        from audit.logger import audit
        logs = audit.get_logs(action_type="DECISION", limit=200)
    except:
        logs = []

    if not logs:
        st.info("No signals yet. Run a scan or decision first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            f_ticker = st.text_input("Filter ticker", "", key="sig_ft")
        with col2:
            f_signal = st.selectbox("Signal", ["All","BUY","SELL","HOLD"], key="sig_fs")

        rows = []
        for l in logs:
            s = l.get("result_summary", {})
            rows.append({
                "Time": l.get("ts", "")[:19],
                "Ticker": l.get("ticker", ""),
                "Signal": l.get("signal", ""),
                "Confidence": l.get("confidence", 0),
                "Price": s.get("price", 0),
                "RSI": s.get("rsi", 0),
                "Entry": s.get("entry", 0),
                "SL": s.get("stop_loss", 0),
                "TP": s.get("take_profit", 0),
                "Shares": s.get("shares", 0),
                "Duration": f"{l.get('duration_ms', 0):.0f}ms",
                "Source": l.get("data_source", ""),
            })
        df = pd.DataFrame(rows)
        if f_ticker:
            df = df[df["Ticker"].str.contains(f_ticker.upper())]
        if f_signal != "All":
            df = df[df["Signal"].str.contains(f_signal)]

        st.dataframe(df, use_container_width=True, height=500)


# ═══════════════════════════════════════════
# PAGE: AUDIT LOG
# ═══════════════════════════════════════════
elif page == "📋 Audit Log":
    st.title("📋 Audit Log")

    try:
        from audit.logger import audit
        stats = audit.get_stats(7)
    except:
        stats = None

    if stats and stats.get("total", 0) > 0:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total (7d)", stats["total"])
        c2.metric("Success Rate", f"{stats.get('success_rate', 0)}%")
        c3.metric("Avg Duration", f"{stats.get('avg_duration_ms', 0):.0f}ms")
        c4.metric("Success", stats.get("success", 0))
        c5.metric("Errors", stats.get("error", 0))

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        f_ticker = st.text_input("Ticker", "", key="audit_ft")
    with col2:
        f_action = st.selectbox("Action Type", ["All","DECISION","SIGNAL","BACKTEST","DATA","SCAN"], key="audit_fa")
    with col3:
        f_status = st.selectbox("Status", ["All","SUCCESS","ERROR"], key="audit_fs")

    try:
        from audit.logger import audit
        kwargs = {"limit": 300}
        if f_ticker: kwargs["ticker"] = f_ticker
        if f_action != "All": kwargs["action_type"] = f_action
        if f_status != "All": kwargs["status"] = f_status
        logs = audit.get_logs(**kwargs)
    except:
        logs = []

    if logs:
        rows = []
        for l in logs:
            rows.append({
                "Time": l.get("ts", "")[:19],
                "Action": l.get("action", ""),
                "Ticker": l.get("ticker", ""),
                "Signal": l.get("signal", ""),
                "Status": l.get("status", ""),
                "Duration": f"{l.get('duration_ms', 0):.0f}ms",
                "Source": l.get("data_source", ""),
                "IP": l.get("ip", ""),
            })
        df = pd.DataFrame(rows)

        def color_status(val):
            if val == "SUCCESS": return "color: #22c55e"
            if val == "ERROR": return "color: #ef4444"
            return ""

        styled = df.style.applymap(color_status, subset=["Status"])
        st.dataframe(styled, use_container_width=True, height=500)

        # Expandable detail
        if st.checkbox("Show raw JSON for selected entries"):
            for l in logs[:10]:
                with st.expander(f"{l.get('ts', '')[:19]} — {l.get('action')} {l.get('ticker')}"):
                    st.json(l)
    else:
        st.info("No audit entries yet.")
