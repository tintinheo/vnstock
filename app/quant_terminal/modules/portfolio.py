"""
Portfolio manager — loads SSI iBoard Excel exports, enriches with live prices,
saves snapshots, and tracks changes (trade detection).
"""
import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from config import PORTFOLIO_DIR, TRADE_LOG_DIR, SETTLEMENT_DAYS, VN_PUBLIC_HOLIDAYS


# ─── RISK CLASSIFICATION ─────────────────────────────────────────────────────

def classify_risk(row: dict) -> tuple:
    """Return (risk_label, color_hex) for a position."""
    pnl_pct = row.get("pnl_pct", 0)
    weight  = row.get("weight_pct", 0)

    if pnl_pct < -3 and weight > 8:
        return "Rất cao", "#DC2626"
    if pnl_pct < -1.5 and weight > 5:
        return "Cao", "#F59E0B"
    if pnl_pct > 5 and weight > 5:
        return "Thấp — chốt lời", "#16A34A"
    if weight < 2:
        return "Nhỏ — xem xét thanh lý", "#6B7280"
    if pnl_pct >= 0:
        return "Thấp", "#16A34A"
    return "Trung bình", "#F59E0B"


# ─── VECTORIZED NUMERIC CLEANER ──────────────────────────────────────────────

def _clean_series(s: pd.Series) -> pd.Series:
    """
    Vectorized: clean a string Series of VN number format into float.
    Handles: "2,580" -> 2580.0 | "1.16%" -> 1.16 | "-" -> 0.0 | pd.NA -> 0.0
    Works correctly with both StringDtype (pd.NA) and object dtype (np.nan).
    """
    # Convert everything to str, replacing any NA-like with "0"
    out = s.astype(str).str.strip()
    # Replace placeholder dashes and other non-numeric markers
    out = out.replace({"nan": "0", "None": "0", "<NA>": "0", "—": "0", "-": "0", "N/A": "0"})
    # Remove thousands separator and percent sign
    out = out.str.replace(",", "", regex=False)
    out = out.str.replace("%", "", regex=False)
    # Empty string -> 0
    out = out.replace("", "0")
    # Convert to numeric, coercing any remaining garbage to NaN then fill 0
    return pd.to_numeric(out, errors="coerce").fillna(0.0)


# ─── SSI EXCEL PARSER ────────────────────────────────────────────────────────

