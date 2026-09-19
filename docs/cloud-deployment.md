# Container deployment for the public demo

PaperLab's website and API are built as Docker images. PostgreSQL, Redis and the HTTPS gateway run in separate containers. The source is in the private [Sultan-112/paperlab](https://github.com/Sultan-112/paperlab) repository. No cloud host, hostname or cloud access has been supplied yet. The app has no paid software dependency; cloud hosting costs depend on the provider.

## Where containers run

The ready-to-run deployment uses Docker Compose on a Linux **container host**. That host may be a cloud VM or another machine with Docker; PaperLab does not build or require a VM itself. A managed container platform can run the same application images, but its service, storage, secret and ingress configuration must be adapted to the provider after one is chosen.

For the Compose deployment, use Docker Engine, Compose v2, Git and Python 3.12. Budget at least 4 vCPU, 8 GB RAM and 20 GB disk without Ollama; allow more if running Ollama locally. Assign a public DNS name and allow inbound TCP 80 and 443. Keep the database, Redis and API private.

## Deploy PaperLab

Clone the private repository on the container host, then run from the repository root:

```sh
python3 scripts/init_env.py
# Edit .env privately and set PUBLIC_DOMAIN to the DNS name.
docker compose -f docker-compose.yml -f docker-compose.public.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build postgres redis api web caddy
```

This starts **only the website and the services it needs**. Grafana, Prometheus, the metrics bridge and Ollama are optional and are not started by these commands. The public profile serves labeled **synthetic replay** until public redistribution permission for live feeds is verified. See [public-demo.md](public-demo.md) for the visitor boundary.

Verify from a browser that `https://<domain>/` loads and clearly says synthetic replay. Check `https://<domain>/monitor/ready` and confirm database, Redis and API ports are not reachable from the public internet. The admin token remains private; visitors can view the demo without it.

## Optional monitoring integration

The website runs without any monitoring tool or connection to Majed's project. If integration is wanted later, use the separate [monitoring handoff](../integrations/majed/README.md). Its metrics bridge and outage tests are optional additions.
