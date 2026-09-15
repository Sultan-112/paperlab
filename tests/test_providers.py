import asyncio
import time

import pytest

from providers.catalog import import_catalog, parse_saudi
from providers.replay import load_replay
from providers.streams import choose_us
from services.runtime import Runtime
from services.strategy import recommend


def test_subscription_cap_and_rotation():
    universe = [f"S{i}" for i in range(500)]
    first = choose_us(["WATCH"], ["HELD"], universe, 0, 30)
    second = choose_us(["WATCH"], ["HELD"], universe, 30, 30)
    assert len(first) == 30 and len(second) == 30
    assert {"WATCH", "HELD"} <= first & second
    assert first != second
    assert len(choose_us(universe, [], universe, 10, 30)) == 30
    assert choose_us([], [], [], 0, 30) == set()


def test_strategy():
    assert recommend([100] * 20)[0] == "HOLD"
    assert recommend(list(range(1, 21)))[0] == "BUY"
    assert recommend(list(range(20, 0, -1)))[0] == "SELL"
    assert recommend(list(range(1, 21)), False)[0] == "HOLD"
    assert recommend([10])[0] == "HOLD"


def test_saudi_parser_and_import(tmp_path):
    rows = parse_saudi('<a href="/company?companySymbol=2222">Aramco</a><a href="?companySymbol=no">Bad</a>')
    assert len(rows) == 1 and rows[0]["id"] == "KSA:2222"
    assert parse_saudi("<html>Access denied</html>") == []
    path = tmp_path / "ksa.csv"
    path.write_text("symbol,name\n2222.SR,Aramco\n")
    assert import_catalog(path)[0]["currency"] == "SAR"


def test_replay_validates_and_covers_three_markets(tmp_path):
    rows = load_replay("data/replay/demo.csv")
    assert {r["market"] for r in rows} == {"US", "KSA", "CRYPTO"}
    p = tmp_path / "bad.csv"
    p.write_text("timestamp,market,symbol,currency,price\n2,US,A,USD,1\n1,US,A,USD,1\n")
    with pytest.raises(ValueError):
        load_replay(p)


def test_event_deduplication_and_bad_prices():
    r = Runtime()
    r.catalog = {"US:AAPL": None}
    now = time.time()
    r.emit("US:AAPL", 100, now, "alpaca-iex")
    r.emit("US:AAPL", 101, now, "alpaca-iex")
    r.emit("US:AAPL", 102, now - 1, "alpaca-iex")
    r.emit("US:AAPL", float("nan"), now + 1, "alpaca-iex")
    assert len(r.history["US:AAPL"]) == 1
    assert r.quotes["US:AAPL"]["price"] == 100
    asyncio.run(r.redis.aclose())
