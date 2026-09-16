"""Read-only public daily history; explicit errors instead of synthetic fallback."""

import math
import time
from urllib.parse import quote

from providers.public_data import public_client, yahoo_symbol


def parse_history(payload, now):
    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise ValueError("No historical data available for this asset")
    result = chart["result"][0]
    if result.get("events", {}).get("splits"):
        raise ValueError("History contains a stock split; import verified adjusted bars instead")
    rows = []
    prices = result["indicators"]["quote"][0]
    for stamp, opening, close in zip(result.get("timestamp", []), prices["open"], prices["close"]):
        if stamp is None or opening is None or close is None or stamp + 86400 > now:
            continue
        if all(math.isfinite(v) and v > 0 for v in (stamp, opening, close)):
            rows.append({"timestamp": stamp, "open": opening, "close": close})
    return rows


async def fetch_history(asset):
    market, symbol = asset.split(":", 1)
    if market == "US":
        symbol = yahoo_symbol(symbol)
    elif market == "KSA":
        symbol += ".SR"
    elif market == "CRYPTO" and symbol in {"BTCUSDT", "ETHUSDT"}:
        # Yahoo USD is a proxy, not the Binance USDT execution feed.
        symbol = symbol[:-4] + "-USD"
    else:
        raise ValueError(
            "Public history supports US/KSA and BTCUSDT/ETHUSDT proxies; use CSV for other assets"
        )
    async with public_client() as client:
        response = await client.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe=""),
            params={"range": "2y", "interval": "1d", "events": "splits"},
        )
        response.raise_for_status()
    return parse_history(response.json(), time.time()), "Yahoo public daily history: " + symbol
