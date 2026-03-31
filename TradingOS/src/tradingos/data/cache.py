"""DuckDB TTL-managed cache for OHLCV, indicators, scan results, and FR-6 tables."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

import duckdb
import pandas as pd

from ..utils.config import cfg
from ..utils.logging import log

_DDL = """
-- OHLCV daily cache
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ticker      VARCHAR NOT NULL,
    trade_date  DATE    NOT NULL,
    open        DOUBLE,
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE,
    volume      BIGINT,
    fetched_at  TIMESTAMP,
    PRIMARY KEY (ticker, trade_date)
);

-- Intraday 5-minute bars
CREATE TABLE IF NOT EXISTS ohlcv_5m (
    ticker      VARCHAR NOT NULL,
    ts          TIMESTAMP NOT NULL,
    open        DOUBLE,
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE,
    volume      BIGINT,
    PRIMARY KEY (ticker, ts)
);

-- Computed indicators
CREATE TABLE IF NOT EXISTS indicators_daily (
    ticker      VARCHAR NOT NULL,
    trade_date  DATE    NOT NULL,
    sma20       DOUBLE, sma50 DOUBLE, ema9 DOUBLE,
    rsi14       DOUBLE, atr14 DOUBLE,
    obv         DOUBLE, z_vol DOUBLE,
    vwap_daily  DOUBLE,
    hurst       DOUBLE,
    computed_at TIMESTAMP,
    PRIMARY KEY (ticker, trade_date)
);

-- Signal history
CREATE TABLE IF NOT EXISTS signal_history (
    signal_id   VARCHAR PRIMARY KEY,
    ticker      VARCHAR NOT NULL,
    signal_date DATE    NOT NULL,
    action      VARCHAR,
    confidence  VARCHAR,
    mfpm_score  INTEGER,
    sms_raw     INTEGER,
    payload     TEXT,
    created_at  TIMESTAMP
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id    VARCHAR PRIMARY KEY,
    event_type  VARCHAR NOT NULL,
    ticker      VARCHAR,
    timestamp   TIMESTAMP NOT NULL,
    signal_id   VARCHAR,
    action      VARCHAR,
    mfpm_score  INTEGER,
    sms_raw     INTEGER,
    amf_decision VARCHAR,
    rejected_reason VARCHAR,
    payload     TEXT
);

-- Watchlist
CREATE TABLE IF NOT EXISTS watchlist (
    ticker      VARCHAR PRIMARY KEY,
    added_at    DATE,
    notes       TEXT
);

-- Scan results
CREATE TABLE IF NOT EXISTS scan_results (
    scan_id     VARCHAR PRIMARY KEY,
    scan_date   DATE NOT NULL,
    scan_type   VARCHAR,
    results_json TEXT,
    created_at  TIMESTAMP
);

-- Backtest results
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id      VARCHAR PRIMARY KEY,
    ticker      VARCHAR NOT NULL,
    start_date  DATE,
    end_date    DATE,
    mode        VARCHAR,
    result_json TEXT,
    created_at  TIMESTAMP
);

-- Sector map
CREATE TABLE IF NOT EXISTS sector_map (
    ticker      VARCHAR PRIMARY KEY,
    sector      VARCHAR NOT NULL,
    industry    VARCHAR
);

-- ── FR-6 Tables ──────────────────────────────────────────────────────────────

-- Money flow daily (FR-6.1)
CREATE TABLE IF NOT EXISTS money_flow_daily (
    ticker          VARCHAR   NOT NULL,
    trade_date      DATE      NOT NULL,
    whale_net       BIGINT,
    whale_net_proxy BIGINT,
    data_source     VARCHAR,
    fol_net         BIGINT,
    cvd_end         BIGINT,
    sms             INTEGER,
    sms_label       VARCHAR,
    stealth_accum   BOOLEAN,
    sector_flow     VARCHAR,
    computed_at     TIMESTAMP,
    PRIMARY KEY (ticker, trade_date)
);

-- Sector flow cache (FR-6.4)
CREATE TABLE IF NOT EXISTS sector_flow (
    sector          VARCHAR   NOT NULL,
    flow_date       DATE      NOT NULL,
    inflow_score    DOUBLE,
    sms_avg         DOUBLE,
    momentum_5d     DOUBLE,
    flow_status     VARCHAR,
    hot_tickers     VARCHAR,
    computed_at     TIMESTAMP,
    PRIMARY KEY (sector, flow_date)
);

