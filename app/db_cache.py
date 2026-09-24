"""
db_cache.py — DuckDB persistence layer for VN-Swing Alpha apps.

Three stores in a single file (data/vn_cache.duckdb):
  1. ohlcv       — daily OHLCV bars per ticker (TTL: today's data = 30 min; history = permanent)
  2. scan_results — latest scanner output per ticker (TTL: configurable, default 15 min)
  3. signal_history — time-series of signals per ticker (permanent, queryable by date range)

Usage (Quant_Profiler + quant_app):
    from db_cache import get_ohlcv, put_ohlcv, get_scan_result, put_scan_result, append_signal_history

Design notes:
  - DuckDB is embedded (no server), single .duckdb file, process-local connection pool.
  - Thread-safe: DuckDB write connections are serialised via a threading.Lock.
  - OHLCV is stored as Parquet-compressed columnar data; random reads by ticker are ~1 ms.
  - All timestamps stored as UTC; display conversion is caller's responsibility.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_log = logging.getLogger("db_cache")

# ─── DB file path ─────────────────────────────────────────────────────────────
_DB_DIR  = Path(__file__).parent / "data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = str(_DB_DIR / "vn_cache.duckdb")

# ─── TTLs (seconds) ───────────────────────────────────────────────────────────
OHLCV_TODAY_TTL   = 1800   # today's row treated stale after 30 min (intraday drift)
OHLCV_HISTORY_TTL = None   # historical bars never expire
SCAN_RESULT_TTL   = 900    # scan result stale after 15 min
SIGNAL_HISTORY_MAX_ROWS = 50_000  # per-ticker limit; oldest rows pruned when exceeded

# ─── Connection management ────────────────────────────────────────────────────
_LOCK = threading.Lock()
_conn = None   # module-level singleton


def _get_conn():
    """Return (or create) the module-level DuckDB connection."""
    global _conn
    if _conn is None:
        try:
            import duckdb
            _conn = duckdb.connect(_DB_PATH)
            _init_schema(_conn)
            _log.info("db_cache: connected to %s", _DB_PATH)
        except ImportError:
            _log.warning("db_cache: duckdb not installed — persistence disabled.")
            _conn = _NullConn()
    return _conn


def _init_schema(conn) -> None:
    """Create tables if not present (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            ticker      VARCHAR NOT NULL,
            date        DATE    NOT NULL,
            open        DOUBLE,
            high        DOUBLE,
            low         DOUBLE,
            close       DOUBLE,
            volume      DOUBLE,
            fetched_at  TIMESTAMP NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            ticker      VARCHAR NOT NULL PRIMARY KEY,
            signal      VARCHAR,
            bull_pct    DOUBLE,
            bear_pct    DOUBLE,
            t25_score   DOUBLE,
            price       DOUBLE,
            result_json TEXT,
            fetched_at  TIMESTAMP NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_history (
            id          INTEGER,
            ticker      VARCHAR NOT NULL,
            ts          TIMESTAMP NOT NULL,
            signal      VARCHAR,
            bull_pct    DOUBLE,
            t25_score   DOUBLE,
            price       DOUBLE,
            regime      VARCHAR,
            vsa_state   VARCHAR,
            PRIMARY KEY (ticker, ts)
        )
    """)
    # Indexes for fast ticker-range queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker ON ohlcv (ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sighistory_ticker ON signal_history (ticker, ts DESC)")


class _NullConn:
    """Dummy connection returned when duckdb is unavailable — all ops are no-ops."""
    def execute(self, *a, **kw): return self
    def fetchdf(self): return pd.DataFrame()
    def fetchone(self): return None
    def close(self): pass


# ─── OHLCV ────────────────────────────────────────────────────────────────────

def get_ohlcv(ticker: str, days: int = 400) -> Optional[pd.DataFrame]:
    """
    Return cached OHLCV DataFrame for *ticker* covering up to *days* bars.
    Returns None when:
      - no data exists in DB, or
      - the most-recent row is today and was fetched >30 min ago (intraday stale).
    Partial results (history present but today stale) return history only.
    """
    ticker = ticker.upper()
    try:
        conn = _get_conn()
        with _LOCK:
            df = conn.execute("""
                SELECT date, open, high, low, close, volume, fetched_at
                FROM   ohlcv
                WHERE  ticker = ?
                ORDER  BY date DESC
                LIMIT  ?
            """, [ticker, days]).fetchdf()

        if df.empty:
            return None

        df = df.sort_values("date").reset_index(drop=True)
        df.index = pd.DatetimeIndex(pd.to_datetime(df["date"]))
        df = df.rename(columns={"open": "Open", "high": "High",
                                 "low": "Low", "close": "Close", "volume": "Volume"})

        # Check freshness of the most-recent bar
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_row  = df.iloc[-1]
        if str(last_row.name.date()) == today_str:
            fetched_dt = pd.to_datetime(last_row["fetched_at"]).timestamp()
            if time.time() - fetched_dt > OHLCV_TODAY_TTL:
                # today's bar is stale — drop it so caller re-fetches current price
                df = df.iloc[:-1]
                if df.empty:
                    return None

        return df[["Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        _log.debug("get_ohlcv(%s): %s", ticker, e)
        return None


def put_ohlcv(ticker: str, df: pd.DataFrame) -> None:
    """
    Upsert *df* into the ohlcv table.
    *df* must have a DatetimeIndex and columns Open/High/Low/Close/Volume.
    """
    if df is None or df.empty:
        return
    ticker = ticker.upper()
    now    = datetime.now(timezone.utc)
    try:
        rows = []
        for dt, row in df.iterrows():
            rows.append((
                ticker,
                dt.date() if hasattr(dt, "date") else dt,
                float(row.get("Open",  row.get("open",  0))),
                float(row.get("High",  row.get("high",  0))),
                float(row.get("Low",   row.get("low",   0))),
                float(row.get("Close", row.get("close", 0))),
                float(row.get("Volume", row.get("volume", 0))),
                now,
            ))
        with _LOCK:
            _get_conn().executemany("""
                INSERT OR REPLACE INTO ohlcv
                    (ticker, date, open, high, low, close, volume, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
        _log.debug("put_ohlcv(%s): %d rows upserted", ticker, len(rows))
    except Exception as e:
        _log.debug("put_ohlcv(%s): %s", ticker, e)


# ─── Scan results ─────────────────────────────────────────────────────────────

def get_scan_result(ticker: str) -> Optional[dict]:
    """Return the cached scan result dict for *ticker*, or None if stale/absent."""
    ticker = ticker.upper()
    try:
        row = _get_conn().execute("""
            SELECT result_json, fetched_at FROM scan_results WHERE ticker = ?
        """, [ticker]).fetchone()
        if row is None:
            return None
        result_json, fetched_at = row
        age = time.time() - pd.to_datetime(fetched_at).timestamp()
        if age > SCAN_RESULT_TTL:
            return None
        return json.loads(result_json)
    except Exception as e:
        _log.debug("get_scan_result(%s): %s", ticker, e)
        return None


def put_scan_result(ticker: str, result: dict) -> None:
    """Upsert a scan result dict for *ticker*."""
    if not result:
        return
    ticker = ticker.upper()
    now    = datetime.now(timezone.utc)
    try:
        with _LOCK:
            _get_conn().execute("""
                INSERT OR REPLACE INTO scan_results
                    (ticker, signal, bull_pct, bear_pct, t25_score, price, result_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                ticker,
                result.get("signal", ""),
                float(result.get("bull_pct", 0) or 0),
                float(result.get("bear_pct", 0) or 0),
                float(result.get("t25_score", 0) or 0),
                float(result.get("price", 0) or 0),
                json.dumps(result, default=str),
                now,
            ])
    except Exception as e:
        _log.debug("put_scan_result(%s): %s", ticker, e)


def get_all_scan_results(min_age_s: float = 0) -> pd.DataFrame:
    """
    Return a DataFrame of all scan_results rows with age <= SCAN_RESULT_TTL.
    Useful for displaying the last full-scan snapshot without re-running.
    """
    try:
        cutoff = datetime.fromtimestamp(time.time() - SCAN_RESULT_TTL, tz=timezone.utc)
        df = _get_conn().execute("""
            SELECT ticker, signal, bull_pct, bear_pct, t25_score, price, fetched_at
            FROM   scan_results
            WHERE  fetched_at >= ?
            ORDER  BY t25_score DESC
        """, [cutoff]).fetchdf()
        return df
    except Exception as e:
        _log.debug("get_all_scan_results: %s", e)
        return pd.DataFrame()


# ─── Signal history ───────────────────────────────────────────────────────────

def append_signal_history(ticker: str, result: dict) -> None:
    """
    Append one signal snapshot to signal_history.
    Automatically prunes oldest rows when per-ticker count exceeds SIGNAL_HISTORY_MAX_ROWS.
    """
    if not result:
        return
    ticker = ticker.upper()
    now    = datetime.now(timezone.utc)
    try:
        with _LOCK:
            conn = _get_conn()
            conn.execute("""
                INSERT OR IGNORE INTO signal_history
                    (ticker, ts, signal, bull_pct, t25_score, price, regime, vsa_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                ticker,
                now,
                result.get("signal", ""),
                float(result.get("bull_pct", 0) or 0),
                float(result.get("t25_score", 0) or 0),
                float(result.get("price", 0) or 0),
                result.get("regime_label", ""),
                result.get("vsa_state", ""),
            ])
            # Prune oldest rows when over limit
            count = conn.execute(
                "SELECT COUNT(*) FROM signal_history WHERE ticker = ?", [ticker]
            ).fetchone()[0]
            if count > SIGNAL_HISTORY_MAX_ROWS:
                excess = count - SIGNAL_HISTORY_MAX_ROWS
                conn.execute("""
                    DELETE FROM signal_history
                    WHERE ticker = ?
                    AND   ts IN (
                        SELECT ts FROM signal_history
                        WHERE ticker = ?
                        ORDER BY ts ASC
                        LIMIT ?
                    )
                """, [ticker, ticker, excess])
    except Exception as e:
        _log.debug("append_signal_history(%s): %s", ticker, e)


def get_signal_history(
    ticker: str,
    start: Optional[datetime] = None,
    end:   Optional[datetime] = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    Return signal history for *ticker* between *start* and *end* (UTC datetimes).
    Columns: ts, signal, bull_pct, t25_score, price, regime, vsa_state.
    """
    ticker = ticker.upper()
    params = [ticker]
    where  = ["ticker = ?"]
    if start:
        where.append("ts >= ?"); params.append(start)
    if end:
        where.append("ts <= ?"); params.append(end)
    sql = f"""
        SELECT ts, signal, bull_pct, t25_score, price, regime, vsa_state
        FROM   signal_history
        WHERE  {' AND '.join(where)}
        ORDER  BY ts DESC
        LIMIT  {int(limit)}
    """
    try:
        df = _get_conn().execute(sql, params).fetchdf()
        return df.sort_values("ts").reset_index(drop=True)
    except Exception as e:
        _log.debug("get_signal_history(%s): %s", ticker, e)
        return pd.DataFrame()


# ─── Maintenance ─────────────────────────────────────────────────────────────

def db_stats() -> dict:
    """Return row counts and file size for monitoring."""
    try:
        conn = _get_conn()
        ohlcv_rows  = conn.execute("SELECT COUNT(*) FROM ohlcv").fetchone()[0]
        scan_rows   = conn.execute("SELECT COUNT(*) FROM scan_results").fetchone()[0]
        signal_rows = conn.execute("SELECT COUNT(*) FROM signal_history").fetchone()[0]
        file_mb     = round(Path(_DB_PATH).stat().st_size / 1_048_576, 2) if Path(_DB_PATH).exists() else 0
        return {
            "ohlcv_rows":    ohlcv_rows,
            "scan_rows":     scan_rows,
            "signal_rows":   signal_rows,
            "db_size_mb":    file_mb,
            "db_path":       _DB_PATH,
        }
    except Exception as e:
        return {"error": str(e)}


def vacuum() -> None:
    """Compact the DuckDB file (reclaim space after bulk deletes)."""
    try:
        with _LOCK:
            _get_conn().execute("VACUUM")
        _log.info("db_cache: VACUUM complete")
    except Exception as e:
        _log.warning("db_cache: VACUUM failed: %s", e)
