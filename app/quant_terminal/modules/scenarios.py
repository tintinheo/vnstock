"""
Scenario planner + trade recommendation engine.
Mirrors the advisory logic we applied manually to TCH, CII, HPG, etc.
"""
import math
import datetime as dt
from typing import Optional

from config import (
    HOSE_TICK, MAX_RISK_PER_TRADE, KELLY_FRACTION,
    MAX_POSITION_PCT, SCENARIO_PROBABILITIES
)
from modules.analysis import compute_signal_score, find_support_resistance


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def round_to_tick(price: float, tick: float = HOSE_TICK) -> float:
    """Round price to nearest HOSE price tick (prices in thousands-VND)."""
    return round(round(price / tick) * tick, 2)


def kelly_size(win_prob: float, avg_win: float, avg_loss: float,
               portfolio_value: float, fraction: float = KELLY_FRACTION) -> dict:
    """
    Calculate Kelly Criterion position size.
    Returns {kelly_pct, kelly_shares_equiv, recommended_pct, risk_amount}
    """
    if avg_loss == 0:
        return {"kelly_pct": 0, "recommended_pct": 0}
    b = avg_win / avg_loss  # odds ratio
    q = 1 - win_prob
    kelly_f = (win_prob * b - q) / b
    kelly_f = max(0, kelly_f)
    recommended = min(kelly_f * fraction, MAX_POSITION_PCT)
    return {
        "kelly_pct": round(kelly_f * 100, 1),
        "recommended_pct": round(recommended * 100, 1),
        "risk_amount": round(portfolio_value * MAX_RISK_PER_TRADE),
    }


# ─── SCENARIO ENGINE ─────────────────────────────────────────────────────────

def generate_scenarios(
    symbol: str,
    cost_price: float,
    market_price: float,
    qty: int,
    hist_df,          # pd.DataFrame with OHLCV
    index_df=None,    # pd.DataFrame for VNINDEX
    analyst_target: Optional[float] = None,
    portfolio_value: float = 38_000_000,
    user_probs: Optional[dict] = None,
) -> dict:
    """
    Generate Bull / Base / Bear scenarios for a single position.
    Returns a rich dict with all scenario parameters.
    """
    probs = user_probs or SCENARIO_PROBABILITIES.copy()
    sig   = compute_signal_score(hist_df)
    sr    = find_support_resistance(hist_df)

    close = market_price or sig.get("close", cost_price)
    atr   = sig.get("atr14", close * 0.02)

    # ── PRICE TARGETS ─────────────────────────────────────────────────────────
    resist_levels = sr.get("resistance", [])
    support_levels= sr.get("support", [])

    # Bull target: analyst target OR nearest resistance OR +15% from close
    bull_target = (
        analyst_target if analyst_target and analyst_target > close * 1.05
        else (resist_levels[0] if resist_levels else round_to_tick(close * 1.15))
    )
    bull_target = round_to_tick(max(bull_target, close * 1.05))

    # Base target: midpoint between close and bull
    base_target = round_to_tick((close + bull_target) / 2)

    # Stop loss: nearest support below cost, or ATR-based
    if support_levels:
        stop = round_to_tick(min(support_levels[-1], cost_price * 0.93))
    else:
        stop = round_to_tick(cost_price - 2.5 * atr)
    stop = min(stop, cost_price * 0.92)  # at least -8% from cost

    # Bear target: stop loss level
    bear_target = stop

    # ── R:R CALCULATION ──────────────────────────────────────────────────────
    risk    = close - stop
    reward_bull = bull_target - close
    reward_base = base_target - close
    rr_bull = reward_bull / risk if risk > 0 else 0
    rr_base = reward_base / risk if risk > 0 else 0

    # ── EXPECTED VALUE ────────────────────────────────────────────────────────
    ev_hold = (
        probs["bull"] * (bull_target - close) +
        probs["base"] * (base_target - close) +
        probs["bear"] * (bear_target - close)
    )
    ev_exit = 0  # selling now = 0 edge by definition

    # ── P&L SCENARIOS ─────────────────────────────────────────────────────────
    def pnl(target):
        return (target - cost_price) * qty

    # ── TRADE ORDERS ─────────────────────────────────────────────────────────
    signal_label = sig.get("label", "Trung tính")
    signal_score = sig.get("score", 0)

    # Determine primary recommendation
    if ev_hold > 0 and signal_score >= -20 and rr_bull >= 1.5:
        primary_action = "GIỮ"
        action_color   = "#16A34A"
    elif signal_score < -40 or (ev_hold < 0 and market_price > cost_price):
        primary_action = "CHỐT LỜI 50%"
        action_color   = "#F59E0B"
    elif market_price < cost_price * 0.95:
        primary_action = "CẮT LỖ"
        action_color   = "#DC2626"
    else:
        primary_action = "QUAN SÁT"
        action_color   = "#6B7280"

    # ── EXIT ORDERS ──────────────────────────────────────────────────────────
    half_qty  = math.ceil(qty / 2)
    small_qty = math.ceil(qty * 0.15)

    orders = [
        {
            "name": "Lệnh 1 — Chốt 50%",
            "type": "LO",
            "side": "Bán",
            "qty": half_qty,
            "price": round_to_tick(max(close, cost_price * 1.02)),
            "note": "Hiện thực hóa lãi, giảm rủi ro",
            "trigger": "Ngay phiên đầu tuần",
            "pnl_est": pnl(round_to_tick(max(close, cost_price * 1.02))) // 2,
        },
        {
            "name": "Lệnh 2 — Chốt thêm",
            "type": "LO",
            "side": "Bán",
            "qty": qty - half_qty - small_qty,
            "price": round_to_tick(bull_target * 0.95),
            "note": "Đặt chờ tại vùng kháng cự gần nhất",
            "trigger": f"Khi giá đạt {round_to_tick(bull_target * 0.95):,.0f}đ",
            "pnl_est": (round_to_tick(bull_target * 0.95) - cost_price) * (qty - half_qty - small_qty),
        },
        {
            "name": "Lệnh 3 — Giữ dài hạn",
            "type": "Trailing Stop",
            "side": "Bán",
            "qty": small_qty,
            "price": bull_target,
            "note": f"Stop dưới {round_to_tick(cost_price * 0.95):,.0f}đ",
            "trigger": "Trailing stop -7% từ đỉnh mới",
            "pnl_est": (bull_target - cost_price) * small_qty,
        },
        {
            "name": "Stop Loss",
            "type": "LO",
            "side": "Bán",
            "qty": qty,
            "price": stop,
            "note": "BẮT BUỘC — kích hoạt nếu giá thủng mức này",
            "trigger": f"Giá đóng cửa < {stop:,.0f}đ",
            "pnl_est": pnl(stop),
        },
    ]

    return {
        "symbol":         symbol,
        "cost_price":     cost_price,
        "market_price":   close,
        "qty":            qty,
        "current_pnl":    (close - cost_price) * qty,
        "current_pnl_pct":(close / cost_price - 1) * 100 if cost_price > 0 else 0,

        "signal_score":   signal_score,
        "signal_label":   signal_label,
        "signal_color":   sig.get("color", "#6B7280"),
        "rsi":            sig.get("rsi", 50),
        "macd_hist":      sig.get("macd_hist", 0),

        "bull_target":    bull_target,
        "base_target":    base_target,
        "bear_target":    bear_target,
        "stop_loss":      stop,

        "probs":          probs,
        "ev_hold":        ev_hold,
        "ev_exit":        ev_exit,

        "rr_bull":        round(rr_bull, 2),
        "rr_base":        round(rr_base, 2),

        "pnl_bull":       pnl(bull_target),
        "pnl_base":       pnl(base_target),
        "pnl_bear":       pnl(bear_target),

        "primary_action": primary_action,
        "action_color":   action_color,
        "orders":         orders,

        "analyst_target": analyst_target,
        "support_levels": support_levels,
        "resistance_levels": resist_levels,
    }


