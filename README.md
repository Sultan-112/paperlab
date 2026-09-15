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

Open **http://localhost:8080**. Copy `APP_TOKEN` from your private `.env` into the dashboard's access-token field. The default replay begins immediately with one hour of clearly labeled synthetic data for all three markets. The local model is optional: explanations fall back to the deterministic strategy reason if Ollama is unavailable.

- Dashboard: http://localhost:8080
- Grafana: http://localhost:3000 — username `admin`, password `GRAFANA_PASSWORD` in `.env`
- Prometheus: http://localhost:9090
- API docs: through `docker compose exec api` or a temporary local port forward; API is not published by default.

The UI supports search, watchlists, paper buy/sell, optional automatic paper trading, BUY/SELL/HOLD signals, AI explanations, a kill switch, separate wallets, P&L, trade history, replay pause/speed, and provider diagnostics.

## What is implemented, and what depends on providers

| Market | Dynamic universe | Data handling |
|---|---|---|
| US | All active equities/ETFs exposed by Alpaca's assets endpoint; free account keys required | IEX trade WebSocket, capped at 30 symbols. Holdings and watchlists receive priority; remaining capacity rotates through the catalog every minute. |
| Crypto | Every active Binance Spot pair exposed by `exchangeInfo`, including different quote currencies | Public all-market mini-ticker WebSocket; updates arrive as Binance publishes them. No Binance key required. |
| Saudi | Best-effort extraction from public exchange catalog pages plus full CSV import | Replay. No claim of free real-time Saudi quotes. Public-page discovery can be blocked or incomplete. |

**Saudi catalog limitation:** the exchange returned HTTP 403 during local verification. A complete Saudi catalog has therefore **not** been verified or bundled. The six-asset replay fixture is a demonstration, not the full market universe. Discovery reports errors and preserves previous catalog data; a successfully scraped Saudi list still carries `coverage: unverified`. To use the full freely obtainable Saudi list, import a current exchange/public export following [the provider guide](docs/providers.md). This is the remaining external-data dependency for full Saudi coverage.

The one-second internal loop evaluates current observations and sends dashboard updates. It does not fabricate live updates. Unchanged or out-of-order events do not extend freshness. The US free feed does not represent all exchanges, and free access limits may change.

## Repository

```text
apps/api/              FastAPI routes, WebSocket, authentication
apps/web/              React dashboard, TypeScript, Vite
services/              Engine, signal strategy, custom paper broker
providers/             Alpaca/Binance data, Saudi discovery/import, CSV replay
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

1. Change `DATA_MODE=live` in `.env`.
2. Add free Alpaca account credentials for **market data / asset discovery**. The application uses only GET `/v2/assets` on the paper API host plus the IEX data WebSocket. It never submits an order to Alpaca or Binance.
3. Run `docker compose up -d --force-recreate api`.
4. Refresh/search catalogs, add assets to the watchlist, and wait for fresh events. Saudi assets have no live price adapter: run them in replay mode.

Every market/quote currency gets a separate 100,000-unit virtual wallet on its first accepted order. Example: `live:US:USD`, `replay:KSA:SAR`, `live:CRYPTO:BTC`. These are artificial starting balances; 100,000 BTC is deliberately not a realistic deposit. There is no exchange-rate conversion and no combined cross-currency P&L.

Automatic paper trading is off initially. Enable it in the order panel to execute strategy signals at up to 100 quote-currency units per asset per minute. It uses the same broker checks as manual orders. Its toggle and the kill switch persist in the database. Disabling automatic trading before restarting is recommended when changing data mode.

## Safety and modeling boundaries

- No live broker executor, deposits, withdrawals, leverage or short selling.
- Market orders fill instantly against the last accepted quote with 0.05% adverse slippage and a 0.10% fee. They do not model order books, liquidity or exchange matching.
- Orders reject missing quotes and observations older than 15 seconds. Live provider timestamps are checked separately from receipt time.
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

## Push to a private repository

Git is initialized locally with an initial reference commit. Review the files, then create an empty **private** GitHub repository and connect it:

```sh
git remote add origin git@github.com:YOUR_USER/paperlab.git
git push -u origin main
```

`.env`, imports, local databases, dependency directories and generated secret files are excluded. Never add credentials to source, screenshots, issues or CI logs. The project is not published and has no configured remote.
