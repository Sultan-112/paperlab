from decimal import Decimal

import pytest

from providers.history import parse_history
from services.evaluation import evaluate, simulate, validate_bars
from services.strategy import automatic_quantity


def bars(n=200):
    return [{"timestamp": 1700000000 + i * 86400, "open": 100 + i, "close": 100 + i} for i in range(n)]


def test_single_entry_survives_repeated_signals_and_held_state():
    assert automatic_quantity("BUY", 100, Decimal(0)) == 1
    assert automatic_quantity("BUY", 100, Decimal(1)) == 0
    assert automatic_quantity("SELL", 100, Decimal("2.5")) == Decimal("2.5")
    assert automatic_quantity("HOLD", 100, Decimal(1)) == 0
    result = simulate(bars(), 20, 150, "single")
    assert result["fills"] == 1
    assert simulate(bars(), 20, 150, "repeated")["fills"] > 1


def test_cost_accounting_on_flat_market():
    data = [{**b, "open": 100, "close": 100} for b in bars()]
    r = simulate(data, 20, 150, "hold")
    expected = 899.9 + 100 / 1.0005 * 0.9995 * 0.999
    assert r["ending_equity"] == pytest.approx(expected)
    assert r["fees_paid"] == pytest.approx(0.1)
    assert r["net_pnl"] < 0
    assert simulate(data, 20, 150, "hold", fee=0, slippage=0)["net_pnl"] == 0


def test_next_open_and_no_future_leakage():
    data = bars()
    changed = [dict(b) for b in data]
    changed[20]["open"] = 500
    r = simulate(changed, 20, 150, "single")
    assert r["trades"][0]["price"] == pytest.approx(500 * 1.0005)
    for b in changed[100:]:
        b["close"] *= 10
        b["open"] *= 10
    original = simulate(data, 20, 150, "single")
    altered = simulate(changed, 20, 150, "single")
    # Only the intentionally changed first fill may differ before the future mutation.
    changed[20]["open"] = data[20]["open"]
    altered = simulate(changed, 20, 150, "single")
    assert original["curve"][:80] == altered["curve"][:80]


def test_validation_independent_cash_and_development_unchanged():
    data = bars()
    report = evaluate(data, "US:TEST", "fixture")
    assert report["segments"]["development"]["end"] < report["segments"]["validation"]["start"]
    for b in data[140:]:
        b["close"] *= 2
    updated = evaluate(data, "US:TEST", "fixture")
    assert updated["segments"]["development"] == report["segments"]["development"]
    assert report["segments"]["validation"]["results"]["hold"]["fills"] == 1


def test_sell_and_loss_drawdown():
    data = bars()
    for i in range(80, 200):
        data[i]["open"] = data[i]["close"] = 100 - (i - 80) * 0.5
    r = simulate(data, 20, 200, "single")
    assert [t["side"] for t in r["trades"]] == ["BUY", "SELL"]
    assert r["closed_sells"] == 1
    assert r["max_drawdown_pct"] > 0


@pytest.mark.parametrize("bad", ["duplicate", "nan", "short"])
def test_invalid_history(bad):
    data = bars()
    if bad == "duplicate":
        data[2]["timestamp"] = data[1]["timestamp"]
    elif bad == "nan":
        data[2]["close"] = float("nan")
    else:
        data = data[:50]
    with pytest.raises(ValueError):
        validate_bars(data)


def test_history_excludes_incomplete_bar_and_rejects_splits():
    row = {"timestamp": [100, 200000], "indicators": {"quote": [{"open": [10, 20], "close": [11, 21]}]}}
    payload = {"chart": {"result": [row]}}
    assert len(parse_history(payload, 210000)) == 1
    row["events"] = {"splits": {"x": {}}}
    with pytest.raises(ValueError, match="split"):
        parse_history(payload, 210000)
