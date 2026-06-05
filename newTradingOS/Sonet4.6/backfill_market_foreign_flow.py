from __future__ import annotations

import argparse
import json

from core.foreign_flow_crawler import (
    fetch_cafef_market_foreign_flow_history,
    summarize_market_foreign_flow_history,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill and cache market-wide foreign-flow history from CafeF.",
    )
    parser.add_argument("--sessions", type=int, default=20, help="Target number of recent sessions to retain in the summary.")
    parser.add_argument("--max-pages", type=int, default=250, help="Maximum CafeF pages to crawl per exchange during the backfill.")
    args = parser.parse_args()

    history = fetch_cafef_market_foreign_flow_history(
        sessions=max(1, args.sessions),
        max_pages_per_exchange=max(1, args.max_pages),
        force_refresh=True,
    )
    summary = summarize_market_foreign_flow_history(history, sessions=max(1, args.sessions))

    payload = {
        "history_rows": int(len(history)),
        "history_sessions": summary.get("history_sessions", 0),
        "history_as_of": summary.get("history_as_of"),
        "net_buy": summary.get("net_buy", 0),
        "net_buy_20d": summary.get("net_buy_20d", 0),
        "trend": summary.get("trend", "N/A"),
        "trend_20d": summary.get("trend_20d", "neutral"),
        "basis": summary.get("basis", "not_available"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()