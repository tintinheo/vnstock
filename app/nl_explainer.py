"""
nl_explainer.py — Natural Language Explanation for T+ Recommendations
═══════════════════════════════════════════════════════════════════════
Gọi Groq API (llama-3.1-8b-instant) để sinh giải thích tiếng Việt
cho nhà đầu tư F0. Tự động fallback sang template-based nếu Groq lỗi.

Usage:
    from nl_explainer import generate_nl_explanation
    explanation = generate_nl_explanation(r_dict, rec_dict)
"""

import os
import json
import logging

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass  # python-dotenv not installed — rely on env vars set externally

try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False

logger = logging.getLogger(__name__)

_GROQ_MODEL = "llama-3.1-8b-instant"
_GROQ_TEMPERATURE = 0.3
_GROQ_MAX_TOKENS = 700

# ─── Score component label maps ───────────────────────────────────────────────

_T25_LABELS = {
    "T25_BUY":     ("Mô hình T+2.5 xác nhận MUA mạnh", 40, 40),
    "T25_WATCH":   ("Mô hình T+2.5 đang theo dõi, chưa xác nhận hẳn", 25, 40),
    "T25_NEUTRAL": ("Mô hình T+2.5 ở trạng thái trung tính", 10, 40),
    "T25_AVOID":   ("Mô hình T+2.5 cảnh báo TRÁNH vào lệnh", 0, 40),
}

_REGIME_LABELS = {
    "BULL_TREND": ("Xu hướng tăng rõ ràng", 20, 20),
    "SIDEWAYS":   ("Thị trường đang đi ngang (sideway)", 12, 20),
    "HIGH_VOL":   ("Biến động cao bất thường", 8, 20),
    "UNKNOWN":    ("Chưa xác định xu hướng rõ ràng", 8, 20),
    "BEAR_TREND": ("Xu hướng giảm — rủi ro cao khi mua", 3, 20),
}

