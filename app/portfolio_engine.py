#!/usr/bin/env python3
"""
portfolio_engine.py  —  Portfolio Hub: CSV parsing, T+2.5 settlement, P&L
═══════════════════════════════════════════════════════════════════════════
Handles SSI broker export CSV (Saturn/iboard format) with fuzzy column
matching, VN-holiday-aware trading calendar, and T+2 KRX settlement logic.

Usage (standalone smoke test):
    python portfolio_engine.py path/to/holdings.csv
"""

import os
import re
import io
from datetime import date, timedelta, datetime
from typing import Optional

import numpy as np
import pandas as pd

# ─── VN Public Holidays (fixed + approximate recurring) ──────────────────────
_VN_HOLIDAYS_2025_2026 = {
    date(2025, 1, 1),   # Tết Dương lịch
    date(2025, 1, 27),  date(2025, 1, 28),  date(2025, 1, 29),
    date(2025, 1, 30),  date(2025, 1, 31),  # Tết Nguyên Đán 2025
    date(2025, 4, 30),  date(2025, 5, 1),   # 30/4 + 1/5
    date(2025, 9, 1),   date(2025, 9, 2),   # Giỗ Tổ Hùng Vương + Quốc khánh
    date(2026, 1, 1),   # Tết Dương lịch
    date(2026, 1, 26),  date(2026, 1, 27),  date(2026, 1, 28),
    date(2026, 1, 29),  date(2026, 1, 30),  # Tết Nguyên Đán 2026
    date(2026, 4, 7),   # Giỗ Tổ Hùng Vương
    date(2026, 4, 30),  date(2026, 5, 1),
    date(2026, 9, 2),
}


# ─── Column aliases: SSI, DNSE, manual entry ─────────────────────────────────
_COL_ALIASES = {
    "ticker": [
        "mã ck", "mã", "ticker", "symbol", "ck", "stock", "co phieu",
        "mã cổ phiếu", "stock code",
    ],
    "qty": [
        "sl đang có", "sl hiện có", "số lượng", "quantity", "qty", "sl",
        "klcp", "kl", "số lượng hiện tại", "sl khớp", "volume",
    ],
    "avg_cost": [
        "giá vốn bq", "giá vốn", "giá vv (vnđ)", "giá vv", "giá mua tb",
        "average cost", "avg cost", "avg_cost", "giá tb", "vốn bình quân",
        "gia von", "giá bình quân",
    ],
    "trade_date": [
        "ngày gd", "ngày mua", "trade date", "date", "ngày", "gd date",
    ],
    "sector": [
        "ngành", "sector", "ngành/sector", "nganh",
    ],
}


def _fuzzy_match(col_name: str, aliases: list[str]) -> bool:
    """Case-insensitive partial match of a column name against a list of aliases."""
    # Normalize newlines (SSI XLSX uses \n inside column headers)
    c = col_name.strip().lower().replace("\n", " ").replace("  ", " ")
    return any(a in c or c in a for a in aliases)


def detect_portfolio_csv_format(df: pd.DataFrame) -> dict:
    """
    Sniff the column mapping from an uploaded DataFrame.
    Returns {'ticker': col, 'qty': col, 'avg_cost': col, 'trade_date': col|None, 'sector': col|None}
    Raises ValueError if ticker or qty cannot be detected.
    """
    mapping = {}
    for field, aliases in _COL_ALIASES.items():
        for col in df.columns:
            if _fuzzy_match(col, aliases):
                mapping[field] = col
                break
    missing = [f for f in ("ticker", "qty", "avg_cost") if f not in mapping]
    if missing:
        raise ValueError(
            f"Không tìm thấy cột: {missing}. "
            f"Cột hiện có: {list(df.columns)}"
        )
    return mapping


def _detect_xlsx(uploaded_file) -> bool:
    """Return True if the file appears to be an Excel XLSX/XLS file."""
    name = ""
    if isinstance(uploaded_file, (str, os.PathLike)):
        name = str(uploaded_file)
    elif hasattr(uploaded_file, "name"):
        name = uploaded_file.name or ""
    return name.lower().endswith((".xlsx", ".xls"))