def parse_ssi_excel(filepath) -> pd.DataFrame:
    """
    Parse an SSI iBoard portfolio Excel export.
    Returns a clean DataFrame with standardized columns.
    """
    filepath = Path(filepath)

    # Read raw to find header row
    df_raw = pd.read_excel(filepath, header=None, dtype=str)
    header_row = None
    for i, row in df_raw.iterrows():
        row_str = " ".join(str(v) for v in row.values if pd.notna(v))
        if "Mã CK" in row_str or "Symbol" in row_str:
            header_row = i
            break

    if header_row is None:
        raise ValueError(f"Cannot find header row in {filepath.name}")

    # Re-read with correct header, keep as string to avoid type ambiguity
    df = pd.read_excel(filepath, header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    # ── Map columns to standard names ────────────────────────────────────────
    col_map = {}
    for col in df.columns:
        c = col.lower().replace("\n", " ")
        if "mã ck" in c or "symbol" in c:
            col_map[col] = "symbol"
        elif "tổng khối lượng" in c or "total volume" in c:
            col_map[col] = "total_qty"
        elif "khối lượng giao dịch" in c or "tradeable" in c:
            col_map[col] = "tradeable_qty"
        elif "giá vốn" in c or "avg cost" in c:
            col_map[col] = "cost_price"
        elif "giá thị trường" in c or "market price" in c:
            col_map[col] = "market_price"
        elif ("giá trị vốn" in c) or ("cost value" in c) or ("giá trị cp" in c and "vốn" in c):
            col_map[col] = "cost_value"
        elif "giá trị tt" in c or "market value" in c:
            col_map[col] = "market_value"
        elif "lãi/ lỗ" in c and "%" not in c:
            col_map[col] = "pnl"
        elif "% lãi/ lỗ" in c or "% profit" in c:
            col_map[col] = "pnl_pct_str"
        elif "% dm" in c or "% weight" in c:
            col_map[col] = "weight_pct_str"

    df = df.rename(columns=col_map)

    # Keep only mapped columns
    keep = [c for c in col_map.values() if c in df.columns]
    df = df[keep].copy()

    # ── Filter valid stock rows ───────────────────────────────────────────────
    if "symbol" not in df.columns:
        raise ValueError("Column 'symbol' not found after mapping.")

    # Convert symbol to string cleanly
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df = df[df["symbol"].str.match(r"^[A-Z]{2,5}$", na=False)].copy()
    df = df.reset_index(drop=True)

    if df.empty:
        raise ValueError("No valid stock rows found in the file.")

    # ── Clean numeric columns (vectorized, no apply) ──────────────────────────
    for col in ["total_qty", "tradeable_qty", "cost_price", "market_price",
                "cost_value", "market_value", "pnl"]:
        if col in df.columns:
            df[col] = _clean_series(df[col])

    # ── Tradeable qty: "-" means 0 (already handled by _clean_series) ────────
    # But also handle the case where it might have been read as NaN
    if "tradeable_qty" in df.columns:
        df["tradeable_qty"] = df["tradeable_qty"].fillna(0)

    # ── P&L percent ──────────────────────────────────────────────────────────
    if "pnl_pct_str" in df.columns:
        df["pnl_pct"] = _clean_series(df["pnl_pct_str"])
    elif "cost_value" in df.columns and "pnl" in df.columns:
        cost_nonzero = df["cost_value"].replace(0, np.nan)
        df["pnl_pct"] = (df["pnl"] / cost_nonzero * 100).fillna(0)

    # ── Portfolio weight ──────────────────────────────────────────────────────
    if "weight_pct_str" in df.columns:
        df["weight_pct"] = _clean_series(df["weight_pct_str"])
    elif "market_value" in df.columns:
        total_mv = df["market_value"].sum()
        df["weight_pct"] = (df["market_value"] / total_mv * 100).round(2) if total_mv > 0 else 0.0

    # ── Metadata ─────────────────────────────────────────────────────────────
    df["source_file"] = filepath.name
    df["loaded_at"]   = dt.datetime.now().isoformat()

    return df


# ─── PORTFOLIO CLASS ─────────────────────────────────────────────────────────

class Portfolio:
    def __init__(self):
        self.df: pd.DataFrame = pd.DataFrame()
        self.loaded_file: str = ""
        self.loaded_at:   str = ""
        self.total_cost:   float = 0
        self.total_market: float = 0
        self.total_pnl:    float = 0
        self.total_pnl_pct:float = 0

    def load_from_file(self, filepath) -> "Portfolio":
        self.df = parse_ssi_excel(filepath)
        self.loaded_file = Path(filepath).name
        self.loaded_at   = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        self._recompute_totals()
        return self

    def enrich_with_live_prices(self, quotes: dict) -> "Portfolio":
        if self.df.empty:
            return self
        for idx, row in self.df.iterrows():
            sym = row["symbol"]
            if sym in quotes and quotes[sym].get("price", 0) > 0:
                live = quotes[sym]["price"]
                self.df.at[idx, "market_price"] = live
                mv = live * row["total_qty"]
                self.df.at[idx, "market_value"] = mv
                cv = row.get("cost_value") or row.get("cost_price", 0) * row["total_qty"]
                self.df.at[idx, "cost_value"] = cv
                pnl = mv - cv
                self.df.at[idx, "pnl"] = pnl
                self.df.at[idx, "pnl_pct"] = (pnl / cv * 100) if cv > 0 else 0
                self.df.at[idx, "live_change_pct"] = quotes[sym].get("pct_change", 0)

        total_mv = self.df["market_value"].sum()
        if total_mv > 0:
            self.df["weight_pct"] = (self.df["market_value"] / total_mv * 100).round(2)

        self._recompute_totals()
        return self

    def add_risk_labels(self) -> "Portfolio":
        if self.df.empty:
            return self
        labels, colors = [], []
        for _, row in self.df.iterrows():
            lbl, clr = classify_risk(row.to_dict())
            labels.append(lbl)
            colors.append(clr)
        self.df["risk_label"] = labels
        self.df["risk_color"]  = colors
        return self

    def _recompute_totals(self):
        if self.df.empty:
            return
        self.total_cost    = self.df.get("cost_value",   pd.Series([0])).sum()
        self.total_market  = self.df.get("market_value", pd.Series([0])).sum()
        self.total_pnl     = self.total_market - self.total_cost
        self.total_pnl_pct = (self.total_pnl / self.total_cost * 100) if self.total_cost > 0 else 0

    def get_position(self, symbol: str) -> Optional[dict]:
        if self.df.empty:
            return None
        rows = self.df[self.df["symbol"] == symbol]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def tradeable_symbols(self) -> list:
        if self.df.empty:
            return []
        if "tradeable_qty" not in self.df.columns:
            return list(self.df["symbol"])
        return list(self.df[self.df["tradeable_qty"] > 0]["symbol"])

    def save_snapshot(self):
        if self.df.empty:
            return
        fname = TRADE_LOG_DIR / f"snapshot_{dt.date.today().isoformat()}.json"
        self.df.to_json(fname, orient="records", force_ascii=False, indent=2)

    def to_display_df(self) -> pd.DataFrame:
        if self.df.empty:
            return pd.DataFrame()
        cols = ["symbol", "total_qty", "tradeable_qty", "cost_price", "market_price",
                "pnl", "pnl_pct", "weight_pct", "risk_label"]
        avail = [c for c in cols if c in self.df.columns]
        df = self.df[avail].copy()
        df = df.rename(columns={
            "symbol": "Mã CP", "total_qty": "KL tổng",
            "tradeable_qty": "KL GD được", "cost_price": "Giá vốn",
            "market_price": "Giá TT", "pnl": "Lãi/Lỗ (đ)",
            "pnl_pct": "% Lãi/Lỗ", "weight_pct": "% DM",
            "risk_label": "Đánh giá rủi ro",
        })
        return df


# ─── PORTFOLIO DIR SCANNER ───────────────────────────────────────────────────

def find_latest_portfolio_file() -> Optional[Path]:
    files = list(PORTFOLIO_DIR.glob("*.xlsx")) + list(PORTFOLIO_DIR.glob("*.xls"))
    return Path(max(files, key=lambda f: f.stat().st_mtime)) if files else None


def list_portfolio_files() -> list:
    files = list(PORTFOLIO_DIR.glob("*.xlsx")) + list(PORTFOLIO_DIR.glob("*.xls"))
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


# ─── T+2 HELPER ──────────────────────────────────────────────────────────────

def settlement_date(trade_date: dt.date) -> dt.date:
    d, count = trade_date, 0
    while count < SETTLEMENT_DAYS:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in VN_PUBLIC_HOLIDAYS:
            count += 1
    return d


def is_settled(trade_date: dt.date, as_of: Optional[dt.date] = None) -> bool:
    return (as_of or dt.date.today()) >= settlement_date(trade_date)
