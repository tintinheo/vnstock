"""data/cafef_client.py – CafeF scraper using POST (ASP.NET postback).

CafeF URL: https://s.cafef.vn/Lich-su-giao-dich-{TICKER}-1.chn
Must use POST with ASP.NET __EVENTTARGET + __EVENTARGUMENT for pagination.
Prices are in nghìn VND → multiply by 1000.
"""
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import logging, time, re

logger = logging.getLogger(__name__)


class CafeFClient:
    BASE = "https://s.cafef.vn/Lich-su-giao-dich-{ticker}-1.chn"

    def __init__(self, timeout=15):
        self.s = requests.Session()
        self.timeout = timeout
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
            "Accept": "*/*",
            "Origin": "https://s.cafef.vn",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-MicrosoftAjax": "Delta=true",
        })

    def _parse_float(self, txt):
        txt = txt.strip().replace(",", "").replace("\xa0", "")
        txt = re.sub(r"[()%]", "", txt)
        try: return float(txt)
        except: return None

    def get_ohlcv(self, ticker: str, start="2020-01-01", end=None, max_pages=50) -> pd.DataFrame:
        ticker = ticker.upper().strip()
        url = self.BASE.format(ticker=ticker)
        start_dt = pd.to_datetime(start) if start else None
        all_rows = []

        # First GET to get the page (and cookies/viewstate)
        try:
            init = self.s.get(url, timeout=self.timeout)
            if init.status_code != 200:
                logger.warning(f"[CafeF] {ticker}: HTTP {init.status_code}")
                return pd.DataFrame()
        except Exception as e:
            logger.warning(f"[CafeF] {ticker} init: {e}")
            return pd.DataFrame()

        for page in range(1, max_pages + 1):
            try:
                body = (
                    f"ctl00$ContentPlaceHolder1$scriptmanager="
                    f"ctl00$ContentPlaceHolder1$ctl03$panelAjax|"
                    f"ctl00$ContentPlaceHolder1$ctl03$pager2"
                    f"&ctl00$ContentPlaceHolder1$ctl03$txtKeyword={ticker}"
                    f"&ctl00$ContentPlaceHolder1$ctl03$dpkTradeDate1$txtDatePicker="
                    f"&ctl00$ContentPlaceHolder1$ctl03$dpkTradeDate2$txtDatePicker="
                    f"&__EVENTTARGET=ctl00$ContentPlaceHolder1$ctl03$pager2"
                    f"&__EVENTARGUMENT={page}"
                    f"&__VIEWSTATE=%2FwEPDwUKMTU2NzY0ODUyMGQYAQUeX19Db250cm9sc1JlcXVpcmVQb3N0QmFja0tleV9fFgEFKGN0bDAwJENvbnRlbnRQbGFjZUhvbGRlcjEkY3RsMDMkYnRTZWFyY2jJnyPYjjwDsOatyCQBZar0ZSQygQ%3D%3D"
                    f"&__VIEWSTATEGENERATOR=2E2252AF"
                    f"&__ASYNCPOST=true&"
                )

                resp = self.s.post(url, data=body, timeout=self.timeout)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", {"id": "GirdTable2"})
                if not table:
                    # Try finding any data table
                    tables = soup.find_all("table")
                    for t in tables:
                        rows = t.find_all("tr")
                        if len(rows) > 2:
                            table = t
                            break
                if not table:
                    break

                rows = table.find_all("tr")[2:]  # skip header rows
                if not rows:
                    break

                found_before_start = False
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 7:
                        continue
                    try:
                        date_txt = cells[0].get_text(strip=True)
                        date = pd.to_datetime(date_txt, format="%d/%m/%Y", errors="coerce")
                        if pd.isna(date):
                            continue

                        if start_dt and date < start_dt:
                            found_before_start = True
                            continue

                        close = self._parse_float(cells[1].get_text())
                        if close is None or close <= 0:
                            continue

                        # CafeF columns vary, but typically:
                        # 0:Date 1:Close 2:Change 3:Vol(KL) 4:Value(GT) 5:Open 6:High 7:Low
                        # OR: 0:Date 1:Close 2:Change 3:Open 4:High 5:Low 6:Vol 7:Value
                        # We try both patterns
                        open_ = self._parse_float(cells[5].get_text()) if len(cells) > 5 else close
                        high = self._parse_float(cells[6].get_text()) if len(cells) > 6 else close
                        low = self._parse_float(cells[7].get_text()) if len(cells) > 7 else close

                        # Volume - try cell 3 or 6
                        vol_txt = cells[3].get_text(strip=True).replace(",", "").replace(".", "")
                        try:
                            volume = int(float(vol_txt)) if vol_txt else 0
                        except:
                            volume = 0

                        # Sanity: if open/high/low seem off, use close
                        if open_ is None or open_ <= 0: open_ = close
                        if high is None or high <= 0: high = close
                        if low is None or low <= 0: low = close

                        all_rows.append({
                            "date": date,
                            "open": open_ * 1000,
                            "high": high * 1000,
                            "low": low * 1000,
                            "close": close * 1000,
                            "volume": volume,
                        })
                    except Exception:
                        continue

                if found_before_start:
                    break  # We've gone past the start date

                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"[CafeF] {ticker} page {page}: {e}")
                break

        if not all_rows:
            logger.warning(f"[CafeF] No data for {ticker}")
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        df = df.drop_duplicates(subset=["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["_source"] = "CafeF"

        if len(df) > 0:
            last = df["close"].iloc[-1]
            logger.info(f"[CafeF] ✅ {ticker}: {len(df)} rows, last={last:,.0f} VND")
        return df
