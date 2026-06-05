"""api/routes.py – REST API endpoints including /decision/{ticker}."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "running", "version": "3.1", "features": ["decision_engine"]}

@router.get("/data/{ticker}")
def get_data(ticker: str, start: str = "2020-01-01"):
    from data.data_manager import DataManager
    dm = DataManager()
    df = dm.get_ohlcv(ticker, start=start)
    return {"ticker": ticker, "rows": len(df),
            "last_close": float(df["close"].iloc[-1]) if len(df) > 0 else 0}

@router.get("/signals/{ticker}")
def get_signals(ticker: str):
    from data.data_manager import DataManager
    from features.technical import build_all_indicators
    from strategies.engine import StrategyEngine
    dm = DataManager()
    df = dm.get_ohlcv(ticker, start="2020-01-01")
    featured = build_all_indicators(df)
    engine = StrategyEngine()
    return engine.run(featured, ticker=ticker)

@router.get("/decision/{ticker}")
def get_decision(ticker: str, capital: float = 500_000_000):
    """Full AI decision with price targets, stop-loss, take-profit, position sizing."""
    from data.data_manager import DataManager
    from features.technical import build_all_indicators
    from features.sentiment import VietnameseFinancialSentiment
    from decision_engine import DecisionEngine

    dm = DataManager()
    df = dm.get_ohlcv(ticker, start="2020-01-01")
    if df.empty or len(df) < 200:
        return {"error": f"Insufficient data for {ticker}"}

    featured = build_all_indicators(df)

    # Sentiment from cached news (if available)
    sa = VietnameseFinancialSentiment()
    try:
        news = dm.get_news(pages=1)
        ticker_news = [n["title"] for n in news if ticker.upper() in n.get("title", "").upper()]
        if not ticker_news:
            ticker_news = [n["title"] for n in news[:5]]
        sent = sa.aggregate_sentiment(ticker_news)
        sentiment_score = sent["compound"]
    except Exception:
        sentiment_score = 0.0

    engine = DecisionEngine()
    result = engine.full_decision(featured, capital=capital, ticker=ticker.upper(),
                                   sentiment_score=sentiment_score)

    # Remove summary (text) for JSON response, keep structured data
    result.pop("summary", None)
    return result

@router.get("/backtest/{ticker}")
def run_backtest(ticker: str, strategy: str = "1W"):
    from data.data_manager import DataManager
    from backtest.engine import BacktestEngine
    dm = DataManager()
    bt = BacktestEngine()
    df = dm.get_ohlcv(ticker, start="2020-01-01")
    return bt.run(df, ticker=ticker, strategy_key=strategy)

@router.get("/portfolio")
def get_portfolio():
    from risk.portfolio import Portfolio
    p = Portfolio()
    return p.summary()

@router.post("/train/{ticker}")
def train(ticker: str, horizon: str = "1W"):
    from models.trainer import ModelTrainer
    trainer = ModelTrainer()
    return trainer.train_single(ticker, horizon)
