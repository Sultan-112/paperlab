import time
from decimal import Decimal

from sqlalchemy import select

from libs.db import Asset, Control, Position, Trade, Wallet

D = Decimal
FEE = D("0.001")
SLIPPAGE = D("0.0005")


def execute(db, asset_id, side, quantity, order_id, quote, mode):
    """Only local ledger writes. Caller serializes requests; wallet row lock protects DB transactions."""
    prior = db.get(Trade, order_id)
    if prior:
        if (prior.asset_id, prior.side, prior.quantity) != (asset_id, side, quantity):
            raise ValueError("Idempotency key already used for a different order")
        return prior
    if db.get(Control, "kill_switch").value == "true":
        raise ValueError("Paper trading is paused by the kill switch")
    if side not in {"BUY", "SELL"} or not quantity.is_finite() or quantity <= 0:
        raise ValueError("Invalid side or quantity")
    asset = db.get(Asset, asset_id)
    if not asset or not asset.active:
        raise ValueError("Unknown or inactive asset")
    if not quote or time.time() - quote["received"] > 15:
        raise ValueError("No fresh quote; wait for a new market event")
    if quote["mode"] != mode:
        raise ValueError("Replay and live-data wallets cannot mix")
    if quote["source"] != "replay" and time.time() - quote["timestamp"] > 15:
        raise ValueError("Provider quote is stale")
    wallet_id = f"{mode}:{asset.market}:{asset.currency}"
    wallet = db.scalar(select(Wallet).where(Wallet.id == wallet_id).with_for_update())
    if not wallet:
        wallet = Wallet(id=wallet_id, cash=D("100000"), initial=D("100000"), realized=D("0"))
        db.add(wallet)
        db.flush()
    pid = f"{wallet_id}:{asset_id}"
    pos = db.get(Position, pid)
    if not pos:
        pos = Position(id=pid, wallet_id=wallet_id, asset_id=asset_id, quantity=D(0), average=D(0))
        db.add(pos)
    price = D(str(quote["price"])) * (1 + SLIPPAGE if side == "BUY" else 1 - SLIPPAGE)
    notional = price * quantity
    fee = notional * FEE
    if side == "BUY":
        if notional > wallet.initial * D("0.1"):
            raise ValueError("Maximum order size is 10% of initial virtual capital")
        if (pos.quantity + quantity) * price > wallet.initial * D("0.25"):
            raise ValueError("Maximum position size is 25% of initial virtual capital")
        if wallet.realized < -wallet.initial * D("0.05"):
            raise ValueError("Realized loss limit reached (5% of initial capital)")
        if notional + fee > wallet.cash:
            raise ValueError("Insufficient virtual balance")
        pos.average = (pos.average * pos.quantity + notional + fee) / (pos.quantity + quantity)
        pos.quantity += quantity
        wallet.cash -= notional + fee
    else:
        if quantity > pos.quantity:
            raise ValueError("Short selling is disabled")
        wallet.cash += notional - fee
        wallet.realized += notional - fee - pos.average * quantity
        pos.quantity -= quantity
        if pos.quantity == 0:
            pos.average = D(0)
    trade = Trade(
        id=order_id,
        asset_id=asset_id,
        wallet_id=wallet_id,
        side=side,
        quantity=quantity,
        price=price,
        fee=fee,
        timestamp=time.time(),
        source=quote["source"],
    )
    db.add(trade)
    db.flush()
    return trade
