"""
Market intelligence — sector classification, breadth, foreign flow.
All data is based on VN30 constituents (Q1 2026 composition).
"""
import logging
import pandas as pd

_log = logging.getLogger("market_intel")

# ─── VN30 SECTOR MAP ─────────────────────────────────────────────────────────
# Source: HOSE official sector classification (Q1 2026)
VN30_SECTORS: dict[str, str] = {
    # Ngân hàng (Banking)
    "VCB":  "Ngân hàng",
    "BID":  "Ngân hàng",
    "CTG":  "Ngân hàng",
    "TCB":  "Ngân hàng",
    "MBB":  "Ngân hàng",
    "ACB":  "Ngân hàng",
    "VPB":  "Ngân hàng",
    "STB":  "Ngân hàng",
    "HDB":  "Ngân hàng",
    "LPB":  "Ngân hàng",
    # Bất động sản (Real Estate)
    "VHM":  "Bất động sản",
    "NVL":  "Bất động sản",
    "PDR":  "Bất động sản",
    "VRE":  "Bất động sản",
    "BCM":  "Bất động sản",
    # Thép (Steel & Materials)
    "HPG":  "Thép",
    "NKG":  "Thép",
    "HSG":  "Thép",
    # Năng lượng (Energy)
    "GAS":  "Năng lượng",
    "PLX":  "Năng lượng",
    "POW":  "Năng lượng",
    "PVD":  "Năng lượng",
    # Tập đoàn đa ngành (Conglomerate)
    "VIC":  "Tập đoàn",
    # Công nghệ (Technology)
    "FPT":  "Công nghệ",
    "CMG":  "Công nghệ",
    # Tiêu dùng / Bán lẻ (Consumer / Retail)
    "MSN":  "Tiêu dùng",
    "MWG":  "Bán lẻ",
    "PNJ":  "Bán lẻ",
    # Bia & Ẩm thực (Beverage)
    "SAB":  "Bia & Ẩm thực",
}

# All unique sectors for ordering
SECTOR_ORDER = [
    "Ngân hàng", "Bất động sản", "Thép", "Năng lượng",
    "Tập đoàn", "Công nghệ", "Tiêu dùng", "Bán lẻ", "Bia & Ẩm thực",
]


# ─── SECTOR RETURNS ──────────────────────────────────────────────────────────

def compute_sector_returns(quotes: dict) -> dict:
    """
    Compute equal-weighted average return per sector from a live quotes batch.

    Parameters
    ----------
    quotes : {symbol: {"price": float, "pct_change": float, ...}}

    Returns
    -------
    {sector_name: avg_pct_change}   — only sectors with ≥1 observation
    """
    sums:   dict = {}
    counts: dict = {}

    for sym, q in quotes.items():
        sector = VN30_SECTORS.get(sym.upper())
        if sector is None:
            continue
        chg = float(q.get("pct_change", 0) or 0)
        sums[sector]   = sums.get(sector,   0.0) + chg
        counts[sector] = counts.get(sector, 0)   + 1

    return {
        sector: round(sums[sector] / counts[sector], 3)
        for sector in sums
        if counts.get(sector, 0) > 0
    }


# ─── MARKET BREADTH ──────────────────────────────────────────────────────────

def compute_market_breadth(symbols: list, quotes: dict) -> dict:
    """
    Compute advance / decline statistics across a list of symbols.

    Parameters
    ----------
    symbols : list of symbol strings to include in breadth
    quotes  : {symbol: quote_dict with "pct_change" key}

    Returns
    -------
    dict with keys: advance, decline, unchanged, total, ad_ratio, breadth_pct
    """
    advance   = 0
    decline   = 0
    unchanged = 0

    for sym in symbols:
        chg = float((quotes.get(sym) or {}).get("pct_change", 0) or 0)
        if chg > 0.05:
            advance += 1
        elif chg < -0.05:
            decline += 1
        else:
            unchanged += 1

    total    = max(1, advance + decline + unchanged)
    ad_ratio = round(advance / decline, 2) if decline > 0 else float("inf")

    return {
        "advance":     advance,
        "decline":     decline,
        "unchanged":   unchanged,
        "total":       total,
        "ad_ratio":    ad_ratio,
        "breadth_pct": round(advance / total * 100, 1),
    }
