"""api/routes.py - REST API with /tickers endpoint for full exchange lists."""
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "running", "version": "3.7"}

@router.get("/tickers")
def get_tickers():
    from data.ticker_list import get_all_tickers, get_ticker_count
    tickers = get_all_tickers()
    counts = get_ticker_count()
    return {"tickers": tickers, "counts": counts, "total": sum(counts.values())}

@router.get("/tickers/{exchange}")
def get_exchange_tickers(exchange: str):
    from data.ticker_list import get_exchange_tickers
    tickers = get_exchange_tickers(exchange.upper())
    if not tickers:
        raise HTTPException(status_code=404, detail=f"Exchange '{exchange}' not found")
    return {"exchange": exchange.upper(), "tickers": tickers, "count": len(tickers)}

@router.get("/data/{ticker}")
def get_data(ticker: str, start: str = "2020-01-01"):
    from data.data_manager import DataManager, DataUnavailableError
    dm = DataManager()
    try:
        df = dm.get_ohlcv(ticker.upper(), start=start)
        return {"ticker": ticker.upper(), "rows": len(df),
                "last_close": float(df["close"].iloc[-1]),
                "last_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
                "data_source": dm.get_data_source(df)}
    except DataUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/decision/{ticker}")
def get_decision(ticker: str, capital: float = 500_000_000):
    from data.data_manager import DataManager, DataUnavailableError
    from features.technical import build_all_indicators
    from decision_engine import DecisionEngine
    dm = DataManager()
    try: df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
    except DataUnavailableError as e: raise HTTPException(status_code=503, detail=str(e))
    if len(df) < 200: raise HTTPException(status_code=422, detail=f"Need 200+ rows, got {len(df)}")
    featured = build_all_indicators(df)
    engine = DecisionEngine()
    result = engine.full_decision(featured, capital=capital, ticker=ticker.upper(), sentiment_score=0.0)
    result["data_source"] = dm.get_data_source(df)
    result["data_rows"] = len(df)
    result.pop("summary", None)
    return result

@router.get("/signals/{ticker}")
def get_signals(ticker: str):
    from data.data_manager import DataManager, DataUnavailableError
    from features.technical import build_all_indicators
    from strategies.engine import StrategyEngine
    dm = DataManager()
    try: df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
    except DataUnavailableError as e: raise HTTPException(status_code=503, detail=str(e))
    featured = build_all_indicators(df)
    engine = StrategyEngine()
    result = engine.run(featured, ticker=ticker.upper())
    result["data_source"] = dm.get_data_source(df)
    return result

@router.get("/backtest/{ticker}")
def run_backtest(ticker: str, strategy: str = "1W"):
    from data.data_manager import DataManager, DataUnavailableError
    from backtest.engine import BacktestEngine
    dm = DataManager()
    try: df = dm.get_ohlcv(ticker.upper(), start="2020-01-01")
    except DataUnavailableError as e: raise HTTPException(status_code=503, detail=str(e))
    bt = BacktestEngine()
    return bt.run(df, ticker=ticker.upper(), strategy_key=strategy)

@router.get("/portfolio")
def get_portfolio():
    from risk.portfolio import Portfolio
    return Portfolio().summary()
