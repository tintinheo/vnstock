"""Portfolio Service — position tracking + exit advisory (SRS §3.5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from ..data.fetcher import fetch_ohlcv
from ..data.cache import cache
from ..core import compute_indicators
from ..core.t25_engine import t25_exit_check
from ..core.exit_engine import progressive_exit_plan
from ..core.money_flow import detect_whale_distribution, proxy_whale_net_from_daily
from ..core.nlp import generate_exit_advisory_text
from ..core.execution_advisory import advise_exit_window
from ..utils.logging import get_logger

log = get_logger("portfolio_service")


@dataclass
class Position:
    ticker: str
    entry_price: float
    entry_date: str
    shares: int
    sl: float
    tp1: float
    tp2: float
    mode: str = "MODE_A"
    notes: str = ""


class PortfolioService:
    def __init__(self, portfolio_value: float = 300_000_000):
        self.portfolio_value = portfolio_value
        self._positions: dict[str, Position] = {}

    def add_position(self, pos: Position) -> None:
        self._positions[pos.ticker] = pos
        cache.put_audit({
            "event_type": "POSITION_OPEN",
            "ticker": pos.ticker,
            "action": f"ENTRY at {pos.entry_price:.0f}",
            "mfpm_score": 0,
            "sms_raw": 0,
            "confidence": "—",
        })

    def remove_position(self, ticker: str) -> None:
        self._positions.pop(ticker.upper(), None)

    @property
    def positions(self) -> dict[str, Position]:
        return self._positions

    def get_exit_advisories(self) -> list[dict]:
        """Evaluate all held positions for exit signals."""
        advisories = []
        for ticker, pos in self._positions.items():
            try:
                df = fetch_ohlcv(ticker, days=30)
                if df.empty:
                    continue
                df = compute_indicators(df)
                last = df.iloc[-1]
                current_price = float(last["close"])
                rsi_now = float(last.get("RSI14", 50))
                vol_today = float(last["volume"])
                avg_vol = float(df["volume"].tail(20).mean())

                entry_dt = datetime.fromisoformat(pos.entry_date)
                hold_days = (datetime.now() - entry_dt).days

                # Distribution check
                flow_df = proxy_whale_net_from_daily(df)
                dist = detect_whale_distribution(df, flow_df)
                dist_warning = dist.get("level", "NONE")

                # T+2.5 check
                t25 = t25_exit_check(
                    ticker=ticker,
                    entry_price=pos.entry_price,
                    current_price=current_price,
                    entry_date=entry_dt,
                    sl=pos.sl, tp1=pos.tp1, tp2=pos.tp2,
                    rsi_now=rsi_now,
                    volume_today=vol_today,
                    avg_volume=avg_vol,
                    distribution_warning=dist_warning,
                    hold_days=hold_days,
                )

                # Progressive exit stages
                atr = float(last.get("ATR14", current_price * 0.02))
                exit_stages = progressive_exit_plan(
                    df=df,
                    entry=pos.entry_price,
                    current_price=current_price,
                    tp1=pos.tp1,
                    tp2=pos.tp2,
                    sl=pos.sl,
                    hold_days=hold_days,
                    shares_held=pos.shares,
                    atr=atr,
                )

                pnl_pct = (current_price - pos.entry_price) / max(pos.entry_price, 1)

                exec_adv = advise_exit_window(
                    t25.action, hold_days, pnl_pct, dist_warning
                )
                text = generate_exit_advisory_text(
                    ticker=ticker,
                    action=t25.action,
                    urgency=t25.urgency,
                    reason=t25.reason,
                    exit_pct=t25.exit_pct,
                    exit_window=t25.exit_window,
                    lang="vi",
                )

                advisories.append({
                    "ticker": ticker,
                    "action": t25.action,
                    "urgency": t25.urgency,
                    "pnl_pct": round(pnl_pct, 4),
                    "hold_days": hold_days,
                    "current_price": current_price,
                    "dist_warning": dist_warning,
                    "exit_stages": [vars(s) for s in exit_stages],
                    "advisory_text": text,
                    "entry_window": exec_adv.get("window", "—"),
                })

                # ── Close paper trade in ledger when exit is triggered ─────
                if t25.action in ("SELL_FULL_ATC", "SELL_PARTIAL"):
                    from datetime import date as _date
                    closed = cache.close_paper_trade(ticker, current_price, _date.today())
                    if closed:
                        log.info(f"Paper trade closed: {ticker} @ {current_price:.2f} ({t25.action})")

            except Exception as e:
                log.warning(f"Exit advisory error {ticker}: {e}")

        return sorted(advisories, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x["urgency"], 3))

    def summary_df(self) -> pd.DataFrame:
        """Return current portfolio summary as DataFrame."""
        rows = []
        for ticker, pos in self._positions.items():
            try:
                df = fetch_ohlcv(ticker, days=5)
                cur = float(df["close"].iloc[-1]) if not df.empty else pos.entry_price
            except Exception:
                cur = pos.entry_price
            pnl = (cur - pos.entry_price) / max(pos.entry_price, 1)
            rows.append({
                "ticker": ticker,
                "entry": pos.entry_price,
                "current": cur,
                "pnl_pct": round(pnl, 4),
                "shares": pos.shares,
                "mode": pos.mode,
                "sl": pos.sl,
                "tp1": pos.tp1,
                "tp2": pos.tp2,
            })
        return pd.DataFrame(rows)
