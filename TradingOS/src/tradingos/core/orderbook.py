"""Order Book Imbalance (OBI) engine.

Computes bid/ask imbalance from a FiinQuant BidAsk snapshot DataFrame.
"""
from __future__ import annotations

import pandas as pd


def compute_order_book_imbalance(bidask_df: pd.DataFrame) -> dict:
    """Compute Order Book Imbalance (OBI) from a bid/ask snapshot.

    OBI = (total_bid_vol − total_ask_vol) / (total_bid_vol + total_ask_vol) × 100

    Args:
        bidask_df: DataFrame from FiinQuant ``BidAsk`` snapshot.
                   Expected to contain bid/ask volume columns (flexible naming).

    Returns:
        Dict with keys:
          obi_pct       — signed imbalance percentage
          obi_signal    — "BUYING_PRESSURE" | "SELLING_PRESSURE" | "BALANCED"
          spread_pct    — (best_ask − best_bid) / best_ask × 100
          bid_ask_depth — {"total_bid": float, "total_ask": float}
    """
    _defaults: dict = {
        "obi_pct": 0.0,
        "obi_signal": "BALANCED",
        "spread_pct": 0.0,
        "bid_ask_depth": {"total_bid": 0.0, "total_ask": 0.0},
    }

    if bidask_df is None or bidask_df.empty:
        return _defaults

    df = bidask_df.copy()
    df.columns = [c.lower() for c in df.columns]

    # ── Discover bid/ask volume columns (flexible naming) ────────────────────
    def _find_col(keywords: list[str]) -> str | None:
        for c in df.columns:
            if all(k in c for k in keywords):
                return c
        return None

    bid_col = _find_col(["bid", "vol"]) or _find_col(["bvol"]) or next(
        (c for c in df.columns if c.startswith("b") and "vol" in c), None
    )
    ask_col = _find_col(["ask", "vol"]) or _find_col(["avol"]) or next(
        (c for c in df.columns if c.startswith("a") and "vol" in c), None
    )

    if bid_col is None or ask_col is None:
        return _defaults

    total_bid = float(df[bid_col].fillna(0).sum())
    total_ask = float(df[ask_col].fillna(0).sum())
    total = total_bid + total_ask
    if total <= 0:
        return _defaults

    obi_pct = round((total_bid - total_ask) / total * 100, 2)

    if obi_pct > 20:
        obi_signal = "BUYING_PRESSURE"
    elif obi_pct < -20:
        obi_signal = "SELLING_PRESSURE"
    else:
        obi_signal = "BALANCED"

    # ── Spread (best ask vs best bid) ────────────────────────────────────────
    spread_pct = 0.0
    bid_price_col = _find_col(["bid", "price"])
    ask_price_col = _find_col(["ask", "price"])
    if bid_price_col and ask_price_col and not df[bid_price_col].empty:
        best_bid = float(df[bid_price_col].max())
        best_ask = float(df[ask_price_col].min())
        if best_ask > 0:
            spread_pct = round((best_ask - best_bid) / best_ask * 100, 4)

    return {
        "obi_pct": obi_pct,
        "obi_signal": obi_signal,
        "spread_pct": spread_pct,
        "bid_ask_depth": {"total_bid": total_bid, "total_ask": total_ask},
    }
