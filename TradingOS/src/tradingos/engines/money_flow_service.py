"""Money Flow Service — DTL Dashboard orchestration (SRS §3.4, FR-6)."""
from __future__ import annotations

import json
from pathlib import Path

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


def _mapping_file_path() -> Path:
    rel_path = str(cfg.strategy("sectors", "mapping_file", default="data/sector_map.json"))
    root = Path(__file__).resolve().parents[3]
    return root / rel_path


def _canonical_sector_from_record(record: dict) -> str:
    text = f"{record.get('industry', '')} {record.get('sub_sector', '')}".lower()
    if "ngân hàng" in text:
        return "Ngân hàng"
    if "chứng khoán" in text or "dịch vụ tài chính" in text:
        return "Chứng khoán"
    if "công nghệ" in text or "phần mềm" in text or "máy tính" in text:
        return "Công nghệ"
    if "bất động sản" in text:
        return "BĐS"
    if "thép" in text or "kim loại" in text:
        return "Thép"
    if "hàng không" in text:
        return "Hàng không"
    if "dầu khí" in text or "năng lượng" in text or "tiện ích" in text:
        return "Năng lượng"
    if "bán lẻ" in text or "thực phẩm" in text or "tiêu dùng" in text:
        return "Bán lẻ"
    return str(record.get("industry") or "OTHER").strip() or "OTHER"


def _load_sector_groups() -> dict[str, list[str]]:
    groups = {k: list(v) for k, v in _SECTOR_TICKERS.items()}
    path = _mapping_file_path()
    if not path.exists():
        return groups
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.debug(f"Could not load sector map JSON: {e}")
        return groups

    for ticker, record in raw.items():
        if not isinstance(record, dict):
            continue
        sector_name = _canonical_sector_from_record(record)
        bucket = groups.setdefault(sector_name, [])
        sym = str(ticker).upper().strip()
        if sym and sym not in bucket:
            bucket.append(sym)
    return groups


def infer_sector_name(ticker: str) -> str:
    ticker = ticker.strip().upper()
    for sector, tickers in _SECTOR_TICKERS.items():
        if ticker in tickers:
            return sector
    for sector, tickers in _load_sector_groups().items():
        if ticker in tickers:
            return sector
    cached = cache.get_sector(ticker)
    return cached if cached and cached != "OTHER" else "OTHER"


def sector_flow_lookup(rotation_result: dict, ticker: str) -> str:
    sector = infer_sector_name(ticker)
    for row in rotation_result.get("rankings", []):
        if row.get("sector") == sector:
            return str(row.get("flow_status", "NEUTRAL"))
    return "NEUTRAL"


class MoneyFlowService:
    def _build_sector_index(self, dfs: list[pd.DataFrame]) -> pd.DataFrame:
        """Aggregate multiple ticker OHLCV series into an equal-weight sector index."""
        merged = pd.concat(dfs, ignore_index=True)
        if merged.empty or "date" not in merged.columns:
            return pd.DataFrame()

        sector_df = (
            merged.groupby("date", as_index=False)
            .agg({
                "open": "mean",
                "high": "mean",
                "low": "mean",
                "close": "mean",
                "volume": "sum",
            })
            .sort_values("date")
            .reset_index(drop=True)
        )
        return compute_indicators(sector_df)

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
        try:
            rotation = self.get_sector_flows([infer_sector_name(ticker)])
            sector_flow = sector_flow_lookup(rotation, ticker)
        except Exception:
            sector_flow = "NEUTRAL"
        return {**sms, "mcvd_detail": mcvd, "stealth_detail": stealth, "sector_flow": sector_flow}

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
        sector_groups = _load_sector_groups()
        sectors = sector_names or list(sector_groups.keys())
        sector_ohlcv: dict[str, pd.DataFrame] = {}
        sector_sms: dict[str, dict] = {}

        for sector in sectors:
            tickers = sector_groups.get(sector, [])
            dfs = []
            sms_vals = []
            for t in tickers:
                try:
                    df = fetch_ohlcv(t, days=60)
                    if not df.empty:
                        df = compute_indicators(df)  # needed for OBV column in sector scoring
                        dfs.append(df)
                        flow_df = proxy_whale_net_from_daily(df)
                        sms = compute_smart_money_score(t, df, flow_df, None, None, "RANGING")
                        sms_float = float(sms.get("sms", 50.0)) if isinstance(sms, dict) else float(sms)
                        sms_vals.append(sms_float)
                        if len(dfs) >= 3:
                            break
                except Exception:
                    pass
            if dfs:
                sector_df = self._build_sector_index(dfs)
                if not sector_df.empty:
                    sector_ohlcv[sector] = sector_df
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
