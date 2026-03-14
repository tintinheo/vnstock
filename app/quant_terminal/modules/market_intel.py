"""
Market intelligence — VN30 sector mapping, sector returns, market breadth.
"""
import logging
from typing import Optional

import pandas as pd

_log = logging.getLogger("market_intel")

# ── VN30 SECTOR MAPPING ───────────────────────────────────────────────────────
# Key = stock symbol, Value = sector name
VN30_SECTORS: dict = {
    # Ngân hàng
    "ACB":  "Ngân hàng",
    "BID":  "Ngân hàng",
    "CTG":  "Ngân hàng",
    "HDB":  "Ngân hàng",
    "MBB":  "Ngân hàng",
    "STB":  "Ngân hàng",
    "TCB":  "Ngân hàng",
    "TPB":  "Ngân hàng",
    "VCB":  "Ngân hàng",
    "VIB":  "Ngân hàng",
    "VPB":  "Ngân hàng",
    "SSB":  "Ngân hàng",
    # Bất động sản
    "BCM":  "Bất động sản",
    "NVL":  "Bất động sản",
    "VHM":  "Bất động sản",
    "VIC":  "Bất động sản",
    "VRE":  "Bất động sản",
    "DIG":  "Bất động sản",
    "SCR":  "Bất động sản",
    "TCH":  "Bất động sản",   # industrial park (not Logistics)
    # Chứng khoán & bảo hiểm
    "BVH":  "Bảo hiểm & Chứng khoán",
    "SSI":  "Bảo hiểm & Chứng khoán",
    "VCI":  "Bảo hiểm & Chứng khoán",
    # Công nghệ
    "FPT":  "Công nghệ",
    # Công nghiệp & Vật liệu
    "GVR":  "Công nghiệp",
    "HPG":  "Vật liệu",
    "VGC":  "Vật liệu xây dựng",   # building materials, not Xây dựng (H-08)
    "CII":  "Xây dựng & Hạ tầng",  # construction/infrastructure, not BĐS (H-08)
    # Hàng tiêu dùng & Bán lẻ
    "MSN":  "Hàng tiêu dùng",
    "MWG":  "Bán lẻ",
    "SAB":  "Hàng tiêu dùng",
    "VNM":  "Hàng tiêu dùng",
    # Hàng không & Du lịch
    "VJC":  "Hàng không",
    "HVN":  "Hàng không",           # VN Airlines — FOL = 0%
    # Năng lượng
    "GAS":  "Năng lượng",
    "PLX":  "Năng lượng",
    "POW":  "Điện",
    "VSH":  "Điện",
    "PGC":  "Dầu khí",              # gas distribution (H-08)
    "PVD":  "Dầu khí",
    # Dược
    "DHG":  "Dược",
    # Khác
    "DTA":  "Khác",
    "ABS":  "Bất động sản",
    "BKG":  "Bất động sản",
}


# ── SECTOR OVERRIDES (manual corrections for misclassified tickers) ───────────
# Takes priority over VN30_SECTORS lookup (H-08 fix).
SECTOR_OVERRIDE: dict = {
    "PGC":  "Dầu khí",
    "POW":  "Điện",
    "VSH":  "Điện",
    "CII":  "Xây dựng & Hạ tầng",
    "SCR":  "Bất động sản",
    "TCH":  "Bất động sản",
    "VGC":  "Vật liệu xây dựng",
    "SSB":  "Ngân hàng",
    "HVN":  "Hàng không",
}


def get_sector(ticker: str) -> str:
    """Get sector for ticker, with manual overrides taking priority."""
    t = ticker.upper()
    return SECTOR_OVERRIDE.get(t) or VN30_SECTORS.get(t, "Khác")


# ── SECTOR BETA (empirical vs VNINDEX 2018-2025) ─────────────────────────────
# Based on published Vietnamese market research and SSI research data.
# Each sector has separate optimistic and pessimistic betas because bear-market
# panic causes non-linear responses (securities sector β > 2.5 during 2022 crash).
SECTOR_BETA: dict = {
    "optimistic": {
        "Ngân hàng":              1.20,
        "Bất động sản":           1.50,
        "Bảo hiểm & Chứng khoán": 1.80,
        "Dầu khí":                0.90,
        "Vật liệu":               1.30,
        "Vật liệu xây dựng":      1.10,
        "Xây dựng & Hạ tầng":     1.20,
        "Hàng không":             1.20,
        "Dược":                   0.60,
        "Điện":                   0.70,
        "Năng lượng":             0.85,
        "Công nghệ":              1.10,
        "Hàng tiêu dùng":         0.80,
        "Bán lẻ":                 1.00,
        "Công nghiệp":            1.00,
        "Khác":                   1.00,
    },
    "pessimistic": {
        # Bear-market betas are higher due to panic/liquidity withdrawal
        "Ngân hàng":              1.25,
        "Bất động sản":           1.70,
        "Bảo hiểm & Chứng khoán": 2.20,  # securities sector crashes harder
        "Dầu khí":                0.95,   # not 0.70 (C-03 correction)
        "Vật liệu":               1.40,
        "Vật liệu xây dựng":      1.25,
        "Xây dựng & Hạ tầng":     1.40,
        "Hàng không":             1.80,   # HVN/VJC crash > 50% in 2020/2022
        "Dược":                   0.50,   # defensive
        "Điện":                   0.60,   # defensive
        "Năng lượng":             1.00,
        "Công nghệ":              1.20,
        "Hàng tiêu dùng":         0.75,
        "Bán lẻ":                 1.10,
        "Công nghiệp":            1.15,
        "Khác":                   1.10,
    },
}

