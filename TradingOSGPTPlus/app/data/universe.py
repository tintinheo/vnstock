from dataclasses import dataclass


@dataclass(frozen=True)
class TickerMeta:
    ticker: str
    exchange: str
    sector: str


SEED_UNIVERSE: tuple[TickerMeta, ...] = (
    TickerMeta("FPT", "HOSE", "Technology"),
    TickerMeta("VCB", "HOSE", "Banking"),
    TickerMeta("HPG", "HOSE", "Materials"),
    TickerMeta("VCG", "HOSE", "Construction"),
    TickerMeta("VIC", "HOSE", "Real Estate"),
    TickerMeta("MSN", "HOSE", "Consumer"),
    TickerMeta("MWG", "HOSE", "Retail"),
    TickerMeta("SSI", "HOSE", "Securities"),
    TickerMeta("VND", "HOSE", "Securities"),
    TickerMeta("ACB", "HOSE", "Banking"),
    TickerMeta("SHB", "HOSE", "Banking"),
    TickerMeta("PVS", "HNX", "Energy"),
    TickerMeta("MBS", "HNX", "Securities"),
    TickerMeta("QNS", "UPCOM", "Consumer"),
)


def normalize_ticker(ticker: str) -> str:
    cleaned = "".join(ch for ch in ticker.upper().strip() if ch.isalnum())
    if not cleaned:
        raise ValueError("ticker is required")
    return cleaned


def lookup_exchange(ticker: str) -> str:
    normalized = normalize_ticker(ticker)
    for item in SEED_UNIVERSE:
        if item.ticker == normalized:
            return item.exchange
    return "UNKNOWN"


def lookup_sector(ticker: str) -> str:
    normalized = normalize_ticker(ticker)
    for item in SEED_UNIVERSE:
        if item.ticker == normalized:
            return item.sector
    return "UNKNOWN"


def list_tickers() -> list[dict[str, str]]:
    return [item.__dict__.copy() for item in SEED_UNIVERSE]

