"""Money Flow Service — DTL Dashboard orchestration (SRS §3.4, FR-6)."""
from __future__ import annotations

import pandas as pd

from ..data.fetcher import fetch_ohlcv
from ..data.cache import cache
from ..core import (
    compute_indicators,
    compute_smart_money_score,
    detect_stealth_accumulation,
    detect_sector_rotation,
    detect_whale_distribution,
)
from ..core.money_flow import proxy_whale_net_from_daily, compute_multiday_whale_flow
from ..utils.logging import get_logger
from ..utils.config import cfg

log = get_logger("money_flow_service")

_SECTOR_TICKERS = {
    "BĐS":       ["VIC", "VHM", "NVL", "PDR", "KDH"],
    "Ngân hàng": ["VCB", "BID", "CTG", "TCB", "MBB"],
    "Thép":      ["HPG", "HSG", "NKG", "TLH", "VGS"],
    "Hàng không":["HVN", "VJC"],
    "Bán lẻ":    ["MWG", "FRT", "PNJ"],
    "Năng lượng":["GAS", "PLX", "PVT", "PVS"],
    "Công nghệ": ["FPT", "CMG"],
    "Chứng khoán":["SSI", "VND", "HCM", "VCI"],
}


class MoneyFlowService:
    def get_sms(self, ticker: str) -> dict:
        """Full SMS for a single ticker."""
        df = fetch_ohlcv(ticker, days=120)
        if df.empty:
            return {"sms": 0, "sms_label": "NO_DATA"}
        df = compute_indicators(df)
        flow_df = proxy_whale_net_from_daily(df)
        mcvd = compute_multiday_whale_flow(flow_df)
        sms = compute_smart_money_score(ticker, df, flow_df, None, None, "RANGING")
        stealth = detect_stealth_accumulation(df, flow_df)
        return {**sms, "mcvd_detail": mcvd, "stealth_detail": stealth}

    def get_distribution_status(self, ticker: str) -> dict:
        """Distribution warning level for a ticker."""
        df = fetch_ohlcv(ticker, days=60)
        if df.empty:
            return {"level": "NONE", "score": 0}
        flow_df = proxy_whale_net_from_daily(df)
        return detect_whale_distribution(df, flow_df)

    def get_whale_watchlist(self, tickers: list[str] | None = None) -> pd.DataFrame:
        """
        SMS scan for watchlist, returns DataFrame sorted by SMS.
        tickers=None uses cached watchlist.
        """
        if tickers is None:
            tickers = cache.get_watchlist()

        rows = []
        for t in tickers:
            try:
                sms_data = self.get_sms(t)
                dist = self.get_distribution_status(t)
                rows.append({
                    "ticker": t,
                    "sms": sms_data.get("sms", 0),
                    "sms_label": sms_data.get("sms_label", "—"),
                    "mcvd_trend": sms_data.get("mcvd_detail", {}).get("mcvd_trend", "FLAT"),
                    "stealth": sms_data.get("stealth_detail", {}).get("detected", False),
                    "dist_warning": dist.get("level", "NONE"),
                })
            except Exception as e:
                log.debug(f"Watchlist SMS error {t}: {e}")

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("sms", ascending=False).reset_index(drop=True)
        return df

    def get_sector_flows(self, sector_names: list[str] | None = None) -> dict:
        """
        Compute sector rotation signals.
        Returns result from detect_sector_rotation().
        """
        sectors = sector_names or list(_SECTOR_TICKERS.keys())
        sector_ohlcv: dict[str, pd.DataFrame] = {}
        sector_sms: dict[str, dict] = {}

        for sector in sectors:
            tickers = _SECTOR_TICKERS.get(sector, [])
            dfs = []
            sms_vals = []
            for t in tickers[:3]:   # top-3 per sector for speed
                try:
                    df = fetch_ohlcv(t, days=60)
                    if not df.empty:
                        dfs.append(df)
                        flow_df = proxy_whale_net_from_daily(df)
                        sms = compute_smart_money_score(t, df, flow_df, None, None, "RANGING")
                        sms_float = float(sms.get("sms", 50.0)) if isinstance(sms, dict) else float(sms)
                        sms_vals.append(sms_float)
                except Exception:
                    pass
            if dfs:
                sector_ohlcv[sector] = pd.concat(dfs).drop_duplicates()
            if sms_vals:
                sector_sms[sector] = sms_vals

        return detect_sector_rotation(sector_ohlcv, sector_sms)

    def get_mcvd_chart_data(self, ticker: str, days: int = 20) -> pd.DataFrame:
        """Return M-CVD bar data for chart component."""
        df = fetch_ohlcv(ticker, days=days + 5)
        if df.empty:
            return pd.DataFrame()
        flow_df = proxy_whale_net_from_daily(df)
        flow_df["date"] = flow_df.index if flow_df.index.dtype != "O" else flow_df.index
        return flow_df.tail(days)[["date", "whale_net", "whale_net_cumulative"]
                                   if "whale_net_cumulative" in flow_df.columns
                                   else ["date", "whale_net"]]
