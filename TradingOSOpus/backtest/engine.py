"""backtest/engine.py – Walk-forward backtesting engine."""
import numpy as np, pandas as pd
from config.settings import TRADING, HORIZONS
from risk.portfolio import Portfolio
from risk.stop_loss import StopLossManager
from risk.position_sizing import atr_position_size
from backtest.metrics import calculate_metrics
from features.technical import atr as compute_atr

class BacktestEngine:
    def __init__(self, initial_capital=None, commission_rate=None, tax_rate=None, slippage_bps=None):
        self.initial_capital=initial_capital or TRADING["initial_capital"]
        self.slippage_bps=slippage_bps or TRADING["slippage_bps"]

    def run(self, df, ticker="TEST", strategy_key="1W", lookback=100):
        from strategies.engine import STRATEGY_MAP
        if strategy_key not in STRATEGY_MAP: return {"error": f"Unknown strategy: {strategy_key}"}
        strategy = STRATEGY_MAP[strategy_key](); portfolio = Portfolio(self.initial_capital)
        stop_mgr = StopLossManager(method="atr", atr_multiplier=2.0)
        equity_curve, signals_log = [], []
        horizon_days = HORIZONS[strategy_key]["days"]; step = max(horizon_days//2, 1)
        atr_series = compute_atr(df).values if len(df)>14 else np.full(len(df), df["close"].std() if len(df)>1 else 1)
        i = lookback
        while i < len(df):
            window = df.iloc[max(0,i-lookback*2):i+1].copy()
            cur_close = float(df["close"].iloc[i])
            cur_date = str(df["date"].iloc[i]) if "date" in df.columns else str(i)
            cur_atr = float(atr_series[i]) if i<len(atr_series) and not np.isnan(atr_series[i]) else cur_close*0.02
            portfolio.update_prices({ticker: cur_close})
            if ticker in portfolio.positions:
                pos = portfolio.positions[ticker]
                sl = stop_mgr.calculate_stop_loss(pos["entry_price"],cur_close,cur_atr,pos.get("highest_price",pos["entry_price"]),pos.get("days_held",0))
                if sl["is_stopped"]:
                    slip=cur_close*self.slippage_bps/10000; portfolio.sell(ticker,cur_close-slip,date=cur_date)
                    signals_log.append({"date":cur_date,"action":"STOP_LOSS","price":cur_close,"reason":sl["reason"]})
                    equity_curve.append(portfolio.total_value); i+=1; continue
            sigs = strategy.generate_signals(window, ticker=ticker)
            if sigs:
                sig=sigs[0]
                if sig.action==1 and ticker not in portfolio.positions:
                    sizing=atr_position_size(portfolio.cash, cur_atr); shares=sizing["shares"]
                    if shares>0:
                        slip=cur_close*self.slippage_bps/10000; portfolio.buy(ticker,cur_close+slip,shares,date=cur_date)
                        signals_log.append({"date":cur_date,"action":"BUY","price":cur_close,"shares":shares,"reason":sig.reason})
                elif sig.action==-1 and ticker in portfolio.positions:
                    slip=cur_close*self.slippage_bps/10000; portfolio.sell(ticker,cur_close-slip,date=cur_date)
                    signals_log.append({"date":cur_date,"action":"SELL","price":cur_close,"reason":sig.reason})
            equity_curve.append(portfolio.total_value); i+=step
        if ticker in portfolio.positions:
            portfolio.sell(ticker,float(df["close"].iloc[-1]),date=str(df["date"].iloc[-1]) if "date" in df.columns else "END")
        eq=pd.Series(equity_curve); metrics=calculate_metrics(eq, portfolio.history)
        return {"ticker":ticker,"strategy":strategy_key,"equity_curve":eq.tolist(),"trades":portfolio.history,"signals":signals_log,"metrics":metrics,"portfolio_summary":portfolio.summary()}

    def run_multiple_strategies(self, df, ticker="TEST"):
        return {k: self.run(df, ticker=ticker, strategy_key=k) for k in HORIZONS}
