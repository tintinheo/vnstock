"""Advisory NLP — Template-based bilingual signal text (SRS §3.8, Module 7).

Three signal modes explained (used throughout advisory text):

  MODE_A — Pullback: giá hồi về vùng hỗ trợ SMA20/SMA50 sau xu hướng tăng,
            RSI phục hồi qua ngưỡng 50 → vào điểm kỹ thuật rủi ro thấp.

  MODE_B — Breakout: giá phá vỡ đỉnh pivot kèm volume đột biến. Second Mouse
            Gate xác nhận nếu có retest thành công (về đỉnh cũ → hồi phục).

  MODE_W — Follow-the-Whale: SMS ≥ ngưỡng + M-CVD tăng liên tục + stealth
            accumulation → tổ chức đang âm thầm tích lũy. Tín hiệu mạnh nhất.
"""
from __future__ import annotations

from ..utils.config import cfg


# ── Static lookup tables ──────────────────────────────────────────────────────

_ACTION_VI = {
    "STRONG_BUY":  "📈 TÍN HIỆU MUA MẠNH",
    "BUY":         "🟢 TÍN HIỆU MUA",
    "WATCH":       "👀 THEO DÕI — cân nhắc vào lệnh",
    "NO_ACTION":   "⏸ Không có tín hiệu",
    "EXIT":        "🔴 Phân phối — giảm / thoát dần",
    "FORCED_EXIT": "⚠️ THOÁT NGAY — ưu tiên cao nhất",
}

_CONFIDENCE_VI = {
    "HIGH":   "🟢 Độ tin cậy CAO",
    "MEDIUM": "🟡 Độ tin cậy TRUNG BÌNH",
    "LOW":    "🔴 Độ tin cậy THẤP",
    "—":      "⚪ —",
}

_MODE_LABEL_VI = {
    "MODE_W": "🐳 Whale Follow (Mode W)",
    "MODE_A": "↩️ Pullback (Mode A)",
    "MODE_B": "🚀 Breakout (Mode B)",
    "—":      "—",
}

_MODE_EXPLAIN_VI = {
    "MODE_A": (
        "**Mode A — Pullback (Vào điểm hồi về hỗ trợ)**\n"
        "Hệ thống phát hiện giá đang trong xu hướng tăng (trên SMA50) và vừa hồi về "
        "vùng SMA20 — vùng hỗ trợ động cổ điển của swing trading. "
        "RSI phục hồi qua ngưỡng 50 xác nhận lực mua đang quay trở lại sau đợt điều chỉnh. "
        "Đây là điểm vào rủi ro thấp nhất trong chu kỳ tăng."
    ),
    "MODE_B": (
        "**Mode B — Breakout (Phá vỡ đỉnh pivot)**\n"
        "Giá vừa phá vỡ ngưỡng kháng cự / đỉnh pivot quan trọng kèm khối lượng đột biến — "
        "dấu hiệu tổ chức / dòng tiền lớn đang đẩy giá. "
        "Second Mouse Gate được kiểm tra: nếu giá kéo về vùng đỉnh cũ trên khối lượng thấp "
        "rồi hồi phục, đây là điểm vào lý tưởng (second mouse gets the cheese). "
        "Nếu chưa retest, rủi ro mua đuổi cao hơn."
    ),
    "MODE_W": (
        "**Mode W — Follow-the-Whale (Theo dòng tiền tổ chức)**\n"
        "SMS và M-CVD nhiều ngày liên tiếp cho thấy một hoặc nhiều tổ chức lớn đang âm thầm "
        "tích lũy cổ phiếu (stealth accumulation). "
        "Đây là tín hiệu mạnh nhất — khi cá mập vào trước, giá thường tăng bền hơn và "
        "ít bị stop-loss hơn so với breakout thông thường. "
        "Cần pass đủ 7 điều kiện W-1…W-7 mới kích hoạt."
    ),
    "—": "",
}

_AMD_VI = {
    "ACCUMULATION": "📦 Tích lũy — tổ chức đang âm thầm gom hàng",
    "MARKUP":       "📈 Markup — xu hướng tăng được xác nhận",
    "DISTRIBUTION": "📤 Phân phối — tổ chức đang xả hàng",
    "MARKDOWN":     "📉 Markdown — xu hướng giảm",
    "RANGING":      "↔️ Đi ngang — chưa có xu hướng rõ ràng",
}

_HMM_VI = {
    "STEADY_BULL":  "🟢 Tăng ổn định — HMM xác nhận bull market",
    "TRENDING_UP":  "🟢 Đang có xu hướng tăng",
    "TRANSITIONAL": "🟡 Đang chuyển tiếp — thận trọng",
    "RANGING":      "🟡 Dao động ngang — chờ xác nhận",
    "STEADY_BEAR":  "🔴 Xu hướng giảm — tránh mua mới",
    "TRENDING_DOWN":"🔴 Đang giảm",
}

_DIST_VI = {
    "NONE":        None,
    "WATCH":       "⚠️ Cảnh báo phân phối nhẹ — theo dõi volume chặt hơn.",
    "CAUTION":     "🔶 Phân phối rõ ràng — hạn chế vào mới, cân nhắc chốt lời từng phần.",
    "EXIT":        "🔴 Phân phối mạnh — nên giảm tỷ trọng.",
    "FORCED_EXIT": "‼️ Phân phối cực mạnh — thoát toàn bộ, ưu tiên cao nhất.",
}

_PATTERN_VI = {
    "VCP":             "📐 VCP (Volatility Contraction Pattern) — biên độ co hẹp dần, sắp bùng nổ",
    "CUP_WITH_HANDLE": "☕ Cup-with-Handle — tích lũy hình chén, rủi ro thấp khi phá đỉnh",
    "WYCKOFF_SPRING":  "🌱 Wyckoff Spring — giá chạm đáy hỗ trợ rồi hồi nhanh trên volume thấp",
    "RSI_DIV_BULLISH": "📊 RSI Divergence tăng — giá tạo đáy thấp hơn nhưng RSI cao hơn → lực giảm đang cạn",
    "FVG":             "🕳️ Fair Value Gap — vùng trống giá, xu hướng lấp đầy",
    "ORDER_BLOCK":     "🧱 Order Block — vùng tổ chức đặt lệnh lớn, hỗ trợ/kháng cự mạnh",
}

_AMF_VI = {
    "PASS":  "✅ Không phát hiện thao túng",
    "WARN":  "⚠️ Có dấu hiệu bất thường nhỏ",
    "BLOCK": "🚫 Phát hiện thao túng — TÍN HIỆU BỊ CHẶN",
}


def _sms_text(sms_raw: int) -> str:
    if sms_raw >= 80:
        return "🐳 Cá mập đang gom CỰC MẠNH — tín hiệu hiếm gặp"
    if sms_raw >= 65:
        return "🐳 Dòng tiền thông minh TÍCH CỰC rõ ràng"
    if sms_raw >= 45:
        return "🟡 Dòng tiền hỗn hợp — có tổ chức quan tâm nhưng chưa quyết định"
    if sms_raw >= 25:
        return "⚪ Dòng tiền bình thường — chủ yếu retail"
    return "❄️ Không có dòng tiền lớn — cổ phiếu đang bị bỏ qua"


def _score_bar(score: int, max_score: int = 120, width: int = 18) -> str:
    filled = round(score / max(max_score, 1) * width)
    filled = min(filled, width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score}/{max_score}"


# ── Decision gate thresholds (mirrors mfpm.py defaults) ──────────────────────
_BUY_MFPM       = 70
_WATCH_MFPM     = 50
_MC_BUY         = 0.55
_MC_STRONG_BUY  = 0.60
_MODE_W_STRONG  = 95
_MODE_W_BUY     = 80
_MODE_W_WATCH   = 60


