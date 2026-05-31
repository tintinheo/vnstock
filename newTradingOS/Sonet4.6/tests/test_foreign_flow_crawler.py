"""
test_foreign_flow_crawler.py — Test crawl và parse lịch sử khối ngoại từ CafeF.
"""
import pytest
import pandas as pd
from core.foreign_flow_crawler import fetch_cafef_weekly_foreign_flow, load_cached_foreign_flow

def test_cafef_weekly_crawl_and_parse():
    df = fetch_cafef_weekly_foreign_flow()
    assert not df.empty, "Crawl trả về DataFrame rỗng"
    assert set(["date", "ticker", "buy_value", "sell_value", "net_value"]).issubset(df.columns)
    assert df["buy_value"].ge(0).all()
    assert df["sell_value"].ge(0).all()
    assert df["ticker"].str.match(r"^[A-Z0-9]{3,}$").all()

def test_load_cached_foreign_flow():
    df = load_cached_foreign_flow()
    if not df.empty:
        assert set(["date", "ticker", "buy_value", "sell_value", "net_value"]).issubset(df.columns)
