"""
Portfolio — loads SSI iBoard Excel exports and manages position data.
All prices stored in thousands-VND internally.
"""
import logging
import datetime as dt
import json
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

_log = logging.getLogger("portfolio")


# ── Column name mappings (SSI iBoard Excel header variants) ──────────────────
_COL_SYMBOL   = ["mã ck", "mã", "tên mã", "ck", "stock", "symbol"]
_COL_TOT_QTY  = ["tổng kl", "số lượng sở hữu", "kl nắm giữ", "tổng số lượng", "total qty", "số lượng"]
_COL_TRADE_QTY= ["kl được bán", "kl gd được", "số lượng giao dịch được", "có thể bán",
                 "kl có thể bán", "tradeable", "t+2"]
_COL_COST     = ["giá vốn", "giá tb mua", "giá trung bình mua", "giá mua tb",
                 "giá trung bình", "cost price", "giá tb"]
_COL_MARKET   = ["giá tt", "giá thị trường", "giá hiện tại", "giá khớp", "market price"]
_COL_VALUE    = ["giá trị tt", "giá trị thị trường", "market value", "gttt"]
_COL_PNL      = ["lãi/lỗ", "lãi lỗ", "lãi / lỗ", "+/-", "p&l", "pnl"]
_COL_PNL_PCT  = ["%lãi/lỗ", "% lãi/lỗ", "%l/l", "% l/l", "% lãi lỗ", "tỷ lệ l/l"]
_COL_WEIGHT   = ["tỷ trọng", "% tt", "tỷ trọng %", "% danh mục", "weight"]


def _match_col(df_cols: list, candidates: list) -> Optional[str]:
    """Find the first DataFrame column that matches any candidate name (case-insensitive)."""
    normalized = {c.lower().strip(): c for c in df_cols}
    for cand in candidates:
        if cand.lower() in normalized:
            return normalized[cand.lower()]
    # Partial match fallback
    for cand in candidates:
        for col_lower, col_orig in normalized.items():
            if cand.lower() in col_lower:
                return col_orig
    return None


