# TradingOS — Tài Liệu Nghiệp Vụ (Business Logic Document)

> **Đối tượng đọc:** Người nắm yêu cầu nghiệp vụ, không cần hiểu code kỹ thuật.  
> **Phạm vi:** Toàn bộ luồng phân tích, bộ quy tắc ra quyết định, và ý nghĩa của từng đầu ra.  
> **Cập nhật lần cuối:** 2026-04-22

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc luồng phân tích](#2-kiến-trúc-luồng-phân-tích)
3. [Lớp đo lường kỹ thuật — Indicators](#3-lớp-đo-lường-kỹ-thuật--indicators)
   - [3.4 Mô hình giá — Chart Patterns](#34-mô-hình-giá--chart-patterns)
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
21. [Nguồn dữ liệu & Cấu hình](#21-nguồn-dữ-liệu--cấu-hình)
22. [Giao diện ứng dụng — 7 trang chức năng](#22-giao-diện-ứng-dụng--7-trang-chức-năng)

---

### Các tính năng mới (cập nhật 2026-04-22)

| Tính năng | Phần liên quan |
|---|---|
| Tích hợp dữ liệu realtime FiinQuant (bu/sd aggressor volume) | Mục 4.5 |
| Tích hợp DNSE LightSpeed API | Mục 4.5 |
| Engine CVD trong phiên — tín hiệu mua/bán thực tế | Mục 4.5 |
| Engine Order Book Imbalance (OBI) — áp lực sổ lệnh | Mục 4.6 |
| CVD score giờ được đưa vào SMS component 6 (thay vì mặc định 5/10) | Mục 4.2 |
| Profiler mở rộng từ 11 lên 13 tab (CVD Intraday + Sổ lệnh) | Mục 17 |
| Cột CVD trong bảng Scanner | Mục 16 |

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

## 2. Kiến trúc luồng phân tích

Khi người dùng tra cứu một mã cổ phiếu, hệ thống chạy tuần tự các bước sau:

```
┌─────────────────────────────────────────────────────────────┐
│  Bước 1 │ Lấy dữ liệu OHLCV (tối đa 1.000 ngày) + giá RT  │
│  Bước 2 │ Tính toán chỉ báo kỹ thuật (SMA, EMA, RSI, ...)  │
│  Bước 3 │ Kiểm tra thao túng giá (AMF)                      │
│  Bước 4 │ Phân tích dòng tiền (Whale / SMS / Phân phối)     │
│    4.5  │ Lấy dữ liệu intraday (FiinQuant → DNSE → SSI 5m)   │
│         │ Tính CVD phiên + OBI (Order Book Imbalance)          │
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

## 3.4 Mô hình giá — Chart Patterns

Hệ thống tự động phát hiện 5 loại mô hình giá cổ điển. Mỗi mô hình được phát hiện sẽ cộng **điểm bonus (+5 đến +15 điểm)** vào tổng điểm MFPM.

| Mô hình | Điều kiện phát hiện | Ý nghĩa nghiệp vụ |
|---|---|---|
| **Wyckoff Spring** | Giá đâm xuống hỗ trợ (10th percentile) nhưng đóng cửa lại trên hỗ trợ, với khối lượng thấp | Lực bán đã cạn kiệt — tổ chức đang hấp thụ áp lực cuối cùng trước khi đẩy giá |
| **VCP** *(Volatility Contraction)* | ≥ 3 pivots với biên độ ngày càng hẹp (30–70% pivot trước) + khối lượng giảm dần | Mã đang tích lũy năng lượng — breakout pivot VCP thường có tỷ lệ thành công cao |
| **Cup-with-Handle** | Đáy hình chén (sâu 12–40%), sau đó consolidate nhẹ (< 8% range) trước khi breakout | Mô hình tích lũy dài hạn — breakout khỏi tay cầm = tín hiệu mua chất lượng cao |
| **FVG** *(Fair Value Gap)* | Khoảng trống giữa high nến 1 và low nến 3 (bullish FVG); hoặc low nến 1 > high nến 3 (bearish FVG) | Vùng giá chưa được "kiểm định" — thị trường thường quay lại lấp các FVG; dùng làm vùng hỗ trợ/kháng cự |
| **RSI Divergence** | Giá tạo đáy mới nhưng RSI không tạo đáy mới (bullish divergence) | Tín hiệu đảo chiều sớm — momentum yếu hơn giá gợi ý lực bán đã cạn |

> **Lưu ý:** FVG được lưu lại trong Audit Log (tối đa 3 vùng gần nhất) để tham chiếu lại khi phân tích nguyên nhân một tín hiệu. Các mô hình VCP / Cup-with-Handle / Wyckoff Spring hiển thị trong cột "Pattern" ở Scanner và tab Chỉ số ở Profiler.

--- — Money Flow & SMS

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
| CVD trong phiên *(nâng cấp)* | 10 điểm | Áp lực mua/bán **thực tế** từ dữ liệu aggressor volume (FiinQuant) hoặc proxy OHLCV. Xem chi tiết ở Mục 4.5. |
| Lô thỏa thuận (PT Deals) | 15 điểm | Bằng chứng giao dịch tổ chức trực tiếp |

> **Thay đổi quan trọng (2026-04-22):** Trước đây, thành phần CVD trong phiên luôn trả về điểm mặc định 5/10 (trung lập) vì không có dữ liệu thực. Từ phiên bản này, nếu tài khoản FiinQuant được cấu hình, CVD được tính từ dữ liệu aggressor volume thực tế (bu/sd) — điểm sẽ phản ánh đúng áp lực mua/bán của từng phiên.

> **Nguyên tắc mới để tránh overfit:** CVD lấy từ `OHLCV Proxy` chỉ được dùng như tín hiệu nghiêng nhẹ quanh vùng trung lập, không được phép đóng góp mạnh ngang với `REAL_FLOW`. Chỉ dữ liệu aggressor volume thực (`bu/sd`) mới có thể nâng hoặc hạ mạnh SMS component này.

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

## 4.5. CVD Trong Phiên — Cumulative Volume Delta (Mới)

### Bài toán nghiệp vụ

> "Trong phiên hôm nay, những người thực sự đang **chủ động mua** (aggressor buy) nhiều hơn hay **chủ động bán** (aggressor sell) nhiều hơn?"

Đây là câu hỏi khác với dòng tiền nhiều ngày. CVD trong phiên đo lường **intent ngay lập tức** của người mua/bán, không phải xu hướng dài hạn.

### Nguồn dữ liệu & Mức độ chất lượng

Hệ thống có **3 cấp độ dữ liệu**, ưu tiên từ cao xuống thấp:

| Cấp | Nguồn | Chất lượng | Điều kiện |
|---|---|---|---|
| **1. Real Flow** | FiinQuant 1 phút (bu/sd) | 🟢 Cao nhất | Tài khoản FiinQuant được cấu hình |
| **2. DNSE LightSpeed** | DNSE API 1 phút | 🟡 Tốt | API key DNSE được cấu hình |
| **3. OHLCV Proxy** | SSI 5 phút (ước tính) | ⚪ Ước tính | Luôn có sẵn (fallback) |

**Giải thích:**
- **Real Flow (FiinQuant):** Mỗi nến 1 phút có 2 trường đặc biệt:
  - `bu` = tổng khối lượng lệnh mua chủ động (aggressor buy) trong phút đó
  - `sd` = tổng khối lượng lệnh bán chủ động (aggressor sell)
  - Delta = `bu − sd` → dương = người mua đang quyết liệt hơn
- **OHLCV Proxy:** Nếu nến đóng cửa cao hơn mở cửa → ước tính là mua; ngược lại là bán. Độ chính xác thấp hơn nhưng vẫn có giá trị định hướng.

**Quy tắc sử dụng trong chấm điểm:**
- `REAL_FLOW`: được phép tác động đầy đủ vào component CVD của SMS.
- `OHLCV_PROXY`: chỉ được xem là tín hiệu timing ngắn hạn, trọng số bị giảm để tránh hiểu nhầm bar direction là institutional flow thật.
- `NONE`: giữ trung lập, không tạo edge giả.

### Các chỉ số CVD được tính

| Chỉ số | Ý nghĩa |
|---|---|
| **CVD Signal** | `BUYING` / `NEUTRAL` / `DISTRIBUTING` — nhận định tổng thể về áp lực phiên |
| **CVD Score (0–10)** | Điểm hóa CVD: 0 = toàn bán, 5 = cân bằng, 10 = toàn mua. Đây là đầu vào cho SMS component 6. |
| **Buying Pressure %** | % số nến trong phiên có delta dương (mua nhiều hơn bán) |
| **CVD Divergence** | Phát hiện khi dòng tiền đi ngược chiều giá (xem bảng bên dưới) |
| **CVD Trend** | `RISING` / `FLAT` / `FALLING` — đà tích lũy mua trong phiên có đang tăng không? |
| **Data Quality** | `REAL_FLOW` / `OHLCV_PROXY` / `NONE` — cho người dùng biết độ tin cậy của tín hiệu |

### Phân kỳ CVD (CVD Divergence) — tín hiệu giá trị cao

| Loại phân kỳ | Điều kiện | Ý nghĩa | Hành động |
|---|---|---|---|
| `BULLISH_DIV` | CVD dương (mua ròng) nhưng giá đang giảm | Tổ chức đang thu gom lặng lẽ trong khi đám đông bán | **Cơ hội mua** — theo dõi chặt |
| `BEARISH_DIV` | CVD âm (bán ròng) nhưng giá đang tăng | Tổ chức đang xả hàng trong khi giá vẫn cao | **Cảnh báo** — có thể đây là bẫy tăng |
| `NONE` | Không có phân kỳ | Bình thường | Không tác động |

---

## 4.6. Order Book Imbalance (OBI) — Áp Lực Sổ Lệnh (Mới)

### Bài toán nghiệp vụ

> "Ngay lúc này, trên sổ lệnh, tổng lệnh chờ mua lớn hơn hay tổng lệnh chờ bán lớn hơn?"

OBI cho biết áp lực ngay tức thời trên bảng giá (order book), trước khi lệnh thực sự khớp. Đây là tín hiệu rất ngắn hạn (vài phút).

### Yêu cầu dữ liệu

OBI chỉ có khi **FiinQuant** được cấu hình và cung cấp snapshot sổ lệnh (BidAsk). Nếu không có FiinQuant, tab Sổ lệnh trong Profiler sẽ hiển thị thông báo "Chưa có dữ liệu".

### Công thức OBI

```
OBI (%) = (Tổng_khối_lượng_mua − Tổng_khối_lượng_bán) / (Tổng_mua + Tổng_bán) × 100
```

Ví dụ: Tổng bid = 700.000 cổ, Tổng ask = 300.000 cổ
→ OBI = (700K − 300K) / (700K + 300K) × 100 = **+40%** → Áp lực mua rõ rệt

### Phân loại OBI Signal

| OBI | Tín hiệu | Ý nghĩa |
|---|---|---|
| > +20% | `BUYING_PRESSURE` | Lệnh chờ mua áp đảo — người mua đang xếp hàng |
| −20% đến +20% | `BALANCED` | Cân bằng cung cầu — chưa có áp lực rõ ràng |
| < −20% | `SELLING_PRESSURE` | Lệnh chờ bán áp đảo — người bán đang xếp hàng |

> **Lưu ý nghiệp vụ:** OBI là tín hiệu **cực ngắn hạn** và có thể thay đổi trong vài giây. Không nên dùng OBI một mình để ra quyết định — nên kết hợp với CVD và tín hiệu T+ để xác nhận.

---

## 5. Phát hiện thao túng giá — AMF (Anti-Manipulation Filter)

### Mục tiêu

Phát hiện các mã đang bị **làm giá** (pump-and-dump, wash trading) để bảo vệ người dùng.

### Quy trình

Hệ thống chạy 4 lớp lọc độc lập, mỗi lớp phát hiện một loại bất thường:

| Lớp | Kiểm tra | Cờ cảnh báo |
|---|---|---|
| **1. Open Spike** | Mở cửa lệch > 6% so với đóng cửa hôm trước | `OPEN_SPIKE_X.Xpct` |
| **2. Wash-Sale Volume** | Khối lượng Z-score > 3.0 — cao bất thường | `WASH_SALE_VOLUME_ZX.X` |
| **3. Bid-Ask Imbalance** | Một phía trong sổ lệnh chiếm > 70% tổng lệnh chờ | `ORDER_BOOK_IMBALANCE_BID/ASK` |
| **4. VWAP Deviation** | Giá lệch VWAP > 3% — dấu hiệu cách xa vùng giá trị thực | `VWAP_DEV_X.Xpct` |

**Quy tắc kết luận:**
- **0 cờ** → `PASS` — an toàn
- **1–2 cờ** → `WARN` — có bất thường, giảm Confidence
- **≥ 3 cờ** → `BLOCK` — phát hiện điều bất thường rõ ràng

### Kết quả (AMF Decision)

| Quyết định | Ý nghĩa | Tác động |
|---|---|---|
| `PASS` | Không phát hiện thao túng | Không tác động |
| `WARN` | Có một vài bất thường nhỏ | Giảm Confidence |
| `BLOCK` | Phát hiện điều bất thường rõ ràng | **Cấm BUY** — chỉ cho phép EXIT |

> ⚠️ **Quy tắc cứng:** `AMF BLOCK` = tự động **NO_ACTION** hoặc **FORCED_EXIT** (nếu kết hợp với phân phối).

---

## 6. Nhận diện pha thị trường — AMD & HMM

### 6.1 Pha Wyckoff (AMD — Accumulation/Markup/Distribution/Markdown)

Mô tả trạng thái hiện tại của mã trong chu kỳ lớn tổ chức (Richard Wyckoff):

| Pha | Mô tả | Khuyến nghị |
|---|---|---|
| `ACCUMULATION` | Tổ chức đang thu gom hàng lặng lẽ. Giá đi ngang / hơi giảm, OBV tăng. | ✅ Tốt để mua |
| `MARKUP` | Giá bắt đầu tăng mạnh. Đám đông bắt đầu nhận ra. | ✅ Cơ hội tốt nhất |
| `DISTRIBUTION` | Tổ chức âm thầm bán. Giá vẫn cao nhưng OBV giảm. | ⛔ Không mua |
| `MARKDOWN` | Giá giảm rõ rệt. Tổ chức đã thoát xong. | ⛔ Tránh xa |
| `RANGING` | Giá dao động trong biên hẹp, không có xu hướng rõ (OBV phẳng). | ⏸ Trung lập — chờ tín hiệu |

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
| `REVERSAL_WARNING_LOW_CONF` | 1–2 tín hiệu đảo chiều — chưa rõ ràng |
| `REVERSAL_WARNING_CONFIRMED` | ≥ 3 tín hiệu đảo chiều đồng nhất — cảnh báo thực sự |
| `NONE` | Bình thường — không có cấu trúc đáng chú ý |
| `INSUFFICIENT_DATA` | Không đủ dữ liệu — cần ít nhất 50 phiên OHLCV |

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
| Sideways | 45% | 30% | 25% |
| Bear trend | 40% | 30% | 30% |

### 9.2 Tín hiệu vào lệnh

| Tín hiệu | Ngưỡng | Ý nghĩa |
|---|---|---|
| `T25_BUY` | ≥ 68 điểm (≥ 74.8 trong bear market) | Vào lệnh T+2.5 |
| `T25_WATCH` | ≥ 55 điểm (≥ 46 trong bear market) | Theo dõi phiên tiếp |
| `T25_NEUTRAL` | Trung gian | Chờ thêm tín hiệu |
| `T25_AVOID` | ≤ 28 điểm (≤ 32 trong non-sideways/non-bear) | Không vào T+2.5 |

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

> **Trailing Stop (ATR-based):** Khi vị thế đã chốt lời một phần tại TP1, hệ thống kích hoạt trailing stop tự động:
> ```
> Trailing Stop = max(High_kể_từ_entry − ATR × 2.5, entry_price)
> ```
> Trailing stop **không bao giờ thấp hơn giá vào lệnh** — đảm bảo vị thế không lỗ sau khi đã đạt TP1. Khi giá chạm trailing stop sau TP1, hệ thống khuyến nghị thoát toàn bộ phần còn lại.

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

### 10.2 Trạng thái kỹ thuật T+ (Timing)

Thay vì gọi là "Phán quyết" trùng lặp với `Action` của MFPM, Engine này chỉ đưa ra góc nhìn ngắn hạn về điểm vào lệnh hiện tại:

| Trạng thái | Điều kiện | Ý nghĩa |
|---|---|---|
| `MUA_NGAY` | Điểm ≥ 7.5 + T25_BUY / Điểm ≥ 5.5 + T25_BUY | ✅ Thích hợp giải ngân T+ |
| `CHO_XAC_NHAN` | Điểm ≥ 5.5 (nhưng T25 không phải BUY) | ⏳ Chờ nến xác nhận phiên tiếp theo |
| `THEO_DOI` | Điểm ≥ 3.0 | 👀 Theo dõi tín hiệu T+ |
| `TRANH_XA` | Điểm < 3.0 hoặc T_AVOID | 🚫 Không có điểm vào T+ an toàn |

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

### 10.4 Tư vấn cửa sổ vào lệnh (Execution Advisory)

Ngoài lịch trình theo setup, hệ thống còn tự động đề xuất **loại lệnh và khung giờ cụ thể** dựa trên Signal Mode tại thời điểm hiện tại:

| Signal Mode | Cửa sổ khuyến nghị | Loại lệnh | Lý do |
|---|---|---|---|
| **Mode W** (Whale) | ATC 14:43 | Lệnh ATC (khớp cuối ngày) | Cá mập thường tích lũy qua ATC — vào cùng chiều |
| **Mode B** (Breakout) | 09:30–09:45 | Lệnh LO tại pivot | Vào breakout ngay sau khi xác nhận mở cửa mạnh |
| **Mode A** (Pullback) | 14:05–14:20 hoặc ATO T+1 | Lệnh LO tại SMA20 ± 0.5% | Pullback — chờ giá kiểm tra lại support |

> **Tự động theo thời gian thực:** Nếu thị trường đang trong cửa sổ ATC (14:43–14:45) và tín hiệu là STRONG_BUY, khuyến nghị sẽ đổi thành "ATC ngay bây giờ". Nếu thị trường đã đóng cửa, khuyến nghị "ATO sáng T+1".

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
| Trung hạn | 35% |
| Dài hạn | 25% |

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
| **Bonus SMS (trung bình)** | +12 điểm | SMS 60–74 |
| **Bonus SMS (nhỏ)** | +5 điểm | SMS 40–59 |
| **Penalty SMS** | −10 điểm | SMS < 20 |
| **Penalty phân phối cá voi** | −25 điểm | M-CVD = DIVERGE_BEARISH (tổ chức bán khi giá tăng) |
| **Bonus Fundamental** | +12 điểm | Fundamental score ≥ 75 |
| **Bonus Fundamental (nhỏ)** | +6 điểm | Fundamental score 60–74 |
| **Penalty Fundamental** | −10 điểm | Fundamental score < 35 |
| **Penalty Fundamental (nhỏ)** | −4 điểm | Fundamental score 35–44 |
| **Bonus Pattern** | +5 đến +15 điểm | Tùy loại mô hình nến |
| **Cộng Macro** | +5 điểm | Môi trường vĩ mô hỗ trợ |
| **Trừ Macro** | −10 điểm | Môi trường vĩ mô thắt chặt |

> **Earnings Risk:** Không trừ điểm MFPM trực tiếp — thay vào đó nâng ngưỡng SMS tối thiểu để vào lệnh (xem Mục 14.2).

### 12.3 Bảng quy tắc Action (Decision Table)

| Điều kiện | Action | Ưu tiên |
|---|---|---|
| Distribution = FORCED_EXIT hoặc AMF BLOCK + Distribution | `FORCED_EXIT` | 1 (cao nhất) |
| Distribution = EXIT | `EXIT` | 2 |
| Mode W: Score ≥ 95 + AMF PASS + MC ≥ 60% | `STRONG_BUY` | 3 |
| Mode W: Score ≥ 80 | `BUY` | 4 |
| Mode A/B: MFPM ≥ 70 + AMF PASS + MC ≥ 55% | `BUY` | 5 |
| MFPM ≥ 50 | `WATCH` | 6 |
| SMS label = WHALE_DISTRIBUTING | WATCH → `NO_ACTION` | 7 |
| Các trường hợp còn lại | `NO_ACTION` | 8 (thấp nhất) |

### 12.4 Mức độ tin cậy (Confidence)

| Mức | Ý nghĩa | Yêu cầu |
|---|---|---|
| `HIGH` | Tín hiệu mạnh, nhiều yếu tố đồng thuận | **Mode W:** W-Score ≥ 95 + STEADY_BULL + MC ≥ 65% · **Mode A/B:** MFPM ≥ 80 + STEADY_BULL |
| `MEDIUM` | Tín hiệu tốt nhưng một số yếu tố chưa rõ | **Mode W:** W-Score ≥ 80 + AMF PASS + MC ≥ 55% · **Mode A/B:** MFPM 60–79 |
| `LOW` | Tín hiệu yếu hoặc dữ liệu không đầy đủ | Dùng proxy OHLCV thay real flow data, hoặc W/MFPM thấp |

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

Hệ thống phát hiện kết quả phải công bố trong **thời gian tới** theo Thông tư 96/2020/TT-BTC và phân loại thành **3 mức rủi ro**:

| Mức | Nhãn | Nguyên nhân |  Ảnh hưởng
|---|---|---|---|
| An toàn | `SAFE` | Không có lịch công bố trong vòng cần thận | Không đổi |  
| Cần chú ý | `CAUTION` | Công bố trong khoảng **5–14 ngày tới** | Nâng ngưỡng SMS vào lệnh lên +5 điểm; Thắt chặt trailing stop (× 0.80 ATR) |
| Rủi ro cao | `HIGH_RISK` | Công bố trong vòng **5 ngày tới** | Nâng ngưỡng SMS lên +10 điểm (hầu hết mã không vượt qua); Thắt chặt trailing stop (× 0.60 ATR) |

> **Cơ chế hạn chế:** Khác với việc trừ thẳng vào điểm MFPM, hệ thống **nâng ngưỡng vào lệnh SMS** khi có BCTC sắp công bố. Điều này có nghĩa: chỉ những mã có dòng tiền tổ chức đủ mạnh mới được khuyến nghị mua trước BCTC. Ngoài ra, trailing stop cũng được tự động thắt chặt hơn để bảo vệ lợi nhuận hiện có.

---

## 15. Cỡ vị thế & Quản trị rủi ro

### Phương pháp tính

Hệ thống dùng **Kelly Criterion** (**30% Kelly** — conservative fraction theo cấu hình mặc định) để tính % vốn nên đặt vào mỗi lệnh:

```
Kellyầy đủ = Win_Rate − (1 − Win_Rate) / (Avg_Win / Avg_Loss)
Kelly thực dùng = Kellyầy đủ × 0.3   (30% Kelly — rất thận trọng)
```

> Sở dĩ dùng 30% thay vì 50% (half-Kelly): Thị trường VN có biến động cao, rủi ro liquidity (LOCK_SAN), và dữ liệu backtest có độ chính xác giới hạn — 30% Kelly là mức bảo thủ phù hợp.

### Điều chỉnh thêm

| Yếu tố điều chỉnh | Tác động |
|---|---|
| **Macro Multiplier** | Vĩ mô restrictive: giảm cỡ vị thế. Accommodative: giữ nguyên hoặc tăng nhẹ. |
| **Win Probability** | < 55%: loại bỏ. 55–60%: cỡ nhỏ. > 70%: cỡ chuẩn. |
| **ATR Risk Cap** | SL × cỡ vị thế không vượt quá 2% tổng vốn |

Đầu ra: **% vốn** và **số cổ phiếu cụ thể** dựa trên vốn tài khoản người dùng nhập. Cổ phiếu luôn được làm tròn xuống theo lô 100 cổ (tiêu chuẩn HOSE).

### Chiến lược vào lệnh chia nhỏ (Progressive Entry)

Thay vì dồn toàn bộ vốn vào một lần, hệ thống chia lệnh vào thành **2–3 đợt** dựa theo Mode:

| Signal Mode | Đợt 1 | Đợt 2 | Đợt 3 | Mục đích |
|---|---|---|---|---|
| **Mode W** | 50% — ATC ngày tín hiệu | 30% — ATO hôm sau (xác nhận giữ vùng) | 20% — Breakout T+3 | Theo dấu cá mập, không để lọ giá ATC quan trọng |
| **Mode B** | 50% — Breakout ngay lập tức | 30% — Retest + confirm | 20% — Add nếu giữ trên pivot | Mua mạnh khi có khối lượng xác nhận |
| **Mode A** | 60% — Pullback tới SMA20 | 40% — RSI confirm > 50 | — | Chia 2 đợt đợi xác nhận momentum |

> **Lưu ý:** Lê kế hoạch chia đợt **chỉ mang tính tư vấn**. Tất cả các đợt dùng chung cùng một giá SL ban đầu — tổng rủi ro không vượt 2% danh mục.

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
| Giới hạn kết quả | 30 mã | Số mã mặc định trả về (có thể điều chỉnh) |

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

`Mã | Action | Conf | MFPM | Macro | Sector | BCTC | W-Score | SMS | Mode | Giá | Vào | SL | TP1 | R:R | AMF | Pattern | HMM | Stealth | T+ Setup | T+ Verdict | T+ Conf | CVD | Tóm tắt NLP`

> **Cột CVD mới (2026-04-22):** Hiển thị tín hiệu CVD trong phiên (`BUYING` / `NEUTRAL` / `DISTRIBUTING`) cho phép lọc nhanh mã nào đang có dòng tiền vào trong phiên. Cột này lấy từ kết quả tính toán CVD Engine (Mục 4.5).

---

## 17. Profiler — Hồ sơ chi tiết một mã

Khi tra cứu một mã cụ thể, hệ thống hiển thị **13 tab** phân tích:

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
| **📊 CVD Intraday** *(Mới)* | Tín hiệu CVD trong phiên: BUYING/NEUTRAL/DISTRIBUTING, badge chất lượng dữ liệu (Real Flow / Proxy), % áp lực mua, phân kỳ CVD, CVD Score 0–10 |
| **📖 Sổ lệnh** *(Mới)* | Order Book Imbalance: OBI%, tín hiệu BUYING_PRESSURE/BALANCED/SELLING_PRESSURE. Yêu cầu FiinQuant — hiển thị thông báo nếu chưa kết nối. |

### Hướng dẫn đọc 2 tab mới

**Tab CVD Intraday:**
- Badge `🟢 Real Flow — FiinQuant bu/sd`: dữ liệu chất lượng cao, tin cậy
- Badge `🟡 Proxy — OHLCV sign`: ước tính, ít chính xác hơn
- Thanh tiến độ "Áp lực mua": > 60% là bullish, < 40% là bearish
- CVD Score: 0–4 = phân phối; 5 = trung lập; 6–10 = mua
- Cảnh báo phân kỳ: `⚡ BULLISH_DIV` hoặc `⚡ BEARISH_DIV` (xem Mục 4.5)

**Tab Sổ lệnh (OBI):**
- Hiển thị OBI% với màu sắc: xanh = mua, đỏ = bán, xám = cân bằng
- Nếu chưa cài FiinQuant: "Chưa có dữ liệu sổ lệnh — cần FiinQuant BidAsk"

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
| **Regime** | `amd_phase`, `hmm_state`, `gmo_omega`, `macro_regime`, `macro_score` |
| **Rủi ro** | `earnings_risk`, `days_to_earnings`, `fundamental_score`, `mc_win_prob` |
| **Gap/VWAP** | `gap_type`, `vwap_dev`, `price_vs_vwap_pct`, `vwap_intraday_dev` |
| **T+2.5** | `t25_score`, `t25_signal`, `t25_morning_score`, `t25_midday_score`, `t25_afternoon_score`, `t25_best_window` |
| **T+ Setup** | `tplus_setup`, `tplus_verdict`, `tplus_entry_low`, `tplus_entry_high`, `tplus_target_t25`, `tplus_target_t5`, `tplus_stop`, `tplus_rr`, `tplus_confidence`, `tplus_session_vi` |
| **CVD & OBI** *(Mới)* | `cvd_signal`, `cvd_divergence`, `cvd_buying_pressure_pct`, `cvd_score`, `cvd_data_quality`, `obi_pct`, `obi_signal`, `data_source_intraday` |
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

---

## 21. Nguồn dữ liệu & Cấu hình

### 21.1 Nguồn dữ liệu đang dùng

| Nguồn | Loại dữ liệu | Cần tài khoản? | Ghi chú |
|---|---|---|---|
| **SSI iBoard API** | OHLCV lịch sử, giao dịch thỏa thuận, dòng tiền nước ngoài, giá realtime | Không (nhưng cần device ID để tránh block) | Nguồn chính — luôn có sẵn |
| **CafeF API** | Lịch kết quả kinh doanh, chỉ số cơ bản | Không | Dùng cho Earnings Risk và Fundamental |
| **NHNN / MoF** | Tỷ giá USD/VND, lãi suất OMO, trái phiếu 10 năm | Không | Dùng cho Macro Regime |
| **FiinQuant** | Nến 1 phút với bu/sd aggressor volume, snapshot sổ lệnh | **Có** — tài khoản fiinquant.vn | Cần cấu hình trong `config/local.toml`. Nếu không có → tự động fallback SSI 5 phút |
| **DNSE LightSpeed** | Nến 1 phút intraday | **Có** — API key DNSE | Cần cấu hình `dnse_api_key`. Ưu tiên sau FiinQuant, trước SSI. |
| **vnstock (offline)** | Danh sách mã theo sàn | Không | Dùng cho Scanner universe |

### 21.2 Thứ tự ưu tiên nguồn dữ liệu intraday

```
FiinQuant 1m (bu/sd) → DNSE 1m → SSI 5m → Không có dữ liệu
```

Hệ thống **không bao giờ crash** khi thiếu nguồn — luôn tự động xuống nguồn thấp hơn và ghi nhãn chất lượng (`REAL_FLOW` / `OHLCV_PROXY` / `NONE`).

### 21.3 Cách kích hoạt FiinQuant

Để sử dụng dữ liệu CVD chất lượng cao:
1. Tạo tài khoản tại [fiinquant.vn](https://fiinquant.vn)
2. Thêm thông tin đăng nhập vào file `config/local.toml` (không bao giờ commit file này):
   ```toml
   [api]
   fiinquantx_username = "email@example.com"
   fiinquantx_password = "mat_khau"
   ```
3. Cài gói thư viện: `pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx`
4. Khởi động lại ứng dụng — hệ thống tự động nhận diện và kích hoạt

---

## 22. Giao diện ứng dụng — 7 trang chức năng

Ứng dụng TradingOS bao gồm **7 trang**, điều hướng qua sidebar bên trái. Các trang được thiết kế theo nguyên tắc "advisory only" — không đặt lệnh tự động.

| # | Trang | Biểu tượng | Chức năng chính |
|---|---|---|---|
| 1 | **Profiler** | 🔍 | Hồ sơ phân tích chi tiết một mã (13 tab) — xem Mục 17 |
| 2 | **Scanner** | 📡 | Quét toàn sàn, lọc/sắp xếp theo tín hiệu — xem Mục 16 |
| 3 | **Performance** | 🏆 | Sổ lệnh paper trading: tỷ lệ thắng, Sharpe, Equity Curve |
| 4 | **Dòng tiền** | 🐳 | Dashboard dòng tiền: Whale Watchlist, M-CVD Chart, Sector Rotation |
| 5 | **Backtest** | 📊 | So sánh Mode A/B/W theo lịch sử thực tế |
| 6 | **Audit** | 🗂 | Nhật ký sự kiện hệ thống (DuckDB) — tra cứu tín hiệu lịch sử |
| 7 | **Cài đặt** | ⚙️ | Cấu hình, Watchlist, DuckDB browser |

### 22.1 Trang Performance — Hiệu suất Paper Trading

> Theo dõi kết quả thực tế của tất cả tín hiệu BUY/STRONG_BUY hệ thống đã phát ra.

| Chỉ số | Ý nghĩa | Ngưỡng tốt |
|---|---|---|
| **Tỷ lệ thắng** | % giao dịch đóng với lãi > 0 | > 55% |
| **Profit Factor** | Tổng lãi / Tổng lỗ — đo hiệu quả rủi ro/lợi nhuận | > 1.5 |
| **Sharpe Ratio** | Lợi nhuận điều chỉnh rủi ro (quy đổi năm, 252 phiên) | > 1.0 |
| **Max Drawdown** | Mức giảm tối đa từ đỉnh equity xuống đáy | < 20% |
| **Calmar Ratio** | Tỷ lệ lợi nhuận TB / Max Drawdown | > 1.0 |
| **Equity Curve** | Biểu đồ đường vốn theo thời gian — kiểm tra tính ổn định | Đường đi lên đều |

Trang cũng hiển thị danh sách giao dịch đang mở (OPEN) và đã đóng (CLOSED) với PnL từng lệnh.

> **Lưu ý:** Đây là **paper trading** (giao dịch ảo). Hệ thống tự ghi nhận tín hiệu và theo dõi đến khi đạt SL/TP để tính toán hiệu suất.

### 22.2 Trang Dòng tiền — Money Flow Dashboard

Cho phép theo dõi dòng tiền thông minh trên **nhiều mã cùng lúc**, khác với Profiler chỉ xem một mã:

| Tab | Nội dung |
|---|---|
| **🐋 Whale Watchlist** | Nhập danh sách mã tùy chọn (hoặc lấy từ Watchlist đã lưu) → tính SMS score + M-CVD trend + stealth signal cho tất cả cùng lúc |
| **📊 M-CVD Chart** | Biểu đồ M-CVD chi tiết theo ngày cho một mã + SMS gauge + stealth accumulation signals |
| **🗺 Sector Rotation** | Bản đồ nhiệt (heatmap) dòng tiền vào/ra theo ngành — xác định sector nào đang được tổ chức ưa thích |

### 22.3 Trang Backtest

So sánh hiệu quả 3 chế độ giao dịch (Mode A/B/W) trên dữ liệu lịch sử thực tế của một mã.

**Cách dùng:** Chọn mã + khoảng thời gian + tham số SL/TP → hệ thống tự chạy backtest cho cả 3 Mode.

**Kết quả trả về:**

| Chỉ số | Ý nghĩa |
|---|---|
| **Win Rate** | Tỷ lệ lệnh có lãi trong khoảng thời gian đó |
| **Avg PnL %** | Lãi/lỗ trung bình mỗi giao dịch |
| **Max Drawdown** | Mức giảm vốn tối đa trong kỳ backtest |
| **Sharpe** | Hiệu quả rủi ro/lợi nhuận |
| **Total Return** | Tổng lợi nhuận tích lũy |
| **Walk-Forward** | Chia nhỏ khoảng thời gian → kiểm tra tính ổn định qua nhiều giai đoạn |
| **Trade List** | Danh sách từng lệnh: ngày vào/ra, giá, PnL%, lý do thoát |

**Ràng buộc VN được tích hợp:**
- **T+3:** Lệnh mua ngày T → thoát sớm nhất ngày T+2 (không cho phép thoát T+0 hoặc T+1)
- **LOCK_SAN Simulation:** 5% trường hợp mô phỏng giá lock sàn → lệnh không khớp được (synthetic miss) — phản ánh rủi ro thực của thị trường VN

### 22.4 Trang Audit — Nhật ký Sự kiện

Toàn bộ sự kiện của hệ thống được ghi vào **DuckDB** và có thể tra cứu qua trang Audit.

**Tính năng:**
- **Lọc** theo mã, loại sự kiện (BUY / SCAN / PROFILE / POSITION_OPEN), khoảng ngày
- **Xem lại** tín hiệu lịch sử: Action, MFPM score, SMS, Mode, confidence
- **FVG Zones:** Mở rộng xem các vùng Fair Value Gap tại thời điểm tín hiệu được phát ra
- **Hướng dẫn chỉ số:** Bảng giải thích ý nghĩa từng chỉ số ảnh hưởng quyết định (MFPM, SMS, AMF, RSI, ATR, v.v.)

> **Mục đích:** Trang Audit là công cụ **kiểm toán** — cho phép nhìn lại "tại sao hệ thống phát tín hiệu X vào ngày Y" và kiểm chứng chất lượng model theo thời gian.

### 22.5 Trang Cài đặt

| Tab | Nội dung |
|---|---|
| **Config** | Xem cấu hình chiến lược hiện tại (strategy.yaml) theo từng section |
| **Watchlist** | Thêm/xóa mã theo dõi — danh sách này được dùng chung trong trang Dòng tiền |
| **DuckDB** | Xem danh sách các bảng database — kiểm tra trạng thái lưu trữ |

---

*Tài liệu này phản ánh trạng thái hệ thống TradingOS v1.2 tính đến 2026-04-22.*  
*Để được cập nhật khi có thay đổi nghiệp vụ lớn, liên hệ team phát triển.*
