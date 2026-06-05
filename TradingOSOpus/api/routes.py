"""api/routes.py – All REST API endpoints."""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "healthy", "version": "3.0.0"}

@router.get("/data/{ticker}")
def get_data(ticker: str, start: str = Query("2020-01-01"), end: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=5000)):
    from data.data_manager import DataManager
    dm = DataManager(); df = dm.get_ohlcv(ticker, start=start, end=end)
    if df.empty: raise HTTPException(404, f"No data for {ticker}")
    return {"ticker": ticker.upper(), "count": min(len(df), limit), "data": df.tail(limit).to_dict(orient="records")}

@router.get("/signals/{ticker}")
def get_signals(ticker: str, sentiment: float = Query(0.0, ge=-1, le=1), ml_pred: float = Query(0.5, ge=0, le=1)):
    from data.data_manager import DataManager; from strategies.engine import StrategyEngine
    dm = DataManager(); df = dm.get_ohlcv(ticker, start="2020-01-01")
    if df.empty: raise HTTPException(404, f"No data for {ticker}")
    return StrategyEngine().run(df, ticker=ticker.upper(), sentiment_score=sentiment, ml_prediction=ml_pred)

@router.get("/backtest/{ticker}")
def run_backtest(ticker: str, strategy: str = Query("1W"), start: str = Query("2020-01-01")):
    from data.data_manager import DataManager; from backtest.engine import BacktestEngine
    dm = DataManager(); df = dm.get_ohlcv(ticker, start=start)
    if df.empty or len(df) < 100: raise HTTPException(400, f"Insufficient data for {ticker}")
    result = BacktestEngine().run(df, ticker=ticker.upper(), strategy_key=strategy)
    result.pop("equity_curve", None); return result

@router.get("/portfolio")
def get_portfolio():
    from risk.portfolio import Portfolio
    return Portfolio().summary()

@router.post("/train/{ticker}")
def train_models_endpoint(ticker: str, horizon: str = Query("1W")):
    from models.trainer import ModelTrainer
    return {"ticker": ticker.upper(), "horizon": horizon, "result": ModelTrainer().train_single(ticker, horizon_key=horizon)}