def generate_gate_explanation(
    ticker: str,
    action: str,
    mfpm_score: int,
    mode_a_score: int,
    mode_b_score: int,
    mode_w_score: int,
    signal_mode: str,
    mc_prob: float,
    distribution_warning: str,
    amf_decision: str,
    hmm_state: str,
    amd_phase: str,
    rsi14: float,
    sms_raw: int,
    mcvd_trend: str,
    stealth_accum: bool,
    pt_net_5d: float,
    close: float,
    mode_w_conditions_failed: list[str] | None = None,
) -> str:
    """
    Return plain-Vietnamese gate diagnostic: which decision gates
    passed/failed and what is needed to upgrade the signal.
    Mirrors the exact gate order in mfpm.py Layer 2.
    """
    lines: list[str] = []

    # ── Gate 0: Distribution warning override ────────────────────────────────
    if distribution_warning in ("EXIT", "FORCED_EXIT"):
        severity = "MẠNH (FORCED_EXIT)" if distribution_warning == "FORCED_EXIT" else "rõ ràng"
        lines.append(
            f"🔴 **Phân phối {severity} đã phát hiện** — override tất cả các cổng khác, "
            "bất kể MFPM hay MC cao đến đâu."
        )
        lines.append(
            "📌 Tín hiệu sẽ chuyển thành BUY/WATCH khi `distribution_warning` quay về `NONE` "
            "hoặc `WATCH` và MFPM đủ ngưỡng."
        )
        return "\n\n".join(lines)

    # ── Gate 1: AMF (Anti-Manipulation Filter) ───────────────────────────────
    if amf_decision == "BLOCK":
        lines.append(
            "🚫 **AMF bị chặn (BLOCK)** — hệ thống phát hiện dấu hiệu thao túng giá. "
            "Tín hiệu bị vô hiệu hoá để bảo vệ vốn."
        )
        lines.append(
            "📌 Tín hiệu sẽ phục hồi khi AMF = PASS (pattern thao túng biến mất)."
        )
        return "\n\n".join(lines)

    # ── Gate paths split by signal_mode ──────────────────────────────────────
    if signal_mode == "MODE_W":
        _gate_explain_mode_w(
            lines, action, mode_w_score, mc_prob,
            mode_w_conditions_failed or [],
        )
    else:
        _gate_explain_mode_ab(
            lines, action, mfpm_score, signal_mode,
            mode_a_score, mode_b_score, amf_decision, mc_prob,
            hmm_state, rsi14,
        )

    # ── Upgrade hint ─────────────────────────────────────────────────────────
    upgrade = _upgrade_hint(
        action, signal_mode, mfpm_score, mode_w_score,
        amf_decision, mc_prob, distribution_warning,
    )
    if upgrade:
        lines.append(upgrade)

    return "\n\n".join(lines)


def _gate_explain_mode_w(
    lines: list[str],
    action: str,
    w: int,
    mc_prob: float,
    w_fails: list[str],
) -> None:
    """Append gate pass/fail lines for MODE_W path."""
    lines.append(
        "🐳 **Đang chạy Mode W (Follow-the-Whale)** — tín hiệu dựa trên điểm số W và MC."
    )

    # W-score gates
    w_gate_strong = _check("W-Score", w, _MODE_W_STRONG)
    w_gate_buy    = _check("W-Score", w, _MODE_W_BUY)
    w_gate_watch  = _check("W-Score", w, _MODE_W_WATCH)

    if action == "STRONG_BUY":
        lines.append(
            f"✅ W-Score = **{w}** ≥ {_MODE_W_STRONG} → STRONG_BUY mở\n"
            f"✅ MC Win Prob = **{mc_prob:.0%}** ≥ {_MC_STRONG_BUY:.0%} → MC PASS\n"
            f"✅ AMF = PASS"
        )
    elif action == "BUY":
        lines.append(
            f"✅ W-Score = **{w}** ≥ {_MODE_W_BUY} → BUY đủ điều kiện\n"
            + (f"❌ W-Score < {_MODE_W_STRONG} → chưa đủ STRONG_BUY" if w < _MODE_W_STRONG else "")
        )
        if mc_prob < _MC_STRONG_BUY:
            lines.append(
                f"❌ MC Win Prob = **{mc_prob:.0%}** < {_MC_STRONG_BUY:.0%} "
                "→ chưa đủ STRONG_BUY (cần ≥ 60%)"
            )
    elif action == "WATCH":
        lines.append(
            f"✅ W-Score = **{w}** ≥ {_MODE_W_WATCH} → WATCH mở\n"
            f"❌ W-Score < {_MODE_W_BUY} → chưa đủ BUY (cần ≥ {_MODE_W_BUY})\n"
            f"📌 MC Win Prob hiện tại: **{mc_prob:.0%}**"
        )
    else:  # NO_ACTION
        lines.append(
            f"❌ W-Score = **{w}** < {_MODE_W_WATCH} → chưa đạt ngưỡng WATCH tối thiểu\n"
            f"📌 Cần W-Score ≥ {_MODE_W_WATCH} để vào WATCH."
        )

    if w_fails:
        fail_items = "\n".join(f"  - {f}" for f in w_fails)
        lines.append(f"📋 **Điều kiện Mode W chưa đạt:**\n{fail_items}")


def _gate_explain_mode_ab(
    lines: list[str],
    action: str,
    mfpm_score: int,
    signal_mode: str,
    mode_a_score: int,
    mode_b_score: int,
    amf_decision: str,
    mc_prob: float,
    hmm_state: str,
    rsi14: float,
) -> None:
    """Append gate pass/fail lines for MODE_A / MODE_B path."""
    mode_label = "Mode A (Pullback)" if signal_mode == "MODE_A" else "Mode B (Breakout)"
    active_score = mode_a_score if signal_mode == "MODE_A" else mode_b_score
    lines.append(f"↩️ **Đang chạy {mode_label}** — điểm base = {active_score}/60.")

    mfpm_buy_gate  = mfpm_score >= _BUY_MFPM
    amf_gate       = amf_decision == "PASS"
    mc_gate        = mc_prob >= _MC_BUY
    mfpm_watch_gate = mfpm_score >= _WATCH_MFPM

    if action in ("BUY", "STRONG_BUY"):
        lines.append(
            f"✅ MFPM = **{mfpm_score}** ≥ {_BUY_MFPM} → vượt ngưỡng BUY\n"
            f"✅ AMF = **PASS**\n"
            f"✅ MC Win Prob = **{mc_prob:.0%}** ≥ {_MC_BUY:.0%}"
        )
    elif action == "WATCH":
        gate_rows: list[str] = []
        if mfpm_buy_gate:
            gate_rows.append(f"✅ MFPM = **{mfpm_score}** ≥ {_BUY_MFPM}")
        else:
            gate_rows.append(
                f"❌ MFPM = **{mfpm_score}** < {_BUY_MFPM} "
                f"(cần thêm **{_BUY_MFPM - mfpm_score} điểm** để đạt BUY)"
            )
        if amf_gate:
            gate_rows.append("✅ AMF = PASS")
        else:
            gate_rows.append("❌ AMF ≠ PASS → chặn BUY")
        if mc_gate:
            gate_rows.append(f"✅ MC Win Prob = **{mc_prob:.0%}** ≥ {_MC_BUY:.0%}")
        else:
            gate_rows.append(
                f"❌ MC Win Prob = **{mc_prob:.0%}** < {_MC_BUY:.0%} "
                f"(cần ≥ {_MC_BUY:.0%} — thường thấp ở cổ phiếu vốn hoá nhỏ / ATR lớn)"
            )
        gate_rows.append(f"✅ MFPM ≥ {_WATCH_MFPM} → WATCH kích hoạt")
        lines.append("\n".join(gate_rows))

        # Explain why MC is low if that's the bottleneck
        if not mc_gate and mfpm_buy_gate and amf_gate:
            lines.append(
                f"💡 **Bottleneck: xác suất thắng MC = {mc_prob:.0%}**.  \n"
                "MC thấp thường do: (1) tỷ lệ R:R dưới 1.5, (2) ATR lớn so với giá → "
                "SL quá rộng → Kelly penalty cao.  \n"
                "Tín hiệu sẽ lên BUY khi MC ≥ 55% (R:R cải thiện hoặc giá vào rõ hơn)."
            )
    else:  # NO_ACTION
        lines.append(
            f"❌ MFPM = **{mfpm_score}** < {_WATCH_MFPM} → chưa đạt WATCH tối thiểu\n"
            f"📌 RSI hiện tại: {rsi14:.1f} | HMM: {hmm_state}"
        )


def _check(label: str, value: int | float, threshold: int | float) -> bool:
    """Return True if value >= threshold."""
    return value >= threshold


