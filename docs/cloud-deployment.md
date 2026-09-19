# Cloud demo deployment and monitoring test

PaperLab is ready to deploy on a Linux VM, but no cloud VM, hostname, GitHub remote, or access credentials have been supplied. The steps below are vendor-neutral. The cloud account and any hosting cost belong to the operator; this project has no paid application dependency.

## VM and network

- Use an Ubuntu or similar Linux VM with Docker Engine, Docker Compose v2, Git and Python 3.12. Budget at least 4 vCPU, 8 GB RAM and 20 GB disk for the application without Ollama; allow more if running Ollama locally.
- Assign a public DNS name to the VM. Allow inbound TCP 80 and 443. Restrict SSH to the operator's address or private network. Do not expose database, Redis, API, metrics bridge, or Grafana ports.
- Put Majed's external website monitor outside this VM. Its existing Grafana, Prometheus, log collector and alert router remain in its own environment. For private metrics, put its collector on the VM or connect through a private agent/tunnel.
- A stopped VM is restarted from the cloud provider console. Arrange that access and verify it before testing full VM shutdown.

## Deploy PaperLab

Clone this repository from a private GitHub repository after it has been pushed, then run from the repository root:

```sh
python3 scripts/init_env.py
# Edit .env privately and set PUBLIC_DOMAIN to the DNS name.
docker compose -f docker-compose.yml -f docker-compose.public.yml -f docker-compose.team-monitoring.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.public.yml -f docker-compose.team-monitoring.yml up -d --build postgres redis api web caddy metrics-bridge
```

This starts the demo and its loopback metrics bridge, without the bundled Grafana/Prometheus. The public profile serves labeled **synthetic replay** until public redistribution permission for live feeds is verified. See [public-demo.md](public-demo.md) for the visitor boundary.

Verify from outside the VM that `https://<domain>/` and `https://<domain>/monitor/ready` work. On the VM, check `curl -fsS http://127.0.0.1:9180/metrics` and `curl -fsS http://127.0.0.1:9180/health/ready`. Confirm the public internet cannot reach port 9180 or any application dependency directly.

## Connect Majed's system and test alerts

Give the team the [monitoring handoff](../integrations/majed/README.md), which contains the dashboard, scrape rules, optional public probes, alerts and log schema. It needs a private route to metrics and the public domain to probe. It does **not** need the PaperLab `APP_TOKEN` or database credentials. Confirm metrics and external probes are healthy before injecting faults.

Run one timed [fault scenario](../integrations/majed/README.md#controlled-alert-scenarios) at a time and verify both **firing** and **resolved** notifications. The scenarios cover the gateway, website, API, PostgreSQL and Redis. For a full VM-down test, use the cloud provider console with a separate recovery plan; local automatic restoration cannot work while the VM is off.
