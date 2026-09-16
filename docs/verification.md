# Verification record

Environment: Windows local workspace, Python 3.12, Node 24, pnpm 11.19.0. Reference created September 16, 2026.

## Initial reference verification

Initial result: **24 tests passed**, Ruff passed, frontend TypeScript check and production build passed, and infrastructure structural checks passed.

- Python dependency installation into an isolated `.venv`.
- Backend tests: broker accounting, duplicate orders, short/size/funds/loss/kill-switch limits, stale data and mode isolation, input validation, stream allocation/rotation, event deduplication, replay validation, Saudi parser/import fixtures, REST authentication, WebSocket snapshots, Ollama fallback, automation controls, and the absence of a provider order-submission path.
- Ruff lint checks.
- React strict TypeScript check and Vite production build.
- YAML/JSON structure checks, loopback Compose port checks, one-replica K3s checks and Grafana dashboard validation.
- Running FastAPI with SQLite and the built frontend through a local preview server.
- Browser observation of streaming replay prices and signals, followed by a simulated buy that appeared in the wallet, position, P&L and trade-history UI.
- Corrected a dev/preview proxy Host-header mismatch discovered by that browser order test.
- Live Binance discovery returned 1,366 active Spot pairs across 27 quote currencies. A bounded WebSocket smoke check received updates for 74 distinct pairs through the provider adapter. These counts are a point-in-time observation, not fixed application limits.

## Free public-data extension

Verified September 16, 2026: 40 backend tests passed, Ruff passed, and frontend TypeScript and production build passed. Added tests cover public catalog parsing, source-specific freshness, unchanged observations, chart history, closed sessions, and retry limits.

The running local application discovered 13,204 US-listed instruments, 469 numeric Saudi entries, and 1,372 active Binance Spot pairs. Actual US snapshots, Saudi delayed observations and Binance streaming prices reached the dashboard. Counts are point-in-time and do not prove complete active-market coverage. The dashboard labels source delays, old quotes and market closure, and includes a scrolling recommendation bar and price-refresh control. No paid credentials were used. Real public feeds are now the default; replay remains selectable.

## Not verified in this environment

- Docker/Compose and Kubernetes/K3s execution: binaries/cluster are unavailable. CI includes a Docker build and PostgreSQL/Redis/API/frontend readiness smoke job, but CI has not run until the repository is pushed.
- Real PostgreSQL locking, persistence across actual container restarts, Grafana rendering, cAdvisor/pod metric collection and Helm installation. Static configuration checks do not establish runtime success.
- Successful local-model inference: Ollama is unavailable; the explicit fallback path was tested.
- Authenticated Alpaca catalog/stream behavior: no user credentials were provided. Allocation logic is covered by tests; an actual free-account session remains necessary.
- A complete current active Saudi asset catalog: public exchange access returned HTTP 403. Mubasher supplied 469 numeric entries, including older records; completeness against the exchange was not independently established. CSV import remains available.
- Sustained all-market Binance streaming or provider outages under load. These integrations require network access and provider availability at runtime.

## Known development-environment details

Vite's default config bundling encountered a Windows sandbox ancestor-directory access error. The project uses a native JavaScript config loader, and the production build succeeded. The dev dependency optimizer also encountered that sandbox restriction in this session; the built frontend was checked with `node node_modules/vite/bin/vite.js preview --configLoader native --host 127.0.0.1 --port 4173`. This is an environment limitation; the standard Vite dev workflow should be verified on the Linux lab.

Test dependencies emitted upstream Starlette/httpx and AnyIO deprecation warnings; tests still passed. `requirements.lock` pins the tested application dependency versions. Dev tool ranges remain in `pyproject.toml`; frontend dependencies are locked by `pnpm-lock.yaml`. Container images use explicit tags but are not digest-pinned.

The optional bundled replay is synthetic, and neither its P&L nor its six-asset count demonstrates strategy profitability or full market catalog coverage.

## Strategy evaluation extension

50 backend tests passed; Ruff, TypeScript and frontend production build passed. Added tests cover next-open fills, future-price independence, separate validation accounting, costs, drawdown, repeated-entry prevention, malformed history, split rejection, and authenticated read-only cached evaluation. Real public history evaluated NVDA, ETH USD proxy and Saudi Aramco; dashboard evaluation of AAPL also completed successfully. See strategy-evaluation.md for results and limits.
