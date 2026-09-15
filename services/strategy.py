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
