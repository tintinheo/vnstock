"""data/vnstock_client.py - Uses vnstock library (v4+) for reliable data.

vnstock v4+ uses KBS as default, VCI as backup.
Install: pip install vnstock
"""
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class VnstockClient:
    """Wrapper around vnstock library."""

    def get_ohlcv(self, ticker: str, start: str = "2020-01-01",
                  end: str = None, source: str = "VCI") -> pd.DataFrame:
        """Fetch OHLCV via vnstock. Prices in VND.

        Args:
            ticker: e.g. 'VCG', 'FPT'
            start: 'YYYY-MM-DD'
            end: 'YYYY-MM-DD' (default today)
            source: 'VCI' or 'TCBS'
        """
        ticker = ticker.upper().strip()
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        try:
            from vnstock import Vnstock

            vs = Vnstock()
            stock = vs.stock(symbol=ticker, source=source)
            df = stock.quote.history(start=start, end=end, interval="1D")

            if df is None or (hasattr(df, 'empty') and df.empty):
                logger.warning(f"[vnstock/{source}] No data for {ticker}")
                return pd.DataFrame()

            # Convert to standard DataFrame if needed
            if hasattr(df, 'to_df'):
                df = df.to_df()
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)

            # Reset index (vnstock sometimes puts date as index)
            if df.index.name is not None:
                df = df.reset_index()

            # Standardize columns - vnstock v4 returns lowercase columns
            col_map = {}
            for col in df.columns:
                cl = str(col).lower().strip()
                if cl in ("time", "tradingdate", "trading_date"):
                    col_map[col] = "date"
                elif cl == "open":
                    col_map[col] = "open"
                elif cl == "high":
                    col_map[col] = "high"
                elif cl == "low":
                    col_map[col] = "low"
                elif cl == "close":
                    col_map[col] = "close"
                elif cl in ("volume", "vol"):
                    col_map[col] = "volume"
            df = df.rename(columns=col_map)

            # If date column is missing, try first column
            if "date" not in df.columns and len(df.columns) > 0:
                first = df.columns[0]
                try:
                    pd.to_datetime(df[first])
                    df = df.rename(columns={first: "date"})
                except Exception:
                    pass

            if "date" not in df.columns:
                logger.error(f"[vnstock/{source}] {ticker}: No date column. Columns: {list(df.columns)}")
                return pd.DataFrame()

            df["date"] = pd.to_datetime(df["date"])

            for c in ["open", "high", "low", "close", "volume"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            # Price unit check: if median < 500 -> x1000 VND format
            if "close" in df.columns and len(df) > 0:
                med = df["close"].median()
                if med < 500:
                    for c in ["open", "high", "low", "close"]:
                        if c in df.columns:
                            df[c] = (df[c] * 1000).round(0)
                    logger.info(f"[vnstock/{source}] {ticker}: Converted x1000->VND (median raw={med:.1f})")

            required = ["date", "open", "high", "low", "close", "volume"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                logger.error(f"[vnstock/{source}] {ticker}: Missing {missing}. Have: {list(df.columns)}")
                return pd.DataFrame()

            df = df[required].copy()
            df = df.dropna(subset=["close"])
            df = df.sort_values("date").reset_index(drop=True)
            df["_source"] = f"vnstock_{source}"

            if len(df) > 0:
                last = df["close"].iloc[-1]
                last_d = df["date"].iloc[-1].strftime("%Y-%m-%d")
                logger.info(f"[vnstock/{source}] {ticker}: {len(df)} bars, last={last:,.0f} VND ({last_d})")

            return df

        except ImportError:
            raise ImportError(
                "vnstock not installed. Run: pip install vnstock"
            )
        except Exception as e:
            logger.warning(f"[vnstock/{source}] {ticker} error: {type(e).__name__}: {e}")
            return pd.DataFrame()
