from datetime import date

import pandas as pd

from app.data.normalizer import normalize_ohlcv


def test_cafef_thousands_to_vnd_normalization():
    raw = pd.DataFrame(
        {
            "date": [date(2026, 1, 1), date(2026, 1, 2)],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [1000, 1500],
        }
    )
    frame = normalize_ohlcv(raw, "FPT", "CafeF", unit_rule="thousands_to_vnd")
    assert frame.iloc[-1]["close"] == 102000
    assert frame.iloc[-1]["unit_rule_applied"] == "thousands_to_vnd"

