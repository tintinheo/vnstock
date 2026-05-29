from pathlib import Path
import pandas as pd, streamlit as st, plotly.graph_objects as go
from app.data.ssi_provider import SsiIboardSnapshotProvider
from app.data.csv_provider import load_ohlcv_csv
from app.data.sample_data import generate_sample
from app.features.indicators import add_indicators, add_relative_strength
from app.models.analytics import market_regime, sector_scores, stock_scores
from app.signals.scanner import scan_realtime, generate_signals
from app.recommendation.decision_engine import build_recommendations, build_realtime_recommendations
from app.risk.position import position_size
from app.backtesting.engine import backtest

st.set_page_config(page_title="VN Trading Recommendation Engine", layout="wide")
st.title("Vietnam Trading App with Recommendation Decision Engine")
st.caption("Decision-support only. No vnstock dependency. Use licensed/allowed data for production.")

mode=st.sidebar.radio("Data mode", ["Realtime SSI snapshot", "Upload historical CSV", "Offline demo sample"])
horizon=st.sidebar.selectbox("Horizon", ["1W","2W","1M","3M","5M"], index=2)
nav=st.sidebar.number_input("NAV", value=1_000_000_000, step=50_000_000)
risk_pct=st.sidebar.slider("Risk per trade %", .25, 3.0, 1.0, .25)/100
positions_raw=st.sidebar.text_input("Current positions, comma-separated", value="")
current_positions=[x.strip().upper() for x in positions_raw.split(',') if x.strip()]

if mode=="Realtime SSI snapshot":
    st.subheader("Realtime snapshot scanner and recommendations")
    groups=st.multiselect("Groups", ["VN30","HOSE","HNX","UPCOM","VN100"], default=["VN30"])
    min_value=st.number_input("Min trading value", value=1_000_000_000, step=500_000_000)
    if st.button("Fetch, scan and recommend"):
        try:
            snap=SsiIboardSnapshotProvider().get_multiple_group_snapshots(groups)
            if snap.attrs.get("errors"): st.warning(snap.attrs["errors"])
            scan=scan_realtime(snap,min_value)
            rec=build_realtime_recommendations(scan)
            st.success(f"Fetched {len(snap)} symbols")
            st.subheader("Realtime Recommendations")
            st.dataframe(rec, use_container_width=True)
            st.subheader("Raw Realtime Scan")
            st.dataframe(scan, use_container_width=True)
            st.download_button("Download recommendations CSV", rec.to_csv(index=False).encode("utf-8-sig"), "realtime_recommendations.csv", "text/csv")
        except Exception as ex:
            st.error(f"Fetch failed: {ex}")
            st.info("If blocked, use historical CSV mode with your provider export.")
    st.stop()

if mode=="Offline demo sample":
    sample=Path("data/sample/sample_ohlcv.csv")
    if not sample.exists(): generate_sample(sample)
    df=load_ohlcv_csv(sample)
else:
    up=st.file_uploader("Upload real historical OHLCV CSV", type="csv")
    if not up: st.info("Upload CSV to continue."); st.stop()
    p=Path("outputs/uploaded.csv"); p.parent.mkdir(exist_ok=True); p.write_bytes(up.getbuffer()); df=load_ohlcv_csv(p)

df=add_relative_strength(add_indicators(df))
as_of=st.sidebar.date_input("As of", value=pd.to_datetime(df.date.max()).date())
reg=market_regime(df,as_of); sectors=sector_scores(df,as_of,horizon); scored=stock_scores(df,as_of,horizon,reg["score"]); sig=generate_signals(scored,horizon)
rec=build_recommendations(scored,sig,reg,horizon,current_positions=current_positions)

c1,c2,c3,c4=st.columns(4); c1.metric("Regime", reg["regime"], f'{reg["score"]:.0f}'); c2.metric("Exposure", f'{reg["exposure"][0]*100:.0f}-{reg["exposure"][1]*100:.0f}%'); c3.metric("Signals", len(sig)); c4.metric("Recommendations", len(rec))
st.write("Regime explanation:", ", ".join(reg["explanation"]))

tabs=st.tabs(["Recommendations","Market","Sectors","Scores","Signals","Risk","Backtest"])
with tabs[0]:
    st.subheader("Final Recommendation Decisions")
    filters=st.multiselect("Show recommendations", ["STRONG_BUY","BUY","WATCH","HOLD","REDUCE","SELL","AVOID","RISK_OFF"], default=["STRONG_BUY","BUY","WATCH","HOLD","REDUCE","SELL"])
    view=rec[rec.recommendation.isin(filters)] if filters else rec
    st.dataframe(view, use_container_width=True)
    st.download_button("Download recommendation CSV", rec.to_csv(index=False).encode("utf-8-sig"), "recommendations.csv", "text/csv")
with tabs[1]:
    idx=df[(df.symbol=="VNINDEX")&(df.date<=pd.to_datetime(as_of))].tail(180)
    if len(idx):
        fig=go.Figure(data=[go.Candlestick(x=idx.date,open=idx.open,high=idx.high,low=idx.low,close=idx.close)]); fig.add_scatter(x=idx.date,y=idx.ma_20,name="MA20"); fig.add_scatter(x=idx.date,y=idx.ma_50,name="MA50"); fig.update_layout(height=500,xaxis_rangeslider_visible=False); st.plotly_chart(fig,use_container_width=True)
    else: st.info("VNINDEX not found. Market regime requires an index symbol for best results.")
with tabs[2]: st.dataframe(sectors,use_container_width=True)
with tabs[3]: st.dataframe(scored[["rank","symbol","sector","close","stock_score","technical_score","liquidity_score","rs_score","sector_score","risk_score"]].head(100),use_container_width=True)
with tabs[4]: st.dataframe(sig,use_container_width=True) if len(sig) else st.warning("No signals.")
with tabs[5]:
    buyable=rec[rec.recommendation.isin(["STRONG_BUY","BUY"])]
    if len(buyable):
        s=st.selectbox("Recommendation", buyable.symbol.tolist()); r=buyable[buyable.symbol==s].iloc[0]
        st.json(position_size(nav,risk_pct,float(r.close),float(r.stop_loss if pd.notna(r.stop_loss) else r.close*0.95)))
    else: st.info("No BUY/STRONG_BUY recommendation for position sizing.")
with tabs[6]:
    if st.button("Run recommendation-based backtest"):
        trades,metrics=backtest(df,horizon); st.json(metrics); st.dataframe(trades,use_container_width=True)
