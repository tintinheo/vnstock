"""Scanner page — batch universe screener."""
from __future__ import annotations

from datetime import datetime, date as _date_cls
from pathlib import Path
import streamlit as st
import pandas as pd

from tradingos.engines.scanner_service import ScannerService
from tradingos.engines.audit_service import AuditService
from tradingos.data.schemas import ScanRequest
from tradingos.data.cache import cache
from tradingos.core.nlp import generate_summary_headline
from tradingos.ui.components.dataframe_filter import filter_dataframe
from tradingos.ui.components.market_breadth import render_market_breadth
from tradingos.ui.components.tplus_explainer import (
    TPLUS_MAPPING_GUIDE,
    build_action_tplus_explanation,
    build_tplus_exit_plan,
    verdict_label,
    verdict_row_tint,
    verdict_style,
)

_ACTION_ORDER = {"STRONG_BUY": 0, "BUY": 1, "WATCH": 2, "NO_ACTION": 3, "EXIT": 4, "FORCED_EXIT": 5}

_RESULT_DIR = Path(__file__).resolve().parents[4] / "data" / "result"

# ── Quick Filter Presets ──────────────────────────────────────────────────────
_PRESETS = {
    "🚀 T+2.5 Ready":  {"min_mfpm": 70, "min_sms": 60, "include_blocked": False,
                         "hint": "MFPM≥70, SMS≥60, AMF=PASS — cơ hội T+2.5 chất lượng cao"},
    "🐳 Whale Alert":  {"min_mfpm": 50, "min_sms": 75, "include_blocked": False,
                         "hint": "SMS≥75 — tổ chức/cá voi đang tích lũy mạnh"},
    "⚡ Breakout":     {"min_mfpm": 65, "min_sms": 55, "include_blocked": False,
                         "hint": "MFPM≥65 — mã chuẩn bị bứt phá, Mode B"},
    "🛡 Phòng thủ":   {"min_mfpm": 50, "min_sms": 45, "include_blocked": False,
                         "hint": "MFPM≥50 — setup thận trọng, AMD=ACCUMULATION"},
    "🔧 Custom":       {"min_mfpm": 0,  "min_sms": 0,  "include_blocked": False,
                         "hint": "Chỉnh tùy ý"},
}


def _save_csv(df: pd.DataFrame, prefix: str) -> Path:
    """Save df to data/result/<prefix>-YYYYMMDD_HHMMSS.csv and return the path."""
    _RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _RESULT_DIR / f"{prefix}-{ts}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path

_SCANNER_READING_GUIDE = """
- `Action`, `MFPM`, `SMS`, `T+ Verdict` là 4 lớp ưu tiên để sàng cơ hội.
- `RSI`, `Pattern`, `HMM`, `Sector Flow` dùng để giải thích bối cảnh, không nên dùng riêng lẻ để mua.
- `AMF` khác `NO_ACTION`: `AMF BLOCK` là cờ rủi ro thao túng, nên coi nặng hơn một tín hiệu kỹ thuật đẹp.
"""

# Core columns always shown; extras hidden behind expander
_CORE_COLUMNS = ["Mã", "Action", "Conf", "MFPM", "SMS", "T+ Verdict", "T+ Conf",
                 "Giá", "Vào", "SL", "R:R", "AMF", "Pattern"]


@st.cache_data(ttl=300, show_spinner=False)
def _load_scanner_macro() -> tuple[float | None, str, dict]:
    """Cache macro + sector-flow for 5 min to avoid repeated API calls on each filter/rerun."""
    from tradingos.core.macro import get_macro_regime
    from tradingos.engines.money_flow_service import MoneyFlowService
    macro_score: float | None = None
    macro_regime = ""
    sector_flows: dict = {}
    try:
        m = get_macro_regime()
        macro_score  = m.get("score")
        macro_regime = m.get("regime", "")
    except Exception:
        pass
    try:
        rotation = MoneyFlowService().get_sector_flows()
        if isinstance(rotation, dict):
            s = rotation.get("sectors", {})
            sector_flows = {k: v.get("flow_status", "NEUTRAL") for k, v in s.items()} if isinstance(s, dict) else {}
    except Exception:
        pass
    return macro_score, macro_regime, sector_flows


