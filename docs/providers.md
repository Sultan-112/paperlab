# Providers, catalogs and replay

## Primary references

- [Nasdaq symbol directory definitions](https://nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs)
- [Mubasher Saudi prices and delay notice](https://english.mubasher.info/countries/SA/stock-prices)

These are integration references, not a promise that free access stays unchanged:

- [Alpaca plans and free stream limits](https://docs.alpaca.markets/us/docs/about-market-data-api)
- [Alpaca assets API](https://docs.alpaca.markets/us/reference/get-v2-assets-1)
- [Alpaca stock streaming protocol](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data)
- [Binance Spot streaming documentation](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams)
- [Binance market-data-only endpoints](https://developers.binance.com/docs/binance-spot-api-docs/faqs/market_data_only)
- [Saudi Exchange market-data services](https://www.saudiexchange.sa/wps/portal/saudiexchange/trading/market-services/market-information-services/market-data)
- [Saudi Exchange issuer directory](https://www.saudiexchange.sa/wps/portal/saudiexchange/trading/participants-directory/issuer-directory?locale=en)

## US

Without credentials, discovery downloads both public Nasdaq Trader symbol directories and excludes test listings. The catalog includes listed instruments beyond common shares and ETFs; it does not guarantee OTC coverage or a price for every symbol. Public Yahoo chart snapshots update watched and held US symbols with a target interval of 15 seconds, with at least one second between requests. Larger watchlists take longer. HTTP 429/403 trigger global backoff; provider timestamps remain unchanged when a poll returns the same observation. This undocumented public endpoint has no availability or real-time guarantee. Closed-session and old observations are marked stale.

With optional Alpaca credentials, the following alternative applies:


Discovery requests all active `us_equity` assets from the free account's assets endpoint, including equities and ETFs, without a hard-coded symbol list. The complete endpoint response replaces active flags for that market. Listings missing from a successful refresh become inactive; failed refreshes retain the last successful list.

The stream connects to IEX, not SIP. Free coverage is exchange-limited and usually sparse outside market sessions. Held positions are pinned first; watchlist symbols use remaining slots. Oversubscribed watchlists rotate. Remaining free slots rotate through the universe. At most 30 requested subscriptions are sent; configure a lower limit through `US_STREAM_LIMIT`. Unsubscribe acknowledgement precedes new subscriptions. One connection is supervised with capped exponential reconnect backoff.

With more than 30 held US symbols, the first 30 receive priority and other quotes can become stale. The UI exposes ages and the broker rejects stale fills. Watching the full US catalog simultaneously is not possible within the free plan.

## Binance

Discovery reads all `TRADING` Spot pairs from `exchangeInfo`. The all-market mini-ticker stream emits changed symbol updates at its documented cadence. Mini-ticker close values are indicative observations, not executable bid/ask quotes. Each pair uses its actual quote currency; currencies are never assumed to be USDT.

Public endpoints may be inaccessible in some regions or networks. The adapter reports/retries errors; it does not circumvent provider restrictions. Catalog refresh is daily and can be requested manually. Newly listed symbols become eligible after a successful catalog refresh.

## Saudi catalog

By default, the public Mubasher Saudi price endpoint supplies the catalog and prices. The app polls once every 60 seconds; the source advertises a 15-minute delay. Numeric TDWL codes of 4�8 digits are retained, including funds, debt and older entries. This is not a verified complete list of currently active Saudi stocks. Per-row timestamps are preserved; naive `updatedAt` values are interpreted as UTC, consistent with observed Saudi session times, but the payload does not declare a timezone. Old records are displayed as stale. The public endpoint may change or become unavailable.

If that catalog request fails, the fallback adapter scans links carrying `companySymbol` or numeric `symbol` parameters on main-market, Nomu, debt, fund and issuer-directory pages. This is best-effort discovery, not a guaranteed stable exchange API. Page routing or rendering may change; an HTTP error or empty result is not treated as success. Successful public scraping still has unverified completeness.

To import every row in a freely obtained catalog, save this UTF-8 CSV to `data/imports/ksa.csv`:

```csv
symbol,name
2222,Saudi Arabian Oil Co.
1120,Al Rajhi Bank
```

The example above only illustrates the format. Supply the full current list you obtained, including Nomu/funds/debt rows if required and present in that source. `.SR` suffixes are normalized. Numeric symbols of 4–8 digits are accepted. The importer validates every row and ingests the complete file rather than taking a fixed subset. Record source URL, download date, market sections and expected row count in your private import notes; compare those with the refresh count. Imported records are not automatically delisted on absence because source completeness cannot be inferred.

Then click **KSA → Refresh KSA catalog**. The file takes priority over public discovery. Imports are not committed. Public delayed quotes remain available for matching symbols. Replay supports historical or synthetic observations for any imported asset; true real-time Saudi prices are not provided.

## Replay for any discovered or imported market

File columns:

```csv
timestamp,market,symbol,name,currency,price
1700000000,US,AAPL,Apple,USD,190.50
1700000000,KSA,2222,Saudi Aramco,SAR,32.10
1700000001,CRYPTO,BTCUSDT,Bitcoin / USDT,USDT,40000
```

- Timestamps are Unix UTC seconds, globally ascending (ties allowed across symbols).
- Prices must be finite and positive. Same-symbol duplicate timestamps are ignored.
- `market` is `US`, `KSA` or `CRYPTO`. All rows need a symbol and quote currency.
- Store your file at `data/imports/my-replay.csv`; set `REPLAY_FILE=data/imports/my-replay.csv`, `DATA_MODE=replay`, and recreate the API.
- Replay registers assets present in the file automatically. Playback advances virtual event time every engine tick, supports pause and 0.1–100× speed, and stops at EOF. It never silently wraps or creates new prices at EOF.
- The broker freshness clock uses playback receipt time, allowing old historical timestamps in replay. Pausing for more than 15 seconds makes orders stale until playback produces another observation.
- The loader reads the file into memory; use bounded datasets in this learning version. Bulk historical downloads are intentionally not assumed to be free or licensed; supply your own permitted data.

The bundled hour-long fixture is synthetic and uses just six symbols across the three markets. It is intended for reproducible UI/strategy demonstrations, not return comparisons or evidence of market-wide catalog coverage.
