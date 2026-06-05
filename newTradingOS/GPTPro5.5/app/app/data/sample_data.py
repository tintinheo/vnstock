from pathlib import Path
import numpy as np, pandas as pd
SYMS={"VCB":"Banking","TCB":"Banking","MBB":"Banking","SSI":"Securities","VND":"Securities","VHM":"Real Estate","HPG":"Steel","FPT":"Technology","MWG":"Retail","GAS":"Oil & Gas","VNINDEX":"Index"}
def generate_sample(path: str|Path, sessions=420, seed=7):
    rng=np.random.default_rng(seed); dates=pd.bdate_range(end=pd.Timestamp.today().normalize(),periods=sessions)
    mret=rng.normal(.0004,.01,sessions); m=1200*np.exp(np.cumsum(mret)); rows=[]
    for s,sec in SYMS.items():
        if s=="VNINDEX": prices=m; base=800_000_000
        else:
            prices=rng.uniform(15,90)*np.exp(np.cumsum(rng.normal(.0002,.018,sessions)+rng.uniform(.7,1.3)*mret)); base=rng.integers(800_000,8_000_000)
        for i,d in enumerate(dates):
            c=float(prices[i]); prev=float(prices[i-1]) if i else c; o=prev*(1+rng.normal(0,.006)); h=max(o,c)*(1+abs(rng.normal(0,.008))); l=min(o,c)*(1-abs(rng.normal(0,.008)))
            v=int(base*rng.lognormal(0,.35)); rows.append({"symbol":s,"date":d.date(),"open":round(o,2),"high":round(h,2),"low":round(l,2),"close":round(c,2),"volume":v,"value":v*c*(1000 if s!="VNINDEX" else 1),"exchange":"HOSE" if s!="VNINDEX" else "INDEX","sector":sec})
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(rows).to_csv(path,index=False); return path
