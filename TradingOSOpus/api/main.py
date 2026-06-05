"""api/main.py – FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(title="Vietnam AI Trading System", version="3.0.0",
    description="Full AI-powered trading system for Vietnam stock market.")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/")
def root():
    return {"app": "Vietnam AI Trading System v3", "status": "running", "docs": "/docs",
        "endpoints": ["/health","/data/{ticker}","/signals/{ticker}","/backtest/{ticker}","/portfolio","/train/{ticker}"]}
