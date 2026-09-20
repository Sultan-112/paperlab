# PaperLab → Majed team monitoring handoff

This folder is safe to share with the monitoring team. It contains no passwords or access tokens. The public demo is not deployed yet; the hostname and server still need to be selected.

## What the team receives

| Need | Endpoint or file | Access |
|---|---|---|
| Prometheus application metrics | `GET http://127.0.0.1:9180/metrics` on the demo VM, using the optional bridge below | VM loopback only; no token |
| Local application readiness | `GET http://127.0.0.1:9180/health/ready` | VM loopback only; no token |
| External uptime | `GET https://<public-domain>/monitor/ready` | Public, small JSON response; no token |
| Grafana dashboard | [`infrastructure/grafana/dashboards/paperlab.json`](../../infrastructure/grafana/dashboards/paperlab.json) | Import into the team's Grafana; select their Prometheus datasource |
| Prometheus scrape examples | [`prometheus-scrape.example.yml`](prometheus-scrape.example.yml) | Merge jobs into existing Prometheus config; edit hostnames |
| Alert examples | [`alerts.example.yml`](alerts.example.yml) | Merge into existing rules; route via team's Alertmanager |
| Public website probes | [`public-probes.example.yml`](public-probes.example.yml) and [`public-alerts.example.yml`](public-alerts.example.yml) | Optional; run probes from outside the demo VM after replacing the domain/exporter |
| Security and API logs | `docker compose logs api` or the team's host log collector | Container stdout/stderr on demo VM |

The live API and broker ports are **not** exposed publicly. The optional bridge is limited to `/metrics` and `/health/ready`; all other paths return 404. A collector already attached to PaperLab's Docker network can skip the bridge and scrape `http://api:8000/metrics`. If the team's monitoring stack runs on another machine, use their agent on the demo VM, an authenticated private VPN, or an SSH tunnel. Do not publish port 9180 on the internet or copy the bridge URL into a public dashboard.

## Start without duplicate monitoring servers

On the future demo VM, after configuring `.env` and `PUBLIC_DOMAIN` as described in [public-demo.md](../../docs/public-demo.md):

```sh
docker compose -f docker-compose.yml -f docker-compose.public.yml -f docker-compose.team-monitoring.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.public.yml -f docker-compose.team-monitoring.yml up -d --build postgres redis api web caddy metrics-bridge
curl -fsS http://127.0.0.1:9180/health/ready
curl -fsS http://127.0.0.1:9180/metrics | grep paperlab_
```

Naming explicit services leaves PaperLab's bundled Prometheus/Grafana stopped; Majed's existing stack collects the metrics. The app remains usable if Ollama is not started: AI explanations fall back to deterministic text. The demo uses synthetic replay by default, while the private learning lab can continue using live feeds.

The example `127.0.0.1:9180` scrape target assumes the collector runs on the **VM host**. For a collector in its own container, use its host-gateway address or attach it to the PaperLab network and scrape `api:8000` privately. For a collector on another VM, use an agent or private tunnel; `127.0.0.1` on that other VM points back to itself.

## Tokens and access

| Credential | Share with monitoring team? | Purpose |
|---|---|---|
| `APP_TOKEN` | **No** | PaperLab admin control, including simulated orders and kill switch. Keep in the private `.env`. |
| `GRAFANA_PASSWORD` from PaperLab `.env` | **No** | Only for the bundled Grafana, which the team does not need. |
| Metrics token | **None required** | Scraping is restricted by the private network/loopback bridge. |
| Team-owned credentials | **Not in Git** | If their collector or alert router needs secrets, configure them in their system. |

Share the public [Sultan-112/paperlab](https://github.com/Sultan-112/paperlab) link with the team. They can read and clone the source without a token or GitHub invitation. Never add `.env` to Git.

## Metric and log contract

Key series: `paperlab_api_latency_seconds`, `paperlab_market_events_total`, `paperlab_provider_errors_total`, `paperlab_decisions_total`, `paperlab_orders_total`, `paperlab_dependency_up`, `paperlab_cpu_percent`, `paperlab_memory_bytes`, `paperlab_market_age_seconds`, `paperlab_security_events_total`, and `paperlab_demo_replay_cycles_total`. The example alert rules cover missing metrics, database/Redis failures, failed admin-token attempts, and optional external demo probing. An external probe is important: an application cannot alert on its own total outage.

Security events are JSON lines from the `paperlab.security` logger with `time`, `component`, `category`, `event`, and `outcome`, plus only safe fixed details such as `transport` or simulated `side`. Example:

```json
{"time":"2026-09-19T12:00:00+00:00","component":"paperlab-api","category":"security","event":"authentication","outcome":"denied","transport":"http"}
```

The app does not put admin tokens, order IDs, request bodies or visitor IPs in these security records. Logs are operational telemetry, not a tamper-proof audit store. Majed's team should set retention, alert routes and escalation in their existing platform.

## Acceptance checks for the team

1. Scrape `/metrics` privately and observe `up{job="paperlab-demo"} == 1` in Prometheus.
2. Import the dashboard and confirm application/process panels show data. Container/pod panels need their separate infrastructure exporters.
3. From outside the VM, probe public `/monitor/ready` and the website homepage. Configure the team's alert router for down and recovered states.
4. Send a deliberately wrong admin token once and confirm a JSON `authentication/denied` event and an increment in `paperlab_security_events_total`—never log the token itself.
5. Confirm attempts to reach the metrics bridge from the public internet fail.

## Controlled alert scenarios

After the site is deployed and Majed's external probes are working, run one scenario at a time **on the demo VM**. The command refuses to stop a service that is already down, runs for 180 seconds by default, and starts it again on normal exit or Ctrl-C. It cannot restore a VM that has been powered off or lost its SSH session; do that through the cloud provider console.

```sh
bash integrations/majed/demo-fault.sh caddy 180
```

| Scenario argument | Expected signal | Visitor impact |
|---|---|---|
| `caddy` | Both public probes fail; private API metrics may stay healthy | Entire public site unreachable |
| `web` | Homepage probe fails; readiness and API metrics may stay healthy | Website unavailable |
| `api` | Readiness fails and private metrics scrape fails | Demo data/API unavailable |
| `postgres` | Readiness fails; `paperlab_dependency_up{dependency="db"}` falls to 0 | Demo data unavailable; database is preserved |
| `redis` | `paperlab_dependency_up{dependency="redis"}` falls to 0; readiness may remain HTTP 200 | Cache/stream functions degraded |

Wait for the alert's `for` period and at least two scrapes; then confirm Majed's **firing and resolved** notifications. Check `docker compose ... ps` and the public URLs after restoration. For a true **VM-down** test, Majed must monitor from outside this VM and the operator must shut down and restart the VM using the chosen cloud provider's console; the local script intentionally cannot do that. Keep the test isolated from other users and coordinate the window with the team.

No webhook endpoint, payload schema or team repository was supplied, so PaperLab does not push telemetry to an unknown destination. The documented pull interfaces let the team integrate it without sharing an admin secret.
