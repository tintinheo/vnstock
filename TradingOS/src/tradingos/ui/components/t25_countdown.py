"""T+2.5 Countdown Widget component."""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from tradingos.utils.dates import VN_TZ, is_trading_day, next_trading_day, trading_day_offset


def _atc_target_dt(entry_date: date) -> tuple[date, str]:
    """
    Return the T+2 exit date (ATC) and human-readable label.
    T+2 is 2 trading days after entry_date.
    """
    t2 = trading_day_offset(entry_date, 2)
    label = t2.strftime("%d/%m/%Y")
    return t2, label


def _trading_days_left(from_date: date, to_date: date) -> int:
    """Count trading days between from_date (inclusive) and to_date (exclusive)."""
    count = 0
    d = from_date
    while d < to_date:
        if is_trading_day(d):
            count += 1
        from datetime import timedelta
        d += timedelta(days=1)
    return count


def render_t25_countdown(
    ticker: str,
    entry_date: date | None = None,
    entry_price: float = 0.0,
    tplus_target_t25: float = 0.0,
    tplus_stop: float = 0.0,
    tplus_entry_low: float = 0.0,
    tplus_entry_high: float = 0.0,
    tplus_verdict: str = "",
    tplus_confidence: float = 0.0,
    key_suffix: str = "",
) -> None:
    """
    Render a T+2.5 countdown box showing:
    - T+0 entry → T+2 ATC exit timeline
    - Trading days remaining
    - Target price and stop for T+2.5
    - Color-coded urgency
    """
    now_vn = datetime.now(VN_TZ)
    today = now_vn.date()

    if entry_date is None:
        entry_date = today

    t2_date, t2_label = _atc_target_dt(entry_date)
    days_left = _trading_days_left(today, t2_date)
    calendar_days = (t2_date - today).days

    # ── Color by urgency ──────────────────────────────────────────────────────
    if today >= t2_date:
        box_color = "#dc2626"
        urgency_text = "🚨 ATC HÔM NAY — Cần xem xét thoát lệnh!"
    elif days_left <= 1:
        box_color = "#f59e0b"
        urgency_text = "⏰ ATC ngày mai"
    else:
        box_color = "#3b82f6"
        urgency_text = f"📅 Còn {days_left} phiên giao dịch ({calendar_days} ngày lịch)"

    # ── Timeline dots ─────────────────────────────────────────────────────────
    t0_label = entry_date.strftime("%d/%m")
    t1_date = trading_day_offset(entry_date, 1)
    t1_label = t1_date.strftime("%d/%m")
    timeline_html = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:8px 0;font-size:13px;">'
        f'<span style="background:#22c55e;color:#000;padding:2px 8px;border-radius:12px;">T+0 {t0_label}</span>'
        f'<span style="color:#64748b;">──────</span>'
        f'<span style="background:#3b82f6;color:#fff;padding:2px 8px;border-radius:12px;">T+1 {t1_label}</span>'
        f'<span style="color:#64748b;">──────</span>'
        f'<span style="background:{box_color};color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;">T+2 ATC {t2_label} ✨</span>'
        f'</div>'
    )

    # ── Price plan ────────────────────────────────────────────────────────────
    target_pct = ""
    if entry_price > 0 and tplus_target_t25 > 0:
        pct = (tplus_target_t25 - entry_price) / entry_price * 100
        target_pct = f" ({pct:+.1f}%)"
    stop_pct = ""
    if entry_price > 0 and tplus_stop > 0:
        spct = (tplus_stop - entry_price) / entry_price * 100
        stop_pct = f" ({spct:+.1f}%)"

    entry_zone_html = ""
    if tplus_entry_low > 0 and tplus_entry_high > 0:
        entry_zone_html = (
            f'<div style="font-size:12px;color:#94a3b8;margin-top:4px;">'
            f'Vùng vào: {tplus_entry_low:,.0f} – {tplus_entry_high:,.0f}</div>'
        )

    verdict_html = ""
    if tplus_verdict:
        _VERDICT_COLOR = {
            "MUA_NGAY": "#22c55e",
            "CHO_XAC_NHAN": "#f59e0b",
            "THEO_DOI": "#3b82f6",
            "TRANH_XA": "#ef4444",
        }
        vc = _VERDICT_COLOR.get(tplus_verdict.upper(), "#94a3b8")
        conf_str = f" · Conf {tplus_confidence:.0f}%" if tplus_confidence > 0 else ""
        verdict_html = (
            f'<span style="background:{vc}22;color:{vc};padding:2px 8px;'
            f'border-radius:8px;font-size:12px;font-weight:600;">'
            f'{tplus_verdict}{conf_str}</span>'
        )

    st.markdown(
        f"""
        <div style="border:1px solid {box_color}55;border-left:4px solid {box_color};
                    border-radius:8px;padding:14px 16px;background:{box_color}0d;
                    margin-bottom:12px;">
          <div style="font-size:13px;font-weight:700;color:{box_color};margin-bottom:6px;">
            ⏱ T+2.5 Countdown — {ticker}
          </div>
          {timeline_html}
          <div style="font-size:14px;color:#e2e8f0;margin-top:8px;">{urgency_text}</div>
          <div style="display:flex;gap:24px;margin-top:10px;flex-wrap:wrap;">
            {'<div><span style="color:#94a3b8;font-size:11px;">Vào lệnh</span><br><span style="font-size:15px;font-weight:700;color:#f1f5f9;">' + f'{entry_price:,.0f}' + '</span></div>' if entry_price > 0 else ''}
            {'<div><span style="color:#94a3b8;font-size:11px;">Target T+2.5</span><br><span style="font-size:15px;font-weight:700;color:#22c55e;">' + f'{tplus_target_t25:,.0f}{target_pct}' + '</span></div>' if tplus_target_t25 > 0 else ''}
            {'<div><span style="color:#94a3b8;font-size:11px;">Stop T+2.5</span><br><span style="font-size:15px;font-weight:700;color:#ef4444;">' + f'{tplus_stop:,.0f}{stop_pct}' + '</span></div>' if tplus_stop > 0 else ''}
          </div>
          {entry_zone_html}
          <div style="margin-top:8px;">{verdict_html}</div>
          <div style="font-size:11px;color:#475569;margin-top:8px;">
            Exit khuyến nghị: ATC {t2_label} 14:43–14:45
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Flash warning if T+2 is today
    if today >= t2_date:
        st.error(f"🚨 **{ticker}** — ATC hôm nay! Kiểm tra T+2.5 Exit Advisory trước 14:43.")
