import pytest

from app.data.clients import MarketDataClient
from app.errors import DataUnavailableError


class EmptyCache:
    def get_valid(self, ticker):
        return None

    def put(self, ticker, frame, metadata):
        raise AssertionError("put should not be called when all sources fail")


def test_data_client_raises_when_sources_and_cache_fail(monkeypatch):
    client = MarketDataClient(cache=EmptyCache())
    monkeypatch.setattr(client, "_fetcher_for", lambda source: (_ for _ in ()).throw(ValueError("down")))
    with pytest.raises(DataUnavailableError):
        client.get_history("FPT")

