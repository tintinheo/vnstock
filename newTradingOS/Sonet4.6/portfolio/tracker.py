"""
portfolio/tracker.py — NewTradingOS v14.0
In-session portfolio state: open positions, closed trades, P&L.
Persisted as JSON in data/portfolio.json.
T+2 settlement aware.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd

from config import BUY_TOTAL, SELL_TOTAL, INITIAL_CAPITAL, LOT_SIZE

logger = logging.getLogger("TradingOS.tracker")

PORTFOLIO_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "portfolio.json"
)


@dataclass
class Position:
    ticker:        str
    timeframe:     str
    entry_date:    str               # ISO date
    entry_price:   float
    n_shares:      int
    stop_loss:     float
    take_profit:   float
    cost_vnd:      float             # entry_price * n_shares * (1 + BUY_TOTAL)
    status:        str = "open"      # 'open' | 't2_pending' | 'closed'
    exit_date:     Optional[str] = None
    exit_price:    Optional[float] = None
    pnl_pct:       Optional[float] = None
    pnl_vnd:       Optional[float] = None
    exit_reason:   Optional[str] = None
    sessions_held: int = 0

    @property
    def current_value(self) -> float:
        return self.entry_price * self.n_shares

    def close(
        self,
        exit_price: float,
        exit_date: str,
        reason: str = "signal",
    ) -> None:
        proceeds       = exit_price * self.n_shares * (1 - SELL_TOTAL)
        self.pnl_vnd   = round(proceeds - self.cost_vnd, 0)
        self.pnl_pct   = round((proceeds / self.cost_vnd) - 1, 6)
        self.exit_price  = exit_price
        self.exit_date   = exit_date
        self.exit_reason = reason
        self.status      = "closed"


@dataclass
class Portfolio:
    capital:    float = INITIAL_CAPITAL
    positions:  list  = field(default_factory=list)   # list[Position]
    trades:     list  = field(default_factory=list)   # list[Position] (closed)
    created_at: str   = field(default_factory=lambda: datetime.now().isoformat())

    # ── Summary ────────────────────────────────────────────────
    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.status == "open"]

    @property
    def cash(self) -> float:
        invested = sum(p.cost_vnd for p in self.open_positions)
        return max(0.0, self.capital - invested)

    @property
    def total_value(self) -> float:
        return self.cash + sum(p.current_value for p in self.open_positions)

    @property
    def realised_pnl(self) -> float:
        return sum(t.pnl_vnd or 0 for t in self.trades)

    # ── Operations ─────────────────────────────────────────────
    def open_position(self, pos: Position) -> bool:
        """
        Add a new position.
        Returns False if insufficient cash.
        """
        if pos.cost_vnd > self.cash:
            logger.warning(
                "Insufficient cash for %s (need %.0f, have %.0f)",
                pos.ticker, pos.cost_vnd, self.cash
            )
            return False
        self.positions.append(pos)
        logger.info("Opened %s x%d @ %.0f (%.0f VND)",
                    pos.ticker, pos.n_shares, pos.entry_price, pos.cost_vnd)
        return True

    def close_position(
        self,
        ticker: str,
        exit_price: float,
        exit_date: str | None = None,
        reason: str = "signal",
    ) -> Optional[Position]:
        """Close the first matching open position."""
        for pos in self.positions:
            if pos.ticker == ticker and pos.status == "open":
                pos.close(exit_price, exit_date or date.today().isoformat(), reason)
                self.trades.append(pos)
                self.positions = [p for p in self.positions if p is not pos]
                # Realise cash
                proceeds = exit_price * pos.n_shares * (1 - SELL_TOTAL)
                self.capital = self.capital - pos.cost_vnd + proceeds
                logger.info(
                    "Closed %s @ %.0f | PnL: %.2f%%",
                    ticker, exit_price, (pos.pnl_pct or 0) * 100,
                )
                return pos
        return None

    def update_stops(self) -> None:
        """Trailing stop: raise stop_loss to break-even after 20% gain."""
        for pos in self.open_positions:
            if pos.entry_price > 0:
                pass  # Extend here for trailing stop logic

    def to_dict(self) -> dict:
        return {
            "capital":    self.capital,
            "positions":  [asdict(p) for p in self.positions],
            "trades":     [asdict(t) for t in self.trades],
            "created_at": self.created_at,
        }

    # ── Persistence ────────────────────────────────────────────
    def save(self, path: str = PORTFOLIO_FILE) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2, default=str)

    @classmethod
    def load(cls, path: str = PORTFOLIO_FILE) -> "Portfolio":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            pf = cls(
                capital=data.get("capital", INITIAL_CAPITAL),
                created_at=data.get("created_at", ""),
            )
            for p in data.get("positions", []):
                pf.positions.append(Position(**p))
            for t in data.get("trades", []):
                pf.trades.append(Position(**t))
            return pf
        except Exception as exc:
            logger.warning("Portfolio load failed: %s — starting fresh.", exc)
            return cls()

    # ── DataFrame views ────────────────────────────────────────
    def positions_df(self) -> pd.DataFrame:
        rows = []
        for p in self.open_positions:
            rows.append({
                "Mã":       p.ticker,
                "TF":       p.timeframe,
                "Ngày vào": p.entry_date,
                "Giá vào":  p.entry_price,
                "SL CP":    p.n_shares,
                "Stop":     p.stop_loss,
                "Target":   p.take_profit,
                "Chi phí":  p.cost_vnd,
            })
        return pd.DataFrame(rows)

    def trades_df(self) -> pd.DataFrame:
        rows = []
        for t in self.trades:
            rows.append({
                "Mã":       t.ticker,
                "TF":       t.timeframe,
                "Vào":      t.entry_date,
                "Ra":       t.exit_date,
                "Giá vào":  t.entry_price,
                "Giá ra":   t.exit_price,
                "SL CP":    t.n_shares,
                "PnL %":    round((t.pnl_pct or 0) * 100, 2),
                "PnL VND":  t.pnl_vnd,
                "Lý do":    t.exit_reason,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Ra", ascending=False)
        return df
