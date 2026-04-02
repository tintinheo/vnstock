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
            f"| | Giá (nghìn VND) | % so với vào |\n"
            f"|---|---|---|\n"
            f"| 📍 Giá hiện tại | **{close:.1f}** | — |\n"
            f"| 🟢 Vào lệnh | **{entry:.1f}** | — |\n"
            f"| 🔴 Cắt lỗ | **{sl:.1f}** | `{sl_pct:+.1f}%` |\n"
            f"| 🎯 Chốt lời T1 | **{tp1:.1f}** | `{tp1_pct:+.1f}%` |\n"
            f"| 🎯 Chốt lời T2 | **{tp2:.1f}** | — |\n"
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