def _upgrade_hint(
    action: str,
    signal_mode: str,
    mfpm_score: int,
    mode_w_score: int,
    amf_decision: str,
    mc_prob: float,
    distribution_warning: str,
) -> str:
    """Single-line summary of what is needed to upgrade to the next level."""
    if distribution_warning in ("EXIT", "FORCED_EXIT"):
        return ""
    if action == "STRONG_BUY":
        return "🏆 **Tín hiệu tốt nhất có thể — không cần cải thiện thêm.**"
    if action == "BUY":
        if signal_mode == "MODE_W":
            needed = _MODE_W_STRONG - mode_w_score
            return (
                f"⬆️ **Để lên STRONG_BUY:** W-Score cần thêm **{needed} điểm** "
                f"(hiện {mode_w_score}/{_MODE_W_STRONG}) VÀ MC ≥ 60%."
            ) if needed > 0 else f"⬆️ **Để lên STRONG_BUY:** MC cần ≥ 60% (hiện {mc_prob:.0%})."
        else:
            return "⬆️ **Tín hiệu BUY đã đủ mạnh trong Mode A/B.**"
    if action == "WATCH":
        if signal_mode == "MODE_W":
            needed = _MODE_W_BUY - mode_w_score
            return (
                f"⬆️ **Để lên BUY:** W-Score cần thêm **{needed} điểm** "
                f"(hiện {mode_w_score}/{_MODE_W_BUY})."
            )
        else:
            bottlenecks: list[str] = []
            if mfpm_score < _BUY_MFPM:
                bottlenecks.append(f"MFPM +{_BUY_MFPM - mfpm_score} điểm (hiện {mfpm_score})")
            if amf_decision != "PASS":
                bottlenecks.append("AMF cần PASS")
            if mc_prob < _MC_BUY:
                bottlenecks.append(f"MC ≥ {_MC_BUY:.0%} (hiện {mc_prob:.0%})")
            if bottlenecks:
                return "⬆️ **Để lên BUY cần:** " + " | ".join(bottlenecks)
    return ""


# ── Main NLP generator ────────────────────────────────────────────────────────

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
    # Extended context (optional — enables richer explanation)
    mode_a_score: int = 0,
    mode_b_score: int = 0,
    amd_phase: str = "RANGING",
    best_pattern: str = "NONE",
    amf_decision: str = "PASS",
    stealth_accum: bool = False,
    stealth_confidence: str = "LOW",
    mcvd_trend: str = "FLAT",
    mcvd_5d: float = 0.0,
    pt_net_5d: float = 0.0,
    rsi14: float = 50.0,
    close: float = 0.0,
    lang: str = "vi",
) -> str:
    """
    Generate a full natural-language advisory explaining WHY.
    Covers: which mode was activated, what drove the score,
    market context (AMD/HMM), money flow, pattern, entry/exit levels.
    Returns a markdown string (Vietnamese).
    """
    action_text  = _ACTION_VI.get(action, action)
    conf_text    = _CONFIDENCE_VI.get(confidence, confidence)
    mode_label   = _MODE_LABEL_VI.get(signal_mode, signal_mode)
    mode_explain = _MODE_EXPLAIN_VI.get(signal_mode, "")
    dist_msg     = _DIST_VI.get(distribution_warning)
    amf_text     = _AMF_VI.get(amf_decision, amf_decision)
    amd_text     = _AMD_VI.get(amd_phase, amd_phase)
    hmm_text     = _HMM_VI.get(hmm_state, hmm_state.replace("_", " "))
    sms_band     = _sms_text(sms_raw)

    # ── Score breakdown ───────────────────────────────────────────────────
    score_bar = _score_bar(mfpm_score, 120)
    if signal_mode == "MODE_W":
        score_lines = (
            f"- **Mode W Score: {mode_w_score} / 115** ← mode đang chạy\n"
            f"- Mode A Score: {mode_a_score} / 60 &nbsp;|&nbsp; Mode B Score: {mode_b_score} / 60\n"
            f"- MFPM tổng: `{score_bar}`"
        )
    elif signal_mode == "MODE_B":
        score_lines = (
            f"- **Mode B Score: {mode_b_score} / 60** ← mode đang chạy\n"
            f"- Mode A Score: {mode_a_score} / 60\n"
            f"- Mode W Score: {mode_w_score} / 115 (chưa đủ điều kiện)\n"
            f"- MFPM tổng: `{score_bar}`"
        )
    else:
        score_lines = (
            f"- **Mode A Score: {mode_a_score} / 60** ← mode đang chạy\n"
            f"- Mode B Score: {mode_b_score} / 60\n"
            f"- Mode W Score: {mode_w_score} / 115 (chưa đủ điều kiện)\n"
            f"- MFPM tổng: `{score_bar}`"
        )

    # ── Mode W fail conditions ────────────────────────────────────────────
    w_fail_block = ""
    if mode_w_conditions_failed:
        items = "\n".join(f"  - {f}" for f in mode_w_conditions_failed)
        w_fail_block = f"\n> 📋 **Mode W chưa kích hoạt** vì các điều kiện sau chưa đạt:\n{items}\n"

    # ── No-action / exit reason ───────────────────────────────────────────
    if action == "NO_ACTION":
        min_watch = cfg.strategy("mfpm", "min_score_buy", default=50)
        reason_block = (
            f"\n**Tại sao không có tín hiệu?**\n"
            f"- MFPM {mfpm_score}/120 chưa đạt ngưỡng WATCH ({min_watch})\n"
            f"- {hmm_text}\n"
            f"- RSI hiện tại: {rsi14:.1f}\n"
            f"- {amf_text}\n"
        )
    elif action in ("EXIT", "FORCED_EXIT"):
        reason_block = (
            f"\n**Tại sao cần thoát?**\n"
            f"- {dist_msg or 'Phân phối phát hiện'}\n"
            f"- {hmm_text}\n"
            f"- {amf_text}\n"
        )
    else:
        reason_block = ""

    # ── Stealth note ──────────────────────────────────────────────────────
    stealth_note = ""
    if stealth_accum:
        stealth_note = (
            f"\n🔍 **Stealth Accumulation** phát hiện (độ tin cậy: **{stealth_confidence}**) "
            "— tổ chức đang gom âm thầm nhiều phiên liên tiếp."
        )

    # ── Put-through note ──────────────────────────────────────────────────
    pt_note = ""
    if pt_net_5d > 5_000_000_000:
        pt_note = (
            f"\n📦 **Giao dịch thoả thuận (Put-through) 5 phiên: +{pt_net_5d/1e9:.1f} tỷ VND** "
            "— tổ chức đang mua số lượng lớn qua khớp thoả thuận."
        )
    elif pt_net_5d < -5_000_000_000:
        pt_note = (
            f"\n📦 **Put-through net 5 phiên: {pt_net_5d/1e9:.1f} tỷ VND** "
            "— tổ chức đang xả hàng qua thoả thuận."
        )

    # ── M-CVD note ────────────────────────────────────────────────────────
    mcvd_icon = "📈" if mcvd_trend == "UP" else ("📉" if mcvd_trend == "DOWN" else "↔️")
    mcvd_note = f"{mcvd_icon} M-CVD xu hướng **{mcvd_trend}** (5 phiên: {mcvd_5d:+,.0f} cp)"

    # ── Pattern note ──────────────────────────────────────────────────────
    pat_note = ""
    if best_pattern and best_pattern not in ("NONE", ""):
        pat_note = f"\n🖼️ **Pattern phát hiện:** {_PATTERN_VI.get(best_pattern, best_pattern)}"

    # ── Distribution warning block ────────────────────────────────────────
    dist_block = f"\n> ⚡ {dist_msg}\n" if dist_msg else ""

    # ── Trade levels ──────────────────────────────────────────────────────
    if entry > 0:
        sl_pct  = (sl - entry) / max(entry, 1) * 100
        tp1_pct = (tp1 - entry) / max(entry, 1) * 100
        trade_block = (
            f"| | Giá (VND) | % so với vào |\n"
            f"|---|---|---|\n"
            f"| 📍 Giá hiện tại | **{close:,.0f}** | — |\n"
            f"| 🟢 Vào lệnh | **{entry:,.0f}** | — |\n"
            f"| 🔴 Cắt lỗ | **{sl:,.0f}** | `{sl_pct:+.1f}%` |\n"
            f"| 🎯 Chốt lời T1 | **{tp1:,.0f}** | `{tp1_pct:+.1f}%` |\n"
            f"| 🎯 Chốt lời T2 | **{tp2:,.0f}** | — |\n"
            f"| ⚖️ R:R | **1:{rr:.1f}** | |\n"
            f"| 🎲 Xác suất thắng MC | **{mc_prob:.0%}** | |\n"
        )
    else:
        trade_block = "_Chưa đủ điều kiện xác định mức giá vào lệnh._"

    text = f"""### {action_text} — **{ticker}**

> {conf_text} &nbsp;|&nbsp; {mode_label} &nbsp;|&nbsp; MFPM: `{score_bar}`
{dist_block}
---

#### 📖 Giải thích tín hiệu

{mode_explain}
{w_fail_block}{reason_block}
---

#### 📊 Chi tiết điểm số

{score_lines}

---

#### 🌡️ Bối cảnh thị trường

| Yếu tố | Đánh giá |
|---|---|
| Chu kỳ AMD | {amd_text} |
| Trạng thái HMM | {hmm_text} |
| Lọc thao túng (AMF) | {amf_text} |
| Dòng tiền SMS={sms_raw} | {sms_band} |
| {mcvd_note} | |
{stealth_note}{pt_note}{pat_note}

---

#### 💰 Giá giao dịch đề xuất

{trade_block}

---

> ⚠️ *TradingOS chỉ mang tính tư vấn — không phải khuyến nghị đầu tư. Nhà đầu tư tự chịu trách nhiệm quyết định giao dịch.*"""

    # ── Gate explanation block ────────────────────────────────────────────
    gate_explain = generate_gate_explanation(
        ticker=ticker,
        action=action,
        mfpm_score=mfpm_score,
        mode_a_score=mode_a_score,
        mode_b_score=mode_b_score,
        mode_w_score=mode_w_score,
        signal_mode=signal_mode,
        mc_prob=mc_prob,
        distribution_warning=distribution_warning,
        amf_decision=amf_decision,
        hmm_state=hmm_state,
        amd_phase=amd_phase,
        rsi14=rsi14,
        sms_raw=sms_raw,
        mcvd_trend=mcvd_trend,
        stealth_accum=stealth_accum,
        pt_net_5d=pt_net_5d,
        close=close,
        mode_w_conditions_failed=mode_w_conditions_failed,
    )
    if gate_explain:
        text = text + f"\n\n---\n\n#### 🔎 Tại sao lại là **{action}**?\n\n{gate_explain}"

    return text.strip()


