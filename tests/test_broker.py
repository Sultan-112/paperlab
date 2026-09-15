import time
from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from libs.db import Asset, Base, Control, Position, Trade, Wallet
from services.broker import execute


@pytest.fixture
def db(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "test.db"))
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as s:
        s.add_all(
            [
                Control(id="kill_switch", value="false"),
                Asset(id="US:AAPL", market="US", symbol="AAPL", name="Apple", currency="USD", source="test"),
            ]
        )
        s.commit()
        yield s
    engine.dispose()


def fill(db, side="BUY", quantity="10", order_id="test-order-1", price=100, **updates):
    quote = dict(price=price, received=time.time(), timestamp=time.time(), mode="replay", source="replay")
    quote.update(updates)
    result = execute(db, "US:AAPL", side, D(quantity), order_id, quote, "replay")
    db.commit()
    return result


def test_buy_sell_accounting(db):
    fill(db)
    fill(db, side="SELL", quantity="10", order_id="test-order-2", price=110)
    wallet = db.get(Wallet, "replay:US:USD")
    assert wallet.cash > wallet.initial
    assert wallet.cash - wallet.initial == wallet.realized
    assert db.scalar(select(Position)).quantity == 0
    assert db.scalar(select(Position)).average == 0


def test_idempotent_retry(db):
    first = fill(db)
    second = fill(db)
    assert first.id == second.id
    assert len(list(db.scalars(select(Trade)))) == 1
    assert db.scalar(select(Position)).quantity == D("10")
    with pytest.raises(ValueError, match="different order"):
        fill(db, quantity="11")


@pytest.mark.parametrize(
    "updates,match",
    [
        ({"received": 0}, "fresh"),
        ({"mode": "live"}, "mix"),
        ({"timestamp": 0, "source": "alpaca-iex"}, "stale"),
    ],
)
def test_stale_and_mode_rejection(db, updates, match):
    with pytest.raises(ValueError, match=match):
        fill(db, **updates)


def test_short_and_size_limits(db):
    with pytest.raises(ValueError, match="Short"):
        fill(db, side="SELL")
    db.rollback()
    with pytest.raises(ValueError, match="order size"):
        fill(db, quantity="101")
    db.rollback()
    fill(db, quantity="90")
    fill(db, quantity="90", order_id="test-order-2")
    with pytest.raises(ValueError, match="position size"):
        fill(db, quantity="90", order_id="test-order-3")


def test_kill_switch(db):
    db.get(Control, "kill_switch").value = "true"
    db.commit()
    with pytest.raises(ValueError, match="kill switch"):
        fill(db)


@pytest.mark.parametrize("q", ["NaN", "Infinity", "0", "-1"])
def test_bad_quantity(db, q):
    with pytest.raises(ValueError):
        fill(db, quantity=q)


def test_insufficient_funds_and_loss_gate(db):
    fill(db)
    wallet = db.get(Wallet, "replay:US:USD")
    wallet.cash = D("0")
    db.commit()
    with pytest.raises(ValueError, match="Insufficient"):
        fill(db, order_id="second-order")
    db.rollback()
    wallet = db.get(Wallet, "replay:US:USD")
    wallet.realized = D("-6000")
    db.commit()
    with pytest.raises(ValueError, match="loss limit"):
        fill(db, order_id="third-order")
