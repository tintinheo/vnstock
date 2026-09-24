from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import requests
import pandas as pd

@dataclass
class SsiIboardConfig:
    base_url: str = "https://iboard-query.ssi.com.vn"
    timeout_seconds: int = 15
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

class SsiIboardSnapshotProvider:
    """Direct SSI iBoard-style snapshot provider. No vnstock is used."""
    def __init__(self, config: SsiIboardConfig | None = None):
        self.config = config or SsiIboardConfig()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.user_agent,
            "Referer": "https://iboard.ssi.com.vn/",
            "Origin": "https://iboard.ssi.com.vn",
            "Accept": "application/json,text/plain,*/*",
        })
    def _get_json(self, path: str):
        r = self.session.get(f"{self.config.base_url}{path}", timeout=self.config.timeout_seconds)
        r.raise_for_status()
        return r.json()
    @staticmethod
    def _pick(row: dict, *names, default=None):
        for n in names:
            if n in row and row[n] not in [None, ""]:
                return row[n]
        return default
    def get_group_snapshot(self, group: str = "VN30") -> pd.DataFrame:
        payload = self._get_json(f"/stock/group/{group.upper()}")
        data = payload.get("data", payload if isinstance(payload, list) else [])
        now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
        rows=[]
        for it in data:
            if not isinstance(it, dict): continue
            sym=self._pick(it,"stockSymbol","symbol","code","ticker")
            if not sym: continue
            price=self._pick(it,"matchedPrice","lastPrice","price","closePrice","refPrice",default=0)
            vol=self._pick(it,"totalVolume","nmTotalTradedQty","volume","matchedVolume",default=0)
            val=self._pick(it,"totalValue","nmTotalTradedValue","value",default=None)
            chg=self._pick(it,"priceChangePercent","changePercent","changePercentValue",default=0)
            try: price=float(price or 0)
            except Exception: price=0.0
            try: vol=float(vol or 0)
            except Exception: vol=0.0
            try: val=float(val) if val is not None else price*vol
            except Exception: val=price*vol
            rows.append({
                "symbol":str(sym).upper(), "date":now.normalize(), "open":price,"high":price,"low":price,"close":price,
                "volume":vol,"value":val,"exchange":str(self._pick(it,"exchange","market",default=group)).upper(),
                "sector":str(self._pick(it,"sector","industryName",default="Unknown")),"change_pct":chg,
                "snapshot_time":now,"source":"SSI_IBOARD_DIRECT"
            })
        return pd.DataFrame(rows).drop_duplicates(subset=["symbol"]) if rows else pd.DataFrame()
    def get_multiple_group_snapshots(self, groups: Iterable[str]) -> pd.DataFrame:
        frames=[]; errors=[]
        for g in groups:
            try: frames.append(self.get_group_snapshot(g))
            except Exception as ex: errors.append({"group":g,"error":str(ex)})
        if not frames: raise RuntimeError(f"No data fetched. Errors: {errors}")
        df=pd.concat(frames,ignore_index=True).drop_duplicates(subset=["symbol"])
        df.attrs["errors"]=errors
        return df
