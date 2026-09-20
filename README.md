# PaperLab

**A local multi-market paper-trading lab for learning deployment, market-data systems, and local AI. Every order is simulated.**

Python FastAPI · React/TypeScript · PostgreSQL · Redis · Ollama · Prometheus · Grafana · Docker Compose · Kubernetes/K3s

## Start here

Requirements: Docker Engine with Compose v2 (a Linux VMware VM is recommended), Python 3.12 for setup, approximately 4 CPU cores, 8 GB RAM minimum / 12 GB recommended, and 20 GB free disk. Initial dependencies, images, model weights, and optional live market feeds need internet access. No paid service or cloud deployment is required.

From the repository root:

```sh
python scripts/init_env.py
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:1.5b
```

Open **http://localhost:8080**. Copy `APP_TOKEN` from your private `.env` into the dashboard's access-token field. The default is real market data (`DATA_MODE=live`), using free no-key public stock sources and Binance streaming. For the offline synthetic demo, set `DATA_MODE=replay` and recreate the API. The local model is optional: explanations fall back to the deterministic strategy reason if Ollama is unavailable.

- Dashboard: http://localhost:8080
- Grafana: http://localhost:3000 — username `admin`, password `GRAFANA_PASSWORD` in `.env`
- Prometheus: http://localhost:9090
- API docs: through `docker compose exec api` or a temporary local port forward; API is not published by default.

The UI supports search, watchlists, paper buy/sell, optional automatic paper trading, BUY/SELL/HOLD signals, AI explanations, a kill switch, separate wallets, P&L, trade history, replay pause/speed, and provider diagnostics.

## What is implemented, and what depends on providers

| Market | Dynamic universe | Data handling |
|---|---|---|
| US | Nasdaq and other-exchange public symbol directories, without keys; optional Alpaca active-equity catalog | Public watchlist price snapshots targeting 15-second polling, or optional free IEX streaming with credentials (30 symbols). |
| Crypto | Every active Binance Spot pair exposed by `exchangeInfo`, including different quote currencies | Public all-market mini-ticker WebSocket; updates arrive as Binance publishes them. No Binance key required. |
| Saudi | Mubasher public numeric-instrument catalog, including Main Market/Nomu/funds/debt entries; CSV import remains available | Real public prices with a stated 15-minute delay, polled every 60 seconds. Old records keep their timestamps and are marked stale. |

**Verified public coverage:** the live check returned 13,204 US-listed instruments, 469 Saudi catalog entries and 1,372 Binance Spot pairs. Counts change over time. US directory counts include listed security types beyond ordinary common shares; OTC coverage and price availability for every listing are not guaranteed. The Saudi third-party catalog contains old/inactive records and is not a verified complete active exchange list. No API key, payment card, paid fallback, or subscription is required for the default feeds. Public endpoints have no availability guarantee. See [the provider guide](docs/providers.md).

The one-second internal loop evaluates current observations and sends dashboard updates. It does not fabricate live updates. Unchanged or out-of-order events do not extend freshness. The US free feed does not represent all exchanges, and free access limits may change.

## Repository

```text
apps/api/              FastAPI routes, WebSocket, authentication
apps/web/              React dashboard, TypeScript, Vite
services/              Engine, signal strategy, custom paper broker
providers/             Free public US/Saudi data, Alpaca/Binance streams, CSV replay
libs/                  SQLAlchemy models, settings, Prometheus instruments
data/replay/           Deterministic synthetic demonstration data
data/imports/          Private user catalogs/replays (gitignored)
infrastructure/        Nginx, Prometheus, Grafana, K3s manifests
scripts/               Local-secret setup and infrastructure validation
tests/                 Broker, provider, replay, API and WebSocket tests
docs/                  Architecture, providers, operations, VMware/K3s guide
.github/workflows/     Lint, tests, frontend build and container smoke CI
```

## Live market data, simulated execution

1. Leave `DATA_MODE=live` (the default), or set it in your existing `.env`.
2. Run `docker compose up -d --force-recreate api`. The application discovers public catalogs automatically.
3. Search or page through the catalog and add any supported asset to your watchlist. Real prices refresh automatically; click **Refresh stock prices** to queue US checks within the source limits.
4. Optional: add free Alpaca keys to enable IEX streaming instead of public US snapshots. It still uses only read-only market data and asset discovery; there is no external order submission.

The news-style ticker shows watched recommendations, prices and source labels. Price flashes represent new observations, not simulated movement. Public US requests are globally paced at no more than one per second; larger watchlists take longer than the 15-second per-symbol target. Saudi refreshes follow the source site's one-minute cadence and do not remove its 15-minute delay.

Every market/quote currency gets a separate 100,000-unit virtual wallet on its first accepted order. Example: `live:US:USD`, `replay:KSA:SAR`, `live:CRYPTO:BTC`. These are artificial starting balances; 100,000 BTC is deliberately not a realistic deposit. There is no exchange-rate conversion and no combined cross-currency P&L.

