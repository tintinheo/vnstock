from __future__ import annotations
import pandas as pd

REGIME_RANK = {"UNKNOWN":0,"BEAR":1,"NEUTRAL":2,"SIDEWAY_UP":3,"BULL":4,"STRONG_BULL":5}

def _confidence(score: float) -> str:
    if score >= 85: return "VERY_HIGH"
    if score >= 75: return "HIGH"
    if score >= 60: return "MEDIUM"
    if score >= 45: return "LOW"
    return "VERY_LOW"

def _position_pct(recommendation: str, confidence: str, risk_reward: float) -> float:
    base = {
        "STRONG_BUY": 0.12,
        "BUY": 0.08,
        "WATCH": 0.00,
        "HOLD": 0.00,
        "REDUCE": -0.30,
        "SELL": -1.00,
        "AVOID": 0.00,
        "RISK_OFF": -0.50,
    }.get(recommendation, 0.0)
    if recommendation in ["STRONG_BUY", "BUY"]:
        if confidence == "VERY_HIGH": base *= 1.15
        elif confidence == "MEDIUM": base *= 0.75
        elif confidence in ["LOW", "VERY_LOW"]: base *= 0.5
        if risk_reward < 2: base *= 0.5
    return round(base, 4)

def build_recommendations(scored: pd.DataFrame, signals: pd.DataFrame, market_regime: dict, horizon: str, current_positions: list[str] | None = None) -> pd.DataFrame:
    """Create final recommendation decisions from score, signal, regime and risk rules.

    Output decisions:
    STRONG_BUY, BUY, WATCH, HOLD, REDUCE, SELL, AVOID, RISK_OFF.
    """
    current_positions = set([s.upper() for s in (current_positions or [])])
    if scored is None or scored.empty:
        return pd.DataFrame()
    sig = signals.copy() if signals is not None and not signals.empty else pd.DataFrame(columns=["symbol"])
    sig_cols = ["symbol","signal_type","entry_low","entry_high","stop_loss","take_profit_1","take_profit_2","risk_reward","reasons"]
    for c in sig_cols:
        if c not in sig.columns: sig[c] = None
    merged = scored.merge(sig[sig_cols], on="symbol", how="left")
    regime_name = market_regime.get("regime", "UNKNOWN")
    regime_score = float(market_regime.get("score", 0))
    regime_rank = REGIME_RANK.get(regime_name, 0)
    rows=[]
    for _, r in merged.iterrows():
        reasons=[]; risks=[]; invalid=[]
        score=float(r.get("stock_score",0) or 0)
        sector_score=float(r.get("sector_score",50) or 50)
        liquidity_score=float(r.get("liquidity_score",0) or 0)
        risk_score=float(r.get("risk_score",50) or 50)
        signal_type=r.get("signal_type") if pd.notna(r.get("signal_type")) else None
        rr=float(r.get("risk_reward",2.0) or 2.0)
        held = str(r.symbol).upper() in current_positions

        if regime_rank <= 1:
            recommendation="RISK_OFF" if held else "AVOID"
            risks.append("Market regime is weak or bearish")
        elif signal_type in ["BREAKOUT_BUY", "PULLBACK_BUY", "TREND_FOLLOWING_BUY"] and score>=85 and sector_score>=70 and liquidity_score>=50 and rr>=2:
            recommendation="STRONG_BUY"
            reasons += ["Confirmed buy signal", "Stock score >= 85", "Sector score >= 70", "Risk/reward acceptable"]
        elif signal_type in ["BREAKOUT_BUY", "PULLBACK_BUY", "TREND_FOLLOWING_BUY"] and score>=75 and sector_score>=60 and liquidity_score>=40 and rr>=1.7:
            recommendation="BUY"
            reasons += ["Confirmed buy signal", "Stock score >= 75", "Sector score supportive"]
        elif held and score>=65 and regime_rank>=2:
            recommendation="HOLD"
            reasons += ["Position is already held", "Score remains acceptable", "Market regime not bearish"]
        elif held and (score<55 or sector_score<45 or regime_rank==2):
            recommendation="REDUCE"
            risks += ["Score, sector or market condition weakened"]
        elif held and (score<45 or regime_rank<=1):
            recommendation="SELL"
            risks += ["Trend or market thesis invalidated"]
        elif score>=65 and sector_score>=55 and regime_rank>=3:
            recommendation="WATCH"
            reasons += ["Setup is improving but no confirmed entry signal yet"]
        else:
            recommendation="AVOID"
            risks += ["No confirmed edge", "Score or liquidity not sufficient"]

        if liquidity_score < 30: risks.append("Liquidity score is low")
        if risk_score < 30: risks.append("Volatility/risk score is weak")
        if sector_score < 45: risks.append("Sector score is weak")
        if regime_score < 55: risks.append("Market regime score below aggressive threshold")

        if signal_type: reasons.append(f"Signal: {signal_type}")
        reasons.append(f"Market regime: {regime_name} ({regime_score:.0f})")
        reasons.append(f"Stock score: {score:.1f}")
        reasons.append(f"Sector score: {sector_score:.1f}")

        invalid += [
            "Close below MA20 with high selling volume",
            "Market regime drops to BEAR or RISK_OFF",
            "Sector score falls below 45",
            "Stop loss is hit",
        ]
        confidence_score = min(100, max(0, 0.45*score + 0.20*sector_score + 0.15*liquidity_score + 0.10*risk_score + 0.10*regime_score))
        confidence = _confidence(confidence_score)
        action = {
            "STRONG_BUY":"Open or add position within risk limit",
            "BUY":"Open position if entry zone is respected",
            "WATCH":"Wait for confirmation or pullback entry",
            "HOLD":"Keep position and trail stop",
            "REDUCE":"Reduce exposure or tighten stop",
            "SELL":"Exit position according to risk rule",
            "AVOID":"Do not open new position",
            "RISK_OFF":"Prioritize capital protection",
        }[recommendation]
        rows.append({
            "symbol": r.symbol, "sector": r.sector, "horizon": horizon,
            "recommendation": recommendation, "confidence": confidence, "confidence_score": round(confidence_score,2),
            "action": action, "suggested_position_pct_nav": _position_pct(recommendation, confidence, rr),
            "close": round(float(r.close),2),
            "entry_low": r.get("entry_low"), "entry_high": r.get("entry_high"), "stop_loss": r.get("stop_loss"),
            "take_profit_1": r.get("take_profit_1"), "take_profit_2": r.get("take_profit_2"), "risk_reward": rr,
            "stock_score": round(score,2), "sector_score": round(sector_score,2), "liquidity_score": round(liquidity_score,2),
            "signal_type": signal_type or "NONE",
            "decision_reasons": " | ".join(dict.fromkeys(reasons)),
            "decision_risks": " | ".join(dict.fromkeys(risks)),
            "invalidation_conditions": " | ".join(invalid),
        })
    order = {"STRONG_BUY":1,"BUY":2,"HOLD":3,"WATCH":4,"REDUCE":5,"SELL":6,"RISK_OFF":7,"AVOID":8}
    out=pd.DataFrame(rows)
    out["sort_key"]=out.recommendation.map(order).fillna(99)
    return out.sort_values(["sort_key","confidence_score"], ascending=[True,False]).drop(columns="sort_key").reset_index(drop=True)