def render() -> None:
    st.title("📡 Scanner")
    st.caption("Quét toàn bộ universe theo MFPM score — lọc cơ hội mua theo Mode A/B/W.")

    # ── Market Breadth Banner (cached 5 min) ───────────────────────────────────
    try:
        macro_score, macro_regime, sector_flows = _load_scanner_macro()
    except Exception:
        macro_score, macro_regime, sector_flows = None, "", {}
    render_market_breadth(macro_score, macro_regime, sector_flows, macro_score is None or macro_score >= 30)

    with st.expander("🧭 Cách đọc kết quả Scanner", expanded=False):
        st.markdown(_SCANNER_READING_GUIDE)
    with st.expander("🧩 Mapping chuẩn giữa Action và T+ Verdict", expanded=False):
        st.markdown(TPLUS_MAPPING_GUIDE)

    # ── Quick Filter Presets ──────────────────────────────────────────────────
    st.markdown("**⚡ Quick Filter:**")
    preset_names = list(_PRESETS.keys())
    preset_key = st.radio(
        "Preset",
        options=preset_names,
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="scanner_preset",
    )
    preset = _PRESETS[preset_key]
    st.caption(f"💡 {preset['hint']}")

    with st.form("scanner_form"):
        col_left, col_right = st.columns([3, 1])
        ticker_input = col_left.text_area(
            "Danh sách mã (mỗi mã một dòng, hoặc CSV — để trống = quét theo sàn đã chọn)",
            placeholder="VCB\nHPG\nSSI\nVNM",
            height=100,
        )
        exchange = col_left.selectbox("Sàn", ["HOSE", "HNX", "UPCOM", "ALL"], index=0)
        min_mfpm = col_right.slider("MFPM tối thiểu", 0, 120, int(preset["min_mfpm"]))
        min_sms  = col_right.slider("SMS tối thiểu", 0, 100, int(preset["min_sms"]))
        max_workers = col_right.slider("Workers", 1, 16, 8)
        include_blocked = col_right.checkbox(
            "Hiển thị mã bị AMF chặn",
            value=bool(preset["include_blocked"]),
            help="AMF (Anti-Manipulation Filter) — bỏ chọn để lọc mã nghi thao túng",
        )
        submitted = st.form_submit_button("🔍 Quét ngay", use_container_width=True)

    if submitted:
        raw = ticker_input.replace(",", "\n").replace(" ", "\n")
        tickers = [t.strip().upper() for t in raw.split("\n") if t.strip()] or None

        if tickers is None:
            st.info(f"⏳ Quét toàn bộ {exchange} — có thể mất vài phút...")

        request = ScanRequest(
            tickers=tickers,
            exchange=exchange,
            limit=len(tickers) if tickers else 2000,
            min_mfpm_score=min_mfpm,
            min_sms=min_sms,
            min_action="",
            include_blocked=include_blocked,
        )

        svc = ScannerService(max_workers=max_workers)
        audit_svc = AuditService()

        with st.spinner("Đang quét..."):
            result = svc.scan(request)

        if not result.results:
            st.info("Không có kết quả phù hợp.")
            st.session_state.pop("scanner_result", None)
            return

        # Log to audit
        for item in result.results:
            audit_svc.log_event(
                event_type="SCAN",
                ticker=item.ticker,
                action=item.action,
                mfpm_score=item.mfpm_score,
                sms_raw=item.sms_raw,
                confidence=item.confidence,
                extra={
                    "signal_mode": item.signal_mode,
                    "close": item.close,
                    "best_pattern": item.best_pattern,
                    "tplus_setup": item.tplus_setup,
                    "tplus_verdict": item.tplus_verdict,
                    "tplus_verdict_vi": getattr(item, "tplus_verdict_vi", ""),
                    "tplus_confidence": item.tplus_confidence,
                    "tplus_entry_low": getattr(item, "tplus_entry_low", 0.0),
                    "tplus_entry_high": getattr(item, "tplus_entry_high", 0.0),
                    "tplus_target_t25": getattr(item, "tplus_target_t25", 0.0),
                    "tplus_target_t5": getattr(item, "tplus_target_t5", 0.0),
                    "tplus_stop": getattr(item, "tplus_stop", 0.0),
                },
            )

        st.session_state["scanner_result"] = result
        st.session_state["scanner_summary"] = (
            f"✅ Quét xong: **{result.tickers_scanned}** mã → "
            f"hiển thị **{result.tickers_passed}** kết quả"
        )
        # Save to cache so Morning Briefing can display latest opportunities
        try:
            import uuid, dataclasses
            _cache_rows = []
            for _r in result.results:
                _row = dataclasses.asdict(_r) if dataclasses.is_dataclass(_r) else dict(vars(_r))
                _cache_rows.append(_row)
            cache.put_scan_result(
                scan_id=str(uuid.uuid4()),
                scan_type="FULL",
                scan_date=_date_cls.today(),
                data={"results": _cache_rows},
            )
        except Exception:
            pass
        # Auto-export to data/result/
        _df_export = pd.DataFrame([
            {
                "Mã": i.ticker, "Action": i.action, "Conf": i.confidence,
                "MFPM": i.mfpm_score, "Macro": i.macro_regime, "MacroScore": i.macro_score,
                "Sector Flow": i.sector_flow, "BCTC Risk": i.earnings_risk,
                "FundScore": i.fundamental_score, "W-Score": i.mode_w_score,
                "SMS": i.sms_raw, "SMS Label": i.sms_label, "Mode": i.signal_mode,
                "Giá": i.close, "Vào": i.entry, "SL": i.sl, "TP1": i.tp1, "R:R": i.rr,
                "AMF": i.amf_decision, "Pattern": i.best_pattern, "HMM": i.hmm_state,
                "Stealth": i.stealth_accum,
                "T+ Setup": getattr(i, "tplus_setup", ""),
                "T+ Verdict": getattr(i, "tplus_verdict", ""),
                "T+ Conf": getattr(i, "tplus_confidence", 0.0),
                "Trend Warning": getattr(i, "trend_warning", "NONE") or "NONE",
                "Dự báo": getattr(i, "fc_overall_vote", "") or "",
                "FC Conf%": round(getattr(i, "fc_overall_conf", 0.0) or 0.0, 0),
                "CVD": getattr(i, "cvd_signal", "N/A"),
            }
            for i in result.results
        ])
        _saved = _save_csv(_df_export, "Scanner")
        st.session_state["scanner_csv_path"] = str(_saved)

    # ── Retrieve from session_state (survives filter reruns) ─────────────────
    result = st.session_state.get("scanner_result")
    if result is None:
        st.info("Nhập danh sách mã và nhấn 🔍 Quét ngay để bắt đầu.")
        return

    st.success(st.session_state.get("scanner_summary", ""))
    if "scanner_csv_path" in st.session_state:
        st.caption(f"💾 Đã lưu CSV: `{st.session_state['scanner_csv_path']}`")

    rows = []
    for item in result.results:
        rows.append({
            "Mã":       item.ticker,
            "Action":   item.action,
            "Conf":     item.confidence,
            "MFPM":     item.mfpm_score,
            "Macro":    item.macro_regime,
            "MacroScore": item.macro_score,
            "Sector Flow": item.sector_flow,
            "BCTC Risk": item.earnings_risk,
            "FundScore": item.fundamental_score,
            "W-Score":  item.mode_w_score,
            "SMS":      item.sms_raw,
            "SMS Label":item.sms_label,
            "Mode":     item.signal_mode,
            "Giá":      item.close,
            "Vào":      item.entry,
            "SL":       item.sl,
            "TP1":      item.tp1,
            "R:R":      item.rr,
            "AMF":      item.amf_decision,
            "Pattern":  item.best_pattern,
            "HMM":      item.hmm_state,
            "Stealth":  item.stealth_accum,
            "Tóm tắt NLP": generate_summary_headline(
                ticker=item.ticker,
                action=item.action,
                mfpm_score=item.mfpm_score,
                signal_mode=item.signal_mode,
                rsi14=getattr(item, "rsi14", 50.0),
                sms_raw=item.sms_raw,
                stealth_accum=item.stealth_accum,
                best_pattern=item.best_pattern,
                distribution_warning=getattr(item, "distribution_warning", "NONE"),
                hmm_state=item.hmm_state,
            ),
            "T+ Setup":   getattr(item, "tplus_setup",    "T_NO_SETUP"),
            "T+ Verdict": getattr(item, "tplus_verdict",  "THEO_DOI"),
            "T+ Verdict VI": verdict_label(
                getattr(item, "tplus_verdict", "THEO_DOI"),
                getattr(item, "tplus_verdict_vi", ""),
            ),
            "T+ Conf":    getattr(item, "tplus_confidence", 0.0),
            "A×T+ Ý nghĩa": build_action_tplus_explanation(
                item.action,
                getattr(item, "tplus_verdict", "THEO_DOI"),
            ),
            "T+ Exit": build_tplus_exit_plan(
                getattr(item, "tplus_verdict", "THEO_DOI"),
                getattr(item, "tplus_stop", 0.0),
                getattr(item, "tplus_target_t25", 0.0),
                getattr(item, "tplus_target_t5", 0.0),
                getattr(item, "tplus_entry_low", 0.0),
                getattr(item, "tplus_entry_high", 0.0),
            ),
            "Trend Warning": getattr(item, "trend_warning", "NONE") or "NONE",
            "D\u1ef1 b\u00e1o":    getattr(item, "fc_overall_vote", "") or "",
            "FC Conf%":   round(getattr(item, "fc_overall_conf", 0.0) or 0.0, 0),
            "CVD":        getattr(item, "cvd_signal",       "N/A"),
        })

    df_all = pd.DataFrame(rows)
    df_all["_sort"] = df_all["Action"].map(_ACTION_ORDER).fillna(9)
    df_all = df_all.sort_values(["_sort", "MFPM"], ascending=[True, False]).drop(columns="_sort")

    # ── Signal breakdown ──────────────────────────────────────────────────────
    breakdown = df_all["Action"].value_counts()
    _icons = {"STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀", "NO_ACTION": "⏸", "EXIT": "🔴", "FORCED_EXIT": "⚠️"}
    cols = st.columns(min(len(breakdown), 6))
    for i, (action, count) in enumerate(breakdown.items()):
        cols[i % len(cols)].metric(f"{_icons.get(action, '📋')} {action}", count)

    st.divider()

    # ── Filter controls ───────────────────────────────────────────────────────
    with st.expander("🔍 Bộ lọc kết quả", expanded=True):
        sc_r1 = st.columns([2, 2, 2, 1])
        selected_actions = sc_r1[0].multiselect(
            "Action",
            options=list(_ACTION_ORDER.keys()),
            default=[],
            placeholder="Tất cả",
            key="scanner_action_filter",
        )
        selected_modes = sc_r1[1].multiselect(
            "Mode",
            options=sorted(df_all["Mode"].unique().tolist()),
            default=[],
            placeholder="Tất cả",
            key="scanner_mode_filter",
        )
        _sc_tw_opts = sorted(df_all["Trend Warning"].dropna().unique().tolist())
        selected_tw = sc_r1[2].multiselect(
            "⚠️ Trend Warning",
            options=_sc_tw_opts,
            default=[],
            placeholder="Tất cả",
            key="scanner_tw_filter",
        )
        stealth_only = sc_r1[3].checkbox("Stealth only", key="scanner_stealth")

        sc_r2 = st.columns([2, 2, 2, 2])
        _sc_fc_opts = [v for v in ["TĂNG", "GIẢM", "TRUNG LẬP"] if v in df_all["Dự báo"].values]
        selected_fc = sc_r2[0].multiselect(
            "🔭 Dự báo",
            options=_sc_fc_opts,
            default=[],
            placeholder="Tất cả",
            key="scanner_fc_filter",
        )
        _sc_vd_opts = sorted(df_all["T+ Verdict"].dropna().unique().tolist())
        selected_vd = sc_r2[1].multiselect(
            "🎯 T+ Verdict",
            options=_sc_vd_opts,
            default=[],
            placeholder="Tất cả",
            key="scanner_vd_filter",
        )
        min_tconf = sc_r2[2].number_input(
            "T+ Conf% tối thiểu", min_value=0, max_value=100, value=0, step=5,
            key="scanner_tconf_min",
        )
        min_fcconf = sc_r2[3].number_input(
            "FC Conf% tối thiểu", min_value=0, max_value=100, value=0, step=5,
            key="scanner_fcconf_min",
        )

    df_show = df_all.copy()
    if selected_actions:
        df_show = df_show[df_show["Action"].isin(selected_actions)]
    if selected_modes:
        df_show = df_show[df_show["Mode"].isin(selected_modes)]
    if stealth_only:
        df_show = df_show[df_show["Stealth"] == True]
    if selected_tw:
        df_show = df_show[df_show["Trend Warning"].isin(selected_tw)]
    if selected_fc:
        df_show = df_show[df_show["Dự báo"].isin(selected_fc)]
    if selected_vd:
        df_show = df_show[df_show["T+ Verdict"].isin(selected_vd)]
    if min_tconf > 0:
        df_show = df_show[df_show["T+ Conf"] >= min_tconf]
    if min_fcconf > 0:
        df_show = df_show[df_show["FC Conf%"] >= min_fcconf]

    st.caption(f"Hiển thị **{len(df_show)}** / {len(df_all)} mã sau lọc")

    # ── View mode: Table vs Card ──────────────────────────────────────────────
    view_col, export_col = st.columns([3, 1])
    view_mode = view_col.radio(
        "Chế độ hiển thị",
        options=["📋 Table", "🃏 Cards"],
        horizontal=True,
        label_visibility="collapsed",
        key="scanner_view_mode",
    )

    # ── Column visibility ─────────────────────────────────────────────────────
    with st.expander("👁 Ẩn/Hiện cột", expanded=False):
        all_cols = [c for c in df_show.columns if c not in ("_sort",)]
        extra_cols = [c for c in all_cols if c not in _CORE_COLUMNS]
        show_extra = st.multiselect(
            "Thêm cột",
            options=extra_cols,
            default=[],
            key="scanner_extra_cols",
        )
    visible_cols = [c for c in _CORE_COLUMNS if c in df_show.columns] + [c for c in show_extra if c in df_show.columns]
    df_display = df_show[visible_cols] if visible_cols else df_show

    # Colour-code Action
    def _colour_action(val: str) -> str:
        colours = {
            "STRONG_BUY": "background-color:#004d1a; color:#00c851",
            "BUY":        "background-color:#002d40; color:#33b5e5",
            "WATCH":      "background-color:#3d3000; color:#ffbb33",
            "NO_ACTION":  "color:#888",
            "EXIT":       "background-color:#3d0000; color:#ff4444",
            "FORCED_EXIT":"background-color:#260000; color:#cc0000",
        }
        return colours.get(val, "")

    def _colour_verdict(val: str) -> str:
        return verdict_style(val)

    def _row_tint(row: pd.Series) -> list[str]:
        tint = verdict_row_tint(row.get("T+ Verdict", ""))
        return [tint] * len(row)

    df_display = filter_dataframe(df_display, key_prefix="scanner")

    visible_buy_like = int(df_display["Action"].isin(["STRONG_BUY", "BUY", "WATCH"]).sum()) if not df_display.empty else 0
    avg_mfpm_visible = float(df_display["MFPM"].mean()) if not df_display.empty and "MFPM" in df_display.columns else 0.0
    avg_tconf_visible = float(df_display["T+ Conf"].mean()) if not df_display.empty and "T+ Conf" in df_display.columns else 0.0
    scan_info_cols = st.columns(4)
    scan_info_cols[0].metric("Mã đang hiển thị", len(df_display), delta=f"/{len(df_all)} tổng")
    scan_info_cols[1].metric("Cơ hội buy/watch", visible_buy_like)
    scan_info_cols[2].metric("MFPM TB", f"{avg_mfpm_visible:.1f}")
    scan_info_cols[3].metric("T+ Conf TB", f"{avg_tconf_visible:.1f}%")

    if view_mode == "📋 Table":
        styled = (
            df_display.style
            .apply(_row_tint, axis=1)
            .map(_colour_action, subset=["Action"] if "Action" in df_display.columns else [])
            .map(_colour_verdict, subset=["T+ Verdict"] if "T+ Verdict" in df_display.columns else [])
        )
        scanner_config = {}
        if "Action" in df_display.columns:
            scanner_config["Action"] = st.column_config.TextColumn("Action")
        if "T+ Verdict" in df_display.columns:
            scanner_config["T+ Verdict"] = st.column_config.TextColumn("T+ Verdict")
        if "T+ Conf" in df_display.columns:
            scanner_config["T+ Conf"] = st.column_config.ProgressColumn("T+ Conf", format="%.0f", min_value=0, max_value=100)
        st.dataframe(styled, use_container_width=True, hide_index=True, column_config=scanner_config)
    else:
        # ── Card View ─────────────────────────────────────────────────────────
        _render_scan_cards_view(df_display)

    # ── Export ────────────────────────────────────────────────────────────────
    exp_col1, exp_col2 = st.columns(2)
    csv_bytes = df_display.to_csv(index=False).encode("utf-8-sig")
    exp_col1.download_button(
        "⬇️ Xuất CSV",
        data=csv_bytes,
        file_name="scan_results.csv",
        mime="text/csv",
    )
    # Copy as Markdown headline summary
    if not df_display.empty:
        buy_rows = df_display[df_display["Action"].isin(["STRONG_BUY", "BUY"])].head(10)
        if not buy_rows.empty:
            md_lines = [f"**TradingOS Scanner {datetime.now().strftime('%d/%m/%Y')}**\n"]
            for _, r in buy_rows.iterrows():
                icon = "🚀" if r.get("Action") == "STRONG_BUY" else "🟢"
                md_lines.append(
                    f"{icon} `{r.get('Mã','')}` {r.get('Action','')} | "
                    f"MFPM={r.get('MFPM',0):.0f} SMS={r.get('SMS',0):.0f} "
                    f"T+={r.get('T+ Verdict','')} | "
                    f"Giá {r.get('Giá',0):,.0f} → TP1 {r.get('TP1', r.get('T+ Conf',0)):,.0f}"
                )
            md_summary = "\n".join(md_lines)
            with exp_col2.expander("📋 Copy Markdown"):
                st.code(md_summary, language="markdown")

    # ── Inline NLP per high-priority result ──────────────────────────────────
    buy_items = [
        item for item in result.results
        if item.action in ("STRONG_BUY", "BUY", "WATCH")
        and item.ticker in df_display["Mã"].values
    ]
    if buy_items:
        st.divider()
        st.markdown("#### 📝 Tóm tắt tín hiệu — NLP")
        st.caption("Hiển thị tối đa 20 mã có tín hiệu STRONG_BUY / BUY / WATCH đầu tiên.")
        _action_icon = {"STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀"}
        for _i, item in enumerate(buy_items[:20]):
            headline = generate_summary_headline(
                ticker=item.ticker,
                action=item.action,
                mfpm_score=item.mfpm_score,
                signal_mode=item.signal_mode,
                rsi14=getattr(item, "rsi14", 50.0),
                sms_raw=item.sms_raw,
                stealth_accum=item.stealth_accum,
                best_pattern=item.best_pattern,
                distribution_warning=getattr(item, "distribution_warning", "NONE"),
                hmm_state=item.hmm_state,
            )
            icon = _action_icon.get(item.action, "📋")
            with st.expander(
                f"{icon} **{item.ticker}** — {item.action}  |  {headline}",
                expanded=False,
            ):
                col_l, col_r = st.columns([1, 1])
                with col_l:
                    st.markdown(f"**Giá:** {item.close:,.0f}")
                    st.markdown(f"**Vào lệnh:** {item.entry:,.0f}")
                    st.markdown(f"**Cắt lỗ:** {item.sl:,.0f}")
                    st.markdown(f"**TP1:** {item.tp1:,.0f}")
                    st.markdown(f"**R:R:** 1:{item.rr:.1f}")
                with col_r:
                    st.markdown(f"**Mode:** {item.signal_mode}")
                    st.markdown(f"**MFPM:** {item.mfpm_score}")
                    st.markdown(f"**SMS:** {item.sms_raw} ({item.sms_label})")
                    st.markdown(f"**HMM:** {item.hmm_state}")
                    st.markdown(f"**Pattern:** {item.best_pattern}")
                    st.markdown(f"**Stealth:** {'✅' if item.stealth_accum else '❌'}")
                if st.button(f"📈 Mở Profiler — {item.ticker}", key=f"nlp_open_{item.ticker}_{_i}"):
                    st.session_state["profiler_ticker"] = item.ticker
                    st.session_state["_nav_pending"] = "🔍 Profiler"
                    st.rerun()

    # ── Drill-down to profiler ────────────────────────────────────────────────
    st.divider()
    ticker_options = df_display["Mã"].tolist() if "Mã" in df_display.columns else []
    if ticker_options:
        selected = st.selectbox("Xem chi tiết mã:", ticker_options)
        if selected and st.button("📈 Mở Profiler", use_container_width=True):
            st.session_state["profiler_ticker"] = selected
            st.session_state["_nav_pending"] = "🔍 Profiler"
            st.rerun()


