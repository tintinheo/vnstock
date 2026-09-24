"""decision_engine.py - Multi-layer buy/sell decision with price targets for Vietnam stock market.

5 Layers:
  1. Market Regime Detection (HMM-inspired: Uptrend/Downtrend/Sideway)
  2. Entry/Exit Signal Generation (Mean Reversion + Momentum hybrid)
  3. Stock Scoring (Technical + Sentiment composite)
  4. Risk Management (ATR stop-loss, Kelly position sizing, price targets)
  5. Execution Guidance (Order type, timing, scaling)
"""
import numpy as np
import pandas as pd
from features.technical import (
    rsi, macd, bollinger_bands, atr, sma, ema,
    adx, volume_ratio, obv, vwap, stochastic, williams_r, cci, mfi
)


class DecisionEngine:
    """5-layer decision framework for Vietnam stock market."""

    def __init__(self, atr_multiplier_sl=2.0, rr_ratio=2.5, max_risk_pct=0.02):
        self.atr_mult_sl = atr_multiplier_sl
        self.rr_ratio = rr_ratio
        self.max_risk_pct = max_risk_pct

    # ═══════════════════════════════════════════════
    # LAYER 1: Market Regime Detection
    # ═══════════════════════════════════════════════
    def detect_regime(self, df):
        """Detect market regime: UPTREND / DOWNTREND / SIDEWAY."""
        close = df["close"]
        sma50_val = sma(close, 50).iloc[-1]
        sma200_val = sma(close, 200).iloc[-1]
        adx_df = adx(df)
        adx_val = adx_df["adx"].iloc[-1] if not np.isnan(adx_df["adx"].iloc[-1]) else 15
        plus_di = adx_df["plus_di"].iloc[-1] if not np.isnan(adx_df["plus_di"].iloc[-1]) else 0
        minus_di = adx_df["minus_di"].iloc[-1] if not np.isnan(adx_df["minus_di"].iloc[-1]) else 0
        atr_val = atr(df).iloc[-1]
        atr_pct = atr_val / close.iloc[-1] * 100 if close.iloc[-1] > 0 else 0

        if sma50_val > sma200_val and adx_val > 25 and plus_di > minus_di:
            regime = "UPTREND"
        elif sma50_val < sma200_val and adx_val > 25 and minus_di > plus_di:
            regime = "DOWNTREND"
        elif adx_val < 20:
            regime = "SIDEWAY"
        elif sma50_val > sma200_val:
            regime = "WEAK_UPTREND"
        else:
            regime = "WEAK_DOWNTREND"

        volatility = "HIGH" if atr_pct > 2.5 else ("LOW" if atr_pct < 1.0 else "NORMAL")

        # Trend strength
        price = close.iloc[-1]
        dist_sma50 = (price - sma50_val) / sma50_val * 100 if sma50_val > 0 else 0
        dist_sma200 = (price - sma200_val) / sma200_val * 100 if sma200_val > 0 else 0

        return {
            "regime": regime,
            "adx": round(adx_val, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "volatility": volatility,
            "atr_pct": round(atr_pct, 2),
            "sma50": round(sma50_val, 0),
            "sma200": round(sma200_val, 0),
            "dist_sma50_pct": round(dist_sma50, 2),
            "dist_sma200_pct": round(dist_sma200, 2),
        }

    # ═══════════════════════════════════════════════
    # LAYER 2: Entry/Exit Signal Generation
    # ═══════════════════════════════════════════════
    def generate_signal(self, df, sentiment_score=0.0):
        """Generate BUY/SELL/HOLD signal with confidence and reasons."""
        regime_info = self.detect_regime(df)
        close = df["close"]
        price = close.iloc[-1]

        # Indicators
        rsi_val = rsi(close).iloc[-1]
        macd_df = macd(close)
        macd_hist = macd_df["macd_histogram"].iloc[-1]
        macd_hist_prev = macd_df["macd_histogram"].iloc[-2] if len(macd_df) > 1 else 0
        macd_line = macd_df["macd_line"].iloc[-1]
        signal_line = macd_df["signal_line"].iloc[-1]
        bb = bollinger_bands(close)
        bb_lower = bb["bb_lower"].iloc[-1]
        bb_upper = bb["bb_upper"].iloc[-1]
        bb_mid = bb["bb_middle"].iloc[-1]
        vr = volume_ratio(df).iloc[-1]
        sma20_val = sma(close, 20).iloc[-1]
        sma50_val = sma(close, 50).iloc[-1]
        stoch = stochastic(df)
        stoch_k = stoch["stoch_k"].iloc[-1] if not np.isnan(stoch["stoch_k"].iloc[-1]) else 50
        stoch_d = stoch["stoch_d"].iloc[-1] if not np.isnan(stoch["stoch_d"].iloc[-1]) else 50
        wr = williams_r(df).iloc[-1] if not np.isnan(williams_r(df).iloc[-1]) else -50
        mfi_val = mfi(df).iloc[-1] if not np.isnan(mfi(df).iloc[-1]) else 50

        buy_score, sell_score = 0, 0
        reasons_buy, reasons_sell = [], []

        # ── Mean Reversion Signals ──
        if rsi_val < 30:
            buy_score += 3; reasons_buy.append(f"RSI={rsi_val:.0f} deeply oversold")
        elif rsi_val < 40:
            buy_score += 1; reasons_buy.append(f"RSI={rsi_val:.0f} near oversold")

        if price <= bb_lower * 1.02:
            buy_score += 2; reasons_buy.append(f"Price near BB Lower ({bb_lower:,.0f})")

        if stoch_k < 20 and stoch_k > stoch_d:
            buy_score += 1; reasons_buy.append(f"Stoch bullish cross in oversold")

        if wr < -80:
            buy_score += 1; reasons_buy.append(f"Williams%R={wr:.0f} oversold")

        if mfi_val < 20:
            buy_score += 1; reasons_buy.append(f"MFI={mfi_val:.0f} money flow oversold")

        # ── Momentum Signals ──
        if macd_hist > 0 and macd_hist_prev <= 0:
            buy_score += 2; reasons_buy.append("MACD bullish crossover")
        elif macd_hist > 0 and macd_hist > macd_hist_prev:
            buy_score += 1; reasons_buy.append("MACD histogram expanding")

        if price > sma50_val and vr > 1.5:
            buy_score += 1; reasons_buy.append(f"Above SMA50 + Volume={vr:.1f}x")

        if price > sma20_val and price > sma50_val:
            buy_score += 1; reasons_buy.append("Price above SMA20 & SMA50")

        # ── Sell Signals ──
        if rsi_val > 75:
            sell_score += 3; reasons_sell.append(f"RSI={rsi_val:.0f} deeply overbought")
        elif rsi_val > 65:
            sell_score += 1; reasons_sell.append(f"RSI={rsi_val:.0f} near overbought")

        if macd_hist < 0 and macd_hist_prev >= 0:
            sell_score += 2; reasons_sell.append("MACD death cross")

        if price < sma20_val and vr > 1.3:
            sell_score += 2; reasons_sell.append("Below SMA20 on volume")

        if price >= bb_upper * 0.98:
            sell_score += 1; reasons_sell.append(f"Price near BB Upper ({bb_upper:,.0f})")

        if stoch_k > 80 and stoch_k < stoch_d:
            sell_score += 1; reasons_sell.append("Stoch bearish cross in overbought")

        if wr > -20:
            sell_score += 1; reasons_sell.append(f"Williams%R={wr:.0f} overbought")

        if mfi_val > 80:
            sell_score += 1; reasons_sell.append(f"MFI={mfi_val:.0f} money flow overbought")

        # ── Regime Filter ──
        if regime_info["regime"] in ("DOWNTREND", "WEAK_DOWNTREND"):
            buy_score -= 2; sell_score += 1
        if regime_info["regime"] in ("UPTREND", "WEAK_UPTREND"):
            buy_score += 1

        # ── Sentiment Filter ──
        if sentiment_score < -0.3:
            buy_score -= 1; reasons_sell.append(f"Negative sentiment={sentiment_score:+.2f}")
        elif sentiment_score > 0.3:
            buy_score += 1; reasons_buy.append(f"Positive sentiment={sentiment_score:+.2f}")

        # ── Final Decision ──
        if buy_score >= 4 and buy_score > sell_score:
            action, confidence = "BUY", min(buy_score / 10, 0.95)
            reasons = reasons_buy
        elif sell_score >= 4 and sell_score > buy_score:
            action, confidence = "SELL", min(sell_score / 8, 0.95)
            reasons = reasons_sell
        elif buy_score >= 2 and buy_score > sell_score:
            action, confidence = "WEAK_BUY", min(buy_score / 10, 0.60)
            reasons = reasons_buy
        elif sell_score >= 2 and sell_score > buy_score:
            action, confidence = "WEAK_SELL", min(sell_score / 8, 0.60)
            reasons = reasons_sell
        else:
            action, confidence = "HOLD", 0.5
            reasons = ["Mixed signals, wait for confirmation"]

        bb_position = (price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

        return {
            "action": action,
            "confidence": round(confidence, 2),
            "buy_score": buy_score,
            "sell_score": sell_score,
            "reasons": reasons,
            "regime": regime_info,
            "indicators": {
                "price": round(price, 0),
                "rsi": round(rsi_val, 1),
                "macd_hist": round(macd_hist, 2),
                "macd_line": round(macd_line, 2),
                "signal_line": round(signal_line, 2),
                "bb_position": round(bb_position, 2),
                "bb_lower": round(bb_lower, 0),
                "bb_upper": round(bb_upper, 0),
                "stoch_k": round(stoch_k, 1),
                "williams_r": round(wr, 1),
                "mfi": round(mfi_val, 1),
                "volume_ratio": round(vr, 2),
                "sma20": round(sma20_val, 0),
                "sma50": round(sma50_val, 0),
            },
        }

    # ═══════════════════════════════════════════════
    # LAYER 3: Price Targets
    # ═══════════════════════════════════════════════
    def calculate_price_targets(self, df, action="BUY"):
        """Calculate entry, stop-loss, and take-profit price levels."""
        price = df["close"].iloc[-1]
        atr_val = atr(df).iloc[-1]
        if np.isnan(atr_val) or atr_val <= 0:
            atr_val = price * 0.02
        vwap_val = vwap(df).iloc[-1]
        bb = bollinger_bands(df["close"])
        bb_lower = bb["bb_lower"].iloc[-1]
        bb_upper = bb["bb_upper"].iloc[-1]
        sma20_val = sma(df["close"], 20).iloc[-1]

        if action in ("BUY", "WEAK_BUY"):
            # Entry zones
            entry_conservative = round(price - 0.3 * atr_val, -2)
            entry_aggressive = round(min(vwap_val, bb_lower * 1.01), -2)
            entry_market = round(price, -2)

            # Stop loss
            stop_loss = round(entry_conservative - self.atr_mult_sl * atr_val, -2)
            sl_pct = (entry_conservative - stop_loss) / entry_conservative * 100 if entry_conservative > 0 else 0

            # Take profits (3 levels)
            risk = entry_conservative - stop_loss
            tp1 = round(entry_conservative + 1.5 * risk, -2)
            tp2 = round(entry_conservative + self.rr_ratio * risk, -2)
            tp3 = round(entry_conservative + 3.5 * risk, -2)

            # Trailing stop activation
            trailing_act = round(entry_conservative + 1.5 * risk, -2)

            return {
                "action": action,
                "current_price": round(price, 0),
                "entry_market": entry_market,
                "entry_conservative": entry_conservative,
                "entry_aggressive": entry_aggressive,
                "stop_loss": stop_loss,
                "stop_loss_pct": round(sl_pct, 2),
                "take_profit_1": tp1,
                "take_profit_1_label": "TP1 (R:R=1.5)",
                "take_profit_2": tp2,
                "take_profit_2_label": f"TP2 (R:R={self.rr_ratio})",
                "take_profit_3": tp3,
                "take_profit_3_label": "TP3 (R:R=3.5)",
                "trailing_stop_activation": trailing_act,
                "atr": round(atr_val, 0),
                "vwap": round(vwap_val, 0),
                "scaling_plan": {
                    "phase_1": {"pct": 50, "price": entry_conservative, "note": "Initial position"},
                    "phase_2": {"pct": 30, "price": round(entry_conservative + 0.5 * risk, -2), "note": "Add on confirmation"},
                    "phase_3": {"pct": 20, "price": round(entry_conservative + risk, -2), "note": "Full position on momentum"},
                },
            }
        else:
            return {
                "action": action,
                "current_price": round(price, 0),
                "exit_market": round(price, 0),
                "exit_limit": round(price + 0.2 * atr_val, -2),
                "exit_sma20": round(sma20_val, 0),
                "atr": round(atr_val, 0),
            }

    # ═══════════════════════════════════════════════
    # LAYER 4: Position Sizing
    # ═══════════════════════════════════════════════
    def calculate_position_size(self, capital, entry_price, stop_loss):
        """ATR-based position sizing with lot rounding (100 shares for VN market)."""
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0 or entry_price <= 0:
            return {"shares": 0, "error": "Invalid prices"}

        risk_amount = capital * self.max_risk_pct
        shares_raw = risk_amount / risk_per_share
        shares = int(shares_raw // 100) * 100  # Round to lot of 100

        cost = shares * entry_price
        max_cost = capital * 0.20  # max 20% of capital per position
        if cost > max_cost:
            shares = int(max_cost / entry_price // 100) * 100
            cost = shares * entry_price

        return {
            "shares": shares,
            "cost": round(cost, 0),
            "risk_amount": round(min(risk_amount, shares * risk_per_share), 0),
            "risk_pct_capital": round(shares * risk_per_share / capital * 100, 2),
            "capital_pct": round(cost / capital * 100, 2),
        }

    # ═══════════════════════════════════════════════
    # FULL DECISION (combines all layers)
    # ═══════════════════════════════════════════════
    def full_decision(self, df, capital=500_000_000, ticker="", sentiment_score=0.0):
        """Run complete 5-layer analysis and return actionable decision."""
        signal = self.generate_signal(df, sentiment_score)
        targets = self.calculate_price_targets(df, signal["action"])

        position = {}
        if signal["action"] in ("BUY", "WEAK_BUY") and "stop_loss" in targets:
            position = self.calculate_position_size(
                capital, targets["entry_conservative"], targets["stop_loss"]
            )

        return {
            "ticker": ticker,
            "signal": signal,
            "price_targets": targets,
            "position_sizing": position,
            "summary": self._build_summary(signal, targets, position, ticker),
        }

    def _build_summary(self, signal, targets, position, ticker):
        """Build human-readable summary string."""
        action = signal["action"]
        conf = signal["confidence"]
        regime = signal["regime"]["regime"]
        adx_v = signal["regime"]["adx"]
        ind = signal["indicators"]

        lines = [
            f"{'='*60}",
            f"  {ticker}  |  {action}  (confidence: {conf:.0%})",
            f"{'='*60}",
            f"  Regime: {regime} (ADX={adx_v}, Vol={signal['regime']['volatility']})",
            f"  Price:  {ind['price']:,.0f} VND",
            f"  RSI={ind['rsi']:.0f}  MACD_H={ind['macd_hist']:+.0f}  Stoch_K={ind['stoch_k']:.0f}  MFI={ind['mfi']:.0f}",
            f"  BB: [{ind['bb_lower']:,.0f} – {ind['bb_upper']:,.0f}]  Position={ind['bb_position']:.0%}",
            f"  Volume Ratio: {ind['volume_ratio']:.1f}x",
        ]

        if action in ("BUY", "WEAK_BUY") and "entry_conservative" in targets:
            lines += [
                f"  {'─'*56}",
                f"  ENTRY (conservative): {targets['entry_conservative']:>12,.0f} VND",
                f"  ENTRY (aggressive):   {targets['entry_aggressive']:>12,.0f} VND",
                f"  STOP-LOSS:            {targets['stop_loss']:>12,.0f} VND  ({targets['stop_loss_pct']:.1f}%)",
                f"  TAKE-PROFIT 1 (1.5R): {targets['take_profit_1']:>12,.0f} VND",
                f"  TAKE-PROFIT 2 (2.5R): {targets['take_profit_2']:>12,.0f} VND",
                f"  TAKE-PROFIT 3 (3.5R): {targets['take_profit_3']:>12,.0f} VND",
            ]
            if position and position.get("shares", 0) > 0:
                lines += [
                    f"  {'─'*56}",
                    f"  POSITION SIZE:        {position['shares']:>12,} shares",
                    f"  COST:                 {position['cost']:>12,.0f} VND ({position['capital_pct']:.1f}% capital)",
                    f"  RISK AMOUNT:          {position['risk_amount']:>12,.0f} VND ({position['risk_pct_capital']:.1f}%)",
                ]
                sp = targets.get("scaling_plan", {})
                if sp:
                    lines.append(f"  {'─'*56}")
                    lines.append(f"  SCALING PLAN:")
                    for phase, info in sp.items():
                        lines.append(f"    {phase}: {info['pct']}% @ {info['price']:,.0f} – {info['note']}")
        elif action in ("SELL", "WEAK_SELL"):
            lines += [
                f"  {'─'*56}",
                f"  EXIT (market):  {targets.get('exit_market', 0):>12,.0f} VND",
                f"  EXIT (limit):   {targets.get('exit_limit', 0):>12,.0f} VND",
            ]

        lines += [
            f"  {'─'*56}",
            f"  REASONS:",
        ]
        for r in signal["reasons"]:
            lines.append(f"    • {r}")

        return "\n".join(lines)
