# 📖 Hướng Dẫn Sử Dụng NewTradingOS v14.0
## Nền tảng giao dịch đa khung thời gian thị trường Việt Nam

> **Lưu ý:** Đây là công cụ hỗ trợ quyết định đầu tư. Không phải khuyến nghị tài chính. Mọi quyết định giao dịch do nhà đầu tư tự chịu trách nhiệm.

---

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Cài đặt và khởi chạy](#2-cài-đặt-và-khởi-chạy)
3. [Giao diện và điều hướng](#3-giao-diện-và-điều-hướng)
4. [Macro Pulse](#4-macro-pulse)
5. [Scanner theo khung thời gian](#5-scanner-theo-khung-thời-gian)
6. [ML Forecast](#6-ml-forecast)
7. [Backtest](#7-backtest)
8. [Portfolio](#8-portfolio)
9. [Audit Log](#9-audit-log)
10. [Hệ thống tính điểm 100 điểm](#10-hệ-thống-tính-điểm-100-điểm)
11. [Các chỉ số kỹ thuật](#11-các-chỉ-số-kỹ-thuật)
12. [Stop-Loss và Target theo ATR](#12-stop-loss-và-target-theo-atr)
13. [Phát hiện chế độ thị trường (Regime)](#13-phát-hiện-chế-độ-thị-trường)
14. [Đặc thù thị trường VN được tích hợp](#14-đặc-thù-thị-trường-vn)
15. [Hỏi & Đáp](#15-hỏi--đáp)

---

## 1. Tổng quan

NewTradingOS v14.0 là ứng dụng phân tích cổ phiếu đa khung thời gian, được tối ưu hoá riêng cho thị trường chứng khoán Việt Nam (HoSE + HNX).

### Điểm nổi bật

| Tính năng | Mô tả |
|---|---|
| **5 khung thời gian** | 1W (tuần), 2W (2 tuần), 1M (tháng), 3M (quý), 5M (5 tháng) |
| **100 điểm composite** | 7 thành phần điểm, mỗi thành phần đo một khía cạnh khác nhau |
| **VN-specific indicators** | CMF, SuperTrend, Ceiling/Floor Streak - được hiệu chỉnh riêng cho VN |
| **ML Ensemble 6 models** | LSTM, XGBoost, RF, Prophet, ARIMA, Monte Carlo |
| **Macro regime detection** | HMM + world markets + foreign flow → regime label |
| **Portfolio tracker** | Mở/đóng vị thế, P&L, T+2 readiness |
| **Audit log bất biến** | Ghi lại mọi sự kiện kinh doanh |

### Vũ trụ cổ phiếu

| Danh sách | Số mã | Mô tả |
|---|---|---|
| VN30 | 30 | Blue chip HoSE |
| VN100 | 100 | Top 100 vốn hoá |
| HOSE | 110 | Sàn HoSE mở rộng |
| HNX | 20 | Sàn Hà Nội |
| MARKET_SCAN_LIST | 130 | HOSE + HNX kết hợp |

---

## 2. Cài đặt và khởi chạy

### Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|---|---|
| Python | 3.10 trở lên (khuyến nghị 3.13) |
| RAM | 4 GB tối thiểu (khuyến nghị 8 GB) |
| Kết nối internet | Bắt buộc (để lấy dữ liệu từ API) |
| OS | Windows / macOS / Linux |

### Cài đặt

```bash
# 1. Tạo môi trường ảo
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux  
source .venv/bin/activate

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Khởi chạy ứng dụng
python -m streamlit run app.py
```

### Các thư viện chính

| Thư viện | Mục đích |
|---|---|
| `streamlit` | Giao diện web |
| `pandas`, `numpy` | Xử lý dữ liệu |
| `plotly` | Biểu đồ tương tác |
| `xgboost`, `scikit-learn` | ML models |
| `prophet` | Dự báo chuỗi thời gian |
| `statsmodels` | ARIMA/SARIMAX |
| `hmmlearn` | Hidden Markov Model |
| `scipy` | Thống kê |

---

## 3. Giao diện và điều hướng

### Sidebar (cột trái)

| Mục | Chức năng |
|---|---|
| **Language** | Chuyển đổi Tiếng Việt / English |
| **Watchlist** | Danh sách mã theo dõi (mỗi mã 1 dòng) |
| **Universe** | Chọn tập dữ liệu: Watchlist / VN30 / VN100 / HOSE / HNX |
| **Lookback days** | Số ngày lịch sử (180–1095 ngày) |
| **🔄 Tải Dữ Liệu** | Tải OHLCV cho tất cả mã trong universe |
| **🌐 Cập nhật Macro** | Tải dữ liệu vĩ mô (thị trường thế giới + VN breadth) |

### Các tab chính

```
🌐 Macro Pulse     — Tổng quan vĩ mô và chế độ thị trường
⚡ 1W Scanner      — Quét tín hiệu khung 1 tuần
📅 2W Scanner      — Quét tín hiệu khung 2 tuần
📆 1M Scanner      — Quét tín hiệu khung 1 tháng
📊 3M Scanner      — Quét tín hiệu khung 3 tháng
🎯 5M Scanner      — Quét tín hiệu khung 5 tháng
🧠 ML Forecast     — Dự báo giá bằng AI ensemble
🧪 Backtest        — Kiểm thử chiến lược lịch sử
💼 Portfolio       — Quản lý danh mục
📜 Audit Log       — Nhật ký giao dịch
📖 Hướng Dẫn      — Tài liệu này
```

### Quy trình sử dụng cơ bản

```
1. Sidebar → Chọn Universe → Tải Dữ Liệu
2. Sidebar → Cập nhật Macro
3. Tab Macro Pulse → Xác định regime (bull/sideways/bear)
4. Tab Scanner phù hợp → Lọc mã theo tín hiệu
5. Mã quan tâm → Xem chi tiết điểm và stop/target
6. Tab Portfolio → Mở vị thế
7. Theo dõi stop/target hàng ngày
```

---

## 4. Macro Pulse

**Đọc điều kiện thị trường trước khi scan.**

### Các chỉ số vĩ mô được theo dõi

| Nguồn | Symbol | Ý nghĩa |
|---|---|---|
| S&P 500 | `^GSPC` | Xu hướng thị trường Mỹ |
| Nikkei 225 | `^N225` | Thị trường Nhật, vốn châu Á |
| CSI 300 | `000300.SS` | Thị trường Trung Quốc, tương quan khu vực với VN |
| Natural Gas | `NG=F` | Nhạy cảm với nhóm năng lượng / hàng hoá |
| Gold | `GC=F` | Risk-off indicator |
| Crude Oil | `CL=F` | Ảnh hưởng cổ phiếu dầu khí VN |
| USD Index | `DX-Y.NYB` | Ảnh hưởng VNĐ và dòng tiền ngoại |
| VIX | `^VIX` | Chỉ số sợ hãi; > 25 = bất ổn |

### MacroScore và Regime

Điểm macro (0–10) được tổng hợp từ:
- Hiệu suất thị trường thế giới (mỗi thị trường +0 đến +1 điểm)
- Breadth VN-Index (tỷ lệ tăng/giảm)
- Dòng tiền ngoại (±1 điểm)

| MacroScore | Regime Label | Ý nghĩa |
|---|---|---|
| 7.5–10.0 | **BULL** | Điều kiện tốt, risk-on |
| 4.5–7.4 | **NEUTRAL** | Trung tính, chọn lọc |
| 0.0–4.4 | **BEAR** | Cẩn thận, giảm exposure |

### Ảnh hưởng của Regime đến Scanner

| Regime | Tác động |
|---|---|
| BULL | Tất cả tín hiệu BUY đều hiển thị |
| SIDEWAYS | Chỉ hiển thị BUY ≥ 65 điểm |
| BEAR | BUY bị downgrade → WATCH; chỉ scan để theo dõi |

---

## 5. Scanner theo khung thời gian

### Chọn khung thời gian phù hợp

| Tab | Horizon | Phù hợp với | Regime |
|---|---|---|---|
| ⚡ 1W | ~5 phiên | Momentum trading, đánh nhanh | Bull only |
| 📅 2W | ~10 phiên | Swing trading | Bull + Sideways |
| 📆 1M | ~22 phiên | Trend following | Bull + Sideways |
| 📊 3M | ~66 phiên | Positional (kết hợp BCTC) | Mọi regime |
| 🎯 5M | ~110 phiên | Macro-driven, vị thế lớn | Mọi regime |

### Cách đọc kết quả Scanner

| Cột | Ý nghĩa |
|---|---|
| **Mã** | Mã cổ phiếu |
| **Score** | Điểm tổng hợp (0–100) |
| **Action** | Tín hiệu: STRONG BUY / BUY / HOLD / WATCH / SELL |
| **Giá** | Giá đóng cửa / giá tham chiếu dùng cho score hiện tại |
| **Stop** | Giá cắt lỗ ATR-based |
| **Target** | Giá mục tiêu |
| **R:R** | Tỷ lệ Risk:Reward |
| **Nguồn** | Nguồn dữ liệu bar hiện tại (DNSE / SSI) |

### Thứ tự ưu tiên khi lọc

1. **Action = STRONG BUY hoặc BUY** (không mua HOLD / WATCH / SELL)
2. **Regime phù hợp** (tham khảo bảng trên)
3. **R:R ≥ 2.0** (đặt cược tối thiểu 1 được 2)
4. **Score ≥ 70** (càng cao càng tốt)
5. **Kiểm tra thêm** trong bảng Score Breakdown để xem thành phần nào yếu

### Score Breakdown

Nhấp vào mã bất kỳ để xem chi tiết điểm 7 thành phần:

```
Trend    [max 25]: SMA/EMA alignment + SuperTrend direction
Momentum [max 20]: MACD cross + histogram + ROC
RSI      [max 15]: Zone-based scoring (VN-calibrated)
Volume   [max 20]: Vol ratio + MFI + CMF + Streak
Foreign  [max  5]: Net foreign buy (1M/3M/5M only)
Macro    [max 10]: macro_score / 10
ADX      [max  5]: Trend quality gate (ADX > 25)
─────────────────
Total    [max 100]
```

---

## 6. ML Forecast

**Dự báo giá sử dụng ensemble 6 mô hình AI.**

### Các mô hình trong ensemble

| Mô hình | Trọng số | Mô tả |
|---|---|---|
| **LSTM** | 25% | Mạng nơ-ron LSTM; fallback sang Holt's nếu TensorFlow chưa cài |
| **XGBoost** | 20% | Gradient boosting trên 60+ features kỹ thuật |
| **Random Forest** | 20% | Bagging ensemble trên features |
| **Prophet** | 15% | Mô hình additive seasonality của Meta |
| **ARIMA** | 10% | SARIMAX(1,1,1)(0,1,0,5) |
| **Monte Carlo** | 10% | Mô phỏng Geometric Brownian Motion (1000 lần) |

### Cách đọc kết quả Forecast

- **Giá dự báo**: Mean của ensemble
- **Khoảng tin cậy (80%)**: Khoảng giá có 80% xác suất nằm trong
- **Hướng**: TĂNG / GIẢM / TRUNG LẬP
- **Confidence**: Mức đồng thuận giữa các mô hình (cao = nhất quán)

### Lưu ý quan trọng

- Dự báo ML là xác suất, không phải chắc chắn
- Monte Carlo giả định phân phối Gaussian → đuôi mập (fat tail) VN chưa được phản ánh đầy đủ
- Sử dụng kết hợp với tín hiệu kỹ thuật từ Scanner, không dùng riêng lẻ

---

## 7. Backtest

**Mô phỏng chiến lược trên dữ liệu lịch sử.**

### Mô hình chi phí thực tế VN

| Chi phí | Tỷ lệ |
|---|---|
| Phí mua | 0.15% |
| Phí bán | 0.15% |
| Thuế TNCN bán | 0.10% |
| Slippage ước tính | 0.05% |
| **Tổng mua** | **0.20%** |
| **Tổng bán** | **0.30%** |
| **Round-trip** | **0.50%** |

### T+2 trong Backtest

Backtest mô phỏng đúng quy tắc thanh toán:
- Mua ngày T → chỉ được bán khi đã giữ đủ tối thiểu 2 phiên giao dịch
- Lệnh signal/time-exit được thực hiện ở open của bar kế tiếp khi vị thế đã T+2 ready

### Chỉ số hiệu suất

| Chỉ số | Cách đọc |
|---|---|
| **CAGR** | % tăng trưởng mỗi năm (> 15% là tốt so với benchmark VN-Index) |
| **Sharpe Ratio** | Return/Risk (> 1.5 tốt; > 2.0 rất tốt) |
| **Max Drawdown** | Sụt giảm tối đa từ đỉnh (< -30% là nguy hiểm) |
| **Win Rate** | Tỷ lệ lệnh thắng (> 55% với R:R 2:1 là đủ sinh lợi) |
| **Profit Factor** | Tổng lãi / Tổng lỗ (> 1.5 là tốt) |

---

## 8. Portfolio

**Quản lý danh mục và theo dõi vị thế.**

### Mở vị thế

1. Trong Scanner, chọn mã quan tâm
2. Nhập số vốn muốn đặt và % rủi ro chấp nhận (mặc định 1–2%)
3. Hệ thống tự tính lot size:

```
Lot Size = FLOOR( (Vốn × %Risk) / (Entry − Stop Loss) )
```

4. Cost basis = `Lot × Entry × 1.0020` (bao gồm phí mua + slippage)

### Đóng vị thế

Nhập giá bán thực tế. P&L được tính:

```
P&L = Lot × (Exit − Entry) − Lot × Exit × 0.0030
```

### Trạng thái vị thế T+2

| Chỉ báo | Ý nghĩa |
|---|---|
| `⏳ T+2 Ready = No` | Đang giữ, chưa đủ số phiên để đóng |
| `✅ T+2 Ready = Yes` | Đã đủ điều kiện T+2 để đóng vị thế |

### Vốn ban đầu

Mặc định: **100,000,000 VNĐ**. Thay đổi trong `config.py → INITIAL_CAPITAL`.

---

## 9. Audit Log

Mọi sự kiện kinh doanh được ghi lại tự động vào `data/audit.jsonl` (không thể xoá, chỉ thêm).

### Loại sự kiện

| Action | Trigger |
|---|---|
| `LOAD_DATA` | Tải dữ liệu |
| `UPDATE_MACRO` | Cập nhật macro |
| `SCAN_SIGNAL` | Chạy scanner hoặc ghi nhận tín hiệu từng mã |
| `OPEN_POSITION` | Mở vị thế |
| `CLOSE_POSITION` | Đóng vị thế |

### Bộ lọc

- Lọc theo Action type, Mã, Khoảng thời gian
- Xem tóm tắt số lượng theo loại
- Xuất CSV để phân tích ngoài ứng dụng

---

## 10. Hệ thống tính điểm 100 điểm

### Tổng quan 7 thành phần

```
┌──────────────────────────────────────────────────────────┐
│                  SCORE TỔNG HỢP (0–100)                  │
├──────────┬──────────┬──────────┬───────────┬─────────────┤
│ Trend    │ Momentum │   RSI    │  Volume   │   Foreign   │
│ max 25   │  max 20  │  max 15  │   max 20  │    max 5    │
├──────────┴──────────┴──────────┴───────────┴─────────────┤
│             Macro Regime              │   ADX Strength   │
│               max 10                  │      max 5       │
└───────────────────────────────────────┴──────────────────┘
```

### Thành phần 1: Trend (max 25 điểm)

| Điều kiện | Điểm |
|---|---|
| Close > SMA_fast | +5 |
| Close > SMA_slow | +6 |
| SMA_fast > SMA_slow (Golden Cross) | +5 |
| EMA_fast > EMA_slow | +5 |
| SMA_fast tăng so với 3 phiên trước | +4 |
| SuperTrend direction = +1 (bullish) | +4 |

### Thành phần 2: Momentum (max 20 điểm)

| Điều kiện | Điểm |
|---|---|
| MACD cắt lên trên Signal line | +8 |
| MACD Histogram dương | +6 |
| ROC > 5% | +6 |

### Thành phần 3: RSI (max 15 điểm) — Đặc biệt hiệu chỉnh VN

| RSI Zone | Điểm | Giải thích |
|---|---|---|
| 45 ≤ RSI < 65 | 15 | **VN sweet spot** — cổ phiếu VN thường tăng mạnh nhất trong vùng này |
| 30 ≤ RSI < 45 | 12 | Hồi phục từ vùng quá bán |
| 65 ≤ RSI ≤ 75 | 10 | Momentum continuation — VN stock có thể duy trì nhiều tuần |
| RSI < 30 | 7 | Quá bán sâu, rủi ro cao |
| 75 < RSI ≤ 85 | 5 | Bắt đầu quá mua |
| RSI > 85 | 2 | Quá mua nghiêm trọng |

> **Tại sao RSI 65–75 = 10 điểm thay vì phạt?** Cổ phiếu VN trong bull run thường duy trì RSI 65–75 nhiều tuần mà không đảo chiều. Phạt vùng này sẽ bỏ lỡ phần lớn lợi nhuận momentum.

### Thành phần 4: Volume/Flow (max 20 điểm)

| Điều kiện | Điểm |
|---|---|
| Vol Ratio > 1.5 | +5 |
| Vol Ratio > 2.5 | +3 (thêm) |
| Vol tăng + Close > SMA_fast | +2 |
| 3 ngày tích luỹ > Vol_MA × 1.2 | +2 |
| MFI > 50 | +2 |
| CMF > 0.05 (dòng tiền thông minh vào) | +3 |
| CMF > 0.15 (dòng tiền tổ chức mạnh) | +1 (thêm) |
| Streak ≥ +2 (≥ 2 phiên trần liên tiếp) | +2 |
| Streak ≤ −2 (≥ 2 phiên sàn liên tiếp) | **−3** (phạt) |

### Thành phần 5: Foreign Flow (max 5 điểm)

Tính cho khung 2W, 1M, 3M, 5M. Hiện tại dữ liệu dùng KBS session snapshot:
- Nếu có verified multi-session history trong tương lai, scoring sẽ ưu tiên `net_20d`
- Với contract hiện tại, `net_20d` giữ neutral và scoring fallback sang net foreign flow của phiên hiện tại

### Thành phần 6: Macro Regime (max 10 điểm)

```
Macro điểm = macro_score (0–10) / 10 × 10 điểm = macro_score
```

### Thành phần 7: ADX Strength (max 5 điểm)

| ADX | Điểm |
|---|---|
| ADX > 40 (rất mạnh) | 5 |
| ADX > 25 (mạnh) | 3 |
| ADX ≤ 25 (yếu/ngang) | 0 |

### Ngưỡng ra quyết định

| Score | Action |
|---|---|
| ≥ 80 | 🟢 **STRONG BUY** |
| 65–79 | 🟢 **BUY** |
| 45–64 | 🟡 **HOLD** |
| 30–44 | 🔵 **WATCH** |
| < 30 | 🔴 **SELL** |

### Điều chỉnh tự động

- **Regime = BEAR/EXTREME_BEAR**: BUY → WATCH (downgrade)
- **Manipulation flag**: STRONG BUY → BUY
- **Streak ≤ −3** (sàn liên tiếp): bật manipulation flag

---

## 11. Các chỉ số kỹ thuật

### Thông số theo khung thời gian

| Indicator | 1W | 2W | 1M | 3M | 5M |
|---|---|---|---|---|---|
| SMA fast | 5 | 10 | 20 | 50 | 100 |
| SMA slow | 20 | 40 | 60 | 120 | 200 |
| EMA fast | 5 | 10 | 20 | 50 | 100 |
| EMA slow | 20 | 40 | 60 | 120 | 200 |
| RSI period | 7 | 9 | 14 | 21 | 28 |
| ATR period | 7 | 10 | 14 | 21 | 28 |
| Volume MA | 5 | 10 | 20 | 50 | 60 |

### 21 chỉ số được tính trong compute_all()

| Cột | Tên đầy đủ | Công thức ngắn gọn |
|---|---|---|
| `SMA_fast` | Simple Moving Average ngắn | `rolling(N).mean()` |
| `SMA_slow` | Simple Moving Average dài | `rolling(N).mean()` |
| `EMA_fast` | Exponential MA ngắn | `ewm(span=N).mean()` |
| `EMA_slow` | Exponential MA dài | `ewm(span=N).mean()` |
| `RSI` | Relative Strength Index | Wilder smoothing, period N |
| `MACD` | MACD Line | `EMA(12) − EMA(26)` |
| `MACD_signal` | Signal Line | `EMA(MACD, 9)` |
| `MACD_hist` | MACD Histogram | `MACD − Signal` |
| `BB_upper/mid/lower` | Bollinger Bands | `SMA ± 2×STD` |
| `BB_pctB` | %B Bollinger | `(Close−Lower)/(Upper−Lower)` |
| `ATR` | Average True Range | `RollingMean(TrueRange, N)` |
| `ADX` | Average Directional Index | Wilder, 14 periods |
| `OBV` | On-Balance Volume | `cumsum(vol × direction)` |
| `Vol_MA` | Volume Moving Average | `rolling(N).mean()` |
| `Vol_ratio` | Volume Ratio | `Vol / Vol_MA` |
| `MFI` | Money Flow Index | `100 − 100/(1+MF+/MF-)` |
| `ROC` | Rate of Change | `(Close − Close_N) / Close_N` |
| `Manip_score` | Manipulation Score | Volume spike + price divergence |
| `CMF` | Chaikin Money Flow | `Σ(MFM×Vol)/Σ(Vol)` ★ |
| `ST` / `ST_dir` | SuperTrend | ATR-based dynamic support ★ |
| `Streak` | Ceiling/Floor Streak | Consecutive ±7% counter ★ |

★ = Chỉ số đặc thù VN, thêm mới phiên bản 14.0

### Chaikin Money Flow (CMF) — chi tiết

```
Money Flow Multiplier (MFM) = ((Close − Low) − (High − Close)) / (High − Low)

MFM = +1 nếu Close = High (mua áp đảo)
MFM = −1 nếu Close = Low  (bán áp đảo)
MFM = 0  nếu Close = Mid  (cân bằng)

CMF = Σ(MFM × Volume, N) / Σ(Volume, N)
```

**Đọc CMF:**
- CMF > +0.15: Dòng tiền tổ chức vào mạnh 
- CMF > +0.05: Dòng tiền vào
- CMF ≈ 0: Trung tính
- CMF < -0.05: Dòng tiền ra

### SuperTrend — chi tiết

```
Basic Upper Band = (High + Low) / 2 + multiplier × ATR
Basic Lower Band = (High + Low) / 2 − multiplier × ATR

Ratchet rule (quan trọng):
  - Upper Band chỉ có thể giảm (không được tăng khi trend bearish)
  - Lower Band chỉ có thể tăng (không được giảm khi trend bullish)

Đổi chiều:
  - Close < Lower Band → bearish (ST_dir = −1)
  - Close > Upper Band → bullish (ST_dir = +1)
```

**Tại sao dùng SuperTrend cho VN?**  
Thị trường VN có nhiều cổ phiếu nhỏ biến động mạnh, SuperTrend với ATR-based band tự điều chỉnh theo biến động thực tế tốt hơn MA đơn thuần.

### Ceiling/Floor Streak

```
Ngưỡng trần = Giá tham chiếu × 1.07 × 0.97 (3% tolerance)
Ngưỡng sàn = Giá tham chiếu × 0.93 × 1.03 (3% tolerance)

Streak = +N nếu N phiên liên tiếp chạm trần
Streak = −N nếu N phiên liên tiếp chạm sàn
Streak = 0  nếu phiên hiện tại bình thường
```

**Ý nghĩa trong đặc thù VN (biên độ ±7%):**
- **+2, +3 trần**: Cầu mua rất mạnh, lực mua bị dồn nén → tích cực
- **−2, −3 sàn**: Bán tháo / margin call liên tiếp → rất nguy hiểm

---

## 12. Stop-Loss và Target theo ATR

### Công thức

```
Stop Loss = Entry − (ATR × stop_atr_mult)
Risk      = Entry − Stop Loss
Target    = Entry + Risk × target_rr
```

### Hệ số theo khung thời gian

| Khung | stop_atr_mult | target_rr | Ý nghĩa |
|---|---|---|---|
| 1W | 1.0× | 1.5 | Tight stop, target nhỏ |
| 2W | 1.5× | 2.0 | Swing trade standard |
| 1M | 2.0× | 2.5 | Xu hướng trung hạn |
| 3M | 2.0× | 3.0 | Vị thế positional |
| 5M | 2.5× | 4.0 | Macro-driven, rộng rãi |

### Ví dụ thực tế

```
VCB, khung 1M:
  Entry = 82,000 VNĐ
  ATR(14) = 1,500 VNĐ
  
  Stop Loss = 82,000 − 1,500 × 2.0 = 79,000 VNĐ  (−3.7%)
  Risk      = 82,000 − 79,000 = 3,000 VNĐ
  Target    = 82,000 + 3,000 × 2.5 = 89,500 VNĐ  (+9.1%)
  R:R Ratio = 2.5 : 1
```

---

## 13. Phát hiện chế độ thị trường

### Hidden Markov Model (HMM)

Hệ thống dùng HMM 3 trạng thái để phân loại chế độ thị trường:

| Trạng thái | Đặc điểm | Chiến lược |
|---|---|---|
| **bull** | Return dương, volatility thấp | Mua theo xu hướng |
| **sideways** | Return gần 0, vol trung bình | Chọn lọc kỹ, mua hỗ trợ |
| **bear** | Return âm, vol cao | Không mua, bảo toàn vốn |

### MacroScore (0–10)

```
Mỗi thị trường thế giới đóng góp 0–1 điểm (dựa trên return gần nhất):
  Dương = +0.75–1.0 điểm
  Gần 0 = +0.25–0.5 điểm
  Âm    = 0 điểm

VN Breadth = Tỷ lệ mã tăng / tổng mã đang giao dịch
  > 60% = +1 điểm
  40–60% = +0.5 điểm
  < 40% = 0 điểm

Foreign Flow:
  Net mua nước ngoài = +1 điểm
  Net bán nước ngoài = −1 điểm

MacroScore = Tổng trên (capped ở 0–10)
```

---

## 14. Đặc thù thị trường VN

### Biên độ dao động ±7% (HoSE)

- **HoSE (Sàn TPHCM)**: ±7% mỗi phiên
- **HNX (Sàn Hà Nội)**: ±10%
- **UPCoM**: ±15%

Biên độ này ảnh hưởng trực tiếp đến:
- RSI zone scoring (VN stock ở 65–75 là bình thường)
- Ceiling/Floor Streak counter (đặc thù chỉ có ở VN)
- Stop-loss không được đặt quá gần (biến động 7% mỗi ngày)

### T+2 Settlement

Hiện tại (chuyển sang T+1 theo lộ trình SSC):
```
T = Ngày mua
T+2 = Ngày đủ điều kiện đóng vị thế theo số phiên giao dịch
```

Ảnh hưởng đến portfolio: ứng dụng chặn đóng vị thế cho đến khi cột `T+2 Ready` đạt trạng thái sẵn sàng.

### ~90% nhà đầu tư cá nhân

Hành vi đám đông mạnh hơn thị trường phát triển:
- RSI có thể duy trì > 70 nhiều tuần trong bull run
- Breakout có xu hướng kéo dài hơn
- Panic sell mạnh và nhanh hơn
- Ceiling/Floor streak phổ biến hơn

### 240 phiên giao dịch/năm

Ít hơn thị trường quốc tế (~252). Ảnh hưởng đến:
- CAGR annualization trong backtest
- Sharpe ratio calculation

---

## 15. Hỏi & Đáp

**Q: Tại sao STRONG BUY nhưng R:R chỉ 1.5?**  
A: Score cao = xác suất tín hiệu đúng cao. R:R thấp = khoảng cách stop/target không lý tưởng. Ưu tiên mã có cả Score cao lẫn R:R ≥ 2.0.

**Q: Macro Pulse không có dữ liệu?**  
A: Nhấn **"Cập nhật Macro"** trên sidebar. Dữ liệu từ Yahoo Finance có thể mất 5–10 giây do fetch song song 8 nguồn.

**Q: CMF âm nhưng Score vẫn cao?**  
A: CMF là 1 trong 5 điều kiện của thành phần Volume. Có thể các điều kiện khác (Vol ratio, MFI, Streak) đang bù đắp.

**Q: Tôi nên dùng khung thời gian nào?**  
A: Phụ thuộc vào horizon đầu tư của bạn. Ngắn hạn < 2 tuần → 1W/2W. Trung hạn 1–3 tháng → 1M/3M. Dài hạn > 3 tháng → 5M.

**Q: Dữ liệu được lấy từ đâu?**  
A: OHLCV từ **DNSE API** (primary) → **SSI API** (fallback). World markets từ **Yahoo chart API**. Breadth và foreign flow từ **KBS snapshot API**. Không cần tài khoản.

**Q: Tại sao có mã trong Scanner nhưng khi load lại không thấy?**  
A: Scanner sử dụng session-state cache. Nếu bạn thay đổi Universe/Macro, nhấn lại Tải Dữ Liệu để invalidate cache cũ.

---

*NewTradingOS v14.0 · Powered by Claude Sonnet 4.6 · Captain Seventh · 2026*
