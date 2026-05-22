# TradingOS — UI/UX & System Improvement Proposal v1.0
> **Ngày:** 2026-05-22 | **Tác giả:** AI Research Analysis | **Phạm vi:** Toàn bộ ứng dụng  
> **Đối tượng:** Nhà đầu tư T+2.5 thị trường Việt Nam (HOSE, HNX)  
> **Hiện trạng phân tích:** Streamlit Alpha + 7 trang + 10 components + 20+ core engines

---

## Mục lục

1. [Tóm tắt điều hành](#1-tóm-tắt-điều-hành)
2. [Phân tích hiện trạng — Điểm mạnh & Gap](#2-phân-tích-hiện-trạng)
3. [Đề xuất UI/UX — Trang Profiler](#3-đề-xuất-uiux--trang-profiler)
4. [Đề xuất UI/UX — Trang Scanner](#4-đề-xuất-uiux--trang-scanner)
5. [Đề xuất UI/UX — Trang Performance](#5-đề-xuất-uiux--trang-performance)
6. [Đề xuất UI/UX — Trang Dòng tiền (DTL)](#6-đề-xuất-uiux--trang-dòng-tiền)
7. [Đề xuất UI/UX — Trang Backtest](#7-đề-xuất-uiux--trang-backtest)
8. [Đề xuất UI/UX — Trang Audit](#8-đề-xuất-uiux--trang-audit)
9. [Đề xuất UI/UX — Trang Cài đặt](#9-đề-xuất-uiux--trang-cài-đặt)
10. [Đề xuất — Dashboard tổng hợp T+2.5](#10-đề-xuất--dashboard-tổng-hợp-t25)
11. [Đề xuất — Navigation & Layout hệ thống](#11-đề-xuất--navigation--layout-hệ-thống)
12. [Đề xuất — Cải thiện Business Logic & Engine](#12-đề-xuất--cải-thiện-business-logic--engine)
13. [Đề xuất — Alerting & Notification System](#13-đề-xuất--alerting--notification-system)
14. [Đề xuất — Mobile-Responsive / PWA](#14-đề-xuất--mobile-responsive--pwa)
15. [Lộ trình triển khai — Ưu tiên theo tác động](#15-lộ-trình-triển-khai)
16. [Phụ lục — Mockup mô tả giao diện](#16-phụ-lục--mockup-mô-tả-giao-diện)

---

## 1. Tóm tắt điều hành

TradingOS hiện là hệ thống phân tích định lượng **alpha-stage** với nền tảng engine rất mạnh (MFPM, SMF, AMF, HMM, BiLSTM, Monte Carlo, T+2.5 Exit Advisory). Tuy nhiên, toàn bộ UI đang xây dựng theo kiểu **developer-first** thay vì **trader-first** — nhiều thông tin quan trọng bị chôn sâu trong tab, form phức tạp và không có luồng hành động rõ ràng cho giao dịch T+2.5.

### Vấn đề cốt lõi

| # | Vấn đề | Mức độ ảnh hưởng |
|---|---|---|
| P1 | Không có "Morning Briefing" — trader phải tự chạy Scanner mỗi sáng, không có tóm tắt ngay lập tức | 🔴 Cao |
| P2 | Profiler có 13 tab — thông tin T+2.5 quan trọng nhất bị đặt ở tab thứ 8 | 🔴 Cao |
| P3 | Scanner không có bộ lọc preset nhanh (Quick Filter) cho T+2.5 — trader phải tự chỉnh slider mỗi lần | 🟠 Trung bình-Cao |
| P4 | Không có cột giá realtime trong Scanner khi đang trong phiên giao dịch | 🟠 Trung bình |
| P5 | Không có cảnh báo ATC 14:43 trực tiếp trong UI — trader có thể bỏ lỡ cửa sổ thoát T+2.5 | 🔴 Cao |
| P6 | Performance page không thể nhập kết quả giao dịch thực (manual entry) | 🟠 Trung bình |
| P7 | Toàn bộ text NLP tiếng Việt được generate nhưng ít hữu ích vì không có action call-out rõ ràng | 🟡 Thấp-Trung bình |
| P8 | Không có trạng thái "danh mục đang nắm giữ" — không thể theo dõi T+0 → T+2.5 lifecycle | 🔴 Cao |
| P9 | Audit log không có filterable timeline — rất khó đọc lịch sử quyết định theo mã | 🟡 Thấp-Trung bình |
| P10 | Không có chart giá tích hợp — trader phải mở ứng dụng khác để xem candlestick | 🔴 Cao |

---

## 2. Phân tích hiện trạng

### 2.1 Điểm mạnh

- **Engine vững chắc:** MFPM, Mode A/B/W, AMF, HMM, SMS, Monte Carlo, T+2.5 Exit Advisory — đây là foundation rất tốt.
- **Dark theme:** Phù hợp với trader làm việc nhiều giờ với màn hình.
- **NLP tiếng Việt:** Giải thích lý do bằng tiếng Việt — rất hữu ích cho F0 và trader không chuyên kỹ thuật.
- **Audit trail:** Ghi log đầy đủ vào DuckDB — có thể truy vết quyết định.
- **T+ Verdict mapping:** Bảng mapping Action × T+Verdict rõ ràng trong TPLUS_MAPPING_GUIDE.
- **AMF filter:** Tự động chặn mã nghi thao túng trước khi hiển thị — phòng thủ tốt.

### 2.2 Gap phân tích — UX

```
Luồng trader hiện tại (BROKEN):
  Mở app → chọn Profiler → nhập mã → chờ ~5-15s → đọc 13 tab → 
  quyết định có vào không → KHÔNG BIẾT lúc nào nên xem ATC

Luồng trader lý tưởng (TARGET):
  Mở app → thấy ngay Morning Briefing (top 5-10 cơ hội + danh mục đang nắm) →
  click vào 1 mã → thấy Signal Card + T+2.5 Plan trong 3 giây →
  nhận cảnh báo ATC 14:43 khi đến giờ thoát lệnh
```

### 2.3 Benchmark so với app trading tương đương

| Feature | TradingOS hiện tại | TradingView | Fiinpro | Target |
|---|---|---|---|---|
| Chart giá tích hợp | ❌ | ✅ | ✅ | ✅ Cần thêm |
| Cảnh báo realtime | ❌ | ✅ | ✅ | ✅ Cần thêm |
| Portfolio tracker | ❌ | ✅ | ❌ | ✅ Cần thêm |
| Quick scan preset | ❌ | ✅ | ✅ | ✅ Cần thêm |
| Giải thích AI | ❌ | ❌ | ❌ | ✅ Đã có (cần cải thiện vị trí) |
| T+2.5 countdown | ❌ | ❌ | ❌ | ✅ Unique differentiator |

---

## 3. Đề xuất UI/UX — Trang Profiler

### 3.1 Vấn đề hiện tại

- 13 tab hiển thị song song — trader không biết tab nào quan trọng hơn.
- Tab T+2.5 (tab thứ 8 trong 13) — thông tin quan trọng nhất trong workflow T+2.5 lại bị đặt sau "Horizon", "SMS/MCVD", "SHAP", "Overlay", "Chỉ số", "NLP", "F0".
- Không có chart OHLCV — trader phải mở Fireant/Simplize/SSI để xem biểu đồ.
- Real-time price header đơn giản (HTML div) nhưng không có màu nền thay đổi khi giá biến động mạnh.
- Signal card render bằng raw HTML — có nguy cơ mất style khi Streamlit cập nhật.

### 3.2 Đề xuất cải thiện

#### P3.1 — Tái cấu trúc tab thành 3 nhóm ưu tiên

```
NHÓM 1 — "Quyết định ngay" (hiển thị mặc định):
  [🎯 T+2.5 Plan]  [📡 Signal]  [📋 Entry/Exit]

NHÓM 2 — "Phân tích sâu" (accordion collapsed):
  [📊 SMS/CVD]  [🔭 Dự báo]  [⚠️ Cảnh báo]  [🔬 SHAP]

NHÓM 3 — "Nền tảng" (collapsed, cho analyst):
  [📈 Chỉ số]  [🧭 Macro/Cơ bản]  [📊 CVD Intraday]  [📖 Sổ lệnh]  [📝 NLP]  [🔰 F0]
```

**Lý do:** Trader T+2.5 chỉ cần biết "vào đâu, stop đâu, target T+2.5 bao nhiêu, thoát lúc nào" — thông tin này phải nằm trong 3 giây đầu tiên sau khi load.

#### P3.2 — Thêm Mini OHLCV Chart (Candlestick 20 ngày)

```python
# Component mới: src/tradingos/ui/components/ohlcv_chart.py
# Sử dụng plotly.graph_objects.Candlestick
# Overlay: SMA20, SMA50, Entry price, Stop loss, TP1, TP2 (horizontal lines)
# Màu: Entry=xanh lá, SL=đỏ, TP1=vàng, TP2=trắng
# Volume subplot bên dưới với màu xanh/đỏ theo chiều nến
```

**Spec:**
- Hiển thị 20 nến gần nhất (có thể chọn 5 / 20 / 60)
- Overlay SMA20 (vàng), SMA50 (xanh dương)
- Đường ngang: Entry, SL (-đỏ), TP1 (-vàng), TP2 (-trắng)
- Click nến → tooltip hiển thị OHLCV + Volume Z-score
- Không cần realtime tick — dùng cache OHLCV daily

#### P3.3 — T+2.5 Countdown Widget

Đây là **differentiator duy nhất** so với tất cả app trading khác trên thị trường VN.

```
┌─────────────────────────────────────────────────────────┐
│  ⏰ T+2.5 Exit Window                                    │
│  Ngày vào: T+0 = hôm nay → Ngày thoát: T+2 ATC         │
│  Còn: 2 ngày 4 giờ 17 phút đến cửa sổ ATC             │
│  ──────────────────────────────────────────             │
│  [T+0 Hôm nay] → [T+1 Thứ 3] → [T+2 Thứ 4 ATC ✨]    │
│  ─────────────────────────────────────────────          │
│  🎯 Kế hoạch thoát: ATC 14:43–14:45 Thứ 4              │
│  Target T+2.5: 28,500 (+4.8%)   Stop: 26,800 (-1.8%)   │
└─────────────────────────────────────────────────────────┘
```

**Implementation:** `st.empty()` + `time.sleep(1)` trong async thread hoặc `st.fragment` (Streamlit 1.37+)

#### P3.4 — Signal Card màu động

Hiện tại Signal Card dùng màu tĩnh cho action. Đề xuất thêm:
- **Pulse animation (CSS)** khi Action = STRONG_BUY hoặc FORCED_EXIT
- **Border glow** theo màu confidence: HIGH=xanh, MEDIUM=vàng, LOW=đỏ
- **Score Breakdown mini bar chart** ngay trong card — hiển thị Mode A/B/W score như 3 progress bar thay vì text

#### P3.5 — "Add to Portfolio" button

Ngay trong Profiler, thêm nút **"📥 Vào lệnh hôm nay"** → ghi nhận vào paper trading ledger với:
- Entry price = giá realtime hoặc entry_price đề xuất
- SL / TP1 / TP2 tự động từ profile
- Ngày vào = hôm nay (T+0)
- Tự động tính T+2 là ngày thoát dự kiến

---

## 4. Đề xuất UI/UX — Trang Scanner

### 4.1 Vấn đề hiện tại

- Form phức tạp với slider MFPM + SMS + Workers + Exchange — quá nhiều tham số cho trader không chuyên.
- Không có **Quick Filter preset** — trader phải nhớ ngưỡng tốt mỗi lần chạy.
- Kết quả trả về dạng table thô — không highlight rõ cơ hội tốt nhất.
- Không có sorting thông minh — hiện chỉ sort theo Action order, không tính đến context thị trường.
- Không có **Market Breadth indicator** — trader không biết thị trường đang tốt hay xấu trước khi scan.
- Column `Tóm tắt NLP` rất dài, làm hẹp các cột quan trọng hơn.

### 4.2 Đề xuất cải thiện

#### P4.1 — Quick Filter Preset

```
[🚀 T+2.5 Ready] [🐳 Whale Alert] [⚡ Breakout] [🛡 Defensive] [Custom →]

T+2.5 Ready preset:    MFPM≥70, SMS≥60, AMF=PASS, T+Verdict=MUA_NGAY/CHO_XAC_NHAN
Whale Alert preset:    SMS≥75, Stealth=True, M-CVD=UP
Breakout preset:       Mode=B, Pattern=VCP/Cup-with-Handle, Vol Z>2
Defensive preset:      MFPM≥50, AMD=ACCUMULATION, Macro=BULL
```

**UX:** Radio button group thay vì form collapse — trader có thể switch preset trong 1 click.

#### P4.2 — Market Breadth Header

Trước khi hiển thị scanner form, thêm dải **Market Context Banner**:

```
┌──────────────────────────────────────────────────────────────────┐
│  📊 Market Breadth (22/05/2026)                                  │
│  VN-Index: 1,287 (+0.8%)  |  Tăng: 187  |  Giảm: 112           │
│  Sector flow: Bank 🐳 | Steel ↗ | Real Estate ↘                 │
│  Macro: BULL 78/100  |  Khuyến nghị: ✅ Phù hợp để scan T+2.5  │
└──────────────────────────────────────────────────────────────────┘
```

**Logic:** Lấy từ `macro_score_gate_adjustment()` đã có sẵn + aggregate sector flows từ `MoneyFlowService`.

#### P4.3 — Scanner Result Cards (thay vì chỉ table)

Thêm chế độ **Card View** bên cạnh Table View:

```
┌───────────────────────────────────┐
│  VCB  🚀 STRONG_BUY  HIGH        │
│  27,500  →  Entry: 27,200        │
│  SL: 25,900 (-4.8%)  TP1: 29,800 │
│  SMS: 78 🐳  T+: MUA_NGAY        │
│  MFPM: 98  Mode: W  Pattern: VCP  │
│  [🔍 Xem chi tiết] [📥 Vào lệnh] │
└───────────────────────────────────┘
```

**UX:** Grid 3 cột (3 cards / row) — trader nhìn thấy top 6-9 cơ hội ngay lập tức mà không cần scroll.

#### P4.4 — Inline Sparkline

Mỗi hàng trong table (hoặc card) thêm **sparkline 20 ngày** — mini chart width 80px. Trader nhận biết xu hướng giá ngay mà không cần mở Profiler.

```python
# plotly.express.line() với height=30, width=80, no axis, transparent bg
# Đường xanh = uptrend, đỏ = downtrend
```

#### P4.5 — Column Visibility Toggle

Ẩn các cột ít dùng mặc định (Tóm tắt NLP, Days→BCTC, FVG zones...) và có nút "Hiện thêm cột" để expand. Giữ 12 cột cốt lõi mặc định:

```
[Mã] [Action] [Conf] [MFPM] [SMS] [T+Verdict] [Giá] [Vào] [SL] [TP1] [AMF] [Pattern]
```

#### P4.6 — Export Enhancements

- Thêm **Copy to Clipboard** (không chỉ download CSV)
- Thêm format Markdown table — để paste vào Telegram/Zalo cho nhóm giao dịch
- Thêm tóm tắt "Sáng nay hệ thống tìm được X mã STRONG_BUY, Y mã BUY..." dạng copyable headline

---

## 5. Đề xuất UI/UX — Trang Performance

### 5.1 Vấn đề hiện tại

- Không có cách nhập kết quả giao dịch thực — chỉ đọc từ `trade_ledger` nhưng không có UI để thêm/sửa entry.
- Không hiển thị **open positions T+2.5 countdown** — trader không biết mã nào đến ngày thoát.
- Equity curve không thể so sánh với VN-Index benchmark.
- Calmar/Sharpe ratio không có giải thích ngữ cảnh cho trader Việt.
- Không có **Winner/Loser analysis** theo sector, mode, time-of-month.

### 5.2 Đề xuất cải thiện

#### P5.1 — Open Positions T+2.5 Dashboard

Đây là **màn hình quan trọng nhất cho trader đang nắm cổ phiếu**.

```
┌──────────────────────────────────────────────────────────────────┐
│  📂 Danh mục đang nắm (Open Positions)                           │
├────┬────────┬────────┬────────┬────────┬──────────┬────────────┤
│ Mã │ Vào   │ Giá RT │ P&L%   │ SL     │ TP1      │ Thoát T+2.5│
├────┼────────┼────────┼────────┼────────┼──────────┼────────────┤
│VCB │ 27,200│ 27,800 │ +2.2%  │ 25,900 │ 29,800   │ ⏰ 1 ngày  │
│HPG │ 14,500│ 14,200 │ -2.1%  │ 13,600 │ 16,000   │ ⏰ 2 ngày  │
│SSI │ 18,000│ 18,900 │ +5.0%  │ 17,000 │ 20,000   │ 🚨 Hôm nay!│
└────┴────────┴────────┴────────┴────────┴──────────┴────────────┘
│ SSI: T+2.5 ATC hôm nay! Đề xuất: SELL_FULL_ATC 14:43           │
└──────────────────────────────────────────────────────────────────┘
```

**Dữ liệu cần:** Paper trade ledger (đã có) + realtime price (đã có trong Profiler) + T+0 date.

#### P5.2 — Manual Trade Entry Form

```
[+ Thêm giao dịch thực]
  Mã: ___  Ngày vào: ___  Giá vào: ___  Số lượng: ___
  SL: ___  TP1: ___  Source: [Scanner/Profiler/Thủ công]
  [💾 Lưu]
```

Kết nối vào `cache.add_to_trade_ledger()` — cần implement method này.

#### P5.3 — Benchmark Comparison

```python
# Thêm VN-Index daily return vào equity curve
# Tính Alpha = Portfolio return - VN-Index return
# Hiển thị: "Hệ thống vượt trội VN-Index +12.3% trong 6 tháng"
```

#### P5.4 — Phân tích thất bại (Loss Analysis)

Section mới "📉 Phân tích lệnh thua":
- Top 5 lệnh thua nặng nhất + lý do (AMF signal? Macro bearish? Wrong mode?)
- Phân phối P&L histogram — nhìn thấy distribution của lợi nhuận
- Heatmap lệnh theo thứ trong tuần × tuần trong tháng — tìm "blind spots"

---

## 6. Đề xuất UI/UX — Trang Dòng tiền (DTL)

### 6.1 Vấn đề hiện tại

- 3 tab (SMS Watchlist, M-CVD Chart, Sector Rotation) nhưng **không có tổng quan dòng tiền thị trường** — trader không biết ngành nào đang "hot".
- Mỗi tab đều yêu cầu nhấn button riêng — không có auto-load.
- Sector Heatmap không rõ metrics đang hiển thị (SMS? M-CVD? Both?).
- Không có lịch sử sector rotation — không thể biết ngành nào đang tăng trưởng momentum.

### 6.2 Đề xuất cải thiện

#### P6.1 — Real-time Money Flow Ticker

Thêm ticker bar ngang ở đầu trang (giống Bloomberg ticker):
```
🐳 VCB: +125M | 🐳 HPG: +89M | ↗ SSI: +32M | ↘ VIC: -45M | ...
```
Tự động refresh mỗi 5 phút.

#### P6.2 — Sector Rotation Clock (Phase Wheel)

Thay sector heatmap tĩnh bằng **sector rotation wheel** — visualization dạng đồng hồ với 11 sector positions:

```
         LEADING (Sắp đỉnh)
    Real Estate     Banking
  Energy              Steel
LAGGING              IMPROVING
  Pharma              Tech
    Consumer    Industrial
         WEAKENING
```

Mỗi sector là bubble với size = tổng dòng tiền, color = momentum tốt/xấu.

#### P6.3 — Dòng tiền nước ngoài vs nội địa

Thêm panel:
```
Foreign Net Flow (5 ngày):
  Mua: VCB (+125B), HPG (+67B), SSI (+34B)
  Bán: VIC (-89B), VHM (-45B)
  
Domestic Institutional Estimate:
  M-CVD TOP: FPT (+89M), MWG (+67M)
```

---

## 7. Đề xuất UI/UX — Trang Backtest

### 7.1 Vấn đề hiện tại

- Chỉ backtest 1 mã tại một thời điểm — không có multi-ticker backtest.
- Không có parameter sweep — trader muốn tìm SL/TP optimal.
- Walk-forward windows ẩn trong expander — mặc định collapsed.
- Không có so sánh với buy-and-hold benchmark.
- Trade list bị giới hạn 50 lệnh đầu (`bt.trades[:50]`) — mất dữ liệu.

### 7.2 Đề xuất cải thiện

#### P7.1 — Basket Backtest

```python
# Cho phép nhập danh sách mã: VCB, HPG, SSI, FPT
# Backtest toàn danh mục với position sizing Kelly
# Output: Portfolio-level equity curve + per-ticker breakdown
```

#### P7.2 — Parameter Optimization Grid

```
SL range: [3%, 4%, 5%, 6%, 7%, 8%]  × TP1 multiplier: [1.5, 2.0, 2.5, 3.0]
→ Heatmap 6×4 = 24 combinations
→ Highlight cell tốt nhất (Max Sharpe hoặc Max Profit Factor)
```

#### P7.3 — Buy-and-Hold Comparison

```python
# Thêm đường BnH vào equity curve
# Tính outperformance: "Mode W vượt B&H 34.2% trong 2022-2024"
```

#### P7.4 — Walk-Forward Auto-Display

Remove expander, hiển thị walk-forward windows mặc định dưới equity curve.

---

## 8. Đề xuất UI/UX — Trang Audit

### 8.1 Vấn đề hiện tại

- Audit log là bảng phẳng không có grouping — khó đọc lịch sử 1 mã theo thời gian.
- Timeline component (`audit_timeline.py`) render stats aggregate nhưng không có visual timeline.
- Không có filter theo "mã đang nắm giữ" — không thể track lifecycle của 1 lệnh.

### 8.2 Đề xuất cải thiện

#### P8.1 — Ticker Timeline View

```
VCB History:
  22/05  15:30  SCAN     → STRONG_BUY  MFPM=98  SMS=82  T+=MUA_NGAY
  22/05  09:45  PROFILE  → BUY         MFPM=91  SMS=78  T+=CHO_XAC_NHAN
  21/05  16:00  SCAN     → BUY         MFPM=85  SMS=71
```

**Implementation:** Group by ticker, sort by timestamp DESC — render dạng `st.timeline` hoặc custom HTML timeline component.

#### P8.2 — Signal Accuracy Heatmap

```
Mỗi tín hiệu STRONG_BUY/BUY có được mark là WIN/LOSS không?
Heatmap: Confidence × Mode → Win Rate
HIGH+ModeW = 71%, MEDIUM+ModeA = 58%, LOW+ModeB = 43%
```

**Cần:** Liên kết audit_event với trade outcome trong ledger (join trên ticker + date range).

---

## 9. Đề xuất UI/UX — Trang Cài đặt

### 9.1 Vấn đề hiện tại

- Config viewer chỉ read-only JSON — không thể chỉnh từ UI.
- Watchlist manager chỉ add/view, không có bulk import từ CSV/text.
- Database section chỉ show table names — không có stats (số rows, size, last update).
- Không có API connection test button — không biết FiinQuant/DNSE đang kết nối được không.

### 9.2 Đề xuất cải thiện

#### P9.1 — API Health Check Panel

```
┌───────────────────────────────────────────────────────┐
│  🔌 Kết nối API                                       │
│  SSI iBoard:    ✅ Connected (latency: 234ms)         │
│  DNSE:          ✅ Connected                          │
│  FiinQuant:     ❌ Not configured — CVD dùng proxy   │
│  VNDirect:      ✅ Connected (fallback)               │
│  [Test All]                                           │
└───────────────────────────────────────────────────────┘
```

#### P9.2 — Strategy Config Editor

Cho phép chỉnh nhanh các tham số quan trọng từ UI:
```
RSI Entry Zone: [40 → 55]  (slider)
SL ATR Multiplier: 1.5    (number input)
Kelly Max %: 25%           (slider)
MFPM BUY Threshold: 70    (slider)
[💾 Lưu và áp dụng]       → write to local.toml
```

#### P9.3 — Watchlist Bulk Import

```
[📋 Paste danh sách] textarea
[📁 Import CSV]
[🔄 Sync từ Scanner kết quả cuối]  ← auto-add top BUY/STRONG_BUY vào watchlist
```

#### P9.4 — Database Maintenance

```
DuckDB stats:
  audit_events: 1,247 rows (2.3 MB) — last: 22/05 15:30
  trade_ledger: 89 rows (0.1 MB)   — last: 21/05 14:43
  ohlcv_cache:  145,231 rows (12 MB)
  
[🗑 Xóa audit > 90 ngày]  [🗑 Xóa OHLCV > 2 năm]  [💾 Backup DB]
```

---

## 10. Đề xuất — Dashboard tổng hợp T+2.5

### 10.1 Trang "Morning Briefing" (NEW)

Đây là trang quan trọng nhất cần thêm — **homepage thực sự** của TradingOS.

**Khái niệm:** Trader mở app lúc 8:45 sáng trước khi phiên mở. Trong 30 giây đầu, họ cần biết:

1. Thị trường hôm nay như thế nào (macro, breadth)?
2. Danh mục đang nắm → mã nào đến ngày T+2.5 thoát?
3. Top cơ hội mới nhất từ scanner đêm trước?
4. Có cảnh báo nào đặc biệt không (AMF, distribution warning)?

```
┌──────────────────────────────────────────────────────────────────────┐
│  ☀️ Morning Briefing — Thứ 5, 22/05/2026                            │
│  VN-Index: 1,287 (+0.8%)  |  Phiên: ATO sắp mở (còn 15 phút)      │
├──────────────────────────────────────────────────────────────────────┤
│  ⚠️ HÀNH ĐỘNG HÔM NAY                                               │
│  🚨 SSI — T+2.5 ATC HÔM NAY (14:43) — Target: 19,500 (+5.1%)      │
│  ⏰ VCB — T+2.5 ngày mai — đang lãi +2.2%, hold                    │
├──────────────────────────────────────────────────────────────────────┤
│  🎯 CƠ HỘI MỚI (Scanner đêm qua)                                   │
│  1. FPT  STRONG_BUY  MFPM=95  SMS=81  T+=MUA_NGAY  Pattern=VCP     │
│  2. MWG  BUY         MFPM=82  SMS=72  T+=CHO_XAC_NHAN              │
│  3. HPG  BUY         MFPM=79  SMS=65  T+=MUA_NGAY   Pattern=Wyck.  │
├──────────────────────────────────────────────────────────────────────┤
│  📊 Dòng tiền sáng nay                                              │
│  Ngành mạnh: Ngân hàng 🐳  |  Ngành yếu: BĐS ↘                    │
│  VN-Index: BULL 78/100  |  Macro: Phù hợp mua T+2.5               │
└──────────────────────────────────────────────────────────────────────┘
```

**Implementation:**
- `_morning_briefing.py` là page mới, set làm default page trong `app.py`
- Load data từ cache (scan result từ lần chạy cuối, không re-scan)
- T+2.5 countdown tính từ trade_ledger entries với `status=OPEN`
- Macro banner lấy từ `macro_score_gate_adjustment()` output

### 10.2 Trang "ATC Alert" (NEW — 14:30-14:45)

Trang này tự động trở thành "active" khi đến gần cửa sổ ATC:

```
┌──────────────────────────────────────────────────────────────────┐
│  ⚡ ATC MODE — 14:35 (còn 8 phút đến ATC 14:43)                 │
│  ─────────────────────────────────────────────────────────────   │
│  📋 LỆNH CẦN XỬ LÝ HÔM NAY:                                     │
│                                                                   │
│  🔴 SSI  SELL_FULL_ATC  [Giá RT: 19,450]  [Lãi: +8.1%]         │
│     Lý do: T+2.5 đã đủ thời gian giữ. TP1=19,500 gần đạt.      │
│     → Đặt lệnh ATC bán toàn bộ trong 14:43–14:45               │
│                                                                   │
│  🟡 VCB  SELL_PARTIAL_ATC  [Giá RT: 27,850]  [Lãi: +2.4%]     │
│     Lý do: T+3 tiếp cận nhưng chưa đạt TP1. Bán 40%.          │
│     → Bán 40%, giữ 60% để extend.                               │
└──────────────────────────────────────────────────────────────────┘
```

**Trigger:** `_session_phase()` trong `t25_engine.py` đã có sẵn. Dùng `st.fragment` auto-refresh mỗi 60 giây khi phase = "NEAR_CLOSE" hoặc "ATC".

---

## 11. Đề xuất — Navigation & Layout hệ thống

### 11.1 Vấn đề hiện tại

- Sidebar navigation dùng `st.radio` — không hỗ trợ sub-menu, badge, notification count.
- Logo là URL external (`img.icons8.com`) — sẽ lỗi khi không có internet.
- Tất cả 7 trang có trọng số như nhau trong navigation, không phân cấp.
- Không có **breadcrumb** — sau khi click từ Scanner → Profiler, không có nút "< Quay lại Scanner".

### 11.2 Đề xuất cải thiện

#### P11.1 — Navigation Hierarchy

```
HÀNH ĐỘNG
  🌅 Morning Briefing        ← New (default page)
  🔍 Profiler
  📡 Scanner
  📂 Danh mục & T+2.5        ← Rename từ Performance, mở rộng scope

PHÂN TÍCH
  🐳 Dòng tiền
  📊 Backtest

HỆ THỐNG
  🗂 Audit
  ⚙️ Cài đặt
```

**Implementation:** Streamlit sidebar với section headers (st.caption) phân nhóm.

#### P11.2 — Notification Badge

```python
# Trong sidebar, hiện badge đỏ nếu:
# - Có T+2.5 đến hạn hôm nay: "📂 [1]"
# - Có FORCED_EXIT signal trong audit gần nhất: "🗂 [⚠️]"
```

#### P11.3 — Quick Ticker Search

Header bar (top of page) với:
```
[🔍 Nhập mã...] → Enter → navigate to Profiler với ticker đó
```

**Implementation:** `st.text_input` trong header area + `st.session_state` redirect.

---

## 12. Đề xuất — Cải thiện Business Logic & Engine

### 12.1 T+2.5 Engine Enhancements

#### B12.1 — Dynamic T+2.5 Window Based on Signal Strength

Hiện tại T+2.5 luôn exit tại ATC T+2. Đề xuất logic nâng cao:

```python
if tplus_confidence >= 90 and pnl_pct < tp1_pct * 0.7:
    # Chưa đạt 70% đường đến TP1 — extend to T+5
    return EXTEND
elif tplus_confidence >= 75 and distribution_warning == "NONE":
    # Tín hiệu tốt, có thể hold thêm 1-2 ngày
    return SELL_PARTIAL_ATC  # Bán 40%, hold 60%
else:
    return SELL_FULL_ATC  # Default T+2.5
```

#### B12.2 — ATC Volume Estimate

Thêm ước tính khối lượng cần bán ATC để thoát trong 1 phiên:
```python
estimated_atc_volume_capacity = avg_volume_20d * 0.15  # ATC ~15% of daily volume
position_size_shares = sizing_shares
is_executable_at_atc = position_size_shares < estimated_atc_volume_capacity
```

Nếu `is_executable_at_atc == False` → cảnh báo: "⚠️ Vị thế lớn — cân nhắc bán dần từ 14:00".

#### B12.3 — T+1 Check Alert

Hiện tại hệ thống chỉ có T+2.5 exit. Đề xuất thêm **T+1 Mid-review**:
- Nếu pnl < -3% tại T+1 → cảnh báo "Đang tiến gần SL — review"
- Nếu pnl > TP1 tại T+1 → cảnh báo "Đạt target sớm — cân nhắc thoát sớm"

### 12.2 Scanner Performance

#### B12.4 — Incremental Scan (Delta Update)

Vấn đề: Full scan HOSE (~400 mã) mất 3-8 phút.

```python
# Chỉ re-scan mã có OHLCV thay đổi so với lần scan trước
# Dùng: DuckDB hash(last_close, volume) để detect change
# Ước tính: Tiết kiệm 60-70% thời gian scan khi thị trường ổn định
```

#### B12.5 — Background Scanner Daemon

```python
# Service chạy nền mỗi 15 phút, ghi kết quả vào DuckDB
# UI chỉ đọc cached result, không chạy scan real-time
# → Profiler load ngay lập tức từ cache thay vì chờ 5-15s
```

### 12.3 Risk Management Enhancements

#### B12.6 — Portfolio-Level Risk Check

Trước khi "Vào lệnh", kiểm tra:
```python
total_exposure = sum(open_positions_pct)  # Tổng danh mục đang nắm
if total_exposure + new_position_pct > 0.8:  # Không quá 80% portfolio
    warning("⚠️ Danh mục đang nắm {total_exposure:.0%} — rủi ro cao khi thêm")
    
# Correlation check: Nếu mã mới cùng sector với 2+ mã đang nắm → cảnh báo
if sector_concentration > 0.4:
    warning("⚠️ Tập trung sector {sector} > 40%")
```

#### B12.7 — Market Halt / Circuit Breaker Detection

```python
# VN-Index giảm > 7% trong phiên → circuit breaker rule
# Tự động đổi tất cả STRONG_BUY → WATCH
# Thêm banner đỏ: "⚠️ VN-Index giảm mạnh — hệ thống đã tự động hạ cấp tín hiệu"
```

---

## 13. Đề xuất — Alerting & Notification System

### 13.1 Vấn đề hiện tại

TradingOS hoàn toàn là pull-based — trader phải chủ động mở app để biết tình trạng. Không có push notification.

### 13.2 Đề xuất

#### A13.1 — Telegram Bot Integration (HIGH PRIORITY)

```python
# config/local.toml
# [notification]
# telegram_bot_token = "..."
# telegram_chat_id = "..."

# Trigger notification khi:
# 1. Scanner tìm thấy STRONG_BUY mới sau lần scan trước
# 2. Mã đang nắm chạm SL → SELL_FULL_ATC HIGH urgency
# 3. Đến 14:30 → nhắc danh sách mã cần xem xét thoát ATC
# 4. Macro chuyển từ BULL → BEAR
```

**Message format:**
```
🚀 TradingOS Alert
FPT — STRONG_BUY (MFPM=95, SMS=81)
Entry: 78,500 | SL: 73,800 | TP1: 90,000
T+ Verdict: MUA_NGAY
Xem chi tiết: [link tới app]
```

#### A13.2 — ATC Reminder (14:30 daily)

Mỗi ngày lúc 14:30, tự động:
1. Chạy `t25_exit_check()` cho tất cả open positions
2. Gửi Telegram/Email summary: "Hôm nay cần thoát: SSI (SELL_FULL), VCB (SELL_PARTIAL)"
3. Hiển thị banner đỏ trong app

#### A13.3 — Watchlist Monitor

Background service theo dõi watchlist mỗi 30 phút:
- Nếu mã trong watchlist chuyển từ WATCH → BUY → alert
- Nếu mã đang trong portfolio chạm SL → alert khẩn

---

## 14. Đề xuất — Mobile-Responsive / PWA

### 14.1 Vấn đề hiện tại

Streamlit trên mobile hiển thị khá kém:
- Sidebar chiếm gần hết màn hình nhỏ
- Multi-column layout bị vỡ khi viewport < 768px
- Scanner table với 30+ cột không đọc được trên mobile

### 14.2 Đề xuất

#### M14.1 — Mobile-First Profiler View

Tạo `profiler_mobile.py` — view tối giản:
```
[Signal Card: 4 metrics] [T+2.5 Box: Entry/SL/TP] [SMS Gauge]
→ "Xem đầy đủ ↓" accordion cho các tab còn lại
```

#### M14.2 — PWA Configuration

```python
# .streamlit/config.toml
# [server]
# enableStaticServing = true
# + manifest.json cho PWA
```

Cho phép "Add to Home Screen" trên điện thoại — trader có app icon ngay trên màn hình.

#### M14.3 — Condensed Scanner untuk Mobile

Khi detect mobile (user agent hoặc viewport):
- Hiển thị max 6 cột: Mã, Action, MFPM, T+Verdict, Giá, T+Exit
- Card view thay vì table

---

## 15. Lộ trình triển khai

### Ưu tiên theo tác động × nỗ lực

| ID | Đề xuất | Tác động | Nỗ lực | Priority |
|---|---|---|---|---|
| P5.1 | Open Positions T+2.5 Dashboard | 🔴 Cao | M | **P0** |
| P10.1 | Morning Briefing page | 🔴 Cao | M | **P0** |
| P10.2 | ATC Alert mode | 🔴 Cao | S | **P0** |
| P3.2 | Mini OHLCV Chart trong Profiler | 🔴 Cao | M | **P1** |
| P3.3 | T+2.5 Countdown Widget | 🔴 Cao | S | **P1** |
| P4.1 | Quick Filter Preset trong Scanner | 🟠 Trung bình-Cao | S | **P1** |
| P4.2 | Market Breadth Header | 🟠 Trung bình | S | **P1** |
| P3.1 | Tái cấu trúc Profiler tabs | 🔴 Cao | M | **P1** |
| P3.5 | "Add to Portfolio" button | 🟠 Trung bình-Cao | S | **P1** |
| A13.1 | Telegram Bot Integration | 🔴 Cao | M | **P1** |
| P4.3 | Scanner Card View | 🟠 Trung bình | M | **P2** |
| P9.1 | API Health Check Panel | 🟠 Trung bình | S | **P2** |
| P5.2 | Manual Trade Entry Form | 🟠 Trung bình | S | **P2** |
| B12.4 | Incremental Scan | 🟠 Trung bình | L | **P2** |
| P4.6 | Export to Markdown/Clipboard | 🟡 Thấp | S | **P3** |
| B12.6 | Portfolio-Level Risk Check | 🟠 Trung bình | M | **P2** |
| P7.1 | Basket Backtest | 🟡 Thấp-Trung bình | L | **P3** |
| M14.1 | Mobile-First Profiler View | 🟠 Trung bình | M | **P3** |
| B12.5 | Background Scanner Daemon | 🟠 Trung bình | L | **P3** |

### Sprint Plan (3 Sprint × 2 tuần)

```
Sprint 1 (P0+P1 — 2 tuần):
  - Morning Briefing page
  - Open Positions T+2.5 Dashboard
  - ATC Alert countdown
  - T+2.5 Countdown widget trong Profiler
  - Quick Filter Preset trong Scanner
  - "Add to Portfolio" button

Sprint 2 (P1+P2 — 2 tuần):
  - Mini OHLCV Chart component
  - Profiler tab restructure
  - Market Breadth Header
  - Telegram Bot notification
  - Manual Trade Entry Form
  - API Health Check Panel

Sprint 3 (P2+P3 — 2 tuần):
  - Scanner Card View
  - Portfolio-Level Risk Check
  - Incremental Scan optimization
  - Export to Markdown
  - Mobile-First view
```

---

## 16. Phụ lục — Mockup mô tả giao diện

### 16.1 Morning Briefing — Layout

```
┌─ Sidebar ────────────────┬─ Main Content ────────────────────────────────────┐
│ [🌅 Morning Briefing] ←  │  ☀️ Morning Briefing — Thứ 5, 22/05/2026 08:47   │
│ [🔍 Profiler]            │  VN-Index: 1,287 (+0.8%) | ATO mở sau 13 phút   │
│ [📡 Scanner]          [1]│  ─────────────────────────────────────────────── │
│ [📂 Danh mục T+2.5]  [2]│  ⚠️ HÀNH ĐỘNG HÔM NAY                           │
│ ──────────────────────   │  🚨 SSI → ATC 14:43 HÔM NAY    [Xem chi tiết →] │
│ PHÂN TÍCH                │  ⏰ VCB → T+2.5 ngày mai                         │
│ [🐳 Dòng tiền]           │                                                   │
│ [📊 Backtest]            │  🎯 CƠ HỘI MỚI (Scanner 22:00 hôm qua)          │
│ ──────────────────────   │  ┌──────────┬──────────┬──────────┐              │
│ HỆ THỐNG                 │  │FPT 🚀    │MWG 🟢    │HPG 🟢    │              │
│ [🗂 Audit]               │  │MFPM=95   │MFPM=82   │MFPM=79   │              │
│ [⚙️ Cài đặt]             │  │T+=MUA    │T+=CHỜ    │T+=MUA    │              │
│                          │  │[→ Profile]│[→Profile]│[→Profile]│              │
│                          │  └──────────┴──────────┴──────────┘              │
└──────────────────────────┴───────────────────────────────────────────────────┘
```

### 16.2 Profiler — Tab Ưu tiên Mới

```
[🎯 T+2.5 Plan*] [📡 Signal] [📋 Entry/Exit] | [📊 SMS/CVD ▼] [🔭 Dự báo ▼] [... ▼]
─────────────────────────────────────────────────────────────────────────────────
  ┌─────────────────────────────────┐   ┌──────────────────────────────────┐
  │  ⏰ T+2.5 Countdown             │   │  📈 OHLCV Chart (20 nến)          │
  │  T+0: 22/05 (Hôm nay)          │   │  [candlestick plot with SMA20/50] │
  │  T+2.5: 27/05 ATC              │   │  Entry ─────── (green line)       │
  │  ⏱ Còn 3 ngày 5 giờ           │   │  TP1 ─ ─ ─ ─ (yellow dashed)    │
  │  ● T+0 ── ● T+1 ── ● T+2 ATC  │   │  SL ─ ─ ─ ─ ─ (red dashed)     │
  ├─────────────────────────────────┤   └──────────────────────────────────┘
  │  Target T+2.5: 29,800 (+4.8%)  │
  │  Stop: 25,900 (-4.8%)          │
  │  Exit: ATC 14:43–14:45 ngày T+2│
  └─────────────────────────────────┘
  *Tab mặc định khi mở Profiler
```

### 16.3 ATC Alert Mode — Full Screen

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⚡ ATC MODE ACTIVE — 14:38 | Còn 5 phút | Phiên HOSE đang NEAR_CLOSE      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  🔴 SSI   SELL_FULL_ATC                                                     │
│  Vào: 18,000 | RT: 19,450 | Lãi: +8.1% | Hold: 3 ngày                     │
│  "T+2.5 đã đủ thời gian. Đạt gần TP1. Thoát toàn bộ ATC hôm nay."        │
│  ─────────────────────────────────────────────────────────────────          │
│                                                                              │
│  🟡 VCB   SELL_PARTIAL_ATC (40%)                                           │
│  Vào: 27,200 | RT: 27,800 | Lãi: +2.2% | Hold: 3 ngày                     │
│  "Tiến tốt nhưng chưa đạt TP1. Bán 40% để khóa lãi, giữ 60% extend."     │
│  ─────────────────────────────────────────────────────────────────          │
│                                                                              │
│  [✅ Đã thực hiện SSI]  [✅ Đã thực hiện VCB]  [⏸ Bỏ qua phiên này]      │
│                                                                              │
│  ⏱ Auto-refresh: 60s | Next check: 14:39:00                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Ghi chú kỹ thuật

### Dependency mới cần thêm

```toml
# requirements.txt additions
python-telegram-bot>=20.0  # Telegram notification
apscheduler>=3.10          # Background scanner daemon
pytz>=2024.1               # VN timezone handling (đã có vn_now())
```

### Streamlit features cần dùng

```python
# Auto-refresh cho ATC Mode
@st.fragment(run_every=60)  # Streamlit 1.37+ fragment auto-rerun
def atc_monitor():
    ...

# st.dialog() cho Quick Entry Form (Streamlit 1.36+)
@st.dialog("📥 Vào lệnh")
def entry_dialog(profile):
    ...

# st.status() cho Scanner progress (better UX than spinner)
with st.status("Đang quét 400 mã...") as status:
    for ticker in universe:
        status.write(f"Đang xử lý {ticker}...")
```

### Component độc lập cần tạo

| File | Mục đích |
|---|---|
| `ui/components/ohlcv_chart.py` | Candlestick chart với overlay entry/SL/TP |
| `ui/components/t25_countdown.py` | T+2.5 countdown timer widget |
| `ui/components/market_breadth.py` | Market context banner |
| `ui/components/position_card.py` | Open position card với T+2.5 status |
| `ui/pages/_morning_briefing.py` | Morning briefing homepage |
| `ui/pages/_atc_alert.py` | ATC mode full screen |
| `engines/notification_service.py` | Telegram/Email push notification |
| `engines/portfolio_tracker.py` | Open position lifecycle manager |

---

*Tài liệu này là đề xuất — mọi implementation cần review business impact và test kỹ trước khi deploy.*  
*Phiên bản tiếp theo: v1.1 sau Sprint 1 review.*
