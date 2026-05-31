"""
foreign_flow_crawler.py — Crawl lịch sử mua/bán ròng khối ngoại từ CafeF (public, không login).
"""
from __future__ import annotations
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import re

CAFEF_WEEKLY_URL = "https://cafef.vn/du-lieu.chn"
CACHE_PATH = Path("data/foreign_flow_cache.csv")


def fetch_cafef_weekly_foreign_flow() -> pd.DataFrame:
    """
    Crawl bảng tổng hợp giao dịch khối ngoại tuần gần nhất từ CafeF.
    Trả về DataFrame: [date, ticker, buy_value, sell_value, net_value]
    """
    resp = requests.get(CAFEF_WEEKLY_URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Tìm bảng giao dịch khối ngoại (thường có tiêu đề 'Giao dịch NĐTNN' hoặc tương tự)
    table = None
    for tbl in soup.find_all("table"):
        if tbl.find(string=re.compile("NĐTNN|khối ngoại", re.I)):
            table = tbl
            break
    if table is None:
        raise RuntimeError("Không tìm thấy bảng giao dịch khối ngoại trên CafeF")

    rows = []
    for tr in table.find_all("tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cols) < 5 or not re.match(r"^[A-Z0-9]{3,}$", cols[0]):
            continue  # Bỏ qua header hoặc dòng không phải mã
        try:
            ticker = cols[0]
            buy_value = float(cols[2].replace(",", ""))
            sell_value = float(cols[3].replace(",", ""))
            net_value = float(cols[4].replace(",", ""))
            # Tuần gần nhất, gán ngày = hôm nay (có thể refine sau)
            date = datetime.today().strftime("%Y-%m-%d")
            rows.append({
                "date": date,
                "ticker": ticker,
                "buy_value": buy_value,
                "sell_value": sell_value,
                "net_value": net_value,
            })
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(CACHE_PATH, index=False)
    return df


def load_cached_foreign_flow() -> pd.DataFrame:
    if CACHE_PATH.exists():
        return pd.read_csv(CACHE_PATH)
    return pd.DataFrame([])


if __name__ == "__main__":
    df = fetch_cafef_weekly_foreign_flow()
    print(df.head())
