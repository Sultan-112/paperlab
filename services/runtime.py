import asyncio
import contextlib
import logging
import math
import time
import uuid
from decimal import Decimal
from collections import defaultdict, deque

import psutil
import httpx
import redis.asyncio as redis
from sqlalchemy import delete, select, text

from libs.config import settings
from libs.db import Asset, Control, Decision, Position, Session, Watch
from libs.metrics import AGE, CPU, DECISIONS, ERRORS, EVENTS, HEALTH, LOOP, MEMORY, ORDERS
from libs.quotes import quote_info
from providers.public_data import public_client, retry_seconds, saudi_snapshot, saudi_ticks, us_snapshot
from providers.catalog import asset, discover
from providers.replay import load_replay
from providers.streams import alpaca_stream, binance_stream, choose_us
from services.strategy import recommend
from services.broker import execute

log = logging.getLogger("paperlab")


class Runtime:
    def __init__(self):
        self.quotes = {}
        self.history = defaultdict(lambda: deque(maxlen=20))
        self.decisions = {}
        self.catalog = {}
        self.status = {}
        self.tasks = []
        self.lock = asyncio.Lock()
        self.redis = redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        self.replay_rows = []
        self.cursor = 0
        self.replay_clock = 0.0
        self.replay_paused = False
        self.replay_speed = 1.0
        self.last_tick = 0.0
        self.last_auto = {}
        self.process = psutil.Process()
        self.us_due = {}
        self.us_attempt = {}
        self.refresh_locks = {m: asyncio.Lock() for m in ["US", "KSA", "CRYPTO"]}
        self.catalog_updated = {}
        self.watch_snapshot = []

    def emit(self, aid, price, timestamp, source, **metadata):
        if aid not in self.catalog:
            return
        price = float(price)
        now = time.time()
        if not math.isfinite(price) or price <= 0 or not math.isfinite(timestamp) or timestamp > now + 10:
            return
        prior = self.quotes.get(aid)
        if prior and source == prior["source"]:
            if timestamp < prior["timestamp"]:
                return
            if timestamp == prior["timestamp"]:
                # A successful poll is a transport check, not a new observation.
                prior["checked"] = now
                prior.update(metadata)
                return
        elif prior:
            self.history[aid].clear()
        self.quotes[aid] = dict(
            price=price,
            timestamp=timestamp,
            received=now,
            source=source,
            mode="replay" if source == "replay" else "live",
            checked=now,
            **metadata,
        )
        self.history[aid].append(price)
        EVENTS.labels(aid.split(":")[0], source).inc()
        if source != "replay":
            provider = "alpaca" if source == "alpaca-iex" else source
            self.status[provider] = {"state": "receiving", "last_event": now}

    async def start(self):
        if settings.mode == "replay":
            self.replay_rows = load_replay(settings.replay_file)
            self.replay_clock = float(self.replay_rows[0]["timestamp"])
            with Session.begin() as db:
                for row in self.replay_rows:
                    aid = f"{row['market']}:{row['symbol']}"
                    if not db.get(Asset, aid):
                        db.add(
                            Asset(
                                **asset(
                                    row["market"],
                                    row["symbol"],
                                    row.get("name") or row["symbol"],
                                    row["currency"],
                                    "replay-fixture",
                                )
                            )
                        )
                        db.flush()
                for aid in sorted({f"{r['market']}:{r['symbol']}" for r in self.replay_rows}):
                    if not db.get(Watch, aid):
                        db.add(Watch(asset_id=aid, added=time.time()))
        self.reload_catalog()
        self.tasks.append(asyncio.create_task(self.loop()))
        self.tasks.append(asyncio.create_task(self.cache_loop()))
        if settings.mode == "live":
            self.tasks += [
                asyncio.create_task(self.catalog_loop()),
                asyncio.create_task(self.supervise("binance", lambda: binance_stream(self.emit))),
                asyncio.create_task(self.saudi_loop()),
            ]
            if settings.alpaca_key and settings.alpaca_secret:
                self.tasks.append(
                    asyncio.create_task(
                        self.supervise("alpaca", lambda: alpaca_stream(self.emit, self.desired_us))
                    )
                )
            else:
                self.tasks.append(asyncio.create_task(self.us_public_loop()))
                self.status["alpaca"] = {
                    "state": "optional",
                    "message": "No keys needed for public snapshots. Free Alpaca keys enable IEX streaming.",
                }

    def reload_catalog(self):
        with Session() as db:
            self.catalog = {a.id: a for a in db.scalars(select(Asset).where(Asset.active.is_(True)))}

    async def refresh(self, market):
        if self.refresh_locks[market].locked():
            return {"ok": True, "message": "Catalog refresh already running"}
        if time.time() - self.catalog_updated.get(market, 0) < 60:
            return self.status.get(
                f"catalog_{market}", {"ok": True, "message": "Using recently refreshed catalog"}
            )
        async with self.refresh_locks[market]:
            return await self._refresh(market)

    async def _refresh(self, market):
        self.catalog_updated[market] = time.time()
        try:
            rows = await discover(market)
            if not rows:
                raise ValueError("Empty catalog response; previous catalog retained")
            async with self.lock:
                with Session.begin() as db:
                    # US and Binance endpoints are complete snapshots. Saudi public pages may be partial.
                    existing = {a.id: a for a in db.scalars(select(Asset).where(Asset.market == market))}
                    if market != "KSA":
                        for a in existing.values():
                            a.active = False
                    for row in rows:
                        if row["id"] in existing:
                            for key, value in row.items():
                                setattr(existing[row["id"]], key, value)
                        else:
                            db.add(Asset(**row))
                    seed_key = "watch_seed_" + market
                    if settings.mode == "live" and not db.get(Control, seed_key):
                        defaults = {
                            "US": ["AAPL", "MSFT", "NVDA", "SPY"],
                            "KSA": ["2222", "1120"],
                            "CRYPTO": ["BTCUSDT", "ETHUSDT"],
                        }
                        ids = {r["id"] for r in rows}
                        for symbol in defaults[market]:
                            aid = market + ":" + symbol
                            if aid in ids and not db.get(Watch, aid):
                                db.add(Watch(asset_id=aid, added=time.time()))
                        db.add(Control(id=seed_key, value="true"))
                self.reload_catalog()
            self.status[f"catalog_{market}"] = {
                "ok": True,
                "count": len(rows),
                "updated": time.time(),
                "coverage": "unverified" if market == "KSA" else "provider active universe",
                "source": rows[0]["source"],
            }
        except Exception as exc:
            ERRORS.labels("catalog_" + market).inc()
            self.status[f"catalog_{market}"] = {
                "ok": False,
                "error": type(exc).__name__,
                "message": str(exc)
                if isinstance(exc, ValueError)
                else "Provider unavailable; previous catalog retained",
            }
        return self.status[f"catalog_{market}"]

    async def catalog_loop(self):
        while True:
            await asyncio.gather(*(self.refresh(m) for m in ["US", "CRYPTO", "KSA"]))
            await asyncio.sleep(86400)

    async def us_public_loop(self):
        backoff = 60
        async with public_client() as client:
            while True:
                ids = [aid for aid in self.watch_snapshot if aid.startswith("US:") and aid in self.catalog]
                aid = min(ids, key=lambda x: self.us_due.get(x, 0)) if ids else None
                if not aid or self.us_due.get(aid, 0) > time.time():
                    await asyncio.sleep(1)
                    continue
                now = time.time()
                self.us_attempt[aid] = now
                self.us_due[aid] = now + settings.stock_poll_seconds
                try:
                    tick = await us_snapshot(client, self.catalog[aid].symbol, now)
                    if tick["currency"] != self.catalog[aid].currency:
                        raise ValueError("Price currency does not match catalog")
                    if not self.history[aid]:
                        self.history[aid].extend(p for _, p in tick["history"])
                    self.emit(
                        aid,
                        tick["price"],
                        tick["timestamp"],
                        "yahoo-public",
                        market_open=tick["market_open"],
                        change_percent=tick["change_percent"],
                    )
                    self.status["yahoo-public"] = {
                        "state": "receiving",
                        "last_check": time.time(),
                        "message": "No-key public snapshots; timing is not guaranteed",
                        "target_interval": settings.stock_poll_seconds,
                    }
                    backoff = 60
                except httpx.HTTPStatusError as exc:
                    ERRORS.labels("yahoo-public").inc()
                    code = exc.response.status_code
                    if code in {429, 403}:
                        wait = retry_seconds(exc.response, backoff)
                        self.status["yahoo-public"] = {
                            "state": "backoff",
                            "http_status": code,
                            "retry_at": time.time() + wait,
                        }
                        await asyncio.sleep(wait)
                        backoff = min(backoff * 2, 900)
                    else:
                        self.us_due[aid] = time.time() + 300
                        self.status["yahoo-public"] = {"state": "partial", "asset": aid, "http_status": code}
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    ERRORS.labels("yahoo-public").inc()
                    self.us_due[aid] = time.time() + 60
                    self.status["yahoo-public"] = {
                        "state": "retrying",
                        "asset": aid,
                        "error": type(exc).__name__,
                    }
                # Global cap: at most one new request each second, even with many watched symbols.
                await asyncio.sleep(1)

    async def saudi_loop(self):
        backoff = settings.saudi_poll_seconds
        async with public_client() as client:
            while True:
                try:
                    payload = await saudi_snapshot(client)
                    accepted = 0
                    for tick in saudi_ticks(payload):
                        if tick[0] in self.catalog:
                            self.emit(*tick)
                            accepted += 1
                    self.status["mubasher-delayed"] = {
                        "state": "receiving",
                        "last_check": time.time(),
                        "count": accepted,
                        "delay_seconds": 900,
                        "message": "15-minute delayed public data; old records remain dated",
                    }
                    backoff = settings.saudi_poll_seconds
                except Exception as exc:
                    ERRORS.labels("mubasher-delayed").inc()
                    if isinstance(exc, httpx.HTTPStatusError):
                        backoff = retry_seconds(exc.response, backoff)
                    self.status["mubasher-delayed"] = {
                        "state": "backoff",
                        "error": type(exc).__name__,
                        "retry_at": time.time() + backoff,
                    }
                    backoff = max(60, backoff)
                await asyncio.sleep(backoff)
                if self.status["mubasher-delayed"]["state"] == "backoff":
                    backoff = min(backoff * 2, 900)

    async def supervise(self, name, run):
        delay = 2
        while True:
            started = time.monotonic()
            try:
                self.status[name] = {"state": "connecting"}
                await run()
            except Exception as exc:
                ERRORS.labels(name).inc()
                self.status[name] = {"state": "retrying", "error": type(exc).__name__}
                log.warning("provider_reconnect provider=%s error=%s", name, type(exc).__name__)
            if time.monotonic() - started > 60:
                delay = 2
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    def desired_us(self):
        with Session() as db:
            watched = [
                w.asset_id[3:]
                for w in db.scalars(select(Watch).order_by(Watch.added))
                if w.asset_id.startswith("US:") and w.asset_id in self.catalog
            ]
            held = [
                p.asset_id[3:]
                for p in db.scalars(select(Position).where(Position.quantity > 0))
                if p.asset_id.startswith("US:")
                and p.wallet_id.startswith("live:")
                and p.asset_id in self.catalog
            ]
        return choose_us(
            watched,
            held,
            sorted(a.symbol for a in self.catalog.values() if a.market == "US"),
            int(time.time() // 60) * settings.us_limit,
            settings.us_limit,
        )

    async def loop(self):
        while True:
            started = time.monotonic()
            try:
                async with self.lock:
                    if settings.mode == "replay" and not self.replay_paused:
                        while self.cursor < len(self.replay_rows):
                            row = self.replay_rows[self.cursor]
                            if float(row["timestamp"]) > self.replay_clock:
                                break
                            self.emit(
                                f"{row['market']}:{row['symbol']}",
                                row["price"],
                                float(row["timestamp"]),
                                "replay",
                            )
                            self.cursor += 1
                        self.replay_clock += self.replay_speed
                    with Session.begin() as db:
                        watched = [w.asset_id for w in db.scalars(select(Watch))]
                        held = [
                            p.asset_id
                            for p in db.scalars(
                                select(Position).where(
                                    Position.quantity > 0, Position.wallet_id.like(settings.mode + ":%")
                                )
                            )
                        ]
                        self.watch_snapshot = list(dict.fromkeys(watched + held))
                        for aid in watched:
                            q = self.quotes.get(aid)
                            fresh = quote_info(q)["fresh"]
                            action, reason = recommend(list(self.history[aid]), fresh)
                            previous = self.decisions.get(aid)
                            self.decisions[aid] = dict(action=action, reason=reason, timestamp=time.time())
                            if (
                                not previous
                                or previous["action"] != action
                                or time.time() - previous.get("saved", 0) >= 60
                            ):
                                db.add(
                                    Decision(
                                        asset_id=aid, action=action, reason=reason, timestamp=time.time()
                                    )
                                )
                                DECISIONS.labels(action).inc()
                                self.decisions[aid]["saved"] = time.time()
                            else:
                                self.decisions[aid]["saved"] = previous.get("saved", 0)
                            if (
                                db.get(Control, "autopaper").value == "true"
                                and fresh
                                and action != "HOLD"
                                and time.time() - self.last_auto.get(aid, 0) >= 60
                            ):
                                self.last_auto[aid] = time.time()
                                a = self.catalog.get(aid)
                                if a:
                                    wallet_id = f"{settings.mode}:{a.market}:{a.currency}"
                                    position = db.get(Position, f"{wallet_id}:{aid}")
                                    # Small fixed quote-currency notional; full risk checks remain in the broker.
                                    qty = (Decimal("100") / Decimal(str(q["price"]))).quantize(
                                        Decimal("0.00000001")
                                    )
                                    if action == "SELL":
                                        qty = min(qty, position.quantity) if position else Decimal(0)
                                    if qty > 0:
                                        try:
                                            with db.begin_nested():
                                                execute(
                                                    db, aid, action, qty, str(uuid.uuid4()), q, settings.mode
                                                )
                                            ORDERS.labels("filled").inc()
                                        except ValueError:
                                            ORDERS.labels("rejected").inc()
                        db.execute(delete(Decision).where(Decision.timestamp < time.time() - 7 * 86400))
                    HEALTH.labels("db").set(1)
                self.last_tick = time.time()
                for market in ["US", "KSA", "CRYPTO"]:
                    received = [
                        q["received"] for aid, q in self.quotes.items() if aid.startswith(market + ":")
                    ]
                    AGE.labels(market).set(time.time() - max(received) if received else -1)
                CPU.set(self.process.cpu_percent())
                MEMORY.set(self.process.memory_info().rss)
            except Exception:
                HEALTH.labels("db").set(0)
                log.exception("engine_tick_failed")
            LOOP.observe(time.monotonic() - started)
            await asyncio.sleep(max(0.01, 1 - (time.monotonic() - started)))

    async def cache_loop(self):
        import json

        while True:
            try:
                async with self.redis.pipeline(transaction=False) as pipe:
                    pipe.set("paperlab:heartbeat", str(self.last_tick), ex=10)
                    for aid, quote in list(self.quotes.items()):
                        if quote_info(quote)["fresh"]:
                            pipe.set("paperlab:quote:" + aid, json.dumps(quote), ex=20)
                    pipe.publish("paperlab:decisions", json.dumps(self.decisions))
                    await pipe.execute()
                HEALTH.labels("redis").set(1)
            except Exception:
                HEALTH.labels("redis").set(0)
            await asyncio.sleep(1)

    async def health(self):
        result = {"engine": time.time() - self.last_tick < 5}
        try:
            with Session() as db:
                db.execute(text("SELECT 1"))
            result["db"] = True
        except Exception:
            result["db"] = False
        try:
            result["redis"] = bool(await self.redis.ping())
        except Exception:
            result["redis"] = False
        return result

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.redis.aclose()


runtime = Runtime()
