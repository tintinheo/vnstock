import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.analytics.decision import DecisionService
from app.data.universe import list_tickers
from app.errors import DataUnavailableError
from app.models import Horizon

st.set_page_config(page_title="Vietnam AI Trading OS", layout="wide")

SECRET_SETTING_KEYS = {
    "CACHE_TTL_HOURS",
    "DATA_SOURCE_PRIORITY",
    "MAX_RISK_PER_TRADE",
    "MAX_POSITION_PCT",
    "MAX_SECTOR_PCT",
    "REQUEST_TIMEOUT_SECONDS",
}


def apply_streamlit_cloud_settings() -> None:
    try:
        secrets = dict(st.secrets)
    except Exception:
        return
    for key in SECRET_SETTING_KEYS:
        if key in secrets and key not in os.environ:
            os.environ[key] = str(secrets[key])


@st.cache_resource
def get_service() -> DecisionService:
    apply_streamlit_cloud_settings()
    return DecisionService()


service = get_service()

st.title("Vietnam AI Trading OS")
st.caption("Decision-support only. Real data or explicit failure; no fake market data fallback.")

tickers = [row["ticker"] for row in list_tickers()]
left, middle, right = st.columns([1, 1, 1])
with left:
    ticker = st.selectbox("Ticker", tickers, index=0)
with middle:
    horizon = st.selectbox("Horizon", [item.value for item in Horizon], index=2)
with right:
    capital = st.number_input("Capital VND", min_value=10_000_000, value=500_000_000, step=10_000_000)

if st.button("Analyze", type="primary"):
    try:
        decision = service.get_decision(ticker, capital, Horizon(horizon), audit_id="streamlit-local")
        st.subheader(f"{decision.ticker} {decision.action.value}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Confidence", f"{decision.confidence:.0f}/95")
        c2.metric("Regime", decision.regime.value)
        c3.metric("Latest", f"{decision.latest_price:,.0f}")
        c4.metric("Shares", f"{decision.position_size.shares:,}")

        price_col, risk_col = st.columns([2, 1])
        with price_col:
            data = service.get_data(ticker)
            frame = pd.DataFrame([row.model_dump() for row in data.data])
            fig = go.Figure()
            fig.add_trace(
                go.Candlestick(
                    x=frame["date"],
                    open=frame["open"],
                    high=frame["high"],
                    low=frame["low"],
                    close=frame["close"],
                    name=ticker,
                )
            )
            fig.add_trace(go.Bar(x=frame["date"], y=frame["volume"], name="Volume", yaxis="y2", opacity=0.25))
            fig.update_layout(
                height=520,
                xaxis_rangeslider_visible=False,
                yaxis2={"overlaying": "y", "side": "right", "showgrid": False},
                margin={"l": 10, "r": 10, "t": 30, "b": 10},
            )
            st.plotly_chart(fig, use_container_width=True)
        with risk_col:
            st.write("Entry", decision.entry.model_dump())
            st.write("Stop", decision.stop_loss.model_dump())
            st.write("Take Profit", decision.take_profit.model_dump())
            st.write("Position", decision.position_size.model_dump())

        st.write("Reasons", decision.reasons)
        if decision.warnings:
            st.warning(", ".join(decision.warnings))
    except DataUnavailableError as exc:
        st.error(str(exc))
        st.json({"source_errors": exc.errors})
    except Exception as exc:
        st.exception(exc)
