"""SMS Gauge — Streamlit speedometer for Smart Money Score."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def render_sms_gauge(sms_raw: int, sms_label: str = "", title: str = "SMS Score") -> None:
    """Render SMS as a Plotly gauge (speedometer)."""
    color = (
        "#00c851" if sms_raw >= 75
        else "#33b5e5" if sms_raw >= 60
        else "#ffbb33" if sms_raw >= 40
        else "#ff4444"
    )

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=sms_raw,
        number={"font": {"color": color, "size": 36}},
        title={"text": f"{title}<br><span style='font-size:0.8em;color:gray'>{sms_label}</span>"},
        delta={"reference": 60, "suffix": " vs 60"},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 40],  "color": "rgba(255,68,68,0.19)"},
                {"range": [40, 60], "color": "rgba(255,187,51,0.19)"},
                {"range": [60, 75], "color": "rgba(51,181,229,0.19)"},
                {"range": [75, 100],"color": "rgba(0,200,81,0.19)"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.75,
                "value": 60,
            },
        },
    ))

    fig.update_layout(
        height=220,
        margin=dict(t=40, b=0, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="white",
    )
    st.plotly_chart(fig, use_container_width=True)