_ACTION_GUIDANCE = {
    "STRONG_BUY": (
        "**Đây là cơ hội mua tốt nhất theo mô hình.** "
        "Bạn có thể xem xét vào lệnh trong phiên hôm nay (ưu tiên khung 10:00–11:30 "
        "hoặc 13:30–14:00), với tỷ lệ vốn theo gợi ý sizing. "
        "Nhớ đặt lệnh cắt lỗ ngay khi khớp lệnh mua."
    ),
    "BUY": (
        "**Tín hiệu mua khá tốt.** "
        "Có thể vào lệnh hôm nay nếu giá dao động trong vùng entry gợi ý. "
        "Đặt cắt lỗ theo mức SL và không mở vị thế quá lớn hơn sizing đề xuất."
    ),
    "WATCH": (
        "**Tín hiệu chưa đủ mạnh để vào lệnh ngay hôm nay.** "
        "Theo dõi thêm 1–2 phiên tới. Nếu phiên sau tiếp tục tăng với khối lượng lớn "
        "(≥0.8× trung bình 20 phiên), xem xét lại."
    ),
    "SKIP": (
        "**Hiện tại không phải thời điểm thích hợp để mua.** "
        "Tín hiệu còn yếu hoặc chưa có xác nhận. "
        "Hãy để mã này vào danh sách theo dõi (watchlist) và kiểm tra lại vào phiên sau."
    ),
    "AVOID": (
        "**Không nên mua mã này lúc này.** "
        "Rủi ro đang cao hơn cơ hội. Bạn không cần làm gì — "
        "hãy giữ tiền mặt và chờ tín hiệu rõ ràng hơn ở một mã khác."
    ),
}


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_prompt(r: dict, rec: dict) -> str:
    """Build the Groq chat prompt from profiler + recommendation data."""
    ticker  = r.get("ticker", "N/A")
    price   = r.get("price", 0)
    pct     = r.get("pct_change", 0) or 0
    action  = rec.get("action", "AVOID")
    grade   = rec.get("grade", "E")
    score   = rec.get("confidence_score", 0)
    t25     = r.get("t25_signal", "T25_NEUTRAL")
    regime  = r.get("regime", "UNKNOWN")
    bull    = r.get("bull_pct", 50) or 50
    vsa     = r.get("vsa_state", "NEUTRAL")
    rsi     = r.get("rsi", 50) or 50
    rsi_div = r.get("rsi_divergence", "NONE")
    confirmed = r.get("signal_confirmed", False)
    bt5wr   = r.get("bt5_win_rate", 0) or 0
    rs      = r.get("rs_rating", 50) or 50
    sigs    = rec.get("supporting_signals", [])
    flags   = rec.get("risk_flags", [])
    entry_l = rec.get("entry_zone_low")
    entry_h = rec.get("entry_zone_high")
    sl      = rec.get("sl_price")
    tp1     = rec.get("tp1_price")
    tp2     = rec.get("tp2_price")
    rr      = rec.get("rr_ratio")
    size    = rec.get("position_size_pct", 0)
    timing  = rec.get("entry_timing", "")
    vwap_d  = r.get("vwap_divergence", "NONE")
    candle  = r.get("candle_talib_pattern") or r.get("candle_pattern", "NEUTRAL")

    data_payload = {
        "mã_cổ_phiếu": ticker,
        "giá_hiện_tại": f"{price:,.0f} ({pct:+.1f}%)" if price else "N/A",
        "khuyến_nghị": action,
        "điểm_tổng": f"{score}/100",
        "xếp_loại": grade,
        "tín_hiệu_T25": t25,
        "xu_hướng": regime,
        "momentum_bull_pct": f"{bull:.0f}%",
        "VSA": vsa,
        "RSI": f"{rsi:.1f}",
        "RSI_phân_kỳ": rsi_div,
        "xác_nhận_tín_hiệu": "Đã xác nhận 2/3 phiên" if confirmed else "Chưa xác nhận",
        "VWAP_phân_kỳ": vwap_d,
        "mẫu_nến": candle,
        "RS_rating": rs,
        "lịch_sử_bt5_winrate": f"{bt5wr:.0f}%",
        "tín_hiệu_ủng_hộ": sigs,
        "cờ_rủi_ro": flags,
        "vùng_vào_lệnh": f"{entry_l:,.0f}–{entry_h:,.0f}" if entry_l and entry_h else "N/A",
        "cắt_lỗ_SL": f"{sl:,.0f}" if sl else "N/A",
        "mục_tiêu_TP1": f"{tp1:,.0f}" if tp1 else "N/A",
        "mục_tiêu_TP2": f"{tp2:,.0f}" if tp2 else "N/A",
        "tỷ_lệ_RR": f"{rr:.2f}:1" if rr else "N/A",
        "sizing_vốn": f"{size:.1f}%",
        "thời_điểm_vào": timing,
    }

    system_prompt = (
        "Bạn là chuyên gia phân tích chứng khoán Việt Nam giàu kinh nghiệm, "
        "chuyên giải thích kết quả phân tích kỹ thuật cho nhà đầu tư mới (F0) "
        "bằng ngôn ngữ đơn giản, dễ hiểu. "
        "Tránh dùng thuật ngữ kỹ thuật nếu không cần — nếu có thì giải thích ngắn gọn. "
        "Giọng văn thân thiện, trung thực, không hype. "
        "Luôn nhắc rằng kết quả chỉ mang tính tham khảo, không phải tư vấn đầu tư chính thức."
    )

    user_prompt = f"""Dưới đây là dữ liệu phân tích kỹ thuật của mã **{ticker}** từ hệ thống VN-Swing Alpha:

```json
{json.dumps(data_payload, ensure_ascii=False, indent=2)}
```

Hãy viết một giải thích đầy đủ bằng tiếng Việt theo đúng 6 phần sau (dùng định dạng Markdown với tiêu đề **in đậm**):

**1. Kết luận** — 1–2 câu tóm tắt kết quả và lý do chính mà F0 cần biết ngay.

**2. Tại sao điểm này?** — Giải thích score {score}/100 dựa vào 4 yếu tố: (a) tín hiệu T25 = {t25}, (b) momentum bull_pct = {bull:.0f}%, (c) xu hướng thị trường = {regime}, (d) cấu trúc giá/VSA/nến. Mỗi yếu tố giải thích 1–2 câu bằng từ ngữ thông thường.

**3. Tín hiệu ủng hộ** — Giải thích từng tín hiệu trong danh sách {sigs} có nghĩa là gì với F0 (1 câu mỗi tín hiệu). Nếu danh sách rỗng, ghi "Không có tín hiệu ủng hộ đáng kể."

**4. Rủi ro cần lưu ý** — Giải thích từng cờ rủi ro trong {flags} tại sao nguy hiểm với ngôn ngữ dễ hiểu (1 câu mỗi cờ). Nếu rỗng, ghi "Không có rủi ro đặc biệt nào được phát hiện."

**5. Kế hoạch giao dịch** — Viết thành câu văn tự nhiên (không phải bullet list): nếu mua thì vào vùng nào, đặt cắt lỗ ở đâu (tức giảm bao nhiêu % so với giá hiện tại), mục tiêu lấy lời TP1/TP2 ở đâu, tỷ lệ rủi ro/lợi nhuận là bao nhiêu, và nên dùng bao nhiêu % vốn cho lệnh này.

**6. Bạn nên làm gì?** — 2–3 câu hướng dẫn hành động cụ thể nhất có thể dựa trên khuyến nghị **{action}**. Nếu là AVOID, hãy nói rõ tại sao nên tránh và khi nào thì xem xét lại.

Kết thúc bằng dòng: *⚠️ Giải thích này được sinh tự động bởi AI và chỉ mang tính tham khảo. Không phải tư vấn đầu tư chính thức.*"""

    return system_prompt, user_prompt


