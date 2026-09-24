from pathlib import Path
import pandas as pd
REQUIRED=["symbol","date","open","high","low","close","volume","value","exchange","sector"]
def load_ohlcv_csv(path: str|Path) -> pd.DataFrame:
    df=pd.read_csv(path)
    missing=[c for c in REQUIRED if c not in df.columns]
    if missing: raise ValueError(f"Missing columns: {missing}")
    df=df.copy(); df["date"]=pd.to_datetime(df["date"])
    for c in ["open","high","low","close","volume","value"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["symbol"]=df["symbol"].astype(str).str.upper().str.strip()
    df["exchange"]=df["exchange"].astype(str).str.upper().str.strip()
    df["sector"]=df["sector"].astype(str).str.strip()
    return df.dropna(subset=["date","symbol","close"]).sort_values(["symbol","date"]).reset_index(drop=True)
