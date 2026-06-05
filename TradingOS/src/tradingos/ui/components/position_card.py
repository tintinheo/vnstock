"""Position Card component — open position with T+2.5 lifecycle status."""
from __future__ import annotations

from datetime import date

import streamlit as st

from tradingos.utils.dates import trading_day_offset, trading_days_between


def render_position_card(
    ticker: str,
    entry_date: date,
    entry_price: float,
    initial_sl: float,
    tp1: float = 0.0,
    rt_price: float | None = None,
    signal_mode: str = "",
    mfpm_score: int = 0,
    key_suffix: str = "",
) -> None:
    """
    Render a compact card for a single open position showing:
    - Current P&L vs entry
    - T+2.5 exit date countdown
    - SL and TP1 reference
    - Action buttons: Mark Closed, View Profile
    """
    today = date.today()
    t2_date = trading_day_offset(entry_date, 2)
    # Use trading days remaining, not calendar days (avoids weekend inflation)
    days_left = max(0, trading_days_between(today, t2_date))

    current_price = rt_price if rt_price and rt_price > 0 else entry_price
    pnl_pct = (current_price - entry_price) / max(entry_price, 1) * 100
    pnl_color = "#22c55e" if pnl_pct >= 0 else "#ef4444"
    pnl_sign = "+" if pnl_pct >= 0 else ""

    # ── T+2.5 urgency ─────────────────────────────────────────────────────────
    if today >= t2_date:
        urgency_html = '<span style="color:#dc2626;font-weight:700;">🚨 ATC HÔM NAY</span>'
        border_color = "#dc2626"
    elif days_left == 1:
        urgency_html = f'<span style="color:#f59e0b;font-weight:700;">⏰ ATC ngày mai ({t2_date.strftime("%d/%m")})</span>'
        border_color = "#f59e0b"
    else:
        urgency_html = f'<span style="color:#64748b;">T+2 ATC {t2_date.strftime("%d/%m")} (còn {days_left}d)</span>'
        border_color = "#1e293b"

    # ── SL check ──────────────────────────────────────────────────────────────
    sl_warn = ""
    if initial_sl > 0 and current_price < initial_sl:
        sl_warn = '<div style="color:#dc2626;font-weight:700;font-size:12px;">⛔ Dưới SL — cần xem xét!</div>'

    mode_badge = f'<span style="background:#1e3a5f;color:#93c5fd;padding:1px 6px;border-radius:8px;font-size:11px;">{signal_mode}</span>' if signal_mode else ""

    st.markdown(
        f"""
        <div style="border:1px solid {border_color};border-radius:8px;padding:12px 14px;
                    background:#0f172a;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
            <div>
              <span style="font-size:18px;font-weight:800;color:#f1f5f9;">{ticker}</span>
              &nbsp;{mode_badge}
              {'&nbsp;<span style="color:#64748b;font-size:11px;">MFPM=' + str(mfpm_score) + '</span>' if mfpm_score else ''}
            </div>
            <div style="font-size:18px;font-weight:700;color:{pnl_color};">
              {pnl_sign}{pnl_pct:.2f}%
            </div>
          </div>
          <div style="display:flex;gap:16px;margin-top:8px;font-size:13px;flex-wrap:wrap;">
            <div><span style="color:#64748b;">Vào:</span> <b>{entry_price:,.0f}</b></div>
            <div><span style="color:#64748b;">Hiện:</span> <b style="color:#f1f5f9;">{current_price:,.0f}</b></div>
            {'<div><span style="color:#64748b;">SL:</span> <b style="color:#ef4444;">' + f'{initial_sl:,.0f}' + '</b></div>' if initial_sl > 0 else ''}
            {'<div><span style="color:#64748b;">TP1:</span> <b style="color:#22c55e;">' + f'{tp1:,.0f}' + '</b></div>' if tp1 > 0 else ''}
          </div>
          <div style="margin-top:8px;">{urgency_html}</div>
          {sl_warn}
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    if col_a.button("🔍 Xem Profiler", key=f"pos_profile_{ticker}_{key_suffix}", use_container_width=True):
        st.session_state["_nav_pending"] = "🔍 Profiler"
        st.session_state["profiler_ticker"] = ticker
        st.rerun()
    if col_b.button("✅ Đóng lệnh", key=f"pos_close_{ticker}_{key_suffix}", use_container_width=True):
        st.session_state[f"close_confirm_{ticker}"] = True
        st.rerun()


def render_close_dialog(ticker: str, entry_price: float, key_suffix: str = "") -> float | None:
    """
    Render an inline close-trade form.  Returns the exit price if confirmed, else None.
    """
    if not st.session_state.get(f"close_confirm_{ticker}"):
        return None

    st.markdown(f"**Đóng lệnh {ticker}:**")
    exit_price = st.number_input(
        "Giá thoát",
        value=float(entry_price),
        min_value=1.0,
        step=100.0,
        key=f"exit_price_{ticker}_{key_suffix}",
    )
    c1, c2 = st.columns(2)
    if c1.button("💾 Xác nhận đóng", key=f"confirm_close_{ticker}_{key_suffix}"):
        st.session_state.pop(f"close_confirm_{ticker}", None)
        return exit_price
    if c2.button("Huỷ", key=f"cancel_close_{ticker}_{key_suffix}"):
        st.session_state.pop(f"close_confirm_{ticker}", None)
    return None
