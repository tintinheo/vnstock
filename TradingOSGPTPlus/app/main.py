from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.backtest import run_simple_backtest
from app.analytics.decision import DecisionService
from app.audit import AuditLogger, audited
from app.config import get_settings
from app.data.universe import list_tickers, normalize_ticker
from app.errors import DataUnavailableError
from app.models import BacktestResponse, DataResponse, DecisionResponse, Horizon, SignalResponse

settings = get_settings()
app = FastAPI(
    title="Vietnam AI Trading OS",
    version="0.1.0",
    description="Decision-support API for Vietnam equities. Returns 503 when no real source or valid cache is available.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = DecisionService(settings=settings)
audit_logger = AuditLogger(settings)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "cache_ttl_hours": settings.cache_ttl_hours,
        "data_source_priority": settings.sources,
        "no_synthetic_data_runtime_fallback": True,
    }


@app.get("/tickers")
def tickers() -> dict:
    return {"tickers": list_tickers(), "note": "Seed universe only; live universe adapter is a Phase 2 extension."}


@app.get("/data/{ticker}", response_model=DataResponse)
def data(ticker: str) -> DataResponse:
    normalized = normalize_ticker(ticker)
    try:
        with audited("data_fetch", normalized, logger=audit_logger) as ctx:
            response = service.get_data(normalized)
            ctx["data_source"] = response.data_source
            ctx["result_summary"] = {"rows": response.row_count, "latest_date": str(response.latest_date)}
            return response
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc), "source_errors": exc.errors}) from exc


@app.get("/signals/{ticker}", response_model=SignalResponse)
def signals(ticker: str, horizon: Horizon = Horizon.one_month) -> SignalResponse:
    normalized = normalize_ticker(ticker)
    try:
        with audited("signals", normalized, {"horizon": horizon.value}, audit_logger) as ctx:
            response = service.get_signals(normalized, horizon)
            selected = response.strategy_signals[horizon.value]
            ctx["data_source"] = response.data_source
            ctx["signal"] = selected["action"]
            ctx["confidence"] = selected["confidence"]
            ctx["result_summary"] = {"regime": response.regime.value, "warnings": response.warnings}
            return response
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc), "source_errors": exc.errors}) from exc


@app.get("/decision/{ticker}", response_model=DecisionResponse)
def decision(
    ticker: str,
    capital: float = Query(default=500_000_000, gt=0),
    horizon: Horizon = Horizon.one_month,
) -> DecisionResponse:
    normalized = normalize_ticker(ticker)
    try:
        with audited("decision", normalized, {"capital": capital, "horizon": horizon.value}, audit_logger) as ctx:
            response = service.get_decision(normalized, capital, horizon, audit_id=ctx["audit_id"])
            ctx["data_source"] = response.data_source
            ctx["signal"] = response.action.value
            ctx["confidence"] = response.confidence
            ctx["result_summary"] = {
                "latest_price": response.latest_price,
                "shares": response.position_size.shares,
                "warnings": response.warnings,
            }
            return response
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc), "source_errors": exc.errors}) from exc


@app.get("/backtest/{ticker}", response_model=BacktestResponse)
def backtest(ticker: str, horizon: Horizon = Horizon.one_month) -> BacktestResponse:
    normalized = normalize_ticker(ticker)
    try:
        with audited("backtest", normalized, {"horizon": horizon.value}, audit_logger) as ctx:
            frame, metadata = service.data_client.get_history(normalized)
            response = run_simple_backtest(frame, horizon, str(metadata.get("source", "UNKNOWN")))
            ctx["data_source"] = response.data_source
            ctx["result_summary"] = response.metrics
            return response
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc), "source_errors": exc.errors}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/audit")
def audit(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    return {"events": audit_logger.read_latest(limit=limit)}