# ─── ORDER BUILDER ────────────────────────────────────────────────────────────

HOSE_SESSIONS = {
    "ATO":        ("08:30", "09:00", "Đặt lệnh ATO — khớp giá mở cửa"),
    "Liên tục 1": ("09:00", "11:30", "Phiên liên tục sáng — LO/MP"),
    "Nghỉ trưa":  ("11:30", "13:00", "Nghỉ trưa — không khớp lệnh"),
    "Liên tục 2": ("13:00", "14:30", "Phiên liên tục chiều — LO/MP"),
    "ATC":        ("14:30", "15:00", "Đặt lệnh ATC — khớp giá đóng cửa"),
    "Sau phiên":  ("15:00", "23:59", "Ngoài giờ — lệnh chờ phiên sau"),
}

def current_session() -> tuple[str, str]:
    """Return (session_name, description) for current time (Hanoi/HCMC time)."""
    now = dt.datetime.now()
    t   = now.strftime("%H:%M")
    for name, (start, end, desc) in HOSE_SESSIONS.items():
        if start <= t < end:
            return name, desc
    return "Ngoài giờ", "Lệnh đặt sẽ có hiệu lực từ phiên ATO ngày hôm sau"


def build_lo_instruction(
    symbol: str,
    side: str,           # "Mua" | "Bán"
    qty: int,
    target_price: float,
    note: str = "",
) -> dict:
    """
    Build a complete LO (Limit Order) instruction with all HOSE-specific details.
    Returns a dict ready for display in the Trade Planner UI.
    """
    price = round_to_tick(target_price)
    value = price * qty
    session, session_desc = current_session()

    # Slippage estimate: assume 0.3% for LO on liquid stocks
    slippage_est = round(price * 0.003 * qty)
    brokerage    = round(value * 0.0015)   # typical 0.15% SSI fee
    net_proceeds = value - brokerage if side == "Bán" else value + brokerage + slippage_est

    return {
        "symbol":        symbol,
        "order_type":    "LO",
        "side":          side,
        "qty":           qty,
        "price":         price,
        "value":         value,
        "session":       session,
        "session_desc":  session_desc,
        "slippage_est":  slippage_est,
        "brokerage_est": brokerage,
        "net_proceeds":  net_proceeds,
        "note":          note,
        "steps": [
            "Đăng nhập SSI iBoard → tab 'Đặt lệnh'",
            f"Mã CK: {symbol}",
            "Loại lệnh: LO (Limit Order)",
            f"Chiều: {side}",
            f"Khối lượng: {qty:,} CP",
            f"Giá: {price:,.0f} đ (bước giá 100đ ✓)",
            "Xác nhận PIN/OTP → Trạng thái: Chờ khớp",
        ],
        "important": [
            f"LO chỉ khớp khi giá thị trường {'≤' if side == 'Mua' else '≥'} {price:,.0f}đ",
            "Lệnh hết hiệu lực cuối phiên — cần đặt lại ngày hôm sau nếu chưa khớp",
            "Phiên ATC (14:30–15:00): LO không khớp trong ATC — tránh đặt mới lúc này",
            f"Phí dự kiến: {brokerage:,.0f}đ (0.15%)",
        ]
    }
