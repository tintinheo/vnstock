"""tests/test_data.py – Test data clients."""
from data.data_manager import DataManager

def test_synthetic_fallback():
    dm = DataManager(); df = dm.get_ohlcv("SYNTHETIC_TEST", start="2020-01-01", use_cache=False)
    assert not df.empty and "close" in df.columns and len(df) > 100

def test_multiple():
    dm = DataManager(); data = dm.get_multiple(tickers=["AAA","BBB"], start="2023-01-01")
    assert len(data) == 2
