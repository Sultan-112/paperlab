import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from libs.quotes import quote_info
from providers.public_data import (
    parse_chart,
    parse_directory,
    retry_seconds,
    saudi_catalog,
    saudi_ticks,
    us_directory,
    us_snapshot,
    yahoo_symbol,
)
from services.runtime import Runtime


def test_nasdaq_directory_ignores_test_and_footer():
    content = "Symbol|Security Name|Test Issue|ETF\nAAPL|Apple|N|N\nTEST|Test|Y|N\nSPY|Fund|N|Y\nFile Creation Time: 20260916|||\n"
    rows = parse_directory(content)
    assert [r["symbol"] for r in rows] == ["AAPL", "SPY"]
    assert rows[0]["source"] == "nasdaq-directory"
    with pytest.raises(ValueError):
        parse_directory("<html>Service unavailable</html>")


def test_both_us_files_required_before_refresh():
    def handler(request):
        if "otherlisted" in request.url.path:
            return httpx.Response(503)
        return httpx.Response(200, text="Symbol|Security Name|Test Issue\nAAPL|Apple|N\n")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await us_directory(client)

    asyncio.run(run())


def test_saudi_catalog_covers_numeric_instruments_and_preserves_old_time():
    payload = {
        "prices": [
            {
                "code": "2222",
                "exchange": "TDWL",
                "name": "ARAMCO",
                "value": "25.68",
                "updatedAt": "2026-09-16 12:19:55",
            },
            {
                "code": "9609",
                "exchange": "TDWL",
                "name": "NOMU",
                "value": "1,000.25",
                "updatedAt": "2024-01-01 10:00:00",
            },
            {"code": "2222.R", "exchange": "TDWL", "name": "Expired right"},
            {"code": "1120", "exchange": "OTHER", "name": "Wrong market"},
        ]
    }
    assert [a["id"] for a in saudi_catalog(payload)] == ["KSA:2222", "KSA:9609"]
    ticks = list(saudi_ticks(payload))
    assert ticks[1][1] == 1000.25
    assert datetime.fromtimestamp(ticks[1][2], timezone.utc).year == 2024
    assert ticks[0][3] == "mubasher-delayed"


def chart():
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 100,
                        "regularMarketTime": 990,
                        "currency": "USD",
                        "currentTradingPeriod": {"regular": {"start": 900, "end": 1100}},
                    },
                    "timestamp": [950, 960, 970, 990, 1010],
                    "indicators": {"quote": [{"close": [98, None, 99, 100, 102]}]},
                }
            ]
        }
    }


def test_chart_seed_excludes_null_current_and_future_observations():
    result = parse_chart(chart(), 1000)
    assert result["market_open"]
    assert result["history"] == [(950, 98), (970, 99)]
    assert parse_chart(chart(), 1200)["market_open"] is False
    with pytest.raises(ValueError):
        parse_chart({"chart": {"error": {"description": "not found"}}}, 1000)


def test_snapshot_endpoint_is_read_only_and_maps_share_class():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=chart())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await us_snapshot(client, "BRK.B", 1000)

    asyncio.run(run())
    assert requests[0].method == "GET"
    assert requests[0].url.path.endswith("/BRK-B")
    assert yahoo_symbol("ABR$D") == "ABR-PD"


@pytest.mark.parametrize(
    "source,event_age,checked_age,expected",
    [
        ("binance", 5, 5, True),
        ("binance", 30, 1, False),
        ("yahoo-public", 90, 10, True),
        ("yahoo-public", 300, 1, False),
        ("mubasher-delayed", 950, 10, True),
        ("mubasher-delayed", 1100, 1, False),
        ("mubasher-delayed", 950, 121, False),
        ("replay", 100000, 5, True),
    ],
)
def test_source_specific_freshness(source, event_age, checked_age, expected):
    q = {
        "source": source,
        "timestamp": 200000 - event_age,
        "received": 199995,
        "checked": 200000 - checked_age,
    }
    assert quote_info(q, 200000)["fresh"] is expected


def test_closed_market_and_expired_replay_cannot_fill():
    q = {"source": "yahoo-public", "timestamp": 1000, "received": 1000, "market_open": False}
    assert not quote_info(q, 1001)["fresh"]
    q = {"source": "replay", "timestamp": 1000, "received": 800, "checked": 1000}
    assert not quote_info(q, 1001)["fresh"]


def test_retry_after_is_respected():
    assert retry_seconds(httpx.Response(429, headers={"Retry-After": "300"})) == 300
    assert retry_seconds(httpx.Response(429, headers={"Retry-After": "invalid"})) == 60


def test_repeated_poll_does_not_revive_old_price_or_extend_history():
    runtime = Runtime()
    runtime.catalog = {"US:AAPL": None}
    runtime.emit("US:AAPL", 100, 1000, "yahoo-public")
    first = runtime.quotes["US:AAPL"]["received"]
    runtime.emit("US:AAPL", 100, 1000, "yahoo-public")
    assert runtime.quotes["US:AAPL"]["received"] == first
    assert len(runtime.history["US:AAPL"]) == 1
    assert not quote_info(runtime.quotes["US:AAPL"])["fresh"]
    asyncio.run(runtime.redis.aclose())
