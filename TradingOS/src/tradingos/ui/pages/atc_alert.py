"""ATC Alert page — full-screen exit advisory during 14:30–14:45 window."""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from tradingos.data.cache import cache
from tradingos.engines.portfolio_tracker import portfolio_tracker
from tradingos.ui.components.position_card import render_close_dialog
from tradingos.utils.dates import vn_now, vn_session_phase, trading_day_offset

_ACTION_BADGE = {
    "SELL_FULL_ATC":    ("🔴 SELL FULL ATC",    "#dc2626"),
    "SELL_PARTIAL_ATC": ("🟡 SELL PARTIAL ATC", "#f59e0b"),
    "EXTEND":           ("🟢 HOLD / EXTEND",    "#22c55e"),
    "HOLD":             ("⏸ HOLD",              "#3b82f6"),
    "REVIEW":           ("👀 REVIEW",            "#94a3b8"),
}

_URGENCY_COLOR = {"HIGH": "#dc2626", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}


def render() -> None:
    now_vn  = vn_now()
    phase   = vn_session_phase()
    time_str = now_vn.strftime("%H:%M")

    # ── Auto-refresh JS during active phases ──────────────────────────────────
    if phase == "ATC":
        st.markdown('<script>setTimeout(()=>window.location.reload(true),15000);</script>',
                    unsafe_allow_html=True)
    elif phase == "NEAR_ATC":
        st.markdown('<script>setTimeout(()=>window.location.reload(true),20000);</script>',
                    unsafe_allow_html=True)
    elif phase == "AFTERNOON":
        st.markdown('<script>setTimeout(()=>window.location.reload(true),60000);</script>',
                    unsafe_allow_html=True)

    # ── Phase banner ──────────────────────────────────────────────────────────
    is_active = phase in ("NEAR_ATC", "ATC", "AFTERNOON", "CLOSED")
    if phase == "ATC":
        banner_color = "#dc2626"
        banner_text  = f"⚡ ATC MODE ACTIVE — {time_str} | Còn ít phút đến lúc đóng cửa!"
    elif phase == "NEAR_ATC":
        from datetime import time as dtime
        atc_opens = dtime(14, 43)
        now_time  = now_vn.time()
        mins_left = max(0, int((datetime.combine(date.today(), atc_opens) - datetime.combine(date.today(), now_time)).total_seconds() / 60))
        banner_color = "#f59e0b"
        banner_text  = f"⏰ NEAR ATC — {time_str} | Còn khoảng {mins_left} phút đến ATC 14:43"
    elif phase == "AFTERNOON":
        banner_color = "#3b82f6"
        banner_text  = f"📋 Phiên chiều — {time_str} | Chuẩn bị ATC (14:43–14:45)"
    else:
        banner_color = "#64748b"
        banner_text  = f"📋 ATC Advisor — {time_str} | {phase}"

    st.markdown(
        f'<div style="padding:14px 20px;background:{banner_color}22;border:1px solid {banner_color}55;'
        f'border-radius:8px;margin-bottom:16px;">'
        f'<span style="font-size:18px;font-weight:800;color:{banner_color};">{banner_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Get exit advisories ───────────────────────────────────────────────────
    advisories = portfolio_tracker.get_exit_advisories()
    open_df    = portfolio_tracker.get_open_positions()

    if open_df.empty:
        st.info(
            "📂 Danh mục trống — chưa có vị thế nào cần xem xét ATC.\n\n"
            "Thêm lệnh từ trang **🔍 Profiler** hoặc **📡 Scanner**."
        )
        return

    if not advisories:
        st.info("Không có advisory nào được tạo.")
        return

    # ── Sort by urgency: HIGH first ───────────────────────────────────────────
    urgency_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    advisories.sort(key=lambda a: urgency_order.get(
        getattr(a.get("advisory"), "urgency", "LOW"), 2
    ))

    # ── ATC Summary ───────────────────────────────────────────────────────────
    sell_count = sum(
        1 for a in advisories
        if getattr(a.get("advisory"), "action", "") in ("SELL_FULL_ATC", "SELL_PARTIAL_ATC")
    )
    hold_count = len(advisories) - sell_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Vị thế đang mở", len(advisories))
    c2.metric("Cần bán ATC", sell_count, delta="Hành động ngay" if sell_count > 0 else None,
              delta_color="inverse")
    c3.metric("Hold / Extend", hold_count)

    st.divider()
    st.markdown("### 📋 Chi tiết từng vị thế")

    for item in advisories:
        ticker     = str(item.get("ticker", ""))
        adv        = item.get("advisory")
        entry_px   = float(item.get("entry_price", 0))
        hold_days  = int(item.get("hold_days", 0))
        t2_date    = item.get("t2_date")
        mfpm       = item.get("mfpm_score", 0)
        mode       = str(item.get("signal_mode", ""))

        adv_action  = getattr(adv, "action",      "REVIEW")   if adv else "REVIEW"
        adv_urgency = getattr(adv, "urgency",     "LOW")      if adv else "LOW"
        adv_reason  = getattr(adv, "reason",      "")         if adv else ""
        exit_pct    = getattr(adv, "exit_pct",    1.0)        if adv else 1.0
        exit_window = getattr(adv, "exit_window", "ATC")      if adv else "ATC"

        badge_text, badge_color = _ACTION_BADGE.get(adv_action, ("❓ " + adv_action, "#64748b"))
        urg_color = _URGENCY_COLOR.get(adv_urgency, "#64748b")

        t2_str = t2_date.strftime("%d/%m/%Y") if t2_date else "—"

        sell_pct_str = f"Bán {int(exit_pct * 100)}%" if exit_pct < 1.0 else "Bán toàn bộ"

        with st.container():
            st.markdown(
                f"""
                <div style="border:1px solid {badge_color}44;border-left:4px solid {badge_color};
                            border-radius:8px;padding:14px 16px;background:#0f172a;margin-bottom:12px;">
                  <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                    <div>
                      <span style="font-size:20px;font-weight:800;color:#f1f5f9;">{ticker}</span>
                      &nbsp;
                      <span style="background:{badge_color}22;color:{badge_color};padding:3px 10px;
                                   border-radius:10px;font-weight:700;font-size:14px;">{badge_text}</span>
                    </div>
                    <div>
                      <span style="color:{urg_color};font-size:13px;font-weight:600;">
                        Urgency: {adv_urgency}
                      </span>
                    </div>
                  </div>
                  <div style="display:flex;gap:16px;margin-top:10px;font-size:13px;flex-wrap:wrap;">
                    <div><span style="color:#64748b;">Vào:</span> <b>{entry_px:,.0f}</b></div>
                    <div><span style="color:#64748b;">Nắm giữ:</span> <b>{hold_days}d</b></div>
                    <div><span style="color:#64748b;">T+2 ATC:</span> <b>{t2_str}</b></div>
                    <div><span style="color:#64748b;">Mode:</span> <b>{mode}</b></div>
                    <div><span style="color:#64748b;">MFPM:</span> <b>{mfpm}</b></div>
                  </div>
                  <div style="margin-top:10px;color:#cbd5e1;font-style:italic;">"{adv_reason}"</div>
                  <div style="margin-top:8px;color:#64748b;font-size:12px;">
                    → Khuyến nghị: <b style="color:{badge_color};">{sell_pct_str}</b> tại {exit_window}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_a, col_b, col_c = st.columns(3)
            if col_a.button("🔍 Xem Profiler", key=f"atc_profile_{ticker}"):
                st.session_state["_nav_pending"] = "🔍 Profiler"
                st.session_state["profiler_ticker"] = ticker
                st.rerun()

            if adv_action in ("SELL_FULL_ATC", "SELL_PARTIAL_ATC"):
                if col_b.button("✅ Đánh dấu đã bán", key=f"atc_close_{ticker}"):
                    st.session_state[f"close_confirm_{ticker}"] = True
                    st.rerun()

            if col_c.button("⏸ Bỏ qua", key=f"atc_skip_{ticker}"):
                st.session_state[f"atc_skip_{ticker}"] = True

            # Inline close form
            if st.session_state.get(f"close_confirm_{ticker}"):
                exit_price = render_close_dialog(ticker, entry_px, key_suffix=f"atc_{ticker}")
                if exit_price is not None:
                    if portfolio_tracker.close_position(ticker, exit_price):
                        st.success(f"✅ Đã đóng {ticker} tại {exit_price:,.0f}")
                        st.rerun()

    # ── Instructions ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("📖 Hướng dẫn thực hiện ATC", expanded=False):
        st.markdown(
            """
            **Cách đặt lệnh ATC:**
            1. Mở ứng dụng môi giới (SSI, VPS, DNSE, VNDirect...)
            2. Chọn mã cần bán → Đặt lệnh **ATO/ATC** (không đặt lệnh LO giờ này)
            3. Cửa sổ: **14:43 – 14:45** (HOSE) | **14:45** (HNX)
            4. Sau khi khớp → quay lại đây click "✅ Đánh dấu đã bán" để ghi nhận

            **Lưu ý:**
            - `SELL_FULL_ATC` = bán toàn bộ vị thế
            - `SELL_PARTIAL_ATC` = bán theo % đề xuất (thường 40%), giữ phần còn lại
            - `EXTEND` = giữ tiếp, hệ thống sẽ tính ngày thoát mới
            - **Không nên đuổi giá sau 14:45** — đặt ATC thì chắc chắn khớp.
            """
        )
