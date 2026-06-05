#!/usr/bin/env python3
"""demo_decision.py - Full decision engine demo with real data for 5 Vietnam stocks."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "=" * 70)
    print("  VIETNAM AI TRADING SYSTEM v3 – DECISION ENGINE DEMO")
    print("  Multi-Layer Buy/Sell Decision with Price Targets")
    print("=" * 70)

    # ── Imports ──
    from data.data_manager import DataManager
    from features.technical import build_all_indicators
    from features.sentiment import VietnameseFinancialSentiment
    from strategies.engine import StrategyEngine
    from decision_engine import DecisionEngine

    dm = DataManager()
    sa = VietnameseFinancialSentiment()
    strategy_engine = StrategyEngine()
    decision_engine = DecisionEngine(atr_multiplier_sl=2.0, rr_ratio=2.5, max_risk_pct=0.02)

    CAPITAL = 500_000_000  # 500M VND

    # ── Vietnamese headlines per ticker ──
    headlines = {
        "FPT": [
            "FPT lai rong ky luc quy 1/2026, tang truong 25% nho AI",
            "FPT ky hop dong ty USD voi doi tac Nhat Ban",
            "Co phieu FPT vuot dinh, khoi ngoai mua rong manh",
            "Lo ngai dinh gia FPT qua cao so voi nganh",
        ],
        "VCB": [
            "Vietcombank dat loi nhuan ky luc 2025, tang 18%",
            "VCB duoc nang hang tin nhiem, trien vong tich cuc",
            "Lai suat giam ho tro tang truong tin dung ngan hang",
            "Khoi ngoai ban rong co phieu ngan hang 3 phien lien tiep",
        ],
        "HPG": [
            "Hoa Phat xuat khau thep tang 40%, gia thep phuc hoi",
            "HPG bao lai dot bien quy 4 nho gia thep tang",
            "Lo ngai thue chong ban pha gia tu My anh huong HPG",
            "San luong thep xay dung tang manh theo dau tu cong",
        ],
        "MBB": [
            "MB Bank tang truong tin dung manh me 2025",
            "MBB mo rong mang ban le, CASA dat ky luc",
            "Chat luong tai san MBB cai thien, no xau giam",
            "Canh bao rui ro tu mang bao hiem lien ket",
        ],
        "TCB": [
            "Techcombank dat loi nhuan khung, dan dau nganh",
            "TCB huong loi tu thi truong bat dong san phuc hoi",
            "Chien luoc zero-fee cua TCB thu hut khach hang moi",
            "Ap luc canh tranh nganh ngan hang ngay cang lon",
        ],
    }

    results = []

    for ticker in ["FPT", "VCB", "HPG", "MBB", "TCB"]:
        print(f"\n{'#' * 70}")
        print(f"  ANALYZING: {ticker}")
        print(f"{'#' * 70}")

        try:
            # Step 1: Fetch data
            df = dm.get_ohlcv(ticker, start="2020-01-01")
            if df.empty or len(df) < 200:
                print(f"  ⚠️ Insufficient data for {ticker} ({len(df)} rows)")
                continue
            print(f"  📊 Data: {len(df)} rows | {df['date'].iloc[0].strftime('%Y-%m-%d')} → {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
            print(f"  💰 Last close: {df['close'].iloc[-1]:,.0f} VND")

            # Step 2: Build indicators
            featured = build_all_indicators(df)

            # Step 3: Sentiment
            ticker_headlines = headlines.get(ticker, [])
            sent_result = sa.aggregate_sentiment(ticker_headlines)
            sentiment_score = sent_result["compound"]
            print(f"  📰 Sentiment: compound={sentiment_score:+.3f} ({len(ticker_headlines)} articles)")

            # Step 4: Decision Engine
            decision = decision_engine.full_decision(
                featured, capital=CAPITAL, ticker=ticker, sentiment_score=sentiment_score
            )

            # Print full summary
            print(f"\n{decision['summary']}")

            # Step 5: Compare with StrategyEngine
            strat_result = strategy_engine.run(featured, ticker=ticker)
            print(f"\n  🔄 StrategyEngine Consensus: {strat_result['consensus']} "
                  f"(BUY:{strat_result['buy_signals']} / SELL:{strat_result['sell_signals']})")

            # Collect for dashboard
            results.append({
                "ticker": ticker,
                "price": decision["signal"]["indicators"]["price"],
                "action": decision["signal"]["action"],
                "confidence": decision["signal"]["confidence"],
                "regime": decision["signal"]["regime"]["regime"],
                "rsi": decision["signal"]["indicators"]["rsi"],
                "entry": decision["price_targets"].get("entry_conservative", "-"),
                "stop_loss": decision["price_targets"].get("stop_loss", "-"),
                "take_profit": decision["price_targets"].get("take_profit_2", "-"),
                "shares": decision["position_sizing"].get("shares", 0),
                "consensus": strat_result["consensus"],
                "sentiment": sentiment_score,
            })

        except Exception as e:
            print(f"  ❌ Error analyzing {ticker}: {e}")
            import traceback; traceback.print_exc()

    # ══════════════════════════════════════════════════
    # DASHBOARD TABLE
    # ══════════════════════════════════════════════════
    if results:
        print(f"\n\n{'=' * 120}")
        print(f"  📋 DECISION DASHBOARD – {len(results)} STOCKS | Capital: {CAPITAL:,.0f} VND")
        print(f"{'=' * 120}")
        header = f"{'Ticker':>6} {'Price':>10} {'Decision':>10} {'Conf':>6} {'Regime':>14} {'RSI':>5} {'Entry':>10} {'SL':>10} {'TP':>10} {'Shares':>8} {'Strat':>6} {'Sent':>6}"
        print(header)
        print("-" * 120)
        for r in results:
            entry_str = f"{r['entry']:>10,.0f}" if isinstance(r['entry'], (int, float)) else f"{r['entry']:>10}"
            sl_str = f"{r['stop_loss']:>10,.0f}" if isinstance(r['stop_loss'], (int, float)) else f"{r['stop_loss']:>10}"
            tp_str = f"{r['take_profit']:>10,.0f}" if isinstance(r['take_profit'], (int, float)) else f"{r['take_profit']:>10}"
            emoji = "🟢" if "BUY" in r["action"] else ("🔴" if "SELL" in r["action"] else "⚪")
            print(f"{r['ticker']:>6} {r['price']:>10,.0f} {emoji}{r['action']:>8} {r['confidence']:>5.0%} "
                  f"{r['regime']:>14} {r['rsi']:>5.0f} {entry_str} {sl_str} {tp_str} "
                  f"{r['shares']:>8,} {r['consensus']:>6} {r['sentiment']:>+.2f}")
        print("-" * 120)

        buy_count = sum(1 for r in results if "BUY" in r["action"])
        sell_count = sum(1 for r in results if "SELL" in r["action"])
        total_cost = sum(r["shares"] * r["entry"] for r in results
                         if isinstance(r["entry"], (int, float)) and r["shares"] > 0)
        print(f"\n  Summary: {buy_count} BUY | {sell_count} SELL | {len(results)-buy_count-sell_count} HOLD")
        print(f"  Total investment if all BUY executed: {total_cost:,.0f} VND ({total_cost/CAPITAL*100:.1f}% of capital)")

    print(f"\n{'=' * 70}")
    print(f"  ✅ DECISION ENGINE DEMO COMPLETE!")
    print(f"  Next: python -m uvicorn api.main:app --reload")
    print(f"        GET /decision/FPT → full AI decision")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