# ─── Template fallback ────────────────────────────────────────────────────────

def _template_fallback(r: dict, rec: dict) -> str:
    """Template-based explanation — used when Groq call fails."""
    ticker  = r.get("ticker", "N/A")
    action  = rec.get("action", "AVOID")
    grade   = rec.get("grade", "E")
    score   = rec.get("confidence_score", 0)
    t25     = r.get("t25_signal", "T25_NEUTRAL")
    regime  = r.get("regime", "UNKNOWN")
    bull    = float(r.get("bull_pct", 50) or 50)
    vsa     = r.get("vsa_state", "NEUTRAL")
    rsi     = float(r.get("rsi", 50) or 50)
    confirmed = r.get("signal_confirmed", False)
    bt5wr   = float(r.get("bt5_win_rate", 0) or 0)
    sigs    = rec.get("supporting_signals", [])
    flags   = rec.get("risk_flags", [])
    sl      = rec.get("sl_price")
    tp1     = rec.get("tp1_price")
    tp2     = rec.get("tp2_price")
    rr      = rec.get("rr_ratio")
    size    = rec.get("position_size_pct", 0)
    price   = float(r.get("price", 0) or 0)

    t25_label, t25_pts, t25_max = _T25_LABELS.get(t25, ("Trung tính", 10, 40))
    reg_label, reg_pts, reg_max = _REGIME_LABELS.get(regime, ("Không rõ xu hướng", 8, 20))
    guidance = _ACTION_GUIDANCE.get(action, _ACTION_GUIDANCE["AVOID"])

    conf_txt = "Tín hiệu đã được xác nhận qua 2/3 phiên liên tiếp." if confirmed else "Tín hiệu **chưa được xác nhận** qua 2/3 phiên — rủi ro cao hơn."

    # Score breakdown
    if bull >= 65:   b_pts, b_desc = 30, "momentum rất mạnh"
    elif bull >= 55: b_pts, b_desc = 20, "momentum khá tốt"
    elif bull >= 50: b_pts, b_desc = 10, "momentum trung bình"
    else:            b_pts, b_desc = 0,  "momentum yếu"
    if confirmed:    b_pts = min(30, b_pts + 5)

    # Signals
    sig_lines = ""
    if sigs:
        for s in sigs:
            sig_lines += f"- **{s}**\n"
    else:
        sig_lines = "- Không có tín hiệu ủng hộ đáng kể.\n"

    # Risk flags
    flag_lines = ""
    if flags:
        for f in flags:
            flag_lines += f"- ⚠️ {f}\n"
    else:
        flag_lines = "- Không có rủi ro đặc biệt nào được phát hiện.\n"

    # Trade plan sentence
    trade_plan = ""
    if sl and price > 0:
        sl_pct = abs(price - float(sl)) / price * 100
        trade_plan += f"Đặt cắt lỗ tại **{sl:,.0f}** (−{sl_pct:.1f}% so với giá hiện tại). "
    if tp1:
        trade_plan += f"Mục tiêu TP1: **{tp1:,.0f}**. "
    if tp2:
        trade_plan += f"TP2: **{tp2:,.0f}**. "
    if rr:
        trade_plan += f"Tỷ lệ rủi ro/lợi nhuận: **{rr:.2f}:1**. "
    if size and size > 0:
        trade_plan += f"Gợi ý dùng tối đa **{size:.1f}% vốn** cho lệnh này."
    if not trade_plan:
        trade_plan = "Không có kế hoạch giao dịch cụ thể — không nên vào lệnh ở thời điểm này."

    lines = [
        "> ⚠️ LLM calling error, template-based is used.",
        "",
        f"**1. Kết luận**",
        f"Mã **{ticker}** được xếp loại **{action}** (Grade {grade}, điểm {score}/100). "
        f"{t25_label} và {reg_label.lower()}.",
        "",
        f"**2. Tại sao điểm này?**",
        f"- T+2.5 signal ({t25}): {t25_label} — {t25_pts}/{t25_max} điểm",
        f"- Momentum (bull_pct={bull:.0f}%): {b_desc} — {b_pts}/30 điểm",
        f"- Xu hướng ({regime}): {reg_label} — {reg_pts}/{reg_max} điểm",
        f"- VSA={vsa}, RSI={rsi:.1f}. {conf_txt}",
        "",
        f"**3. Tín hiệu ủng hộ**",
        sig_lines.rstrip(),
        "",
        f"**4. Rủi ro cần lưu ý**",
        flag_lines.rstrip(),
        "",
        f"**5. Kế hoạch giao dịch**",
        trade_plan,
        "",
        f"**6. Bạn nên làm gì?**",
        guidance,
        "",
        f"*⚠️ Giải thích này được sinh tự động và chỉ mang tính tham khảo. "
        f"Không phải tư vấn đầu tư chính thức.*",
    ]
    return "\n".join(lines)


