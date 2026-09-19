# Public demo and monitoring handoff

PaperLab can be presented as a public, read-only demo. This is a deployment profile, not an active public site. The public server and domain have not been chosen. Keep the existing local deployment for private development.

The public profile defaults to the bundled **synthetic replay**, which transparently loops after its hour-long fixture. It shows six example assets across US, Saudi and crypto, not the full live catalog. This keeps the demo moving without presenting invented movements as real prices. The private local lab remains on live free feeds. Rights to publicly redistribute the US and Saudi third-party quote feeds have not been verified. `PUBLIC_DEMO=true` with `DATA_MODE=live` refuses startup unless `PUBLIC_LIVE_DATA_ALLOWED=true` is deliberately set after permission is confirmed. This switch is an operator assertion, not a license. See [Yahoo's terms](https://legal.yahoo.com/in/en/yahoo/terms/otos/index.html) and the terms of each chosen data provider before enabling public live quotes.

## Public visitor boundary

Set `PUBLIC_DEMO=true` using `docker-compose.public.yml`. A visitor without a token can search the demo asset catalog and see the shared watchlist, synthetic prices and educational signals. The API omits wallets, positions, trade history and automation settings from guest state. Guest requests cannot change watches, paper orders, controls, replay, catalogs, or request the expensive history evaluation. An administrator can enter the private `APP_TOKEN` to use these functions. `PUBLIC_DEMO` refuses startup when `APP_TOKEN` is empty. The public site is still a simulation: no real broker order route exists.

The public gateway exposes HTTPS on ports 80/443 and a minimal `/monitor/ready` endpoint. API, PostgreSQL and Redis remain on the private Docker network. The base stack's other published ports bind to loopback only; do not forward ports 3000, 8000, 8080, 9090, 5432, 6379 or 11434 from the container host. The readiness probe reports HTTP 200 when the API engine and database are ready, 503 otherwise. Redis status is returned in JSON.

## Deploy when a host and domain are chosen

Follow the [container deployment guide](cloud-deployment.md) for the website-only service list. Monitoring is optional.

Use a Docker-capable Linux host with Compose, DNS for a domain pointing to it, and inbound TCP 80/443. [Caddy automatic HTTPS](https://caddyserver.com/docs/quick-starts/https) needs the DNS and ports to work. Obtain a no-cost domain/subdomain you control if the project must remain free. Validate with the chosen provider's terms and reliability; this repository does not choose or register one.

1. Make a private `.env` with `python scripts/init_env.py`, then set `PUBLIC_DOMAIN` to the chosen hostname. Keep `APP_TOKEN` private. Use a separate demo database from personal experiments.
2. Run `docker compose -f docker-compose.yml -f docker-compose.public.yml config --quiet`. Review the resolved port bindings without printing expanded secret values.
3. Run `docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build postgres redis api web caddy`. Optional Ollama model: start `ollama`, then pull `qwen2.5:1.5b`.
4. Verify `https://<domain>/` as a visitor: the **synthetic replay** label, changing example prices and signals are visible, guest state contains empty wallet/order arrays, and mutation requests return 401. Check `https://<domain>/monitor/ready` and HTTPS certificate. Verify the API, Grafana and database ports are not internet-reachable.
5. Check `docker compose ps` and `docker compose logs --tail=100 api caddy` for application health.

The public gateway serves the demo and health probe only. The `APP_TOKEN` is not embedded in the frontend bundle. Do not paste it into public screenshots or share the admin browser session.

## Optional monitoring integration

PaperLab's API exposes internal `/metrics` for Prometheus. Grafana automatically provisions the PaperLab dashboard with request latency, feed events/errors, decisions, simulated orders, DB/Redis/Ollama health, CPU/memory, quote ages and security events. Prometheus alert rules cover API scrape failure, dependency failure, repeated provider errors, repeated access-token failures, and its own scrape target. On Linux, enable `--profile linux-observability` for cAdvisor container charts; this component is privileged and internal only. On K3s, use the existing ServiceMonitor and monitoring values.

Security-relevant API events are newline-delimited JSON in `docker compose logs api`, category `security`: failed token checks, blocked cross-origin requests, accepted/rejected simulated orders, kill-switch changes and automatic paper-trading changes. Event names and outcomes are fixed to keep metric labels bounded. Tokens, order IDs, request bodies and client IPs are deliberately absent. Majed's agent can collect these container logs and scrape the **internal** Prometheus endpoint. It can also probe public `/monitor/ready` independently to detect a full outage that the app's Prometheus cannot report while down. The team's system can consume Prometheus alerts, but outbound webhook delivery is not configured until its endpoint, authentication and payload schema are supplied. No secret or telemetry is sent to a third party by this profile alone.

For a team that already runs Grafana and Prometheus, use the [Majed monitoring handoff](../integrations/majed/README.md) and optional loopback metrics bridge. Start only the application services to avoid duplicate Grafana and Prometheus instances.

The handoff includes repeatable fault scenarios for the public gateway, website, API, PostgreSQL and Redis. Majed's external probe should check both the homepage and `/monitor/ready`: either alone misses a distinct outage. A full container-host shutdown is a separate test initiated and recovered through the hosting provider.

Do not treat the security event stream as a complete audit ledger: it is not tamper-evident, and logs may be rotated. The durable paper-trade ledger is in PostgreSQL. Define retention, access, alert routing and incident ownership with Majed's team before the public launch.
