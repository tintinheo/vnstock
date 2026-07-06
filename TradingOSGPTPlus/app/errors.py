class TradingOSError(Exception):
    """Base application error."""


class DataUnavailableError(TradingOSError):
    """Raised when real sources and valid cache cannot provide market data."""

    def __init__(self, ticker: str, errors: list[str] | None = None):
        self.ticker = ticker
        self.errors = errors or []
        detail = "; ".join(self.errors) if self.errors else "no usable source returned data"
        super().__init__(f"Data unavailable for {ticker}: {detail}")