def parse_portfolio_csv(uploaded_file) -> pd.DataFrame:
    """
    Parse an SSI/DNSE portfolio CSV or XLSX (file path, bytes, or file-like object).
    Returns a clean DataFrame with columns:
        ticker, qty, avg_cost, trade_date (date | None), sector (str | '')
    Filters out rows with qty <= 0 or avg_cost <= 0.

    SSI iBoard XLSX format:
        Row 0: blank / metadata
        Row 1: account info
        Row 2: column headers  ← header=2
        Row 3+: data
    """
    is_xlsx = _detect_xlsx(uploaded_file)

    if is_xlsx:
        # ── XLSX path ────────────────────────────────────────────────────────
        # SSI iBoard exports have 2 header/metadata rows before the real column row
        try:
            df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=2, thousands=",")
        except Exception:
            # Fallback: try first sheet with no skip
            df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=0)
        # Seek back so Streamlit can re-read if needed
        if hasattr(uploaded_file, "seek"):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
    else:
        # ── CSV path ─────────────────────────────────────────────────────────
        if isinstance(uploaded_file, (str, os.PathLike)):
            raw = open(uploaded_file, "rb").read()
        elif hasattr(uploaded_file, "read"):
            raw = uploaded_file.read()
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
        else:
            raw = uploaded_file  # bytes

        # Try UTF-8 then cp1258 (Vietnamese Windows encoding)
        text = ""
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, AttributeError):
                text = raw if isinstance(raw, str) else ""
                break

        try:
            df_raw = pd.read_csv(io.StringIO(text), thousands=",")
        except Exception:
            df_raw = pd.read_csv(io.StringIO(text), thousands=",", sep=";")

    # Rename purely-unnamed columns (common in SSI/DNSE export padding)
    df_raw.columns = [
        c if not str(c).startswith("Unnamed") else f"_col{i}"
        for i, c in enumerate(df_raw.columns)
    ]

    mapping = detect_portfolio_csv_format(df_raw)
    out = pd.DataFrame()
    out["ticker"]     = df_raw[mapping["ticker"]].astype(str).str.strip().str.upper()
    out["qty"]        = pd.to_numeric(df_raw[mapping["qty"]].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    out["avg_cost"]   = pd.to_numeric(df_raw[mapping["avg_cost"]].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    if "trade_date" in mapping:
        out["trade_date"] = pd.to_datetime(df_raw[mapping["trade_date"]], dayfirst=True, errors="coerce").dt.date
    else:
        out["trade_date"] = None

    if "sector" in mapping:
        out["sector"] = df_raw[mapping["sector"]].astype(str).str.strip()
    else:
        out["sector"] = ""

    # Clean
    out = out[out["qty"] > 0]
    out = out[out["avg_cost"] > 0]
    out = out[out["ticker"].str.len() >= 2]
    out = out.reset_index(drop=True)
    return out


# ─── VN Trading Calendar ─────────────────────────────────────────────────────

def is_vn_trading_day(d: date) -> bool:
    """Return True if d is a Vietnam Stock Exchange trading day."""
    if d.weekday() >= 5:   # Saturday=5, Sunday=6
        return False
    if d in _VN_HOLIDAYS_2025_2026:
        return False
    return True


def get_vn_trading_days(start: date, end: date) -> list[date]:
    """Return a sorted list of trading days in [start, end]."""
    days = []
    cur = start
    while cur <= end:
        if is_vn_trading_day(cur):
            days.append(cur)
        cur += timedelta(days=1)
    return days


def calculate_t2_settlement(trade_date: date) -> date:
    """
    Calculate the T+2 settlement date per KRX rules (2 VN trading days forward).
    For KRX the new standard is T+2 (net cash available at end of T+2).
    """
    count = 0
    d = trade_date
    while count < 2:
        d += timedelta(days=1)
        if is_vn_trading_day(d):
            count += 1
    return d


def classify_settlement_status(
    holdings_df: pd.DataFrame,
    today: Optional[date] = None,
) -> pd.DataFrame:
    """
    Add 'settlement_date' and 'status' columns to a holdings DataFrame.
    status values:
        'settled'    — shares fully available
        't2_pending' — trade date = today, settles in 2 trading days
        't1_pending' — settles tomorrow
    """
    if today is None:
        today = date.today()
    df = holdings_df.copy()

    def _status(row):
        td = row.get("trade_date")
        if pd.isna(td) or td is None:
            return date.fromisoformat(str(today - timedelta(days=5))), "settled"
        if isinstance(td, str):
            td = date.fromisoformat(td)
        settle = calculate_t2_settlement(td)
        if today >= settle:
            return settle, "settled"
        remaining = len(get_vn_trading_days(today, settle)) - 1
        if remaining <= 1:
            return settle, "t1_pending"
        return settle, "t2_pending"

    results = df.apply(_status, axis=1)
    df["settlement_date"] = [r[0] for r in results]
    df["status"] = [r[1] for r in results]
    return df


# ─── Performance Attribution ─────────────────────────────────────────────────

# Sector map (VN stock exchange) — partial list of common tickers
_SECTOR_MAP = {
    "HPG": "Thép", "HSG": "Thép", "NKG": "Thép",
    "VCB": "Ngân hàng", "BID": "Ngân hàng", "CTG": "Ngân hàng",
    "MBB": "Ngân hàng", "TCB": "Ngân hàng", "ACB": "Ngân hàng",
    "VHM": "Bất động sản", "NVL": "Bất động sản", "PDR": "Bất động sản",
    "DIG": "Bất động sản", "CII": "Hạ tầng", "TCH": "Bất động sản",
    "VNM": "Tiêu dùng", "MSN": "Tiêu dùng", "SAB": "Tiêu dùng",
    "GEG": "Điện", "REE": "Điện/Hạ tầng", "PC1": "Điện",
    "VIC": "Đa ngành", "VRE": "Bất động sản",
    "FPT": "Công nghệ", "CMG": "Công nghệ",
    "VJC": "Hàng không", "HVN": "Hàng không",
}


def calculate_performance(
    holdings_df: pd.DataFrame,
    current_prices: dict,
) -> pd.DataFrame:
    """
    Enrich holdings with: market_value, unrealized_pnl, pnl_pct,
    portfolio_weight, sector.
    current_prices: {ticker: price} dict from fetch_ssi_realtime or batch fetch.
    """
    df = holdings_df.copy()

    def _cur_price(ticker):
        p = current_prices.get(ticker)
        if isinstance(p, dict):
            return p.get("price") or p.get("close") or 0
        return float(p) if p else 0

    df["current_price"]   = df["ticker"].apply(_cur_price)
    df["price_available"] = df["current_price"] > 0
    # When price is unavailable (SSI fetch failed) use cost_basis as fallback
    # so market_value stays neutral and P&L shows 0 instead of fake −100%.
    df["cost_basis"]      = df["qty"] * df["avg_cost"]
    df["market_value"]    = np.where(
        df["price_available"],
        df["qty"] * df["current_price"],
        df["cost_basis"],   # fallback: hold at cost → 0 P&L
    )
    df["unrealized_pnl"]  = np.where(
        df["price_available"],
        df["market_value"] - df["cost_basis"],
        0.0,
    )
    df["pnl_pct"]         = np.where(
        df["price_available"] & (df["cost_basis"] > 0),
        df["unrealized_pnl"] / df["cost_basis"] * 100,
        0.0,
    )
    total_value = df["market_value"].sum()
    df["portfolio_weight"] = np.where(
        total_value > 0,
        df["market_value"] / total_value * 100,
        0.0,
    )
    # Enrich sector if not already set
    if "sector" not in df.columns or (df["sector"] == "").all():
        df["sector"] = df["ticker"].map(_SECTOR_MAP).fillna("Khác")
    else:
        df["sector"] = df.apply(
            lambda r: _SECTOR_MAP.get(r["ticker"], r.get("sector") or "Khác"),
            axis=1,
        )
    return df


def build_portfolio_summary(holdings_df: pd.DataFrame) -> dict:
    """
    Aggregate portfolio-level metrics and sector attribution.
    Returns dict with: total_value, total_cost, total_pnl, total_pnl_pct,
    sector_attribution {sector: pct_weight}, top_gainer, top_loser.
    """
    df = holdings_df
    total_value = df["market_value"].sum()
    total_cost  = df["cost_basis"].sum()
    total_pnl   = df["unrealized_pnl"].sum()
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    sector_attr = (
        df.groupby("sector")["market_value"].sum()
        / total_value * 100
        if total_value > 0
        else pd.Series(dtype=float)
    ).sort_values(ascending=False).to_dict()

    top_gainer = df.loc[df["pnl_pct"].idxmax()] if not df.empty and df["pnl_pct"].max() > 0 else None
    top_loser  = df.loc[df["pnl_pct"].idxmin()] if not df.empty and df["pnl_pct"].min() < 0 else None

    return {
        "total_value":     total_value,
        "total_cost":      total_cost,
        "total_pnl":       total_pnl,
        "total_pnl_pct":   total_pnl_pct,
        "sector_attribution": sector_attr,
        "top_gainer":      top_gainer["ticker"] if top_gainer is not None else "",
        "top_gainer_pct":  float(top_gainer["pnl_pct"]) if top_gainer is not None else 0.0,
        "top_loser":       top_loser["ticker"] if top_loser is not None else "",
        "top_loser_pct":   float(top_loser["pnl_pct"]) if top_loser is not None else 0.0,
        "position_count":  len(df),
    }


# ─── Smoke test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Quick T+2 test
        today = date(2026, 3, 16)  # Monday
        settle = calculate_t2_settlement(today)
        print(f"T+2 from {today} → {settle}")

        # Quick mock portfolio
        mock = pd.DataFrame({
            "ticker":   ["HPG", "VNM", "TCH"],
            "qty":      [1000, 500, 2000],
            "avg_cost": [20000, 60000, 15000],
            "trade_date": [date(2026, 3, 14), date(2026, 3, 12), date(2026, 3, 10)],
        })
        mock = classify_settlement_status(mock, today=today)
        df   = calculate_performance(mock, {"HPG": 21000, "VNM": 58000, "TCH": 16000})
        summary = build_portfolio_summary(df)
        print(df[["ticker", "qty", "avg_cost", "current_price", "pnl_pct", "status"]].to_string())
        print("\nSummary:", summary)
    else:
        df = parse_portfolio_csv(sys.argv[1])
        print(df.to_string())
