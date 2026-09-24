"""Market Breadth banner component — shows VN-Index context before scanner."""
from __future__ import annotations

import streamlit as st

from tradingos.utils.dates import vn_session_phase, vn_now


_PHASE_LABELS = {
    "PRE_MARKET":  "Chưa mở phiên",
    "PRE_ATO":     "Chuẩn bị ATO",
    "ATO":         "Khớp lệnh ATO",
    "MORNING":     "Phiên sáng đang chạy",
    "LUNCH":       "Nghỉ trưa",
    "AFTERNOON":   "Phiên chiều đang chạy",
    "NEAR_ATC":    "Sắp vào ATC",
    "ATC":         "Khớp lệnh ATC",
    "CLOSED":      "Phiên đã đóng",
}

_PHASE_COLOR = {
    "PRE_MARKET":  "#64748b",
    "PRE_ATO":     "#64748b",
    "ATO":         "#3b82f6",
    "MORNING":     "#22c55e",
    "LUNCH":       "#64748b",
    "AFTERNOON":   "#22c55e",
    "NEAR_ATC":    "#f59e0b",
    "ATC":         "#f59e0b",
    "CLOSED":      "#64748b",
}


def render_market_breadth(
    macro_score: float | None = None,
    macro_regime: str = "",
    sector_flows: dict | None = None,
    scan_ok_for_t25: bool = True,
) -> None:
    """
    Render a compact market context banner at the top of scanner/morning briefing.

    Parameters
    ----------
    macro_score : float | None
        Score from macro engine (−100 to +100); None if unavailable.
    macro_regime : str
        Text regime label (ACCOMMODATIVE / NEUTRAL / RESTRICTIVE).
    sector_flows : dict | None
        {sector_name: flow_status} mapping from MoneyFlowService.
    scan_ok_for_t25 : bool
        Whether macro conditions support T+2.5 scanning today.
    """
    phase = vn_session_phase()
    phase_label = _PHASE_LABELS.get(phase, phase)
    phase_color = _PHASE_COLOR.get(phase, "#64748b")
    now_str = vn_now().strftime("%H:%M %d/%m/%Y")

    # ── Macro badge ───────────────────────────────────────────────────────────
    if macro_score is not None:
        macro_color = "#22c55e" if macro_score >= 50 else "#f59e0b" if macro_score >= 20 else "#ef4444"
        macro_text = f"{macro_regime or 'N/A'} {macro_score:.0f}/100"
    else:
        macro_color = "#64748b"
        macro_text = "Macro N/A"

    # ── T+2.5 suitability ─────────────────────────────────────────────────────
    t25_color = "#22c55e" if scan_ok_for_t25 else "#f59e0b"
    t25_icon  = "✅" if scan_ok_for_t25 else "⚠️"
    t25_text  = "Phù hợp scan T+2.5" if scan_ok_for_t25 else "Thận trọng T+2.5"

    # ── Sector highlights ─────────────────────────────────────────────────────
    sector_html = ""
    if sector_flows:
        inflow  = [s for s, v in sector_flows.items() if v == "INFLOW"][:3]
        outflow = [s for s, v in sector_flows.items() if v == "OUTFLOW"][:2]
        parts = []
        if inflow:
            parts.append(
                "<span style='color:#22c55e;'>🟢 " + " · ".join(inflow) + "</span>"
            )
        if outflow:
            parts.append(
                "<span style='color:#ef4444;'>🔴 " + " · ".join(outflow) + "</span>"
            )
        if parts:
            sector_html = (
                f'<span style="color:#64748b;font-size:12px;margin-left:12px;">'
                f'Ngành: {" &nbsp;|&nbsp; ".join(parts)}</span>'
            )

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;
                    padding:10px 16px;background:#12122a;border-radius:8px;
                    border:1px solid #1e293b;margin-bottom:12px;font-size:13px;">
          <span style="color:{phase_color};font-weight:700;">⏱ {phase_label}</span>
          <span style="color:#475569;">|</span>
          <span style="color:#94a3b8;">{now_str}</span>
          <span style="color:#475569;">|</span>
          <span style="color:{macro_color};font-weight:600;">📊 {macro_text}</span>
          <span style="color:#475569;">|</span>
          <span style="color:{t25_color};font-weight:600;">{t25_icon} {t25_text}</span>
          {sector_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
