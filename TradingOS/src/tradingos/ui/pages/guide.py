"""Guide page — renders HUONG_DAN.md and BUSINESS_LOGIC.md in-app."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

# Paths relative to the TradingOS project root
_DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"
_ROOT_DIR = Path(__file__).resolve().parents[4]

_DOCS = {
    "📖 Hướng dẫn sử dụng": _DOCS_DIR / "HUONG_DAN.md",
    "🧠 Business Logic": _ROOT_DIR / "BUSINESS_LOGIC.md",
    "📋 README": _ROOT_DIR / "README.md",
}


def _load_md(path: Path) -> str:
    if not path.exists():
        return f"_Không tìm thấy file: `{path}`_"
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"_Lỗi đọc file: {exc}_"


def render() -> None:
    st.title("📖 Tài liệu & Hướng dẫn")

    # ── Document selector ────────────────────────────────────────────────────
    col_sel, col_search = st.columns([3, 2])
    with col_sel:
        selected = st.selectbox(
            "Chọn tài liệu",
            options=list(_DOCS.keys()),
            index=0,
            key="guide_doc_select",
        )
    with col_search:
        search_term = st.text_input(
            "🔍 Tìm trong tài liệu",
            placeholder="Nhập từ khoá...",
            key="guide_search",
        ).strip().lower()

    st.divider()

    # ── Load content ─────────────────────────────────────────────────────────
    content = _load_md(_DOCS[selected])

    # ── Search highlight ─────────────────────────────────────────────────────
    if search_term:
        lines = content.split("\n")
        matched = [
            (i + 1, line)
            for i, line in enumerate(lines)
            if search_term in line.lower()
        ]
        if matched:
            st.success(f"Tìm thấy **{len(matched)}** kết quả cho `{search_term}`:")
            with st.expander("Xem kết quả tìm kiếm", expanded=True):
                for lineno, line in matched[:30]:
                    # Highlight the search term
                    highlighted = line.replace(
                        search_term,
                        f"**{search_term}**",
                    ).replace(
                        search_term.upper(),
                        f"**{search_term.upper()}**",
                    ).replace(
                        search_term.capitalize(),
                        f"**{search_term.capitalize()}**",
                    )
                    st.markdown(f"*Dòng {lineno}:* {highlighted}")
            st.divider()
        else:
            st.warning(f"Không tìm thấy `{search_term}` trong tài liệu này.")

    # ── Table of contents (extract headings) ─────────────────────────────────
    headings = [
        line.strip()
        for line in content.split("\n")
        if line.startswith("## ")
    ]
    if headings:
        with st.expander("📋 Mục lục nhanh", expanded=False):
            for h in headings:
                label = h.lstrip("# ").strip()
                st.markdown(f"- {label}")

    st.divider()

    # ── Render the markdown ───────────────────────────────────────────────────
    st.markdown(content, unsafe_allow_html=False)

    # ── Footer ───────────────────────────────────────────────────────────────
    st.divider()
    st.caption(f"📄 Nguồn: `{_DOCS[selected]}`")
    if st.button("⬇️ Tải xuống tài liệu", key="guide_download"):
        st.download_button(
            label="Tải file .md",
            data=content.encode("utf-8"),
            file_name=_DOCS[selected].name,
            mime="text/markdown",
        )