# ── Exit advisory ─────────────────────────────────────────────────────────────

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
    urgency_vi = {"HIGH": "🔴 Cao", "MEDIUM": "🟡 Trung bình", "LOW": "🟢 Thấp"}.get(urgency, urgency)
    if lang == "vi":
        return (
            f"**{ticker}** — {action.replace('_', ' ')} (Urgency: {urgency_vi})\n"
            f"- Lý do: {reason}\n"
            f"- Tỷ lệ thoát: **{exit_pct:.0%}**\n"
            f"- Cửa sổ khuyến nghị: **{exit_window}**\n"
            "> *Chỉ mang tính tư vấn.*"
        )
    return (
        f"**{ticker}** — {action.replace('_', ' ')} (Urgency: {urgency})\n"
        f"- Reason: {reason}\n"
        f"- Exit fraction: {exit_pct:.0%}\n"
        f"- Recommended window: **{exit_window}**\n"
        "> *Advisory only.*"
    )


# ── Indicator-level NLP ───────────────────────────────────────────────────────

_RSI_TIERS = [
    (30,          "📊 **RSI {rsi:.0f}** — vùng **quá bán** mạnh: áp lực bán đang kiệt sức. "
                  "Xác suất hồi phục kỹ thuật cao — theo dõi tín hiệu đảo chiều."),
    (45,          "📊 **RSI {rsi:.0f}** — vùng **yếu / hồi phục**: momentum đang xây lại từ đáy. "
                  "Đây là điểm khởi đầu chu kỳ tăng Mode A nếu giá đang trên SMA50."),
    (55,          "📊 **RSI {rsi:.0f}** — vùng **trung tính**: momentum chưa có xu hướng rõ. "
                  "Chờ RSI vượt 55 để xác nhận xung lực tăng."),
    (70,          "📊 **RSI {rsi:.0f}** — vùng **mạnh**: momentum đang tích cực. "
                  "Xu hướng tăng được xác nhận, có thể tiếp diễn."),
    (float("inf"),"📊 **RSI {rsi:.0f}** — vùng **quá mua**: áp lực chốt lời cao. "
                  "Tránh mua đuổi — chờ RSI điều chỉnh về 60–65 trước khi vào mới."),
]


def generate_indicator_explanation(
    rsi14: float,
    close: float,
    sma20: float,
    sma50: float,
    sma200: float,
    atr14: float,
    volume: float,
    avg_volume_20d: float,
    macd: float = 0.0,
) -> list[str]:
    """Return plain-Vietnamese NLP bullet points explaining each technical indicator.

    Used in the Profiler 'Chỉ số' tab and anywhere indicator values are displayed.
    """
    insights: list[str] = []

    # ── RSI ──────────────────────────────────────────────────────────────────
    for threshold, template in _RSI_TIERS:
        if rsi14 <= threshold:
            insights.append(template.format(rsi=rsi14))
            break

    # ── SMA position ─────────────────────────────────────────────────────────
    if close > 0:
        if sma200 > 0:
            rel200 = (close - sma200) / sma200 * 100
            if close >= sma200:
                insights.append(
                    f"📈 **Xu hướng dài hạn (SMA200)**: Giá trên SMA200 ({sma200:,.0f}) "
                    f"+{rel200:.1f}% → uptrend dài hạn còn nguyên ✅"
                )
            else:
                insights.append(
                    f"📉 **Xu hướng dài hạn (SMA200)**: Giá dưới SMA200 ({sma200:,.0f}) "
                    f"{rel200:.1f}% → thận trọng với vị thế dài hạn ⚠️"
                )

        if sma50 > 0:
            rel50 = (close - sma50) / sma50 * 100
            if close > sma50:
                insights.append(
                    f"✅ **Trên SMA50** (+{rel50:.1f}%): điều kiện cần cho T+ swing trading. "
                    "Mua hồi về SMA20 là điểm vào rủi ro thấp nhất."
                )
            else:
                insights.append(
                    f"⚠️ **Dưới SMA50** ({rel50:.1f}%): chưa đủ điều kiện xu hướng tăng. "
                    "Chờ giá tái chinh phục SMA50 trước khi tham gia mua."
                )

        if sma20 > 0 and sma50 > 0 and abs(close - sma20) / max(sma20, 1) < 0.025:
            insights.append(
                f"↩️ **Hồi về SMA20** ({sma20:,.0f}): vùng hỗ trợ động cổ điển — "
                "đây là điểm vào lý tưởng của Mode A (Pullback)."
            )

    # ── Volume ───────────────────────────────────────────────────────────────
    if avg_volume_20d > 0:
        vr = volume / avg_volume_20d
        if vr >= 3.0:
            insights.append(
                f"🔊 **Khối lượng {vr:.1f}× bình thường** — dòng tiền lớn đột biến. "
                "Xác nhận hướng giá trước khi hành động."
            )
        elif vr >= 1.5:
            insights.append(
                f"📢 **Khối lượng tăng {vr:.1f}×** — dòng tiền đang tham gia. "
                "Tín hiệu có độ tin cậy tốt hơn khi khối lượng cao."
            )
        elif vr < 0.5:
            insights.append(
                f"🔇 **Khối lượng thấp ({vr:.1f}×)** — thiếu sự quan tâm từ dòng tiền lớn. "
                "Mọi tín hiệu cần xác nhận thêm trước khi vào lệnh."
            )
        else:
            insights.append(
                f"🔁 **Khối lượng bình thường ({vr:.1f}×)** — không có dòng tiền bất thường."
            )

    # ── ATR (volatility) ─────────────────────────────────────────────────────
    if close > 0 and atr14 > 0:
        atr_pct = atr14 / close * 100
        if atr_pct >= 5.0:
            insights.append(
                f"⚡ **Biến động cao (ATR = {atr_pct:.1f}% giá / {atr14:,.0f} VND)** — "
                "cỡ vị thế nên nhỏ hơn; SL rộng hơn để tránh bị dừng sớm."
            )
        elif atr_pct >= 2.5:
            insights.append(
                f"📐 **Biến động bình thường (ATR = {atr_pct:.1f}% / {atr14:,.0f} VND)** — "
                "TradingOS tính SL và TP theo bội số ATR mặc định."
            )
        else:
            insights.append(
                f"🟢 **Biến động thấp (ATR = {atr_pct:.1f}% / {atr14:,.0f} VND)** — "
                "cổ phiếu ổn định, ít bị stop-loss, phù hợp đầu tư trung dài hạn."
            )

    return insights