SECTOR_BETA_DISCLAIMER_VI = (
    "⚠️ Beta ngành là ước tính thực nghiệm từ dữ liệu HOSE 2018–2025, "
    "không phải tham số cố định. Chúng thay đổi theo chu kỳ thị trường "
    "và thanh khoản. Không dùng để ra quyết định đầu tư độc lập."
)


# ── FOREIGN OWNERSHIP LIMITS ─────────────────────────────────────────────────
# Approximate FOL caps as of 2026 — requires periodic manual update
KNOWN_FOL_RESTRICTIONS: dict = {
    "HVN":  {"cap_pct": 0.0,  "reason": "DNNN — khối ngoại không được mua"},
    "VCB":  {"cap_pct": 6.5,  "reason": "NHNN sở hữu trên 90% — room ngoại rất hẹp"},
    "BID":  {"cap_pct": 5.0,  "reason": "NH quốc doanh — room ngoại hạn chế"},
    "CTG":  {"cap_pct": 5.0,  "reason": "NH quốc doanh — room ngoại hạn chế"},
    "VJC":  {"cap_pct": 49.0, "reason": "Ngành hàng không — tỷ lệ ngoại tối đa 49%"},
    "FPT":  {"cap_pct": 49.0, "reason": "Room ngoại thường ở mức cao"},
    "VNM":  {"cap_pct": 49.0, "reason": "Ngoại thường gần đầy room"},
}


def get_fol_status(ticker: str, foreign_pct: float = 0.0) -> dict:
    """Return FOL status for a ticker. (H-04 fix)"""
    t = ticker.upper()
    info = KNOWN_FOL_RESTRICTIONS.get(t)
    if not info:
        return {"has_restriction": False, "near_cap": False, "warning": ""}
    cap = info["cap_pct"]
    room = max(0.0, cap - foreign_pct)
    near_cap = room < 3.0 or (cap > 0 and foreign_pct / cap > 0.90 and cap > 0)
    warning = ""
    if cap == 0.0:
        warning = f"⛔ {t}: {info['reason']} — Khối ngoại không thể giao dịch."
    elif near_cap:
        warning = (
            f"⚠️ Room ngoại {t} gần hết ({room:.1f}% còn lại). "
            f"Tín hiệu tích lũy chỉ phản ánh dòng tiền nội. "
            f"Khối ngoại không thể mua thêm."
        )
    return {
        "has_restriction": True,
        "cap_pct":         cap,
        "room_pct":        room,
        "near_cap":        near_cap,
        "warning":         warning,
        "reason":          info["reason"],
    }


# ── SECTOR RETURNS ────────────────────────────────────────────────────────────

def compute_sector_returns(quotes_batch: dict) -> dict:
    """
    Compute average intraday return (%) per sector from a batch of quote dicts.
    quotes_batch: {symbol: quote_dict}  (quote_dict has 'pct_change' field)
    Returns {sector_name: avg_pct_change}.
    """
    if not quotes_batch:
        return {}

    from collections import defaultdict
    sector_returns = defaultdict(list)

    for sym, q in quotes_batch.items():
        sector = VN30_SECTORS.get(sym.upper())
        if not sector:
            continue
        pct = q.get("pct_change", None)
        if pct is not None:
            try:
                sector_returns[sector].append(float(pct))
            except (TypeError, ValueError):
                pass

    result = {}
    for sector, returns in sector_returns.items():
        if returns:
            result[sector] = round(sum(returns) / len(returns), 3)

    return result


# ── MARKET BREADTH ────────────────────────────────────────────────────────────

def compute_market_breadth(symbols: list, quotes_batch: dict) -> dict:
    """
    Compute advance/decline breadth from a batch of quotes.
    symbols: list of stock codes
    quotes_batch: {symbol: quote_dict}
    Returns {advance, decline, unchanged, ad_ratio, breadth_pct}.
    """
    advance   = 0
    decline   = 0
    unchanged = 0

    for sym in symbols:
        q   = quotes_batch.get(sym.upper()) or quotes_batch.get(sym)
        if not q:
            continue
        pct = q.get("pct_change", 0) or 0
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            pct = 0.0

        if pct > 0.05:
            advance += 1
        elif pct < -0.05:
            decline += 1
        else:
            unchanged += 1

    total      = advance + decline + unchanged
    ad_ratio   = (advance / decline) if decline > 0 else float("inf")
    breadth_pct= (advance / total * 100) if total > 0 else 0.0

    return {
        "advance":     advance,
        "decline":     decline,
        "unchanged":   unchanged,
        "ad_ratio":    round(ad_ratio, 2) if ad_ratio != float("inf") else float("inf"),
        "breadth_pct": round(breadth_pct, 1),
    }
