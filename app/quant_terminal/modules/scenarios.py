"""
Scenarios — investment scenario generation, LO/ATO/ATC order builder,
session detection, and buy scenario sizing.
All prices in thousands-VND.
"""
import datetime as dt
import logging
import math

try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    _VN_TZ = _ZoneInfo("Asia/Ho_Chi_Minh")
except ImportError:
    _VN_TZ = dt.timezone(dt.timedelta(hours=7))

import numpy as np
import pandas as pd

from config import (
    HOSE_TICK, SELL_TAX_RATE, SSI_MIN_BROKERAGE,
    MAX_RISK_PER_TRADE, VN_PUBLIC_HOLIDAYS, hose_tick,
    compute_price_limits,
)
from modules.analysis import compute_signal_score, find_support_resistance

_log = logging.getLogger("scenarios")

_SSI_BROKERAGE_RATE = 0.0015   # 0.15% of trade value, min SSI_MIN_BROKERAGE k.VND


# ── HELPERS ───────────────────────────────────────────────────────────────────

def round_to_tick(price: float) -> float:
    """Round price to nearest valid HOSE tick (thousands-VND)."""
    tick = hose_tick(price)
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 3)


def _brokerage(value_k: float) -> float:
    """Estimate SSI brokerage in thousands-VND. 0.15% capped at minimum."""
    b = value_k * _SSI_BROKERAGE_RATE
    return max(b, float(SSI_MIN_BROKERAGE))


def _sell_tax(value_k: float) -> float:
    """0.1% withholding tax on sell value (thousands-VND)."""
    return value_k * SELL_TAX_RATE


def _is_trade_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in VN_PUBLIC_HOLIDAYS


# ── SESSION ───────────────────────────────────────────────────────────────────

def current_session() -> tuple:
    """Return (session_name, description) for the current VN time."""
    now  = dt.datetime.now(tz=_VN_TZ)
    hm   = now.hour * 60 + now.minute
    day  = now.date()

    if not _is_trade_day(day):
        return "Đóng cửa", "Ngoài ngày giao dịch (cuối tuần/ngày lễ)"

    if hm < 8 * 60:
        return "Trước giờ mở", "Chưa đến giờ mở phiên (08:00)"
    if hm < 9 * 60:
        return "PRE", "Nhập lệnh trước giờ mở (08:00–09:00)"
    if hm < 9 * 60 + 15:
        return "ATO", "Khớp lệnh mở cửa — ATO (09:00–09:15)"
    if hm < 11 * 60 + 30:
        return "Liên tục 1", f"Phiên liên tục sáng (09:15–11:30) | {now.strftime('%H:%M')}"
    if hm < 13 * 60:
        return "Nghỉ trưa", "Nghỉ giữa phiên (11:30–13:00)"
    if hm < 14 * 60 + 30:
        return "Liên tục 2", f"Phiên liên tục chiều (13:00–14:30) | {now.strftime('%H:%M')}"
    if hm < 14 * 60 + 45:
        return "ATC", "Khớp lệnh đóng cửa — ATC (14:30–14:45)"
    if hm < 15 * 60:
        return "PT", "Phiên thỏa thuận (14:45–15:00)"
    return "Đóng cửa", "Thị trường đã đóng cửa (sau 15:00)"


# ── SCENARIO GENERATION ───────────────────────────────────────────────────────

