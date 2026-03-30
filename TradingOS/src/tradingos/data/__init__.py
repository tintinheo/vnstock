"""
data/ — Data fetching, caching, and normalization.

Modules:
    fetcher.py      — Multi-source OHLCV cascade (DNSE, SSI, CafeF, TCBS)
    cache.py        — DuckDB persistence layer (read-through / write-back)
    realtime.py     — SSI iboard-query real-time price feed
    normalizer.py   — Price scale normalization, tick rounding, VND conversion
"""
