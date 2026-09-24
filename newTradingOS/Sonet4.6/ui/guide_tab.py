"""Guide tab renderer — reads docs/HUONG_DAN.md and renders in-app."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from ui.components import render_decision_panel, render_section_header

# Locate docs directory relative to this file:
# guide_tab.py → ui/ → Sonet4.6/ → docs/
_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
_ROOT_DIR = Path(__file__).resolve().parent.parent

_DOCS: dict[str, Path] = {
    "📖 Hướng dẫn sử dụng (VI)": _DOCS_DIR / "HUONG_DAN.md",
    "📋 Installation Guide (EN)": _ROOT_DIR / "GUIDE.md",
}


def _load_md(path: Path) -> str:
    if not path.exists():
        return f"_Không tìm thấy file: `{path.name}`_"
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"_Lỗi đọc file: {exc}_"


def _guide_quickstart(lang: str = "VI") -> list[dict[str, str]]:
    if lang == "VI":
        return [
            {
                "title": "1. Tải dữ liệu",
                "body": "Chọn watchlist hoặc universe phù hợp, sau đó tải giá để app có context review ban đầu.",
            },
            {
                "title": "2. Cập nhật macro",
                "body": "Nạp regime, macro score, foreign-flow và trust labels trước khi đánh giá tín hiệu.",
            },
            {
                "title": "3. Review tín hiệu",
                "body": "Bắt đầu từ Signal Review và Macro Pulse; chỉ mở diagnostics sâu khi cần xác minh thêm.",
            },
            {
                "title": "4. Validate hành động",
                "body": "Dùng ML, Backtest và Portfolio để kiểm tra forecast usage, độ robust và room rủi ro trước khi vào lệnh.",
            },
        ]
    return [
        {
            "title": "1. Load data",
            "body": "Choose a watchlist or universe first so every review workspace has current price context.",
        },
        {
            "title": "2. Refresh macro",
            "body": "Refresh macro to load regime, macro score, foreign flow, and trust labels before judging any signal.",
        },
        {
            "title": "3. Review signals",
            "body": "Start with Signal Review and Macro Pulse; only open deep diagnostics when you need more confirmation.",
        },
        {
            "title": "4. Validate action",
            "body": "Use ML, Backtest, and Portfolio to validate forecast usage, robustness, and risk room before acting.",
        },
    ]


def render_guide_tab(lang: str = "VI") -> None:
    """Render the full in-app documentation viewer."""

    render_section_header(
        "📖 Hướng Dẫn Sử Dụng" if lang == "VI" else "📖 User Guide",
        "Bắt đầu từ quick-start workflow trước, rồi mới mở full reference khi cần tra cứu chi tiết.",
    )
    render_decision_panel(
        "Quick start",
        "Tải dữ liệu -> cập nhật macro -> review -> validate trước khi hành động"
        if lang == "VI"
        else "Load data -> refresh macro -> review -> validate before acting",
        "Guide tab ưu tiên onboarding nhanh; tài liệu đầy đủ vẫn nằm phía dưới để tra cứu sâu."
        if lang == "VI"
        else "The guide starts with onboarding; the full reference remains below for deeper lookup.",
        metrics=[
            (
                "Primary flow" if lang != "VI" else "Luồng chính",
                "Guided review",
                "Macro + Signal Review first",
            ),
            (
                "Decision mode" if lang != "VI" else "Decision mode",
                "Trust-first",
                "Read provenance before conviction",
            ),
            (
                "Advanced tools" if lang != "VI" else "Công cụ sâu",
                "ML | Backtest | Portfolio",
                "Validate before sizing",
            ),
        ],
        tone="info",
    )

    cards = _guide_quickstart(lang)
    st.subheader("🚀 Quick Start" if lang != "VI" else "🚀 Bắt Đầu Nhanh")
    cols = st.columns(2)
    for index, card in enumerate(cards):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{card['title']}**")
                st.caption(card["body"])

    # ── Document selector + search ───────────────────────────────────────────
    st.divider()
    col_sel, col_search = st.columns([3, 2])
    with col_sel:
        selected = st.selectbox(
            "Tài liệu" if lang == "VI" else "Document",
            options=list(_DOCS.keys()),
            index=0,
            key="guide_tab_doc_select",
        )
    with col_search:
        search_term = st.text_input(
            "🔍 Tìm kiếm" if lang == "VI" else "🔍 Search",
            placeholder="RSI, MACD, stop-loss...",
            key="guide_tab_search",
        ).strip().lower()

    content = _load_md(_DOCS[selected])

    # ── Search results ────────────────────────────────────────────────────────
    if search_term:
        lines = content.split("\n")
        matched = [
            (i + 1, line)
            for i, line in enumerate(lines)
            if search_term in line.lower()
        ]
        if matched:
            st.success(f"✅ Tìm thấy **{len(matched)}** kết quả cho `{search_term}`")
            with st.expander("Xem kết quả", expanded=True):
                for lineno, line in matched[:25]:
                    clean = line.strip()
                    if not clean:
                        continue
                    # Bold the search term (case-insensitive)
                    import re
                    highlighted = re.sub(
                        f"({re.escape(search_term)})",
                        r"**\1**",
                        clean,
                        flags=re.IGNORECASE,
                    )
                    st.markdown(f"> *Dòng {lineno}:* {highlighted}")
            st.divider()
        else:
            st.warning(f"Không tìm thấy `{search_term}` trong tài liệu này.")

    # ── Table of contents ─────────────────────────────────────────────────────
    h2_headings = [
        line.lstrip("# ").strip()
        for line in content.split("\n")
        if line.startswith("## ")
    ]
    if h2_headings:
        with st.expander("📋 Mục lục" if lang == "VI" else "📋 Table of Contents", expanded=False):
            cols = st.columns(2)
            half = (len(h2_headings) + 1) // 2
            for i, h in enumerate(h2_headings):
                cols[0 if i < half else 1].markdown(f"- {h}")

    st.divider()

    # ── Main content ──────────────────────────────────────────────────────────
    with st.expander(
        "📚 Full reference document" if lang != "VI" else "📚 Tài liệu tham chiếu đầy đủ",
        expanded=bool(search_term),
    ):
        st.markdown(content, unsafe_allow_html=False)

    # ── Download ──────────────────────────────────────────────────────────────
    st.divider()
    dl_col, info_col = st.columns([1, 3])
    with dl_col:
        st.download_button(
            label="⬇️ Tải xuống (.md)",
            data=content.encode("utf-8"),
            file_name=_DOCS[selected].name,
            mime="text/markdown",
            key="guide_tab_download",
        )
    with info_col:
        st.caption(f"📄 `{_DOCS[selected].relative_to(_ROOT_DIR)}`")
