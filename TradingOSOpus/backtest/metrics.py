"""backtest/metrics.py – Performance metrics calculator."""
import numpy as np, pandas as pd

def calculate_metrics(equity_curve, trades, risk_free_rate=0.045, periods_per_year=252):
    if len(equity_curve) < 2: return {"error":"Insufficient data"}
    returns = equity_curve.pct_change().dropna()
    total_return = (equity_curve.iloc[-1]/equity_curve.iloc[0])-1
    n_years = len(returns)/periods_per_year
    cagr = (1+total_return)**(1/max(n_years,0.01))-1
    annual_vol = returns.std() * np.sqrt(periods_per_year)
    down_ret = returns[returns<0]
    down_vol = down_ret.std()*np.sqrt(periods_per_year) if len(down_ret)>0 else 0.001
    rf_daily = (1+risk_free_rate)**(1/periods_per_year)-1
    sharpe = (returns.mean()-rf_daily)/max(returns.std(),1e-8)*np.sqrt(periods_per_year)
    sortino = (returns.mean()-rf_daily)/max(down_vol/np.sqrt(periods_per_year),1e-8)*np.sqrt(periods_per_year)
    cummax = equity_curve.cummax(); dd = (equity_curve-cummax)/cummax; max_dd = dd.min()
    calmar = cagr / max(abs(max_dd),1e-8)
    pnls = [t.get("pnl",0) for t in trades if "pnl" in t]
    wins = [p for p in pnls if p>0]; losses = [p for p in pnls if p<0]
    win_rate = len(wins)/max(len(pnls),1)
    profit_factor = sum(wins)/max(abs(sum(losses)),1) if losses else float("inf")
    return {"total_return_pct":round(total_return*100,2),"cagr_pct":round(cagr*100,2),"annual_volatility":round(annual_vol*100,2),
        "sharpe_ratio":round(sharpe,3),"sortino_ratio":round(sortino,3),"calmar_ratio":round(calmar,3),"max_drawdown_pct":round(max_dd*100,2),
        "total_trades":len(pnls),"win_rate_pct":round(win_rate*100,1),"avg_win":round(np.mean(wins),0) if wins else 0,
        "avg_loss":round(np.mean(losses),0) if losses else 0,"profit_factor":round(profit_factor,2),"n_days":len(equity_curve)}
