"""Morning Briefing page — default homepage for TradingOS."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from tradingos.data.cache import cache
from tradingos.engines.portfolio_tracker import portfolio_tracker
from tradingos.ui.components.market_breadth import render_market_breadth
from tradingos.ui.components.position_card import render_position_card, render_close_dialog
from tradingos.utils.dates import vn_now, vn_session_phase, trading_day_offset

_PHASE_VN = {
    "PRE_MARKET":  "Chưa mở phiên",
    "PRE_ATO":     "Chuẩn bị ATO",
    "ATO":         "Đang ATO",
    "MORNING":     "Phiên sáng",
    "LUNCH":       "Nghỉ trưa",
    "AFTERNOON":   "Phiên chiều",
    "NEAR_ATC":    "Sắp ATC",
    "ATC":         "Đang ATC",
    "CLOSED":      "Đã đóng phiên",
}

_WEEKDAYS_VN = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]

_ACTION_ICON = {
    "STRONG_BUY": "🚀",
    "BUY":        "🟢",
    "WATCH":      "👀",
    "NO_ACTION":  "⏸",
    "EXIT":       "🔴",
    "FORCED_EXIT":"⚠️",
}


def render() -> None:
    now_vn   = vn_now()
    today    = now_vn.date()
    weekday  = _WEEKDAYS_VN[today.weekday()]
    phase    = vn_session_phase()
    phase_vn = _PHASE_VN.get(phase, phase)
    time_str = now_vn.strftime("%H:%M")

    st.markdown(
        f'<h2 style="margin-bottom:4px;">☀️ Morning Briefing</h2>'
        f'<p style="color:#64748b;margin-top:0;">{weekday}, {today.strftime("%d/%m/%Y")} — {time_str} | {phase_vn}</p>',
        unsafe_allow_html=True,
    )

    # ── Market Breadth Banner ─────────────────────────────────────────────────
    macro_score  = None
    macro_regime = ""
    sector_flows: dict = {}
    try:
        from tradingos.engines.money_flow_service import MoneyFlowService
        mf_svc = MoneyFlowService()
        rotation = mf_svc.get_sector_flows()
        if isinstance(rotation, dict):
            sectors = rotation.get("sectors", {})
            sector_flows = {k: v.get("flow_status", "NEUTRAL") for k, v in sectors.items()} if isinstance(sectors, dict) else {}
    except Exception:
        pass

    try:
        from tradingos.core.macro import get_macro_regime
        macro_data   = get_macro_regime()
        macro_score  = macro_data.get("score")
        macro_regime = macro_data.get("regime", "")
    except Exception:
        pass

    scan_ok = macro_score is None or macro_score >= 30
    render_market_breadth(macro_score, macro_regime, sector_flows, scan_ok)

    # ── Section 1: Actions needed today ──────────────────────────────────────
    due_today = portfolio_tracker.get_positions_due_today()
    advisories = portfolio_tracker.get_exit_advisories()
    advisory_map = {a["ticker"]: a for a in advisories}

    open_positions = portfolio_tracker.get_open_positions()

    st.markdown("### ⚠️ Hành động hôm nay")

    if due_today:
        for pos in due_today:
            ticker     = str(pos.get("ticker", ""))
            entry_date = _to_date(pos.get("entry_date"))
            entry_px   = float(pos.get("entry_price") or 0)
            adv        = advisory_map.get(ticker, {}).get("advisory")
            adv_action = getattr(adv, "action", "REVIEW") if adv else "REVIEW"
            adv_reason = getattr(adv, "reason", "") if adv else ""
            t2 = trading_day_offset(entry_date, 2) if entry_date else today

            col_l, col_r = st.columns([5, 1])
            col_l.markdown(
                f'<div style="border-left:4px solid #dc2626;padding:8px 12px;background:#1c0a0a;border-radius:6px;">'
                f'<b style="color:#f87171;">🚨 {ticker}</b> — ATC {"hôm nay" if today >= t2 else t2.strftime("%d/%m")} '
                f'<span style="color:#64748b;font-size:12px;">({adv_action})</span><br>'
                f'<span style="color:#94a3b8;font-size:12px;">{adv_reason}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if col_r.button("→ Xem", key=f"mb_due_{ticker}", use_container_width=True):
                st.session_state["_nav_pending"] = "🔍 Profiler"
                st.session_state["profiler_ticker"] = ticker
                st.rerun()

        st.divider()
    elif not open_positions.empty:
        st.info("✅ Không có vị thế nào đến hạn ATC hôm nay.")
    else:
        st.info("📂 Chưa có vị thế nào trong danh mục. Thêm lệnh từ trang **📡 Scanner** hoặc **🔍 Profiler**.")

    # ── Section 2: Open positions ─────────────────────────────────────────────
    if not open_positions.empty:
        st.markdown(f"### 📂 Danh mục đang nắm ({len(open_positions)} mã)")

        # Sort: most urgent first
        rows = []
        for _, row in open_positions.iterrows():
            entry_d = _to_date(row.get("entry_date"))
            t2 = trading_day_offset(entry_d, 2) if entry_d else today
            rows.append((t2, row))
        rows.sort(key=lambda x: x[0])

        for t2_d, row in rows:
            ticker   = str(row.get("ticker", ""))
            entry_d  = _to_date(row.get("entry_date"))
            entry_px = float(row.get("entry_price") or 0)
            sl       = float(row.get("initial_sl") or 0)

            render_position_card(
                ticker=ticker,
                entry_date=entry_d or today,
                entry_price=entry_px,
                initial_sl=sl,
                signal_mode=str(row.get("signal_mode") or ""),
                mfpm_score=int(row.get("mfpm_score") or 0),
                key_suffix=f"mb_{ticker}",
            )

            # Handle close dialog inline
            exit_price = render_close_dialog(ticker, entry_px, key_suffix=f"mb_{ticker}")
            if exit_price is not None:
                if portfolio_tracker.close_position(ticker, exit_price):
                    st.success(f"✅ Đã đóng {ticker} tại {exit_price:,.0f}")
                    st.rerun()
                else:
                    st.error(f"Không tìm thấy lệnh mở cho {ticker}")

        st.divider()

    # ── Section 3: Latest scanner opportunities ───────────────────────────────
    st.markdown("### 🎯 Cơ hội mới nhất")

    cached = cache.get_latest_scan("FULL")
    if cached and "results" in cached:
        _render_scan_cards(cached["results"])
    else:
        st.info(
            "Chưa có kết quả scan được cache. "
            "Chạy **📡 Scanner** để quét và kết quả sẽ hiển thị ở đây tự động."
        )
        col_scan, _ = st.columns([1, 3])
        if col_scan.button("📡 Mở Scanner ngay", use_container_width=True):
            st.session_state["_nav_pending"] = "📡 Scanner"
            st.rerun()

    # ── Section 4: Quick ticker lookup ────────────────────────────────────────
    st.divider()
    st.markdown("### 🔍 Tra cứu nhanh")
    col_q, col_btn = st.columns([3, 1])
    quick_ticker = col_q.text_input(
        "Nhập mã cổ phiếu",
        placeholder="VCB, HPG, FPT...",
        label_visibility="collapsed",
        key="mb_quick_ticker",
    ).strip().upper()
    if col_btn.button("→ Phân tích", use_container_width=True, key="mb_quick_go"):
        if quick_ticker:
            st.session_state["_nav_pending"] = "🔍 Profiler"
            st.session_state["profiler_ticker"] = quick_ticker
            st.rerun()


def _render_scan_cards(results: list[dict]) -> None:
    """Render top BUY/STRONG_BUY from cached scan results as cards."""
    buy_results = [
        r for r in results
        if r.get("action") in ("STRONG_BUY", "BUY")
        and r.get("amf_decision", "") != "BLOCK"
    ]

    if not buy_results:
        st.info("Scanner gần nhất không có tín hiệu BUY/STRONG_BUY.")
        return

    # Sort by MFPM desc
    buy_results.sort(key=lambda r: r.get("mfpm_score", 0) or 0, reverse=True)
    top = buy_results[:6]

    cols = st.columns(3)
    for i, r in enumerate(top):
        ticker     = r.get("ticker", "")
        action     = r.get("action", "")
        mfpm       = r.get("mfpm_score", 0) or 0
        sms        = r.get("sms_raw", 0) or 0
        tplus_v    = r.get("tplus_verdict", "") or ""
        close_px   = r.get("close", 0) or 0
        pattern    = r.get("best_pattern", "") or ""
        conf       = r.get("confidence", "") or ""

        icon = _ACTION_ICON.get(action, "")
        _VERDICT_COLOR = {
            "MUA_NGAY":      "#22c55e",
            "CHO_XAC_NHAN":  "#f59e0b",
            "THEO_DOI":      "#3b82f6",
            "TRANH_XA":      "#ef4444",
        }
        vc = _VERDICT_COLOR.get(tplus_v.upper(), "#64748b")
        _action_color = {
            "STRONG_BUY": "#22c55e",
            "BUY":        "#3b82f6",
        }.get(action, "#94a3b8")

        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="border:1px solid {_action_color}44;border-radius:8px;
                            padding:12px 14px;background:#0f172a;margin-bottom:8px;">
                  <div style="font-size:18px;font-weight:800;color:{_action_color};">
                    {icon} {ticker}
                  </div>
                  <div style="font-size:12px;color:#64748b;margin:2px 0;">
                    {action} · {conf}
                  </div>
                  <div style="display:flex;gap:12px;margin-top:6px;font-size:13px;">
                    <span>MFPM <b>{mfpm}</b></span>
                    <span>SMS <b>{sms}</b></span>
                  </div>
                  <div style="margin-top:6px;">
                    <span style="background:{vc}22;color:{vc};padding:1px 7px;
                                 border-radius:8px;font-size:12px;">{tplus_v}</span>
                    {'&nbsp;<span style="color:#64748b;font-size:11px;">' + pattern + '</span>' if pattern else ''}
                  </div>
                  <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
                    Giá: {close_px:,.0f} VND
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("→ Profiler", key=f"mb_card_{ticker}_{i}", use_container_width=True):
                st.session_state["_nav_pending"] = "🔍 Profiler"
                st.session_state["profiler_ticker"] = ticker
                st.rerun()

    if len(buy_results) > 6:
        st.caption(f"Hiển thị 6/{len(buy_results)} cơ hội — mở **📡 Scanner** để xem đầy đủ.")
        if st.button("📡 Xem tất cả trong Scanner", key="mb_all_scanner"):
            st.session_state["_nav_pending"] = "📡 Scanner"
            st.rerun()


# ── helpers ───────────────────────────────────────────────────────────────────

def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        if hasattr(value, "date"):
            return value.date()
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None
