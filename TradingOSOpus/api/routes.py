"""api/routes.py - v4.0 with audit + numpy fix + /tickers."""
import numpy as np
import time as _time
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
router = APIRouter()

def sanitize(obj):
    if isinstance(obj, dict): return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)): return [sanitize(v) for v in obj]
    elif isinstance(obj, np.integer): return int(obj)
    elif isinstance(obj, np.floating): return float(obj)
    elif isinstance(obj, np.bool_): return bool(obj)
    elif isinstance(obj, np.ndarray): return obj.tolist()
    elif hasattr(obj, "item"): return obj.item()
    return obj

def _audit():
    from audit.logger import audit; return audit

@router.get("/health")
def health(): return {"status": "running", "version": "4.0"}

@router.get("/tickers")
def get_tickers():
    from data.ticker_list import get_all_tickers, get_ticker_count
    return {"tickers": get_all_tickers(), "counts": get_ticker_count(), "total": sum(get_ticker_count().values())}

@router.get("/tickers/{exchange}")
def get_exchange_tickers(exchange: str):
    from data.ticker_list import get_exchange_tickers
    t = get_exchange_tickers(exchange.upper())
    if not t: raise HTTPException(404, f"Exchange '{exchange}' not found")
    return {"exchange": exchange.upper(), "tickers": t, "count": len(t)}

@router.get("/data/{ticker}")
def get_data(ticker: str, start: str = "2020-01-01", request: Request = None):
    from data.data_manager import DataManager, DataUnavailableError
    t0 = _time.time(); dm = DataManager()
    try:
        df = dm.get_ohlcv(ticker.upper(), start=start)
        r = sanitize({"ticker": ticker.upper(), "rows": len(df), "last_close": float(df["close"].iloc[-1]), "last_date": df["date"].iloc[-1].strftime("%Y-%m-%d"), "data_source": dm.get_data_source(df)})
        _audit().log("DATA", ticker.upper(), {"start": start}, r, "SUCCESS", (_time.time()-t0)*1000, str(getattr(getattr(request, "client", None), "host", "")))
        return r
    except DataUnavailableError as e:
        _audit().log("DATA", ticker.upper(), {"start": start}, {}, "ERROR", (_time.time()-t0)*1000)
        raise HTTPException(503, str(e))

@router.get("/decision/{ticker}")
def get_decision(ticker: str, capital: float = 500_000_000, request: Request = None):
    from data.data_manager import DataManager, DataUnavailableError
    from features.technical import build_all_indicators
    from decision_engine import DecisionEngine
    t0 = _time.time(); dm = DataManager()
    try: df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
    except DataUnavailableError as e:
        _audit().log("DECISION", ticker.upper(), {"capital": capital}, {}, "ERROR", (_time.time()-t0)*1000)
        raise HTTPException(503, str(e))
    if len(df) < 200:
        _audit().log("DECISION", ticker.upper(), {}, {}, "ERROR", (_time.time()-t0)*1000)
        raise HTTPException(422, f"Need 200+ rows, got {len(df)}")
    featured = build_all_indicators(df)
    result = DecisionEngine().full_decision(featured, capital=capital, ticker=ticker.upper(), sentiment_score=0.0)
    result["data_source"] = dm.get_data_source(df); result["data_rows"] = len(df); result.pop("summary", None)
    result = sanitize(result)
    _audit().log("DECISION", ticker.upper(), {"capital": capital}, result, "SUCCESS", (_time.time()-t0)*1000, str(getattr(getattr(request, "client", None), "host", "")))
    return result

@router.get("/signals/{ticker}")
def get_signals(ticker: str, request: Request = None):
    from data.data_manager import DataManager, DataUnavailableError
    from features.technical import build_all_indicators
    from strategies.engine import StrategyEngine
    t0 = _time.time(); dm = DataManager()
    try: df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
    except DataUnavailableError as e:
        _audit().log("SIGNAL", ticker.upper(), {}, {}, "ERROR", (_time.time()-t0)*1000)
        raise HTTPException(503, str(e))
    featured = build_all_indicators(df)
    result = sanitize(StrategyEngine().run(featured, ticker=ticker.upper()))
    result["data_source"] = dm.get_data_source(df)
    _audit().log("SIGNAL", ticker.upper(), {}, result, "SUCCESS", (_time.time()-t0)*1000, str(getattr(getattr(request, "client", None), "host", "")))
    return result

@router.get("/backtest/{ticker}")
def run_backtest(ticker: str, strategy: str = "1W", request: Request = None):
    from data.data_manager import DataManager, DataUnavailableError
    from backtest.engine import BacktestEngine
    t0 = _time.time(); dm = DataManager()
    try: df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
    except DataUnavailableError as e:
        _audit().log("BACKTEST", ticker.upper(), {"strategy": strategy}, {}, "ERROR", (_time.time()-t0)*1000)
        raise HTTPException(503, str(e))
    result = sanitize(BacktestEngine().run(df, ticker=ticker.upper(), strategy_key=strategy))
    _audit().log("BACKTEST", ticker.upper(), {"strategy": strategy}, result, "SUCCESS", (_time.time()-t0)*1000, str(getattr(getattr(request, "client", None), "host", "")))
    return result

@router.get("/portfolio")
def get_portfolio(): return sanitize({"cash": 500000000, "positions": [], "total_equity": 500000000})

@router.get("/audit")
def get_audit(date_from: Optional[str] = None, date_to: Optional[str] = None, action_type: Optional[str] = None, ticker: Optional[str] = None, status: Optional[str] = None, limit: int = 500):
    return {"entries": _audit().get_logs(date_from, date_to, action_type, ticker, status, limit), "count": len(_audit().get_logs(date_from, date_to, action_type, ticker, status, limit))}

@router.get("/audit/stats")
def get_audit_stats(days: int = 7): return _audit().get_stats(days)

@router.delete("/audit")
def clear_audit(days: int = 30): return {"removed_files": _audit().clear_old(days)}
