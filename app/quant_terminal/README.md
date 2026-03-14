# Captain Seventh Quant Terminal

**Version:** 1.0.0 · **Released:** 2026-03-14 · **Status:** ✅ Production  
Real-time portfolio intelligence for Vietnam equity markets (HOSE/HNX/UPCOM).  
Built on SSI iBoard API · Python · Streamlit.

> 📄 **Full documentation:** [`docs/`](docs/)  
> — [BRD.md](docs/BRD.md) · [RELEASE_NOTES.md](docs/RELEASE_NOTES.md) · [USER_GUIDE.md](docs/USER_GUIDE.md)

---

## Cài đặt

### Bước 1 — Clone / giải nén thư mục app

```bash
cd ~/Documents
# Đặt thư mục quant_terminal vào đây
```

### Bước 2 — Tạo virtual environment

```bash
cd quant_terminal
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
```

### Bước 3 — Cài dependencies

```bash
pip install -r requirements.txt
```

### Bước 4 — Cấu hình (tuỳ chọn)

Chỉnh file `config.py`:
- `PORTFOLIO_DIR` — thư mục chứa file Excel SSI iBoard
- `SSI_USER` / `SSI_PASSWORD` — dùng biến môi trường (không hardcode)
- `DATA_SOURCE` — mặc định là "SSI"

```bash
# Cách đặt credentials (an toàn hơn hardcode)
export SSI_USER="your_username"
export SSI_PASSWORD="your_password"
```

### Bước 5 — Chạy app

```bash
streamlit run app.py
```

Trình duyệt tự mở tại `http://localhost:8501`

---

## Cách sử dụng

### Upload portfolio từ SSI iBoard

1. Đăng nhập [iboard.ssi.com.vn](https://iboard.ssi.com.vn)
2. Vào **Tài sản** → **Danh mục chứng khoán**
3. Nhấn **Export** → chọn định dạng Excel (.xlsx)
4. Upload file vào sidebar của app **hoặc** đặt thẳng vào:

```
~/Documents/quant_terminal/portfolio/
```

App tự động phát hiện file mới nhất trong thư mục này.

### Các tab chức năng

| Tab | Chức năng |
|-----|-----------|
| 📊 Danh Mục | P&L real-time, heat map, signal digest toàn danh mục |
| 🔍 Phân Tích | Technical signals, kịch bản Bull/Base/Bear, kế hoạch lệnh |
| 🌐 Thị Trường | VNINDEX chart, macro events, alpha vs index |
| 📋 Trade Log | Lịch sử giao dịch, snapshot hiệu suất |
| ⚡ Rủi Ro | VaR, CVaR, correlation matrix, Kelly Criterion sizing |

> Xem [docs/USER_GUIDE.md](docs/USER_GUIDE.md) để hướng dẫn chi tiết từng tab.

### Lưu snapshot

Nhấn **"Lưu snapshot danh mục"** trong tab Danh Mục sau mỗi ngày giao dịch.
App dùng các snapshot này để tính hiệu suất theo thời gian.

---

## Cấu trúc thư mục

```
quant_terminal/
├── app.py                  # Main Streamlit app (entry point)
├── config.py               # Cấu hình: paths, API, tham số giao dịch
├── requirements.txt        # Dependencies
├── test_smoke.py           # 10 smoke tests — must pass before any release
├── docs/                   # SDLC documentation
│   ├── BRD.md              # Business Requirements Document
│   ├── RELEASE_NOTES.md    # Version history + feature specs
│   └── USER_GUIDE.md       # Full user manual
└── modules/
    ├── ssi_fetcher.py      # SSI iBoard REST client (primary data source)
    ├── data_fetcher.py     # Data pipeline + cache (SSI → VCI → TCBS → mock)
    ├── portfolio.py        # Load/save/enrich portfolio from SSI Excel
    ├── analysis.py         # RSI, MACD, BB, EMA, Beta, VaR, S/R
    └── scenarios.py        # Scenario engine + Kelly + order builder
```

Dữ liệu lưu tại:
```
~/Documents/quant_terminal/
├── portfolio/      ← File Excel SSI iBoard
├── trade_log/      ← JSON snapshots + trade log
└── .cache/         ← Cache giá (tự động)
```

---

## Nâng cấp sau (Backlog)

| Sprint | Feature | Status |
|--------|---------|--------|
| Sprint 2 | Backtesting engine (walk-forward validation) | 📋 Planned |
| Sprint 2 | Sector rotation dashboard | 📋 Planned |
| Sprint 3 | Alert system (Telegram/email khi giá chạm target) | 📋 Planned |
| Sprint 3 | Statistical arbitrage pairs screener | 📋 Planned |
| Sprint 4 | WebSocket real-time feed (ssi-fcdata) | 📋 Planned |
| Phase 4 | US equities via Interactive Brokers API | 🔮 Roadmap |
| Phase 4 | Crypto systematic strategies | 🔮 Roadmap |

---

*© 2026 Captain Seventh Quant Terminal · SDLC-compliant per PMBOK + BABOK v3*

## Nguồn dữ liệu

- **Giá thời gian thực**: SSI iBoard API qua thư viện `vnstock`
- **Lịch sử OHLCV**: SSI / VCI / TCBS (cấu hình trong `config.py`)
- **Chỉ số tài chính**: SSI Research API
- **Nếu API không khả dụng**: App tự động dùng dữ liệu mock để demo

---

## License

Dự án cá nhân — không phân phối lại.
Không phải lời khuyên đầu tư chuyên nghiệp.
