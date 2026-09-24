import numpy as np, pandas as pd
def rsi(close, period=14):
    d=close.diff(); gain=d.clip(lower=0); loss=-d.clip(upper=0)
    rs=gain.ewm(alpha=1/period,adjust=False).mean()/loss.ewm(alpha=1/period,adjust=False).mean().replace(0,np.nan)
    return 100-100/(1+rs)
def add_indicators(df):
    out=[]
    for _,g in df.sort_values(["symbol","date"]).groupby("symbol",sort=False):
        g=g.copy(); c=g.close
        for w in [5,10,20,50,100,200]: g[f"ma_{w}"]=c.rolling(w,min_periods=max(3,w//4)).mean()
        ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean(); g["macd"]=ema12-ema26; g["macd_signal"]=g.macd.ewm(span=9,adjust=False).mean(); g["macd_hist"]=g.macd-g.macd_signal
        tr=pd.concat([(g.high-g.low),(g.high-g.close.shift()).abs(),(g.low-g.close.shift()).abs()],axis=1).max(axis=1); g["atr_14"]=tr.ewm(alpha=1/14,adjust=False).mean(); g["rsi_14"]=rsi(c)
        for w in [1,5,10,20,60,100]: g[f"return_{w}d"]=c.pct_change(w)
        g["volume_ma20"]=g.volume.rolling(20,min_periods=5).mean(); g["volume_ratio_5_20"]=g.volume.rolling(5,min_periods=3).mean()/g.volume_ma20
        g["value_ma20"]=g.value.rolling(20,min_periods=5).mean(); g["volatility_20d"]=g.return_1d.rolling(20,min_periods=10).std(); g["high_20d"]=g.high.rolling(20,min_periods=5).max()
        out.append(g)
    return pd.concat(out,ignore_index=True)
def add_relative_strength(df,index_symbol="VNINDEX"):
    idx=df[df.symbol==index_symbol][["date","return_20d","return_60d"]].rename(columns={"return_20d":"idx_return_20d","return_60d":"idx_return_60d"})
    df=df.merge(idx,on="date",how="left"); df["rs_vs_index_20d"]=df.return_20d-df.idx_return_20d; df["rs_vs_index_60d"]=df.return_60d-df.idx_return_60d
    sec=df.groupby(["date","sector"],as_index=False).return_20d.mean().rename(columns={"return_20d":"sector_return_20d"}); df=df.merge(sec,on=["date","sector"],how="left"); df["rs_vs_sector_20d"]=df.return_20d-df.sector_return_20d
    return df
