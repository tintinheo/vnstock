# Vietnam AI Trading OS GPT Plus

Decision-support and research system for HOSE, HNX, and UPCOM tickers. It is not financial advice and it is not an autonomous trading bot.

## What Is Implemented

- FastAPI service with `/health`, `/tickers`, `/data/{ticker}`, `/signals/{ticker}`, `/decision/{ticker}`, `/backtest/{ticker}`, and `/audit`.
- Public-first data layer: KBS first, CafeF second, then explicit unavailable stubs for Vietstock, FireAnt, and DNSE.
- No `vnstock` dependency.
- No synthetic, random, fake, or placeholder market data runtime fallback.
- Cache fallback with TTL and source metadata. If live sources fail and no valid cache exists, API returns HTTP 503.
- Unit normalization for Vietnam source conventions, including CafeF thousands-to-VND.
- Indicator engine: SMA, EMA, RSI, MACD, ATR, Bollinger bands, volume ratio, returns, drawdown.
- Five horizon rule sets: `1W`, `2W`, `1M`, `3M`, `5M`.
- Risk engine: max 2% capital-at-risk, max 20% position cap, ATR/stop based sizing, and 100-share lot rounding.
- JSONL audit logs for decisions, data failures, signals, and backtests.
- Streamlit dashboard for quick local use.

## Disclaimers

Vietnam AI Trading OS is a research and decision-support tool, not financial advice. Past performance does not guarantee future results. All trading involves risk of capital loss. Users must comply with Vietnam securities law, exchange rules, broker requirements, tax rules, and data-source terms.

## Quick Start

```powershell
cd D:\portfolio\vnstock\TradingOSGPTPlus
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If `python` opens the Microsoft Store or fails with a launcher/session error, install Python 3.11+ from python.org and disable the Windows App Execution Alias for Python.

API docs:

```text
http://127.0.0.1:8000/docs
```

Streamlit UI:

```powershell
streamlit run streamlit_app.py
```

For Streamlit Community Cloud from the existing `vnstock` repo, deploy this app path:

```text
TradingOSGPTPlus/streamlit_app.py
```

See `DEPLOY_STREAMLIT.md` for the full checklist.

## Example Calls

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/decision/FPT?capital=500000000&horizon=1M"
Invoke-RestMethod "http://127.0.0.1:8000/signals/HPG?horizon=2W"
Invoke-RestMethod "http://127.0.0.1:8000/backtest/VCB?horizon=3M"
```

## Data Rules

The service attempts live sources in this order:

1. KBS
2. CafeF
3. Vietstock
4. FireAnt
5. DNSE
6. Valid local cache, only after real-source failure

If none succeeds, it returns HTTP 503. This behavior is intentional.

Cache files are written to `data_cache/`. Audit events are written to `audit_logs/audit-YYYY-MM-DD.jsonl`.

## Project Layout

```text
app/
  analytics/       indicators, regime, strategies, risk, decision, backtest
  data/            source clients, cache, unit normalization, ticker seed list
  ui/              Streamlit dashboard
  main.py          FastAPI entrypoint
streamlit_app.py   Streamlit Cloud entrypoint
tests/             focused unit tests
```

## Test

```powershell
pytest
```

## Production Notes

Before live use, verify source terms of use, current HOSE/HNX/UPCOM rules, KRX settlement details, and any broker integration requirements. Treat the backup adapters as evaluation points until their lawful and stable endpoint contracts are confirmed.
