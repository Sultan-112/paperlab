import csv
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from libs.config import settings

SAUDI_ROOT = "https://www.saudiexchange.sa/wps/portal/saudiexchange/"
SAUDI_PAGES = [
    "ourmarkets/main-market-watch",
    "ourmarkets/nomu-parallel-market-watch",
    "ourmarkets/sukuk-and-bonds-market-watch",
    "ourmarkets/funds-market-watch",
    "trading/participants-directory/issuer-directory",
]


def asset(market, symbol, name, currency, source):
    return dict(
        id=f"{market}:{symbol}",
        market=market,
        symbol=symbol,
        name=name[:250],
        currency=currency,
        source=source,
        active=True,
    )


def parse_saudi(html):
    """Parse public company links; fail closed if the exchange serves a JS-only shell."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for link in soup.select("a[href]"):
        query = parse_qs(urlparse(link["href"]).query)
        symbol = (query.get("companySymbol") or query.get("symbol") or [""])[0]
        if re.fullmatch(r"\d{4,8}", symbol):
            name = link.get_text(" ", strip=True) or symbol
            found[symbol] = asset("KSA", symbol, name, "SAR", "saudi-public")
    return list(found.values())


def import_catalog(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"symbol", "name"}.issubset(rows[0]):
        raise ValueError("KSA CSV requires symbol,name columns")
    result = []
    for row in rows:
        symbol = row["symbol"].removesuffix(".SR").strip()
        if not re.fullmatch(r"\d{4,8}", symbol) or not row["name"].strip():
            raise ValueError("Invalid Saudi catalog symbol or name")
        result.append(asset("KSA", symbol, row["name"], "SAR", "saudi-import"))
    return result


async def discover(market):
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if market == "CRYPTO":
            r = await client.get("https://data-api.binance.vision/api/v3/exchangeInfo")
            r.raise_for_status()
            return [
                asset(
                    "CRYPTO", s["symbol"], f"{s['baseAsset']}/{s['quoteAsset']}", s["quoteAsset"], "binance"
                )
                for s in r.json()["symbols"]
                if s["status"] == "TRADING" and s.get("isSpotTradingAllowed", True)
            ]
        if market == "US":
            if not settings.alpaca_key or not settings.alpaca_secret:
                raise ValueError("US discovery needs free Alpaca account credentials")
            # Only this read-only asset endpoint is used on the broker API domain.
            r = await client.get(
                "https://paper-api.alpaca.markets/v2/assets",
                params={"status": "active", "asset_class": "us_equity"},
                headers={
                    "APCA-API-KEY-ID": settings.alpaca_key,
                    "APCA-API-SECRET-KEY": settings.alpaca_secret,
                },
            )
            r.raise_for_status()
            return [asset("US", s["symbol"], s["name"], "USD", "alpaca") for s in r.json()]
        if market != "KSA":
            raise ValueError("Unknown market")
        if Path(settings.ksa_catalog).exists():
            return import_catalog(settings.ksa_catalog)
        found = {}
        for page in SAUDI_PAGES:
            r = await client.get(SAUDI_ROOT + page, params={"locale": "en"})
            r.raise_for_status()
            found.update({a["id"]: a for a in parse_saudi(r.text)})
        if not found:
            raise ValueError(
                "Saudi pages expose no catalog rows. Import a freely obtained symbol,name CSV; completeness is unverified."
            )
        return list(found.values())
