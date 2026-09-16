# Strategy evaluation

Use **Does the strategy beat holding?** on the dashboard. Select a watched asset in the signal panel, then Evaluate. The endpoint is authenticated, read-only and never changes wallets or places orders. Successful reports are cached for ten minutes. No strategy is automatically selected from results.

## Method

- Fetch up to two years of completed daily OHLC data from the free public Yahoo chart endpoint. US and Saudi symbols are supported subject to availability. BTCUSDT/ETHUSDT use explicitly labeled Yahoo USD proxies, not Binance execution data. Other assets support offline CSV input.
- Keep the original fixed 5/20-observation average rule and 0.2% threshold. Compare repeated entries, one entry while flat/full exit, and buy-and-hold. No optimized parameters.
- Chronological 70/30 development/validation split. Each segment starts independently with 1,000 virtual quote-currency units, using prior bars only for indicator warmup. No position transfers across the boundary.
- Signals formed from prior closes execute at the following bar's open. Charge 0.1% fees and 0.05% adverse slippage each side. Ending equity includes estimated liquidation costs, even if the position is open. Fees paid excludes that estimated final liquidation fee.
- Each entry invests 100 units; repeated entries can accumulate up to a 250-unit position. Buy-and-hold invests 100 units and leaves the rest in cash. Returns and drawdowns use the whole 1,000-unit account. The policies therefore have different exposure; this is not a risk-matched comparison or the entire live broker risk model.
- Daily repeated entries are a research proxy, not a reproduction of once-per-minute live orders. Daily bars cannot validate the live strategy, whose observations arrive at irregular source-dependent intervals.
- Price-only analysis excludes dividends, taxes and financing. Histories with reported stock splits are rejected instead of silently introducing split-related signals. CSV users must supply consistent, verified bars.
- Selected symbols, one historical split and assumed trading costs do not establish a profitable trading advantage. Reusing validation to revise a strategy makes that period development data; a fresh forward test is then needed.

## Local commands

```powershell
python -m scripts.evaluate --asset US:NVDA --output data/research/nvda.json
python -m scripts.evaluate --asset KSA:2222 --output data/research/aramco.json
python -m scripts.evaluate --asset CRYPTO:ETHUSDT --output data/research/eth.json
python -m scripts.evaluate --asset US:EXAMPLE --csv data/imports/daily.csv --output data/research/custom.json
```

CSV columns: `timestamp,open,close`. UTC Unix seconds, unique ascending timestamps, positive finite prices and at least 120 completed daily bars. Research reports include trade ledgers and equity curves; a `.bars.json` companion preserves the exact input. Local research downloads are gitignored.

## Automatic paper-order change

Automatic BUY now opens one approximately 100-unit position only when flat. Further BUY signals do not add to an existing holding, even after a restart. SELL closes the entire existing position, including a position accumulated before this change or opened manually. Broker risk limits still apply. Existing balances and history are preserved. This change controls repeated exposure; it is not a claim of better returns. No new stop-loss or profit target is implied.

## Initial real-data results

Completed September 16, 2026. Validation net account returns after assumed costs:

| Asset | Repeated daily entries | One entry / full exit | Buy and hold |
|---|---:|---:|---:|
| NVDA | +0.318% | -0.384% | +1.482% |
| ETH USD proxy | +0.806% | +1.181% | +1.442% |
| Saudi Aramco 2222 | +0.637% | +0.247% | -0.069% |

The one-entry policy underperformed holding in two of three samples. Aramco excludes dividends, so its comparison is not a total-return comparison. These results do not justify calling the strategy profitable or superior. Next research work should collect regular intraday bars, evaluate an unchanged policy on a fresh forward period and compare exposure consistently across a broader predefined universe.