# ── Scanner one-liner NLP ─────────────────────────────────────────────────────

_MODE_SHORT = {
    "MODE_A": "↩️ Pullback",
    "MODE_B": "🚀 Breakout",
    "MODE_W": "🐳 Whale Follow",
}

_PATTERN_SHORT = {
    "VCP":             "📐 VCP",
    "CUP_WITH_HANDLE": "☕ Cup&Handle",
    "WYCKOFF_SPRING":  "🌱 Wyckoff Spring",
    "RSI_DIV_BULLISH": "📊 RSI Div↑",
    "FVG":             "🕳️ FVG",
    "ORDER_BLOCK":     "🧱 OB",
}

_HMM_EMOJI = {
    "STEADY_BULL": "🟢", "TRENDING_UP": "🟢",
    "TRANSITIONAL": "🟡", "RANGING": "🟡",
    "STEADY_BEAR": "🔴", "TRENDING_DOWN": "🔴",
}


def generate_summary_headline(
    ticker: str,
    action: str,
    mfpm_score: int,
    signal_mode: str,
    rsi14: float = 50.0,
    sms_raw: int = 0,
    stealth_accum: bool = False,
    best_pattern: str = "NONE",
    distribution_warning: str = "NONE",
    hmm_state: str = "RANGING",
) -> str:
    """Single-line Vietnamese summary for scanner table or card subtitle.

    Returns a compact, emoji-annotated string describing the most important
    signal drivers without duplicating the full generate_signal_text() output.
    """
    if distribution_warning in ("EXIT", "FORCED_EXIT"):
        return (
            f"⚠️ Phân phối {'cực mạnh' if distribution_warning == 'FORCED_EXIT' else 'rõ ràng'} "
            f"→ cân nhắc thoát. Tránh mua mới (MFPM {mfpm_score})."
        )

    mode_label = _MODE_SHORT.get(signal_mode, signal_mode)
    parts: list[str] = [f"{mode_label} | MFPM {mfpm_score}"]

    if stealth_accum:
        parts.append("🔍 Stealth Accum")
    if sms_raw >= 65:
        parts.append(f"🐳 SMS {sms_raw}")
    if best_pattern and best_pattern not in ("NONE", ""):
        parts.append(_PATTERN_SHORT.get(best_pattern, best_pattern))
    if rsi14 < 35:
        parts.append(f"RSI {rsi14:.0f} quá bán ✅")
    elif rsi14 > 70:
        parts.append(f"RSI {rsi14:.0f} quá mua ⚠️")

    hmm_emoji = _HMM_EMOJI.get(hmm_state, "⚪")
    parts.append(f"{hmm_emoji} {hmm_state.replace('_', ' ')}")

    return " | ".join(parts)


# ── F0 Beginner Mode explanation ──────────────────────────────────────────────

_ACTION_F0 = {
    "STRONG_BUY":  "🚀 MUA MẠNH",
    "BUY":         "🟢 MUA",
    "WATCH":       "👀 THEO DÕI",
    "NO_ACTION":   "⏸ CHƯA CÓ TÍN HIỆU",
    "EXIT":        "🔴 CÂN NHẮC THOÁT",
    "FORCED_EXIT": "⚠️ THOÁT NGAY",
}

_SCORE_TIERS_F0 = [
    (30,          "rất yếu — chưa có tín hiệu đủ mạnh"),
    (50,          "yếu — cần quan sát thêm"),
    (70,          "trung bình — có cơ hội nhưng chưa lý tưởng"),
    (90,          "mạnh — đây là tín hiệu đáng chú ý"),
    (float("inf"),"rất mạnh — cơ hội tốt nhất hệ thống có thể ghi nhận"),
]

_MODE_F0_EXPLAIN = {
    "MODE_A": (
        "↩️ **Chiến lược: Mua điểm hồi về (Pullback)**\n\n"
        "Cổ phiếu đang trong xu hướng tăng. Giá hồi về vùng hỗ trợ (đường MA20) — "
        "đây là điểm vào rủi ro thấp nhất trong một chu kỳ tăng. "
        "Hình dung như đợi xe bus giảm tốc rồi nhảy lên, thay vì chạy đuổi theo."
    ),
    "MODE_B": (
        "🚀 **Chiến lược: Mua điểm phá vỡ (Breakout)**\n\n"
        "Giá vừa phá vỡ vùng kháng cự quan trọng kèm khối lượng lớn — "
        "dấu hiệu dòng tiền lớn đang đẩy giá lên tầm cao mới. "
        "*Rủi ro cần lưu ý:* nếu không có đủ xác nhận, giá có thể bị 'giả vỡ' (false breakout) và quay lại."
    ),
    "MODE_W": (
        "🐳 **Chiến lược: Theo dòng tiền tổ chức (Follow-the-Whale)**\n\n"
        "Hệ thống phát hiện quỹ đầu tư / tổ chức lớn đang âm thầm mua vào. "
        "Khi 'cá mập' vào trước, giá thường tăng bền và ít bị dừng lỗ hơn các tín hiệu khác. "
        "Đây là tín hiệu **mạnh nhất** mà TradingOS có thể đưa ra."
    ),
    "—": "Hệ thống chưa xác định được chiến lược phù hợp cho cổ phiếu này.",
}

_PATTERN_F0_EXPLAIN = {
    "VCP": (
        "📐 **VCP (Biên độ thu hẹp dần):** Qua nhiều đợt điều chỉnh, biên độ "
        "giá co hẹp dần — tích luỹ lực bùng nổ. Mark Minervini gọi đây là "
        "setup lý tưởng trước breakout."
    ),
    "CUP_WITH_HANDLE": (
        "☕ **Cup-with-Handle (Chén + Tay cầm):** Mẫu hình tích lũy dài hạn. "
        "Khi giá phá đỉnh 'miệng chén' với khối lượng lớn — upside rất mạnh."
    ),
    "WYCKOFF_SPRING": (
        "🌱 **Wyckoff Spring:** Giá chạm đáy hỗ trợ rồi bật lại nhanh trên "
        "khối lượng thấp — tổ chức đang hấp thụ áp lực bán cuối cùng trước khi đẩy giá."
    ),
    "RSI_DIV_BULLISH": (
        "📊 **RSI Divergence tăng:** Giá tạo đáy thấp hơn nhưng RSI tạo đáy "
        "cao hơn — lực giảm đang cạn kiệt, xu hướng sắp đảo chiều tăng."
    ),
    "FVG": (
        "🕳️ **Fair Value Gap:** Có vùng 'lỗ hổng giá' do di chuyển nhanh. "
        "Thị trường thường quay lại lấp đầy vùng này."
    ),
    "ORDER_BLOCK": (
        "🧱 **Order Block:** Vùng tổ chức đã từng đặt lệnh lớn. "
        "Khi giá quay về vùng này, tổ chức thường mua lại — hỗ trợ/kháng cự mạnh."
    ),
}


def _f0_score_interpret(score: int) -> str:
    for threshold, text in _SCORE_TIERS_F0:
        if score <= threshold:
            return text
    return "rất mạnh"


