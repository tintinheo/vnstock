# User Guide — Captain Seventh Quant Terminal

**Document ID:** QT-UG-001  
**Version:** 1.0  
**Date:** 2026-03-14  
**Audience:** TheCaptain7th (primary user) and future team members  

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Daily Workflow (Morning Ritual)](#2-daily-workflow-morning-ritual)
3. [Tab 1 — 📊 Danh Mục (Portfolio Dashboard)](#3-tab-1----danh-mục-portfolio-dashboard)
4. [Tab 2 — 🔍 Phân Tích Cổ Phiếu (Stock Analysis)](#4-tab-2----phân-tích-cổ-phiếu-stock-analysis)
5. [Tab 3 — 🌐 Thị Trường (Market Overview)](#5-tab-3----thị-trường-market-overview)
6. [Tab 4 — 📋 Trade Log](#6-tab-4----trade-log)
7. [Tab 5 — ⚡ Rủi Ro (Risk Dashboard)](#7-tab-5----rủi-ro-risk-dashboard)
8. [Sidebar Reference](#8-sidebar-reference)
9. [How to Read the Signals](#9-how-to-read-the-signals)
10. [How to Place an Order (SSI iBoard)](#10-how-to-place-an-order-ssi-iboard)
11. [Troubleshooting](#11-troubleshooting)
12. [Keyboard Shortcuts & Tips](#12-keyboard-shortcuts--tips)

---

## 1. Getting Started

### 1.1 Installation

```bash
# Open terminal in the quant_terminal directory
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt
streamlit run app.py
```

Your browser opens automatically at `http://localhost:8501`.

### 1.2 Loading Your Portfolio

The app needs your SSI iBoard portfolio export to do anything useful.

**Export from SSI iBoard:**
1. Log in at [iboard.ssi.com.vn](https://iboard.ssi.com.vn) or the SSI iBoard mobile app
2. Navigate to **Tài sản** → **Danh mục chứng khoán**
3. Click **Export** → **Excel (.xlsx)**
4. Save the file

**Load into the app (two options):**

| Option | How | Best for |
|--------|-----|---------|
| Upload via sidebar | Click "Upload file SSI iBoard (.xlsx)" in the left sidebar | One-time manual load |
| Auto-detect folder | Place file in `~/Documents/quant_terminal/portfolio/` | Daily routine |

Once loaded, the app automatically:
- Parses all positions (symbol, quantity, cost price, market value)
- Detects T+2 tradeable quantities
- Fetches live prices from SSI iBoard
- Computes P&L, weights, and risk labels

---

## 2. Daily Workflow (Morning Ritual)

> **Target time: 8:45–9:10 AM (before HOSE opens at 09:15)**

### Step 1 — Load latest portfolio (2 min)
1. Open the app (`streamlit run app.py`)
2. Upload today's SSI iBoard export **or** ensure the file is in the portfolio folder
3. Click **Load** in the sidebar if using the folder option

### Step 2 — Check Signal Digest (2 min)
→ **Tab 1 (Danh Mục)** → scroll to **Signal Digest** table

Read each row:
- **Score** — composite signal from −100 to +100
  - > +30: bullish, consider adding
  - −10 to +10: neutral, hold
  - < −30: bearish, review exit
- **Hành động** — blended recommendation (signal + your P&L position)
- **Top Pick / Watch** — highlighted at the bottom

> ⚠️ **Rule #1:** Never trade against the signal without a documented macro reason.

### Step 3 — Review Risk Dashboard (3 min)
→ **Tab 5 (⚡ Rủi Ro)**

- Is **Portfolio VaR 1D** within acceptable range? (target: < −1.5%)
- Any position **VaR < −3%**? → That's the first candidate to reduce
- Is **HHI > 40**? → Portfolio over-concentrated, diversify
- Does the **Kelly table** show ⬇ Giảm for any large position? → Act on it

### Step 4 — Check Market Context (2 min)
→ **Tab 3 (🌐 Thị Trường)**

- VNINDEX direction — trending up, down, or sideways?
- Upcoming macro events in the calendar? (FOMC, earnings dates)
- Your alpha vs index — are you outperforming?

### Step 5 — Enable Auto-Refresh
→ Sidebar → **⟳ Tự động cập nhật** → Toggle ON → set to 60s

Now the app will pull live prices from SSI every 60 seconds during the session.

### Step 6 — Plan your trades (5 min, if applicable)
→ **Tab 2 (🔍 Phân Tích)** → select symbol from sidebar

Run scenario analysis:
1. Adjust Bull/Base/Bear probability sliders to match your macro view
2. Read the **primary recommendation banner** (GIỮ / QUAN SÁT / CHỐT LỜI / CẮT LỖ)
3. Review the 3 scenario cards for P&L estimates
4. Follow the **order plan** — use the LO Builder to generate step-by-step instructions

### Step 7 — Log trades after execution (2 min)
→ **Tab 4 (📋 Trade Log)** → "Thêm giao dịch thủ công"

Always log immediately after placing an order. Never trade without logging.

### After Close — Snapshot (1 min)
→ **Tab 1** → click **"↓ Lưu snapshot danh mục"**

This saves today's portfolio state for performance attribution and future VaR calculation.

---

## 3. Tab 1 — 📊 Danh Mục (Portfolio Dashboard)

### KPI Row (top 5 metrics)

| Metric | What it means |
|--------|--------------|
| Tổng giá trị TT | Total current market value of all positions |
| Lãi/Lỗ thuần | Unrealised P&L in VND; green = profit |
| Số mã | Number of distinct stocks held |
| Đang lãi / lỗ | Count of positions currently in profit / loss |
| Mã GD được (T+2) | Positions that have completed T+2 settlement and can be sold today |

### Portfolio Table

Color-coded by P&L:
- 🟢 Green = positive P&L
- 🔴 Red = negative P&L

**Rủi ro column:**

| Label | Meaning | Action |
|-------|---------|--------|
| Thấp | P&L positive, weight normal | No action needed |
| Thấp — chốt lời | P&L > 5% with large weight | Consider taking profit |
| Trung bình | Slight loss, normal weight | Monitor |
| Cao | Loss > 1.5% with large weight | Review exit plan |
| Rất cao | Loss > 3% with large weight | Immediate attention |
| Nhỏ — xem xét thanh lý | Weight < 2% | Consider closing — too small to manage |

Click a symbol button (🟢 / 🔴 HPG, etc.) to jump directly to that stock's analysis in Tab 2.

### P&L Attribution Chart
Horizontal bar chart sorted by P&L contribution. The leftmost bar (most red) is your biggest drag. Review if it has a bad signal score.

### Heat Map
- Large green cells = big, profitable positions → working well
- Large red cells = big, losing positions → **priority review**
- Small grey cells = tiny positions → consider closing to simplify

### Signal Digest
See [Section 9 — How to Read the Signals](#9-how-to-read-the-signals) for full interpretation guide.

**Top Pick:** Highest signal score in your portfolio → potential add candidate  
**Watch:** Lowest signal score → exit or reduce candidate

---

## 4. Tab 2 — 🔍 Phân Tích Cổ Phiếu (Stock Analysis)

### How to Select a Stock
- Type a ticker in the sidebar text input (e.g. `HPG`)
- Or click a symbol button in Tab 1
- Or use the "Chọn từ danh mục" dropdown in the sidebar

### Quote Header
Top row shows live price, % change, your P&L on this position, total value held, and P/E ratio.

### Technical Signals Panel (left column)
| Component | How to read |
|-----------|------------|
| Điểm tổng hợp | Composite score. +50 and above = clear buy signal. −50 and below = strong sell. |
| Individual signals | Each indicator votes independently. Most arrows pointing up = bullish consensus |
| Beta vs VNINDEX | Beta > 1 = amplified market moves (riskier). Beta < 1 = defensive |
| RSI (14) | > 70 = overbought (sell). < 30 = oversold (buy). 50 = neutral |
| MACD Hist | Positive and growing = momentum building. Negative and falling = momentum weakening |

### Price Chart (right column)
- **Candlesticks** — green = up day, red = down day
- **EMA-20** (yellow), **EMA-50** (blue), **EMA-200** (purple): price above all three = strong uptrend
- **Red dashed line** = your cost price (only shown if you hold the position)
- **Volume bars** (bottom of candle chart): high volume on up days = buying pressure ✅; high volume on down days = selling pressure ⚠️
- **RSI panel**: horizontal lines at 70 (overbought) and 30 (oversold)
- **MACD Hist panel**: green bars above zero = bullish momentum

**Range selector:** Zoom in/out by scrolling on the chart; drag to pan.

### Scenario Analysis

**Use this before every trade. No trade without a scenario plan.**

1. **Set probabilities** (Bull/Base/Bear sliders must sum to ~100%)
   - Bull: Your view if the market/sector recovers
   - Base: Most likely outcome based on current trends
   - Bear: Downside if macro deteriorates

2. **Analyst target** (optional): Enter the analyst consensus price target if available. Leave at 0 if not.

3. **Read the recommendation banner:**
   - 🟢 **GIỮ** — EV positive, signal healthy, R:R ≥ 1.5 → Hold or add
   - 🟡 **QUAN SÁT** — Wait; no clear edge yet
   - 🟠 **CHỐT LỜI 50%** — Signal weakening but still in profit → Take partial profit
   - 🔴 **CẮT LỖ** — Price below cost × 0.95 → Follow the plan; exit

4. **Three scenario cards** — each shows target price, P&L estimate for your full position

5. **Order Plan** — 4 pre-generated orders:
   - Lệnh 1: Chốt 50% at current price (if applicable)
   - Lệnh 2: Chốt thêm at resistance
   - Lệnh 3: Trailing stop for remaining position
   - Stop Loss: Mandatory — **this is non-negotiable**

### Support & Resistance
Green levels = support (price tends to bounce here)  
Red levels = resistance (price tends to stall here)

Distance shown as % from current price.

### LO Order Builder
Expand to generate a full step-by-step order instruction:
1. Select Mua/Bán
2. Enter quantity and price
3. Click "Tạo hướng dẫn lệnh LO"
4. Follow the numbered steps on SSI iBoard exactly

---

## 5. Tab 3 — 🌐 Thị Trường (Market Overview)

### Market Indices
- **VNINDEX** — broad market. The primary benchmark.
- **VN30** — top 30 blue chips. Liquidity proxy.
- **Phiên GD** — current trading session (Pre-ATO / ATO / Continuous / ATC / Closed)

### VNINDEX Chart
120-session history with EMA-20 and EMA-50. Good for answering:
- Is the market in an uptrend (price > EMA-20 > EMA-50)? If yes: bias long.
- Is the market in a downtrend? If yes: reduce all positions, tighter stops.

### Portfolio vs VNINDEX
**Alpha** = your P&L % − VN-Index 120-session return

| Alpha | Interpretation |
|-------|---------------|
| Positive | You are outperforming — strategy is working |
| Zero | Market-rate return — no edge being added |
| Negative | Underperforming — strategy needs review |

> **Target:** Alpha ≥ +10% annualised for BO-02.

### Macro Event Calendar
Key upcoming dates that could move your positions. Check this every morning.

---

## 6. Tab 4 — 📋 Trade Log

### Recording a Trade
Fill in all 5 fields and click **"Ghi nhận giao dịch"**:

| Field | Example |
|-------|---------|
| Ngày GD | 14/03/2026 |
| Mã CK | HPG |
| Mua/Bán | Mua |
| KL | 1000 |
| Giá | 26650 |

> ⚠️ Enter the **actual execution price** from your SSI confirmation, not the order price.

### Trade Log Table
Sorted newest-first. Shows all transactions with value and timestamp.

Summary metrics at the bottom: total bought, total sold, total trade count.

### Performance Stats
Requires at least 2 snapshots (taken by clicking **"↓ Lưu snapshot danh mục"** on different days).

Shows total return between earliest and latest snapshot.

**Build the habit:** Save a snapshot every trading day at close. After 30 days you have a meaningful performance curve.

---

## 7. Tab 5 — ⚡ Rủi Ro (Risk Dashboard)

### Section A — VaR Table

**What is VaR?**  
Value-at-Risk (95%, 1 day) = the maximum you'd expect to lose on a given day with 95% confidence, based on historical behaviour of that stock.

Example: VaR = −2.3% means on a bad day (1 in 20 days), you'd expect to lose at least 2.3% of that position.

**CVaR** = average loss on those rare bad days. Always worse than VaR. The more realistic number for tail risk.

**How to use it:**
1. Sort by **VaR 1D (%)** ascending — the worst VaR is your biggest risk
2. Positions with VaR < −3% and large weight → immediate review
3. Portfolio VaR > −2% → good; < −3% → consider reducing overall exposure

### Section B — Correlation Matrix

Colours:
- **Deep blue** (−1.0) = inversely correlated (good for diversification)
- **White** (0.0) = no correlation (independent)
- **Deep red** (+1.0) = moves together (no diversification benefit)

**How to use it:**  
If all your positions are deep red (corr > 0.7), then when one falls they all fall. You don't have a portfolio — you have one bet with multiple names.

Target: average off-diagonal correlation < 0.4 for a well-diversified portfolio.

### Section C — Kelly Criterion

**Rule of thumb:** Use **½ Kelly** (the "rec" column) as your target position size.

Example row:
```
Mã: HPG | Win Rate: 52% | Avg Win: 1.8% | Avg Loss: 1.4% | B: 1.28
Full Kelly: 18.4% | ½ Kelly: 9.2% | % Hiện tại: 12.5% | Điều chỉnh: ⬇ Giảm
```

This means: based on HPG's return history, the optimal position is ~9.2% of your portfolio. You currently hold 12.5% — the system recommends reducing.

**Why not Full Kelly?** Full Kelly maximises long-term geometric return but causes extreme volatility and drawdowns. Half-Kelly sacrifices ~25% of the benefit but halves the variance. It is the professional standard.

---

## 8. Sidebar Reference

| Control | Purpose |
|---------|---------|
| Upload file / Select file | Load SSI iBoard Excel portfolio |
| Load button | Trigger parse + live price fetch |
| Refresh giá | Manual one-shot price refresh |
| ⟳ Toggle ON/OFF | Enable/disable auto-refresh loop |
| Chu kỳ selector | Refresh interval: 30 / 60 / 120 / 300 seconds |
| Progress bar | Counts down to next auto-refresh |
| Nhập mã CK | Type any ticker to load in Tab 2 |
| Chọn từ danh mục | Pick from your current portfolio |
| Phiên hiện tại | Shows current trading session (ATO/Continuous/ATC/Closed) |
| Giờ HCM | Current Ho Chi Minh City time |

---

## 9. How to Read the Signals

### Composite Score (−100 to +100)

| Range | Label | Meaning | Example Action |
|-------|-------|---------|----------------|
| +60 to +100 | Mua mạnh | Strong buy consensus (3+ indicators aligned) | Consider adding if R:R > 2× |
| +20 to +60 | Tích cực | Bullish lean | Hold; watch for entry on pullback |
| −20 to +20 | Trung tính | No clear signal | Hold; no new position |
| −20 to −60 | Tiêu cực | Bearish lean | Reduce; tighten stop |
| −60 to −100 | Bán mạnh | Strong sell (3+ indicators aligned) | Exit or cut loss immediately |

### Individual Indicator Quick Reference

**RSI (Relative Strength Index)**
- > 70: Overbought — price has run too far, expect pullback or consolidation
- 30–70: Normal range — no extreme
- < 30: Oversold — price has fallen sharply, potential bounce

**MACD Histogram**
- Positive AND increasing: Momentum building upward — bullish
- Positive AND decreasing: Momentum fading — watch carefully
- Negative AND decreasing (more negative): Selling pressure — bearish
- Negative AND increasing (less negative): Potential reversal forming

**Bollinger Bands position**
- Price > 95% of band width: Near upper band — overbought, potential reversal
- Price < 5% of band width: Near lower band — oversold, potential bounce

**EMA Trend**
- Price > EMA-20 > EMA-50: Clear uptrend — ride the trend
- Price < EMA-20 < EMA-50: Clear downtrend — avoid longs
- Mixed (price > EMA-20 but < EMA-50): Transitioning — wait for confirmation

**Volume Ratio**
- Vol > 1.5× 20-day average: Unusual interest — confirms the direction of the candle
- Vol < 0.5× average: Low conviction — don't trust the direction of that candle

---

## 10. How to Place an Order (SSI iBoard)

### Using the LO Builder

1. Go to **Tab 2 → Phân Tích** → select your symbol
2. Scroll to **"Bộ xây dựng lệnh LO chi tiết"** → expand it
3. Fill in: Side (Mua/Bán), Quantity (KL), Price (Giá đặt)
4. Click **"Tạo hướng dẫn lệnh LO"**
5. Follow the numbered steps exactly on SSI iBoard

### Manual Steps on SSI iBoard

1. Log in at [iboard.ssi.com.vn](https://iboard.ssi.com.vn)
2. Click **Lệnh** in the top navigation
3. Select your account
4. Fill in:
   - **Mã CK**: stock ticker (e.g. HPG)
   - **Bên**: Mua / Bán
   - **Khối lượng**: number of shares (must be multiples of 100 on HOSE)
   - **Giá**: your limit price
   - **Loại lệnh**: LO (Limit Order)
5. Confirm pre-trade checklist:
   - [ ] Is this price within ±7% of reference price? (HOSE band)
   - [ ] Do I have sufficient T+2-settled shares (for sell)?
   - [ ] Is this aligned with my scenario plan?
6. Click **Đặt lệnh** → confirm PIN

### Order Types Quick Reference

| Type | Vietnamese | When to use |
|------|-----------|-------------|
| LO | Lệnh giới hạn | Standard — you choose the price. Use for all planned trades |
| ATO | Mở cửa | Fills at opening price. Use only if you must get in at open |
| ATC | Đóng cửa | Fills at closing price. Avoid unless rebalancing |
| MP | Thị trường | Fills at best available price. ⚠️ Use only for urgent exits |

> **Rule:** Always use **LO**. Never use MP unless you are emergency-exiting a stop loss and the LO isn't filling.

---

## 11. Troubleshooting

### App won't start

```
Error: No module named 'pandas_ta'
```
**Fix:** `pip install pandas-ta`

```
Error: No module named 'vnstock'
```
**Fix:** `pip install vnstock`

---

### Prices not updating

**Symptom:** All prices show 0 or are hours old  

**Check:**
1. Is auto-refresh ON? (sidebar toggle)
2. Click **Refresh giá** manually
3. Check internet connection
4. Run: `python -c "from modules.ssi_fetcher import check_connectivity; print(check_connectivity())"`

If `"ok": False` → SSI iBoard is unreachable. The app will automatically fall back to vnstock (VCI source). Prices may be 15-minute delayed.

---

### Portfolio shows zero P&L

**Symptom:** Lãi/Lỗ shows 0 for all positions  

**Likely cause:** SSI Excel format changed, or cost column not found.

**Fix:**
1. Open the Excel file manually
2. Look for a column containing "Giá trị vốn" or "Cost Value"
3. If column names have changed, report to maintainer — `modules/portfolio.py` `parse_ssi_excel()` needs updating

---

### Cache error / JSON decode error

```
JSONDecodeError: Expecting value
```
**Fix:** Clear cache:
```powershell
Remove-Item -Recurse -Force "$HOME\Documents\quant_terminal\.cache\*"
```

---

### Smoke tests failing

```bash
$env:PYTHONIOENCODING="utf-8"
python test_smoke.py
```

All 10 tests should pass. If any fail:
- Test [02–06, 09]: Data issue → check SSI connectivity
- Test [10]: SSI quote API → check `ssi_fetcher.check_connectivity()`
- Test [01]: Import error → check `requirements.txt` installations

---

### Chart not rendering / blank

**Symptom:** Plotly chart shows blank  
**Fix:** Reload the browser tab (F5). Streamlit chart state sometimes becomes stale on long sessions.

---

## 12. Keyboard Shortcuts & Tips

| Action | Shortcut / Tip |
|--------|---------------|
| Reload app | `R` key when Streamlit is focused |
| Clear cache (Streamlit) | Top-right menu → "Clear cache" |
| Full screen chart | Click the expand icon (⛶) top-right of any Plotly chart |
| Download chart as PNG | Hover chart → camera icon |
| Stop auto-refresh | Toggle OFF in sidebar — useful when researching to prevent page jumping |
| Zoom chart | Scroll mouse wheel over chart |
| Reset chart zoom | Double-click on chart |

### Pro Tips

> **Tip 1:** Set refresh interval to 300s when market is closed. Switch to 30s in the last 15 minutes before close (13:15–14:45 HCM) when ATC auctions matter.

> **Tip 2:** Save a snapshot BEFORE making changes to your portfolio (pre-trade baseline) and AFTER (post-trade actual). This gives clean attribution.

> **Tip 3:** The Signal Digest works best when run at 8:45 AM (before open) and at 14:00 (before ATC). These are the two highest-information moments in the VN trading day.

> **Tip 4:** If the heat map shows one very large green cell, that position is dominating your portfolio. Use the Kelly table to verify whether this is justified by the stock's historical win rate.

> **Tip 5:** Never act on a signal without checking the VNINDEX trend first (Tab 3). A strong buy signal on a stock in a falling market has much lower probability of success.

---

*User Guide prepared under BABOK v3 User Documentation standards.*  
*Last updated: 2026-03-14 · Version 1.0*
