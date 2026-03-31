"""Advisory NLP — Template-based bilingual signal text (SRS §3.8, Module 7)."""
from __future__ import annotations

from ..utils.config import cfg


# ── Action → signal text ──────────────────────────────────────────────────────

_ACTION_VI = {
    "STRONG_BUY":   "📈 Tín hiệu MUA MẠNH",
    "BUY":          "🟢 Tín hiệu MUA",
    "WATCH":        "👀 THEO DÕI – cân nhắc vào",
    "NO_ACTION":    "⏸ Không hành động",
    "EXIT":         "🔴 Phân phối – THOÁT dần",
    "FORCED_EXIT":  "⚠️ THOÁT NGAY",
}
_ACTION_EN = {
    "STRONG_BUY":   "📈 STRONG BUY signal",
    "BUY":          "🟢 BUY signal",
    "WATCH":        "👀 WATCH – consider entry",
    "NO_ACTION":    "⏸ No action",
    "EXIT":         "🔴 Distribution – reduce position",
    "FORCED_EXIT":  "⚠️ EXIT IMMEDIATELY",
}

_CONFIDENCE_VI = {
    "HIGH":   "Độ tin cậy CAO",
    "MEDIUM": "Độ tin cậy TRUNG BÌNH",
    "LOW":    "Độ tin cậy THẤP",
    "—":      "",
}

_MODE_VI = {
    "MODE_W": "Whale Follow",
    "MODE_A": "Pullback",
    "MODE_B": "Breakout",
}


def generate_signal_text(
    ticker: str,
    action: str,
    confidence: str,
    mfpm_score: int,
    mode_w_score: int,
    sms_raw: int,
    hmm_state: str,
    signal_mode: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    rr: float,
    mc_prob: float,
    distribution_warning: str,
    mode_w_conditions_failed: list[str] | None = None,
    lang: str = "vi",
) -> str:
    """
    Generate a narrative advisory text in Vietnamese or English.
    Returns markdown string.
    """
    action_text = (_ACTION_VI if lang == "vi" else _ACTION_EN).get(action, action)
    conf_text = _CONFIDENCE_VI.get(confidence, confidence)
    mode_text = _MODE_VI.get(signal_mode, signal_mode)

    sms_band = (
        "Cá mập đang gom mạnh" if sms_raw >= 75
        else "Dòng tiền thông minh tích cực" if sms_raw >= 60
        else "Hỗn hợp (cẩn trọng)" if sms_raw >= 40
        else "Không có dòng tiền lớn"
    )

    dist_note = {
        "NONE":        "",
        "WATCH":       "\n> ⚠️ Phân phối mức WATCH — theo dõi chặt.",
        "CAUTION":     "\n> 🔶 Phân phối mức CAUTION — hạn chế vào mới.",
        "EXIT":        "\n> 🔴 Phân phối mức EXIT — đang thoát dần.",
        "FORCED_EXIT": "\n> ‼️ Phân phối FORCED EXIT — thoát toàn bộ ngay.",
    }.get(distribution_warning, "")

    fail_lines = ""
    if mode_w_conditions_failed:
        fail_lines = "\n**Mode W chưa đạt:**\n" + "\n".join(f"- {f}" for f in mode_w_conditions_failed)

    if lang == "vi":
        text = f"""### {action_text} — **{ticker}**
> {conf_text} | Mode: **{mode_text}** | MFPM: {mfpm_score}/120{dist_note}

| Chỉ số | Giá trị |
|--------|---------|
| MFPM Score | {mfpm_score} |
| Mode W Score | {mode_w_score} |
| SMS Raw | {sms_raw} |
| Thị trường (HMM) | {hmm_state.replace('_', ' ')} |
| Xác suất thắng MC | {mc_prob:.0%} |

**Giá giao dịch**
- Vào lệnh: **{entry:,.0f}** đ  
- Cắt lỗ: **{sl:,.0f}** đ  
- Chốt T1: **{tp1:,.0f}** đ &nbsp;|&nbsp; Chốt T2: **{tp2:,.0f}** đ  
- RR: **1:{rr:.1f}**

**Phân tích dòng tiền:** {sms_band}
{fail_lines}
> *TradingOS Advisory Only — không phải khuyến nghị đầu tư.*"""
    else:
        text = f"""### {action_text} — **{ticker}**
> Confidence: {confidence} | Mode: {mode_text} | Score: {mfpm_score}/120{dist_note}

| Indicator | Value |
|-----------|-------|
| MFPM Score | {mfpm_score} |
| Mode W Score | {mode_w_score} |
| SMS Raw | {sms_raw} |
| Market HMM | {hmm_state.replace('_', ' ')} |
| MC Win Prob | {mc_prob:.0%} |

**Trade Levels**
- Entry: **{entry:,.0f}** VND  
- Stop-loss: **{sl:,.0f}** VND  
- TP1: **{tp1:,.0f}** &nbsp;|&nbsp; TP2: **{tp2:,.0f}** VND  
- R:R = 1:{rr:.1f}

**Smart Money:** {sms_band}
{fail_lines}
> *Advisory only — not investment advice.*"""

    return text.strip()


def generate_exit_advisory_text(
    ticker: str,
    action: str,
    urgency: str,
    reason: str,
    exit_pct: float,
    exit_window: str,
    lang: str = "vi",
) -> str:
    """Generate exit advisory narrative."""
    if lang == "vi":
        return (
            f"**{ticker}** — {action.replace('_', ' ')} ({urgency})\n"
            f"- Lý do: {reason}\n"
            f"- Tỷ lệ thoát: {exit_pct:.0%}\n"
            f"- Cửa sổ khuyến nghị: **{exit_window}**\n"
            "> *Chỉ mang tính tư vấn.*"
        )
    else:
        return (
            f"**{ticker}** — {action.replace('_', ' ')} ({urgency})\n"
            f"- Reason: {reason}\n"
            f"- Exit fraction: {exit_pct:.0%}\n"
            f"- Recommended window: **{exit_window}**\n"
            "> *Advisory only.*"
        )