def _f0_upgrade_advice(
    action: str,
    signal_mode: str,
    mfpm_score: int,
    mode_w_score: int,
    mc_win_prob: float,
    amf_decision: str,
    distribution_warning: str,
    hmm_state: str,
) -> str:
    """Section 6: concrete recommendation + upgrade criteria for F0 investors."""
    if action == "FORCED_EXIT":
        return (
            "**→ THOÁT NGAY**\n\n"
            "Phân phối cực mạnh đang diễn ra. Nếu đang nắm giữ cổ phiếu này, "
            "ưu tiên **bán toàn bộ ngay trong phiên hôm nay** để bảo toàn vốn. "
            "Quay lại xem xét khi tín hiệu phân phối biến mất và điểm MFPM tái tạo trên 50.\n\n"
            "📌 **Tín hiệu mua sẽ xuất hiện trở lại khi:**\n"
            "  - Không còn dấu hiệu phân phối (Distribution = NONE)\n"
            "  - Điểm MFPM phục hồi trên 50\n"
            "  - Thị trường chung ổn định trở lại (HMM = TRANSITIONAL hoặc cao hơn)"
        )

    if action == "EXIT":
        return (
            "**→ Giảm tỷ trọng dần**\n\n"
            "Có dấu hiệu tổ chức đang bán ra. Nếu đang nắm giữ, nên "
            "**chốt lời 50–70%** và giữ phần nhỏ còn lại với stop loss chặt. "
            "⛔ Không mua thêm.\n\n"
            "📌 **Tín hiệu mua mạnh hơn sẽ xuất hiện khi:**\n"
            "  - Dấu hiệu phân phối biến mất (Distribution = NONE hoặc WATCH)\n"
            "  - Điểm MFPM tái tạo trên 50\n"
            "  - Thị trường chung chuyển sang tăng (HMM = TRENDING_UP)"
        )

    if action == "STRONG_BUY":
        return (
            "**→ Đây là tín hiệu tốt nhất** 🏆\n\n"
            "Tất cả điều kiện đều được đáp ứng. "
            "Có thể **thực hiện mua theo kế hoạch bên dưới** với tỷ trọng đầy đủ. "
            "Đặt lệnh trong cửa sổ thời gian khuyến nghị và tuân thủ nghiêm stop loss — "
            "đây là điều quan trọng nhất để bảo vệ vốn."
        )

    if action == "BUY":
        if signal_mode == "MODE_W":
            needed = max(0, 95 - mode_w_score)
            upgrade = (
                f"  - Điểm W-Score tăng thêm **{needed} điểm** nữa (hiện {mode_w_score}/115)\n"
                f"  - Xác suất thắng MC đạt ≥ 60% (hiện {mc_win_prob:.0%})"
            ) if needed > 0 else f"  - Xác suất thắng MC đạt ≥ 60% (hiện {mc_win_prob:.0%})"
        else:
            upgrade = "  - Tín hiệu BUY trong Mode A/B đã tối ưu — không cần thêm điều kiện"
        return (
            "**→ Có thể mua** với tỷ trọng vừa phải\n\n"
            "Tín hiệu đã đủ mạnh. Mua theo kế hoạch bên dưới với **50–75% tỷ trọng** "
            "bình thường của bạn. Quản lý rủi ro chặt — đặt stop loss ngay khi mua.\n\n"
            f"📌 **Để tín hiệu nâng lên STRONG_BUY:**\n{upgrade}"
        )

    if action == "WATCH":
        bottlenecks: list[str] = []
        if signal_mode == "MODE_W":
            needed = max(0, 80 - mode_w_score)
            if needed > 0:
                bottlenecks.append(f"Điểm W-Score tăng thêm **{needed} điểm** (hiện {mode_w_score}/115)")
        else:
            if mfpm_score < 70:
                bottlenecks.append(f"Điểm MFPM tăng thêm **{70 - mfpm_score} điểm** (hiện {mfpm_score}/120)")
            if amf_decision != "PASS":
                bottlenecks.append("Bộ lọc thao túng (AMF) cần = PASS — tín hiệu giao dịch bất thường cần biến mất")
            if mc_win_prob < 0.55:
                bottlenecks.append(
                    f"Xác suất thắng Monte Carlo cần ≥ 55% (hiện {mc_win_prob:.0%}) — "
                    "thường cải thiện khi R:R tốt hơn hoặc ATR giảm"
                )
        upgrade_list = "\n".join(f"  - {b}" for b in bottlenecks) if bottlenecks else "  - Chờ thêm tín hiệu xác nhận từ phiên kế tiếp"
        return (
            "**→ Chưa mua, theo dõi chặt**\n\n"
            "Tín hiệu đang hình thành nhưng chưa đủ mạnh để vào lệnh an toàn. "
            "**Đặt cảnh báo giá** (price alert) ở vùng vào lệnh và chờ xác nhận. "
            "Không 'mua trước chờ xác nhận sau' — đây là sai lầm phổ biến của F0.\n\n"
            f"📌 **Điều kiện để tín hiệu nâng lên MUA:**\n{upgrade_list}"
        )

    # NO_ACTION
    hmm_context = {
        "STEADY_BULL":  "Thị trường chung đang tăng tốt — nhưng cổ phiếu này chưa đủ điểm riêng",
        "TRENDING_UP":  "Thị trường đang tăng — nhưng tín hiệu cổ phiếu này chưa đủ",
        "TRANSITIONAL": "Thị trường đang chuyển tiếp — chưa rõ xu hướng, thận trọng",
        "RANGING":      "Thị trường đang đi ngang — chưa có xu hướng rõ, nên chờ",
        "STEADY_BEAR":  "Thị trường đang giảm — không phải thời điểm mua mới",
        "TRENDING_DOWN": "Thị trường đang giảm — thận trọng với mọi giao dịch mới",
    }.get(hmm_state, f"Thị trường: {hmm_state}")
    needed_mfpm = max(0, 50 - mfpm_score)
    return (
        "**→ Kiên nhẫn chờ, chưa hành động**\n\n"
        f"{hmm_context}. "
        f"Điểm MFPM hiện tại {mfpm_score}/120 chưa đạt ngưỡng tối thiểu 50 để theo dõi.\n\n"
        "📌 **Tín hiệu THEO DÕI sẽ xuất hiện khi:**\n"
        f"  - Điểm MFPM tăng thêm **{needed_mfpm} điểm** nữa (hiện {mfpm_score}/120)\n"
        "  - RSI phục hồi về vùng 45–60 (momentum tích cực)\n"
        "  - Khối lượng giao dịch tăng lên trên mức bình thường\n"
        "  - Dòng tiền thông minh (SMS) đạt trên 45\n"
        + (f"  - Bộ lọc thao túng (AMF) cần = PASS (hiện: {amf_decision})" if amf_decision != "PASS" else "  - Bộ lọc thao túng (AMF) đang PASS ✅")
    )


