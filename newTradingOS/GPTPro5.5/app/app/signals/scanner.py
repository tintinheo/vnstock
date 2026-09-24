import pandas as pd
def scan_realtime(snapshot, min_value=1_000_000_000):
    if snapshot.empty: return pd.DataFrame()
    df=snapshot.copy(); df["close"]=pd.to_numeric(df.close,errors="coerce").fillna(0); df["volume"]=pd.to_numeric(df.volume,errors="coerce").fillna(0); df["value"]=pd.to_numeric(df.value,errors="coerce").fillna(df.close*df.volume); df["change_pct_num"]=pd.to_numeric(df.get("change_pct",0),errors="coerce").fillna(0)
    df=df[df.value>=min_value].copy() if (df.value>=min_value).any() else df.copy(); df["liquidity_score"]=df.value.rank(pct=True)*100; df["momentum_score"]=df.change_pct_num.rank(pct=True)*100; df["realtime_score"]=.65*df.liquidity_score+.35*df.momentum_score
    df["signal_type"]="REALTIME_WATCH"; df.loc[(df.realtime_score>=80)&(df.change_pct_num>0),"signal_type"]="REALTIME_MOMENTUM_WATCH"; df.loc[df.change_pct_num<-2,"signal_type"]="REALTIME_RISK_ALERT"
    return df.sort_values("realtime_score",ascending=False)
def generate_signals(scored, horizon="1M"):
    rows=[]
    for _,r in scored.iterrows():
        typ=None; reasons=[]
        if r.stock_score>=75 and r.close>=r.high_20d*.995 and r.volume_ratio_5_20>1.1: typ="BREAKOUT_BUY"; reasons=["high score","near 20D high","volume expansion"]
        elif r.stock_score>=70 and r.close>r.ma_50 and r.close<=r.ma_20*1.03: typ="PULLBACK_BUY"; reasons=["uptrend","near MA20"]
        elif horizon in ["1M","3M","5M"] and r.stock_score>=72 and r.close>r.ma_50: typ="TREND_FOLLOWING_BUY"; reasons=["trend following setup"]
        if typ:
            atr=r.atr_14 if pd.notna(r.atr_14) else r.close*.03; mult={"1W":1.5,"2W":2,"1M":2.2,"3M":2.5,"5M":3}.get(horizon,2.2); stop=max(0,r.close-mult*atr); risk=max(r.close-stop,r.close*.01)
            rows.append({"symbol":r.symbol,"sector":r.sector,"horizon":horizon,"signal_type":typ,"score":round(float(r.stock_score),2),"close":round(float(r.close),2),"entry_low":round(float(r.close*.99),2),"entry_high":round(float(r.close*1.01),2),"stop_loss":round(float(stop),2),"take_profit_1":round(float(r.close+2*risk),2),"take_profit_2":round(float(r.close+3*risk),2),"risk_reward":2.0,"reasons":"; ".join(reasons)})
    return pd.DataFrame(rows).sort_values("score",ascending=False) if rows else pd.DataFrame()
