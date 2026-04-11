# TradingOS — Tài Liệu Nghiệp Vụ (Business Logic Document)

> **Đối tượng đọc:** Người nắm yêu cầu nghiệp vụ, không cần hiểu code kỹ thuật.  
> **Phạm vi:** Toàn bộ luồng phân tích, bộ quy tắc ra quyết định, và ý nghĩa của từng đầu ra.  
> **Cập nhật lần cuối:** 2026-04-11

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc luồng phân tích (12 bước)](#2-kiến-trúc-luồng-phân-tích-12-bước)
3. [Lớp đo lường kỹ thuật — Indicators](#3-lớp-đo-lường-kỹ-thuật--indicators)
4. [Phân tích dòng tiền — Money Flow & SMS](#4-phân-tích-dòng-tiền--money-flow--sms)
5. [Phát hiện thao túng giá — AMF (Anti-Manipulation Filter)](#5-phát-hiện-thao-túng-giá--amf-anti-manipulation-filter)
6. [Nhận diện pha thị trường — AMD & HMM](#6-nhận-diện-pha-thị-trường--amd--hmm)
7. [Cảnh báo xu hướng — Trend Warning](#7-cảnh-báo-xu-hướng--trend-warning)
8. [Phân tích Gap & VWAP](#8-phân-tích-gap--vwap)
9. [Giao dịch T+2.5 — T+2.5 Entry Score](#9-giao-dịch-t25--t25-entry-score)
10. [Phân loại Setup T+ — T+ Engine](#10-phân-loại-setup-t--t-engine)
11. [Dự báo đa khung — Horizon Forecast](#11-dự-báo-đa-khung--horizon-forecast)
12. [Mô hình chấm điểm tổng hợp — MFPM](#12-mô-hình-chấm-điểm-tổng-hợp--mfpm)
13. [Tính xác suất thắng bằng Monte Carlo](#13-tính-xác-suất-thắng-bằng-monte-carlo)
14. [Môi trường vĩ mô & Rủi ro kết quả kinh doanh](#14-môi-trường-vĩ-mô--rủi-ro-kết-quả-kinh-doanh)
15. [Cỡ vị thế & Quản trị rủi ro](#15-cỡ-vị-thế--quản-trị-rủi-ro)
16. [Scanner — Quét toàn sàn](#16-scanner--quét-toàn-sàn)
17. [Profiler — Hồ sơ chi tiết một mã](#17-profiler--hồ-sơ-chi-tiết-một-mã)
18. [Bảng quy tắc tổng hợp (Truth Table)](#18-bảng-quy-tắc-tổng-hợp-truth-table)
19. [Cấu trúc đầu ra](#19-cấu-trúc-đầu-ra)
20. [Giới hạn & Tuyên bố miễn trách](#20-giới-hạn--tuyên-bố-miễn-trách)

---

## 1. Tổng quan hệ thống

**TradingOS** là hệ thống tư vấn giao dịch cổ phiếu thị trường Việt Nam (HOSE, HNX).  
Hệ thống **không đặt lệnh tự động** — mọi đầu ra đều là **khuyến nghị** để con người ra quyết định cuối cùng.

### Bài toán nghiệp vụ cốt lõi

> "Với một mã cổ phiếu bất kỳ tại thời điểm hiện tại, hệ thống phải trả lời 5 câu hỏi:"

| # | Câu hỏi | Đầu ra tương ứng |
|---|---|---|
| 1 | Nên mua, giữ hay bán? | Tín hiệu hành động (Action) |
| 2 | Độ tin cậy tín hiệu cao hay thấp? | Mức tin cậy (Confidence) |
| 3 | Vào giá bao nhiêu? Cắt lỗ ở đâu? Target giá nào? | Entry / SL / TP1 / TP2 |
| 4 | Tại sao hệ thống đưa ra kết luận đó? | Lý do phân tích (bằng tiếng Việt) |
| 5 | Nền tảng nào tốt nhất để thực hiện giao dịch T+2.5? | Khuyến nghị T+ Setup & phiên giao dịch |

### Nguyên tắc thiết kế

- **Đa yếu tố:** Không một chỉ báo đơn lẻ nào ra quyết định. Mọi tín hiệu đều được tổng hợp.
- **Bảo vệ vốn trước:** Tín hiệu phân phối / thao túng luôn ghi đè tín hiệu mua.
- **Phù hợp luật T+3 Việt Nam:** Mọi khuyến nghị được thiết kế cho chu kỳ thanh toán T+3, tập trung vào điểm thoát T+2.5 (ATC ngày T+2).
- **Minh bạch lý do:** Mọi quyết định đều có giải thích rõ ràng bằng tiếng Việt.

---

## 2. Kiến trúc luồng phân tích (12 bước)

Khi người dùng tra cứu một mã cổ phiếu, hệ thống chạy tuần tự 12 bước sau:

```
┌─────────────────────────────────────────────────────────────┐
│  Bước 1 │ Lấy dữ liệu OHLCV (tối đa 1.000 ngày) + giá RT  │
│  Bước 2 │ Tính toán chỉ báo kỹ thuật (SMA, EMA, RSI, ...)  │
│  Bước 3 │ Kiểm tra thao túng giá (AMF)                      │
│  Bước 4 │ Phân tích dòng tiền (Whale / SMS / Phân phối)     │
│  Bước 5 │ Nhận dạng mô hình nến + Gap + VWAP + T+2.5 Score │
│      5b │ Phân loại Setup T+ (T_BREAKOUT, T_PULLBACK, ...)  │
│  Bước 6 │ Phân tích pha thị trường (AMD/HMM) + vĩ mô       │
│      6b │ Rủi ro kết quả KQKD + điểm cơ bản (Fundamental)  │
│      6c │ Dự báo đa khung (Short / Mid / Long)              │
│  Bước 7 │ Chấm điểm tổng hợp MFPM → Action + Confidence    │
│  Bước 8 │ Tính cỡ vị thế (Position Sizing)                  │
│  Bước 9 │ Tư vấn phiên giao dịch (ATO/Sáng/ATC...)         │
│ Bước 10 │ Tạo nội dung NLP tiếng Việt                       │
│ Bước 11 │ Tổng hợp hồ sơ TickerProfile (~90 trường dữ liệu) │
│ Bước 12 │ Ghi log kiểm toán                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Lớp đo lường kỹ thuật — Indicators

Đây là lớp nền tảng. Mọi dữ liệu thô từ sàn đều được chuyển hóa thành các chỉ số đo lường chuẩn.

### 3.1 Đường trung bình (Moving Averages)

| Chỉ số | Ý nghĩa nghiệp vụ |
|---|---|
| **SMA 3, 5, 7, 10 ngày** | Xu hướng siêu ngắn hạn — dùng cho tín hiệu scalping T+1 |
| **SMA 20 ngày** | Đường trung bình tháng — mức hỗ trợ/kháng cự quan trọng nhất |
| **SMA 50 ngày** | Xu hướng trung hạn (2–3 tháng) |
| **SMA 200 ngày** | Xu hướng dài hạn — ranh giới bull/bear tổng thể |
| **EMA 9, 21 ngày** | Đường nhanh hơn SMA, phản ứng sớm — dùng cho T+ pullback |
| **EMA 50, 200 ngày** | Phiên bản nhạy hơn SMA50/200 |

**Quy tắc xếp chồng (MA Alignment):**
- `Giá > EMA9 > EMA21 > SMA50 > SMA200` = trạng thái tăng hoàn hảo
- `Giá < SMA20 < SMA50 < SMA200` = trạng thái giảm — không mua

### 3.2 Chỉ báo động lượng

| Chỉ số | Ngưỡng nghiệp vụ | Tín hiệu |
|---|---|---|
| **RSI 14 ngày** | < 35 = quá bán; > 70 = quá mua | Phản chiều khi ở cực |
| **MACD (Histogram)** | Cắt từ âm sang dương | Momentum tích cực |
| **Stochastic %K/%D** | %K cắt %D lên khi < 40 | Golden cross = mua |
| **Williams %R** | < −80 = quá bán; > −20 = quá mua | Tương tự Stochastic |
| **CCI** | > +100 = breakout; < −100 = oversold | Xác nhận đột phá |
| **ADX / DI+/DI−** | ADX > 25: xu hướng mạnh; DI+ > DI− = tăng | Đo sức mạnh xu hướng |

### 3.3 Khối lượng & Biến động

| Chỉ số | Ý nghĩa |
|---|---|
| **ATR 14 ngày** | Biên độ dao động trung bình mỗi ngày → dùng đặt SL/TP |
| **OBV** | Tổng khối lượng tích lũy theo chiều giá → tổ chức đang mua hay bán? |
| **Z-Volume** | Khối lượng hôm nay nằm bao nhiêu độ lệch chuẩn so với bình thường; Z > 2 = bất thường |
| **OFI** | Ước tính áp lực mua/bán từ OHLCV; dương = mua ròng |
| **Bollinger Bands** (20d, 2σ) | Kênh giá. Dải hẹp = tích lũy năng lượng. Chạm dải dưới = hỗ trợ. |
| **Hurst Exponent** | > 0.5: thị trường xu hướng. < 0.5: thị trường hồi quy trung bình. |

---

## 4. Phân tích dòng tiền — Money Flow & SMS

### Bài toán nghiệp vụ

> "Tổ chức / cá voi đang mua hay đang bán mã này?"

Thị trường Việt Nam không công bố dữ liệu dòng tiền tổ chức theo thời gian thực. Hệ thống ước tính bằng hai cách:
- **Proxy từ OHLCV:** Ngày có khối lượng lớn & đóng cửa cao = cá voi mua; đóng thấp = cá voi bán.
- **Giao dịch thỏa thuận (Put-Through):** Nếu có dữ liệu thực tế từ SSI, dùng thay thế proxy.

### 4.1 M-CVD (Multi-day Cumulative Volume Delta)

Theo dõi tổng dòng tiền ước tính của cá voi trong **5 ngày** và **20 ngày** gần nhất.

| M-CVD | Ý nghĩa |
|---|---|
| `mcvd_5d > 0` | Cá voi mua ròng trong tuần qua |
| `mcvd_20d > 0, trend = UP` | Tổ chức tích lũy bền vững trong tháng qua |
| `mcvd_vs_price = DIVERGE_BULLISH` | **Tín hiệu mạnh nhất:** Cá voi mua khi giá giảm = tích lũy ẩn |
| `mcvd_vs_price = DIVERGE_BEARISH` | **Cảnh báo đỏ:** Cá voi bán khi giá tăng = phân phối |

### 4.2 SMS — Smart Money Score (0–100)

Điểm tổng hợp đo lường mức độ tham gia của "smart money":

| Thành phần | Điểm tối đa | Nội dung đo |
|---|---|---|
| M-CVD Trend | 20 điểm | Tổ chức có mua ổn định không? |
| Chất lượng khối lượng (VQS) | 15 điểm | Khối lượng có tự nhiên hay bị làm giả? |
| Dòng tiền nước ngoài (5 ngày) | 15 điểm | Quỹ ngoại đang mua hay bán? |
| Độ dốc OBV | 15 điểm | Tích lũy OBV có đang tăng không? |
| Pha AMD | 10 điểm | Mã đang ở pha tích lũy/markup hay phân phối? |
| CVD trong phiên | 10 điểm | Áp lực mua/bán trong phiên hôm nay |
| Lô thỏa thuận (PT Deals) | 15 điểm | Bằng chứng giao dịch tổ chức trực tiếp |

**SMS Labels (nhãn kết luận):**

| Nhãn | Ý nghĩa | Ảnh hưởng lên tín hiệu |
|---|---|---|
| `WHALE_BUYING` | Tổ chức đang tích lũy | Tăng mạnh Action |
| `WHALE_DISTRIBUTING` | Tổ chức đang thoát hàng | Hạ xuống NO_ACTION |
| `MIXED` | Tín hiệu trái chiều | Giảm Confidence |
| `RETAIL_DRIVEN` | Không có dấu ấn tổ chức | Thông thường |

### 4.3 Tích lũy ẩn (Stealth Accumulation)

Phát hiện khi tổ chức mua **lặng lẽ** — chia nhỏ giao dịch, giá đi ngang hoặc hơi giảm, nhưng OBV tăng đều. Đây là tín hiệu **rất có giá trị** vì chỉ xuất hiện trước các đợt tăng lớn.

### 4.4 Cảnh báo phân phối (Distribution Warning)

Hệ thống theo dõi liên tục dấu hiệu tổ chức "xả hàng":

| Mức | Ý nghĩa | Hành động bắt buộc |
|---|---|---|
| `NONE` | Bình thường | Không tác động |
| `WATCH` | Bắt đầu có dấu hiệu phân phối | Thêm vào danh sách theo dõi |
| `CAUTION` | Phân phối rõ ràng hơn | Xem xét thu hẹp vị thế |
| `EXIT` | Tổ chức đang thoát mạnh | **Bán (EXIT)** — ghi đè mọi tín hiệu mua |
| `FORCED_EXIT` | Kết hợp phân phối + thao túng | **Bán ngay (FORCED_EXIT)** |

> ⚠️ **Quy tắc cứng:** `EXIT` hoặc `FORCED_EXIT` **luôn ghi đè** mọi tín hiệu mua, bất kể MFPM score là bao nhiêu.

---

## 5. Phát hiện thao túng giá — AMF (Anti-Manipulation Filter)

### Mục tiêu

Phát hiện các mã đang bị **làm giá** (pump-and-dump, wash trading) để bảo vệ người dùng.

### Quy trình

Hệ thống kiểm tra các dấu hiệu bất thường trong pattern OHLCV:
- Khối lượng cao bất thường nhưng biên độ giá hẹp bất thường (wash trading)
- Giá tăng/giảm quá mạnh mà không có tin tức tương ứng
- Các dấu hiệu thao túng intraday

### Kết quả (AMF Decision)

| Quyết định | Ý nghĩa | Tác động |
|---|---|---|
| `PASS` | Không phát hiện thao túng | Không tác động |
| `WATCH` | Có một vài bất thường nhỏ | Giảm Confidence |
| `BLOCK` | Phát hiện điều bất thường rõ ràng | **Cấm BUY** — chỉ cho phép EXIT |

> ⚠️ **Quy tắc cứng:** `AMF BLOCK` = tự động **NO_ACTION** hoặc **FORCED_EXIT** (nếu kết hợp với phân phối).

---

## 6. Nhận diện pha thị trường — AMD & HMM

### 6.1 Pha Wyckoff (AMD — Accumulation/Markup/Distribution/Markdown)

Mô tả trạng thái hiện tại của mã trong chu kỳ lớn tổ chức (Richard Wyckoff):

| Pha | Mô tả | Khuyến nghị |
|---|---|---|
| `ACCUMULATION` | Tổ chức đang thu gom hàng lặng lẽ. Giá đi ngang / hơi giảm. | ✅ Tốt để mua |
| `MARKUP` | Giá bắt đầu tăng mạnh. Đám đông bắt đầu nhận ra. | ✅ Cơ hội tốt nhất |
| `DISTRIBUTION` | Tổ chức âm thầm bán. Giá vẫn cao nhưng OBV giảm. | ⛔ Không mua |
| `MARKDOWN` | Giá giảm rõ rệt. Tổ chức đã thoát xong. | ⛔ Tránh xa |

### 6.2 Chế độ HMM (Hidden Markov Model)

Mô hình thống kê phân loại trạng thái ẩn của thị trường:

| Trạng thái | Ý nghĩa |
|---|---|
| `STEADY_BULL` | Chế độ tăng ổn định |
| `TRANSITIONAL` | Đang chuyển tiếp (rủi ro cao hơn) |
| `STEADY_BEAR` | Chế độ giảm ổn định |

HMM là đầu vào cho MFPM — trong `STEADY_BEAR`, ngưỡng vào mua được nâng cao hơn.

---

## 7. Cảnh báo xu hướng — Trend Warning

### Mục tiêu

Phân loại **cấu trúc xu hướng hiện tại** của mã, độc lập với tín hiệu mua/bán.

### 10 trạng thái cảnh báo

| Cảnh báo | Ý nghĩa |
|---|---|
| `UPTREND_STRENGTHENING` | Tăng mạnh hơn — môi trường mua tốt |
| `UPTREND_EXHAUSTING` | Tăng đang mệt — RSI cao, MACD giảm, OBV suy — cẩn thận |
| `DOWNTREND_STRENGTHENING` | Giảm mạnh hơn — tránh mua |
| `DOWNTREND_EXHAUSTING` | Giảm có thể sắp kết thúc — theo dõi đảo chiều |
| `RANGE_COMPRESSION` | Giá đi ngang + Bollinger hẹp — đang tích lũy năng lượng |
| `BREAKOUT_EMERGING` | BB nén + KL bứt phá — chuẩn bị theo dõi hướng |
| `DIVERGENCE_BULLISH` | Giá giảm nhưng RSI/OBV tăng — tín hiệu đảo chiều tăng sớm |
| `DIVERGENCE_BEARISH` | Giá tăng nhưng RSI/OBV giảm — tín hiệu đảo chiều giảm |
| `REVERSAL_WARNING_LOW_CONF` | 1–2 tín hiệu đảo chiều — chưa rõ ràng |
| `REVERSAL_WARNING_CONFIRMED` | ≥ 3 tín hiệu đảo chiều đồng nhất — cảnh báo thực sự |

Mỗi cảnh báo kèm theo:
- **Độ tin cậy (confidence):** 0–100%
- **Danh sách lý do** bằng tiếng Việt (tối đa 5 lý do)

---

## 8. Phân tích Gap & VWAP

### 8.1 Gap (Khoảng trống giá)

| Loại Gap | Điều kiện | Ý nghĩa |
|---|---|---|
| `GAP_UP` | Mở cửa > giá đóng hôm trước × 1.005 | Momentum mua mạnh qua đêm |
| `GAP_DOWN` | Mở cửa < giá đóng hôm trước × 0.995 | Áp lực bán qua đêm |
| `NO_GAP` | Trong phạm vi ±0.5% | Bình thường |

Hệ thống cũng tính **tỷ lệ lấp gap lịch sử** — mã này có xu hướng lấp gap sau bao nhiêu ngày?

### 8.2 VWAP (Giá trung bình theo khối lượng)

| Vị trí giá so với VWAP | Ý nghĩa |
|---|---|
| `ABOVE` (> +0.5%) | Giá đang trên vùng giá trị — bullish nhưng chú ý hồi về |
| `BELOW` (< −0.5%) | Giá dưới vùng giá trị — vùng value hoặc xu hướng yếu |
| `AT` | Giá tại vùng cân bằng |

**VWAP trong phiên (intraday 5 phút):** Khi giá trên VWAP trong phiên = người mua đang kiểm soát phiên đó. Độ dốc VWAP cho biết xu hướng phiên đang tăng/giảm.

### 8.3 Pivot & Fibonacci

- **Monthly Pivot Points (PP, R1, R2, S1, S2):** Vùng hỗ trợ/kháng cự từ 20 ngày qua — dùng trong T+2.5 score
- **Fibonacci 61.8%:** Vùng hồi lý tưởng — giá hồi 61.8% từ đỉnh gần nhất = cơ hội mua pullback chất lượng cao

---

## 9. Giao dịch T+2.5 — T+2.5 Entry Score

### Bối cảnh nghiệp vụ

> Thị trường Việt Nam áp dụng thanh toán T+3. Người mua hôm nay (T+0) chỉ có thể bán sớm nhất vào T+2. Điểm thoát lệnh tối ưu là **ATC ngày T+2 (14:43–14:45)** — gọi là "T+2.5".

Module này đánh giá **mức độ phù hợp để vào lệnh mới** với mục tiêu thoát T+2.5.

### 9.1 Điểm vào (Entry Score: 0–100)

Ba nhóm tín hiệu (tổng 50 đầu vào):

| Nhóm | Điểm tối đa | Nội dung |
|---|---|---|
| **A — Momentum** | 20 điểm | MACD slope, RSI recovery, volume surge, Stoch cross, Williams %R, CCI |
| **B — Cấu trúc** | 20 điểm | MA alignment, vị trí vs SMA200, hồi về SMA20, Fibonacci/Pivot support, ADX |
| **C — Xác nhận** | 10 điểm | Mô hình nến, phân kỳ RSI, chế độ thị trường |

**Trọng số thay đổi theo chế độ:**

| Chế độ | Nhóm A | Nhóm B | Nhóm C |
|---|---|---|---|
| Bull trend | 35% | 40% | 25% |
| Sideways | 45% | 35% | 20% |
| Bear trend | 30% | 35% | 35% |

### 9.2 Tín hiệu vào lệnh

| Tín hiệu | Ngưỡng | Ý nghĩa |
|---|---|---|
| `T25_BUY` | ≥ 68 điểm (≥ 74.8 trong bear market) | Vào lệnh T+2.5 |
| `T25_WATCH` | ≥ 55 điểm | Theo dõi phiên tiếp |
| `T25_NEUTRAL` | Trung gian | Chờ thêm tín hiệu |
| `T25_AVOID` | ≤ 28-32 điểm | Không vào T+2.5 |

### 9.3 Tư vấn thoát lệnh (cho vị thế đang nắm)

| Điều kiện | Hành động |
|---|---|
| Distribution = EXIT/FORCED_EXIT | ⚠️ Bán 100% ngay tại ATC — ưu tiên KHẨN |
| Giá ≤ Stop Loss | ⚠️ Bán 100% ngay tại ATC — ưu tiên KHẨN |
| Giá ≥ TP2 (mục tiêu đầy đủ) | Bán 100% tại ATC |
| Giá ≥ TP1 VÀ đã nắm ≥ 3 ngày | Bán 40% — chốt một phần, giữ phần còn lại |
| Đã nắm ≥ 15 ngày (giới hạn tối đa) | Thoát toàn bộ vị thế |
| RSI > 80 và khối lượng > 2.5× bình thường | Bán 40% — dấu hiệu blowoff top |
| Các trường hợp khác | HOLD |

### 9.4 Phân tích đa khung (T+2.5 Multi-Frame)

Cho điểm 3 cửa sổ thời gian trong ngày:

| Cửa sổ | Thời điểm | Khi nào dùng |
|---|---|---|
| **Morning (Sáng)** | 9:15–11:30 | Momentum cao, phù hợp Breakout / Pullback |
| **Midday (Trưa)** | 12:45–13:15 | Cửa sổ T+2.5 thực sự — thanh toán lệnh trưa |
| **Afternoon (Chiều)** | 13:00–14:30 | Vào cuối phiên — Hồi từ hỗ trợ / Support Bounce |

---

## 10. Phân loại Setup T+ — T+ Engine

### Mục tiêu

> "Mã này đang hình thành loại cơ hội T+ nào? Có nên vào lệnh không?"

### 10.1 8 loại Setup T+

| Setup | Điều kiện phát hiện | Ý nghĩa |
|---|---|---|
| `T_BREAKOUT` | Giá > kháng cự gần nhất + KL > 1.5× trung bình + RSI 50–70 + MACD tăng | Bứt phá kháng cự — momentum cao |
| `T_PULLBACK_EMA` | Giá trong vùng EMA9–EMA21 + OBV ổn định + giá trên SMA50/200 | Hồi về EMA trong uptrend — tiếp diễn |
| `T_SUPPORT_BOUNCE` | Giá tại SMA20 ±1.5% hoặc SMA50 ±1.5% hoặc BB dưới + RSI 35–52 + MACD bẻ gãy | Bật lên từ hỗ trợ kỹ thuật |
| `T_OVERSOLD_RECOVERY` | RSI < 40 + Stoch golden cross < 30 + MACD_hist bẻ cong lên + KL tăng ngày phục hồi | Phục hồi từ vùng quá bán |
| `T_RANGE_BREAK` | BB width < 75% trung bình 20 ngày + KL bứt phá + ADX đang tăng | BB nén bứt phá — sắp có biến động lớn |
| `T_MOMENTUM_CONT` | ADX > 30 + DI+ > DI− + xếp chồng MA hoàn hảo + OBV tăng | Tiếp diễn xu hướng mạnh |
| `T_NO_SETUP` | Không đủ điều kiện cho setup nào | Chưa có cơ hội T+ rõ ràng |
| `T_AVOID` | Distribution = EXIT/BLOCK, AMF = BLOCK, AMD = DISTRIBUTION/MARKDOWN, hoặc RSI > 82 | Không giao dịch T+ |

Mỗi setup được **chấm điểm 0–10**. Setup có điểm cao nhất được chọn. Ngưỡng tối thiểu để được coi là setup hợp lệ là **3.0 điểm**.

### 10.2 Phán quyết T+ (Verdict)

| Phán quyết | Điều kiện | Ý nghĩa |
|---|---|---|
| `MUA_NGAY` | Điểm ≥ 7.5 + T25_BUY / Điểm ≥ 5.5 + T25_BUY | Hành động ngay khi trigger xác nhận |
| `CHO_XAC_NHAN` | Điểm ≥ 5.5 (nhưng T25 không phải BUY) | Chờ nến xác nhận phiên tiếp |
| `THEO_DOI` | Điểm ≥ 3.0 | Đưa vào watchlist — chưa hành động |
| `TRANH_XA` | Điểm < 3.0 hoặc T_AVOID | Tránh hoàn toàn |

**Quy tắc R:R:** Nếu tỷ lệ Reward:Risk < 1.2, tự động hạ từ `MUA_NGAY` xuống `CHO_XAC_NHAN`.

### 10.3 Các tham số giao dịch được tạo ra

| Tham số | Cách tính | Ý nghĩa |
|---|---|---|
| **Vùng vào lệnh (Entry Zone)** | Close ± ATR × 0.1–0.3 (tùy setup) | Vùng giá lý tưởng để đặt lệnh |
| **Mục tiêu T+2.5** | Entry + ATR × 1.5–2.0 (tùy setup) | Giá chốt lời tại ATC ngày T+2 |
| **Mục tiêu T+5** | Entry + ATR × 2.5–3.5 | Giá chốt nếu giữ dài hơn |
| **Stop Loss** | Entry − ATR × 0.8–1.1 + Floor SL từ BB dưới | Không được thấp hơn BB dưới hoặc hỗ trợ gần nhất |
| **Phiên vào lệnh** | Tùy setup (xem bảng bên dưới) | Khi nào trong ngày nên vào |

**Lịch trình phiên theo setup:**

| Setup | Phiên tốt nhất |
|---|---|
| T_BREAKOUT, T_RANGE_BREAK | Sáng (9:30–11:00) — bắt kịp momentum |
| T_PULLBACK_EMA, T_SUPPORT_BOUNCE | Sáng — xác nhận hỗ trợ giữ vững |
| T_OVERSOLD_RECOVERY | Trưa (12:45–13:30) — chờ ổn định trước khi vào |
| T_MOMENTUM_CONT | Sáng — cưỡi sóng momentum |

---

## 11. Dự báo đa khung — Horizon Forecast

### 3 khung dự báo

**Ngắn hạn (3–5 phiên)** — dùng: RSI, MACD hist, Stochastic cross, Bollinger, volume, Gap type
**Trung hạn (~1 tháng)** — dùng: MA stack, ADX, HMM state, AMD phase, Macro regime, Fundamental score
**Dài hạn (3–6 tháng)** — dùng: SMA200 slope, Fundamental score, Earnings growth, Macro regime

Mỗi khung trả về:
- **Vote:** `TĂNG` / `GIẢM` / `TRUNG LẬP`
- **Độ tin cậy:** 5%–95%
- **5 lý do hàng đầu** (tiếng Việt)

### Tổng hợp Overall Vote

| Phân bổ trọng số | Tỷ lệ |
|---|---|
| Ngắn hạn | 40% |
| Trung hạn | 40% |
| Dài hạn | 20% |

**Giới hạn độ tin cậy:** Nếu ngắn hạn và dài hạn **trái chiều**, độ tin cậy Overall bị **giới hạn tối đa 55%** (tránh đưa ra kết luận mạnh khi thị trường mâu thuẫn).

---

## 12. Mô hình chấm điểm tổng hợp — MFPM

**MFPM (Multi-Factor Portfolio Model)** là bộ não ra quyết định cuối cùng. Nó tổng hợp tất cả các tín hiệu trên thành một Action duy nhất.

### 12.1 Ba chế độ vào lệnh (Signal Mode)

**Mode A — Pullback Entry (tối đa 60 điểm)**

Điều kiện lý tưởng:
- RSI vừa cắt lên qua 50 (momentum chuyển tích cực)
- Giá gần SMA20 (vùng hỗ trợ tự nhiên)
- Giá vẫn trên SMA50 (uptrend trung hạn còn nguyên)
- Khối lượng xác nhận

→ Đây là chiến thuật **mua pullback** trong xu hướng tăng.

**Mode B — Breakout Entry (tối đa 60 điểm)**

Điều kiện lý tưởng:
- Giá vượt đỉnh pivot gần nhất
- Khối lượng bứt phá (> 1.5× trung bình)
- ATR mở rộng (biến động tăng)
- RSI trong vùng breakout (55–75)

Bổ sung: **"Second Mouse Gate"** — nếu giá đã bứt phá và đang **retest** vùng breakout cũ, thưởng thêm 15 điểm (đây là cách mua an toàn hơn, không phải bắt breakout đầu tiên).

**Mode W — Follow-The-Whale (tối đa 115 điểm)**

Chế độ có điểm cao nhất, nhưng yêu cầu **tất cả 7 điều kiện cá voi** phải đạt:

| Điều kiện | Nội dung |
|---|---|
| W-1 | SMS score ≥ ngưỡng cơ sở (60) |
| W-2 | Dòng tiền cá voi dậy được xu hướng (≥ 55% các ngày trong 20 ngày qua) |
| W-3 | AMF = PASS (không bị chặn vì thao túng) |
| W-4 | HMM không phải STEADY_BEAR |
| W-5 | AMD pha là Accumulation hoặc Markup |
| W-6 | Có stealth accumulation HOẶC intraday buying dương |
| W-7 | Sector không có net outflow |

Nếu **một điều kiện nào thất bại**, Mode W không kích hoạt.

### 12.2 Điểm điều chỉnh thêm

Sau khi có điểm mode, các điều chỉnh sau được áp dụng:

| Điều chỉnh | Giá trị | Điều kiện |
|---|---|---|
| **Bonus SMS** | +20 điểm | SMS ≥ 75 |
| **Penalty SMS** | −10 điểm | SMS < 20 |
| **Bonus Fundamental** | +12 điểm | Fundamental score ≥ 80 |
| **Penalty Fundamental** | −10 điểm | Fundamental score < 40 |
| **Bonus Pattern** | +5 đến +15 điểm | Tùy loại mô hình nến |
| **Cộng Macro** | +5 điểm | Môi trường vĩ mô hỗ trợ |
| **Trừ Macro** | −10 điểm | Môi trường vĩ mô thắt chặt |
| **Cộng Earnings** | +0 điểm | Không có rủi ro KQKD |
| **Trừ Earnings** | −5 đến −15 điểm | Có KQKD quan trọng sắp công bố |

### 12.3 Bảng quy tắc Action (Decision Table)

| Điều kiện | Action | Ưu tiên |
|---|---|---|
| Distribution = FORCED_EXIT hoặc AMF BLOCK + Distribution | `FORCED_EXIT` | 1 (cao nhất) |
| Distribution = EXIT | `EXIT` | 2 |
| Mode W: Score ≥ 95 + STEADY_BULL + MC ≥ 60% | `STRONG_BUY` | 3 |
| Mode W: Score ≥ 80 | `BUY` | 4 |
| Mode A/B: MFPM ≥ 70 + AMF PASS + MC ≥ 55% | `BUY` | 5 |
| MFPM ≥ 50 | `WATCH` | 6 |
| SMS label = WHALE_DISTRIBUTING | WATCH → `NO_ACTION` | 7 |
| Các trường hợp còn lại | `NO_ACTION` | 8 (thấp nhất) |

### 12.4 Mức độ tin cậy (Confidence)

| Mức | Ý nghĩa | Yêu cầu |
|---|---|---|
| `HIGH` | Tín hiệu mạnh, nhiều yếu tố đồng thuận | Mode W hoặc MFPM ≥ 80 + real data |
| `MEDIUM` | Tín hiệu tốt nhưng một số yếu tố chưa rõ | MFPM 60–79 |
| `LOW` | Tín hiệu yếu hoặc dữ liệu không đầy đủ | Dùng proxy OHLCV thay real flow data |

**Tự động hạ Confidence:** Nếu dùng dữ liệu proxy ước tính (không có real institutional flow data), Confidence bị hạ **một bậc**.

---

## 13. Tính xác suất thắng bằng Monte Carlo

### Mục tiêu

> "Nếu tôi vào lệnh ngay bây giờ, xác suất giá chạm TP1 trước khi chạm SL trong 10 ngày tới là bao nhiêu?"

### Phương pháp

1. Hệ thống lấy **500 mẫu biến động giá lịch sử thực tế** của mã đó (không dùng phân phối chuẩn)
2. Mỗi mẫu mô phỏng một "kịch bản" 10 ngày từ giá hiện tại
3. Đếm số kịch bản chạm TP1 trước SL → đó là **Win Probability**

### Yêu cầu để BUY

| Action | Win Probability tối thiểu |
|---|---|
| `BUY` | ≥ 55% |
| `STRONG_BUY` | ≥ 60% |

Nếu Win Probability không đạt ngưỡng, Action bị hạ xuống `WATCH` dù điểm MFPM cao.

---

## 14. Môi trường vĩ mô & Rủi ro kết quả kinh doanh

### 14.1 Macro Regime (Chế độ vĩ mô)

Hệ thống phân tích 3 nguồn dữ liệu vĩ mô:
- **Tỷ giá USD/VND** (30–60 ngày)
- **Lợi suất trái phiếu chính phủ 10 năm (VN10Y)**
- **Thanh khoản OMO của NHNN** (bơm/hút tiền)

Kết quả phân loại vĩ mô:

| Regime | Điều kiện | Tác động lên ngưỡng |
|---|---|---|
| `ACCOMMODATIVE` | Lãi suất giảm, VND ổn định, NHNN bơm tiền | Hạ ngưỡng BUY (dễ mua hơn) |
| `NEUTRAL` | Bình thường | Không thay đổi |
| `RESTRICTIVE` | Lãi suất tăng, VND mất giá mạnh, NHNN hút tiền | Nâng ngưỡng BUY (khó mua hơn) |

### 14.2 Rủi ro kết quả kinh doanh (Earnings Risk)

Hệ thống được kết quả phải công bố trong **30 ngày tới**:

| Ngưỡng | Mức rủi ro | Điểm MFPM bị trừ |
|---|---|---|
| > 30 ngày hoặc không có lịch | `SAFE` | 0 |
| 15–30 ngày | `MODERATE` | −5 điểm |
| 7–15 ngày | `HIGH` | −10 điểm |
| < 7 ngày | `CRITICAL` | −15 điểm |

> **Lý do:** Trước ngày công bố kết quả kinh doanh, biến động giá khó dự đoán hơn và cần yêu cầu tín hiệu chắc chắn hơn để vào lệnh.

---

## 15. Cỡ vị thế & Quản trị rủi ro

### Phương pháp tính

Hệ thống dùng **Kelly Criterion** (phân số Kelly) để tính % vốn nên đặt vào mỗi lệnh:

```
Kelly = (Win_Rate × (Avg_Win / Avg_Loss) - (1 - Win_Rate)) / (Avg_Win / Avg_Loss)
Fractional Kelly = Kelly × 0.5  (dùng nửa Kelly để giảm rủi ro)
```

### Điều chỉnh thêm

| Yếu tố điều chỉnh | Tác động |
|---|---|
| **Macro Multiplier** | Vĩ mô restrictive: giảm cỡ vị thế. Accommodative: giữ nguyên hoặc tăng nhẹ. |
| **Win Probability** | < 55%: loại bỏ. 55–60%: cỡ nhỏ. > 70%: cỡ chuẩn. |
| **ATR Risk Cap** | SL × cỡ vị thế không vượt quá 2% tổng vốn |

Đầu ra: **% vốn** và **số cổ phiếu cụ thể** dựa trên vốn tài khoản người dùng nhập.

---

## 16. Scanner — Quét toàn sàn

### Luồng hoạt động

```
1. Chọn sàn (HOSE, HNX, hoặc cả hai) → lấy danh sách ~500–1.500 mã
2. Tính Macro Regime một lần (dùng chung cho tất cả mã)
3. Chạy song song phân tích cho từng mã (tối đa 4 mã cùng lúc)
   - Timeout 60 giây/mã
   - Các bước: OHLCV → Indicators → AMF → Money Flow → Patterns → MFPM → T+ Setup
4. Gom kết quả → lọc theo filter người dùng → sắp xếp
```

### Các bộ lọc người dùng

| Bộ lọc | Mặc định | Ý nghĩa |
|---|---|---|
| Sàn (Exchange) | HOSE | Quét HOSE, HNX, hoặc cả hai |
| Action tối thiểu | Hiển thị tất cả | Chỉ hiện BUY trở lên, hoặc tất cả |
| MFPM tối thiểu | 0 | Lọc theo điểm tổng hợp |
| SMS tối thiểu | 0 | Lọc theo điểm smart money |
| Stealth Only | Tắt | Chỉ hiện mã có tích lũy ẩn |
| Bao gồm AMF Blocked | Có | Ẩn/hiện mã bị gắn cờ thao túng |
| Giới hạn kết quả | 2.000 mã | Số mã tối đa hiển thị |

### Sắp xếp kết quả

```
1. STRONG_BUY
2. BUY
3. WATCH
4. NO_ACTION
5. EXIT
6. FORCED_EXIT
Trong mỗi nhóm → sắp xếp theo MFPM score từ cao xuống thấp
```

### Các cột hiển thị trong bảng scanner

`Mã | Action | Conf | MFPM | Macro | Sector | BCTC | W-Score | SMS | Mode | Giá | Vào | SL | TP1 | R:R | AMF | Pattern | HMM | Stealth | T+ Setup | T+ Verdict | T+ Conf | Tóm tắt NLP`

---

## 17. Profiler — Hồ sơ chi tiết một mã

Khi tra cứu một mã cụ thể, hệ thống hiển thị 11 tab phân tích:

| Tab | Nội dung |
|---|---|
| **📋 Horizon** | Bảng kế hoạch giao dịch theo thời gian (2d/3d/5d/7d/10d/15d): Action, Entry, SL, TP1, TP2 |
| **📊 SMS / M-CVD** | Biểu đồ dòng tiền cá voi, điểm SMS, M-CVD, phân kỳ giá-flow |
| **🔬 SHAP** | Đóng góp của từng yếu tố vào điểm MFPM (phân tích nguyên nhân tín hiệu) |
| **🧭 Overlay** | Biểu đồ nến với các đường MA, Bollinger, VWAP overlay |
| **📈 Chỉ số** | Bảng giá trị tất cả chỉ báo kỹ thuật |
| **📝 NLP Insights** | Phân tích toàn diện viết bằng ngôn ngữ tự nhiên tiếng Việt |
| **🔰 Giải thích F0** | Giải thích đơn giản dành cho nhà đầu tư mới |
| **⚡ T+2.5** | Điểm T+2.5, tín hiệu, phân tích 3 phiên (sáng/trưa/chiều) |
| **⚠️ Trend Warning** | Cảnh báo cấu trúc xu hướng hiện tại + lý do |
| **🔭 Dự báo** | Vote 3 khung: Ngắn / Trung / Dài hạn + Overall |
| **🎯 T+ Setup** | Phán quyết T+ (MUA_NGAY/CHO_XAC_NHAN/THEO_DOI/TRANH_XA), vùng vào lệnh, mục tiêu, SL, phiên tốt nhất |

### Thông tin realtime (header)

Trên trang profiler hiển thị:
- **Giá hiện tại** (live từ API)
- **%Thay đổi** so với phiên trước
- **MFPM Score** và **Action** tổng hợp
- **Dự báo tổng hợp** (Overall vote + độ tin cậy)

---

## 18. Bảng quy tắc tổng hợp (Truth Table)

### Quy tắc bất biến (không bao giờ bị ghi đè)

| # | Quy tắc | Lý do nghiệp vụ |
|---|---|---|
| R-1 | AMF BLOCK → không bao giờ BUY | Mã có thao túng = rủi ro pháp lý và tài chính |
| R-2 | WHALE_DISTRIBUTING → Action tối đa là NO_ACTION | Khi tổ chức bán, giá thường giảm |
| R-3 | Distribution EXIT/FORCED_EXIT → ghi đè mọi tín hiệu mua | Bảo vệ vốn ưu tiên hơn cơ hội lãi |
| R-4 | Monte Carlo < 55% → không BUY dù điểm cao | Xác suất thực tế quan trọng hơn điểm mô hình |
| R-5 | Proxy data → Confidence bị hạ 1 bậc | Khuyến khích dùng data thực chất lượng cao |
| R-6 | AMD DISTRIBUTION/MARKDOWN → không BUY trong Mode W | Wyckoff phase xác nhận tổ chức đang bán |
| R-7 | T+ Setup T_AVOID → Verdict luôn TRANH_XA | Bảo vệ người dùng khỏi mua vào mã đang phân phối |
| R-8 | R:R < 1.2 → T+ Verdict hạ từ MUA_NGAY xuống CHO_XAC_NHAN | Tỷ lệ risk/reward không đủ hấp dẫn |

### Thứ tự ưu tiên tín hiệu (khi xung đột)

```
FORCED_EXIT > EXIT > BLOCK (AMF) > Distribution Warning > Macro Gate
> Monte Carlo Gate > Mode W Score > Mode A/B Score > Pattern Bonus
```

---

## 19. Cấu trúc đầu ra

### 19.1 Các trường Action (Hành động)

| Giá trị | Ý nghĩa | Màu sắc UI |
|---|---|---|
| `STRONG_BUY` | Tín hiệu mua rất mạnh — Mode W đang kích hoạt | 🟢 Xanh lá đậm |
| `BUY` | Tín hiệu mua — đủ điều kiện kỹ thuật và dòng tiền | 🟢 Xanh lá |
| `WATCH` | Theo dõi — chưa đủ điều kiện nhưng đang tiến triển | 🟡 Vàng |
| `NO_ACTION` | Không hành động — không có setup rõ ràng | ⚪ Xám |
| `EXIT` | Thoát lệnh — dấu hiệu phân phối hoặc cắt lỗ | 🔴 Đỏ |
| `FORCED_EXIT` | Thoát khẩn cấp — thao túng + phân phối | 🔴 Đỏ đậm |

### 19.2 Các trường T+ Verdict

| Giá trị | Tiếng Anh | Ý nghĩa tiếng Việt |
|---|---|---|
| `MUA_NGAY` | Buy Now | Vào lệnh khi giá xác nhận trigger |
| `CHO_XAC_NHAN` | Wait for Confirmation | Chờ nến/KL phiên tiếp xác nhận |
| `THEO_DOI` | Monitor | Đưa vào watchlist |
| `TRANH_XA` | Avoid | Không giao dịch T+ mã này |

### 19.3 Nhóm trường chính trong TickerProfile

| Nhóm | Trường tiêu biểu |
|---|---|
| **Định danh** | `ticker`, `exchange`, `last_updated` |
| **Tín hiệu chính** | `action`, `confidence`, `signal_mode`, `mfpm_score` |
| **Tham số giao dịch** | `entry_price`, `sl`, `sl_pct`, `tp1`, `tp2`, `rr_ratio` |
| **Dòng tiền** | `sms_raw`, `sms_label`, `mcvd_5d`, `mcvd_20d`, `mcvd_trend`, `stealth_accum`, `distribution_warning` |
| **Regime** | `amd_phase`, `hmm_state`, `macro_regime`, `macro_score` |
| **Rủi ro** | `earnings_risk`, `days_to_earnings`, `fundamental_score`, `mc_win_prob` |
| **Gap/VWAP** | `gap_type`, `vwap_dev`, `price_vs_vwap_pct`, `vwap_intraday_dev` |
| **T+2.5** | `t25_score`, `t25_signal`, `t25_morning_score`, `t25_midday_score`, `t25_afternoon_score`, `t25_best_window` |
| **T+ Setup** | `tplus_setup`, `tplus_verdict`, `tplus_entry_low`, `tplus_entry_high`, `tplus_target_t25`, `tplus_target_t5`, `tplus_stop`, `tplus_rr`, `tplus_confidence`, `tplus_session_vi` |
| **Dự báo** | `fc_short_vote`, `fc_short_conf`, `fc_mid_vote`, `fc_mid_conf`, `fc_long_vote`, `fc_long_conf`, `fc_overall_vote` |
| **Xu hướng** | `trend_warning`, `trend_warning_confidence`, `trend_warning_reasons` |
| **NLP** | `advisory_text`, `entry_window` |
| **Sizing** | `sizing_pct`, `sizing_shares` |

---

## 20. Giới hạn & Tuyên bố miễn trách

### Giới hạn hệ thống

| Giới hạn | Mô tả |
|---|---|
| **Dữ liệu không hoàn hảo** | Dòng tiền tổ chức ước tính từ OHLCV (proxy) — không phải dữ liệu thực tế của từng nhà đầu tư |
| **Não trạng thị trường** | Hệ thống không đọc được thông tin nội bộ (insider), chỉ phân tích dữ liệu giá/KL công khai |
| **Môi trường sự kiện** | Biến cố đột xuất (dịch bệnh, chiến tranh, chính sách bất ngờ) nằm ngoài khả năng dự báo |
| **Sàn mục tiêu** | Chỉ hỗ trợ HOSE và HNX. Không hỗ trợ UPCOM. |
| **Kỳ vọng dữ liệu** | Cần tối thiểu 20 ngày dữ liệu để tính chỉ báo; 50 ngày để phân tích đầy đủ; 200 ngày cho độ chính xác cao nhất |
| **Độ trễ dữ liệu** | Phụ thuộc vào API nguồn (SSI, vnstock) — có thể có độ trễ 15 phút với dữ liệu intraday |

### Tuyên bố miễn trách

> **TradingOS là công cụ hỗ trợ ra quyết định, không phải robot giao dịch tự động.**
>
> Mọi khuyến nghị đều dựa trên dữ liệu lịch sử và mô hình thống kê. Kết quả trong quá khứ không đảm bảo lợi nhuận trong tương lai.
>
> **Người dùng chịu hoàn toàn trách nhiệm về quyết định giao dịch của mình.**

---

*Tài liệu này phản ánh trạng thái hệ thống TradingOS v1.1 tính đến 2026-04-11.*  
*Để được cập nhật khi có thay đổi nghiệp vụ lớn, liên hệ team phát triển.*