# ── Card View helper ──────────────────────────────────────────────────────────

def _render_scan_cards_view(df: pd.DataFrame) -> None:
    """Render scanner results as a 3-column card grid."""
    if df.empty:
        st.info("Không có kết quả.")
        return

    _ACOLOR = {
        "STRONG_BUY": "#22c55e",
        "BUY":        "#3b82f6",
        "WATCH":      "#f59e0b",
        "NO_ACTION":  "#64748b",
        "EXIT":       "#ef4444",
        "FORCED_EXIT":"#dc2626",
    }
    _VCOLOR = {
        "MUA_NGAY":     "#22c55e",
        "CHO_XAC_NHAN": "#f59e0b",
        "THEO_DOI":     "#3b82f6",
        "TRANH_XA":     "#ef4444",
    }
    _AICON = {
        "STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀",
        "NO_ACTION": "⏸", "EXIT": "🔴", "FORCED_EXIT": "⚠️",
    }

    cols = st.columns(3)
    for i, (_, row) in enumerate(df.iterrows()):
        ticker  = str(row.get("Mã", ""))
        action  = str(row.get("Action", ""))
        mfpm    = row.get("MFPM", 0) or 0
        sms     = row.get("SMS", 0) or 0
        verdict = str(row.get("T+ Verdict", "") or "")
        price   = row.get("Giá", 0) or 0
        entry   = row.get("Vào", 0) or 0
        sl_val  = row.get("SL", 0) or 0
        pattern = str(row.get("Pattern", "") or "")
        conf    = str(row.get("Conf", "") or "")

        ac  = _ACOLOR.get(action, "#64748b")
        vc  = _VCOLOR.get(verdict.upper(), "#64748b")
        ico = _AICON.get(action, "📋")

        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="border:1px solid {ac}44;border-radius:8px;padding:12px;
                            background:#0f172a;margin-bottom:8px;">
                  <div style="font-size:17px;font-weight:800;color:{ac};">{ico} {ticker}</div>
                  <div style="font-size:12px;color:#64748b;margin:2px 0;">{action} · {conf}</div>
                  <div style="display:flex;gap:10px;margin:6px 0;font-size:13px;">
                    <span>MFPM <b>{mfpm:.0f}</b></span>
                    <span>SMS <b>{sms:.0f}</b></span>
                  </div>
                  <span style="background:{vc}22;color:{vc};padding:1px 7px;
                               border-radius:8px;font-size:12px;">{verdict}</span>
                  {'&nbsp;<span style="color:#64748b;font-size:11px;">' + pattern + '</span>' if pattern else ''}
                  <div style="color:#94a3b8;font-size:12px;margin-top:6px;">
                    {f'{price:,.0f}' if price else '—'}
                    {f' → Entry {entry:,.0f}' if entry else ''}
                    {f' | SL {sl_val:,.0f}' if sl_val else ''}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("→ Profiler", key=f"card_profile_{ticker}_{i}", use_container_width=True):
                st.session_state["_nav_pending"] = "🔍 Profiler"
                st.session_state["profiler_ticker"] = ticker
                st.rerun()

