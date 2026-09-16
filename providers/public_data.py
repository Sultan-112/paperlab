"""Read-only, no-key public data. No execution endpoints or paid fallback."""

import csv
import io
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

USER_AGENT = "PaperLab/0.1 (local educational market viewer)"
MUBASHER_URL = "https://english.mubasher.info/api/1/stocks/prices/all"
NASDAQ_ROOT = "https://www.nasdaqtrader.com/dynamic/SymDir/"


def public_client():
    return httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def retry_seconds(response, default=60):
    raw = response.headers.get("Retry-After", "")
    try:
        return max(default, float(raw))
    except ValueError:
        try:
            return max(
                default, parsedate_to_datetime(raw).timestamp() - datetime.now(timezone.utc).timestamp()
            )
        except (ValueError, TypeError, OverflowError):
            return default


def parse_directory(content):
    from providers.catalog import asset

    rows = list(csv.DictReader(io.StringIO(content), delimiter="|"))
    if not rows or "Security Name" not in rows[0] or "Test Issue" not in rows[0]:
        raise ValueError("Invalid Nasdaq symbol directory; existing catalog retained")
    found = {}
    for row in rows:
        symbol = (row.get("ACT Symbol") or row.get("Symbol") or "").strip()
        name = row.get("Security Name") or ""
        if row.get("Test Issue") != "N" or not symbol or not name:
            continue
        found[symbol] = asset("US", symbol, name, "USD", "nasdaq-directory")
    if not found:
        raise ValueError("Empty Nasdaq symbol directory")
    return list(found.values())


async def us_directory(client):
    result = {}
    # Both files must succeed before the catalog can be replaced.
    for name in ["nasdaqlisted.txt", "otherlisted.txt"]:
        r = await client.get(NASDAQ_ROOT + name)
        r.raise_for_status()
        result.update({a["id"]: a for a in parse_directory(r.text)})
    return list(result.values())


def saudi_rows(payload):
    rows = payload.get("prices")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Saudi provider returned no catalog rows")
    # Numeric Saudi instruments include Main Market, Nomu, funds and debt.
    # Legacy .B/.R lines are excluded; activity/completeness is not guaranteed.
    return [
        r
        for r in rows
        if r.get("exchange") == "TDWL" and re.fullmatch(r"\d{4,8}", str(r.get("code", ""))) and r.get("name")
    ]


async def saudi_snapshot(client):
    response = await client.get(MUBASHER_URL, params={"country": "sa"})
    response.raise_for_status()
    payload = response.json()
    if not saudi_rows(payload):
        raise ValueError("Saudi provider returned no usable catalog rows")
    return payload


def saudi_catalog(payload):
    from providers.catalog import asset

    return [asset("KSA", r["code"], r["name"], "SAR", "mubasher-public") for r in saudi_rows(payload)]


def saudi_ticks(payload):
    for row in saudi_rows(payload):
        try:
            price = float(str(row["value"]).replace(",", ""))
            # updatedAt is the per-instrument UTC data timestamp; lastUpdate is a page clock.
            stamp = datetime.fromisoformat(row["updatedAt"])
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if math.isfinite(price) and price > 0:
                yield ("KSA:" + row["code"], price, stamp.timestamp(), "mubasher-delayed")
        except (KeyError, TypeError, ValueError, OverflowError):
            continue


def yahoo_symbol(symbol):
    return symbol.replace("$", "-P").replace(".", "-")


def parse_chart(payload, now):
    chart = payload.get("chart", {})
    results = chart.get("result")
    if chart.get("error") or not results:
        raise ValueError("No public price snapshot for this symbol")
    result = results[0]
    meta = result["meta"]
    price = float(meta["regularMarketPrice"])
    stamp = float(meta["regularMarketTime"])
    if not math.isfinite(price) or price <= 0 or not math.isfinite(stamp) or stamp > now + 10:
        raise ValueError("Invalid public market price or timestamp")
    period = meta.get("currentTradingPeriod", {}).get("regular", {})
    market_open = period.get("start", 0) <= now < period.get("end", 0)
    samples = []
    series = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    for t, p in zip(result.get("timestamp", []), series):
        if t is not None and p is not None and t < stamp and math.isfinite(float(p)) and p > 0:
            samples.append((float(t), float(p)))
    return {
        "price": price,
        "timestamp": stamp,
        "market_open": market_open,
        "currency": meta.get("currency"),
        "history": sorted(samples)[-19:],
        "change_percent": meta.get("regularMarketChangePercent"),
    }


async def us_snapshot(client, symbol, now):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(yahoo_symbol(symbol), safe="")
    response = await client.get(url, params={"interval": "1m", "range": "1d"})
    response.raise_for_status()
    return parse_chart(response.json(), now)
