# 🇻🇳 Vietnam AI Trading System v3

**Full AI-powered trading system for Vietnam stock market (HOSE / HNX / UPCOM)**

Production pipeline: Data → Features → ML/DL Models → 5 Trading Strategies → Backtest → API

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                │
│  TCBS API → VCI API → CafeF News → Synthetic Fallback      │
├─────────────────────────────────────────────────────────────┤
│                    FEATURES                                  │
│  13+ Technical Indicators │ Vietnamese Sentiment (180+ terms)│
├─────────────────────────────────────────────────────────────┤
│                    ML MODELS                                 │
│  XGBoost (Walk-Forward) │ BiLSTM (PyTorch) │ Lasso │ Ensemble│
├─────────────────────────────────────────────────────────────┤
│                    5 STRATEGIES                              │
│  1W Momentum │ 2W Swing │ 1M Position │ 3M Cycle │ 5M Value │
├─────────────────────────────────────────────────────────────┤
│                    RISK / BACKTEST / API                     │
│  ATR Sizing │ Stop-Loss │ Portfolio │ Metrics │ FastAPI      │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure
```
vietnam-trading-app-v3/
├── config/settings.py           # API endpoints, params, VN30 tickers
├── data/
│   ├── tcbs_client.py           # TCBS API (NO vnstock)
│   ├── vci_client.py            # VCI REST + GraphQL
│   ├── news_scraper.py          # CafeF headline scraper
│   └── data_manager.py          # Unified manager + synthetic fallback
├── features/
│   ├── technical.py             # 13+ indicators (RSI, MACD, BB, ATR, ADX...)
│   ├── sentiment.py             # Vietnamese sentiment (180+ terms)
│   └── feature_builder.py       # ML feature matrix (60+ features)
├── models/
│   ├── xgboost_model.py         # XGBoost + walk-forward
│   ├── bilstm_model.py          # PyTorch BiLSTM + early stopping
│   ├── linear_model.py          # Lasso regression
│   ├── ensemble.py              # Weighted voting ensemble
│   └── trainer.py               # Full training pipeline
├── strategies/
│   ├── weekly_momentum.py       # 1W: RSI + MACD + Volume
│   ├── swing_trader.py          # 2W: SMA breakout + Sentiment
│   ├── position_trader.py       # 1M: ML ensemble + Golden Cross
│   ├── cycle_trader.py          # 3M: Macro regime + Fundamentals
│   ├── value_investor.py        # 5M: P/E, ROE, FTSE scoring
│   └── engine.py                # Orchestrator
├── risk/
│   ├── position_sizing.py       # ATR-based + Kelly Criterion
│   ├── stop_loss.py             # Fixed / Trailing / ATR / Time
│   └── portfolio.py             # Portfolio management
├── backtest/
│   ├── engine.py                # Walk-forward backtesting
│   ├── metrics.py               # Sharpe, Sortino, Calmar, MDD...
│   └── report.py                # HTML report generator
├── api/
│   ├── main.py                  # FastAPI
│   └── routes.py                # 6 REST endpoints
├── tests/                       # Comprehensive pytest suite
├── demo.py                      # End-to-end demo
├── run_backtest.py              # CLI backtest runner
├── train_models.py              # CLI training script
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml
└── README.md
```

## 🚀 Quick Start

### 1. Install
```bash
cd vietnam-trading-app-v3
pip install -r requirements.txt
```

### 2. Run Demo
```bash
python demo.py
```

### 3. Start API
```bash
uvicorn api.main:app --reload --port 8000
# Open http://localhost:8000/docs
```

### 4. Backtest
```bash
python run_backtest.py --ticker FPT --strategy 1W --report
python run_backtest.py --ticker VNM --all --report
```

### 5. Train Models
```bash
python train_models.py --ticker FPT --all
```

### 6. Tests
```bash
pytest tests/ -v
```

### 7. Docker
```bash
docker-compose up --build
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | App info |
| `/health` | GET | Health check |
| `/data/{ticker}` | GET | Fetch OHLCV data |
| `/signals/{ticker}` | GET | Trading signals (all 5 strategies) |
| `/backtest/{ticker}` | GET | Run backtest |
| `/portfolio` | GET | Portfolio status |
| `/train/{ticker}` | POST | Train models |

## 📊 Data Sources (No vnstock)

| Source | Type | Endpoint |
|---|---|---|
| **TCBS** | OHLCV, Overview, Intraday | `apipubaws.tcbs.com.vn` |
| **VCI** | OHLCV, Price Board, GraphQL | `trading.vietcap.com.vn` |
| **CafeF** | News Headlines | `cafef.vn` (scraping) |
| **Synthetic** | Offline fallback | Geometric Brownian Motion |

## 🧠 Models

| Model | Type | Use Case |
|---|---|---|
| **XGBoost** | Direction classifier | Walk-forward validated |
| **BiLSTM** | Sequence predictor | PyTorch with early stopping |
| **Lasso** | Linear regression | Baseline + feature selection |
| **Ensemble** | Weighted voting | Combines all models |

## 📈 Strategy Horizons

| Horizon | Strategy | Key Indicators |
|---|---|---|
| **1 Week** | Momentum Scalping | RSI, MACD, Volume |
| **2 Weeks** | Swing Trading | SMA20, Bollinger, Sentiment |
| **1 Month** | Position Trading | ML Ensemble, SMA50/100 |
| **3 Months** | Cycle Trading | Macro, P/E, EPS |
| **5 Months** | Value Investing | Fundamentals, FTSE |

## ⚠️ Disclaimer

This is a **simulation and research tool**. Past performance does not guarantee
future results. Always do your own research before making investment decisions.

## 📝 License

MIT License – Free for personal and commercial use.

---
*Built for the Vietnam stock market by AI Trading System v3*
