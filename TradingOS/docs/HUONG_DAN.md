# 📖 Hướng Dẫn Sử Dụng TradingOS Alpha
## Nền tảng phân tích cổ phiếu thị trường Việt Nam

> **Lưu ý quan trọng:** TradingOS là công cụ hỗ trợ ra quyết định đầu tư. Hệ thống **không** tự động đặt lệnh. Mọi quyết định mua/bán đều do nhà đầu tư tự chịu trách nhiệm.

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Giao diện và điều hướng](#2-giao-diện-và-điều-hướng)
3. [Morning Briefing](#3-morning-briefing)
4. [ATC Alert](#4-atc-alert)
5. [Profiler — Phân tích cổ phiếu đơn](#5-profiler)
6. [Scanner — Quét thị trường](#6-scanner)
7. [Dòng tiền (Money Flow)](#7-dòng-tiền)
8. [Backtest — Kiểm thử chiến lược](#8-backtest)
9. [Portfolio & Hiệu suất](#9-portfolio--hiệu-suất)
10. [Audit Log](#10-audit-log)
11. [Các chỉ số kỹ thuật](#11-các-chỉ-số-kỹ-thuật)
12. [Thuật toán và Logic khuyến nghị](#12-thuật-toán-và-logic-khuyến-nghị)
13. [Quản lý rủi ro và vị thế](#13-quản-lý-rủi-ro-và-vị-thế)
14. [Quy tắc T+2.5 và ATC](#14-quy-tắc-t25-và-atc)
15. [Câu hỏi thường gặp](#15-câu-hỏi-thường-gặp)

---

## 1. Tổng quan hệ thống

TradingOS Alpha là nền tảng phân tích đầu tư chứng khoán Việt Nam tích hợp:

| Thành phần | Mô tả |
|---|---|
| **Profiler** | Phân tích toàn diện một mã cổ phiếu: kỹ thuật + cơ bản + macro + dòng tiền |
| **Scanner** | Quét hàng trăm mã theo bộ lọc tùy chọn |
| **Money Flow** | Theo dõi dòng tiền cá voi, CVD, dòng tiền ngành |
| **Backtest** | Kiểm tra hiệu quả chiến lược trên dữ liệu lịch sử |
| **Portfolio** | Quản lý danh mục, vị thế, P&L thời gian thực |
| **Morning Briefing** | Tóm tắt thị trường đầu ngày tự động |
| **ATC Alert** | Cảnh báo vị thế cần thoát tại phiên ATC (14:43–14:45) |

### Kiến trúc tổng thể

```
Nguồn dữ liệu (DNSE / SSI / FiinQuant)
         │
         ▼
  Data Fetcher & Cache (5 phút TTL)
         │
    ┌────┴────┐
    │         │
Indicators  Macro Engine
(SMA/EMA/   (USD/VND,
RSI/ATR/    Bond yield,
OBV/Hurst)  SBV OMO)
    │         │
    └────┬────┘
         │
  Profiler Service
  ┌──────┴──────────────────────────────────┐
  │ AMF · AMD · HMM · MFPM · SMS · T25     │
  │ BiLSTM · Multi-Horizon · Patterns      │
  │ Macro Gate · Fundamental · Earnings    │
  └──────────────────┬──────────────────────┘
                     │
              Signal + Action
         (STRONG_BUY / BUY / WATCH /
          NO_ACTION / EXIT / FORCED_EXIT)
```

---

## 2. Giao diện và điều hướng

### Sidebar trái

| Mục | Chức năng |
|---|---|
| Logo + Version | Hiển thị phiên bản hiện tại (v1.2 Alpha) |
| Navigation radio | Chuyển đổi giữa các trang |
| 🔍 Tra cứu nhanh | Nhập mã cổ phiếu (VCB, FPT...) → chuyển thẳng đến Profiler |
| ⚠️ Disclaimer | Nhắc nhở đây là công cụ tư vấn, không đặt lệnh tự động |

### Cấu trúc trang

```
🌅 Morning Briefing     — Tóm tắt thị trường mỗi sáng
⚡ ATC Alert            — Vị thế đến hạn T+2.5 (có badge đỏ nếu có)
📂 Danh mục & Hiệu suất — Portfolio overview + equity curve
── HÀNH ĐỘNG ──
🔍 Profiler             — Phân tích chi tiết một mã
📡 Scanner              — Quét nhiều mã theo bộ lọc
── PHÂN TÍCH ──
🐳 Dòng tiền            — Whale flow, CVD, sector heatmap
📊 Backtest             — Simulation lịch sử
── HỆ THỐNG ──
🗂 Audit                — Nhật ký thao tác
⚙️ Cài đặt              — API key, thông số cá nhân hoá
📖 Hướng dẫn           — Tài liệu này
```

---

## 3. Morning Briefing

**Mở ra mỗi sáng trước khi thị trường mở cửa (trước 9:15).**

### Nội dung hiển thị

| Mục | Ý nghĩa |
|---|---|
| **Macro Snapshot** | USD/VND, VN 10y bond yield, SBV OMO net, MacroRegime |
| **VN-Index Overview** | Giá đóng cửa hôm qua, % thay đổi, breadth (A/D ratio) |
| **Top Gainers/Losers** | 5 mã tăng mạnh nhất / giảm mạnh nhất trong universe |
| **Sector Performance** | Heatmap 18 ngành so với phiên trước |
| **Lịch sự kiện** | BCTC, cổ tức, ngày chốt quyền trong tuần |
| **Portfolio Alerts** | Vị thế đang giữ: stop-loss đang bị đe doạ, TP1/TP2 tiếp cận |

### Cách đọc

- **MacroRegime = ACCOMMODATIVE**: Điều kiện tốt, nới lỏng sizing
- **MacroRegime = NEUTRAL**: Thị trường trung tính, vận hành bình thường
- **MacroRegime = RESTRICTIVE**: Tín hiệu cảnh báo, thắt chặt sizing

---

## 4. ATC Alert

**ATC (At-The-Close)** là phiên khớp lệnh đóng cửa 14:43–14:45 HoSE.

### Khi nào xuất hiện

Badge đỏ 🔴 trên sidebar khi có vị thế đến hạn T+2.5 trong ngày.

### Logic tính T+2.5

```
Ngày mua (T) + 2 ngày giao dịch = T+2 (ngày nhận cổ phiếu)
Ngày bán sớm nhất = T+2 (bán T+2 thực tế tính là T+2.5 trong quy định hiện hành)
```

Ví dụ:
- Mua thứ Hai → sớm nhất bán được thứ Tư
- Mua thứ Sáu → sớm nhất bán được thứ Ba tuần sau

### Quyết định thoát lệnh

| Điều kiện | Hành động | Độ ưu tiên |
|---|---|---|
| Distribution warning = EXIT | `SELL_FULL_ATC` | 🔴 HIGH |
| Stop-loss bị phá vỡ | `SELL_FULL_ATC` | 🔴 HIGH |
| TP1 chạm + hold ≥ 3 ngày | `SELL_PARTIAL_ATC (40%)` | 🟡 MEDIUM |
| TP2 chạm | `SELL_FULL_ATC` | 🟡 MEDIUM |
| Xu hướng yếu nhưng ổn | `EXTEND` | 🟢 LOW |
| Bình thường | `HOLD` | — |

---

## 5. Profiler

**Trang phân tích chuyên sâu nhất của hệ thống.**

### Cách sử dụng

1. Nhập mã cổ phiếu (ví dụ: `VCB`, `FPT`, `HPG`)
2. Chọn timeframe và chế độ (Normal / Intraday)
3. Nhấn **Phân tích**

### Các thành phần kết quả

#### 5.1 Signal Card — Tín hiệu chính

| Trường | Ý nghĩa |
|---|---|
| **Action** | `STRONG_BUY` / `BUY` / `WATCH` / `NO_ACTION` / `EXIT` / `FORCED_EXIT` |
| **Confidence** | Độ tin cậy của tín hiệu (0–100%) |
| **Entry Price** | Giá vào lệnh đề xuất |
| **Stop Loss (SL)** | Giá cắt lỗ (ATR-based) |
| **TP1 / TP2** | Mục tiêu lợi nhuận 1 và 2 |
| **R:R Ratio** | Tỷ lệ Risk:Reward |
| **Signal Mode** | `MODE_W` / `MOMENTUM` / `MEAN_REVERT` / `RANGE` |

#### 5.2 Multi-Horizon Forecast

Dự báo theo 3 horizon thời gian, mỗi horizon có vote và confidence:

| Horizon | Khoảng thời gian | Tín hiệu chính |
|---|---|---|
| **Short** | 3–5 phiên giao dịch | RSI, MACD, Stochastic, BB position, gap |
| **Mid** | ~1 tháng | Cấu trúc trend, regime, khối lượng tích luỹ |
| **Long** | 3–6 tháng | Cơ bản, macro, xu hướng dài hạn |

Vote: **TĂNG** 📈 / **GIẢM** 📉 / **TRUNG LẬP** ↔

#### 5.3 Smart Money Score (SMS)

Đánh giá sự tham gia của "tiền thông minh" (tổ chức, cá voi):

| Nhãn | SMS Score | Ý nghĩa |
|---|---|---|
| STRONG ACCUM | ≥ 70 | Tích luỹ mạnh, khả năng tăng cao |
| ACCUM | 50–69 | Đang tích luỹ |
| NEUTRAL | 30–49 | Trung tính |
| DISTRIB | 10–29 | Phân phối, cẩn thận |
| STRONG DISTRIB | < 10 | Phân phối mạnh, rủi ro cao |

#### 5.4 MFPM Score (Money Flow & Price Momentum)

Kết hợp dòng tiền + động lực giá:

| Score | Ý nghĩa |
|---|---|
| 80–100 | Dòng tiền vào mạnh + xu hướng giá tốt |
| 60–79 | Tích cực |
| 40–59 | Trung tính |
| 20–39 | Dòng tiền yếu |
| 0–19 | Dòng tiền ra, rủi ro cao |

#### 5.5 AMD Phase (Accumulation–Markup–Distribution)

Xác định giai đoạn trong chu kỳ Wyckoff:

| Phase | Ý nghĩa | Hành động |
|---|---|---|
| **ACCUMULATION** | Smart money đang gom hàng | Cân nhắc mua |
| **MARKUP** | Giá tăng mạnh, xu hướng xác nhận | Giữ hoặc thêm |
| **DISTRIBUTION** | Smart money bán ra | Cẩn thận, chuẩn bị thoát |
| **MARKDOWN** | Giá giảm | Không mua |
| **UNCERTAIN** | Không xác định | Chờ tín hiệu rõ hơn |

#### 5.6 HMM State (Hidden Markov Model)

Trạng thái ẩn của thị trường được phát hiện bởi mô hình HMM:

- **TRENDING_UP**: Xu hướng tăng mạnh
- **TRENDING_DOWN**: Xu hướng giảm
- **SIDEWAYS_LOW_VOL**: Đi ngang, khối lượng thấp
- **SIDEWAYS_HIGH_VOL**: Đi ngang, biến động cao (cẩn thận)

#### 5.7 BiLSTM Forecast

Mô hình deep learning Bidirectional LSTM dự báo giá trong 5–10 phiên tới. Kết quả bao gồm:
- Giá dự báo (mean)
- Dải confidence interval 80%
- Hướng xu hướng (TĂNG / GIẢM)

#### 5.8 M-CVD (Multi-day Cumulative Volume Delta)

Đo lường áp lực mua/bán tích luỹ trong nhiều ngày:
- **Dương và tăng**: Áp lực mua đang lấn át
- **Âm và giảm**: Áp lực bán đang lấn át
- **M-CVD Trend**: `BULLISH` / `BEARISH` / `NEUTRAL`

---

## 6. Scanner

**Quét nhiều mã trong một lần để lọc cơ hội đầu tư.**

### Bộ lọc có sẵn

| Lọc | Tùy chọn |
|---|---|
| **Universe** | VN30, VN100, HOSE, HNX, Custom |
| **Action** | ALL / STRONG_BUY / BUY / WATCH |
| **Macro Regime** | ACCOMMODATIVE / NEUTRAL / RESTRICTIVE |
| **Sector** | 18 ngành (Ngân hàng, BĐS, Thép, Dầu khí...) |
| **Signal Mode** | MODE_W / MOMENTUM / MEAN_REVERT |
| **Min Confidence** | 0–100% |
| **Min MFPM** | 0–100 |

### Cột trong kết quả Scanner

| Cột | Ý nghĩa |
|---|---|
| Mã | Mã cổ phiếu |
| Action | Tín hiệu hành động |
| Conf | Độ tin cậy |
| MFPM | Điểm dòng tiền + momentum |
| SMS | Smart Money Score |
| Giá | Giá đóng cửa gần nhất |
| Vào lệnh | Entry price đề xuất |
| Cắt lỗ | Stop-loss |
| TP1/TP2 | Target profit 1 & 2 |
| R:R | Risk:Reward ratio |
| AMD | Giai đoạn Wyckoff |
| HMM | Trạng thái HMM |
| Stealth | Có tích luỹ lén không |
| Dist Warn | Cảnh báo phân phối |

### Cách đọc kết quả

1. **Ưu tiên mã có Action = BUY/STRONG_BUY** với Confidence ≥ 70%
2. **Kiểm tra AMD**: ACCUMULATION hoặc MARKUP mới nên mua
3. **Kiểm tra Dist Warn**: Nếu có cảnh báo phân phối, bỏ qua dù Action = BUY
4. **Nhấp vào mã** để chuyển sang Profiler xem phân tích chi tiết

---

## 7. Dòng tiền

**Phân tích dòng tiền theo chiều sâu.**

### 7.1 Whale Flow (Dòng tiền Cá voi)

Theo dõi các lệnh khớp lớn (put-through deals + block trades):

| Chỉ số | Ý nghĩa |
|---|---|
| **Whale Net Buy** | Tổng mua – Tổng bán của giao dịch thoả thuận |
| **Whale Net 5d** | Xu hướng 5 ngày gần nhất |
| **Stealth Accumulation** | Hệ thống phát hiện tích luỹ lén (khối lượng tăng, giá không tăng tương xứng) |

### 7.2 CVD (Cumulative Volume Delta)

```
CVD = Σ (Volume mua chủ động - Volume bán chủ động)
```

CVD dương và tăng dần = áp lực mua tích luỹ  
CVD âm và giảm = áp lực bán tích luỹ

### 7.3 Sector Heatmap

Bản đồ nhiệt hiển thị dòng tiền theo 18 ngành trong 1 phiên / 5 phiên / 1 tháng. Màu sắc:
- 🟢 Xanh đậm: Ngành có dòng tiền vào mạnh
- 🔴 Đỏ đậm: Ngành có dòng tiền ra mạnh

---

## 8. Backtest

**Kiểm tra chiến lược trên dữ liệu lịch sử.**

### Mô hình chi phí giao dịch VN

| Chi phí | Tỷ lệ |
|---|---|
| Phí mua | 0.15% |
| Phí bán | 0.15% |
| Thuế TNCN bán | 0.10% |
| Slippage ước tính | 0.05% |
| **Tổng lượt mua** | **0.20%** |
| **Tổng lượt bán** | **0.30%** |
| **Tổng 1 round-trip** | **0.50%** |

### Các chỉ số hiệu suất

| Chỉ số | Ý nghĩa |
|---|---|
| **CAGR** | Tăng trưởng kép hàng năm |
| **Sharpe Ratio** | Return / Risk (> 1.5 = tốt) |
| **Max Drawdown** | Mức sụt giảm tối đa từ đỉnh |
| **Win Rate** | Tỷ lệ lệnh thắng |
| **Avg Win / Avg Loss** | R:R thực tế trung bình |
| **Profit Factor** | Tổng lãi / Tổng lỗ |

### T+2.5 trong Backtest

Backtest mô phỏng đúng quy tắc T+2.5: vị thế mua ngày T chỉ được tính là sở hữu từ ngày T+2.5 → bán sớm nhất ngày T+3 (làm tròn).

---

## 9. Portfolio & Hiệu suất

### Mở vị thế

1. Từ Profiler hoặc Scanner, nhấn **Thêm vào Portfolio**
2. Hệ thống tự tính:
   - **Lot size** = `(Vốn × % risk) / (Entry − Stop Loss)`
   - **Cost basis** = `Lot × Entry × (1 + 0.20%)`
3. Vị thế được lưu vào `data/portfolio.json`

### Đóng vị thế

1. Chọn vị thế → nhập giá bán
2. Hệ thống tính P&L:
   ```
   P&L = Lot × (Exit − Entry) − (Lot × Exit × 0.30%)
   ```

### Performance Dashboard

- **Equity Curve**: Đồ thị tổng danh mục theo thời gian
- **Sector Breakdown**: Phân bổ theo ngành
- **Win/Loss Distribution**: Phân phối lãi/lỗ
- **Open Risk**: Tổng rủi ro đang mở (% NAV)

---

## 10. Audit Log

Mọi thao tác của hệ thống được ghi vào nhật ký bất biến (`data/audit.jsonl`).

### Các loại sự kiện

| Action | Ý nghĩa |
|---|---|
| `PROFILE` | Phân tích một mã |
| `SCAN` | Chạy Scanner |
| `OPEN_POSITION` | Mở vị thế |
| `CLOSE_POSITION` | Đóng vị thế |
| `ATC_ADVISORY` | Khuyến nghị thoát ATC |

### Bộ lọc Audit

- Lọc theo Action, Mã, Ngày, Kết quả
- Xuất CSV để phân tích bên ngoài

---

## 11. Các chỉ số kỹ thuật

### Nhóm xu hướng (Trend)

| Chỉ số | Công thức | Ý nghĩa |
|---|---|---|
| **SMA** | `SUM(Close, N) / N` | Đường trung bình đơn; xác nhận xu hướng dài hạn |
| **EMA** | `EMA(t) = Close × k + EMA(t-1) × (1-k)`, k=2/(N+1) | Trung bình mũ; phản ứng nhanh hơn SMA |
| **Golden Cross** | SMA_fast cắt lên trên SMA_slow | Tín hiệu mua dài hạn |
| **Death Cross** | SMA_fast cắt xuống dưới SMA_slow | Tín hiệu bán |

### Nhóm momentum

| Chỉ số | Công thức | Ngưỡng quan trọng |
|---|---|---|
| **RSI** | `100 − 100 / (1 + RS)`, RS = AvgGain/AvgLoss | < 30: quá bán; > 70: quá mua (VN: > 75 mới thực sự quá mua) |
| **RSI thích ứng** | RSI thresholds điều chỉnh theo ngành và tối ưu PSO | Mỗi ngành có ngưỡng riêng (PSO-optimized) |
| **MACD** | `EMA(12) − EMA(26)` | Cắt đường tín hiệu EMA(9) = entry signal |
| **Stochastic** | `(Close − Low_14) / (High_14 − Low_14) × 100` | < 20: quá bán; > 80: quá mua |
| **ROC** | `(Close − Close_N) / Close_N × 100` | Tốc độ thay đổi giá |

### Nhóm biến động

| Chỉ số | Công thức | Ứng dụng |
|---|---|---|
| **ATR** | `Mean(TrueRange_N)` | Đo lường biến động; dùng để tính stop-loss |
| **Bollinger Bands** | `SMA ± 2×STD` | Giá chạm lower band = cơ hội; chạm upper = cẩn thận |
| **BB %B** | `(Close − Lower) / (Upper − Lower)` | 0 = lower band; 1 = upper band |

### Nhóm khối lượng

| Chỉ số | Công thức | Ý nghĩa |
|---|---|---|
| **OBV** | `OBV += Vol nếu Close↑; OBV -= Vol nếu Close↓` | Tích luỹ khối lượng theo hướng giá |
| **VWAP** | `Σ(Price × Vol) / Σ(Vol)` | Giá trung bình theo khối lượng; tham chiếu trong ngày |
| **Vol Ratio** | `Vol hôm nay / AvgVol_N` | > 1.5: khối lượng bất thường; > 3: breakout tiềm năng |
| **MFI** | Kết hợp giá và khối lượng, 0–100 | > 80: overbought; < 20: oversold |
| **CMF** | `Σ(MFM × Vol) / Σ(Vol)` | Chaikin Money Flow: > 0 = mua chủ động |

### Nhóm xu hướng mạnh

| Chỉ số | Ý nghĩa |
|---|---|
| **ADX** | > 25: xu hướng mạnh; > 40: xu hướng rất mạnh; < 20: đi ngang |
| **Hurst Exponent** | > 0.6: xu hướng; < 0.4: đảo chiều; = 0.5: random walk |
| **Z-score Volume** | Số độ lệch chuẩn của khối lượng so với trung bình → phát hiện đột biến |

### Chỉ số đặc thù thị trường VN

| Chỉ số | Mô tả |
|---|---|
| **Ceiling/Floor Streak** | Đếm số phiên liên tiếp chạm trần (+7%) / chạm sàn (−7%). +N phiên trần = nhu cầu mua cao; −N phiên sàn = phân phối hoặc margin call |
| **SuperTrend** | Đường xu hướng ATR-based; đổi chiều = tín hiệu đảo trend |
| **OFI (Order Flow Imbalance)** | Mất cân bằng dòng lệnh mua/bán trong sổ lệnh |
| **M-CVD** | CVD nhiều ngày; đo áp lực mua/bán tích luỹ |

---

## 12. Thuật toán và Logic khuyến nghị

### 12.1 AMF (Adaptive Multi-Factor) Engine

Lõi tính điểm tín hiệu của Profiler. Kết hợp 7 nhóm yếu tố:

```
Score_AMF = w1×Trend + w2×Momentum + w3×Volume + w4×Volatility
          + w5×SmartMoney + w6×Macro + w7×Fundamental
```

Trọng số `w` được điều chỉnh tự động theo:
- MacroRegime (ACCOMMODATIVE → nới Momentum; RESTRICTIVE → nới Fundamental)
- Signal Mode (MODE_W → nới SmartMoney)
- Volatility Regime (High vol → nới Volatility weight)

### 12.2 AMD Phase Detection (Wyckoff Method)

Thuật toán nhận diện 5 giai đoạn chu kỳ Wyckoff:

```
1. Phân tích cấu trúc giá (Higher High/Lower Low)
2. Phân tích khối lượng theo phase:
   - ACCUMULATION: vol tăng ở đáy, spread hẹp
   - MARKUP: vol tăng cùng giá
   - DISTRIBUTION: vol tăng ở đỉnh, giá không tăng
   - MARKDOWN: vol tăng khi giá giảm
3. Xác nhận bởi OFI và M-CVD
4. Áp dụng hysteresis để tránh flip-flop
```

### 12.3 HMM (Hidden Markov Model)

Mô hình Markov ẩn với 4 trạng thái học từ dữ liệu lịch sử:

- **Inputs**: Return hàng ngày, log(Vol Ratio), ATR normalised
- **States**: 4 trạng thái ẩn được gán nhãn hậu kỳ
- **Output**: Trạng thái hiện tại + xác suất chuyển trạng thái

### 12.4 MFPM Score

```
MFPM = 0.4 × MoneyFlow_Score + 0.3 × Momentum_Score + 0.3 × Price_Structure_Score

MoneyFlow_Score  = f(CMF, M-CVD, Whale Net, OFI)
Momentum_Score   = f(RSI, MACD, ROC, BB%B)
Price_Structure  = f(ADX, SMA alignment, Hurst, Vol quality)
```

### 12.5 Mode W Detection

Pattern "Mode W" là mẫu hình W-bottom với xác nhận khối lượng:

```
Điều kiện Mode W:
1. Đáy thứ 1 (W1) ← giá giảm với vol cao
2. Rally nhỏ ← vol thấp (hết áp lực bán)
3. Đáy thứ 2 (W2) thấp hơn W1 hoặc bằng ← vol thấp hơn W1 (bullish divergence)
4. Breakout qua neckline ← vol tăng mạnh
```

Khi phát hiện Mode W, `signal_mode = "MODE_W"` và score được bonus thêm.

### 12.6 Macro Gate

MacroRegime tác động đến việc nâng/hạ action:

| MacroRegime | Effect on Action |
|---|---|
| ACCOMMODATIVE | BUY → có thể STRONG_BUY nếu đủ điều kiện khác |
| NEUTRAL | Action giữ nguyên |
| RESTRICTIVE | STRONG_BUY → BUY; BUY → WATCH (giảm sizing) |

### 12.7 Earnings Risk Gate

Nếu BCTC (báo cáo tài chính quý) công bố trong vòng 5 ngày:
- Giảm Confidence −15%
- Action STRONG_BUY → BUY (earnings risk quá cao để có conviction mạnh)

### 12.8 Multi-Horizon Forecast Logic

```
Short-term (3–5 phiên):
  Bull signals: RSI ∈ (40,65), MACD cross up, Stoch < 30 reversal, BB %B < 0.2
  Bear signals: RSI > 75, MACD cross down, BB %B > 0.85, high vol decline
  Vote = sign(bull_pts − bear_pts), Conf = |bull − bear| / (bull + bear) × 100

Mid-term (~1 tháng):
  Bull: SMA alignment (fast > slow > price), MACD histogram positive slope, 
        ADX > 25 with DI+ > DI−, vol quality score > 0.6
  Bear: Death cross, MACD bearish divergence, regime = MARKDOWN

Long-term (3–6 tháng):
  Bull: Hurst > 0.6, fundamental_score > 60, MacroRegime = ACCOMMODATIVE,
        price > SMA_200
  Bear: Fundamental deterioration, macro restrictive, sector outflow
```

---

## 13. Quản lý rủi ro và vị thế

### 13.1 Stop-Loss ATR-based

```
Stop Loss = Entry − (ATR × multiplier)

Multiplier theo volatility regime:
  - Low vol:    1.0 × ATR
  - Normal vol: 1.5 × ATR  
  - High vol:   2.0 × ATR
  - Extreme:    2.5 × ATR
```

### 13.2 Position Sizing — Kelly Criterion

```
f* = (p × b − q) / b

Trong đó:
  p = xác suất thắng (win rate lịch sử của chiến lược)
  q = 1 − p
  b = Avg Win / Avg Loss (R:R ratio)

Áp dụng Kelly phân số (fractional Kelly):
  Lot size = Vốn × (f* × 0.25) / (Entry − Stop)
```

Hệ số 0.25 (Quarter Kelly) để giảm thiểu rủi ro do ước tính sai p và b.

### 13.3 Macro Sizing Multiplier

```
Khi MacroRegime = ACCOMMODATIVE: sizing × 1.0 (normal)
Khi MacroRegime = NEUTRAL:       sizing × 0.8
Khi MacroRegime = RESTRICTIVE:   sizing × 0.5
```

### 13.4 Calibrate Stop với VaR

Sau khi tính ATR-stop, hệ thống kiểm tra:
```
VaR_99 = quantile(returns, 1%) × Position Value

Nếu (Entry − ATR_Stop) < VaR_99 cần thiết:
  → Mở rộng stop đến mức đảm bảo không vượt quá VaR budget
```

---

## 14. Quy tắc T+2.5 và ATC

### Lịch giao dịch HoSE

| Phiên | Thời gian | Hình thức |
|---|---|---|
| **ATO** (At-The-Open) | 9:00–9:15 | Khớp lệnh định kỳ mở cửa |
| **Liên tục sáng** | 9:15–11:30 | Khớp lệnh liên tục |
| **Nghỉ trưa** | 11:30–13:00 | Không giao dịch |
| **Liên tục chiều** | 13:00–14:30 | Khớp lệnh liên tục |
| **Gần đóng** | 14:30–14:43 | Khớp lệnh liên tục |
| **ATC** (At-The-Close) | 14:43–14:45 | Khớp lệnh định kỳ đóng cửa |

### Tại sao thoát lệnh ở ATC?

1. **Thanh khoản cao nhất**: Đây là phiên có khối lượng khớp tập trung nhất cuối ngày
2. **Giá đóng cửa chính thức**: Giá ATC = giá reference cho ngày mai
3. **Giảm slippage**: Lệnh ATC ít bị trượt giá hơn lệnh LO (Limit Order) cuối ngày
4. **T+2.5 compliance**: Bán đúng ngày T+2.5 để tuân thủ quy định thanh toán

---

## 15. Câu hỏi thường gặp

**Q: Tại sao có mã Action = STRONG_BUY nhưng Confidence thấp?**  
A: Action dựa trên tổng điểm AMF, Confidence dựa trên sự đồng thuận giữa các chỉ số. Mã có nhiều chỉ số mâu thuẫn sẽ có Confidence thấp dù tổng điểm cao. Nên ưu tiên mã có cả Action tốt lẫn Confidence cao.

**Q: Distribution Warning nghĩa là gì?**  
A: Hệ thống phát hiện khối lượng tăng bất thường trong khi giá không tăng hoặc giảm → dấu hiệu smart money đang bán ra. Nếu bạn đang giữ mã này, cân nhắc thoát một phần.

**Q: Stealth Accumulation khác gì Accumulation thông thường?**  
A: Stealth Accumulation = tích luỹ lén, tức là khối lượng tăng nhưng giá gần như không biến động. Smart money đang gom hàng dần dần để không làm giá tăng nhanh. Đây thường là giai đoạn sớm trước khi markup.

**Q: MacroScore âm có nghĩa là gì?**  
A: MacroScore = -100 đến +100. Âm = điều kiện vĩ mô bất lợi (VND yếu, lãi suất tăng, SBV hút tiền). Trong điều kiện này, hệ thống tự động thắt chặt sizing và nâng ngưỡng để ra tín hiệu BUY.

**Q: Hệ thống có hoạt động intraday không?**  
A: Có. Nếu có API FiinQuant, Profiler hỗ trợ mode Intraday với dữ liệu 5 phút, CVD intraday, và OFI từ sổ lệnh thời gian thực.

**Q: Dữ liệu được cập nhật mỗi bao lâu?**  
A: OHLCV cuối ngày từ DNSE (cập nhật sau 17:00). Intraday 5m từ FiinQuant (nếu có). Macro (USD/VND, bond yield) được cache 5 phút TTL.

---

*TradingOS Alpha v1.2 · Tài liệu này được cập nhật cùng với phiên bản ứng dụng*
