"""data/news_scraper.py – CafeF news scraper."""
import re, requests
from config.settings import CAFEF_NEWS_URL

HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_cafef_headlines(pages=3):
    articles = []
    for page in range(1, pages + 1):
        try:
            r = requests.get(CAFEF_NEWS_URL.format(page=page), headers=HEADERS, timeout=10)
            r.raise_for_status()
            for m in re.finditer(r'title="([^"]{10,})"', r.text):
                articles.append({"title": m.group(1).strip(), "source": "cafef"})
        except Exception as e:
            print(f"[CafeF] page {page}: {e}")
    return articles