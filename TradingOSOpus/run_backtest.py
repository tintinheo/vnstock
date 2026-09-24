#!/usr/bin/env python3
"""run_backtest.py – Standalone backtest runner."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
from data.data_manager import DataManager
from backtest.engine import BacktestEngine
from backtest.report import generate_html_report

def main():
    p = argparse.ArgumentParser(description="Vietnam Trading Backtest")
    p.add_argument("--ticker", default="FPT"); p.add_argument("--strategy", default="1W", choices=["1W","2W","1M","3M","5M"])
    p.add_argument("--start", default="2020-01-01"); p.add_argument("--capital", type=float, default=5e8)
    p.add_argument("--report", action="store_true"); p.add_argument("--all", action="store_true")
    args = p.parse_args()
    print(f"\n\U0001f680 Backtest: {args.ticker} | {args.strategy} | from {args.start}")
    dm = DataManager(); df = dm.get_ohlcv(args.ticker, start=args.start)
    print(f"   Data: {len(df)} bars\n")
    bt = BacktestEngine(initial_capital=args.capital)
    for sk in (["1W","2W","1M","3M","5M"] if args.all else [args.strategy]):
        r = bt.run(df, ticker=args.ticker, strategy_key=sk); m = r["metrics"]
        print(f"  [{sk}] Return={m.get('total_return_pct',0):+.2f}%  Sharpe={m.get('sharpe_ratio',0):.3f}  "
              f"MaxDD={m.get('max_drawdown_pct',0):.2f}%  WinRate={m.get('win_rate_pct',0):.0f}%  Trades={m.get('total_trades',0)}")
        if args.report: print(f"  \U0001f4c4 {generate_html_report(r)}")
    print("\n✅ Done!")

if __name__ == "__main__": main()
