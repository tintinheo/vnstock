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
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd

from config import BUY_TOTAL, SELL_TOTAL, INITIAL_CAPITAL, LOT_SIZE
from core.market_calendar import trading_sessions_between

logger = logging.getLogger("TradingOS.tracker")

from core.audit import log_event, ACTION_OPEN, ACTION_CLOSE

PORTFOLIO_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "portfolio.json"
)


# Break-even stop thresholds per timeframe (VN-02 fix).
# For short holds (1W = 5 sessions) raising the stop requires only +7% gain
# (1 HOSE trần session) rather than +15%, making the mechanism actually useful.
# Longer holds retain progressively higher thresholds to avoid premature stop.
# _BREAKEVEN_THRESHOLD_DEFAULT preserves existing behaviour for positions whose
# timeframe is unknown or not in the dict (e.g. manual positions).
_BREAKEVEN_THRESHOLD: dict[str, float] = {
    "1W": 0.07,
    "2W": 0.08,
    "1M": 0.10,
    "3M": 0.12,
    "5M": 0.15,
}
_BREAKEVEN_THRESHOLD_DEFAULT = 0.15


def _coerce_iso_date(value: str | date | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _trading_sessions_between(entry_date: str, exit_date: str | date | None = None) -> int:
    return trading_sessions_between(entry_date, exit_date)


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

    def held_sessions(self, as_of_date: str | date | None = None) -> int:
        return _trading_sessions_between(self.entry_date, as_of_date)

    def settlement_ready(self, as_of_date: str | date | None = None, min_sessions: int = 2) -> bool:
        return self.held_sessions(as_of_date) >= min_sessions

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
        """Giá trị danh mục theo giá vào (không phản ánh lãi/lỗ chưa thực hiện).
        Dùng market_value() khi cần giá trị mark-to-market.
        """
        return self.cash + sum(p.current_value for p in self.open_positions)

    def market_value(self, price_dict: dict) -> float:
        """Mark-to-market: tổng giá trị danh mục theo giá thị trường hiện tại.

        Parameters
        ----------
        price_dict : dict[ticker -> current_price (float)]
            Nếu ticker không có trong dict, fallback về entry_price.
        """
        mtm = sum(
            price_dict.get(p.ticker, p.entry_price) * p.n_shares
            for p in self.open_positions
        )
        return self.cash + mtm

    def unrealized_pnl(self, price_dict: dict) -> float:
        """Tổng lãi/lỗ chưa thực hiện (VND) trên tất cả vị thế đang mở.

        Parameters
        ----------
        price_dict : dict[ticker -> current_price (float)]
        """
        return sum(
            (price_dict.get(p.ticker, p.entry_price) - p.entry_price) * p.n_shares
            for p in self.open_positions
        )

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
        log_event(
            ACTION_OPEN,
            ticker=pos.ticker,
            timeframe=pos.timeframe,
            detail={
                "entry_price": pos.entry_price,
                "n_shares":    pos.n_shares,
                "cost_vnd":    pos.cost_vnd,
                "stop_loss":   pos.stop_loss,
                "take_profit": pos.take_profit,
                "entry_date":  pos.entry_date,
            },
        )
        return True

    def close_position(
        self,
        ticker: str,
        exit_price: float,
        exit_date: str | None = None,
        reason: str = "signal",
        timeframe: str | None = None,
        entry_date: str | None = None,
    ) -> Optional[Position]:
        """Close the first matching open position.

        When multiple open legs share the same ticker, callers can disambiguate
        by timeframe and/or entry_date so the intended position is closed.
        """
        effective_exit_date = exit_date or date.today().isoformat()
        for pos in self.positions:
            if pos.ticker != ticker or pos.status != "open":
                continue
            if timeframe is not None and pos.timeframe != timeframe:
                continue
            if entry_date is not None and pos.entry_date != entry_date:
                continue
            pos.sessions_held = pos.held_sessions(effective_exit_date)
            if not pos.settlement_ready(effective_exit_date):
                logger.info(
                    "Close blocked for %s @ %.0f: held %d sessions, requires T+2",
                    ticker, exit_price, pos.sessions_held,
                )
                return None
            pos.close(exit_price, effective_exit_date, reason)
            self.trades.append(pos)
            self.positions = [p for p in self.positions if p is not pos]
            # Realise cash
            proceeds = exit_price * pos.n_shares * (1 - SELL_TOTAL)
            self.capital = self.capital - pos.cost_vnd + proceeds
            logger.info(
                "Closed %s @ %.0f | PnL: %.2f%%",
                ticker, exit_price, (pos.pnl_pct or 0) * 100,
            )
            log_event(
                ACTION_CLOSE,
                ticker=ticker,
                timeframe=pos.timeframe,
                detail={
                    "entry_price": pos.entry_price,
                    "exit_price":  exit_price,
                    "n_shares":    pos.n_shares,
                    "pnl_pct":     round((pos.pnl_pct or 0) * 100, 2),
                    "pnl_vnd":     pos.pnl_vnd,
                    "reason":      reason,
                    "entry_date":  pos.entry_date,
                    "exit_date":   pos.exit_date,
                    "sessions":    pos.sessions_held,
                },
                result="ok",
            )
            return pos
        return None

    def update_stops(self, price_dict: dict | None = None) -> list:
        """Break-even trailing stop: nâng stop lên giá vào khi lãi ≥ 15%.

        Phù hợp thị trường VN: 15% ≈ 2× biên độ trần HOSE — đây là mốc
        trader VN thường dùng để bảo toàn vốn sau đợt tăng mạnh.

        Parameters
        ----------
        price_dict : dict[ticker -> current_price] | None
            Nếu None hoặc ticker không có, bỏ qua vị thế đó.

        Returns
        -------
        list[str] — danh sách ticker đã được nâng stop.
        """
        if not price_dict:
            return []
        updated = []
        for pos in self.open_positions:
            cur = price_dict.get(pos.ticker)
            if cur is None or pos.entry_price <= 0:
                continue
            gain_pct = (cur - pos.entry_price) / pos.entry_price
            # Break-even: nâng stop lên entry_price theo ngưỡng từng timeframe.
            # 1W: +7% (1 phiên trần HOSE); 5M: +15% (giữ nguyên như cũ).
            # Chỉ nâng khi stop hiện tại còn thấp hơn entry (tránh gọi lại)
            threshold = _BREAKEVEN_THRESHOLD.get(
                pos.timeframe, _BREAKEVEN_THRESHOLD_DEFAULT
            )
            if gain_pct >= threshold and pos.stop_loss < pos.entry_price:
                pos.stop_loss = pos.entry_price
                updated.append(pos.ticker)
                logger.info("Break-even stop: %s stop nâng lên %.0f (threshold=%.0f%%)",
                            pos.ticker, pos.entry_price, threshold * 100)
        return updated

    def to_dict(self) -> dict:
        return {
            "capital":    self.capital,
            "positions":  [asdict(p) for p in self.positions],
            "trades":     [asdict(t) for t in self.trades],
            "created_at": self.created_at,
        }

    # ── Persistence ────────────────────────────────────────────
    def save(self, path: str = PORTFOLIO_FILE) -> None:
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"{os.path.basename(path)}.",
            suffix=".tmp",
            dir=directory,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
