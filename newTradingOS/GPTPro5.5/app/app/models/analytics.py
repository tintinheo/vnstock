import pandas as pd, numpy as np
RET={"1W":"return_5d","2W":"return_10d","1M":"return_20d","3M":"return_60d","5M":"return_100d"}
def pct(s): return s.rank(pct=True).fillna(.5)*100
def market_regime(df, as_of, index_symbol="VNINDEX"):
    d=df[df.date<=pd.to_datetime(as_of)]; idx=d[d.symbol==index_symbol].sort_values("date")
    if idx.empty: return {"regime":"UNKNOWN","score":0,"exposure":(0,0),"explanation":["Index not found"]}
    r=idx.iloc[-1]; score=0; exp=[]
    for w,pts in [(20,15),(50,20),(200,20)]:
        if r.close>r.get(f"ma_{w}",np.inf): score+=pts; exp.append(f"Index above MA{w}")
    if r.get("ma_50",0)>r.get("ma_200",0): score+=10; exp.append("MA50 above MA200")
    latest=d[d.date==r.date]; uni=latest[latest.symbol!=index_symbol]
    if len(uni):
        breadth=(uni.close>uni.ma_50).mean(); score += 20 if breadth>.6 else 10 if breadth>.45 else 0; exp.append(f"Breadth {breadth:.0%}")
    regime="STRONG_BULL" if score>=85 else "BULL" if score>=70 else "SIDEWAY_UP" if score>=55 else "NEUTRAL" if score>=40 else "BEAR"
    exposure={"STRONG_BULL":(.8,1),"BULL":(.6,.8),"SIDEWAY_UP":(.4,.6),"NEUTRAL":(.2,.4),"BEAR":(0,.2)}[regime]
    return {"date":r.date,"regime":regime,"score":float(score),"exposure":exposure,"explanation":exp}
def sector_scores(df, as_of, horizon="1M"):
    latest=df[df.date<=pd.to_datetime(as_of)].sort_values("date").groupby("symbol",as_index=False).tail(1); latest=latest[latest.sector.str.lower()!="index"].copy()
    if latest.empty: return latest
    rc=RET[horizon]; agg=latest.groupby("sector").agg(avg_return=(rc,"mean"),avg_rs=("rs_vs_index_20d","mean"),avg_liq=("value_ma20","mean"),breadth=("close",lambda x:np.nan),count=("symbol","count")).reset_index()
    br=latest.assign(above=latest.close>latest.ma_50).groupby("sector").above.mean().reset_index(name="breadth"); agg=agg.drop(columns="breadth").merge(br,on="sector")
    for c in ["avg_return","avg_rs","avg_liq","breadth"]: agg[c+"_score"]=pct(agg[c])
    agg["sector_score"]=.3*agg.avg_rs_score+.25*agg.avg_liq_score+.25*agg.avg_return_score+.2*agg.breadth_score
    return agg.sort_values("sector_score",ascending=False)
def stock_scores(df, as_of, horizon, regime_score):
    latest=df[df.date<=pd.to_datetime(as_of)].sort_values("date").groupby("symbol",as_index=False).tail(1); latest=latest[latest.sector.str.lower()!="index"].copy()
    if latest.empty: return latest
    ss=sector_scores(df,as_of,horizon)[["sector","sector_score"]]; latest=latest.merge(ss,on="sector",how="left")
    latest["technical_score"]=((latest.close>latest.ma_20).astype(int)+(latest.close>latest.ma_50).astype(int)+(latest.ma_20>latest.ma_50).astype(int)+(latest.macd_hist>0).astype(int)+latest.rsi_14.between(45,75).astype(int))/5*100
    latest["liquidity_score"]=pct(latest.value_ma20); latest["rs_score"]=pct(latest.rs_vs_index_20d); latest["risk_score"]=(100-pct(latest.volatility_20d)).clip(0,100); latest["sector_score"]=latest.sector_score.fillna(50)
    latest["stock_score"]=(.3*latest.technical_score+.2*latest.liquidity_score+.2*latest.rs_score+.2*latest.sector_score+.1*latest.risk_score).clip(0,100)
    latest["rank"]=latest.stock_score.rank(ascending=False,method="first").astype(int)
    return latest.sort_values("stock_score",ascending=False)
