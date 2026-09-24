#!/usr/bin/env python3
"""demo.py – End-to-end demonstration of Vietnam AI Trading System."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from data.data_manager import DataManager
from features.feature_builder import FeatureBuilder
from features.sentiment import VietnameseFinancialSentiment
from strategies.engine import StrategyEngine
from backtest.engine import BacktestEngine
from backtest.report import generate_html_report
from risk.portfolio import Portfolio

def main():
    print("=" * 70)
    print("  VIETNAM AI TRADING SYSTEM v3  –  Full Demo")
    print("=" * 70)

    ticker = "FPT"

    # 1. Data
    print("\n▶ [1/6] Loading data...")
    dm = DataManager()
    df = dm.get_ohlcv(ticker, start="2020-01-01")
    print(f"  {ticker}: {len(df)} bars | Close range: {df['close'].min():,.0f} – {df['close'].max():,.0f}")

    # 2. Features
    print("\n▶ [2/6] Building features...")
    fb = FeatureBuilder()
    featured = fb.build(df, horizon=5)
    feat_cols = fb.get_feature_columns(featured)
    print(f"  Generated {len(feat_cols)} features")

    # 3. Sentiment
    print("\n▶ [3/6] Sentiment analysis...")
    sa = VietnameseFinancialSentiment()
    headlines = [
        "VN-Index tăng mạnh vượt 1900 điểm, thanh khoản tăng kỷ lục",
        "Khối ngoại bán ròng mạnh, lo ngại lãi suất tăng",
        "FPT lãi lớn nhờ AI và chuyển đổi số, cổ phiếu phi mã",
        "Rủi ro căng thẳng thương mại Mỹ-Trung gia tăng",
        "FTSE nâng hạng Việt Nam, dòng vốn kỳ vọng 1.5 tỷ USD",
    ]
    for h in headlines:
        s = sa.score_text(h)
        e = "\U0001f7e2" if s["compound"]>0.1 else ("\U0001f534" if s["compound"]<-0.1 else "\u26aa")
        print(f"  {e} [{s['compound']:+.3f}] {h[:60]}...")
    agg = sa.aggregate_sentiment(headlines)
    print(f"  \U0001f4ca Aggregate: {agg['compound']:+.4f}")

    # 4. Signals
    print("\n▶ [4/6] Generating signals...")
    engine = StrategyEngine()
    dashboard = engine.run(df, ticker=ticker, sentiment_score=agg["compound"],
        ml_prediction=0.6, macro_regime="expansion", pe_ratio=13, eps_growth=0.18)
    print(f"  Consensus: {dashboard['consensus']} | BUY:{dashboard['buy_signals']} SELL:{dashboard['sell_signals']}")
    for key, strat in dashboard["strategies"].items():
        if "signals" in strat:
            for s in strat["signals"]:
                e = "\U0001f7e2" if s["action"]=="BUY" else ("\U0001f534" if s["action"]=="SELL" else "\u26aa")
                print(f"    {e} [{key}] {strat['name']}: {s['action']} conf={s['confidence']:.2f} {s['reason'][:50]}")

    # 5. Backtest
    print("\n▶ [5/6] Running backtests...")
    bt = BacktestEngine()
    for skey in ["1W", "2W", "1M"]:
        r = bt.run(df, ticker=ticker, strategy_key=skey)
        m = r["metrics"]
        print(f"  [{skey}] Return={m.get('total_return_pct',0):+.1f}%  Sharpe={m.get('sharpe_ratio',0):.2f}  "
              f"MaxDD={m.get('max_drawdown_pct',0):.1f}%  WinRate={m.get('win_rate_pct',0):.0f}%  Trades={m.get('total_trades',0)}")
        if skey == "1W":
            rp = generate_html_report(r)
            print(f"  \U0001f4c4 Report: {rp}")

    # 6. Portfolio
    print("\n▶ [6/6] Portfolio simulation...")
    pf = Portfolio(initial_capital=500_000_000)
    pf.buy(ticker, df["close"].iloc[-1], 500, date="2026-06-01")
    pf.update_prices({ticker: df["close"].iloc[-1] * 1.05})
    s = pf.summary()
    print(f"  Capital: {s['total_value']:,.0f} VND | Return: {s['total_return_pct']:+.2f}%")

    print("\n" + "=" * 70)
    print("  ✅ Demo complete! Next: uvicorn api.main:app --reload")
    print("=" * 70)

if __name__ == "__main__":
    main()