-- Whale distribution alerts (FR-6.6)
CREATE TABLE IF NOT EXISTS distribution_alerts (
    alert_id        VARCHAR   PRIMARY KEY,
    ticker          VARCHAR   NOT NULL,
    alert_date      DATE      NOT NULL,
    warning_level   VARCHAR,
    flags           VARCHAR,
    score           INTEGER,
    explanation     TEXT,
    resolved        BOOLEAN   DEFAULT FALSE,
    created_at      TIMESTAMP
);
"""


class Cache:
    """Thread-local DuckDB connection wrapper with TTL management."""

    def __init__(self) -> None:
        self._db_path = str(cfg.db_path)
        self._con: duckdb.DuckDBPyConnection | None = None

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            try:
                self._con = duckdb.connect(self._db_path)
                self._con.execute(_DDL)
            except Exception:
                # File locked by another process — fall back to in-memory DB
                self._con = duckdb.connect(":memory:")
                self._con.execute(_DDL)
        return self._con

    def close(self) -> None:
        if self._con:
            self._con.close()
            self._con = None

    # ── OHLCV ────────────────────────────────────────────────────────────────

    def get_ohlcv(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        return self.con.execute(
            "SELECT * FROM ohlcv_daily WHERE ticker=? AND trade_date>=? AND trade_date<=? ORDER BY trade_date",
            [ticker, start, end],
        ).df()

    def put_ohlcv(self, ticker: str, df: pd.DataFrame) -> None:
        df = df.copy()
        df["ticker"] = ticker
        df["fetched_at"] = datetime.utcnow()
        if "trade_date" not in df.columns and "date" in df.columns:
            df = df.rename(columns={"date": "trade_date"})
        self.con.execute(
            "INSERT OR REPLACE INTO ohlcv_daily SELECT ticker,trade_date,open,high,low,close,volume,fetched_at FROM df"
        )

    def ohlcv_is_fresh(self, ticker: str, as_of: date) -> bool:
        ttl = cfg.get("data", "ohlcv_ttl_today", default=1800)
        row = self.con.execute(
            "SELECT fetched_at FROM ohlcv_daily WHERE ticker=? AND trade_date=? LIMIT 1",
            [ticker, as_of],
        ).fetchone()
        if not row:
            return False
        age = (datetime.utcnow() - row[0]).total_seconds()
        return age < ttl

    # ── Money Flow Daily ──────────────────────────────────────────────────────

    def get_money_flow(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        return self.con.execute(
            "SELECT * FROM money_flow_daily WHERE ticker=? AND trade_date>=? AND trade_date<=? ORDER BY trade_date",
            [ticker, start, end],
        ).df()

    def put_money_flow(self, ticker: str, trade_date: date, record: dict) -> None:
        self.con.execute(
            """INSERT OR REPLACE INTO money_flow_daily
               (ticker,trade_date,whale_net,whale_net_proxy,data_source,fol_net,
                cvd_end,sms,sms_label,stealth_accum,sector_flow,computed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                ticker, trade_date,
                record.get("whale_net"), record.get("whale_net_proxy"),
                record.get("data_source", "PROXY_OHLCV"),
                record.get("fol_net"), record.get("cvd_end"),
                record.get("sms"), record.get("sms_label"),
                record.get("stealth_accum", False), record.get("sector_flow"),
                datetime.utcnow(),
            ],
        )

    # ── Scan Results ──────────────────────────────────────────────────────────

    def get_latest_scan(self, scan_type: str = "FULL") -> dict | None:
        ttl = cfg.get("data", "scan_result_ttl", default=900)
        row = self.con.execute(
            "SELECT results_json, created_at FROM scan_results WHERE scan_type=? ORDER BY created_at DESC LIMIT 1",
            [scan_type],
        ).fetchone()
        if not row:
            return None
        age = (datetime.utcnow() - row[1]).total_seconds()
        if age > ttl:
            return None
        return json.loads(row[0])

    def put_scan_result(self, scan_id: str, scan_type: str, scan_date: date, data: dict) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO scan_results (scan_id,scan_date,scan_type,results_json,created_at) VALUES (?,?,?,?,?)",
            [scan_id, scan_date, scan_type, json.dumps(data, default=str), datetime.utcnow()],
        )

    # ── Audit Log ────────────────────────────────────────────────────────────

    def put_audit(self, record: dict) -> None:
        import uuid
        audit_id = record.get("audit_id") or str(uuid.uuid4())
        self.con.execute(
            """INSERT OR REPLACE INTO audit_log
               (audit_id,event_type,ticker,timestamp,signal_id,action,mfpm_score,
                sms_raw,amf_decision,rejected_reason,payload)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [
                audit_id, record["event_type"], record.get("ticker"),
                record.get("timestamp", datetime.utcnow()),
                record.get("signal_id"), record.get("action"),
                record.get("mfpm_score"), record.get("sms_raw"),
                record.get("amf_decision"), record.get("rejected_reason"),
                json.dumps(record.get("payload", {}), default=str),
            ],
        )

    def query_audit(
        self,
        ticker: str | None = None,
        event_type: str | None = None,
        days_back: int = 30,
        limit: int = 200,
    ) -> pd.DataFrame:
        from datetime import timedelta
        start = datetime.utcnow() - timedelta(days=days_back)
        event_types = [event_type] if event_type else None
        clauses = ["timestamp>=?"]
        params: list[Any] = [start]
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        if ticker:
            clauses.append("ticker=?")
            params.append(ticker)
        where = "WHERE " + " AND ".join(clauses)
        params.append(limit)
        return self.con.execute(
            f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?",
            params,
        ).df()

    # ── Distribution Alerts ───────────────────────────────────────────────────

    def put_distribution_alert(self, alert: dict) -> None:
        self.con.execute(
            """INSERT OR REPLACE INTO distribution_alerts
               (alert_id,ticker,alert_date,warning_level,flags,score,explanation,resolved,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                alert["alert_id"], alert["ticker"], alert["alert_date"],
                alert["warning_level"], json.dumps(alert.get("flags", [])),
                alert.get("score", 0), alert.get("explanation", ""),
                alert.get("resolved", False), datetime.utcnow(),
            ],
        )

    def get_distribution_alerts(self, active_only: bool = True) -> pd.DataFrame:
        where = "WHERE resolved=FALSE" if active_only else ""
        return self.con.execute(
            f"SELECT * FROM distribution_alerts {where} ORDER BY created_at DESC"
        ).df()

    # ── Sector Flow ───────────────────────────────────────────────────────────

    def put_sector_flow(self, sector: str, flow_date: date, record: dict) -> None:
        self.con.execute(
            """INSERT OR REPLACE INTO sector_flow
               (sector,flow_date,inflow_score,sms_avg,momentum_5d,flow_status,hot_tickers,computed_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                sector, flow_date,
                record.get("inflow_score"), record.get("sms_avg"),
                record.get("momentum_5d"), record.get("flow_status"),
                json.dumps(record.get("hot_tickers", [])), datetime.utcnow(),
            ],
        )

    def get_sector_flows(self, flow_date: date) -> pd.DataFrame:
        return self.con.execute(
            "SELECT * FROM sector_flow WHERE flow_date=? ORDER BY inflow_score DESC",
            [flow_date],
        ).df()

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def get_watchlist(self) -> list[str]:
        rows = self.con.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
        return [r[0] for r in rows]

    def add_to_watchlist(self, ticker: str, notes: str = "") -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO watchlist (ticker,added_at,notes) VALUES (?,?,?)",
            [ticker, date.today(), notes],
        )

    # ── Sector Map ────────────────────────────────────────────────────────────

    def get_sector(self, ticker: str) -> str:
        row = self.con.execute(
            "SELECT sector FROM sector_map WHERE ticker=?", [ticker]
        ).fetchone()
        return row[0] if row else "OTHER"

    def put_sector_map(self, records: list[dict]) -> None:
        for r in records:
            self.con.execute(
                "INSERT OR REPLACE INTO sector_map (ticker,sector,industry) VALUES (?,?,?)",
                [r["ticker"], r.get("sector", "OTHER"), r.get("industry", "")],
            )


# Module-level singleton
cache = Cache()
