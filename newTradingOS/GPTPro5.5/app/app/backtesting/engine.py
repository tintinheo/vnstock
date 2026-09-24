import pandas as pd
from app.models.analytics import market_regime, stock_scores
from app.signals.scanner import generate_signals
from app.recommendation.decision_engine import build_recommendations
STEP={"1W":5,"2W":10,"1M":20,"3M":60,"5M":100}
def backtest(df,horizon="1M",top_n=5,fee_bps=40, decision_filter=("STRONG_BUY","BUY")):
    dates=sorted(df.date.unique()); step=STEP[horizon]; trades=[]; fee=fee_bps/10000
    for i in range(220,len(dates)-step,step):
        dt=dates[i]; reg=market_regime(df,dt)
        if reg["score"]<50: continue
        sc=stock_scores(df,dt,horizon,reg["score"]); sig=generate_signals(sc,horizon); rec=build_recommendations(sc,sig,reg,horizon)
        picks=rec[rec.recommendation.isin(decision_filter)].head(top_n)
        for _,s in picks.iterrows():
            g=df[(df.symbol==s.symbol)&(df.date>=dt)].sort_values("date").head(step+1)
            if len(g)<=step: continue
            ret=(g.iloc[-1].close*(1-fee))/(g.iloc[0].close*(1+fee))-1; trades.append({"entry_date":dt,"exit_date":g.iloc[-1].date,"symbol":s.symbol,"return":ret,"recommendation":s.recommendation})
    t=pd.DataFrame(trades)
    if t.empty: return t,{"total_trades":0}
    pf=t.loc[t["return"]>0,"return"].sum()/abs(t.loc[t["return"]<0,"return"].sum()) if (t["return"]<0).any() else 999
    return t,{"total_trades":len(t),"avg_return":float(t["return"].mean()),"win_rate":float((t["return"]>0).mean()),"best":float(t["return"].max()),"worst":float(t["return"].min()),"profit_factor":float(pf)}
