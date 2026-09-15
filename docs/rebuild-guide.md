# Your later manual rebuild

This repository is the complete reference to study. Rebuild it separately in these learning checkpoints rather than modifying away your working reference.

1. **Domain model:** write normalized assets, event timestamps, virtual wallets and decimal accounting. Reproduce broker tests without a web server.
2. **Replay:** load a tiny three-market CSV; implement the one-second clock and prove stale-price rejection and EOF behavior.
3. **FastAPI:** expose watchlists, a state snapshot, paper orders and the kill switch. Add idempotency and API tests.
4. **React:** build asset search and the watch table, then connect WebSocket snapshots and the paper-order form.
5. **PostgreSQL:** persist ledger state, restart the app and verify unchanged balances. Learn transaction boundaries and migrations.
6. **Redis:** add expiring caches/pub-sub and prove cache failure does not corrupt the ledger or block the engine.
7. **Providers:** add Binance discovery/streaming, then Alpaca universe discovery and bounded dynamic subscriptions. Treat source limits as explicit constraints.
8. **Saudi data:** import a complete allowed catalog and replay a permitted dataset. Keep source provenance and coverage visible.
9. **Signals and AI:** add the deterministic moving-average rule, then local explanations. Prove AI output cannot execute orders.
10. **Automatic simulation:** enable a bounded consumer of strategy decisions and run all risk checks through the same broker.
11. **Observability:** add latency, error, event and health metrics; make Grafana explain failures you intentionally introduce.
12. **Containers:** build API/frontend images, add Compose dependency readiness, volumes and local-only access.
13. **VMware/K3s:** load local images, create Secrets, bind PVCs, use probes and expose only through local forwarding.
14. **CI and portfolio:** run tests/builds automatically; record a short demonstration showing failure handling as well as the happy path.

For each checkpoint, explain the behavior first, write the smallest working implementation, run a concrete verification, and compare it with the reference. Useful portfolio evidence includes an architecture diagram, a replay demo, passing CI, Grafana during a provider outage, and a DB restart that preserves virtual positions. Avoid profitability claims based on the synthetic fixture.
