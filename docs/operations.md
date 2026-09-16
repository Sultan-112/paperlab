# Operations

## Routine commands

```sh
docker compose ps
docker compose logs -f api
docker compose restart api
docker compose down
```

`down` retains named volumes. Do not add `-v` unless you intentionally want to erase the virtual ledger and local models. Data-mode changes require recreating the API container; replay starts at the beginning and warm-up resets. Both the automatic-trading toggle and kill switch persist. Disable automation if you want a passive replay.

## Observability

The default Grafana dashboard provisions automatically. Prometheus records:

| Signal | Metric |
|---|---|
| API request latency | `paperlab_api_latency_seconds` by route template/method |
| Market events | `paperlab_market_events_total` by market/source |
| Decision records | `paperlab_decisions_total` by action |
| Paper orders | `paperlab_orders_total` by outcome |
| Provider failures | `paperlab_provider_errors_total` by provider |
| DB/Redis/Ollama state | `paperlab_dependency_up` |
| Engine processing time | `paperlab_loop_seconds` |
| Process CPU / memory | `paperlab_cpu_percent`, `paperlab_memory_bytes` |
| Source freshness | `paperlab_market_age_seconds` (`-1` = no observations) |
| US stream allocation | `paperlab_us_subscriptions` |

Ollama health is populated when an explanation is requested. Market age is the newest received event in that market; inspect individual row ages for trading freshness. API route labels use templates to avoid per-symbol metric explosion. Decision counters describe saved decisions, not the total number of loop evaluations.

For container metrics on the Linux VMware VM:

```sh
docker compose --profile linux-observability up -d
```

cAdvisor needs privileged read access to host container statistics in this lab. It exposes no host port. The base stack will show the cAdvisor target down when its optional profile is off. Container panels then have no data; the core application/process panels still work. K3s pod metrics use kube-state-metrics and kubelet cAdvisor via kube-prometheus-stack.

Prometheus includes rules for API unavailability, dependency outages and repeated provider errors. Alerts remain local in Prometheus; no email or messaging integration is configured.

## Back up the virtual ledger

Linux shell, from the repository root:

```sh
mkdir -p data/imports/backups
docker compose exec -T postgres pg_dump -U paperlab -d paperlab > data/imports/backups/paperlab.sql
```

Restore only into a deliberately prepared database. The backup contains trading history but not the `.env` secrets. Keep a private copy of `.env` separately. Files under `data/imports` are excluded from Git.

## Troubleshooting

- **Dashboard reconnects indefinitely:** check the access token, API logs and DB health. Refreshing `.env` in the shell does not update an already-running container.
- **US catalog empty:** check the free Nasdaq directory endpoint and provider diagnostics; refresh retries preserve the previous catalog. Alpaca credentials are optional. Credentials are never returned in provider diagnostics.
- **US quote is stale:** the market may be closed, the public endpoint may be backing off, or a large watchlist may be awaiting its turn. With optional Alpaca keys, an IEX trade/stream slot may be pending. Repeated public snapshots retain the original source timestamp.
- **Saudi discovery error:** check the public Mubasher feed or import a freely obtained catalog. Its listed rows are not guaranteed active or complete. Prices are delayed 15 minutes and polling every 60 seconds cannot remove that delay.
- **Binance disconnects:** network or regional restrictions can affect public access. Check diagnostics; retries use backoff.
- **Ollama fallback:** pull the configured model, check `docker compose logs ollama`, and allow sufficient RAM. Initial inference can exceed the 60-second explanation timeout on small CPUs.
- **Redis down:** durable orders remain in PostgreSQL; the UI/engine continue with a degraded dependency gauge. Redis is not an alternate order ledger.
- **Replay completed:** recreate/restart the API to start the file again; virtual balances remain. Use a separate database for independent experiments.
- **K3s Pending pod:** inspect PVC binding, node capacity and image availability. The manifests use local-path-compatible RWO volumes and Recreate deployments.

## Secret handling

Run `scripts/init_env.py` once; it generates random hexadecimal secrets without printing their values. `.env` is ignored and Docker build contexts exclude it. Use the provided secret-generation pipe for Kubernetes instead of committing a Secret manifest. Kubernetes Secret values are not inherently encrypted at rest; keep the VM and kubeconfig private. The CI pipeline creates disposable secrets and uses `docker compose config --quiet` so expanded credentials are not logged.
