"""data/kbs_client.py – KB Securities direct API. Uses IIS server only.

IIS Base: https://kbbuddywts.kbsec.com.vn/iis-server/investment
Historical: GET /stocks/{symbol}/data_day?sdate=DD-MM-YYYY&edate=DD-MM-YYYY
"""
import requests
import pandas as pd
from datetime import datetime
import logging, time

logger = logging.getLogger(__name__)

IIS = "https://kbbuddywts.kbsec.com.vn/iis-server/investment"


class KBSClient:
    def __init__(self, timeout=20, max_retries=3):
        self.s = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
            "Accept": "application/json",
        })

    def get_ohlcv(self, ticker: str, start="2020-01-01", end=None) -> pd.DataFrame:
        ticker = ticker.upper().strip()
        if end is None: end = datetime.now().strftime("%Y-%m-%d")
        sd = datetime.strptime(start, "%Y-%m-%d").strftime("%d-%m-%Y")
        ed = datetime.strptime(end, "%Y-%m-%d").strftime("%d-%m-%Y")

        url = f"{IIS}/stocks/{ticker}/data_day"
        params = {"sdate": sd, "edate": ed}

        for attempt in range(self.max_retries):
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    time.sleep(3*(attempt+1)); continue
                r.raise_for_status()
                body = r.json()

                # KBS returns: {"symbol":"VCG","data_day":[{t,o,h,l,c,v},...]}
                bars = body.get("data_day", body.get("data", []))
                if not bars:
                    logger.warning(f"[KBS] Empty for {ticker}")
                    return pd.DataFrame()

                df = pd.DataFrame(bars)
                col_map = {"t":"date","o":"open","h":"high","l":"low","c":"close","v":"volume"}
                df = df.rename(columns=col_map)

                if "date" not in df.columns:
                    logger.error(f"[KBS] {ticker}: no date col. {list(df.columns)}")
                    return pd.DataFrame()

                df["date"] = pd.to_datetime(df["date"])
                for c in ["open","high","low","close"]:
                    if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
                if "volume" in df.columns:
                    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

                # Price normalization
                if "close" in df.columns and len(df) > 0:
                    med = df["close"].median()
                    if med < 500:
                        for c in ["open","high","low","close"]:
                            if c in df.columns: df[c] = (df[c]*1000).round(0)
                        logger.info(f"[KBS] {ticker}: x1000→VND")
                    else:
                        for c in ["open","high","low","close"]:
                            if c in df.columns: df[c] = df[c].round(0)

                req = ["date","open","high","low","close","volume"]
                miss = [c for c in req if c not in df.columns]
                if miss:
                    logger.error(f"[KBS] {ticker}: missing {miss}")
                    return pd.DataFrame()

                df = df[req].dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
                df["_source"] = "KBS"
                if len(df) > 0:
                    logger.info(f"[KBS] ✅ {ticker}: {len(df)} bars, last={df['close'].iloc[-1]:,.0f}")
                return df

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[KBS] Conn error {ticker} (attempt {attempt+1})")
                time.sleep(2**attempt)
            except Exception as e:
                logger.warning(f"[KBS] {ticker}: {type(e).__name__}: {e}")
                break

        logger.error(f"[KBS] ❌ {ticker} failed")
        return pd.DataFrame()