# ─── Main entry point ─────────────────────────────────────────────────────────

def generate_nl_explanation(r: dict, rec: dict) -> str:
    """
    Generate a Vietnamese natural-language explanation of a T+ recommendation.

    Calls Groq llama-3.1-8b-instant. On any failure (no API key, network error,
    quota exceeded, timeout) automatically falls back to template-based output
    prefixed with a warning line.

    Args:
        r:   Full analyse_ticker result dict.
        rec: T+ recommendation dict from generate_t_plus_recommendation().

    Returns:
        Markdown string — 6-section Vietnamese explanation for F0 investors.
    """
    if not _GROQ_AVAILABLE:
        logger.warning("nl_explainer: groq package not installed — using template fallback")
        return _template_fallback(r, rec)

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("nl_explainer: GROQ_API_KEY not set — using template fallback")
        return _template_fallback(r, rec)

    try:
        client = Groq(api_key=api_key)
        system_prompt, user_prompt = _build_prompt(r, rec)
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=_GROQ_TEMPERATURE,
            max_tokens=_GROQ_MAX_TOKENS,
        )
        text = response.choices[0].message.content.strip()
        if not text:
            raise ValueError("Empty response from Groq")
        return text
    except Exception as exc:
        logger.warning("nl_explainer: Groq call failed (%s) — using template fallback", exc)
        fallback = _template_fallback(r, rec)
        # Prepend specific error context to the warning already in template
        return fallback.replace(
            "> ⚠️ LLM calling error, template-based is used.",
            f"> ⚠️ LLM calling error ({type(exc).__name__}), template-based is used.",
            1,
        )