def generate_scenarios(
    symbol: str,
    cost_price: float,
    market_price: float,
    qty: int,
    hist_df: pd.DataFrame,
    index_df=None,
    analyst_target=None,
    portfolio_value: float = 38_000_000,
    user_probs: dict = None,
    exchange: str = "HOSE",
) -> dict:
    """
    Generate 3-scenario investment plan (bull/base/bear) with orders.
    Prices in thousands-VND.
    exchange: used to enforce daily circuit-breaker limits (C-04 fix).
    """
    p = user_probs or {"bull": 0.30, "base": 0.45, "bear": 0.25}
    p_bull = p.get("bull", 0.30)
    p_base = p.get("base", 0.45)
    p_bear = p.get("bear", 0.25)

    # ── Technical context ─────────────────────────────────────────────────────
    sig = compute_signal_score(hist_df) if hist_df is not None and not hist_df.empty else {}
    sr  = find_support_resistance(hist_df) if hist_df is not None and not hist_df.empty else {"resistance": [], "support": []}
    signal_score = sig.get("score", 0)

    close = market_price or cost_price
    atr   = float(hist_df["close"].pct_change().std() * close) if (
        hist_df is not None and not hist_df.empty and "close" in hist_df
    ) else close * 0.015

    # ── Exchange circuit-breaker limits (C-04 fix) ────────────────────────────
    ceil_p, floor_p = compute_price_limits(close, exchange)

    # ── Stop loss (trail from close, not cost — avoids R:R distortion) ───────
    support_levels = [s for s in sr.get("support", []) if s < close]
    if support_levels:
        stop = round_to_tick(min(support_levels[-1], close * 0.93))
    else:
        stop = round_to_tick(close - 2.5 * atr)
    stop = round_to_tick(max(stop, close * 0.90))   # cap: max -10% from close
    # Clamp stop price so it doesn't go below today's floor (C-04 fix)
    stop_p = round_to_tick(max(stop, floor_p))

    # ── Targets ───────────────────────────────────────────────────────────────
    resistance_levels = [r for r in sr.get("resistance", []) if r > close]

    # Bull target: nearest resistance or +7%
    if resistance_levels:
        bull_target = round_to_tick(resistance_levels[0])
    elif analyst_target and analyst_target > close:
        bull_target = round_to_tick(analyst_target)
    else:
        bull_target = round_to_tick(close * 1.07)

    # Clamp targets at ceiling (C-04 fix)
    bull_target = min(bull_target, ceil_p)

    # Base target: +2% (flat-ish), also capped at ceiling
    base_target = min(round_to_tick(close * 1.02), ceil_p)

    # Bear target: stop level
    bear_target = stop_p

    # ── Expected value ────────────────────────────────────────────────────────
    def pnl(price: float) -> float:
        return (price - cost_price) * qty

    pnl_bull = pnl(bull_target)
    pnl_base = pnl(base_target)
    pnl_bear = pnl(bear_target)
    ev_hold  = p_bull * (bull_target - cost_price) + p_base * (base_target - cost_price) + p_bear * (bear_target - cost_price)

    # ── R:R ───────────────────────────────────────────────────────────────────
    risk_per_cp  = close - stop_p
    reward_per_cp= bull_target - close
    rr_bull = (reward_per_cp / risk_per_cp) if risk_per_cp > 0 else 0.0

    # ── Primary action (CẮT LỖ has highest priority) ─────────────────────────
    # M-03: add ±0.5% epsilon to exclude effectively break-even positions
    pnl_pct_vs_cost = (market_price / cost_price - 1) * 100 if cost_price > 0 else 0
    if abs(pnl_pct_vs_cost) < 0.5:
        primary_action = "QUAN SÁT"  # break-even — do not trigger cut-loss
        action_color   = "#6B7280"
    elif market_price < cost_price * 0.93:
        primary_action = "CẮT LỖ"
        action_color   = "#DC2626"
    elif ev_hold > 0 and signal_score >= -20 and rr_bull >= 1.5:
        primary_action = "GIỮ"
        action_color   = "#16A34A"
    elif signal_score < -40 or (ev_hold < 0 and market_price > cost_price * 1.03):
        primary_action = "CHỐT LỜI 50%"
        action_color   = "#F59E0B"
    else:
        primary_action = "QUAN SÁT"
        action_color   = "#6B7280"

    # ── Orders ────────────────────────────────────────────────────────────────
    # H-03 fix: cap lot quantities to actual holding; no hardcoded floor of 100
    half_qty    = max(10, (qty // 2 // 10) * 10)
    half_qty    = min(half_qty, qty)
    quarter_qty = max(10, (qty // 4 // 10) * 10)
    quarter_qty = min(quarter_qty, qty)

    chot_50_price = min(round_to_tick(bull_target), ceil_p)
    chot_all_price= min(round_to_tick(bull_target * 1.02), ceil_p)
    scale_out_p   = round_to_tick(close)
    _stop_p       = stop_p  # already clamped above

    orders = [
        {
            "name":    "Lệnh 1 — Chốt lời 50%",
            "type":    "LO",
            "side":    "Bán",
            "price":   chot_50_price,
            "qty":     half_qty,
            "pnl_est": (chot_50_price - cost_price) * half_qty,
            "note":    f"Chốt 50% KL khi giá chạm {chot_50_price*1000:,.0f}đ (kháng cự gần)",
            "trigger": f"Giá ≥ {chot_50_price*1000:,.0f}đ hoặc P&L > {((chot_50_price/cost_price)-1)*100:.1f}%",
        },
        {
            "name":    "Lệnh 2 — Chốt hết",
            "type":    "LO",
            "side":    "Bán",
            "price":   chot_all_price,
            "qty":     qty,
            "pnl_est": (chot_all_price - cost_price) * qty,
            "note":    f"Thoát toàn bộ nếu giá vượt {chot_all_price*1000:,.0f}đ (target +2% so kháng cự)",
            "trigger": f"Giá ≥ {chot_all_price*1000:,.0f}đ",
        },
        {
            "name":    "Lệnh 3 — Giảm tỷ trọng",
            "type":    "ATO",
            "side":    "Bán",
            "price":   scale_out_p,
            "qty":     quarter_qty,
            "pnl_est": (scale_out_p - cost_price) * quarter_qty,
            "note":    "Bán 25% KL theo giá mở cửa để giảm rủi ro tập trung",
            "trigger": "Tín hiệu suy yếu liên tiếp 2 phiên hoặc VN-Index giảm > 2%",
        },
        {
            "name":    "Lệnh 4 — Cắt lỗ / Stop",
            "type":    "LO (canh tay)",
            "side":    "Bán",
            "price":   _stop_p,
            "qty":     qty,
            "pnl_est": (_stop_p - cost_price) * qty,
            "note":    f"Dời stop thủ công khi giá tăng. Stop hiện tại: {_stop_p*1000:,.0f}đ",
            "trigger": f"Giá ≤ {_stop_p*1000:,.0f}đ ({((_stop_p/close)-1)*100:.1f}% từ TT)",
        },
    ]

    # For CẮT LỖ recommendation: only show stop-loss order
    if primary_action == "CẮT LỖ":
        orders = [orders[-1]]

    return {
        "symbol":         symbol,
        "primary_action": primary_action,
        "action_color":   action_color,
        "ev_hold":        round(ev_hold, 3),
        "rr_bull":        round(rr_bull, 2),
        "stop_loss":      _stop_p,
        "bull_target":    bull_target,
        "base_target":    base_target,
        "bear_target":    bear_target,
        "pnl_bull":       pnl_bull,
        "pnl_base":       pnl_base,
        "pnl_bear":       pnl_bear,
        "orders":         orders,
        "signal_score":   signal_score,
        "atr":            atr,
        "ceiling":        ceil_p,
        "floor":          floor_p,
    }


# ── LO / ATO / ATC BUILDER ───────────────────────────────────────────────────

def build_lo_instruction(
    symbol: str,
    side: str,
    qty: int,
    price: float,
    note: str = "",
    order_type: str = "LO",
) -> dict:
    """
    Build step-by-step LO/ATO/ATC order instruction.
    price in thousands-VND.
    Returns {steps, order_type, value, brokerage_est, sell_tax, session, important}.
    """
    session_name, _ = current_session()
    price_display   = round_to_tick(price) if order_type == "LO" else price
    value           = price_display * qty                          # thousands-VND
    brokerage       = _brokerage(value)                            # thousands-VND
    sell_tax        = _sell_tax(value) if side == "Bán" else 0.0   # thousands-VND

    if order_type in ("ATO", "ATC"):
        timing = "08:30–09:15" if order_type == "ATO" else "14:30–14:45"
        steps = [
            f"Đăng nhập SSI iBoard hoặc app SSI trên điện thoại",
            f"Tìm mã <b>{symbol.upper()}</b> → Nhấn <b>{side}</b>",
            f"Chọn loại lệnh: <b>{order_type}</b>",
            f"Nhập khối lượng: <b>{qty:,} CP</b>",
            f"Giá sẽ khớp tự động tại giá {order_type} — không cần nhập giá",
            f"Kiểm tra tổng giá trị ≈ <b>{value*1000:,.0f}đ</b> → xác nhận lệnh",
            f"Thời điểm hiệu lực: <b>{timing}</b>",
        ]
        if note:
            steps.append(f"Ghi chú: {note}")
        important = [
            f"Lệnh {order_type} chỉ có hiệu lực trong khung giờ {timing}",
            f"Phí dự kiến: {brokerage*1000:,.0f}đ (0.15% hoặc tối thiểu {SSI_MIN_BROKERAGE*1000:,}đ)",
            *(
                [f"Thuế 0.1% ước tính: {sell_tax*1000:,.0f}đ (tính trên tổng giá trị bán)"]
                if sell_tax > 0 else []
            ),
        ]
        return {
            "steps":        steps,
            "order_type":   order_type,
            "value":        value,
            "brokerage_est": brokerage,
            "sell_tax":     sell_tax,
            "session":      session_name,
            "important":    important,
        }

    # ── LO ────────────────────────────────────────────────────────────────────
    tick_k   = hose_tick(price_display)        # tick in thousands-VND
    tick_vnd = int(round(tick_k * 1000))        # tick in raw VND (e.g. 50)
    direction = "≤" if side == "Bán" else "≥"

    steps = [
        f"Đăng nhập SSI iBoard hoặc app SSI trên điện thoại",
        f"Tìm mã <b>{symbol.upper()}</b> → Nhấn <b>{side}</b>",
        f"Chọn loại lệnh: <b>LO</b> (Limit Order)",
        f"Nhập giá: <b>{price_display*1000:,.0f}đ</b> ({price_display:.3f} nghìn đồng) "
        f"(bước giá {tick_vnd}đ ✓)",
        f"Nhập khối lượng: <b>{qty:,} CP</b>",
        f"Giá trị lệnh ≈ <b>{value*1000:,.0f}đ</b> — phí ≈ {brokerage*1000:,.0f}đ",
        f"Kiểm tra thông tin và xác nhận đặt lệnh",
    ]
    if note:
        steps.append(f"Ghi chú: {note}")

    important = [
        f"LO chỉ khớp khi giá thị trường {direction} <b>{price_display*1000:,.0f}đ</b> — "
        "lệnh GTC cho đến khi hủy hoặc khớp hết",
        f"Giá phải nằm trong biên độ ngày (trần/sàn) — kiểm tra trước khi đặt",
        f"Phí dự kiến: {brokerage*1000:,.0f}đ (0.15% hoặc tối thiểu {SSI_MIN_BROKERAGE*1000:,}đ)",
        *(
            [f"Thuế 0.1% trên giá bán: {sell_tax*1000:,.0f}đ"]
            if sell_tax > 0 else []
        ),
    ]

    return {
        "steps":        steps,
        "order_type":   "LO",
        "value":        value,
        "brokerage_est": brokerage,
        "sell_tax":     sell_tax,
        "session":      session_name,
        "important":    important,
    }


# ── BUY SCENARIO ─────────────────────────────────────────────────────────────

def generate_buy_scenarios(
    symbol: str,
    market_price: float,
    hist_df: pd.DataFrame,
    portfolio_value_vnd: float,
) -> dict:
    """
    Generate buy entry plan for a new/additional position.
    portfolio_value_vnd: raw VND (for sizing)
    Returns dict with entry_price, target1, target2, stop_loss, rr,
    recommended_qty, value, brokerage_est, total_cost, signal_label, signal_score, rsi,
    ceiling, floor.
    """
    close = market_price or 15.0
    ceil_p, floor_p = compute_price_limits(close)

    sig      = compute_signal_score(hist_df) if hist_df is not None and not hist_df.empty else {}
    sr       = find_support_resistance(hist_df) if hist_df is not None and not hist_df.empty else {}
    atr      = float(hist_df["close"].pct_change().std() * close) if (
        hist_df is not None and not hist_df.empty and "close" in hist_df
    ) else close * 0.015

    entry = round_to_tick(close)

    # Stop: below recent support or -5%
    supports = [s for s in sr.get("support", []) if s < entry]
    stop     = round_to_tick(supports[-1] if supports else (entry - 2 * atr))
    stop     = round_to_tick(max(stop, entry * 0.90))

    # Targets
    resistances = [r for r in sr.get("resistance", []) if r > entry]
    target1 = round_to_tick(resistances[0] if resistances else entry * 1.05)
    target2 = round_to_tick(resistances[1] if len(resistances) > 1 else entry * 1.10)

    risk_per_cp   = entry - stop
    reward_per_cp = target1 - entry
    rr = (reward_per_cp / risk_per_cp) if risk_per_cp > 0 else 0.0

    # 2% risk rule: risk_amount = portfolio_value * 2%
    risk_amount_vnd = portfolio_value_vnd * MAX_RISK_PER_TRADE
    if risk_per_cp > 0:
        max_qty_risk = int(risk_amount_vnd / (risk_per_cp * 1000))  # risk_per_cp in k.VND
    else:
        max_qty_risk = 100
    # Minimum 10 shares, round to nearest 10
    rec_qty = max(10, (max_qty_risk // 10) * 10)

    value     = round_to_tick(entry) * rec_qty       # thousands-VND
    brokerage = _brokerage(value)
    total_cost = value + brokerage                   # thousands-VND

    return {
        "entry_price":     entry,
        "target1":         target1,
        "target2":         target2,
        "stop_loss":       stop,
        "rr":              round(rr, 2),
        "recommended_qty": rec_qty,
        "value":           value,
        "brokerage_est":   brokerage,
        "total_cost":      total_cost,
        "signal_label":    sig.get("label", "N/A"),
        "signal_score":    sig.get("score", 0),
        "rsi":             sig.get("rsi", 50.0),
        "ceiling":         ceil_p,
        "floor":           floor_p,
    }
