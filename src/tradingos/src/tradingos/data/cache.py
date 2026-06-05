import duckdb
import pandas as pd
from datetime import datetime
import os

DB_PATH = os.getenv("TRADINGOS_DB_PATH", "data/vn_cache.duckdb")

def get_connection():
    """Returns a DuckDB connection with WAL enabled for concurrent reads."""
    conn = duckdb.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_tables():
    """Initializes DuckDB schema if it does not exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_daily (
            ticker VARCHAR,
            trade_date DATE,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            adjusted_close DOUBLE,
            fetched_at TIMESTAMP,
            PRIMARY KEY (ticker, trade_date)
        );
        
        CREATE TABLE IF NOT EXISTS scan_results (
            ticker VARCHAR,
            scan_date DATE,
            mfpm_score INTEGER,
            signal VARCHAR,
            mode VARCHAR,
            expires_at TIMESTAMP,
            PRIMARY KEY (ticker, scan_date)
        );
    """)
    conn.close()

def save_ohlcv_batch(df: pd.DataFrame):
    """Saves a batch of OHLCV data to DuckDB."""
    conn = get_connection()
    df['fetched_at'] = datetime.now()
    # Using DuckDB's native Pandas integration for fast inserts
    conn.execute("INSERT OR REPLACE INTO ohlcv_daily SELECT * FROM df")
    conn.close()

def load_ohlcv(ticker: str, start_date: str = None) -> pd.DataFrame:
    """Loads historical data for a specific ticker."""
    conn = get_connection()
    query = f"SELECT * FROM ohlcv_daily WHERE ticker = '{ticker}'"
    if start_date:
        query += f" AND trade_date >= '{start_date}'"
    query += " ORDER BY trade_date ASC"
    
    df = conn.execute(query).df()
    conn.close()
    return df