Automatic paper trading is off initially. Enable it in the order panel to execute strategy signals at up to 100 quote-currency units per asset per minute. It uses the same broker checks as manual orders. Its toggle and the kill switch persist in the database. Disabling automatic trading before restarting is recommended when changing data mode.

## Safety and modeling boundaries

- No live broker executor, deposits, withdrawals, leverage or short selling.
- Market orders fill instantly against the last accepted quote with 0.05% adverse slippage and a 0.10% fee. They do not model order books, liquidity or exchange matching.
- Orders use source-aware freshness: streaming/replay 15 seconds; public US snapshots 120 seconds; delayed Saudi timestamps 17 minutes with a successful source check in the last 120 seconds. These are explicit paper-simulation tolerances, not promises of executable market prices. Known closed US sessions, older Saudi records, and expired transport checks reject fills. Repeated polls never reset the underlying price timestamp.
- Buy limits: 10% of initial wallet capital per order, 25% per position, and a 5% cumulative realized-loss stop for new buys. The latter is not a daily-loss or drawdown limit. Sells remain possible unless the kill switch is enabled.
- Decimal ledger accounting, transactional commits, wallet row locks and idempotency keys protect paper balances. Run exactly **one API process/replica**; this reference is not designed for multiple engine writers.
- BUY/SELL/HOLD is a transparent 5/20-observation moving-average rule. Ollama explains it; the model cannot place orders or override risk checks. Signals are educational, not validated forecasts.
- Live/replay wallets are separate. Restarting replay replays the file from its beginning and retains its existing paper balances. The fixture contains no actual historical prices.
- API readiness requires DB and engine health. Redis is an optional cache/pub-sub dependency and can be degraded without stopping the engine. Quotes and rolling windows rebuild after restart.
- No migrations framework yet: schema is created idempotently on first startup. Back up the database before changing the reference schema.

## Development without Docker

```sh
python -m venv .venv
# Linux: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e '.[dev]'
python -m uvicorn apps.api.main:app --env-file .env --host 127.0.0.1 --port 8000
# In another terminal:
cd apps/web
corepack enable
corepack prepare pnpm@11.19.0 --activate
pnpm install --frozen-lockfile
pnpm dev
```

Without `DATABASE_URL`, the dev server uses SQLite. Compose and K3s use PostgreSQL. Without Redis, the dev dashboard still works and reports degraded cache health. Keep the API at one worker; hot reload is not needed for the initial demo.

```sh
python -m pytest -q
python -m ruff check .
python scripts/validate_infrastructure.py
cd apps/web
pnpm lint
pnpm build
```

## Deployment, observability and learning

- [VMware and K3s lab instructions](docs/vmware-k3s.md)
- [Architecture and extension points](docs/architecture.md)
- [Provider coverage, limits and replay format](docs/providers.md)
- [Operations, backups and troubleshooting](docs/operations.md)
- [Verification results and limitations](docs/verification.md)
- [Suggested manual rebuild sequence](docs/rebuild-guide.md)

The provisioned Grafana dashboard includes API latency, market-event and decision rates, order outcomes, provider errors, DB/Redis/Ollama health, process CPU/memory, quote age and US subscription count. Container/pod panels require the Linux cAdvisor profile or the K3s monitoring stack described in the lab guide. No external alert delivery is configured.

## GitHub repository

The source is public at [Sultan-112/paperlab](https://github.com/Sultan-112/paperlab). Anyone can read and clone the repository; only authorized contributors can push changes. `.env`, imports, local databases, dependency directories and generated secret files are excluded. Never add credentials to source, screenshots, issues or CI logs.

## Strategy evaluation

The dashboard now compares repeated entries, one entry/full exit, and buy-and-hold on free daily history with costs and chronological validation. Automatic paper trading no longer adds to an existing position on repeated BUY signals. [Method, results, and limits](docs/strategy-evaluation.md). This is research infrastructure, not a validated profitable strategy.

## Public demo option

An opt-in [public read-only deployment profile](docs/public-demo.md) serves a clearly labeled synthetic replay and signals over HTTPS while keeping paper orders and wallet data behind the private admin token. Grafana, Prometheus and structured security events provide monitoring hooks for an external security system. Public redistribution rights for live third-party prices have not been verified, so the public profile does not use live feeds by default. A public server/domain is still needed for deployment; a team endpoint is needed only for outbound alert delivery.

If a team already has Grafana and Prometheus, use the [monitoring handoff](integrations/majed/README.md). It provides a private metrics/readiness bridge, importable dashboard, scrape and alert examples, log schema, and a list of the credentials the team does and does not need.

For cloud hosting, follow the [container deployment guide](docs/cloud-deployment.md). It starts the website, API, PostgreSQL, Redis and HTTPS gateway as containers. Monitoring remains optional. A container host or managed container provider and a domain must be chosen before the site can be put online.
