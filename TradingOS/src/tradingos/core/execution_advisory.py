"""Execution Advisory — [H1 ADVISORY ONLY] MTL/ATC advisor (SRS §8.1).

[H1 SRS CONSTRAINT] This module NEVER places orders.
All outputs are human-readable advisory strings only.
"""
from __future__ import annotations

from datetime import datetime, time


def _session_phase() -> str:
    now = datetime.now().time()
    if now < time(9, 0):     return "PRE_MARKET"
    elif now < time(9, 15):  return "PRE_ATO"
    elif now < time(9, 30):  return "ATO"
    elif now < time(11, 30): return "MORNING"
    elif now < time(13, 0):  return "LUNCH"
    elif now < time(14, 30): return "AFTERNOON"
    elif now < time(14, 43): return "NEAR_ATC"
    elif now <= time(14, 45): return "ATC"
    else:                    return "CLOSED"


def advise_entry_window(
    action: str,
    signal_mode: str,
    confidence: str,
    current_price: float = 0.0,
    entry_target: float = 0.0,
) -> dict:
    """
    Recommend optimal entry window for VN session.
    Returns advisory dict (display only, no order logic).
    """
    phase = _session_phase()

    if action not in ("BUY", "STRONG_BUY"):
        return {
            "advisory": "Không vào lệnh — tín hiệu chưa đủ điều kiện.",
            "window": "—",
            "order_type": "—",
            "rationale": "",
        }

    if signal_mode == "MODE_W" and confidence in ("HIGH", "MEDIUM"):
        window = "ATC 14:43 hôm nay"
        order_type = "ATC (Khớp cuối ngày)"
        rationale = "Mode W: Cá mập thường tích lũy cuối ngày qua ATC."
    elif signal_mode == "MODE_B":
        window = "09:30–09:45 (sau mở cửa, confirm breakout)"
        order_type = "LO (Lệnh giới hạn) tại pivot"
        rationale = "Mode B: Vào breakout ngay sau xác nhận mở cửa mạnh."
    else:  # MODE_A
        window = "14:05–14:20 hoặc ATO T+1"
        order_type = "LO tại SMA20 ± 0.5%"
        rationale = "Mode A: Pullback — vào khi giá kiểm tra lại support."

    # Current-time override
    if phase in ("ATC", "NEAR_ATC") and action == "STRONG_BUY":
        window = "ATC ngay bây giờ (14:43)"
        order_type = "ATC"
        rationale += " ⏰ Đang trong cửa sổ ATC — tín hiệu mạnh."
    elif phase == "CLOSED":
        window = "ATO sáng mai"
        order_type = "ATO"
        rationale += " 🔔 Thị trường đóng cửa — plan ATO sáng T+1."

    notes = []
    if current_price > 0 and entry_target > 0:
        drift = (current_price - entry_target) / entry_target
        if drift > 0.03:
            notes.append(f"⚠️ Giá hiện tại {current_price:,.0f} cao hơn target {drift:+.1%} — cân nhắc chờ pullback.")
        elif drift < -0.03:
            notes.append(f"ℹ️ Giá hiện tại {current_price:,.0f} dưới target {drift:+.1%} — có thể vào ngay.")

    return {
        "advisory": f"Vào lệnh tại: **{window}**",
        "window": window,
        "order_type": order_type,
        "rationale": rationale,
        "notes": notes,
        "disclaimer": "[H1] TradingOS không đặt lệnh. Tất cả kết quả chỉ mang tính tư vấn.",
    }


def advise_exit_window(
    action: str,
    hold_days: int,
    pnl_pct: float,
    distribution_warning: str = "NONE",
) -> dict:
    """Recommend exit window advisory."""
    phase = _session_phase()

    if distribution_warning in ("EXIT", "FORCED_EXIT"):
        return {
            "advisory": f"⚠️ THOÁT NGAY — {distribution_warning}. Dùng lệnh ATC.",
            "window": "ATC ngay",
            "urgency": "HIGH",
            "disclaimer": "[H1] Advisory only.",
        }

    if action == "SELL_FULL_ATC":
        window = "ATC 14:43" if phase in ("NEAR_ATC", "ATC", "CLOSED") else "ATC hôm nay"
    elif action == "SELL_PARTIAL_ATC":
        window = "ATC 14:43 (40% vị thế)"
    else:
        window = "Giữ, theo dõi tiếp"

    return {
        "advisory": f"Thoát tại: {window}",
        "window": window,
        "urgency": "MEDIUM" if pnl_pct > 0 else "HIGH",
        "disclaimer": "[H1] Advisory only.",
    }