def build_realtime_recommendations(scan: pd.DataFrame) -> pd.DataFrame:
    """Recommendation layer for realtime snapshot-only mode."""
    if scan is None or scan.empty: return pd.DataFrame()
    rows=[]
    for _, r in scan.iterrows():
        score=float(r.get("realtime_score",0) or 0); change=float(r.get("change_pct_num",0) or 0)
        if r.get("signal_type") == "REALTIME_RISK_ALERT": rec="RISK_OFF"; conf="MEDIUM"; action="Avoid new entry or tighten risk"
        elif score>=85 and change>0: rec="WATCH"; conf="HIGH"; action="Add to intraday watchlist, wait for historical confirmation"
        elif score>=70: rec="WATCH"; conf="MEDIUM"; action="Monitor liquidity and confirm with historical chart"
        else: rec="AVOID"; conf="LOW"; action="No realtime edge"
        rows.append({
            "symbol":r.symbol,"exchange":r.get("exchange"),"sector":r.get("sector"),"recommendation":rec,"confidence":conf,
            "action":action,"close":r.get("close"),"change_pct":change,"value":r.get("value"),
            "realtime_score":round(score,2),"signal_type":r.get("signal_type"),
            "decision_reasons":"Realtime snapshot only: liquidity and momentum based",
            "invalidation_conditions":"Requires historical confirmation before BUY decision"
        })
    return pd.DataFrame(rows)
