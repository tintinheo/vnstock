# 🇻🇳 VN Trading OS — Streamlit Edition

## Deploy to Streamlit Community Cloud

1. **Push to GitHub**:
```bash
git init
git add .
git commit -m "VN Trading Streamlit app"
git remote add origin https://github.com/YOUR_USER/vn-trading-streamlit.git
git push -u origin main
```

2. **Deploy on Streamlit Cloud**:
- Go to [share.streamlit.io](https://share.streamlit.io)
- Click "New app"
- Select your repo, branch `main`, file `streamlit_app.py`
- Click Deploy!

3. **Local Run**:
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Project Structure
```
├── streamlit_app.py        # Main Streamlit app (all pages)
├── data/
│   ├── data_manager.py     # KBS + CafeF data fetching
│   ├── kbs_client.py       # KBS Securities API
│   ├── cafef_client.py     # CafeF scraper
│   └── ticker_list.py      # HOSE/HNX/UPCOM ticker lists
├── features/
│   └── technical.py        # Technical indicators (RSI, MACD, BB, etc.)
├── decision_engine.py      # Buy/Sell/Hold decision logic
├── audit/
│   └── logger.py           # Audit trail
├── .streamlit/
│   └── config.toml         # Dark theme config
├── requirements.txt
└── README.md
```

## Features
- 📊 Dashboard: Top 30 HOSE stocks scanned automatically
- 🔍 Scanner: Scan ALL tickers from HOSE (~400), HNX (~200), UPCOM
- 🎯 Decision Engine: Full buy/sell/hold with entry, SL, TP, position sizing
- 📈 Interactive Plotly charts
- 📋 Audit Log: Every action logged with timing
- 🎨 Dark theme matching TradingView aesthetic
