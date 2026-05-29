"""
ui/ml_tab.py — NewTradingOS v14.0
ML Ensemble forecast tab — single stock deep dive with all models.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import TIMEFRAME_CONFIG
from ml.ensemble import ensemble_forecast
from ml.lstm_model import TF_AVAILABLE
from ml.classical_models import XGB_AVAILABLE, PROPHET_AVAILABLE, ARIMA_AVAILABLE
from core.indicators import compute_all
from ui.components import (
    candlestick_chart, GREEN, RED, YELLOW, BLUE, PURPLE, GREY,
)


def render_ml_tab(
    data_dict: dict,
    regime: str,
    macro_data: dict,
    lang: str = "VI",
) -> None:
    st.subheader("🧠 ML Ensemble Forecast")

    # ── Model availability banner ─────────────────────────────
    flags = {
        "LSTM (TF)":  TF_AVAILABLE,
        "XGBoost":    XGB_AVAILABLE,
        "Prophet":    PROPHET_AVAILABLE,
        "ARIMA":      ARIMA_AVAILABLE,
        "RandomForest": True,
        "Monte Carlo":  True,
    }
    cols = st.columns(len(flags))
    for col, (name, avail) in zip(cols, flags.items()):
        col.metric(name, "✅" if avail else "❌")

    st.divider()

    # ── Controls ─────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.selectbox("Mã cổ phiếu", sorted(data_dict.keys()),
                               key="ml_ticker")
    with c2:
        tf = st.selectbox("Timeframe", list(TIMEFRAME_CONFIG.keys()),
                           index=2, key="ml_tf")  # default 1M
    with c3:
        epochs = st.slider("LSTM Epochs", 20, 150, 60, key="ml_epochs",
                            disabled=not TF_AVAILABLE)

    if st.button("🔮 Chạy Dự Báo", type="primary", key="ml_run"):
        df_raw, src = data_dict.get(ticker, (None, "N/A"))
        if df_raw is None or df_raw.empty:
            st.error(f"Không có dữ liệu cho {ticker}")
            return

        with st.spinner(f"Đang chạy ML ensemble cho {ticker} ({tf})…"):
            fc = ensemble_forecast(
                df_raw.copy(), tf,
                ticker=ticker,
                regime=regime,
                macro_dict=macro_data,
                n_lstm_epochs=epochs,
            )

        cfg    = TIMEFRAME_CONFIG[tf]
        n_days = cfg["hold_sessions"]

        # ── Price chart with forecast ─────────────────────────
        df_ind = compute_all(df_raw.copy(), cfg)
        lookback_bars = {"1W": 60, "2W": 90, "1M": 120, "3M": 200, "5M": 300}.get(tf, 120)
        fig = candlestick_chart(df_ind.tail(lookback_bars), ticker, tf,
                                 forecast=fc, height=550)
        st.plotly_chart(fig, use_container_width=True)

        # ── Forecast summary ─────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Giá hiện tại",  f"{fc.current_price:,.0f}")
        c2.metric("Dự báo Target", f"{fc.target_price:,.0f}")
        up_color = GREEN if fc.upside_pct >= 0 else RED
        c3.metric("Upside/Downside", f"{fc.upside_pct:+.1f}%")
        c4.metric("Horizon",       f"{n_days} phiên")

        st.divider()

        # ── Model weights & individual predictions ────────────
        st.subheader("📊 Trọng Số & Dự Báo Từng Mô Hình")
        weight_rows = []
        for m, w in fc.weights_used.items():
            preds = fc.model_preds.get(m, [])
            end_p = preds[-1] if preds else None
            weight_rows.append({
                "Mô hình": m.upper(),
                "Trọng số %": round(w * 100, 1),
                "Dự báo cuối": f"{end_p:,.0f}" if end_p else "N/A",
                "Upside %": f"{((end_p / fc.current_price) - 1) * 100:+.1f}%"
                             if (end_p and fc.current_price) else "N/A",
            })
        st.dataframe(pd.DataFrame(weight_rows), use_container_width=True,
                     hide_index=True)

        # ── Individual model curves ───────────────────────────
        fut_dates = pd.bdate_range(
            start=df_raw.index[-1], periods=n_days + 1
        )[1:]

        model_colors = {
            "lstm":    PURPLE,
            "xgb":     "#ff8c42",
            "rf":      "#42b6ff",
            "prophet": GREEN,
            "arima":   YELLOW,
            "mc":      "#ff69b4",
            "holt":    GREY,
        }

        fig2 = go.Figure()
        # Historical (last 30 bars)
        last_30 = df_raw.tail(30)
        fig2.add_trace(go.Scatter(
            x=last_30.index, y=last_30["Close"],
            name="Historical", line=dict(color=BLUE, width=2),
        ))
        # Ensemble
        fig2.add_trace(go.Scatter(
            x=list(fut_dates), y=fc.prices,
            name="Ensemble", line=dict(color=BLUE, width=3, dash="dot"),
        ))
        # Individual models
        for m, preds in fc.model_preds.items():
            if not preds:
                continue
            color = model_colors.get(m, GREY)
            fig2.add_trace(go.Scatter(
                x=list(fut_dates[:len(preds)]), y=preds,
                name=m.upper(), line=dict(color=color, width=1.2, dash="dash"),
                opacity=0.7,
            ))
        # Bull/Bear band
        if fc.prices_bull and fc.prices_bear:
            fig2.add_trace(go.Scatter(
                x=list(fut_dates), y=fc.prices_bull,
                name="Bull P75", line=dict(color=GREEN, width=0.8),
                showlegend=True, opacity=0.5,
            ))
            fig2.add_trace(go.Scatter(
                x=list(fut_dates), y=fc.prices_bear,
                name="Bear P25",
                line=dict(color=RED, width=0.8),
                fill="tonexty", fillcolor="rgba(100,200,150,0.07)",
                showlegend=True, opacity=0.5,
            ))

        fig2.update_layout(
            height=400, template="plotly_dark",
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            title=f"{ticker} — Individual Model Forecasts ({tf})",
            legend=dict(orientation="h"),
            margin=dict(l=40, r=40, t=60, b=30),
        )
        st.plotly_chart(fig2, use_container_width=True)