def generate_f0_explanation(
    ticker: str,
    action: str,
    mfpm_score: int,
    signal_mode: str,
    confidence: str,
    close: float,
    entry_price: float,
    stop_loss: float,
    sl_pct: float,
    tp1: float,
    tp2: float,
    rr_ratio: float,
    rsi14: float,
    sms_raw: int,
    sms_label: str,
    stealth_accum: bool,
    distribution_warning: str,
    hmm_state: str,
    amd_phase: str,
    amf_decision: str,
    best_pattern: str,
    mcvd_trend: str,
    mc_win_prob: float,
    mode_w_score: int = 0,
    mode_a_score: int = 0,
    mode_b_score: int = 0,
    macro_regime: str = "",
    earnings_risk: str = "SAFE",
    sma20: float = 0.0,
    sma50: float = 0.0,
    sma200: float = 0.0,
    volume: float = 0.0,
    avg_volume_20d: float = 0.0,
    atr14: float = 0.0,
    mode_w_conditions_failed: list[str] | None = None,
) -> str:
    """Generate a beginner-friendly (F0 investor) explanation of the trading signal.

    Structured into 6 sections, using plain Vietnamese with no assumed finance knowledge:
      1. Kết luận
      2. Tại sao điểm này?
      3. Tín hiệu ủng hộ
      4. Rủi ro cần lưu ý
      5. Kế hoạch giao dịch
      6. Bạn nên làm gì?
    """
    action_f0     = _ACTION_F0.get(action, action)
    score_interp  = _f0_score_interpret(mfpm_score)
    mode_explain  = _MODE_F0_EXPLAIN.get(signal_mode, _MODE_F0_EXPLAIN["—"])

    # ── Section 1: Kết luận ───────────────────────────────────────────────────
    _verdict = {
        "STRONG_BUY":  "Đây là **tín hiệu tốt nhất** mà hệ thống có thể đưa ra — kỹ thuật, dòng tiền và vĩ mô đều ủng hộ.",
        "BUY":         "Tín hiệu **đủ mạnh để xem xét mua** theo kế hoạch với tỷ trọng vừa phải.",
        "WATCH":       "Tín hiệu đang **hình thành** nhưng chưa đủ điều kiện vào lệnh an toàn. Theo dõi và chờ xác nhận.",
        "NO_ACTION":   "Hiện **chưa có tín hiệu mua**. Đây không phải thời điểm thích hợp để mua cổ phiếu này.",
        "EXIT":        "**Cảnh báo rủi ro** — phân phối đang được phát hiện. Nếu đang nắm giữ, cân nhắc thoát dần.",
        "FORCED_EXIT": "**THOÁT NGAY** — phân phối cực mạnh, rủi ro vốn rất cao. Ưu tiên bán toàn bộ.",
    }.get(action, "")

    s1 = (
        "### 1. 📊 Kết luận\n\n"
        f"Kết quả phân tích kỹ thuật của mã cổ phiếu **{ticker}** cho thấy tín hiệu "
        f"**{action_f0}** với điểm tổng là **{mfpm_score}/120** — {score_interp}.\n\n"
        f"{_verdict}"
    )

    # ── Section 2: Tại sao điểm này? ─────────────────────────────────────────
    hmm_vi = {
        "STEADY_BULL":   "thị trường đang trong xu hướng tăng ổn định 🟢",
        "TRENDING_UP":   "thị trường đang tăng 🟢",
        "TRANSITIONAL":  "thị trường đang chuyển tiếp — chưa rõ xu hướng 🟡",
        "RANGING":       "thị trường đang đi ngang 🟡",
        "STEADY_BEAR":   "thị trường đang trong xu hướng giảm 🔴",
        "TRENDING_DOWN": "thị trường đang giảm 🔴",
    }.get(hmm_state, hmm_state)

    amd_vi = {
        "ACCUMULATION": "giai đoạn **tích lũy** — tổ chức đang âm thầm gom hàng ✅",
        "MARKUP":       "giai đoạn **tăng giá** (Markup) — xu hướng tăng đang xác nhận ✅",
        "DISTRIBUTION": "giai đoạn **phân phối** — tổ chức đang bán ra ⚠️",
        "MARKDOWN":     "giai đoạn **giảm giá** (Markdown) ⚠️",
        "RANGING":      "giai đoạn **đi ngang** — chưa có xu hướng rõ",
    }.get(amd_phase, amd_phase)

    mc_quality = (
        "cao" if mc_win_prob >= 0.60 else
        "khá tốt" if mc_win_prob >= 0.55 else
        "trung bình" if mc_win_prob >= 0.50 else "thấp"
    )

    amf_line = {
        "PASS":  "✅ Không phát hiện thao túng giá",
        "WARN":  "⚠️ Có dấu hiệu nhỏ bất thường — quan sát thêm",
        "BLOCK": "🚫 Phát hiện thao túng giá — tín hiệu bị vô hiệu hoá",
    }.get(amf_decision, amf_decision)

    why_bullets = [
        f"- **Chiến lược hệ thống:** {mode_explain}",
        f"- **Điểm kỹ thuật tổng hợp (MFPM):** {mfpm_score}/120 — {score_interp}",
        f"- **Bối cảnh thị trường chung:** {hmm_vi}",
        f"- **Chu kỳ giá cổ phiếu (AMD):** Đang ở {amd_vi}",
        f"- **Bộ lọc thao túng (AMF):** {amf_line}",
    ]
    if mc_win_prob > 0:
        why_bullets.append(
            f"- **Xác suất thắng (1000 kịch bản mô phỏng):** {mc_win_prob:.0%} — {mc_quality} "
            "*(mô phỏng 1.000 kịch bản giá ngẫu nhiên, tính tỷ lệ đạt TP trước khi chạm SL)*"
        )
    dist_vi = {
        "WATCH":       "⚠️ Cảnh báo nhẹ — theo dõi khối lượng chặt hơn",
        "CAUTION":     "🔶 Rõ ràng — hạn chế vào mới",
        "EXIT":        "🔴 Mạnh — nên giảm tỷ trọng",
        "FORCED_EXIT": "‼️ Cực mạnh — thoát toàn bộ",
    }.get(distribution_warning)
    if dist_vi:
        why_bullets.append(f"- **Cảnh báo phân phối:** {dist_vi}")

    s2 = "### 2. 🔍 Tại sao điểm này?\n\n" + "\n".join(why_bullets)

    # ── Section 3: Tín hiệu ủng hộ ───────────────────────────────────────────
    supports: list[str] = []

    if rsi14 < 35:
        supports.append(
            f"📊 **RSI = {rsi14:.0f} (quá bán):** Áp lực bán đang kiệt sức — "
            "thường xuất hiện ngay trước đợt phục hồi mạnh."
        )
    elif 35 <= rsi14 < 50:
        supports.append(
            f"📊 **RSI = {rsi14:.0f} (đang hồi phục):** Momentum đang xây lại từ đáy, "
            "ủng hộ xu hướng tăng sắp tới."
        )

    if sma50 > 0 and close > sma50:
        pct_50 = (close - sma50) / sma50 * 100
        supports.append(
            f"📈 **Giá trên MA50 (+{pct_50:.1f}%):** Điều kiện cần thiết cho tín hiệu mua T+. "
            "Xu hướng tăng trung hạn đang được duy trì."
        )
    if sma200 > 0 and close > sma200:
        pct_200 = (close - sma200) / sma200 * 100
        supports.append(
            f"📈 **Giá trên MA200 (+{pct_200:.1f}%):** Xu hướng tăng dài hạn được xác nhận — "
            "nền tảng quan trọng cho nhà đầu tư giữ 3–6 tháng."
        )

    if sms_raw >= 65:
        supports.append(
            f"🐳 **Dòng tiền tổ chức cao (SMS = {sms_raw}/100):** "
            "Phát hiện quỹ đầu tư / tổ chức lớn đang mua vào. "
            "Khi 'cá mập' vào trước, giá thường tăng bền hơn."
        )
    elif sms_raw >= 45:
        supports.append(
            f"🟡 **Dòng tiền hỗn hợp (SMS = {sms_raw}/100):** "
            "Có sự quan tâm từ tổ chức nhưng chưa quyết định rõ ràng."
        )

    if stealth_accum:
        supports.append(
            "🔍 **Tích lũy âm thầm (Stealth Accumulation):** Nhiều phiên có khối lượng lớn "
            "nhưng giá ít thay đổi — dấu hiệu tổ chức đang gom hàng mà không muốn đẩy giá."
        )

    if mcvd_trend == "UP":
        supports.append(
            "📈 **Dòng tiền thông minh (M-CVD tăng):** Dòng tiền tổng hợp nâng dần "
            "qua nhiều phiên — xác nhận tích lũy đang diễn ra."
        )

    if best_pattern and best_pattern not in ("NONE", ""):
        pat_text = _PATTERN_F0_EXPLAIN.get(best_pattern, f"Mẫu hình **{best_pattern}** được phát hiện.")
        supports.append(pat_text)

    if amd_phase in ("ACCUMULATION", "MARKUP"):
        amd_msg = {
            "ACCUMULATION": "Cổ phiếu đang bước vào giai đoạn tích lũy — theo lý thuyết Wyckoff, đây thường là giai đoạn mua tốt nhất.",
            "MARKUP": "Cổ phiếu đang trong giai đoạn tăng giá chính thức — uptrend đang diễn ra.",
        }[amd_phase]
        supports.append(f"🔄 **Chu kỳ {amd_phase}:** {amd_msg}")

    if macro_regime == "ACCOMMODATIVE":
        supports.append(
            "🏦 **Môi trường vĩ mô thuận lợi:** Chính sách tiền tệ nới lỏng "
            "(lãi suất thấp / SBV bơm tiền) — thị trường chứng khoán thường được hưởng lợi."
        )

    if avg_volume_20d > 0 and volume / avg_volume_20d >= 1.5:
        vr = volume / avg_volume_20d
        supports.append(
            f"🔊 **Khối lượng tăng {vr:.1f}×:** Dòng tiền đang tham gia tích cực — "
            "tín hiệu có độ tin cậy cao hơn."
        )

    if signal_mode == "MODE_W" and mode_w_score >= 60:
        supports.append(
            f"🐳 **Mode W kích hoạt (W-Score = {mode_w_score}/115):** "
            "Hội tụ đủ điều kiện dòng tiền tổ chức — tín hiệu mạnh và bền nhất."
        )

    s3_body = "\n\n".join(supports) if supports else "_Chưa có tín hiệu ủng hộ đáng kể tại thời điểm này._"
    s3 = f"### 3. ✅ Tín hiệu ủng hộ\n\n{s3_body}"

    # ── Section 4: Rủi ro cần lưu ý ──────────────────────────────────────────
    risks: list[str] = []

    if distribution_warning in ("CAUTION", "EXIT", "FORCED_EXIT"):
        level_text = {"CAUTION": "rõ ràng", "EXIT": "mạnh", "FORCED_EXIT": "cực mạnh"}[distribution_warning]
        risks.append(
            f"🔴 **Phân phối {level_text} ({distribution_warning}):** "
            "Có dấu hiệu tổ chức đang bán ra — "
            "đây là rủi ro nghiêm trọng nhất, ưu tiên hơn mọi tín hiệu mua."
        )
    elif distribution_warning == "WATCH":
        risks.append(
            "⚠️ **Cảnh báo phân phối nhẹ (WATCH):** "
            "Theo dõi khối lượng chặt hơn trong 2–3 phiên tới."
        )

    if amf_decision == "BLOCK":
        risks.append(
            "🚫 **Thao túng giá (AMF BLOCK):** Phát hiện dấu hiệu bơm/xả hoặc "
            "giao dịch bất thường. Tín hiệu bị vô hiệu hoá để bảo vệ vốn. "
            "**Tuyệt đối không vào lệnh.**"
        )
    elif amf_decision == "WARN":
        risks.append(
            "⚠️ **Dấu hiệu nhỏ bất thường (AMF WARN):** Chưa đủ mức chặn tín hiệu "
            "nhưng cần trọng khi vào lệnh."
        )

    if rsi14 > 70:
        risks.append(
            f"📊 **RSI = {rsi14:.0f} (quá mua):** Cổ phiếu đang ở vùng quá mua. "
            "Rủi ro điều chỉnh ngắn hạn cao — tránh mua đuổi, "
            "chờ RSI điều chỉnh về 60–65 trước khi xem xét."
        )

    if sma50 > 0 and close < sma50:
        pct_below = (close - sma50) / sma50 * 100
        risks.append(
            f"📉 **Giá dưới MA50 ({pct_below:.1f}%):** Xu hướng trung hạn chưa đủ mạnh. "
            "Điều kiện cần thiết cho tín hiệu mua T+ chưa được đáp ứng."
        )

    if sma200 > 0 and close < sma200:
        risks.append(
            "📉 **Giá dưới MA200:** Xu hướng dài hạn đang giảm. "
            "Phù hợp lướt sóng ngắn hạn nhưng không nên giữ dài."
        )

    if hmm_state in ("STEADY_BEAR", "TRENDING_DOWN"):
        risks.append(
            f"🔴 **Thị trường giảm ({hmm_state}):** Khi thị trường chung đi xuống, "
            "ngay cả cổ phiếu tốt cũng khó tăng bền. Tránh mua mới."
        )

    if amd_phase in ("DISTRIBUTION", "MARKDOWN"):
        phase_msg = "phân phối (tổ chức xả hàng)" if amd_phase == "DISTRIBUTION" else "giảm giá (Markdown)"
        risks.append(
            f"📤 **Chu kỳ {phase_msg}:** Rủi ro cao — "
            "không phải thời điểm tham gia ở giá hiện tại."
        )

    if earnings_risk in ("CAUTION", "HIGH_RISK"):
        risks.append(
            f"📋 **Sắp có kết quả kinh doanh ({earnings_risk}):** "
            + ("Có thể biến động mạnh sau công bố — giảm tỷ trọng xuống 50%." if earnings_risk == "CAUTION"
               else "Rủi ro cao với kết quả kinh doanh — thận trọng tuyệt đối.")
        )

    if macro_regime == "RESTRICTIVE":
        risks.append(
            "🏦 **Môi trường vĩ mô thắt chặt:** Lãi suất cao hoặc tỷ giá áp lực — "
            "thường gây áp lực lên toàn bộ thị trường chứng khoán."
        )

    if avg_volume_20d > 0 and volume > 0 and volume < avg_volume_20d * 0.5:
        risks.append(
            f"🔇 **Khối lượng thấp ({volume/avg_volume_20d:.1f}×):** "
            "Thiếu sự tham gia của dòng tiền lớn — tín hiệu cần xác nhận thêm."
        )

    if mode_w_conditions_failed:
        fail_str = "; ".join(mode_w_conditions_failed[:3])
        risks.append(
            f"🐳 **Mode W chưa đủ điều kiện:** Còn thiếu: {fail_str}. "
            "Chờ đủ điều kiện để tín hiệu bền vững hơn."
        )

    s4_body = "\n\n".join(risks) if risks else "_Không phát hiện rủi ro đặc biệt tại thời điểm này._"
    s4 = f"### 4. ⚠️ Rủi ro cần lưu ý\n\n{s4_body}"

    # ── Section 5: Kế hoạch giao dịch ────────────────────────────────────────
    if entry_price > 0 and stop_loss > 0:
        sl_loss_pct = abs(sl_pct) * 100
        tp1_gain = (tp1 - entry_price) / max(entry_price, 1) * 100
        tp2_gain = (tp2 - entry_price) / max(entry_price, 1) * 100
        rr_text = f"1:{rr_ratio:.1f}" if rr_ratio > 0 else "—"
        rr_quality = (
            "✅ Tốt — mỗi 1đ rủi ro có thể kiếm được hơn 1.5đ lợi nhuận"
            if rr_ratio >= 1.5 else
            "⚠️ Thấp hơn 1.5 — cân nhắc kỹ trước khi vào"
        )
        mc_explain = (
            f"{'✅ Đủ tốt để vào lệnh' if mc_win_prob >= 0.55 else '⚠️ Dưới 55% — cân nhắc'} "
            f"({mc_win_prob:.0%} trong 1.000 kịch bản mô phỏng)"
        )

        trade_block = (
            f"| Mức giá | Giá (đồng) | Ý nghĩa |\n"
            f"|---|---|---|\n"
            f"| 📍 Giá hiện tại | **{close:,.0f}** | Giá đóng cửa gần nhất |\n"
            f"| 🟢 Vùng vào lệnh | **{entry_price:,.0f}** | Mức giá tốt nhất để đặt lệnh mua |\n"
            f"| 🔴 Cắt lỗ (Stop Loss) | **{stop_loss:,.0f}** | Nếu giá chạm mức này → **bán ngay, không do dự** |\n"
            f"| 🎯 Chốt lời 1 (TP1) | **{tp1:,.0f}** | Chốt 50–70% vị thế tại đây |\n"
            f"| 🎯 Chốt lời 2 (TP2) | **{tp2:,.0f}** | Phần còn lại nếu đà tăng tiếp tục |\n"
            f"\n"
            f"- 📉 **Rủi ro cắt lỗ:** -{sl_loss_pct:.1f}% từ giá vào\n"
            f"- 📈 **Lợi nhuận mục tiêu TP1:** +{tp1_gain:.1f}%\n"
            f"- 📈 **Lợi nhuận mục tiêu TP2:** +{tp2_gain:.1f}%\n"
            f"- ⚖️ **Tỷ lệ R:R:** {rr_text} — {rr_quality}\n"
            f"- 🎲 **Xác suất thắng:** {mc_explain}"
        )

        atr_note = ""
        if atr14 > 0 and close > 0:
            atr_pct = atr14 / close * 100
            atr_note = (
                f"\n\n> 💡 **Biến động ngày:** ATR = {atr14:,.0f}đ ({atr_pct:.1f}% giá). "
                + ("Biến động cao — hãy dùng tỷ trọng nhỏ hơn bình thường (≤50%)." if atr_pct >= 5.0
                   else "Biến động bình thường — áp dụng sizing theo khuyến nghị.")
            )
    else:
        trade_block = (
            "_Chưa đủ điều kiện để xác định mức giá vào lệnh. "
            "Xuất hiện khi tín hiệu đạt mức THEO DÕI trở lên._"
        )
        atr_note = ""

    s5 = f"### 5. 💰 Kế hoạch giao dịch\n\n{trade_block}{atr_note}"

    # ── Section 6: Bạn nên làm gì? ───────────────────────────────────────────
    advice = _f0_upgrade_advice(
        action=action,
        signal_mode=signal_mode,
        mfpm_score=mfpm_score,
        mode_w_score=mode_w_score,
        mc_win_prob=mc_win_prob,
        amf_decision=amf_decision,
        distribution_warning=distribution_warning,
        hmm_state=hmm_state,
    )

    disclaimer = (
        "\n\n---\n"
        "> ⚠️ *Đây là công cụ hỗ trợ phân tích, **không phải khuyến nghị đầu tư**. "
        "Mọi quyết định giao dịch hoàn toàn do nhà đầu tư tự chịu trách nhiệm. "
        "TradingOS không đặt lệnh tự động và không chịu trách nhiệm về kết quả giao dịch.*"
    )

    s6 = f"### 6. 🎯 Bạn nên làm gì?\n\n{advice}{disclaimer}"

    return "\n\n---\n\n".join([s1, s2, s3, s4, s5, s6])
