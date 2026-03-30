# TRADING OS — ALPHA PROPOSAL v1.0
## Hệ Điều Hành Giao Dịch Định Lượng Thị Trường Chứng Khoán Việt Nam

> **Tổng hợp từ toàn bộ research proposals + phân tích mâu thuẫn + nghiên cứu thực tiễn VN market**
> **Phiên bản:** v1.0 | **Ngày:** 30/03/2026 | **Dự án:** TradingOS Alpha

---

# MỤC LỤC

- [PHẦN I — BỐI CẢNH VĨ MÔ VÀ THỊ TRƯỜNG](#phần-i)
- [PHẦN II — NGHIÊN CỨU & GIẢI QUYẾT MÂU THUẪN](#phần-ii)
- [PHẦN III — FINAL UNIFIED ALGORITHM](#phần-iii)
- [PHẦN IV — KIẾN TRÚC HỆ THỐNG](#phần-iv)
- [PHẦN V — KẾ HOẠCH TRIỂN KHAI 5 PHASES](#phần-v)
- [PHẦN VI — BẢNG QUYẾT ĐỊNH MÂU THUẪN](#phần-vi)
- [PHẦN VII — RỦI RO & COMPLIANCE](#phần-vii)
- [PHẦN VIII — BACKLOG BỔ SUNG (13 ITEMS)](#phần-viii)

---

# PHẦN I — BỐI CẢNH VĨ MÔ VÀ THỊ TRƯỜNG {#phần-i}

## 1.1 Các Chỉ Số Trọng Yếu 2025–2026

| Chỉ số | Giá trị | Ý nghĩa cho Trading OS |
|---|---|---|
| GDP tăng trưởng | 8.0–8.5% | NPAT doanh nghiệp tăng 14–20% |
| Tăng trưởng EPS (dự báo) | 14.5–26.7% | Xác nhận giai đoạn Markup Wyckoff |
| P/E Forward 2026 | 12.5x–13.9x | Dưới trung bình 10 năm (14.0x) → dư địa re-rating |
| VN-Index mục tiêu | 1,920–2,300 điểm | Kịch bản baseline và optimistic |
| Nâng hạng FTSE | Tháng 9/2026 | Catalyst thu hút 6–8 tỷ USD vốn ngoại |
| Lãi suất SBV | 4.5–5.0% | Hỗ trợ thanh khoản + chi phí vốn margin |
| Thanh khoản bình quân | ~29.5 nghìn tỷ VND/phiên | Đủ cho algorithmic trading không gây slippage |

> **VN30 Rebalancing Risk:** VN30 được tái cơ cấu 2 lần/năm (tháng 1 và tháng 7). Trước kỳ rebalancing ~2 tuần: mã bị loại khỏi VN30 thường bị bán tháo; mã mới vào thường bị mua đuổi. `sector_map` cần update sau mỗi kỳ rebalancing. Đây là **event risk** — reduce position sizing nếu holding mã gần ranh giới VN30 trong tháng 1 và tháng 7.

## 1.2 Cơ Chế T+2.5 và Liquidity Singularity

| Mốc thời gian | Sự kiện | Tác động chiến lược |
|---|---|---|
| T+0 08:45 | Pre-open (đặt/sửa lệnh ATO) | Có thể quan sát imbalance sớm — không khớp |
| T+0 09:00–09:15 | ATO session | Khớp theo giá mở — **monitor only**, slippage không kiểm soát |
| T+0 09:15 | Entry window mở | Khớp lệnh liên tục bắt đầu |
| T+0 11:30 | Nghỉ trưa | Lệnh không khớp — hủy lệnh treo nếu cần |
| T+0 13:00 | Phiên chiều mở | MTL order khả dụng (HOSE only) |
| T+2 11:30–12:30 | VSDC (VSD) clearing hoàn tất | Cổ phiếu T+0 về tài khoản |
| T+2 12:45–13:15 | **T+2.5 Danger Window** | Áp lực bán T+0 từ ngày trước; monitor và có thể exit sớm |
| T+2 13:00 | **Liquidity Singularity** | Áp lực bán đồng loạt — intraday volatility peak |
| T+2 14:05–14:20 | **Optimal entry window chiều** | Hàng T+2 đã hấp thụ, trend xác lập |
| T+2 14:30–14:45 | ATC window | Execution tối ưu exit hoặc entry ATC |

### T+0 Same-Day Trading (HOSE, từ 11/2024)

> **VSD cho phép bán cổ phiếu mua cùng ngày từ T+0 kể từ tháng 11/2024 tại HOSE.**

| Điểm | Chi tiết |
|---|---|
| Điều kiện bật | `account_has_t0 = True` trong config (không phải mọi broker hỗ trợ) |
| Cơ chế | Broker credit trước cổ phiếu dựa trên lệnh mua đã khớp |
| Giới hạn | Chỉ bán được trong cùng phiên liên tục (không bán ATC nếu mua ATO) |
| Rủi ro | Broker charge phí T+0 riêng + lãi suất tín dụng nội ngày |
| **Impact Strategy** | Nếu T+0 enabled: cho phép intraday cut-loss ngay nếu Spring fail; không cần giữ đến T+2 |
| **Backtest flag** | `T0_SAME_DAY_SELL = config.get("account_has_t0", False)` |

## 1.3 Biên Độ Dao Động — Thực Tế Cơ Chế

| Sàn | Biên độ | Ceiling | Floor | Đặc biệt |
|---|---|---|---|---|
| HOSE | ±7% | ref × 1.07 | ref × 0.93 | IPO 5 phiên đầu: ±20% |
| HNX | ±10% | ref × 1.10 | ref × 0.90 | Phiên đầu sau treo: ±20% |
| UPCOM | ±15% | ref × 1.15 | ref × 0.85 | Mã mới: ±40% |

> **Trading OS không trade UPCOM** — spread rộng, liquidity thấp, dễ bị thao túng.

---

# PHẦN II — NGHIÊN CỨU & GIẢI QUYẾT MÂU THUẪN {#phần-ii}

## 2.1 Mâu Thuẫn Stop-Loss: -5% vs -7% vs ATR

### Nguồn gốc mâu thuẫn
- **-7~8% (O'Neil CAN SLIM):** Thiết kế cho US market, không có circuit breaker, hold 3–13 tuần
- **-5% (MFPM T+2.5):** Thiết kế cho HOSE ±7%, hold 2–8 ngày

### Phân tích thực nghiệm VN 2020–2025
- Với swing 3–7 ngày: -5% stop outperforms -7% (Sharpe +0.15–0.25) do herding effect
- -7% trên HOSE = mất gần 1 biên độ → cho phép cổ phiếu gần sàn trước khi cắt
- EMA(20) break trigger tại ~3.5–4.5% → hiệu quả hơn con số cứng

### Kết luận — Phân tầng theo timeframe

| Chiến lược | Timeframe | Stop Mechanism |
|---|---|---|
| T+2.5 Swing | 2–8 ngày | ATR×1.5 HOẶC EMA(20) break (đến trước) + hard cap -7% |
| CAN SLIM Mid-term | 3–13 tuần | -7% cứng HOẶC SMA(50) break |
| Trailing (sau +7%) | Mọi | Max(High) × (1 − 0.05) |

```python
# Reconciled stop-loss formula
sl_atr     = entry - 1.5 * ATR14
sl_ema     = EMA(close, 20)
sl_hard    = entry * 0.93       # hard cap -7% (HOSE worst-case sàn)
final_sl   = max(sl_atr, sl_ema, sl_hard)  # lấy mức gần entry nhất
```

---

## 2.2 Mâu Thuẫn RSI Trigger: 40 vs 50–65 vs Adaptive

### Phân tích — 3 điểm khác nhau trên cùng 1 chart

```
RSI 80 ─────────────              ← CLIMAX EXIT (mới — từ proposal cuối)
RSI 70 ─────────────   /──────    ← Overbought exit
RSI 65 ─────────────  /
RSI 55 ─────────────  /           ← BREAKOUT ZONE (Mode B, 50-65)
RSI 50 ─────────────/─────
RSI 45 ─────────────              ← PULLBACK VALID (Mode A extended)
RSI 42 ─────────────              ← Mode A original trigger
RSI 30 ─────────────    \__/      ← Oversold deep
```

### Đặc thù thị trường VN
- Retail-dominated (>80% volume) → RSI oscillation biên độ rộng hơn US
- RSI 40–50 VN tương đương RSI 30–40 US market
- T+2.5 momentum decay: RSI 65+ thường đảo chiều nhanh do chốt lời T+0

### Kết luận — Adaptive RSI Thresholds

| Regime (HMM) | Entry Zone | Confirmation | Exit |
|---|---|---|---|
| Steady Bull | RSI pullback về 40–50 | Vượt 50, giữ vững | RSI > 80 và declining |
| Sideways | RSI ≤ 42 cross-up | Volume Z-score > 1.5 | RSI chạm 65 |
| Volatile Bear | Không entry | N/A | Thoát ngay nếu RSI < 40 |
| T+ Swing | RSI 50–65 | Volume > 1.5×MAV | RSI chạm 70 |

```python
# Mode A mở rộng
if rsi_crossup_from <= 42:  mfpm_bonus = 30   # oversold sâu — tín hiệu mạnh
elif rsi_crossup_from <= 50: mfpm_bonus = 20  # pullback hợp lệ

# Exit RSI — trigger mới
if rsi > 80 and rsi < rsi_prev:
    return ExitSignal.RSI_CLIMAX_EXIT
```

---

## 2.3 Mâu Thuẫn Take-Profit: Fibonacci vs Cố Định 15% vs ATR

### Phân tích từng phương pháp

| Phương pháp | Vấn đề | Kết luận |
|---|---|---|
| Fibonacci 1.618/2.618 | Phụ thuộc wave counting — không tự động hóa đáng tin cậy trên VN | **Dùng CÓ ĐIỀU KIỆN với Hurst Exponent** |
| Cố định 15% | Không thích nghi volatility — cùng quy tắc nhưng risk-adjusted return khác nhau | **Loại bỏ** |
| ATR-based | Thích nghi tự động. Backtesting VN30 2020–2025: Sharpe +0.18 vs fixed 15% | **Primary method** |

### Kết luận — TP Hybrid với Hurst Gate

$$H = \frac{\log(R/S)}{\log(n)}$$

| Hurst (H) | Ý nghĩa | TP Strategy |
|---|---|---|
| H > 0.55 | Trending mạnh | TP2 = Fibonacci 2.618 (capped 25%) |
| 0.45 ≤ H ≤ 0.55 | Random walk | TP2 = 3.5 × ATR14 |
| H < 0.45 | Mean-reverting | TP2 = Fibonacci 1.618 (chốt nhanh) |

```python
def calculate_tp(entry, atr14, hurst, swing_low=None):
    """swing_low: swing low gần nhất — cần thiết cho Fibonacci extension.
    Nếu không có, fallback về ATR-only cho cả TP1 và TP2."""
    # TP1 — ATR-based always
    tp1 = max(entry + 2.0 * atr14, entry * 1.10)
    tp1 = min(tp1, entry * 1.18)

    # TP2 — Hurst-gated hybrid
    if hurst > 0.55 and swing_low is not None:
        fib_target = fibonacci_extension(swing_low, entry, ratio=2.618)
        tp2 = min(fib_target, entry * 1.25)
    elif hurst < 0.45 and swing_low is not None:
        fib_target = fibonacci_extension(swing_low, entry, ratio=1.618)
        tp2 = min(fib_target, entry * 1.22)
    else:
        tp2 = max(entry + 3.5 * atr14, entry * 1.17)
        tp2 = min(tp2, entry * 1.25)

    return tp1, tp2
```

---

## 2.4 Framework Layering — Giải Quyết Xung Đột Wyckoff + CAN SLIM + MFPM

Ba framework hoạt động ở 3 timeframe khác nhau — xung đột xảy ra khi áp dụng vào cùng một decision point.

```
TẦNG 1 — MACRO REGIME (Weekly/Monthly)
    ├── HMM 3-state: Steady Bull | Volatile Bear | Sideways
    ├── GMO Ω: S&P500 + DXY + Oil + SBV + VNI
    ├── VN30F Basis: Premium(+)/Discount(-) indicator
    ├── Hurst Exponent: trending vs mean-reverting
    └── Output: RISK_ON | CAUTIOUS | RISK_OFF

    ─────────────────────────────────────────────

TẦNG 2 — UNIVERSE SELECTION (Weekly scan)
    ├── Liquidity filter: 200–280 mã HOSE+HNX
    ├── CAN SLIM score: → 60–80 watchlist
    ├── FOL status: FOREIGN_BUY | NEUTRAL | ROOM_DAY
    └── Output: Watchlist + CAN SLIM Score

    ─────────────────────────────────────────────

TẦNG 3 — ENTRY TIMING (Daily/Intraday)
    ├── MFPM Mode A: Pullback (RSI cross-up ≤50)
    ├── MFPM Mode B: Breakout (RSI 50-65 + Pivot break)
    ├── VCP Pattern + Wyckoff Spring + Weis Wave
    ├── Monte Carlo: GBM 1000 simulations win probability gate
    └── Output: Signal + Entry/SL/TP

    ─────────────────────────────────────────────

TẦNG 4 — EXECUTION (Intraday)
    ├── ATO (09:00–09:15): monitor only
    ├── Morning entry: 09:15–11:30
    ├── T+2.5 danger: 12:45–13:15 (monitor/exit)
    ├── Afternoon entry: 14:05–14:20
    ├── ATC Router: 14:30–14:45
    └── Output: Lệnh cụ thể (giá, qty, loại LO/ATC/MTL)
```

---

## 2.5 Phân Tích Biên Độ ±7% HOSE / ±10% HNX trong Thuật Toán

### Tác động 1 — Entry Gate
```python
def circuit_breaker_gate(close, ref_price, exchange):
    bands = {'HOSE': 0.07, 'HNX': 0.10, 'UPCOM': 0.15}
    band  = bands[exchange]
    ceiling = ref_price * (1 + band)
    floor   = ref_price * (1 - band)

    if close >= ceiling * 0.99:
        return "REJECT", "Giá tại trần — không còn upside"
    if close <= floor * 1.01:
        return "REJECT", "Giá tại sàn — nguy hiểm thanh khoản"
    if (ceiling - close) / close < 0.02:
        return "FLAG", "Gần trần — hạn chế upside <2%"
    return "OK", None
```

### Tác động 2 — Position Sizing Worst-Case
```python
# Stop không phải lúc nào cũng khớp được — gap down/lock sàn
max_loss_per_share = entry * band  # 0.07 HOSE / 0.10 HNX
max_qty_by_risk    = (equity * 0.02) / max_loss_per_share
qty = min(kelly_qty, max_qty_by_risk)
qty = (qty // 100) * 100  # round down to 100-lot
```

### Tác động 3 — Trailing Stop Floor
```python
# Trailing stop không nhỏ hơn 3.5% với HOSE (intraday noise ~1.5–3%)
trailing_sl = max(high_since_entry * 0.95, entry * 0.965)
```

---

## 2.6 FOL (Foreign Ownership Limit) trong Thuật Toán

### Cơ chế thực tế

| Ngành | FOL tối đa |
|---|---|
| Hầu hết ngành thông thường | 49% |
| Ngân hàng thương mại | 30% |
| Quốc phòng, truyền thông | 0% (cấm) |

### FOL Analysis Module

```python
def fol_analysis(ticker, quote, threshold: int = 100_000):
    foreign_pct   = quote['foreignCurrentPercent']
    foreign_limit = quote['foreignPercent']
    room_pct      = (foreign_limit - foreign_pct) / foreign_limit
    net_buy       = quote['foreignBuyQtty'] - quote['foreignSellQtty']

    # ⚠️ Thứ tự if/elif quan trọng: kiểm tra điều kiện hẹp trước
    if room_pct < 0.05 and net_buy < -threshold:
        # Room gần cạn NHƯNG NN đang bán ròng → room mở lại → cơ hội dip entry
        status = "FOL_DIP_ENTRY"
    elif room_pct < 0.05:
        # Room cạn + NN không mua/bán rõ → tín hiệu khối lượng NN không đáng tin
        status = "ROOM_DAY"
    elif room_pct > 0.30 and net_buy > threshold:
        # Room rộng + NN mua ròng mạnh → tín hiệu xác nhận tốt
        status = "FOREIGN_BUY"
    else:
        status = "NEUTRAL"

    return status, room_pct, net_buy
```

### NPF Settlement Failure Flag (KRX)

```python
def check_npf_flag(
    ticker: str,
    npf_violations_db: dict,
    suspension_days: int = 7,
) -> dict:
    """
    NPF (Non-pre-funding) Settlement Failure Guard.
    Per Circular 08/2026/TT-BTC (pending final regulatory verification).

    Logic: Nếu tổ chức nước ngoài fail-to-settle trong rolling 90 ngày,
    hệ thống tạm ngưng tín hiệu FOREIGN_BUY cho mã đó trong 7 phiên.

    npf_violations_db example: {"HPG": [{"date": date(2026,3,28),
                                         "entity": "EV_FUND_X",
                                         "settled": False}]}
    """
    from datetime import date, timedelta
    today = date.today()
    cutoff = today - timedelta(days=90)
    recent_fails = [
        v for v in npf_violations_db.get(ticker, [])
        if not v["settled"] and v["date"] >= cutoff
    ]
    if recent_fails:
        latest_fail = max(v["date"] for v in recent_fails)
        suspended_until = latest_fail + timedelta(days=suspension_days)
        if today <= suspended_until:
            return {
                "npf_flag"        : True,
                "suspended_until" : str(suspended_until),
                "reason"          : f"NPF fail {latest_fail} — FOL_FOREIGN_BUY penalized",
                "mfpm_adjustment" : -10,  # reduce foreign confirmation score
            }
    return {"npf_flag": False, "mfpm_adjustment": 0}
```

> **Implementation note:** `npf_violations_db` populated from SSI EP-10 corporate events or
> exchange bulletin. Circular 08/2026/TT-BTC cited — verify exact circular number before production.
> If data unavailable: default `npf_flag = False` (conservative pass).

### FOL Integration vào MFPM Score

| Điều kiện | Điểm MFPM |
|---|---|
| room_pct > 30% + foreign net buy > 0 | +10 |
| status = FOL_DIP_ENTRY (room mở lại) | +8 |
| status = ROOM_DAY + foreign net buy = 0 | -5 |
| status = ROOM_DAY + foreign net sell | -15 |

---

## 2.7 ATO / ATC Sessions trong Thuật Toán

### ATO (09:00–09:15) — Monitor Only

```python
if current_time < "09:15":
    mode = "ATO_MONITOR_ONLY"
    # Không khớp lệnh — slippage không kiểm soát được
    # Tính ATO gap: (ATO_price - ref) / ref
    # Nếu gap > 3%: cảnh báo "đã đuổi" — reject signal
    ato_gap_flag = abs(ato_price - ref_price) / ref_price > 0.03
```

### ATC Router (14:30–14:45) — Expected Closing Price

$$ECP = \arg\max_P \left[\min(Q_{buy}(P),\ Q_{sell}(P))\right]$$

```python
def smart_atc_router(position, order_book, current_time):
    ecp           = calculate_ecp(order_book)     # EP-4 SSI iboard-query
    last_continuous = last_matched_price
    # Imbalance = tỷ lệ lệnh mua/bán trong phiên ATC (không dùng total day volume)
    atc_total     = max(buy_qty_atc + sell_qty_atc, 1)
    imbalance     = (buy_qty_atc - sell_qty_atc) / atc_total

    # Aggressive SELL — chốt lời T+ hoặc cắt lỗ khẩn cấp
    if position.unrealized_pnl >= target_pct and current_time >= "14:43:00":
        submit_ATC_sell()        # time priority

    # Aggressive BUY — Spring/Breakout trong phiên ATC
    if breakout_signal and ecp < last_continuous and imbalance > 0.30:
        if "14:40:00" <= current_time < "14:44:30":
            submit_ATC_buy()     # đón đầu Gap Up ngày T+1

    # Anti-Manipulation Gate
    if abs(ecp - last_continuous) / last_continuous > 0.025:
        cancel_all_atc_orders()
        log_warning("ATC_MANIPULATION_DETECTED")

    # --- MTL (Market-to-Limit) Handling — KRX standard on HOSE ---
    # MTL fills against best available contra-orders; any unfilled remainder
    # automatically converts to LO at the last matched price.
    # This replaces the deprecated MP (Market Price) order type on HOSE post-KRX.
    #
    # KRX Auction Priority Note:
    #   • ATO/ATC run in SEPARATE auction phases — they do NOT compete with
    #     continuous LO for time-priority.
    #   • Within continuous session: earlier LO at same price level takes
    #     time priority over later LO (standard price-time-priority rule).
    #   • At ceiling/floor: multiple LO at same price queued by arrival time;
    #     ATO/ATC input timestamps used only within their own auction phase.
    #
    # Fat-finger Protection: reject MTL order if qty > 5× avg_vol_5m or
    # if expected fill would move price > 1.5% from last traded.
    def submit_mtl(
        side: str, qty: int, last_price: float, avg_vol_5m: float
    ):
        if qty > avg_vol_5m * 5:
            log_warning("FAT_FINGER_BLOCKED", qty=qty)
            return
        price_impact_est = qty / max(avg_vol_5m, 1) * 0.002  # rough estimate
        if price_impact_est > 0.015:
            log_warning("PRICE_IMPACT_HIGH", est=price_impact_est)
            return
        return {"type": "MTL", "side": side, "qty": qty}
```

---

## 2.8 Universe Selection — Lọc Tối Thiểu 200 Mã

### Cascade Lọc

```python
def build_universe():
    # Step 1: HOSE + HNX (~830 mã) — bỏ UPCOM
    universe = fetch_all_tickers(exchanges=["HOSE", "HNX"])

    # Step 2: Liquidity gate — tiered by exchange
    # HNX liquidity tự nhiên thấp hơn HOSE: ngưỡng riêng để giữ diversity
    def _liq_gate(t):
        min_vol = 100_000 if exchange_of(t) == "HNX" else 500_000
        return avg_vol_20d(t) >= min_vol
    universe = [t for t in universe if _liq_gate(t)]

    # Step 3: Price / cap filter
    universe = [t for t in universe if price(t) >= 5_000]
    universe = [t for t in universe if market_cap(t) >= 500_000_000_000]  # 500 tỷ VND

    # Step 4: Data quality
    universe = [t for t in universe if len(ohlcv(t)) >= 200]

    # Step 5: Not suspended (ST/UT/HA)
    universe = [t for t in universe if trade_status(t) not in ['ST','UT','HA']]

    # Step 5b: PCA (Periodic Continuous Auction) — KRX restricted stocks
    # PCA stocks trade in 15 rounds × 15-minute auctions instead of continuous session.
    # Exclude from auto-signal generation; display [PCA] label in UI for manual review.
    # Cancellation/edit blocked in final 5 min of each PCA round (enforce in atc_router).
    pca_tickers = fetch_pca_restricted_tickers()  # from SSI EP-2 status field or exchange bulletin
    pca_set     = set(pca_tickers)
    universe    = [t for t in universe if t not in pca_set]
    # Note: pca_tickers flagged in watchlist table (status='PCA') for manual oversight

    # Dynamic threshold adjustment
    if len(universe) < 200:
        # Hạ ngưỡng volume xuống 300,000
        universe = rebuild(min_volume=300_000)
    elif len(universe) > 280:
        # Nâng ngưỡng lên 700,000
        universe = rebuild(min_volume=700_000)

    return universe  # target: 200–280 mã
```

### CAN SLIM Weekly Filter (từ 200+ → 60–80 watchlist)

| Tiêu chí | Điều kiện VN-Adjusted | Điểm |
|---|---|---|
| **C** — Current Quarterly EPS | Tăng ≥ 15% YoY | 20 |
| **A** — Annual EPS | Tăng ≥ 10% liên tiếp 3 năm + ROE ≥ 17% | 15 |
| **N** — New High | Trong 5% của 52W high hoặc vừa phá + new catalyst | 15 |
| **S** — Supply/Demand | Z_vol > 1.5 trong 5 phiên; ưu tiên midcap float thấp | 15 |
| **L** — Leader | RS Rating > 70 (top 30% vs VNI); tránh laggards | 20 |
| **I** — Institutional | Foreign ownership tăng QoQ (SSI EP-10) | 10 |
| **M** — Market | SMA(50) > SMA(200) | **GATE** (loại nếu fail) |

```python
# RS Rating — composite theo O'Neil (xấp xỉ IBD methodology)
# Weights: 40% × 3-tháng + 20% × 6-tháng + 20% × 9-tháng + 20% × 12-tháng
# ⚠️ 4-week only là quá ngắn hạn và volatile cho universe selection

def compute_rs_rating(prices, universe_prices):
    """prices: Series of close for 1 ticker; universe_prices: dict {ticker: Series}"""
    def composite_return(s):
        w3  = s.pct_change(63).iloc[-1]   # ~3 tháng (63 phiên)
        w6  = s.pct_change(126).iloc[-1]  # ~6 tháng
        w9  = s.pct_change(189).iloc[-1]  # ~9 tháng
        w12 = s.pct_change(252).iloc[-1]  # ~12 tháng
        return 0.40 * w3 + 0.20 * w6 + 0.20 * w9 + 0.20 * w12

    ticker_score = composite_return(prices)
    all_scores   = [composite_return(p) for p in universe_prices.values()]
    return percentile_rank(ticker_score, all_scores)  # 1–99

# Chạy cuối tuần, dùng cho cả tuần tiếp theo
# Output: mã có CAN SLIM Score ≥ 50 → Watchlist
```

---

# PHẦN III — FINAL UNIFIED ALGORITHM {#phần-iii}

## Module 0: Data Ingestion Daemon (Rust + io_uring)

### 0.1 Mục Đích

Tách biệt **hot-path data collection** khỏi Python analytics pipeline. Binary Rust chạy nền liên tục, thu thập dữ liệu từ SSI iBoard API và ghi vào shared DuckDB file. Python app chỉ **đọc** từ DuckDB — không polling HTTP trong analytics hot path.

### 0.2 Pipeline

```
SSI iBoard API (HTTP polling)
    │
    ▼  [Rust daemon — io_uring zero-copy recv (Linux) / Tokio IOCP (Windows)]
    ├── EP-3 quotes:        200 ms polling interval (09:00–15:00 VN)
    ├── EP-6 breadth stats: 5-min refresh
    └── EP-7 index stats:   5-min refresh
         │
         ▼  [DuckDB WAL mode — concurrent Python reads safe]
         ohlcv_5m · ohlcv_daily · sector_map  (TTL managed by daemon)
              │
              ▼  [Python → IndicatorEngine → MFPM → UI]
```

### 0.3 Performance Targets (Data Layer)

| Metric | Target | Ghi chú |
|---|---|---|
| Network hop: SSI server → daemon buffer | **≤ 3.9 ms** P50 | io_uring zero-copy recv |
| End-to-end: SSI response → DuckDB write | **< 100 ms** | Deserialize + INSERT |
| Quote polling interval (market hours) | 200 ms | EP-3, batch 50 tickers/req |
| Analytics pipeline P50 (Python) | 2–5 s | **Không thay đổi** |
| Full scan 200 mã P50 (Python) | 35–75 s | **Không thay đổi** |

> **Separation of concerns:** Rust daemon chịu trách nhiệm data freshness; Python app giả định DuckDB luôn fresh ≤ 100 ms trong giờ giao dịch.

### 0.4 Implementation Sketch

```rust
// data/collector_daemon/src/main.rs
// Linux: tokio-uring 0.4+ (io_uring, kernel ≥ 5.1)
// Windows: tokio 1.x + IOCP fallback (cfg(target_os = "windows"))

async fn poll_and_write(
    tickers: &[&str],
    conn: &duckdb::Connection,
) -> anyhow::Result<()> {
    let resp = http_get_uring(SSI_EP3_URL, tickers).await?;  // io_uring recv
    let rows: Vec<QuoteRow> = serde_json::from_slice(&resp)?;
    conn.execute_batch("INSERT OR REPLACE INTO ohlcv_5m ...")?; // DuckDB WAL
    Ok(())
}
```

**Cargo deps:** `tokio-uring 0.4` · `duckdb 0.9` · `serde_json 1.x` · `anyhow 1.x`

---

## Module 1: Global Macro Overlay (GMO)

### 1.1 HMM — Primary Regime Detector

Sử dụng Hidden Markov Model với 3 hidden states, input = [daily_return, realized_volatility_10d]:

| State | Returns | Volatility | Action |
|---|---|---|---|
| **Steady Bull** | Dương, ổn định | Thấp | Full MFPM, nới TP |
| **Volatile Bear** | Âm | Cực cao | Cash + Short VN30F hedge |
| **Sideways** | ~0 | Trung bình | Swing: mua Spring, bán TP1 nhanh |

```python
from hmmlearn import hmm
import numpy as np

def fit_hmm(features: np.ndarray) -> hmm.GaussianHMM:
    """
    Fit GaussianHMM với state-pinning để ngăn label switching.
    Label switching: khi thêm data mới, state 0/1/2 có thể đổi nghĩa.
    Fix: sau fit, sort states theo emission mean[0] (returns) tăng dần
         → state 0 = Bear (return thấp nhất), state 2 = Bull (cao nhất)
    """
    model = hmm.GaussianHMM(n_components=3, covariance_type="full",
                             n_iter=300, random_state=42)
    model.fit(features)

    # Pin state order: sort by emission mean return (feature[0])
    order = np.argsort(model.means_[:, 0])   # ascending return
    # Reorder means, covars, transmat
    model.means_  = model.means_[order]
    model.covars_ = model.covars_[order][:, order] if model.covars_.ndim == 3 else model.covars_[order]
    model.transmat_ = model.transmat_[order][:, order]
    model.startprob_ = model.startprob_[order]
    return model

# BEAR_STATE=0, SIDEWAYS_STATE=1, BULL_STATE=2 (pinned)
hmm_model     = fit_hmm(features)   # full history
current_state = hmm_model.predict(recent_obs)[-1]

# ⚠️ Monthly refit: HMM phải được re-fit hàng tháng với data mới nhất
# Lý do: emission parameters drift khi market regime thay đổi
# Schedule: đầu mỗi tháng giao dịch, fit lại trên rolling 3 năm
def monthly_refit_hmm(full_history: np.ndarray, window_years: int = 3) -> hmm.GaussianHMM:
    trading_days = 252 * window_years
    window_data  = full_history[-trading_days:]
    return fit_hmm(window_data)

# Transition probability
P_bear = hmm_model.predict_proba(recent_obs)[-1][0]  # state 0 = pinned Bear
if P_bear > 0.60:
    risk_state = "RISK_OFF"
    raise_cash_to(0.60)
    trigger_vn30f_short_hedge()
```

### 1.2 GMO Ω — Macro Sanity Check

$$\Omega = 0.30 \cdot S_{SP500} + 0.20 \cdot S_{DXY} + 0.15 \cdot S_{Oil} + 0.20 \cdot S_{SBV} + 0.15 \cdot S_{VNI}$$

Mỗi $S \in \{-1, 0, +1\}$:

| Factor | +1 | -1 |
|---|---|---|
| S&P500 | > SMA(50) | < SMA(50) × 0.97 |
| DXY | Giảm (VND strengthen) | Tăng > 1%/tuần |
| Oil | Biến động < 5%/tháng | Spike > 10% |
| SBV | Lãi suất ≤ 4.5% | Tăng lãi suất |
| VNI | > SMA(50) | < SMA(50) × 0.97 |

| Ω (final, sau breadth adjustment) | Trạng thái | Action |
|---|---|---|
| ≥ 0.4 | **RISK_ON** | Full position sizing |
| 0 ≤ Ω < 0.4 | **CAUTIOUS** | 50% position, chỉ Mode A |
| Ω < 0 | **RISK_OFF** | Không entry mới |

### 1.3 Market Breadth Supplement

```python
# Từ SSI EP-7 (market-stat)
advance_decline_ratio = num_advancing / num_declining

omega_adjustment = 0.0   # default: no adjustment

if vni_advancing and advance_decline_ratio < 1.0:
    flag = "NARROW_RALLY"   # VNI tăng nhưng breadth yếu → không đáng tin
    omega_adjustment = -0.1

if advance_decline_ratio > 1.5:
    omega_adjustment = +0.1

# ⚠️ Phải apply adjustment vào Ω cuối — không chỉ tính xong rồi bỏ
omega_final = omega + omega_adjustment
```

### 1.4 VN30F Basis Indicator

$$Basis = \frac{VN30F1M_{price} - VN30_{index}}{VN30_{index}} \times 100\%$$

| Basis | Ý nghĩa | Action |
|---|---|---|
| > +0.5% | Premium mạnh | Xác nhận RISK_ON |
| -0.2% đến +0.5% | Neutral | Không điều chỉnh |
| < -0.5% | Discount sâu — hedging | Thêm vào CAUTIOUS |

> **Nguồn dữ liệu VN30F:** Giá futures VN30F1M lấy từ SSI iboard EP-6 (`/stock/group/VN30`) hoặc trực tiếp từ HNX derivatives market (symbol `VN30F1M`). Nếu không có API trực tiếp, dùng EP-3 với symbol `VN30F1M` — điền vào `VN30F1M_price`. Nếu unavailable, bỏ qua Basis indicator và dùng only HMM + GMO Ω.

### 1.5 Herding Detection (Kalman Filter)

```python
# Áp dụng Kalman Filter vào cross-sectional return variance
# Variance → 0: tất cả cổ phiếu tăng/giảm đồng loạt = herding cực đoan

# ⚠️ herding_threshold KHÔNG hard-code — calibrate từ lịch sử
# Phương pháp: dùng percentile 10% của historical cross-variance
# (10% thấp nhất = top 10% herding sessions trong history)
def calibrate_herding_threshold(historical_variances: list, percentile: float = 10) -> float:
    """Trả về ngưỡng herding = percentile thấp của historical variance."""
    return float(np.percentile(historical_variances, percentile))

# Ví dụ: herding_threshold = calibrate_herding_threshold(cross_var_history, percentile=10)
# Nếu chưa có history đủ 252 phiên: dùng tạm 0.0002 (empirical VN estimate)
herding_threshold = getattr(config, 'kalman_herding_threshold', 0.0002)

if kalman_cross_variance < herding_threshold:
    wyckoff_alert = "DISTRIBUTION_LIKELY"
    force_risk_off = True
```

---

## Module 2: Technical Indicators

### 2.1 Core Indicators

```python
# Trend
SMA50  = SMA(close, 50)
SMA200 = SMA(close, 200)
EMA20  = EMA(close, 20)
EMA9   = EMA(close, 9)

# Oscillators
RSI14  = RSI(close, 14)
MACD_hist = MACD(close, 12, 26, 9)['histogram']

# Volatility
ATR14  = ATR(high, low, close, 14)
BB_upper, BB_lower = BollingerBands(close, 20, 2)

# Volume
Z_vol  = (volume - volume.rolling(20).mean()) / volume.rolling(20).std()
MAV20  = volume.rolling(20).mean()
OBV    = OnBalanceVolume(close, volume)

# Trend strength
ADX14  = ADX(high, low, close, 14)
```

### 2.2 VWAP — Hai Vai Trò Khác Nhau

> **Phân biệt quan trọng:** VWAP xuất hiện ở hai ngữ cảnh trong TradingOS với input data và mục đích hoàn toàn khác nhau.

| Vai trò | Input data | TTL cache | Cột lưu | Dùng để |
|---|---|---|---|---|
| **Intraday VWAP** (tích lũy phiên) | `ohlcv_5m` 5-min bars | 5 phút | Computed on-demand, không store | Entry timing: `close > VWAP_intraday?`; Tranche 2 gate; T+2.5 exit check |
| **Daily Typical Price** (end-of-day ref) | `ohlcv_daily` (H+L+C) | 24h | `typical_price_close` trong `indicators_daily` | Historical support/resistance ref; MFPM overnight scoring |

**Công thức chuẩn dùng Typical Price, không phải Close:**

$$VWAP = \frac{\sum (TP_i \times Volume_i)}{\sum Volume_i}, \quad TP_i = \frac{High_i + Low_i + Close_i}{3}$$

```python
def compute_vwap(df: pd.DataFrame, mode: str = "intraday") -> pd.DataFrame:
    """
    Hai chế độ:

    mode="intraday"  — df là chuỗi 5-min bars trong 1 ngày (từ ohlcv_5m).
                       VWAP reset lúc 09:00, tích lũy đến cuối phiên.
                       TTL cache = 5 phút. Dùng cho entry timing, Tranche 2
                       gate, T+2.5 exit check (close vs VWAP real-time).
                       → Computed on-demand; KHÔNG lưu vào indicators_daily.

    mode="daily_ref" — df là chuỗi daily bars (từ ohlcv_daily).
                       VWAP(daily) = Typical Price (H+L+C)/3 của từng ngày:
                       TP_i = (H+L+C)/3 — không có ý nghĩa cumsum vì mỗi
                       hàng là 1 ngày khác nhau.
                       Lưu vào cột `typical_price_close` trong indicators_daily.
                       Dùng như price reference overnight: close T-1 > TP T-1
                       → ngày hôm qua mua ròng vào cuối phiên.
    """
    # ⚠️ Dùng Typical Price (H+L+C)/3, không phải Close — đây là định nghĩa chuẩn VWAP
    df['TP']   = (df['High'] + df['Low'] + df['Close']) / 3
    df['TPxV'] = df['TP'] * df['Volume']

    if mode == "intraday":
        # Reset mỗi ngày giao dịch (groupby date) — CHỈ dùng với 5-min bars
        df['VWAP'] = (
            df['TPxV'].groupby(df.index.date).cumsum()
            / df['Volume'].groupby(df.index.date).cumsum()
        )
    else:  # daily_ref
        # Không cumsum — TP của mỗi ngày là independent reference
        # Lưu vào cột tên rõ ràng để tránh nhầm lẫn với intraday VWAP
        df['typical_price_close'] = df['TP']
        df['VWAP'] = df['TP']  # alias dùng trong MFPM scoring (overnight)
    return df
```

**Lưu ý triển khai:**
- `intraday VWAP`: tính trong `ProfilerService` khi user mở Full Profile hoặc
  tại các checkpoint entry/exit. Không persist vào DuckDB.
- `typical_price_close` (daily ref): lưu vào `indicators_daily.typical_price_close`.
  Column tên `vwap` trong DuckDB schema là **alias** của `typical_price_close`
  để backward-compat — xem DuckDB schema phần Data Models.

### 2.3 Hurst Exponent

```python
def hurst_exponent(series, min_lag=2, max_lag=100):
    # ⚠️ R/S analysis cần ít nhất max_lag × 2 data points để estimate ổn định
    # Với max_lag=100 → cần ≥ 200 điểm. Series ngắn hơn → H noisy, không reliable
    if len(series) < max_lag * 2:
        return 0.50    # không đủ data → neutral (0.5 = random walk)

    lags = list(range(min_lag, max_lag))
    tau  = [series.diff(lag).dropna().std() for lag in lags]
    # Loại bỏ lag có std=0 (flat series segment) tránh log(0)
    valid = [(l, t) for l, t in zip(lags, tau) if t > 0]
    if len(valid) < 5:
        return 0.50    # không đủ variation để fit

    valid_lags, valid_tau = zip(*valid)
    # ⚠️ np.polyfit(deg=1) trả về ndarray shape (2,) = [slope, intercept]
    # KHÔNG unpack 3 giá trị — sẽ raise ValueError
    poly = np.polyfit(np.log(valid_lags), np.log(valid_tau), 1)
    H    = float(poly[0])                     # slope = Hurst Exponent
    return float(np.clip(H, 0.0, 1.0))        # clamp [0,1] — giá trị hợp lệ
```

### 2.4 RSI Cross-Up Detector

```python
def rsi_crossup(rsi_series, level=42):
    return (rsi_series.shift(1) < level) & (rsi_series >= level)
```

### 2.5 Swing Low Auto-Detection (dùng trong calculate_tp khi swing_low=None)

```python
def detect_swing_low(df, lookback: int = 20) -> float:
    """
    Tự động phát hiện đáy cục bộ (swing low) trong lookback bars.
    Dùng làm anchor cho fibonacci_extension khi không có external swing_low.

    Logic: không phải chỉ min() — tìm đáy có confirmation (nến trước và sau đều cao hơn)
    Fallback nếu không tìm được pivot: dùng min của toàn bộ lookback window.
    """
    lows = df['Low'].iloc[-lookback:-1].values   # bỏ nến hiện tại
    # Tìm pivot low: lows[i] < lows[i-1] và lows[i] < lows[i+1]
    pivot_lows = [lows[i] for i in range(1, len(lows) - 1)
                  if lows[i] < lows[i-1] and lows[i] < lows[i+1]]
    return float(min(pivot_lows)) if pivot_lows else float(min(lows))
```

### 2.6 Fibonacci Extension (hàm thiếu — gọi trong calculate_tp)

```python
def fibonacci_extension(swing_low: float, swing_high: float, ratio: float) -> float:
    """
    Tính Fibonacci Extension target.
    Standard formula: target = swing_high + (swing_high - swing_low) × (ratio - 1)
    hoặc đơn giản hơn: target = swing_low + (swing_high - swing_low) × ratio

    Convention dùng trong TradingOS: từ đáy → đỉnh → extension
    swing_low  : đáy của đợt pullback (entry zone)
    swing_high : đỉnh trước pullback (pivot high / resistance)
    ratio      : 1.618 hoặc 2.618

    Ví dụ: swing_low=25000, swing_high=30000 → Fib 1.618 = 25000 + 5000×1.618 = 33090
    """
    move = swing_high - swing_low
    return swing_low + move * ratio
```

### 2.6 Pivot High Definition (dùng cho Mode B)

```python
def find_pivot_high(df, left_bars: int = 5, right_bars: int = 5) -> float:
    """
    Pivot High: nến giữa có High cao hơn tất cả left_bars bên trái
    và right_bars bên phải — xác nhận đỉnh kháng cự cục bộ.

    Mode B trigger: Close > pivot_high (phá kháng cự) với Volume surge
    Lookback: last 20–50 bars → dùng max của tất cả pivot highs trong vùng đó
    """
    highs  = df['High'].values
    pivots = []
    for i in range(left_bars, len(highs) - right_bars):
        if highs[i] == max(highs[i - left_bars: i + right_bars + 1]):
            pivots.append(highs[i])
    return max(pivots) if pivots else df['High'].iloc[-20:].max()  # fallback
```

### 2.7 Order Flow Imbalance (OFI) — từ EP-4 Order Book

```python
def compute_ofi(order_book: dict) -> float:
    """
    OFI = (Best Bid Volume - Best Ask Volume) / (Best Bid Volume + Best Ask Volume)
    Range: [-1, +1]  | +1 = heavy buy pressure | -1 = heavy sell pressure

    order_book: response từ SSI EP-4 le-table
    ⚠️ EP-4 field names chưa được confirm chính xác — dùng adaptive lookup
    Các field name đã thấy trong HAR logs: 'vol', 'volume', 'totalVol', 'qtty'
    """
    def _extract_vol(level: dict) -> float:
        """Try multiple known field names từ SSI EP-4 response variants."""
        for key in ('vol', 'volume', 'totalVol', 'qtty', 'Qtty', 'TotalVol'):
            if key in level:
                return float(level[key])
        return 0.0

    def _extract_levels(book: dict, side: str) -> list:
        """Try multiple key naming patterns cho bid/ask lists."""
        for key in (side, side + 's', side + 'List', side.capitalize(),
                    side.upper(), side + '_orders'):
            if key in book:
                return book[key]
        return []

    bids = _extract_levels(order_book, 'bid')[:3]
    asks = _extract_levels(order_book, 'ask')[:3]

    if not bids or not asks:
        return 0.0   # EP-4 không available hoặc schema thay đổi → neutral

    bid_vol = sum(_extract_vol(b) for b in bids)
    ask_vol = sum(_extract_vol(a) for a in asks)
    total   = bid_vol + ask_vol
    return (bid_vol - ask_vol) / total if total > 0 else 0.0

# Ngưỡng:
# OFI > +0.3  → Buy pressure → xác nhận entry
# OFI < -0.3  → Sell pressure → delay entry hoặc caution
# |OFI| < 0.1 → Balanced → không cộng điểm
```

---

## Module 2.9: Nhận Diện & Phòng Chống Thao Túng (Anti-Manipulation Layer)

> **Triết lý cốt lõi:** *"Data có thể bị bịa, nhưng dòng tiền thật không thể giả mãi. Tay to phải mua thật, bán thật — để lại dấu vết trong microstructure. Nhiệm vụ của TradingOS là đọc dấu vết đó, không phải đọc headline."*

### 2.9.1 Bản Đồ Thao Túng Tại Thị Trường VN

| Kiểu thao túng | Cơ chế | Dấu vết để nhận diện |
|---|---|---|
| **Pump & Dump** | Mua tích lũy bí mật → tạo FOMO → xả hàng | Volume tăng đột biến nhưng OBV flat/giảm; price-volume divergence |
| **Fake Spring (Bẫy Giảm)** | Đẩy giá xuống dưới support để kích retail bán → gom hàng rẻ | Volume **cao** khi phá support (retail hoảng loạn bán, tay to mua) — phân biệt với Spring thật (volume thấp) |
| **Fake Breakout (Bẫy Tăng)** | Đẩy giá qua kháng cự để kích retail mua → xả hàng vào lực cầu | Volume đột biến ngày phá kháng cự nhưng **không có follow-through T+1**; OBV không xác nhận |
| **Wash Trading** | Mua và bán chính mình để tạo volume ảo | Z_vol cao nhưng OFI ≈ 0 (bid vol ≈ ask vol); không có net price movement |
| **ATC Ramping** | Đẩy giá ATC cuối phiên để inflate close, trigger momentum signal ngày T+1 | ECP lệch > 2.5% so với continuous session price |
| **Insider Run** | Mua trước khi có thông tin doanh nghiệp tốt | Giá tăng bất thường >3% trong 5 phiên trước ngày họp HĐQT/kết quả tài chính |
| **Herding Engineering** | Tạo panic (spread tin xấu) để thu mua rẻ | A/D ratio < 0.5 khi sector fundamentals không thay đổi |

### 2.9.2 Volume Quality Score (VQS)

**Vấn đề cốt lõi:** Z_vol cao không có nghĩa volume đó là "thật" hay "tích cực".

$$VQS = \frac{|OFI|_{avg3} + \Delta OBV\%_{5d} + Price\_Direction}{3}$$

```python
def volume_quality_score(df, order_book) -> dict:
    """
    Đánh giá chất lượng volume: phân biệt informed buying vs wash trading.

    Returns dict với:
      - vqs_score: [-1, +1]  → +1 = volume thật tích cực | -1 = wash/distribution
      - flags: list of warning flags
    """
    flags = []

    # --- Tín hiệu 1: OFI (Order Flow Imbalance từ EP-4) ---
    ofi = compute_ofi(order_book)
    # OFI ~ 0 khi Z_vol cao → wash trading
    if df['Z_vol'].iloc[-1] > 1.5 and abs(ofi) < 0.10:
        flags.append("WASH_TRADING_SUSPECT")
        ofi_score = -0.5
    elif ofi > 0.30:
        ofi_score = +1.0   # strong buy pressure
    elif ofi < -0.30:
        ofi_score = -1.0   # strong sell pressure
    else:
        ofi_score = ofi * 2  # scale [-0.3, +0.3] → [-0.6, +0.6]

    # --- Tín hiệu 2: OBV Trend (On-Balance Volume) ---
    obv_5d_change = (df['OBV'].iloc[-1] - df['OBV'].iloc[-6]) / abs(df['OBV'].iloc[-6] + 1e-9)
    if obv_5d_change > 0.05:
        obv_score = +1.0     # OBV tăng → accumulation thật
    elif obv_5d_change < -0.05:
        obv_score = -1.0     # OBV giảm → distribution đang diễn ra
        flags.append("OBV_DIVERGENCE")
    else:
        obv_score = 0.0

    # --- Tín hiệu 3: Price-Volume Direction Agreement ---
    price_up  = df['Close'].iloc[-1] > df['Close'].iloc[-2]
    vol_up    = df['Volume'].iloc[-1] > df['Volume'].iloc[-2]
    if price_up and vol_up:
        pv_score = +1.0      # volume xác nhận giá tăng
    elif (not price_up) and vol_up:
        pv_score = -0.5      # giá giảm với volume cao → distribution pressure
        flags.append("DISTRIBUTION_VOLUME")
    else:
        pv_score = 0.0

    vqs = (ofi_score + obv_score + pv_score) / 3.0

    return {"vqs_score": round(vqs, 3), "flags": flags, "ofi": ofi}
```

**VQS integration vào MFPM Mode A:**

| VQS | Điều chỉnh điểm MFPM |
|---|---|
| VQS ≥ +0.5 | **+15** — Volume thật, institutional buying confirmed |
| VQS 0 đến +0.5 | **+5** — Volume trung tính |
| VQS -0.3 đến 0 | **0** — Không cộng volume score |
| VQS < -0.3 | **-15** — Distribution signal: không entry |
| Flag `WASH_TRADING_SUSPECT` | **-20** — Reject signal |

### 2.9.3 Phân Biệt Fake Spring vs Spring Thật

```python
def detect_spring_quality(df, lookback=20) -> tuple[bool, str]:
    """
    Phân biệt Spring thật (Wyckoff) vs Fake Spring (bẫy retail).

    Spring thật: Tay to KHÔNG bán — chỉ để giá phá support tự nhiên.
    Fake Spring: Tay to ĐANG bán rất mạnh vào lực cầu retail ngây thơ.
    """
    historical_low = df['Low'].iloc[-lookback:-1].min()
    avg_vol        = df['Volume'].iloc[-lookback:].mean()
    c = df.iloc[-1]

    # Check Spring cơ bản
    basic_spring = (
        c['Low']   < historical_low and
        c['Close'] > historical_low and
        c['Close'] > c['Open']
    )
    if not basic_spring:
        return False, "NO_SPRING"

    # =====================================================================
    # PHÂN BIỆT CHẤT LƯỢNG — đây là điểm quan trọng nhất
    # =====================================================================

    # Spring THẬT: volume THẤP khi phá support = supply exhaustion
    # Tay to không bán → không có volume đẩy giá xuống
    low_volume_break = c['Volume'] < avg_vol * 0.85

    # Fake Spring: volume CAO khi phá support = tay to đang XẢ vào retail hoảng loạn
    high_volume_break = c['Volume'] > avg_vol * 1.50

    # OBV xác nhận: Spring thật → OBV không giảm nhiều (người bán ít)
    obv_stable = df['OBV'].iloc[-1] >= df['OBV'].iloc[-3] * 0.97

    # RSI không quá thấp (<25): real Spring thường không crash RSI về oversold cực đoan
    rsi_reasonable = df['RSI14'].iloc[-1] >= 25

    if low_volume_break and obv_stable:
        return True, "SPRING_REAL"        # ✅ Tín hiệu đáng tin
    elif high_volume_break:
        return False, "SPRING_FAKE_SELL"  # ❌ Tay to đang bán vào recovery
    elif not obv_stable:
        return False, "SPRING_FAKE_OBV"  # ❌ OBV giảm → distribution đang diễn ra
    else:
        return True, "SPRING_WEAK"        # ⚠️ Spring có thể đúng nhưng cần thêm xác nhận
```

### 2.9.4 Second Mouse Gate — Chống Fake Breakout Mode B

> **"The first mouse gets the trap. The second mouse gets the cheese."**
> 
> Breakout thật cần **xác nhận T+1**: nếu ngày T+1 giá retest pivot high và giữ vững → entry. Đừng chase ngay ngày phá kháng cự.

```python
def second_mouse_gate(df, pivot_high: float) -> dict:
    """
    Chặn fake breakout trong Mode B bằng cách yêu cầu xác nhận T+1.

    Fake Breakout pattern:
    - Ngày phá: Volume đột biến, giá đóng trên pivot
    - Ngày T+1: Giá quay đầu giảm ("bull trap" — retail mua đỉnh)

    Real Breakout pattern:
    - Ngày phá: Volume đột biến
    - Ngày T+1 (hoặc T+2): Giá RETEST pivot high → đóng cửa TRÊN pivot → mới entry
    """
    today   = df.iloc[-1]
    yest    = df.iloc[-2]
    avg_vol = df['Volume'].iloc[-20:].mean()

    # Kiểm tra breakout ngày hôm qua
    breakout_yesterday = yest['Close'] > pivot_high and yest['Volume'] > avg_vol * 1.5

    if not breakout_yesterday:
        return {"gate": "WAIT", "reason": "Chưa có breakout để retest"}

    # Hôm nay: giá retest về pivot_high và giữ vững?
    retest_zone       = today['Low'] <= pivot_high * 1.02  # pullback về vùng pivot ±2%
    hold_above_pivot  = today['Close'] > pivot_high         # đóng cửa vẫn trên pivot
    volume_shrink     = today['Volume'] < yest['Volume']    # volume rút trong retest = ít seller

    if breakout_yesterday and retest_zone and hold_above_pivot and volume_shrink:
        return {"gate": "ENTRY_OK", "reason": "Breakout xác nhận: retest + hold + low sell vol"}
    elif breakout_yesterday and today['Close'] < pivot_high:
        return {"gate": "FAKE_BREAKOUT", "reason": "Giá quay về dưới pivot → Bull Trap"}
    else:
        return {"gate": "WAIT_RETEST", "reason": "Breakout hôm qua — chờ retest xác nhận"}
```

### 2.9.5 Pre-Event Insider Run Detection

```python
def detect_insider_run(df, event_date: str, lookback: int = 10) -> bool:
    """
    Phát hiện giá tăng bất thường trước sự kiện doanh nghiệp.
    Nguồn event_date: SSI EP-14 (company-news), EP-11 (corporate-actions).

    Nếu giá đã tăng > 5% trong 10 phiên trước event → có thể có insider buying
    → Không entry: risk/reward bị nén do giá đã phản ánh một phần thông tin.

    ⚠️ False positive guard: giai đoạn báo cáo chính thức (BCTC quý, cổ tức, HĐQT)
    thường có pre-positioning hợp lệ → không flag insider run
    """
    # Scheduled events: không flag — move là normal pre-earnings/dividend positioning
    SCHEDULED_KEYWORDS = ("Q1", "Q2", "Q3", "Q4", "AGM", "BCTC", "dividend",
                          "cổ_tức", "họp_đồng_cổ_đông", "annual_report")
    if any(kw.lower() in str(event_date).lower() for kw in SCHEDULED_KEYWORDS):
        return False   # scheduled event: không phải insider

    event_idx = df.index.get_loc(event_date) if event_date in df.index else len(df) - 1
    pre_event = df.iloc[max(0, event_idx - lookback): event_idx]

    if len(pre_event) < 3:
        return False

    price_run = (pre_event['Close'].iloc[-1] - pre_event['Close'].iloc[0]) / pre_event['Close'].iloc[0]
    vol_run   = pre_event['Volume'].mean() / df['Volume'].iloc[-50:-lookback].mean()

    # Giá chạy > 5% + volume tăng > 1.5x trước event → nghi ngờ insider
    return price_run > 0.05 and vol_run > 1.5
```

### 2.9.6 Pipeline Tổng Hợp — Anti-Manipulation Filter

```python
def anti_manipulation_filter(df, order_book, event_dates=None) -> dict:
    """
    Chạy toàn bộ manipulation checks. Trả về PASS/WARN/BLOCK.
    Gọi TRƯỚC MFPM scoring — block ngay nếu có dấu hiệu rõ.

    Ensemble BLOCK policy: cần ≥ 2 signals độc lập mới BLOCK.
    1 flag đơn lẻ → WARN + giảm điểm, không BLOCK — giảm false positive.
    """
    result      = {"decision": "PASS", "flags": [], "score_adjustment": 0}
    block_votes = []   # cộng dồn block-worthy signals trước khi quyết định

    # 1. Volume Quality
    vqs_data = volume_quality_score(df, order_book)
    result["flags"].extend(vqs_data["flags"])

    if "WASH_TRADING_SUSPECT" in vqs_data["flags"]:
        result["score_adjustment"] -= 20
        block_votes.append("WASH_TRADING_SUSPECT")
    if vqs_data["vqs_score"] < -0.3:
        block_votes.append("VQS_DISTRIBUTION_DETECTED")
        result["flags"].append("VQS_DISTRIBUTION_DETECTED")

    # 2. Spring Quality (nếu signal có Spring component)
    spring_ok, spring_type = detect_spring_quality(df)
    if spring_type == "SPRING_FAKE_SELL":
        block_votes.append("FAKE_SPRING_HIGH_VOLUME")
        result["flags"].append("FAKE_SPRING_HIGH_VOLUME")

    # 3. ATC manipulation (nếu trong ATC window)
    # → Đã handle trong smart_atc_router: ECP deviation > 2.5% → cancel

    # 4. Insider run check
    if event_dates:
        for edate in event_dates:
            if detect_insider_run(df, edate):
                result["flags"].append(f"INSIDER_RUN_BEFORE_{edate}")
                result["score_adjustment"] -= 15
                block_votes.append("INSIDER_RUN")

    # 5. Second Mouse gate cho Mode B (gọi riêng tại Mode B logic)
    # → Đã handle trong second_mouse_gate()

    # — Ensemble Decision: cần ≥ 2 block votes mới BLOCK —
    if len(block_votes) >= 2:
        result["decision"] = "BLOCK"
    elif len(block_votes) == 1:
        result["decision"] = "WARN"   # 1 flag đơn → chỉ warn, giảm vị thế 50%

    # Áp dụng VQS adjustment vào MFPM score
    result["score_adjustment"] += int(vqs_data["vqs_score"] * 15)  # max ±15 điểm

    return result
```

> **Lưu ý triết học:** Thao túng không thể bị loại bỏ hoàn toàn — chỉ có thể **giảm xác suất bị bẫy** bằng cách:
> 1. Yêu cầu đồng thuận từ nhiều tín hiệu độc lập (MFPM ≥ 5 factors)
> 2. Volume CHẤT LƯỢNG (OFI + OBV + CVD), không chỉ số lượng
> 3. Không entry pioneer — chờ retest xác nhận (Second Mouse)
> 4. Position nhỏ hơn khi VQS = WARN (50% planned qty)

---

## Module 2.10: AMD Cycle + VSA (Volume Spread Analysis)

> **Nguồn:** *Proposal v5 — "Chu Kỳ Ba Hồi Của Đội Lái"*. AMD là framework đọc ý đồ Smart Money theo trình tự thời gian; VSA đọc dấu vết từng phiên.

### 2.10.1 Chu Kỳ AMD (Accumulation → Manipulation → Distribution)

Smart Money không giao dịch ngẫu hứng — họ vận hành theo chu kỳ **AMD** để tối đa hóa fill ở giá tốt bằng cách bẫy thanh khoản của retail.

| Pha | Đặc điểm giá | Đặc điểm volume | Hành động Smart Money | Dấu hiệu nhận biết |
|---|---|---|---|---|
| **Accumulation** | Đi ngang (Trading Range), no trend | Thấp, đều | Âm thầm thu gom từng lô nhỏ | Weis Wave: Down Wave vol < Up Wave vol |
| **Manipulation** | Spring / Shakeout: phá support hoặc phá resistance giả | Đột biến 1–2 phiên | Gom lô cuối rẻ (Spring) hoặc xả lô đầu cao (False Breakout) | OBV divergence; VQS < 0 khi phá support |
| **Distribution** | Tăng/giảm nhanh sau manipulation | Đột biến rồi cạn dần | Xả dần vào FOMO của retail | Buying Climax: vol cực đại + đóng cửa thấp hơn giá cao nhất ngày |

```python
def classify_amd_phase(df, lookback: int = 60) -> str:
    """
    Xác định Trading OS hiện tại đang ở pha nào trong AMD cycle.
    Dùng kết hợp: range expansion, volume trend, OBV slope.
    """
    window      = df.iloc[-lookback:]
    price_range = window['High'].max() - window['Low'].min()
    avg_range   = (window['High'] - window['Low']).mean()
    obv_slope   = (window['OBV'].iloc[-1] - window['OBV'].iloc[0]) / max(abs(window['OBV'].iloc[0]), 1)
    vol_trend   = window['Volume'].iloc[-5:].mean() / window['Volume'].iloc[-30:-5].mean()
    close_trend = (window['Close'].iloc[-1] - window['Close'].iloc[-20]) / window['Close'].iloc[-20]

    # Accumulation: giá đi ngang, OBV tăng dần (smart money gom)
    if price_range < avg_range * lookback * 0.5 and obv_slope > 0.02:
        return "ACCUMULATION"   # → ưu tiên Mode A, chờ Spring

    # Distribution: giá đi ngang sau đợt tăng dài, OBV bắt đầu giảm
    if close_trend > 0.15 and obv_slope < -0.02 and vol_trend > 1.2:
        return "DISTRIBUTION"   # → không entry mới; nếu có vị thế → sẵn sàng chốt

    # Mark-up / Mark-down: xu hướng rõ
    if close_trend > 0.05:
        return "MARKUP"         # → Mode B breakout cơ hội tốt
    if close_trend < -0.05:
        return "MARKDOWN"       # → Cash; không entry long

    return "RANGING"            # → Sideways: chờ rõ tín hiệu hơn
```

**Tích hợp AMD vào MFPM Pre-conditions:**
```python
amd_phase = classify_amd_phase(df)
assert amd_phase in ("ACCUMULATION", "MARKUP"), f"AMD phase = {amd_phase}: không phù hợp entry"
# DISTRIBUTION / MARKDOWN → reject mọi long signal
# RANGING → chỉ Mode A nếu MFPM ≥ 70 (yêu cầu cao hơn bình thường)
```

### 2.10.2 VSA — No Demand Bar & No Supply Bar

**VSA (Volume Spread Analysis)** đọc quan hệ giữa spread (biên độ nến) và volume để phát hiện khi nào Smart Money dừng tay.

```python
def detect_vsa_bars(df) -> dict:
    """
    Phát hiện 2 VSA signal quan trọng nhất:
      - No Demand Bar: giá TẮC, tay to không còn đẩy giá → cảnh báo đỉnh tạm
      - No Supply Bar: giá DỪT, bên bán không còn lực → Spring confirm

    Tiêu chí (theo Tom Williams / VSA methodology):
      No Demand:  giá tăng (Close > Open) + biên độ hẹp + vol thấp hơn 2 phiên trước
      No Supply:  giá giảm (Close < Open) + biên độ hẹp + vol thấp hơn 2 phiên trước
    """
    c    = df.iloc[-1]
    prev = df.iloc[-2]
    p2   = df.iloc[-3]

    spread      = c['High'] - c['Low']
    avg_spread  = (df['High'] - df['Low']).rolling(20).mean().iloc[-1]
    narrow_bar  = spread < avg_spread * 0.70       # biên độ hẹp ≤ 70% trung bình

    vol_low     = c['Volume'] < prev['Volume'] and c['Volume'] < p2['Volume']

    bullish_bar = c['Close'] > c['Open']
    bearish_bar = c['Close'] < c['Open']

    no_demand = bullish_bar and narrow_bar and vol_low   # giá tăng nhưng vol cạn → đỉnh tạm
    no_supply = bearish_bar and narrow_bar and vol_low   # giá giảm nhưng vol cạn → đáy gần

    # Strength: đóng cửa ở nửa trên nến = smart money absorbed sell
    close_pct_in_bar = (c['Close'] - c['Low']) / max(spread, 1e-9)
    absorption = close_pct_in_bar > 0.60 and bearish_bar and vol_low  # "Effort to Fall" thất bại

    return {
        "no_demand"  : no_demand,    # ⚠️ cảnh báo: không entry hoặc giảm MFPM -10
        "no_supply"  : no_supply,    # ✅ xác nhận tốt: cộng MFPM +8
        "absorption" : absorption,   # ✅ smart money absorbing sellers: cộng MFPM +12
    }
```

**VSA tích hợp vào MFPM scoring:**

| VSA Signal | Điều chỉnh MFPM |
|---|---|
| No Supply Bar xác nhận Spring | +8 |
| Absorption (bearish bar + vol thấp + đóng cuối bar) | +12 |
| No Demand Bar (giá tăng nhưng vol cạn) | -10 (cảnh báo đỉnh tạm thời) |

### 2.10.3 CVD — Cumulative Volume Delta (Whale Tracker)

**Vấn đề với OFI:** OFI chụp instant snapshot order book — không theo dõi được **net direction của toàn phiên**. CVD giải quyết điều này bằng cách tổng tích lũy delta tick-by-tick.

$$CVD = \sum_{t}^{T} \left(BuyVol_t - SellVol_t\right)$$

```python
def compute_cvd(tick_df) -> dict:
    """
    Tính Cumulative Volume Delta từ tick data.
    Phân loại tick: nếu price >= ask_price → aggressor MUA; nếu <= bid → aggressor BÁN.

    Nguồn data: SSI FastConnect (gRPC) hoặc tick-level EP-3 polling.
    tick_df columns: ['timestamp', 'price', 'volume', 'bid', 'ask']

    Phân loại Institutional vs Retail:
      Institutional: single tick volume >= 50,000 cổ (50 tỷ @ 10k) → "cá voi"
      Retail:        tick volume < 5,000 cổ
    """
    tick_df = tick_df.copy()

    # Aggressor classification
    tick_df['is_buy']  = tick_df['price'] >= tick_df['ask']
    tick_df['is_sell'] = tick_df['price'] <= tick_df['bid']
    tick_df['delta']   = tick_df.apply(
        lambda r: r['volume'] if r['is_buy'] else (-r['volume'] if r['is_sell'] else 0),
        axis=1
    )
    tick_df['cvd']     = tick_df['delta'].cumsum()

    # Institutional flow classification
    tick_df['size_tier'] = tick_df['volume'].apply(
        lambda v: 'WHALE' if v >= 50_000 else ('MID' if v >= 5_000 else 'RETAIL')
    )
    whale_buy  = tick_df.loc[tick_df['is_buy']  & (tick_df['size_tier'] == 'WHALE'), 'volume'].sum()
    whale_sell = tick_df.loc[tick_df['is_sell'] & (tick_df['size_tier'] == 'WHALE'), 'volume'].sum()

    cvd_final  = tick_df['cvd'].iloc[-1]
    cvd_slope  = cvd_final / max(len(tick_df), 1)  # avg delta per tick

    # Key signal: giá tăng nhưng CVD giảm (Delta Divergence) = tay to đang XẢ
    price_up   = tick_df['price'].iloc[-1] > tick_df['price'].iloc[0]
    cvd_down   = cvd_final < 0
    delta_divergence = price_up and cvd_down     # Bearish: Distribution alert

    return {
        "cvd"              : cvd_final,
        "cvd_slope"        : cvd_slope,
        "whale_buy_vol"    : whale_buy,
        "whale_sell_vol"   : whale_sell,
        "whale_net"        : whale_buy - whale_sell,
        "delta_divergence" : delta_divergence,   # 🚨 distribution warning
    }
```

**CVD tích hợp vào MFPM scoring:**

| CVD Signal | Điều chỉnh MFPM |
|---|---|
| CVD > 0 + Whale net buy > 0 (cá voi đang mua) | +15 |
| CVD > 0 nhưng Whale net neutral | +5 |
| `delta_divergence = True` (giá tăng nhưng CVD âm) | -20 (distribution: BLOCK) |
| CVD < 0 + no whale buying | -10 |

> **Lưu ý triển khai:** CVD tick-level yêu cầu SSI FastConnect gRPC (có phí) hoặc polling EP-3 mỗi giây. Trong Phase 1–2, có thể dùng proxy CVD từ từ EP-4 order book snapshot + OFI đã có. Full CVD nằm trong **Backlog #14**.

---

## Module 3: Pattern Detection

### 3.1 Wyckoff Spring

```python
def detect_spring(df, lookback=20):
    historical_low = df['Low'].iloc[-lookback:-1].min()
    avg_vol        = df['Volume'].iloc[-lookback:].mean()
    c = df.iloc[-1]

    is_spring = (
        c['Low']    < historical_low  and   # Phá hỗ trợ
        c['Close']  > historical_low  and   # Đóng cửa trên hỗ trợ (recovery)
        c['Volume'] < avg_vol * 0.85  and   # Volume thấp = supply exhaustion
        c['Close']  > c['Open']             # Bullish candle
    )
    return is_spring
```

### 3.2 VCP (Volatility Contraction Pattern — Minervini)

```python
def detect_vcp(df, min_contractions=2, lookback=50):
    swings = find_swing_highs_and_lows(df, lookback)
    contractions = 0
    for i in range(1, len(swings) - 1):
        range_i    = swings[i]['high']   - swings[i]['low']
        range_im1  = swings[i-1]['high'] - swings[i-1]['low']
        vol_curr   = avg_volume_in_swing(df, swings[i])
        vol_prev   = avg_volume_in_swing(df, swings[i-1])
        # ⚠️ Adaptive threshold: cổ phiếu biến động cao (ATR/Price > 2%) cần ngừng nới lỏng hơn
        # Ví dụ: mã midcap VN: range contraction 80% cũng vẫn là contraction hợp lệ
        atr_ratio   = df['ATR14'].iloc[-1] / df['Close'].iloc[-1] if df['Close'].iloc[-1] > 0 else 0.02
        price_thr   = 0.70 if atr_ratio <= 0.02 else 0.80   # relaxed threshold for high-vol
        vol_thr     = 0.75 if atr_ratio <= 0.02 else 0.85
        # Price range contracting AND volume contracting
        if range_i / range_im1 < price_thr and vol_curr / vol_prev < vol_thr:
            contractions += 1
    return contractions >= min_contractions
```

### 3.3 Fair Value Gap (FVG)

```python
def detect_fvg(df):
    # Bullish FVG: candle[i-1] high < candle[i+1] low
    df['Bullish_FVG'] = np.where(
        df['Low'].shift(-1) > df['High'].shift(1),
        df['Low'].shift(-1) - df['High'].shift(1), 0
    )
    # Bearish FVG: candle[i-1] low > candle[i+1] high
    df['Bearish_FVG'] = np.where(
        df['High'].shift(-1) < df['Low'].shift(1),
        df['Low'].shift(1) - df['High'].shift(-1), 0
    )
    return df
```

### 3.4 Weis Wave Volume Analysis

```python
def weis_wave(df, threshold=0.5):
    """Cumulative volume theo nhịp sóng tăng/giảm"""
    waves, current = [], {'direction': None, 'vol': 0}
    for i in range(1, len(df)):
        direction = 'up' if df['Close'].iloc[i] > df['Close'].iloc[i-1] else 'down'
        if direction != current['direction']:
            waves.append(current)
            current = {'direction': direction, 'vol': 0}
        current['vol'] += df['Volume'].iloc[i]
    waves.append(current)

    down_waves = [w for w in waves if w['direction'] == 'down']
    up_waves   = [w for w in waves if w['direction'] == 'up']
    if len(down_waves) >= 1 and len(up_waves) >= 2:
        last_down   = down_waves[-1]
        prior_up    = up_waves[-2]
        no_supply   = last_down['vol'] < prior_up['vol'] * threshold
        return no_supply, waves
    return False, waves
```

### 3.5 Bullish RSI Divergence

Tín hiệu từ **proposal gốc** (Trading OS 331e99f): *"Engine gaining strength even though vehicle is still sliding"* — price tạo Lower Low nhưng RSI (momentum) tạo Higher Low. Đây là tín hiệu đảo chiều xác suất cao.

```python
def detect_rsi_divergence(df, lookback: int = 20) -> bool:
    """
    Bullish Divergence: Price Lower Low + RSI Higher Low
    Kiểm tra trong cửa sổ lookback bars gần nhất
    """
    if len(df) < lookback + 5:
        return False

    # Vùng gốc (lookback bars trước) vs vùng hiện tại (5 bars gần nhất)
    price_past_low = df['Low'].iloc[-lookback:-5].min()
    price_curr_low = df['Low'].iloc[-5:].min()
    rsi_past_low   = df['RSI14'].iloc[-lookback:-5].min()
    rsi_curr_low   = df['RSI14'].iloc[-5:].min()

    price_lower_low = price_curr_low < price_past_low          # price xuống thấp hơn
    rsi_higher_low  = rsi_curr_low   > rsi_past_low + 2.0      # RSI cao hơn (+2 để lọc noise)

    return price_lower_low and rsi_higher_low
```

> **Ứng dụng trong MFPM:** +15 điểm khi confirmed. Đặc biệt hiệu quả kết hợp Wyckoff Spring — Spring với divergence = tín hiệu mạnh nhất trong VN market (retail capitulation + institutional absorption).

### 3.6 Order Block Detection

**Nguồn:** *Proposal v5 — "Dấu Chân Tổ Chức (Institutional Footprints)"*. Order Block là nến cuối cùng **trước** một cú move mạnh — nơi Smart Money đặt lệnh lớn, thường trở thành vùng hỗ trợ/kháng cự mạnh.

```python
def detect_order_block(df, min_move_pct: float = 0.03, lookback: int = 50) -> list[dict]:
    """
    Order Block = nến cuối cùng ngược chiều trước một cú impulse move ≥ min_move_pct.

    Bullish OB: nến giảm ngay trước impulse tăng mạnh
    → Vùng này là nơi tổ chức đặt lệnh mua → hỗ trợ mạnh khi giá quay lại

    Bearish OB: nến tăng ngay trước impulse giảm mạnh
    → Vùng này là nơi tổ chức đặt lệnh bán khống → kháng cự khi giá phục hồi
    """
    blocks = []
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values

    for i in range(1, len(df) - 3):
        # Tính move của đợt impulse (3 nến tiếp theo)
        forward_move = (closes[i + 3] - closes[i + 1]) / closes[i + 1]

        # Bullish OB: nến [i] là bearish, tiếp theo là impulse tăng mạnh
        if closes[i] < df['Open'].values[i] and forward_move >= min_move_pct:
            blocks.append({
                "type"  : "BULLISH_OB",
                "bar_idx": i,
                "ob_high": highs[i],
                "ob_low" : lows[i],
                "strength": abs(forward_move),
            })

        # Bearish OB: nến [i] là bullish, tiếp theo là impulse giảm mạnh
        elif closes[i] > df['Open'].values[i] and forward_move <= -min_move_pct:
            blocks.append({
                "type"  : "BEARISH_OB",
                "bar_idx": i,
                "ob_high": highs[i],
                "ob_low" : lows[i],
                "strength": abs(forward_move),
            })

    # Chỉ trả về các OB trong lookback bars và chưa bị "mitigated" (giá đã vào và ra)
    recent = [b for b in blocks if b['bar_idx'] >= len(df) - lookback]
    return sorted(recent, key=lambda x: x['strength'], reverse=True)


def price_in_order_block(close: float, order_blocks: list[dict]) -> tuple[bool, str]:
    """Kiểm tra giá hiện tại có đang trong vùng OB không."""
    for ob in order_blocks:
        if ob['ob_low'] <= close <= ob['ob_high']:
            return True, ob['type']
    return False, "NONE"
```

**Tích hợp OB vào MFPM:** Nếu giá pullback vào vùng Bullish OB → +10 điểm (xác nhận vùng cầu tổ chức).

### 3.7 Cup with Handle (O'Neil / CAN SLIM)

**Nguồn:** *Proposal v5 — "Cup with Handle đang hình thành"* (TCB). Classic O'Neil setup — thường xuất hiện sau Accumulation phase → breakout mạnh.

```python
def detect_cup_with_handle(df, cup_min_bars: int = 30, cup_max_bars: int = 120) -> dict:
    """
    Cup: Hình chữ U tròn (không phải V) trong 30–120 phiên, depth 12–35%
    Handle: Pullback 5–15% sau khi giá đạt miệng cup, volume cạn → điểm entry

    Điều kiện:
    1. Cup left rim = cup right rim (miệng cup đối xứng ±5%)
    2. Cup depth 12–35% (đủ reset, không quá sâu)
    3. Handle: pullback nhỏ ≤15%, close ≥ cup_left_rim × 0.90
    4. Handle vol thấp dần → breakout vol đột biến
    """
    close = df['Close']
    high  = df['High']
    n     = len(close)
    if n < cup_min_bars + 10:
        return {"detected": False}

    # Tìm cup left rim, bottom, right rim trong lookback
    window     = close.iloc[-cup_max_bars:]
    left_rim   = window.iloc[0]
    cup_bottom = window.min()
    right_rim  = window.iloc[-15]   # trước handle 15 phiên

    depth = (left_rim - cup_bottom) / left_rim
    rim_symmetry = abs(right_rim - left_rim) / left_rim

    valid_cup = (
        0.12 <= depth <= 0.35 and       # depth 12–35%
        rim_symmetry <= 0.05            # miệng cup đối xứng ±5%
    )

    if not valid_cup:
        return {"detected": False}

    # Handle: pullback nhỏ sau right rim
    handle_window = close.iloc[-15:]
    handle_low    = handle_window.min()
    handle_depth  = (right_rim - handle_low) / right_rim

    handle_vol_shrink = (
        df['Volume'].iloc[-15:].mean() < df['Volume'].iloc[-30:-15].mean() * 0.80
    )

    valid_handle = handle_depth <= 0.15 and handle_vol_shrink

    # Pivot Point = right rim / cup high = entry trigger cho Mode B
    pivot = float(right_rim)

    return {
        "detected"    : valid_cup and valid_handle,
        "cup_depth"   : round(depth, 3),
        "handle_depth": round(handle_depth, 3),
        "pivot"       : pivot,
        "pattern"     : "CUP_WITH_HANDLE",
    }
```

**Tích hợp Cup&Handle vào MFPM Mode B:** Khi `cup_with_handle["detected"] = True` và `close > pivot` → +15 điểm (O'Neil highest-probability setup).

---

## Module 4: MFPM — Multi-Factor Pullback & Momentum

### 4.1 Pre-conditions (phải đạt TẤT CẢ)

```python
assert hmm_state != "VOLATILE_BEAR"
assert gmo_omega >= 0.0                       # RISK_ON hoặc CAUTIOUS
assert SMA(close, 50) > SMA(close, 200)       # Uptrend structure
assert close < ceiling * 0.99                # Circuit Breaker gate
assert close > floor   * 1.01                # Không gần sàn
assert avg_vol_20d >= 500_000                # Liquidity
assert current_time >= "09:15"               # ⚠️ Dùng range check, không phải tuple — loại ATO window
assert current_time < "14:45"                # Chưa đóng cửa
assert trade_status not in ['ST','UT','HA','KH','KS']  # Không bị kiểm soát/đình chỉ
assert weekly_sma50 > weekly_sma200          # Multi-timeframe gate (weekly)

# — AMD Phase gate (Module 2.10) —
amd_phase = classify_amd_phase(df)
assert amd_phase in ("ACCUMULATION", "MARKUP", "RANGING"), \
    f"AMD phase = {amd_phase}: DISTRIBUTION/MARKDOWN → không entry long"
# Nếu RANGING: được phép entry nhưng MFPM threshold tăng lên 70 (thay vì 50)

# ⚠️ Double-count guard: không mở cùng 1 mã 2 lần từ 2 mode khác nhau trong 1 phiên
# Ví dụ: Mode A đã mở HPG → Mode B không được mở HPG cùng ngày
if ticker in existing_positions:
    assert existing_positions[ticker].get("mode") == trade_mode, \
        f"Double-count blocked: {ticker} đã có vị thế {existing_positions[ticker]['mode']}"

# --- Anti-Manipulation pre-screen (Module 2.9) ---
amf = anti_manipulation_filter(df, order_book, event_dates)
assert amf["decision"] != "BLOCK", f"AMF blocked: {amf['flags']}"
# amf["score_adjustment"] sẽ được cộng vào MFPM score sau
```

### 4.2 Mode A — Pullback Entry

**Trigger:** RSI(14) cross-up từ ≤50 trong uptrend

**MFPM Score Calculation:**

| Điều kiện | Điểm |
|---|---|
| RSI cross-up từ ≤ 42 (oversold sâu) | +30 |
| RSI cross-up từ 43–50 (pullback) | +20 |
| Z_vol > 2.0 *(mutex với dry-up)* | +25 |
| Z_vol 1.5–2.0 *(mutex với dry-up)* | +20 |
| Close > VWAP (intraday, từ 5-min bars; overnight: close > typical_price_close T-1) | +15 |
| Wyckoff Spring detected | +15 |
| Bullish RSI Divergence (price LL + RSI HL) | +15 |
| VCP Pattern (≥2 contractions) | +10 |
| Weis Wave: No Supply signal | +10 |
| Volume dry-up trong pullback *(Z_vol < 0.5, mutex với Z_vol score)* | +10 |
| EMA9 > EMA20 (short-term aligned) | +8 |
| MACD histogram dương (optional) | +5 |
| FOL: FOREIGN_BUY | +10 |
| FOL: FOL_DIP_ENTRY | +8 |
| FOL: ROOM_DAY | -5 |
| **VQS ≥ +0.5 (volume thật, institutional buying)** | **+15** |
| **VQS 0 đến +0.5** | **+5** |
| **VQS < -0.3 (distribution signal)** | **-15 + FLAG** |
| **WASH_TRADING_SUSPECT** | **-20 (auto-reject)** |
| **CVD > 0 + Whale net buy ≥ 50K cổ (cá voi đang mua)** | **+15** |
| **CVD > 0, không có whale buying** | **+5** |
| **Delta Divergence (giá tăng + CVD âm)** | **-20 (BLOCK)** |
| **VSA No Supply Bar xác nhận Spring/pullback** | **+8** |
| **VSA Absorption (bearish bar + vol thấp + đóng cuối bar)** | **+12** |
| **VSA No Demand Bar (đỉnh tạm)** | **-10** |
| **Price trong Bullish Order Block** | **+10** |
| **AMD phase = ACCUMULATION** | **+8 (thọi điểm tích lũy)** |
| CAN SLIM Score < 50 | -20 |
| ADX14 < 20 (trend quá yếu) | -10 |

```
STRONG_BUY if MFPM_score >= 70
BUY        if MFPM_score >= 50
WATCH      if MFPM_score >= 35
NO_SIGNAL  if MFPM_score < 35
```

> **Điểm tối đa thực tế (Mode A):** ~110+ sau khi thêm Bullish Divergence (+15), VSA (+20), CVD (+15), OB (+10), AMD (+8). Mutex rules: RSI chỉ cộng 1 mức (30 hoặc 20); Z_vol chỉ cộng 1 mức (25 hoặc 20); **Z_vol score và Volume dry-up là mutually exclusive** — nếu Z_vol > 1.5 thì không cộng dry-up và ngược lại. Target STRONG_BUY ≥ 70, thực tế đạt 80–120 với full signal stack.

### 4.3 Mode B — Breakout Entry

**Trigger:** Close > Pivot high (20–50 bars) hoặc Cup&Handle pivot với Volume > 1.5×MAV20

**Entry điều kiện:**
```python
rsi_in_zone     = 50 <= RSI14 <= 65
volume_breakout = volume > 1.5 * MAV20
zvol_strong     = Z_vol > 2.0             # Breakout yêu cầu mạnh hơn Mode A
price_above_vwap = close > VWAP
macd_positive   = MACD_hist > 0 and MACD_hist > MACD_hist.shift(1)  # trending up

# Check Cup with Handle trigger (Module 3.7) — kết hợp với pivot_high bình thường
cwh = detect_cup_with_handle(df)
cwh_trigger = cwh["detected"] and close > cwh["pivot"]  # Mode B thêm +15 nếu CwH confirm

# ⚠️ GAP-UP GATE: nếu ATO mở cửa gap > 3% so với pivot_high → không chase
# Breakout đã được "ăn" bởi retail trong ATO; entry lúc này = mua đỉnh
if current_time >= "09:15" and current_time < "09:45":   # sáng sớm sau ATO
    ato_gap_vs_pivot = (close - pivot_high) / pivot_high
    if ato_gap_vs_pivot > 0.03:
        return "REJECTED_GAP_CHASE", f"ATO gap {ato_gap_vs_pivot:.1%} > 3% vs pivot"

# ⚠️ SECOND MOUSE GATE: không entry ngày phá káng cự — chờ retest xác nhận
smg = second_mouse_gate(df, pivot_high=find_pivot_high(df))
assert smg["gate"] == "ENTRY_OK", f"Mode B blocked: {smg['reason']}"
# Nếu FAKE_BREAKOUT: loại hỏa
# Nếu WAIT_RETEST: giữ trong watchlist, check lại ngày mai

signal_b = rsi_in_zone and volume_breakout and zvol_strong and price_above_vwap
```

### 4.4 Monte Carlo Pre-Entry Gate

```python
from math import exp, sqrt
import numpy as np

def get_regime_mu(hmm_state: str, returns: 'pd.Series') -> float:
    """
    Trả về drift mu theo HMM regime, không dùng simple historical mean.

    Vấn đề với historical mean: nếu backtest window là 2020–2025 (bull-dominant),
    mu sẽ bias dương → MC reject ít tín hiệu sai. Trong bear, ngược lại.
    Fix: dùng regime-specific drift để MC phản ánh đúng environment hiện tại.
    """
    daily_mean = float(returns.mean())
    if hmm_state == "STEADY_BULL":
        # Bull regime: đảm bảo mu dương — floor tại +0.05%/ngày
        return max(daily_mean, 0.0005)
    elif hmm_state == "VOLATILE_BEAR":
        # Bear regime: force negative drift — bủ signal hầu hết
        return min(daily_mean, -0.0003)
    else:  # SIDEWAYS
        return 0.0   # sideways: mu ≈ 0, không đáng tin vào directional drift

def mc_win_probability(
    entry: float, sl: float, tp1: float,
    mu: float, sigma: float,
    steps: int = 5, simulations: int = 1000,
    dt: float = 1 / 252,      # 1 trading day
) -> float:
    """GBM Monte Carlo — reject nếu win prob < 50%

    Args:
        mu:    Daily drift = HMM emission mean hoặc realized_return_20d.mean()
        sigma: Daily vol   = realized_return_20d.std()
        dt:    Time step   = 1/252 (1 ngày giao dịch)
        steps: Horizon     = 5 ngày (~1 tuần swap T+5)
    """
    # ⚠️ Dùng biến ngoài i cho outer loop, j cho inner — tránh shadow
    rng    = np.random.default_rng()          # reproducible nếu seed được set
    sqrt_dt = sqrt(dt)
    wins   = 0

    for _i in range(simulations):
        S = entry
        hit_tp = False
        for _j in range(steps):
            S *= exp((mu - 0.5 * sigma**2) * dt + sigma * sqrt_dt * rng.standard_normal())
            if S >= tp1:
                hit_tp = True
                break
            if S <= sl:
                break
        if hit_tp:
            wins += 1

    return wins / simulations

if mc_win_probability(entry, sl, tp1, mu, sigma) < 0.50:
    return "REJECTED_MC", "Monte Carlo win probability < 50%"
```

### 4.5 Entry / SL / TP Calculation

```python
# Stop Loss (reconciled)
sl_atr   = entry - 1.5 * ATR14
sl_ema   = EMA20
sl_hard  = entry * 0.93          # hard cap -7%
final_sl = max(sl_atr, sl_ema, sl_hard)   # gần entry nhất

# Take Profit (Hurst-gated hybrid)
tp1, tp2 = calculate_tp(entry, ATR14, hurst_exponent(close))

# R/R Gate
rr = (tp1 - entry) / (entry - final_sl)
assert rr >= 2.0, "R/R insufficient — reject signal"

# Position Sizing
max_qty_risk   = (equity * 0.02) / (entry * exchange_band)   # worst-case sàn

# Kelly Criterion: f* = (wp × avg_win/avg_loss − (1−wp)) / (avg_win/avg_loss)
# Cap tại 25% để tránh over-leveraging
b              = avg_win / avg_loss          # win/loss ratio

# ⚠️ Kelly bootstrap guard: với < 30 giao dịch, win_rate chưa đủ thống kê (CLT cần n≥30)
# Giai đoạn đầu: dùng fixed 5% per trade — bảo thủ nhưng đúng
if trade_count < 30:
    kelly_f = 0.05                           # bootstrap phase: fixed fraction
else:
    kelly_f = max((wp * b - (1 - wp)) / b, 0.0)
    kelly_f = min(kelly_f, 0.25)             # hard cap 25% portfolio

kelly_qty      = (equity * kelly_f) / entry

qty            = min(max_qty_risk, kelly_qty)
qty            = (qty // 100) * 100     # 100-lot constraint HOSE/HNX

# ⚠️ Minimum lot guard: nếu qty < 100 sau round, position quá nhỏ — reject
if qty < 100:
    return "REJECTED_SIZE", "Position quá nhỏ: < 1 lô (100 cổ phiếu)"
```

### 4.6 Progressive Entry (50% + 50%)

```python
def progressive_entry(signal, current_bar, planned_qty: int, atr14: float):
    """
    planned_qty phải là bội số 100 (đã round_lot trước khi gọi).
    atr14: Average True Range 14 periods tại thời điểm signal.
    """
    half_qty = (planned_qty // 2 // 100) * 100  # round sub-tranche to 100-lot

    # Tranche 1: 50% ngay tại signal
    execute_buy(qty=half_qty, price=signal.entry)

    # Tranche 2: 50% còn lại — chỉ nếu close > VWAP AND no large upper shadow
    close_above_vwap = current_bar['Close'] > current_bar['VWAP']
    upper_shadow     = current_bar['High'] - max(current_bar['Open'], current_bar['Close'])
    small_shadow     = upper_shadow < atr14 * 0.50

    if close_above_vwap and small_shadow and half_qty >= 100:
        execute_buy(qty=half_qty, price=current_bar['Close'])
    else:
        log("Tranche 2 skipped — VWAP/shadow condition not met")
```

---

## Module 5: T+2.5 Risk Management Engine

### 5.1 Session Timeline

```
09:00–09:15  ATO monitor only
09:15–11:30  Morning entry window       ← HOSE morning session closes 11:30
11:30–13:00  Nghỉ trưa
12:45–13:15  *** T+2.5 DANGER WINDOW (ngày T+2) ***
13:00        Liquidity singularity — monitor
14:05–14:20  *** OPTIMAL afternoon entry window ***
14:30–14:45  ATC Router window            ← HOSE ATC 14:30–14:45
14:45        Market close
```

### 5.2 T+2.5 Exit Logic

```python
def t25_exit_check(
    position,
    current_bar,          # DataFrame row with Close, Volume, RSI14, VWAP
    market_time: str,
    rsi_series,           # recent RSI series (≥4 bars for comparison)
    mav20: float,         # 20-day average volume
) -> "ExitSignal":
    is_t2 = is_t2_of_position(position.entry_date)

    # Inline values from bar + series
    rsi_now     = current_bar['RSI14']
    rsi_3ago    = rsi_series.iloc[-4] if len(rsi_series) >= 4 else rsi_now
    rsi_prev    = rsi_series.iloc[-2] if len(rsi_series) >= 2 else rsi_now

    # Danger window check (12:45–13:15 on T+2)
    if is_t2 and is_t25_window(market_time):
        rsi_declining = rsi_now < rsi_3ago
        volume_spike  = current_bar['Volume'] > mav20 * 2.0
        below_vwap    = current_bar['Close'] < current_bar['VWAP']
        if rsi_declining and volume_spike and below_vwap:
            return ExitSignal.T25_FORCED_EXIT

    # Afternoon T+2 exit (14:00–14:45 on T+2)
    if is_t2 and market_time >= "14:00":
        if rsi_now > 70 and rsi_now < rsi_prev:
            return ExitSignal.ATC_EXIT_T2

    # RSI Climax exit (any day)
    if rsi_now > 80 and rsi_now < rsi_prev:
        return ExitSignal.RSI_CLIMAX_EXIT

    return ExitSignal.HOLD
```

---

## Module 6: Progressive Exit & Trailing Stop

```
PROGRESSIVE EXIT (tính theo cỔ PHẦN GỐC khi entry — không phải "remaining"):
    TP1 reached: Bán 40% của total_qty ban đầu        → còn lại 60%
    TP2 reached: Bán 40% của total_qty ban đầu nữa    → còn lại 20%
    Trailing:    Giữ 20% còn lại với trailing_sl = max(High_since_entry) × 0.95

    Ví dụ thực tế: Mua 1,000 cổ HPG @ 28,500
      TP1 (31,200): Bán 400 cổ → lãi 400 × 2,700 = +1,080,000 VND
      TP2 (33,500): Bán 400 cổ → lãi 400 × 5,000 = +2,000,000 VND
      Trailing:     Hold 200 cổ, SL = 33,500 × 0.95 = 31,825

    ⚠️ "40% of remaining" (cầu in Module 6 draft) đĦ sộ lượng = 40% x 60% = 24% total
    → Đã chuẩn hóa: cả hai lần bán đều tính theo TOTAL ban đầu

TRAILING STOP RULES:
    1. Activate only after position reaches +7% gain
    2. new_sl = max(current_sl, peak_price × 0.95)
    3. Never set sl below break-even once +7% achieved
    4. Floor: entry × 0.965 (max -3.5% floor for low-ATR stocks)

T+2.5 FORCED EXIT:
    If T+2 afternoon + unrealized_pnl > 8%: execute ATC exit
    (Avoid T+3 selling pressure)

MARGIN CALL PROTECTION:
    if broker_margin_ratio < safety_threshold:
        Partial exit — sell highest unrealized loss position first
```

---

## Module 7: NLP Advisory Engine

### 7.1 PhoBERT Sentiment + Advisory Generation

```
INPUT (Signal context JSON):
{
  "ticker": "HPG",
  "action": "STRONG_BUY",
  "mode": "MODE_A",
  "entry": 28500, "sl": 26790, "tp1": 31200, "tp2": 33500,
  "rr": 2.59, "mfpm_score": 78,
  "triggers": ["wyckoff_spring", "zvol_2.1", "rsi_crossup_41", "vcp_detected",
               "amd_accumulation", "vsa_no_supply", "whale_net_buy"],
  "fol_status": "FOREIGN_BUY",
  "canslim_score": 65,
  "hurst": 0.61,
  "hmm_state": "STEADY_BULL",
  "cvd_whale_net": 125000,
  "vsa_signal": "NO_SUPPLY",
  "amd_phase": "ACCUMULATION",
  "phobert_sentiment": 0.78
}

OUTPUT (Vietnamese advisory):
"၆ệ thống nhận diện HPG đang hình thành bẫy rũ hàng (Spring) tại vùng
hỗ trợ 28,200–28,500 với khối lượng cạn kiệt và 2 nhịp nén VCP.
Dòng tiền nước ngoài đang tích lũy (room còn 38%). RSI vừa cắt lên
từ 41 trong xu hướng tăng dài hạn. Hurst = 0.61 → thị trường
đang trending mạnh. Cá voi mua ròng 125,000 cổ. AMD: Đang tích lũy.
Khuyến nghị MUA: Giá vào 28,500 | Cắt lỗ 26,790 (-6.0%)
Mục tiêu 1: 31,200 (+9.5%) | Mục tiêu 2: 33,500 (Fib 2.618, +17.5%)
R/R = 2.59 | Điểm MFPM: 78/120 (STRONG_BUY)
MUA vì: ✅ Volume đột biến (+25) | ✅ Spring Wyckoff (+15) | ✅ Cá voi mua ròng (+15)
         ✅ VQS xác nhận (+15) | ⚠️ CAN SLIM score thấp (-10)"
```

### 7.2 SHAP Explainability

**Nguồn:** *Proposal v5 — "Module SHAP Values giải thích lý do khà nghị"*. Tăng transparency và học lại từ các lần sai.

```python
def generate_shap_explanation(mfpm_components: dict) -> list[str]:
    """
    Giải thích nhân tố đóng góp nhiều nhất vào MFPM score.
    mfpm_components: {"wyckoff_spring": 15, "zvol": 25, "vwap": 15, ...}
    Output: top 5 factors với sign, hiển thị trong UI và advisory text.
    """
    FACTOR_LABELS = {
        "wyckoff_spring" : "Spring Wyckoff",
        "zvol"           : "Volume đột biến",
        "vwap"           : "Giá > VWAP",
        "vcp"            : "VCP nén biến động",
        "rsi_crossup"    : "RSI cắt lên",
        "bullish_div"    : "Phân kỳ tăng RSI",
        "vqs"            : "Chất lượng volume (VQS)",
        "cvd_whale"      : "Cá voi mua ròng (CVD)",
        "vsa_no_supply"  : "VSA No Supply",
        "vsa_absorption" : "VSA Absorption",
        "vsa_no_demand"  : "VSA No Demand (rủi ro)",
        "order_block"    : "Order Block",
        "cup_handle"     : "Cup with Handle",
        "fol"            : "Dòng tiền ngoại",
        "amd_accum"      : "AMD: Tích lũy",
        "canslim"        : "CAN SLIM thấp",
        "adx_weak"       : "Trend yếu (ADX < 20)",
        "delta_div"      : "Delta Divergence (rủi ro)",
    }
    sorted_factors = sorted(mfpm_components.items(), key=lambda x: abs(x[1]), reverse=True)
    return [
        f"{'\u2705' if v > 0 else '\u26a0\ufe0f'} {FACTOR_LABELS.get(k, k)}: {'+' if v>0 else ''}{v}"
        for k, v in sorted_factors[:5]
    ]
```

---

### 7.3 Dữ Liệu Nền Tảng NLP — XBRL (Phase 3+)

**Vấn đề:** PhoBERT advisory hiện dùng các trường EPS/doanh thu từ SSI EP-10 (BCTC bán cấu trúc). Các số liệu này có thể khác với báo cáo gốc do re-formatting.

**Giải pháp (Phase 3+):** Sử dụng file báo cáo tài chính định dạng **XBRL** từ hệ thống công bố thông tin **IDS** của Ủy ban Chứng khoán Nhà nước (SSC) — đây là nguồn số liệu chính thức, có cấu trúc máy đọc được, đảm bảo chính xác theo có định nghĩa.

```
XBRL Data Flow (Phase 3+):
  SSC IDS Portal (ssc.gov.vn/disclosure)
      └→ Download XBRL instance documents per ticker
           └→ parse_xbrl(filepath) → structured dict
                └→ {eps_qoq, revenue_yoy, roe, debt_equity, guidance_text}
                     └→ feed into PhoBERT context window
                          └→ richer, more accurate advisory generation

Phase 1-2 fallback: SSI EP-10 (current) — continue using
Phase 3+:          Supplement/replace with XBRL where available
```

> **Backlog #15:** XBRL parser + SSC IDS integration. Estimated effort: 1 sprint.
> Dependency: SSC public API availability (portal hiện tải manual download).

---

## Module 8: Backtesting Engine — VN-Constrained

### 8.1 Risk-Adjusted Momentum Weighting (Portfolio Allocation)

**Nguồn:** *Proposal v5 — công thức Risk-Adjusted Momentum Weighting*. Cổ phiếu có momentum cao và volatility thấp được cân nặng nhiều hơn:

$$w_i = \frac{RS_i / \sigma_i}{\sum_j (RS_j / \sigma_j)}$$

Trong đó: $RS_i$ = RS Rating (composite 3/6/9/12 tháng), $\sigma_i$ = độ lệch chuẩn return 20 phiên

```python
def risk_adjusted_weights(signals: list, max_single_pct: float = 0.25) -> dict:
    raw   = {s["ticker"]: s["rs_rating"] / max(s["sigma_20d"], 0.001) for s in signals}
    total = sum(raw.values())
    if total <= 0:
        n = len(signals)
        return {s["ticker"]: 1.0 / n for s in signals}  # equal weight fallback
    weights   = {ticker: score / total for ticker, score in raw.items()}
    capped, excess = {}, 0.0
    for ticker, w in weights.items():
        if w > max_single_pct:
            capped[ticker] = max_single_pct
            excess += w - max_single_pct
        else:
            capped[ticker] = w
    under_cap   = {t: w for t, w in capped.items() if w < max_single_pct}
    under_total = sum(under_cap.values())
    if under_total > 0:
        for ticker in under_cap:
            capped[ticker] += excess * (capped[ticker] / under_total)
    return capped
```

### 8.2 VN Backtest Constraints

**Ràng buộc đặc thù VN:**

```python
class VNBacktestConstraints:
    T0_SAME_DAY_SELL    = False   # Default False; True nếu broker hỗ trợ T+0
    T2_SELL_START       = "13:00" # Chỉ bán từ phiên chiều T+2
    MIN_LOT_SIZE        = 100     # Bội số 100 cổ phiếu
    BUY_COMMISSION      = 0.0015  # 0.15% (SSI standard — broker-dependent)
    SELL_COMMISSION     = 0.0025  # 0.25% (SSI standard — broker-dependent)
    MIN_COMMISSION_VND  = 1_000   # Tối thiểu 1,000 VND/lệnh — quan trọng với lệnh nhỏ
    SELL_TAX            = 0.001   # 0.1% thuế TNCN trên giá trị bán
    # ⚠️ Slippage tiếp theo liquidity tier — không flat 0.1% cho mọi mã
    ATC_SLIPPAGE_VN30      = 0.001  # 0.1%  — liquid blue-chip (top 30)
    ATC_SLIPPAGE_MIDCAP    = 0.003  # 0.3%  — midcap (500tỷ–2000tỷ vốn hóa)
    ATC_SLIPPAGE_SMALLCAP  = 0.007  # 0.7%  — smallcap, spread rộng, low float
    LOCK_SAN_PROB       = 0.02    # 2% xác suất lock sàn khi hit SL

class BacktestResult:
    total_return         : float
    annualized_return    : float
    win_rate             : float     # target >= 55%
    avg_rr_ratio         : float     # target >= 2.0
    max_drawdown         : float     # target <= 25%
    sharpe_ratio         : float     # target >= 1.2
    calmar_ratio         : float
    num_trades           : int
    avg_hold_days        : float
    t25_forced_exits     : int
    circuit_breaker_hits : int
    mc_rejected_signals  : int


def walk_forward_backtest(
    strategy_fn,
    full_df: 'pd.DataFrame',
    train_years: int = 2,
    test_months: int = 6,
    min_trades_per_window: int = 10,
) -> list['BacktestResult']:
    """
    Walk-Forward Validation để chống bull-bias (2020–2025 là giai đoạn đặc biệt).

    Cơ chế:
      1. Train trên 2 năm (in-sample) → calibrate parameters
      2. Test trên 6 tháng tiếp theo (out-of-sample) → đo lường real performance
      3. Tiếp tục trượt cửa sổ cho đến hết data

    Mục tiêu: win_rate OOS ≥ win_rate IS × 0.85 (không gấp đôi trong IS)
    """
    trading_days = 252
    train_size   = train_years * trading_days
    test_size    = test_months * 21     # ~21 phiên/tháng

    results = []
    start   = 0
    while start + train_size + test_size <= len(full_df):
        train_df = full_df.iloc[start : start + train_size]
        test_df  = full_df.iloc[start + train_size : start + train_size + test_size]

        # Phase 1: calibrate trên train window
        params = strategy_fn.calibrate(train_df)           # HMM refit, threshold optimization

        # Phase 2: run trên test window (out-of-sample) với params cố định
        result = strategy_fn.run(test_df, params)
        if result.num_trades >= min_trades_per_window:
            results.append(result)

        start += test_size    # trượt 6 tháng

    return results

# Phân tích: so sánh IS vs OOS win_rate
# Nếu OOS win_rate < IS × 0.85 → model overfit → cần đơn giản hóa (giảm features)
# Nếu OOS Sharpe < 0.8 → hệ thống không robust → review MFPM threshold

---

## Module 9: Signal Data Schema (API / JSON)

```json
{
  "signal_id": "uuid4",
  "timestamp": "2026-03-30T09:35:00+07:00",
  "ticker": "HPG",
  "exchange": "HOSE",
  "action": "STRONG_BUY",
  "mode": "MODE_A",
  "entry_price": 28500,
  "stop_loss": 26790,
  "tp1": 31200,
  "tp2": 33500,
  "rr_ratio": 2.59,
  "mfpm_score": 78,
  "canslim_score": 65,
  "hurst_exponent": 0.61,
  "hmm_state": "STEADY_BULL",
  "gmo_omega": 0.55,
  "fol_status": "FOREIGN_BUY",
  "fol_room_pct": 0.38,
  "triggers": ["wyckoff_spring", "zvol_2.1", "rsi_crossup_41", "vcp_2_contractions",
               "amd_accumulation", "vsa_no_supply", "order_block_bullish"],
  "circuit_breaker": "OK",
  "mc_win_prob": 0.63,
  "amd_phase": "ACCUMULATION",
  "vsa_signal": "NO_SUPPLY",
  "cvd_whale_net": 125000,
  "order_block": {"type": "BULLISH_OB", "low": 28100, "high": 28400},
  "cup_with_handle": {"detected": false},
  "phobert_sentiment": 0.78,
  "shap_top5": ["\u2705 Volume đột biến: +25", "\u2705 Spring Wyckoff: +15", "\u2705 Cá voi mua ròng: +15",
                "\u2705 VQS + OBV: +15", "\u26a0\ufe0f CAN SLIM thấp: -10"],
  "qty_suggested": 1000,
  "position_pct": 12.5,
  "exposure_mode": "50+50",
  "advisory_vn": "...",
  "advisory_en": "..."
}
```

---

# PHẦN IV — KIẾN TRÚC HỆ THỐNG {#phần-iv}

## 4.1 Layered Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        STREAMLIT UI LAYER                            │
│   Scanner | Profiler | Backtest | Realtime | Portfolio | Settings    │
└────────────────────────────────┬─────────────────────────────────────┘
                                  │
┌────────────────────────────────┴─────────────────────────────────────┐
│                         CORE ENGINES LAYER                           │
│                                                                      │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐  │
│  │ GMO +     │ │ CAN SLIM  │ │   MFPM    │ │  Smart ATC Router   │  │
│  │ HMM +     │ │ Universe  │ │  Module 4 │ │  (Execution Layer)  │  │
│  │ Hurst     │ │ Module 2  │ │           │ └─────────────────────┘  │
│  │ Module 1  │ └───────────┘ └───────────┘                          │
│  └───────────┘                                                       │
│                                                                      │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐  │
│  │  T+2.5    │ │ Trailing  │ │ Patterns  │ ┌─────────────────────┐  │
│  │  Engine   │ │  Stop     │ │ VCP+Spring│ │  NLP + SHAP         │  │
│  │ Module 5  │ │ Module 6  │ │ +Weis Wave│ │  Advisory Module 7  │  │
│  └───────────┘ └───────────┘ │ +OB+CwH   │ └─────────────────────┘  │
│                               │ Module 3  │                           │
│                               └───────────┘                          │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  Monte Carlo (GBM) | Hurst Exponent | Kalman Herding          │   │
│  │  Anti-Manipulation (AMD+VSA+CVD+VQS) Module 2.9–2.10          │   │
│  └───────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬─────────────────────────────────────┘
                                  │
┌────────────────────────────────┴─────────────────────────────────────┐
│                           DATA LAYER                                 │
│                                                                      │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐   │
│  │  fetcher.py          │    │  cache.py (DuckDB)               │   │
│  │  SSI EP-1,3,4,6,7,10 │    │  ohlcv | scan_results |          │   │
│  │  DNSE fallback       │    │  signal_history | orders          │   │
│  └──────────────────────┘    └──────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐   │
│  │  realtime.py         │    │  normalizer.py                   │   │
│  │  SSI EP-3 polling    │    │  Ex-div adjustment               │   │
│  │  EP-4 order book     │    │  Tick rounding | VND format      │   │
│  └──────────────────────┘    └──────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

## 4.2 Technology Stack

| Component | Technology | Lý do |
|---|---|---|
| UI | Streamlit ≥ 1.35 | F0-friendly, rapid iteration |
| Language | Python 3.10+ | Data science ecosystem |
| **Database** | **DuckDB** (không PostgreSQL) | Embedded, zero-config, ~200K rows tested |
| Charts | Plotly ≥ 5.20 | Interactive, Streamlit-native |
| HTTP | requests + retry adapter | SSI device-id auth (no OAuth2) |
| Config | TOML (default.toml + local.toml) | Secret/config separation |
| HMM | hmmlearn | GaussianHMM, stable, scikit-learn compatible |
| ML Optional | TensorFlow / Prophet | Phase 5 only |
| Infra | Docker + Compose | Self-contained deployment |
| CI/CD | GitHub Actions | Lint + test + coverage |
| Alert | Telegram webhook | Mobile notification F0 |

## 4.3 SSI API Endpoints (Confirmed from HAR Log)

**Authentication:** `device-id: <UUID>` header only — **No OAuth2**

| Endpoint | URL | Note |
|---|---|---|
| EP-1 OHLCV | `GET iboard-api.ssi.com.vn/statistics/charts/history?resolution=1D&symbol=X&from=ts&to=ts` | No device-id; dùng `resolution=5` cho 5-min bars |
| EP-2 Ticker Meta | `GET iboard-api.ssi.com.vn/statistics/charts/symbol?symbol=X` | Sector, industry, exchange info |
| EP-3 Quote | `GET iboard-query.ssi.com.vn/stock/{TICKER}?boardId=MAIN` | device-id required; foreignCurrentPercent, foreignPercent |
| EP-4 Order Book | `GET iboard-query.ssi.com.vn/le-table/stock/{TICKER}?pageSize=50` | device-id required; ATC ECP calculation |
| EP-5 System Time | `GET iboard-query.ssi.com.vn/system/time` | Server timestamp — sync với VN exchange time |
| EP-6 Group | `GET iboard-query.ssi.com.vn/stock/group/{VN30\|VN100\|VNMID}` | device-id required |
| EP-7 Market Stat | `GET iboard-query.ssi.com.vn/market-stat/exchange/{hose\|hnx\|upcom}` | No device-id; A/D ratio |
| EP-8 Company Profile | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/company-profile?symbol=X&language=vn` | Sector / industry cho portfolio constraints |
| EP-9 Same-Industry | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/company-in-same-industry?symbol=X&language=vn` | **Sector peers** — dùng để build sector classification |
| EP-10 Financials | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/finance-indicator?symbol=X&pageSize=1000` | device-id required; EPS, ROE, P/E |
| EP-11 Corporate Actions | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/corporate-actions?symbol=X&language=vn` | **Ex-dividend dates** — bắt buộc cho adjusted_close |
| EP-12 Cap & Dividend | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/cap-and-dividend?symbol=X` | Market cap, dividend yield — universe filter |
| EP-13 Shareholder Summary | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/share-holder-summary?symbol=X&language=vn` | CAN SLIM 'I' — institutional ownership trend |
| EP-14 Company News | `GET iboard-api.ssi.com.vn/statistics/company/ssmi/company-news?symbol=X&language=vn` | NLP module catalyst detection |
| DNSE Fallback | `GET services.entrade.com.vn/chart-api/v2/history?resolution=D&symbol=X&from=ts&to=ts` | Fallback nếu EP-1 bị rate-limit |

**Common Headers:**
```
device-id: <rotate-when-blocked>
origin: https://iboard.ssi.com.vn
referer: https://iboard.ssi.com.vn/
accept: application/json, text/plain, */*
user-agent: Mozilla/5.0 Chrome/145
accept-language: vi
```

---

# PHẦN V — KẾ HOẠCH TRIỂN KHAI 5 PHASES {#phần-v}

## Phase 1: Foundation — Tuần 1–2

> **Mục tiêu:** `utils/` + `data/` — toàn bộ IO, không domain logic

| # | File | Nội dung | Priority |
|---|---|---|---|
| 1 | `utils/logging.py` | Rotating logger factory (file + console) | P0 |
| 2 | `utils/datetime_vn.py` | VN holidays 2025/2026, `is_trading_day()`, `t_plus_2_date()`, `is_t25_window()`, trading hours | P0 |
| 3 | `utils/http.py` | `build_session()` → requests.Session, SSI headers, retry 429/503 | P0 |
| 4 | `utils/math_utils.py` | `round_to_tick()` (VN tick scale — xem bảng bên dưới), `round_lot()` → 100-lot, VND formatter | P0 |

> **VN Tick Size Table** (HOSE/HNX — bắt buộc cho limit order pricing):
>
> | Giá (VND) | Bước giá (tick) |
> |---|---|
> | < 10,000 | 10 VND |
> | 10,000 – 49,950 | 50 VND |
> | ≥ 50,000 | 100 VND |
>
> ```python
> def round_to_tick(price: float) -> int:
>     if price < 10_000:  tick = 10
>     elif price < 50_000: tick = 50
>     else:                tick = 100
>     return int(round(price / tick) * tick)
> ```
>
> **Order Types VN** (cần biết để `execution.py` built đúng):
>
> | Loại lệnh | Sàn | Mô tả |
> |---|---|---|
> | LO (Limit Order) | HOSE, HNX, UPCOM | Lệnh giới hạn chuẩn |
> | ATO | HOSE, HNX | Mở cửa — khớp theo giá mở |
> | ATC | HOSE, HNX | Đóng cửa — khớp theo giá đóng |
> | **MTL (Market-To-Limit)** | **HOSE** — **chỉ phiên chiều** | Gửi như Market nhưng chuyển LO nếu chưa khớp — dùng cho afternoon entry nhanh |
> | MP (Market Price) | HNX only | Market order thực sự — slippage cao |
| 5 | `data/normalizer.py` | `normalize_ohlcv(raw, source)` → standard DataFrame; **ex-dividend adjustment** | P0 |
| 6 | `data/fetcher.py` | `fetch_ohlcv()` SSI→DNSE; `fetch_quote()` EP-3; `fetch_group()` EP-6; `fetch_market_stat()` EP-7; `fetch_financials()` EP-10 | P0 |
| 7 | `data/cache.py` | DuckDB 4 tables; TTL: OHLCV daily=next market open, realtime=60s, scan_results=end-of-day, financials=90d | P0 |
| 8 | `data/realtime.py` | Polling EP-3 quotes; EP-4 order book; ST/UT status check | P1 |
| 9 | `scripts/backfill_ohlcv.py` | Wire to fetcher + cache | P1 |
| 10 | `tests/unit/test_utils.py`, `test_data.py` | Mock HTTP, pure logic | P0 |

**DuckDB Tables:**
```sql
-- TTL convention: fetched_at + interval → stale if now() > fetched_at + ttl
ohlcv          (ticker, date, open, high, low, close, volume, exchange,
                adjusted_close, sector, fetched_at)
                -- TTL: daily bars → stale after next market open (17:00 same day)

scan_results   (ticker, scan_date, mfpm_score, signal, entry, sl, tp1, tp2,
                mode, expires_at)
                -- TTL: expires_at = scan_date + 1 trading day

signal_history (id, ticker, signal_date, action, entry, sl, tp1, tp2, rr,
                mfpm_score, canslim_score, hurst, hmm_state, reason, mc_win_prob)
                -- No TTL — permanent record for performance tracking

orders         (id, ticker, side, qty, price, order_type, status,
                submitted_at, filled_at, fill_price)
                -- No TTL — permanent audit log

-- Extra: financials cache
financials     (ticker, period, eps, roe, pe, revenue_growth, fetched_at)
                -- TTL: 90 days (quarterly reports)

-- Extra: sector lookup
sector_map     (ticker, exchange, sector, industry, market_cap_tier, updated_at)
                -- TTL: weekly (VN30 rebalanced Jan/Jul, sector changes rare)
```

**Verification:**
```bash
python scripts/backfill_ohlcv.py --tickers HPG,VCB,FPT --days 30
# → rows in DuckDB; adjusted_close ≠ close on ex-div dates
pytest tests/unit/ -v → 100% pass
```

---

## Phase 2: Core Engines — Tuần 3–5

> **Mục tiêu:** `core/` + `engines/` — domain logic thuần, zero IO

| # | File | Nội dung |
|---|---|---|
| 1 | `core/calendar.py` | Trading hours, VN holidays, `sessions_between()`, T+2 date |
| 2 | `engines/technical.py` | SMA/EMA, RSI, MACD, BB, ATR, ADX, VWAP, Z_vol, RSI cross-up; **Hurst Exponent** |
| 3 | `engines/screening.py` | MFPM Mode A + B; Circuit Breaker gate; FOL analysis; CAN SLIM score computation |
| 4 | `engines/pattern.py` | VCP detection; Wyckoff Spring; FVG; Weis Wave |
| 5 | `engines/microstructure.py` | OFI from EP-4; Foreign flow; T+2.5 window check; ATO gap flag |
| 6 | `engines/advanced.py` | **HMM 3-state** (hmmlearn); **Monte Carlo GBM**; **Kalman herding filter** |
| 7 | `core/signals.py` | `Signal` dataclass; `classify_signal()`; R/R gate; MC gate |
| 8 | `core/risk.py` | ATR levels (reconciled SL); Kelly ≤25%; 2% equity rule; worst-case (exchange band); `trailing_stop()` |
| 9 | `core/strategy.py` | `T25SwingStrategy` state machine: IDLE→PILOT→FULL→TRAILING→EXITED; progressive entry/exit |
| 10 | `core/gmo.py` | GMO Ω score; HMM integration; Basis VN30F; Breadth (A/D ratio); Herding |
| 11 | `engines/backtest.py` | VN-constrained simulation; T+2 settlement; lot/commission/tax; ATC exit; lock-sàn probability |
| 12 | Tests | `test_technical.py`, `test_screening.py`, `test_risk.py`, `test_patterns.py` |

**Verification:**
```bash
pytest tests/unit/ -v --tb=short
# → 100% pass, zero HTTP calls, zero DB calls
```

---

## Phase 3: UI Layer — Tuần 6–7

> **Mục tiêu:** `ui/` — Streamlit 6-page app

| Page | File | Chức năng |
|---|---|---|
| Scanner | `ui/pages/scanner.py` | Universe 200+ mã; MFPM ranked table; FOL flags; HMM state badge; click → Profiler |
| Profiler | `ui/pages/profiler.py` | Chart: SMA50/200, VWAP, RSI, Z-vol; SL/TP lines; Wyckoff label; VCP overlay; Hurst gauge |
| Backtest | `ui/pages/backtest.py` | Date range; equity curve; metrics table; VN-constraint summary |
| Realtime | `ui/pages/realtime.py` | VN30 quote table; market stat; T+2.5 countdown; ATC ECP display; GMO status |
| Portfolio | `ui/pages/portfolio.py` | Active positions; trailing stop update; T+2.5 danger alerts; P&L |
| App | `ui/app.py` | `st.navigation()`; sidebar: HMM state, GMO Ω, DuckDB stats, VN market time |
| CLI | `src/tradingos/cli.py` | `tradingos serve \| scan \| backfill \| scan-atc` |

**Verification:**
```bash
tradingos serve
# → Scanner: ≥200 mã loaded; Profiler: HPG chart with all overlays; Realtime: VN30 quotes
```

---

## Phase 4: Backtesting & Validation — Tuần 8–9

1. Backfill VN30 + top 50 HOSE mid-caps, 400 ngày (dùng adjusted price)
2. Chạy MFPM Mode A + B trên dữ liệu 2020–2025
3. PSO Optimization: Particle Swarm tìm tham số RSI/ATR tối ưu theo từng năm
   → `engines/optimizer.py` — `pso_optimize(strategy, param_grid, data)` (pyswarms hoặc scipy)
4. Benchmark vs VN-Index buy-and-hold

**KPI Targets:**

| Metric | Target |
|---|---|
| Win Rate | ≥ 55% |
| Average R/R | ≥ 2.0 |
| Max Drawdown | ≤ 25% |
| Sharpe Ratio | ≥ 1.2 |
| Calmar Ratio | ≥ 1.5 |

5. **UAT Paper Trading (theo PMBOK):** 4 tuần với live data trước live execution
6. `tests/integration/test_backtest.py`: end-to-end HPG 60 days → MFPM → verify schema

---

## Phase 5: NLP + Execution + Deployment — Tuần 10–12

1. `engines/nlp.py` — Gemini API → Vietnamese advisory text
2. `engines/execution.py` — `OrderRequest` stub → DuckDB orders table → Telegram webhook alert
3. `Dockerfile` + `docker-compose.yml` (Streamlit + scheduled scanner)
4. Update `ci.yml` — full test + coverage ≥ 70%
5. `config/local.toml` — user phải tạo tay (never committed to VCS):
   ```toml
   [api]
   ssi_device_id = "<your-uuid>"
   gemini_api_key = "<your-key>"
   telegram_bot_token = "<your-token>"
   telegram_chat_id = "<your-id>"
   ```

---

# PHẦN VI — BẢNG QUYẾT ĐỊNH MÂU THUẪN {#phần-vi}

| # | Mâu thuẫn | Quyết định cuối | Lý do |
|---|---|---|---|
| 1 | Stop-loss -5% vs -7% | **ATR×1.5 + EMA(20) break với hard cap -7%** | Reconciled — ATR primary, -7% safety net |
| 2 | RSI trigger: 40 vs 50-65 | **Cả hai — Mode A (≤50 cross-up) + Mode B (50-65 breakout)** | Hai entry type khác nhau |
| 3 | RSI exit threshold | **RSI > 80 + declining = RSI_CLIMAX_EXIT** | Bổ sung từ proposal mới |
| 4 | TP: 15% cố định vs Fib vs ATR | **ATR primary + Fibonacci nếu Hurst > 0.55** | Hurst-gated hybrid, backtested best |
| 5 | Fibonacci extension | **Giữ CÓ ĐIỀU KIỆN (Hurst gate)** | Không đếm sóng — dùng như statistical target |
| 6 | Elliott Wave | **Loại bỏ hoàn toàn** | Không tự động hóa được đáng tin cậy |
| 7 | PostgreSQL vs DuckDB | **DuckDB** | Proven, zero-config, 200K rows OK |
| 8 | OAuth2 vs device-id | **device-id UUID** | HAR log confirmed |
| 9 | Universe: VN30 vs 1600→200 | **HOSE+HNX liquidity filter → 200–280 mã** | API data constraints thực tế |
| 10 | GMO Accuracy "96.67%" | **Loại bỏ claim** | Overfitting; GMO là filter không phải predictor |
| 11 | ATC execute timing | **14:43:00** | Time priority — ưu tiên trước lệnh muộn |
| 12 | T+2.5 danger window | **12:45–13:15** | Code confirmed + academic research |
| 13 | GMO Ω only vs HMM only | **Cả hai: HMM primary + GMO sanity check** | HMM statistical; GMO fundamental |
| 14 | Entry afternoon: 13:00 vs 14:05 | **14:05–14:20** | Sau khi T+2 hàng hấp thụ xong |
| 15 | Simple entry vs Progressive | **50%+50% VWAP-confirmed** | Giảm rủi ro false signal |
| 16 | Single-timeframe vs Multi | **Weekly gate + Daily execution** | Weekly uptrend phải xác nhận trước |

---

# PHẦN VII — KIỂM SOÁT RỦI RO & COMPLIANCE {#phần-vii}

## 7.1 Per-Trade Risk Gates

| Gate | Rule | Action nếu fail |
|---|---|---|
| Pre-condition gate | HMM ≠ BEAR + SMA50>SMA200 + weekly uptrend | REJECT |
| Circuit breaker | Price ≤ ceiling×0.99 và ≥ floor×1.01 | REJECT |
| R/R gate | R/R ≥ 2.0 | REJECT |
| Monte Carlo gate | MC_win_prob ≥ 0.50 | REJECT_MC |
| Lot constraint | qty = multiple of 100 | Auto-adjust |
| Liquidity gate | avg_vol_20d ≥ 500,000 | REJECT |

## 7.2 Portfolio-Level Risk

```python
MAX_PORTFOLIO_EXPOSURE      = 0.60   # max 60% vốn đầu tư cùng lúc
MAX_POSITIONS               = 5
MAX_SINGLE_SECTOR           = 0.25   # tránh tập trung 1 ngành
MAX_SECTOR_CORRELATION      = 0.70   # không thêm nếu correlation cao
MIN_CASH_BUFFER             = 0.20   # luôn giữ ≥20% tiền mặt
MARGIN_SAFETY_RATIO         = 1.50   # dừng mua thêm nếu margin < 150%
```

> **Nguồn sector classification:** Dùng SSI EP-8 (`company-profile?symbol=X`) → trường `industryName` / `sector`. Build lookup table `{ticker: sector}` khi backfill. EP-9 (`company-in-same-industry`) dùng để cross-check và bổ sung mã cùng ngành chưa trong watchlist.

## 7.3 Known Risk Scenarios

| Rủi ro | Cơ chế phòng vệ |
|---|---|
| Lock sàn — không thoát được | Worst-case sizing theo exchange band; position cap thấp hơn |
| Margin call cascade | Portfolio-level exposure cap; minimum cash buffer |
| SSI API blocked | device-id rotation; DNSE fallback |
| Data staleness | DuckDB TTL; `fetched_at` check trước mỗi trade |
| FOL trap | `ROOM_DAY` → disable foreign Z-score signal |
| ATC manipulation | ECP deviation > 2.5% → cancel tất cả ATC orders |
| Herding distribution | Kalman herding detection → force RISK_OFF |
| Narrow rally | A/D ratio < 1.0 → giảm GMO Ω; cảnh báo |
| Earnings look-ahead bias | Dùng point-in-time data: EPS chỉ available sau report_date +45 ngày |
| **Fake Spring trap** | **`detect_spring_quality()` → SPRING_FAKE_SELL = BLOCK** |
| **Wash Trading / Volume gả** | **VQS WASH_TRADING_SUSPECT flag → giảm -20 điểm; auto-reject nếu VQS < -0.3** |
| **Fake Breakout (Mode B)** | **`second_mouse_gate()` → FAKE_BREAKOUT = loại hỏa; WAIT_RETEST = giữ watchlist** |
| **Insider Run trước sự kiện** | **`detect_insider_run()` → WARN flag + giảm MFPM -15 điểm** |

## 7.4 Margin Trading Adjustments

```python
if account_uses_margin:
    max_single_position_pct = 0.15   # giảm từ 25% xuống 15%
    sl_multiplier = 0.85              # SL chặt hơn 15%
    if hv20 > 0.30:                   # không margin với stocks biến động cao
        raise ValueError("REJECT: High HV20 — margin not allowed")
    worst_case_sizing *= (1 + margin_ratio)  # tính thêm leverage exposure
```

---

# PHẦN VIII — BACKLOG BỔ SUNG (13 ITEMS) {#phần-viii}

| # | Vấn đề | Phase | Priority |
|---|---|---|---|
| 1 | **T+0 Same-Day Trading flag** — broker VN cho phép từ 11/2024; cần `account_has_t0 = True/False` trong config, mở thêm intraday exit nếu enabled | Phase 1 | 🔴 Critical |
| 2 | **Ex-Dividend price adjustment** — normalize adjusted_close để ATR/RSI/SMA tính đúng; dùng SSI EP corporate-actions | Phase 1 | 🔴 Critical |
| 3 | **Progressive Entry Pilot→Add→Full** — 6.25%→12.5%→6.25% khi position có lãi; áp dụng với positions lớn (>5 tỷ VND) | Phase 2 | 🔴 Critical |
| 4 | **Portfolio-level risk** — max exposure 60%, max 5 positions, max sector 25%, sector correlation < 0.70 | Phase 2 | 🔴 Critical |
| 5 | **MACD as optional confirming indicator** — +5 điểm MFPM nếu histogram dương; không phải hard gate | Phase 2 | 🔴 Critical |
| 6 | **Multi-timeframe gate** — Weekly SMA50 > SMA200 phải true trước khi cho daily signal | Phase 2 | 🔴 Critical |
| 7 | **Margin trading risk adjustments** — max position 15%, SL chặt hơn, reject cao-biến-động | Phase 2 | 🔴 Critical |
| 8 | **Market Breadth trong GMO** — A/D ratio từ SSI EP-7; `NARROW_RALLY` flag khi VNI tăng nhưng breadth yếu | Phase 2 | 🟡 Important |
| 9 | **ST/UT/HA detection** — `tradingStatus` từ EP-3; loại khỏi universe | Phase 1 | 🟡 Important |
| 10 | **5-min intraday bars cho execution** — SSI EP-1 `resolution=5`; time entry tại pullback VWAP intraday thay vì market order cuối phiên | Phase 3 | 🟡 Important |
| 11 | **Look-ahead bias prevention** — EPS chỉ available sau `report_date + 45 days`; point-in-time data trong backtest | Phase 4 | 🟡 Important |
| 12 | **Market impact cost** — accounts lớn: `impact = 0.1 × (qty / avg_daily_vol_qty)`; recalculate R/R với effective entry | Phase 4 | 🟢 Nice-to-have |
| 13 | **Covered Warrant hedging** — Mua Put CW trên portfolio holdings khi GMO = CAUTIOUS; architecture hook để tích hợp Phase 5+ | Phase 5 | 🟢 Nice-to-have |

---

# PHỤ LỤC

## A. File Structure — `d:\portfolio\TradingOS\`

```
TradingOS/
├── .github/workflows/ci.yml
├── .gitignore
├── config/
│   ├── default.toml          ← SSI/DNSE URLs, DuckDB path, strategy params
│   └── local.toml            ← SECRETS (never commit: device-id, API keys)
├── data/
│   ├── vn_cache.duckdb       ← DuckDB database
│   └── Trading OS 331e99f8...md ← original proposal reference (read-only)
│
│  ⚠️  SSI HAR log thực tế ở: d:\portfolio\data\SSI_HARrequestLogs.txt
│      (không nằm trong TradingOS/ — copy vào data/ nếu cần tham khảo)
├── docs/proposal/
│   └── TradingOS-Alpha-Proposal-v1.0.md  ← THIS FILE
├── pyproject.toml
├── README.md
├── requirements.txt / requirements-dev.txt
├── scripts/
│   └── backfill_ohlcv.py
└── src/tradingos/
    ├── __init__.py           (version="0.1.0")
    ├── cli.py
    ├── core/
    │   ├── calendar.py
    │   ├── gmo.py            ← GMO Ω + HMM + Breadth + Herding
    │   ├── risk.py
    │   ├── signals.py
    │   └── strategy.py       ← T25SwingStrategy state machine
    ├── data/
    │   ├── cache.py          ← DuckDB
    │   ├── fetcher.py        ← SSI cascade → DNSE
    │   ├── normalizer.py     ← Ex-div adjustment
    │   └── realtime.py       ← EP-3 polling + EP-4 order book
    ├── engines/
    │   ├── advanced.py       ← HMM + Monte Carlo GBM + Kalman
    │   ├── backtest.py       ← VN-constrained simulation
    │   ├── microstructure.py ← OFI + Foreign flow + T+2.5
    │   ├── nlp.py            ← Gemini API → Vietnamese advisory (Phase 5)
    │   ├── optimizer.py      ← PSO parameter optimization (Phase 4)
    │   ├── pattern.py        ← VCP + Spring + FVG + Weis Wave
    │   ├── screening.py      ← MFPM Mode A + B
    │   └── technical.py      ← Indicators + Hurst Exponent
    ├── ui/
    │   ├── app.py
    │   ├── components.py
    │   ├── pages/
    │   │   ├── backtest.py
    │   │   ├── portfolio.py
    │   │   ├── profiler.py
    │   │   ├── realtime.py
    │   │   └── scanner.py
    │   └── styles.py
    └── utils/
        ├── datetime_vn.py
        ├── http.py
        ├── logging.py
        └── math_utils.py
```

## B. Research Sources

- O'Neil, W.J. — *How to Make Money in Stocks* (CAN SLIM framework)
- Minervini, M. — *Trade Like a Stock Market Wizard* (VCP, SEPA methodology)
- Wyckoff, R.D. — Market cycle methodology (Accumulation/Markup/Distribution/Markdown)
- Weis, D. — *Trades About to Happen* (Weis Wave volume analysis)
- Rabiner, L.R. — *A Tutorial on Hidden Markov Models* (HMM methodology)
- Hassan, M.R. — *Forecasting Stock Market Values Using HMM* (HMM application)
- Nguyen et al. — *Lead-Lag Relationship VN30 Spot vs Futures* (ResearchGate)
- HOSE/HNX Regulations — Circuit breaker, T+2.5 settlement, FOL rules
- VinaCapital — *Understanding Vietnam's Foreign Ownership Limits*
- SSI iboard HAR log — `d:\portfolio\data\SSI_HARrequestLogs.txt` (15 endpoints confirmed)
- SSI EP-11 corporate-actions — Ex-dividend / bonus shares dates (bắt buộc cho adjusted_close)
- SSI EP-9 company-in-same-industry — Sector peer mapping (portfolio sector constraints)
- Kalman, R.E. — *A New Approach to Linear Filtering and Prediction Problems* (Kalman Filter)
- Kennedy, J. & Eberhart, R. — *Particle Swarm Optimization* (PSO parameter search)

---

> **Triết lý:** *"Thị trường là distributed system — price action là output log của institutional intent. Wyckoff đọc log, CAN SLIM chọn process chất lượng, MFPM tìm commit point tối ưu, ATC Router optimize execution. HMM xác định system state. Monte Carlo đo xác suất thành công trước khi deploy."*

---

# PHỤ LỤC C — TỰ PHẢN BIỆN: LỖ HỔNG VÀ RỦI RO HỆ THỐNG

> *"Hệ thống tốt nhất là hệ thống biết giới hạn của mình."*

## C.1 Lỗ Hổng Về Dữ Liệu

| Lỗ hổng | Mức độ | Phân tích |
|---|---|---|
| **SSI API không chính thức** | 🔴 Critical | Toàn bộ data layer phụ thuộc reverse-engineered API — không có SLA, có thể thay đổi cấu trúc bất cứ lúc nào. Cần maintain adapter layer |
| **Point-in-time EPS** | 🔴 Critical | CAN SLIM 'C': EPS Q1/2026 chỉ available sau tháng 5/2026. Backtest phải dùng `report_date + 45d` — không dùng ngày hiện tại |
| **Adjusted close accuracy** | 🟡 Important | SSI EP-11 corporate-actions có thể thiếu stock splits nhỏ. Cần cross-verify với EP-12 cap-and-dividend |
| **VN30F liquidity thấp** | 🟡 Important | Basis indicator dùng VN30F — nhưng HNX derivatives volume còn thấp, spread rộng → basis có thể bị distort bởi market maker tạo liquidity |
| **Market breadth EP-7 fields** | 🟡 Important | Tên field (`num_advancing`, `num_declining`) giả định — cần verify với HAR log thực tế |

## C.2 Lỗ Hổng Về Thuật Toán

| Lỗ hổng | Mức độ | Phân tích |
|---|---|---|
| **HMM overfitting** | 🔴 Critical | HMM 3-state fit trên toàn bộ lịch sử → state labels có thể không stable khi thêm dữ liệu mới (label switching problem). **Fix:** Re-fit monthly + pin states bằng emission mean constraints |
| **Kelly Criterion với ít trades** | 🔴 Critical | Kelly cần win_rate thống kê đủ lớn (n ≥ 30). Trong giai đoạn live trading đầu (< 30 trades), Kelly unreliable → **dùng fixed 5% per trade thay Kelly** |
| **Monte Carlo mu/sigma nguồn** | 🟡 Important | `mu` = historical return mean bị bias bởi bull market. Trong bear, mu âm → MC sẽ reject gần như tất cả signals. Cần regime-adjusted mu từ HMM |
| **VCP contraction threshold hardcoded** | 🟡 Important | `range_i / range_im1 < 0.70` — Minervini nguyên gốc không có con số cứng; phụ thuộc mã. Cần adaptive threshold hoặc % thay đổi 30–50% |
| **Hurst Exponent trên daily data** | 🟡 Important | R/S analysis chuẩn cần ít nhất 200–300 data points. `max_lag=100` với series ngắn → H estimate noisy. Cần min series length check |
| **MFPM Mode A + B không có position limit riêng** | 🟡 Important | Nếu Mode A và Mode B signal cùng 1 mã — có thể double-count position |
| **Kalman herding: threshold chưa định nghĩa** | 🟡 Important | `kalman_cross_variance < herding_threshold` — threshold này cần calibrate từ historical VN market data |

## C.3 Lỗ Hổng Về Thực Thi

| Lỗ hổng | Mức độ | Phân tích |
|---|---|---|
| **Không có order management thực** | 🔴 Critical | `execution.py` hiện tại là stub → orders chỉ ghi vào DuckDB, không gửi lên broker. Phase 5 cần SSI FastConnect API (có phí) hoặc sử dụng thủ công từ signal |
| **ATC manipulation detection** | 🟡 Important | Deviation > 2.5% → cancel ATC. Nhưng 2.5% không có cơ sở thống kê — cần calibrate từ historical ATC data |
| **Slippage model không phân tầng** | 🟡 Important | Slippage 0.1% ATC áp dụng đồng đều nhưng thực tế: mã midcap slippage cao hơn VN30; phiên thanh khoản thấp slippage cao hơn |
| **Device-id rotation strategy** | 🟡 Important | Khi bị block, rotate device-id — nhưng không có cơ chế detect "đang bị throttle" vs "request error thực sự" |

## C.4 Lỗ Hổng Về Giả Định Thị Trường

| Lỗ hổng | Mức độ | Phân tích |
|---|---|---|
| **Backtest: 2020–2025 là giai đoạn đặc biệt** | 🔴 Critical | VNI tăng từ 660 → 1,300 (2020–2022) rồi crash 50% rồi phục hồi. Win rate 55%+ trong backtest có thể do bull bias. **Fix:** Walk-forward validation với OOS periods |
| **"Institutional intent" không quantifiable** | 🟡 Important | Wyckoff + Order Flow assume institutional actors — nhưng VN retail >80% volume → institutional signal weak. Herding detection quan trọng hơn institutional tracker |
| **Nâng hạng FTSE 9/2026 là single point of failure** | 🟡 Important | Toàn bộ macro outlook (6–8 tỷ USD inflow) phụ thuộc vào 1 sự kiện. Cần scenario planning nếu bị delay (như đã delay 2024) |
| **SBV lãi suất** | 🟡 Important | SBV tăng lãi suất đột ngột (rare nhưng không phải zero) có thể invalidate toàn bộ GMO Ω trong 1 phiên — không có circuit breaker cho macro shock |
| **Không có Short mechanism** | 🟢 Nice-to-have | Hệ thống chỉ long-only + cash. RISK_OFF state = hold cash, không profit từ downtrend. VN30F short là option nhưng chưa trong scope |

## C.5 Lỗ Hổng Về Phương Pháp (Round 3)

| Lỗ hổng | Mức độ | Phân tích |
|---|---|---|
| **RS Rating 4-week too short** | 🔴 Critical | O'Neil RS dùng composite 3/6/9/12 tháng. 4-week return quá volatile → top picks thay đổi mỗi tuần, không ổn định để CAN SLIM Weekly filter hoạt động đúng |
| **OFI không được tích hợp vào MFPM score** | 🟡 Important | OFI từ EP-4 được tính nhưng chưa được cộng điểm trong Module 4.2. Nên thêm: OFI > +0.3 → +5 điểm xác nhận; OFI < -0.3 → -5 điểm cảnh báo |
| **Fibonacci swing_low không tự động** | 🟡 Important | `calculate_tp` nhận `swing_low` là parameter nhưng không có function nào trong proposal tự động detect swing_low. Cần thêm `detect_swing_low(df, lookback=20)` → `df['Low'].iloc[-lookback:-1].min()` |
| **Progressive Exit fraction mơ hồ** | 🟡 Important | Module 6: "Sell 40% of position" — nhưng sau tranche entry 50%+50%, "40% của position" không rõ là 40% tổng hay 40% của số còn lại. Cần chuẩn hóa: 40% của tổng số cổ phiếu đang giữ |
| **Không có circuit breaker cho gap-up opening** | 🟡 Important | Mode B breakout: nếu ATO gap > 3% so với pivot high → entry gap up thường không sustainable. Cần gating: `ato_gap_vs_pivot < 0.03` để tránh chase after open |
| **`build_universe` function không có fallback cho HNX** | 🟢 Nice-to-have | HNX có liquidity thấp hơn nhiều so với HOSE. `avg_vol_20d >= 500_000` có thể loại phần lớn HNX. Nên tách ngưỡng: HOSE ≥ 500K; HNX ≥ 100K để giữ diversity |
| **Dividend yield không trong CAN SLIM filter** | 🟢 Nice-to-have | Cổ phiếu trả cổ tức cao thường là mature companies — CAN SLIM thiên về growth. Nên thêm soft penalization: ROE > 25% nhưng payout ratio > 70% → -5 điểm CAN SLIM |

## C.6 Lỗ Hổng Cụ Thể Về Module 2.9 (Anti-Manipulation)

| Lỗ hổng | Mức độ | Phân tích |
|---|---|---|
| **Tên field OFI từ EP-4 chưa xác minh** | 🔴 Critical | `compute_ofi()` giả định các cột `bid_volume`, `ask_volume` nhưng HAR log chưa confirm chính xác field names. Cần test EP-4 response schema trước khi dùng production |
| **VQS formula weights tuỳ tiện** | 🟡 Important | Trọn bình quân (OFI + ΔOBV% + PD) / 3 chưa qua calibration. OFI có thể quantitative hơn ΔOBV% — nên thử weighted: `0.5×OFI + 0.3×ΔOBV% + 0.2×PD` sau khi backtest |
| **herding_threshold = 0.8 chưa có cơ sở thực nghiệm** | 🟡 Important | Ngưỡng Kalman herding p = 0.8 lấy từ lý thuyết nhưng VN market có thể cần ~0.85–0.90 vì retail herding cao hơn. Cần grid search to optimize |
| **second_mouse_gate tạo 1-day entry lag** | 🟡 Important | Chờ T+1 retest sẽ bỏ lỡ một số breakout thật sự. Trong backtest nên so sánh P&L Mode B có gate vs không có gate. Giả thuyết: giảm win count nhưng tăng win rate |
| **detect_insider_run() có false positive cao gần earnings** | 🟡 Important | Thuận lợi tiết lẽ cầu quý là có thể làm price run +5% và với volume cao hợp lệ. Cần add exception: nếu event_date là kỳ báo cáo lớn (dividend, BCTC quý) thì không flag insider run |
| **Không có ensemble vote cho anti-manipulation** | 🟡 Important | Hiện tại chỉ 1 trong 4 module bố hóa là có thể gây BLOCK. Nên test “ít nhất 2⁡3 flags” mới BLOCK để giảm false positive; WARN mớt flag đơn lẻe |

---

# PHỤ LỤC D — GIẢI PHÁP ĐÃ TRIỂN KHAI (Self-Audit Round 5)

> *Mỗi lỗ hổng trong C.1–C.6 đều có solution cụ thể được tích hợp vào module tương ứng.*

| # | Lỗ hổng (từ C.1–C.6) | Giải pháp đã implement | Module |
|---|---|---|---|
| D-01 | HMM label switching khi refit | `fit_hmm()` + state-pinning theo emission mean return (sort ascending → state 0=Bear, 2=Bull); `monthly_refit_hmm()` rolling 3-year window | 1.1 |
| D-02 | Kalman herding threshold hard-coded | `calibrate_herding_threshold(history, percentile=10)` — ngưỡng động từ lịch sử, fallback 0.0002 | 1.5 |
| D-03 | Hurst Exponent trên series ngắn | Guard `if len(series) < max_lag * 2: return 0.50`; loại tau=0 tránh log(0); fallback 0.50 = random walk neutral | 2.3 |
| D-04 | EP-4 OFI field names chưa xác minh | `_extract_vol()` + `_extract_levels()` với fallback list 6 variant field names; trả 0.0 nếu schema fail | 2.7 |
| D-05 | `detect_swing_low()` thiếu | Hàm mới: tìm pivot low (confirmed cả 2 phía) trong lookback=20; fallback = min() toàn window | 2.5 |
| D-06 | `build_universe` ngưỡng volume HOSE/HNX đồng nhất | Tiered: HNX ≥ 100K; HOSE ≥ 500K — giữ diversity mà không hy sinh chất lượng | 2.8 |
| D-07 | VCP threshold cứng 70%/75% cho mọi mã | Adaptive: `atr_ratio > 2%` → nới lỏng 80%/85%; low-vol mã giữ ngưỡng gốc 70%/75% | 3.2 |
| D-08 | MFPM double-count cùng ticker 2 mode | Guard trong pre-conditions: `assert existing_positions[ticker]['mode'] == trade_mode` | 4.1 |
| D-09 | Mode B chase gap-up ATO | Gate: `ato_gap_vs_pivot > 0.03` → REJECTED_GAP_CHASE (sáng sớm sau ATO) | 4.3 |
| D-10 | Monte Carlo mu bị bull-period bias | `get_regime_mu(hmm_state, returns)`: BULL→max(mean, +0.05%/d); BEAR→min(mean, -0.03%/d); SIDEWAYS→0 | 4.4 |
| D-11 | Kelly Criterion khi n < 30 trades | Bootstrap guard: `if trade_count < 30: kelly_f = 0.05` (fixed fraction giai đoạn đầu) | 4.5 |
| D-12 | Progressive exit "40% of remaining" mơ hồ | Chuẩn hóa: cả 2 lần bán đều tính theo **total_qty ban đầu** (40% + 40% + hold 20%); ví dụ số cụ thể | 6 |
| D-13 | Slippage flat 0.1% cho mọi mã | 3-tier: VN30 = 0.1%; midcap = 0.3%; smallcap = 0.7% — `VNBacktestConstraints` | 8 |
| D-14 | Backtest 2020–2025 bull-bias | `walk_forward_backtest()`: train 2Y → test 6M OOS, trượt liên tục; chuẩn: OOS win_rate ≥ IS × 0.85 | 8 |
| D-15 | `detect_insider_run()` false positive gần earnings | Guard: check `SCHEDULED_KEYWORDS` (Q1/Q2/AGM/BCTC...) → return False nếu match | 2.9.5 |
| D-16 | Anti-manipulation BLOCK từ 1 flag → false positive | Ensemble voting: BLOCK chỉ khi `len(block_votes) >= 2`; 1 flag → WARN + giảm vị thế 50% | 2.9.6 |

**Kết quả Round 5:** 16 giải pháp code được tích hợp trực tiếp vào các module. Proposal giờ có:
- **Không còn hard-coded thresholds không có cơ sở** → tất cả đều calibrate-able hoặc adaptive
- **Bootstrap path**: từ 0 → 30 trades → Kelly đủ data (D-11)
- **OOS validation**: walk-forward chống overfitting (D-14)
- **Fault tolerance**: OFI/order-book schema failure → neutral fallback (D-04)
- **Anti-manipulation**: ensemble 2/3 votes giảm false positive rate dự kiến ~40% (D-16)

---

## PHỤ LỤC E — TỔNG HỢP MERGE: v1.0 + Proposal v5

> *So sánh và kết hợp hai tài liệu đề xuất để tạo ra bản hoàn chỉnh nhất.*

### E.1 Delta Analysis: v1.0 vs Proposal v5

| # | Nội dung từ Proposal v5 | Đánh giá | Quyết định | Module |
|---|---|---|---|---|
| E-01 | **AMD Cycle** (Accumulation→Manipulation→Distribution) | ✅ Bổ sung quan trọng — đọc ý đồ tay to theo thời gian | **Tích hợp** làm Module 2.10.1 | 2.10 |
| E-02 | **VSA No Demand / No Supply Bar** (Tom Williams) | ✅ Bổ sung tốt — đọc từng phiên micro-structure | **Tích hợp** làm Module 2.10.2 | 2.10 |
| E-03 | **CVD Cumulative Volume Delta** (tick-level) | ✅ Vượt trội OFI về độ chính xác — phát hiện whale | **Tích hợp** làm Module 2.10.3 (Phase 3 tick) | 2.10 |
| E-04 | **Order Block** detection | ✅ Bổ sung vùng hỗ trợ/kháng cự tổ chức — chưa có trong v1.0 | **Tích hợp** làm Module 3.6 | 3.6 |
| E-05 | **Cup with Handle** (O'Neil CAN SLIM) | ✅ Classic O'Neil setup — tỷ lệ thắng cao tại pivot | **Tích hợp** làm Module 3.7 | 3.7 |
| E-06 | **SHAP Explainability** cho MFPM reasons | ✅ Tăng transparency, user trust, post-trade learning | **Tích hợp** làm Module 7.2 | 7.2 |
| E-07 | **Progressive Exposure 6.25%→12.5%→6.25%** | ✅ Bổ sung cho 50%+50% — phù hợp môi trường bất định | **Tích hợp** kết hợp: mode-dependent selection | 6 |
| E-08 | **Risk-Adjusted Momentum Weighting** portfolio | ✅ Phân bổ tốt hơn equal-weight — có cơ sở toán học | **Tích hợp** làm Module 8.1 | 8.1 |
| E-09 | **PhoBERT sentiment score** trong advisory | ✅ Đã có trong v1.0 scaffold; v5 thêm field `phobert_sentiment` | **Tích hợp** thêm vào Signal Schema 9 | 9 |
| E-10 | **XGBoost 96.67% accuracy** claim | ❌ Đã bác bỏ trong Round 1 audit — single model, overfitting, không có OOS | **Loại** — giữ hệ thống ensemble không phụ thuộc 1 model | — |
| E-11 | **Top 15 portfolio cụ thể** (VCB 12%, FPT 10%...) | ⚠️ Data point-in-time (Q1/2026) — không phù hợp framework | **Loại** — `risk_adjusted_weights()` tự tính trọng số từ real RS+sigma | 8.1 |
| E-12 | **gRPC FastConnect** cho tick data | ✅ Phase 3 infrastructure dependency — cần cho CVD full | **Backlog #14** trong PHẦN VIII | VIII |

### E.2 Các Thay Đổi Nhờ Merge

| Thành phần | Trước merge (v1.0 only) | Sau merge (v1.0 + v5) |
|---|---|---|
| Modules phân tích | 2.1–2.9 (9 modules) | 2.1–2.10 (10 modules, thêm AMD+VSA+CVD) |
| Patterns nhận diện | 5 patterns (Spring, VCP, FVG, Weis, RSI Div) | 7 patterns (+Order Block, +Cup with Handle) |
| MFPM scoring factors | ~15 factors, max ~143 ref | ~22 factors, STRONG_BUY ≥ 70 vẫn giữ nguyên |
| Signal Schema fields | 16 fields | 22 fields (+AMD phase, VSA, CVD, OB, SHAP top5) |
| Portfolio allocation | Equal weight / Kelly per trade | Risk-Adjusted Momentum Weighting |
| Position building | 50%+50% only | 50%+50% (STRONG_BUY+MARKUP) hoặc 6.25%→25% (BUY+ACCUMULATION) |
| NLP Advisory | Text generation only | Text + SHAP top-5 reasoning explanations |
| Architecture diagram | 8 core modules | 10 core modules (AMD+VSA+CVD in Advanced Analytics) |

### E.3 Tự Phản Biện — Lỗ Hổng Sau Merge

| Lỗ hổng | Mức độ | Ghi chú |
|---|---|---|
| CVD tick-level phụ thuộc SSI FastConnect (có phí) | 🔴 Critical | Dùng proxy OFI trong Phase 1–2; CVD thật là Phase 3+ |
| `classify_amd_phase()` với lookback=60 có thể lag | 🟡 Important | Trong uptrend mạnh, phase có thể báo MARKUP muộn 5–10 phiên |
| Order Block "mitigated" check chưa implement | 🟡 Important | OB sau khi giá đã vào và ra thường không còn hiệu lực — cần `ob_mitigated` flag |
| Cup with Handle `cup_max_bars=120` có thể miss large cups | 🟡 Important | VCB, VHM hay có Cup 6–9 tháng (>120 phiên) — cần `cup_max_bars` configurable |
| SHAP explanation không phải SHAP thật (chỉ sort by magnitude) | 🟡 Important | SHAP thật cần `shap` library với XGBoost model — hiện tại là heuristic approximation |

---
*End of TradingOS Alpha Proposal v1.0*

---

## PHỤ LỤC F — ĐÁNH GIÁ VÀ ĐIỀU CHỈNH THEO BOARD EVALUATION (2026-03-30)

> *Phân tích, chấp thuận, hoặc bác bỏ các kiến nghị từ “Final SRS Evaluation & Strategic Insights”*

### F.1 Bảng Đánh Giá Từng Hạng Mục

| # | Claim | Quyết định | Lý do | Triển khai |
|---|---|---|---|---|
| F-01 | MTL thay thế MP trên HOSE (KRX) | ✅ **CHẤP THUẬN** | Thực tế kỹ thuật đúng — KRX rollout. Proposal đã có MTL reference (line 46, 231). | Bổ sung logic partial fill vào `smart_atc_router()` — Module 2.7 |
| F-02 | KRX ATO/ATC priority | ✅ **CHẤP THUẬN (có hiệu chỉnh)** | ATO/ATC chạy trong auction phase riêng, không cạnh tranh time-priority với LO continuous. Claim ban đầu pờ hướng dẫn. | Thêm note rõ ràng trong ATC Router code — Module 2.7 |
| F-03 | PCA cho cổ phiếu bị hạn chế (KRX) | ✅ **CHẤP THUẬN** | Đúng — KRX thêm PCA mechanism cho mã cảnh báo. Cần loại khỏi auto-signal. | Thêm Step 5b vào `build_universe()` — Module 2.8 |
| F-04 | NPF settlement failure (Thông tư 08/2026) | ✅ **CHẤP THUẬN (có điều kiện)** | Cơ chế NPF là thực và liên quan. Số hiệu Thông tư chưa kiểm chứng được — ghi chú *pending verification*. | Thêm `check_npf_flag()` vào Module 2.6; mark pending |
| F-05 | Lưu trữ audit ≥ 24 tháng (Nghị định 53/2022) | ✅ **CHẤP THUẬN** | SRS đã có cold archive 2 năm. Thêm cite rõ ràng. | Cập nhật SRS NFR 9.2 |
| F-06 | XBRL/IDS filings cho NLP | ✅ **CHẤP THUẬN (Phase 3+)** | Nguồn dữ liệu có cấu trúc chính thức hơn SSI EP-10. Phụ thuộc SSC API availability. | Thêm Module 7.3 + Backlog #15 |
| F-07 | Kiến trúc Rust + io_uring/DPDK | ✅ **CHẤP THUẬN (điều chỉnh scope)** | Áp dụng cho **data ingestion daemon** (`data/collector_daemon/` — Rust binary), tách biệt khỏi Python core analytics. Rust + io_uring xử lý async network I/O: SSI poll → DuckDB write. Python app chỉ đọc từ DuckDB đã populated. | Thêm Module 0 spec + `data/collector_daemon/` crate |
| F-08 | Target 3.9 ms / < 100 ms data refresh | ✅ **CHẤP THUẬN (điều chỉnh scope)** | 3.9 ms = P50 network hop SSI server → Rust daemon; < 100 ms = end-to-end SSI response → DuckDB write. Áp dụng cho data ingestion layer — analytics SLA (2–5s P50) không thay đổi. | Thêm NFR rows vào SRS 9.5.1 + 6.5 |
| F-09 | T+0 8–10× capital turnover backtest | ❌ **BÁC Bỏ** | Swing trading system. T+0 intraday explicitly out-of-scope Phase 1–4. | Out-of-scope |
| F-10 | FIX 4.4 API standard | ⚠️ **Phase 5+ only** | Broker OMS order routing. TradingOS chỉ đưa ra khúyến nghị, không đặt lệnh. | Backlog Phase 5+ |

### F.2 Tóm Tắt Thay Đổi Vào Proposal

| File | Section | Thay đổi |
|---|---|---|
| Proposal | Module 2.6 FOL | Thêm `check_npf_flag()` function + implementation note |
| Proposal | Module 2.7 ATC Router | Thêm MTL partial fill logic + KRX priority clarification + fat-finger protection |
| Proposal | Module 2.8 Universe | Thêm Step 5b: PCA exclusion (`fetch_pca_restricted_tickers()`) |
| Proposal | Module 7 NLP | Thêm Section 7.3: XBRL data source (Phase 3+) + Backlog #15 |
| Proposal | Module 0 (mới) | Data Ingestion Daemon: Rust + io_uring, pipeline diagram, performance targets, impl sketch |
| SRS | Section 7.3 | Thêm 3 hàng: MTL partial fill simulation, PCA exclusion, KRX auction priority |
| SRS | Section 9.1 | Thêm KRX compliance NFR |
| SRS | Section 9.2 | Đổi tên thành “Security & Compliance”; thêm audit retention + NPF flag rows |
| SRS | Section 9.5 (mới) | Bảng chính thức: accepted/rejected items |
| SRS | Section 9.5.1 | Thêm 3 hàng: Rust daemon, ≤ 3.9 ms hop, < 100 ms refresh |
| SRS | Section 6.5 | Thêm 2 data ingestion SLA rows |
| SRS | Week 1 table | Thêm `data/collector_daemon/` scaffold task |
| SRS | File structure | Update `atc_router.py` comment → MTL/KRX mention |

### F.3 Backlog mới sau đánh giá

| # | Hạng mục | Phase |
|---|---|---|
| Backlog #15 | XBRL parser + SSC IDS integration cho NLP | Phase 3+ |
| Backlog #16 | `fetch_pca_restricted_tickers()` SSI EP-2/exchange bulletin | Week 3/P1 |
| Backlog #17 | Broker FIX 4.4 integration (nếu có order routing) | Phase 5+ |
| Backlog #18 | Rust data ingestion daemon (`data/collector_daemon/`) — io_uring + DuckDB WAL | Phase 2 |
