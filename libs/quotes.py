"""Single freshness policy shared by signals, the broker and the UI."""

import time

# (allowed source age, allowed transport age, display label).
# Public stock snapshots may be delayed; these are simulation tolerances, not SLAs.
POLICIES = {
    "replay": (15, 15, "Replay"),
    "binance": (15, 15, "Streaming"),
    "alpaca-iex": (15, 15, "Streaming · IEX only"),
    "yahoo-public": (120, 120, "Public snapshot · delay may vary"),
    "mubasher-delayed": (1020, 120, "Delayed 15 min"),
}


def quote_info(quote, now=None):
    now = time.time() if now is None else now
    if not quote:
        return {"fresh": False, "label": "Waiting for source", "age": None, "event_age": None}
    source = quote["source"]
    source_limit, transport_limit, label = POLICIES.get(source, (15, 15, "Unverified source"))
    age = max(0, now - quote["received"])
    checked_age = max(0, now - quote.get("checked", quote["received"]))
    event_age = max(0, now - quote["timestamp"])
    event_fresh = age <= 15 if source == "replay" else event_age <= source_limit
    fresh = checked_age <= transport_limit and event_fresh
    if quote.get("market_open") is False:
        fresh = False
        label += " · market closed"
    elif not fresh:
        label += " · stale"
    return {"fresh": fresh, "label": label, "age": age, "event_age": event_age, "checked_age": checked_age}
