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
    BLUE,
    GREEN,
    GREY,
    PURPLE,
    RED,
    YELLOW,
    apply_dark_chart_layout,
    candlestick_chart,
    render_guidance_callout,
    render_section_header,
)


MODEL_LABELS = {
    "lstm": "LSTM",
    "xgb": "XGBoost",
    "rf": "RandomForest",
    "prophet": "Prophet",
    "arima": "ARIMA",
    "mc": "Monte Carlo",
    "holt": "Holt",
}


def _format_model_name(model: str) -> str:
    return MODEL_LABELS.get(model, model.upper())


def _latest_bar_date_label(df: pd.DataFrame) -> str:
    if df is None or len(df.index) == 0:
        return "N/A"

    try:
        return pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")
    except Exception:
        return str(df.index[-1])


def _forecast_trust_state(
    fc,
    data_source: str,
    df_raw: pd.DataFrame,
    regime: str,
) -> dict:
    active_models = sorted(fc.model_preds.keys())
    available_models = {
        name for name, available in fc.method_flags.items() if available
    }
    expected_models = sorted(
        available_models | set(fc.weights_used.keys()) | set(active_models)
    )

    fallback_only = active_models == ["holt"]
    if fallback_only:
        expected_models = ["holt"]

    inactive_models = [
        model for model in expected_models if model not in active_models
    ]
    models_expected = len(expected_models)
    models_used = len(active_models)

    band_pct = 0.0
    if fc.current_price > 0 and fc.prices_bull and fc.prices_bear:
        band_pct = (
            (fc.prices_bull[-1] - fc.prices_bear[-1])
            / fc.current_price
            * 100
        )

    degraded = fallback_only or bool(inactive_models)

    return {
        "source": data_source or "N/A",
        "as_of": _latest_bar_date_label(df_raw),
        "regime": regime,
        "active_models": active_models,
        "inactive_models": inactive_models,
        "models_used": models_used,
        "models_expected": models_expected,
        "band_pct": round(float(band_pct), 2),
        "fallback_only": fallback_only,
        "degraded": degraded,
    }


def _forecast_usage_policy(trust: dict, upside_pct: float) -> dict[str, str]:
    if trust.get("fallback_only"):
        return {
            "usage": "Informational only",
            "confidence": "Low",
            "next_step": "Không dùng để sizing; chờ scanner và macro xác nhận",
            "tone": "warning",
        }
    if trust.get("band_pct", 0.0) >= 12:
        return {
            "usage": "Watchlist candidate" if upside_pct > 0 else "Informational only",
            "confidence": "Low",
            "next_step": "Dải bất định còn rộng, chỉ dùng như vùng tham chiếu",
            "tone": "warning",
        }
    if trust.get("degraded"):
        return {
            "usage": "Watchlist candidate" if upside_pct >= 5 else "Scenario support",
            "confidence": "Medium",
            "next_step": "Cần thêm xác nhận từ scanner score, regime và risk budget",
            "tone": "info",
        }
    if upside_pct >= 5 and trust.get("band_pct", 0.0) <= 8:
        return {
            "usage": "Eligible for sizing review",
            "confidence": "Higher",
            "next_step": "Đối chiếu scanner, stop/target và room vốn trước khi hành động",
            "tone": "success",
        }
    if upside_pct > 0:
        return {
            "usage": "Scenario support",
            "confidence": "Medium",
            "next_step": "Dùng như lớp xác nhận bổ sung, không phải quyết định độc lập",
            "tone": "info",
        }
    return {
        "usage": "Informational only",
        "confidence": "Medium",
        "next_step": "Forecast chưa cho bullish edge rõ ràng",
        "tone": "info",
    }


def render_ml_tab(
    data_dict: dict,
    regime: str,
    macro_data: dict,
    lang: str = "VI",
) -> None:
    render_section_header(
        "🧠 ML Ensemble Forecast",
        "Đọc usage policy và confidence trước, sau đó mới nhìn chart ensemble và dispersion giữa các model.",
    )

    if not data_dict:
        st.info("Chưa có dữ liệu giá. Hãy tải dữ liệu trước khi chạy ML forecast.")
        return

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
        trust = _forecast_trust_state(fc, src, df_raw, regime)
        usage_policy = _forecast_usage_policy(trust, fc.upside_pct)

        cfg    = TIMEFRAME_CONFIG[tf]
        n_days = cfg["hold_sessions"]

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Nguồn dữ liệu", trust["source"])
        t2.metric("Bar cuối", trust["as_of"])
        t3.metric("Models chạy", f"{trust['models_used']}/{trust['models_expected']}")
        t4.metric("Dải P75-P25", f"{trust['band_pct']:.1f}%")

        p1, p2, p3 = st.columns(3)
        p1.metric("Usage Policy", usage_policy["usage"], usage_policy["confidence"])
        p2.metric("Decision Mode", "Trust-first", f"Regime {trust['regime']}")
        p3.metric("Next Step", usage_policy["next_step"], f"Models {trust['models_used']}/{trust['models_expected']}")

        active_models = ", ".join(
            _format_model_name(model) for model in trust["active_models"]
        ) or "N/A"
        st.caption(
            f"Cơ sở forecast: {active_models} | Regime đầu vào: {trust['regime']}"
        )

        if trust["fallback_only"]:
            st.warning(
                "Forecast này đang ở chế độ fallback: toàn bộ model chính không đóng góp, "
                "kết quả hiện chỉ dựa trên Holt smoothing. Không nên xem đây là tín hiệu mạnh."
            )
        elif trust["degraded"]:
            inactive_models = ", ".join(
                _format_model_name(model) for model in trust["inactive_models"]
            )
            st.info(
                "Forecast này đang dùng ensemble suy giảm: một số model không tham gia run hiện tại "
                f"({inactive_models}). Trọng số đã được tái phân bổ trên các model còn lại."
            )

        if trust["band_pct"] >= 12:
            st.warning(
                f"Dải bất định P75-P25 đang rộng {trust['band_pct']:.1f}% so với giá hiện tại. "
                "Nên xem target như vùng tham chiếu thay vì mức giá chắc chắn."
            )

        if usage_policy["tone"] == "success":
            render_guidance_callout("Usage guidance", usage_policy["next_step"], tone="success")
        elif usage_policy["tone"] == "warning":
            render_guidance_callout("Usage guidance", usage_policy["next_step"], tone="warning")
        else:
            render_guidance_callout("Usage guidance", usage_policy["next_step"], tone="info")

        st.divider()

        # ── Price chart with forecast ─────────────────────────
        df_ind = compute_all(df_raw.copy(), cfg)
        lookback_bars = {"1W": 60, "2W": 90, "1M": 120, "3M": 200, "5M": 300}.get(tf, 120)
        fig = candlestick_chart(df_ind.tail(lookback_bars), ticker, tf,
                                 forecast=fc, height=550)
        st.plotly_chart(fig, width="stretch")

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
        st.dataframe(pd.DataFrame(weight_rows), width="stretch",
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

        apply_dark_chart_layout(
            fig2,
            height=400,
            title=f"{ticker} — Individual Model Forecasts ({tf})",
            margin=dict(l=40, r=40, t=60, b=30),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig2, width="stretch")
