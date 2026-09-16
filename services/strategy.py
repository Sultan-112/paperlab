def recommend(prices, fresh=True):
    if not fresh:
        return "HOLD", "Quote is stale or unavailable"
    if len(prices) < 20:
        return "HOLD", f"Warming up: {len(prices)}/20 distinct market observations"
    fast = sum(prices[-5:]) / 5
    slow = sum(prices[-20:]) / 20
    delta = fast / slow - 1
    if delta > 0.002:
        return "BUY", f"5-observation mean is {delta:.2%} above 20-observation mean"
    if delta < -0.002:
        return "SELL", f"5-observation mean is {-delta:.2%} below 20-observation mean"
    return "HOLD", "Moving averages are within the 0.2% neutral band"


def automatic_quantity(action, price, held):
    """One small entry while flat; close the position on SELL. No pyramiding."""
    from decimal import Decimal

    if action == "BUY" and held == 0:
        return (Decimal("100") / Decimal(str(price))).quantize(Decimal("0.00000001"))
    if action == "SELL" and held > 0:
        return held
    return Decimal(0)
