"""Research-only daily-bar evaluation. Never submits orders or modifies wallets."""

import math
from datetime import datetime, timezone

from services.strategy import recommend


def validate_bars(bars):
    if len(bars) < 120:
        raise ValueError("At least 120 completed daily bars are required")
    previous = -1
    for bar in bars:
        if not all(math.isfinite(bar[k]) and bar[k] > 0 for k in ("timestamp", "open", "close")):
            raise ValueError("Bar values must be finite and positive")
        if bar["timestamp"] <= previous:
            raise ValueError("Bars must have unique ascending timestamps")
        previous = bar["timestamp"]


def simulate(bars, start, end, policy, fee=0.001, slippage=0.0005):
    """Prior close signal -> next open fill. Independent cash at each segment."""
    if policy not in {"repeated", "single", "hold"}:
        raise ValueError("Unknown policy")
    if not (0 <= fee < 1 and 0 <= slippage < 1):
        raise ValueError("Invalid costs")
    cash, held, cost = 1000.0, 0.0, 0.0
    peak, drawdown, fees, turnover = cash, 0.0, 0.0, 0.0
    trades, round_trips, wins, exposed = [], 0, 0, 0
    curve = []

    def fill(side, quantity, bar, reason):
        nonlocal cash, held, cost, fees, turnover, round_trips, wins
        price = bar["open"] * (1 + slippage if side == "BUY" else 1 - slippage)
        value = quantity * price
        charge = value * fee
        if side == "BUY":
            if value + charge > cash or (held + quantity) * price > 250:
                return
            cash -= value + charge
            cost += value + charge
            held += quantity
        else:
            basis = cost * quantity / held
            cash += value - charge
            cost -= basis
            held -= quantity
            round_trips += 1
            wins += value - charge > basis
        fees += charge
        turnover += value
        trades.append(
            {
                "timestamp": bar["timestamp"],
                "side": side,
                "price": price,
                "quantity": quantity,
                "fee": charge,
                "reason": reason,
            }
        )

    for i in range(start, end):
        bar = bars[i]
        action, reason = recommend([b["close"] for b in bars[max(0, i - 20) : i]])
        if policy == "hold":
            action, reason = ("BUY", "Buy-and-hold benchmark") if i == start else ("HOLD", "")
        if action == "BUY" and (policy == "repeated" or held < 1e-10):
            fill("BUY", 100 / (bar["open"] * (1 + slippage)), bar, reason)
        elif action == "SELL" and held > 1e-10:
            quantity = min(held, 100 / (bar["open"] * (1 - slippage))) if policy == "repeated" else held
            fill("SELL", quantity, bar, reason)
        # Equity includes the estimated fee/slippage to liquidate open holdings.
        equity = cash + held * bar["close"] * (1 - slippage) * (1 - fee)
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
        exposed += held > 1e-10
        curve.append({"timestamp": bar["timestamp"], "equity": round(equity, 6)})
    return {
        "return_pct": (equity / 1000 - 1) * 100,
        "net_pnl": equity - 1000,
        "max_drawdown_pct": drawdown * 100,
        "fees_paid": fees,
        "turnover": turnover,
        "fills": len(trades),
        "closed_sells": round_trips,
        "win_rate_pct": wins / round_trips * 100 if round_trips else None,
        "exposure_pct": exposed / (end - start) * 100,
        "ending_equity": equity,
        "curve": curve,
        "trades": trades,
    }


def evaluate(bars, asset, source):
    validate_bars(bars)
    split = int(len(bars) * 0.7)
    segments = {}
    for name, start, end in (("development", 20, split), ("validation", split, len(bars))):
        results = {policy: simulate(bars, start, end, policy) for policy in ("repeated", "single", "hold")}
        segments[name] = {
            "start": bars[start]["timestamp"],
            "end": bars[end - 1]["timestamp"],
            "bars": end - start,
            "results": results,
        }
    validation = segments["validation"]["results"]
    delta = validation["single"]["net_pnl"] - validation["hold"]["net_pnl"]
    return {
        "asset": asset,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bars": len(bars),
        "interval": "1d",
        "initial_capital": 1000,
        "entry_notional": 100,
        "fee_pct": 0.1,
        "slippage_pct": 0.05,
        "segments": segments,
        "validation_advantage": delta,
        "conclusion": "Single-entry policy "
        + ("outperformed" if delta > 0 else "did not outperform")
        + " the 100-unit buy-and-hold benchmark in this validation sample. No proven trading edge.",
        "limitations": [
            "Fixed 5/20-average rule with 0.2% threshold; no parameter search or automatic promotion.",
            "Daily bars differ from the live irregular-observation strategy. This does not validate live profitability.",
            "Validation is the last 30% of bars. It becomes development data if used to revise the strategy.",
            "Each segment starts with 1,000 units cash; entries and benchmark invest 100 units. Repeated policy can hold up to 250.",
            "Signals use previous closes; fills use the next open. Endpoint equity includes estimated exit costs.",
            "Price-only results exclude dividends, taxes and spread beyond assumed slippage; bars with reported splits are rejected.",
            "Selected-symbol, single-period results have selection bias and are not a full-universe portfolio test.",
        ],
    }