def _to_float(val) -> float:
    """Convert a cell value (possibly formatted with commas/%) to float."""
    if val is None or val != val:  # NaN
        return 0.0
    s = str(val).replace(",", "").replace("%", "").replace("đ", "").strip()
    if s in ("", "-", "—"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _classify_risk(pnl_pct: float, weight: float) -> str:
    """Classify position risk based on P&L% and portfolio weight."""
    if pnl_pct < -7 and weight > 8:
        return "Rất cao"
    if pnl_pct < -4 and weight > 5:
        return "Cao"
    if pnl_pct > 10 and weight > 5:
        return "Thấp — chốt lời"
    return "Bình thường"


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_ssi_excel(path: Path) -> pd.DataFrame:
    """
    Parse an SSI iBoard portfolio Excel export.
    Returns a tidy DataFrame with standard column names; prices in thousands-VND.
    """
    # Try to read; skip metadata rows at top (SSI typically adds 1–3 header lines)
    raw = None
    for skip in (0, 1, 2, 3, 4):
        try:
            candidate = pd.read_excel(path, skiprows=skip, dtype=str)
            cols_lower = [str(c).lower().strip() for c in candidate.columns]
            # Detect if we found the data table (must have a symbol-like column)
            if any(any(cand in cl for cand in _COL_SYMBOL) for cl in cols_lower):
                raw = candidate
                break
        except Exception:
            continue

    if raw is None:
        _log.error("parse_ssi_excel: could not detect header row in %s", path)
        return pd.DataFrame()

    raw.columns = [str(c).strip() for c in raw.columns]
    cols = list(raw.columns)

    def gc(candidates):
        return _match_col(cols, candidates)

    c_sym   = gc(_COL_SYMBOL)
    c_tot   = gc(_COL_TOT_QTY)
    c_trade = gc(_COL_TRADE_QTY)
    c_cost  = gc(_COL_COST)
    c_mkt   = gc(_COL_MARKET)
    c_val   = gc(_COL_VALUE)
    c_pnl   = gc(_COL_PNL)
    c_pnlp  = gc(_COL_PNL_PCT)
    c_wt    = gc(_COL_WEIGHT)

    if not c_sym:
        _log.error("parse_ssi_excel: no symbol column found in %s (cols=%s)", path, cols[:10])
        return pd.DataFrame()

    rows = []
    for _, row in raw.iterrows():
        sym = str(row[c_sym]).strip().upper()
        # Skip blank / subtotal rows
        if not sym or sym in ("NAN", "", "MÃ CK", "TOTAL", "TỔNG") or len(sym) > 10:
            continue

        tot_qty   = _to_float(row[c_tot])   if c_tot   else 0.0
        trade_qty = _to_float(row[c_trade]) if c_trade else 0.0
        cost_raw  = _to_float(row[c_cost])  if c_cost  else 0.0
        mkt_raw   = _to_float(row[c_mkt])   if c_mkt   else 0.0
        pnl_raw   = _to_float(row[c_pnl])   if c_pnl   else 0.0
        pnl_pct   = _to_float(row[c_pnlp])  if c_pnlp  else 0.0
        weight    = _to_float(row[c_wt])    if c_wt    else 0.0

        # Normalize prices: SSI exports raw VND (e.g., 26650) → thousands-VND (26.65)
        # Heuristic: if price > 1000, it's raw VND
        if cost_raw > 1000:
            cost_raw /= 1000.0
        if mkt_raw > 1000:
            mkt_raw /= 1000.0
        # PnL: raw VND → thousands-VND
        if abs(pnl_raw) > 1_000_000:
            pnl_raw /= 1000.0
        # %L/L: already a percentage — do NOT divide
        # (previous bug was dividing by 1000 here — fixed)

        rows.append({
            "symbol":       sym,
            "total_qty":    tot_qty,
            "tradeable_qty": trade_qty,
            "cost_price":   cost_raw,
            "market_price": mkt_raw if mkt_raw > 0 else cost_raw,
            "pnl":          pnl_raw,
            "pnl_pct":      pnl_pct,
            "weight_pct":   weight,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df[df["total_qty"] > 0].copy()
    df["pnl"]    = pd.to_numeric(df["pnl"],    errors="coerce").fillna(0)
    df["pnl_pct"]= pd.to_numeric(df["pnl_pct"],errors="coerce").fillna(0)
    return df


# ── Portfolio class ───────────────────────────────────────────────────────────

class Portfolio:
    """Holds parsed portfolio positions with live-price enrichment."""

    def __init__(self):
        self.df            = pd.DataFrame()
        self._source_path  = None

    # ── Load ──────────────────────────────────────────────────────────────────

    def load_from_file(self, path: Path) -> "Portfolio":
        self._source_path = path
        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            self.df = parse_ssi_excel(path)
        else:
            _log.error("Unsupported file format: %s", suffix)
            self.df = pd.DataFrame()

        if not self.df.empty:
            self._recalculate()
        return self

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def total_market(self) -> float:
        """Total market value in thousands-VND."""
        if self.df.empty or "market_price" not in self.df or "total_qty" not in self.df:
            return 0.0
        return float((
            pd.to_numeric(self.df["market_price"], errors="coerce").fillna(0) *
            pd.to_numeric(self.df["total_qty"],    errors="coerce").fillna(0)
        ).sum())

    @property
    def total_pnl(self) -> float:
        """Total P&L in thousands-VND."""
        if self.df.empty or "pnl" not in self.df:
            return 0.0
        return float(pd.to_numeric(self.df["pnl"], errors="coerce").fillna(0).sum())

    @property
    def total_pnl_pct(self) -> float:
        """Portfolio-level P&L %."""
        cost_total = float((
            pd.to_numeric(self.df.get("cost_price", pd.Series()), errors="coerce").fillna(0) *
            pd.to_numeric(self.df.get("total_qty",  pd.Series()), errors="coerce").fillna(0)
        ).sum()) if not self.df.empty else 0.0
        if cost_total <= 0:
            return 0.0
        return self.total_pnl / cost_total * 100

    # ── Methods ───────────────────────────────────────────────────────────────

    def get_position(self, symbol: str) -> Optional[dict]:
        """Return position dict for a symbol, or None."""
        if self.df.empty:
            return None
        mask = self.df["symbol"].str.upper() == symbol.upper()
        if not mask.any():
            return None
        return self.df[mask].iloc[0].to_dict()

    def tradeable_symbols(self) -> list:
        """Return list of symbols with tradeable_qty > 0."""
        if self.df.empty or "tradeable_qty" not in self.df:
            return []
        mask = pd.to_numeric(self.df["tradeable_qty"], errors="coerce").fillna(0) > 0
        return list(self.df[mask]["symbol"].unique())

    def enrich_with_live_prices(self, quotes: dict):
        """Update market_price from live quotes dict {symbol: quote_dict}."""
        if self.df.empty:
            return
        for i, row in self.df.iterrows():
            sym = row["symbol"].upper()
            q   = quotes.get(sym) or {}
            price = float(q.get("price", 0) or 0)
            if price > 0:
                self.df.at[i, "market_price"] = price
        self._recalculate()

    def add_risk_labels(self):
        """Compute and attach risk_label column."""
        if self.df.empty:
            return
        labels = []
        for _, row in self.df.iterrows():
            pnl_pct = float(row.get("pnl_pct", 0) or 0)
            weight  = float(row.get("weight_pct", 0) or 0)
            labels.append(_classify_risk(pnl_pct, weight))
        self.df["risk_label"] = labels

    def save_snapshot(self):
        """Save current df to a JSON snapshot file."""
        from config import TRADE_LOG_DIR
        if self.df.empty:
            return
        ts_str   = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = TRADE_LOG_DIR / f"snapshot_{ts_str}.json"
        records  = self.df.copy()
        records["market_value"] = (
            pd.to_numeric(records.get("market_price", pd.Series()), errors="coerce").fillna(0) *
            pd.to_numeric(records.get("total_qty",    pd.Series()), errors="coerce").fillna(0)
        )
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records.to_dict(orient="records"), f, default=str, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.error("save_snapshot failed: %s", e)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _recalculate(self):
        """Recompute pnl, pnl_pct, weight_pct after any price update."""
        if self.df.empty:
            return
        cost_p  = pd.to_numeric(self.df["cost_price"],   errors="coerce").fillna(0)
        mkt_p   = pd.to_numeric(self.df["market_price"], errors="coerce").fillna(0)
        qty     = pd.to_numeric(self.df["total_qty"],    errors="coerce").fillna(0)

        self.df["pnl"]    = (mkt_p - cost_p) * qty
        self.df["pnl_pct"]= ((mkt_p / cost_p - 1) * 100).where(cost_p > 0, 0)

        total_mkt = (mkt_p * qty).sum()
        if total_mkt > 0:
            self.df["weight_pct"] = (mkt_p * qty) / total_mkt * 100
        else:
            self.df["weight_pct"] = 0.0

        if "risk_label" not in self.df.columns:
            self.df["risk_label"] = "Bình thường"


# ── Utilities ─────────────────────────────────────────────────────────────────

def list_portfolio_files() -> list:
    """Return list of portfolio Excel files in PORTFOLIO_DIR, newest first."""
    from config import PORTFOLIO_DIR
    files = sorted(
        PORTFOLIO_DIR.glob("*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    files += sorted(
        PORTFOLIO_DIR.glob("*.xls"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files
