import asyncio
import json
import time
from datetime import datetime

import websockets

from libs.config import settings
from libs.metrics import SUBSCRIPTIONS


def choose_us(watched, held, catalog, offset, limit):
    """Held positions and watchlist first; rotate remaining universe capacity every minute."""
    priority = list(dict.fromkeys(held + watched))
    if len(priority) >= limit:
        # Rotate oversubscribed watchlists too, while prioritizing held symbols.
        pinned = list(dict.fromkeys(held))[:limit]
        rest = [s for s in priority if s not in pinned]
        n = len(rest)
        return set(pinned + [rest[(offset + i) % n] for i in range(min(limit - len(pinned), n))])
    rest = [s for s in catalog if s not in priority]
    n = len(rest)
    return set(priority + [rest[(offset + i) % n] for i in range(min(limit - len(priority), n))])


async def binance_stream(emit):
    async with websockets.connect(
        "wss://data-stream.binance.vision/ws/!miniTicker@arr", ping_interval=20, max_size=8 * 1024 * 1024
    ) as ws:
        async for raw in ws:
            for tick in json.loads(raw):
                emit("CRYPTO:" + tick["s"], tick["c"], tick["E"] / 1000, "binance")


async def alpaca_stream(emit, desired):
    if not settings.alpaca_key:
        raise ValueError("Alpaca credentials not configured")
    async with websockets.connect("wss://stream.data.alpaca.markets/v2/iex") as ws:
        await ws.send(
            json.dumps({"action": "auth", "key": settings.alpaca_key, "secret": settings.alpaca_secret})
        )
        active = set()
        authenticated = False
        last_change = 0
        while True:
            if authenticated and time.monotonic() - last_change >= 60:
                target = desired()
                remove, add = active - target, target - active
                if remove:
                    await ws.send(json.dumps({"action": "unsubscribe", "trades": sorted(remove)}))
                    # Wait for the server's subscription acknowledgement before adding new slots.
                    while True:
                        messages = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                        for msg in messages:
                            if msg["T"] == "error":
                                raise ValueError(f"Alpaca error {msg.get('code')}")
                            if msg["T"] == "t":
                                emit(
                                    "US:" + msg["S"],
                                    msg["p"],
                                    datetime.fromisoformat(msg["t"].replace("Z", "+00:00")).timestamp(),
                                    "alpaca-iex",
                                )
                        if any(m["T"] == "subscription" for m in messages):
                            break
                if add:
                    await ws.send(json.dumps({"action": "subscribe", "trades": sorted(add)}))
                active = target
                SUBSCRIPTIONS.set(len(active))
                last_change = time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except TimeoutError:
                continue
            for tick in json.loads(raw):
                if tick["T"] == "error":
                    raise ValueError(f"Alpaca error {tick.get('code')}")
                if tick["T"] == "success" and tick.get("msg") == "authenticated":
                    authenticated = True
                if tick["T"] == "t":
                    stamp = datetime.fromisoformat(tick["t"].replace("Z", "+00:00")).timestamp()
                    emit("US:" + tick["S"], tick["p"], stamp, "alpaca-iex")
