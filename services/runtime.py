import asyncio
import contextlib
import logging
import math
import time
import uuid
from decimal import Decimal
from collections import defaultdict, deque

import psutil
import redis.asyncio as redis
from sqlalchemy import delete, select, text

from libs.config import settings
from libs.db import Asset, Control, Decision, Position, Session, Watch
from libs.metrics import AGE, CPU, DECISIONS, ERRORS, EVENTS, HEALTH, LOOP, MEMORY, ORDERS
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

    def emit(self, aid, price, timestamp, source):
        if aid not in self.catalog:
            return
        price = float(price)
        now = time.time()
        if not math.isfinite(price) or price <= 0 or not math.isfinite(timestamp) or timestamp > now + 10:
            return
        prior = self.quotes.get(aid)
        if prior and timestamp <= prior["timestamp"]:
            return
        self.quotes[aid] = dict(
            price=price,
            timestamp=timestamp,
            received=now,
            source=source,
            mode="replay" if source == "replay" else "live",
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
                asyncio.create_task(
                    self.supervise("alpaca", lambda: alpaca_stream(self.emit, self.desired_us))
                ),
            ]

    def reload_catalog(self):
        with Session() as db:
            self.catalog = {a.id: a for a in db.scalars(select(Asset).where(Asset.active.is_(True)))}

    async def refresh(self, market):
        try:
            rows = await discover(market)
            if not rows:
                raise ValueError("Empty catalog response; previous catalog retained")
            async with self.lock:
                with Session.begin() as db:
                    # US and Binance endpoints are complete snapshots. Saudi public pages may be partial.
                    if market != "KSA":
                        for a in db.scalars(select(Asset).where(Asset.market == market)):
                            a.active = False
                    for row in rows:
                        db.merge(Asset(**row))
                self.reload_catalog()
            self.status[f"catalog_{market}"] = {
                "ok": True,
                "count": len(rows),
                "updated": time.time(),
                "coverage": "unverified" if market == "KSA" else "provider active universe",
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
                        for aid in watched:
                            q = self.quotes.get(aid)
                            fresh = bool(q and time.time() - q["received"] <= 15)
                            if q and q["source"] != "replay":
                                fresh = fresh and time.time() - q["timestamp"] <= 15
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
                        if time.time() - quote["received"] <= 15:
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
