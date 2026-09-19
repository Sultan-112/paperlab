"""Static structural checks; not a substitute for Docker/Kubernetes runtime validation."""

import json
from pathlib import Path

import yaml

for path in Path("infrastructure").rglob("*.yaml"):
    list(yaml.safe_load_all(path.read_text()))
for path in Path("infrastructure").rglob("*.yml"):
    list(yaml.safe_load_all(path.read_text()))
compose = yaml.safe_load(Path("docker-compose.yml").read_text())
for name, service in compose["services"].items():
    assert all(str(port).startswith("127.0.0.1:") for port in service.get("ports", [])), name
public = yaml.safe_load(Path("docker-compose.public.yml").read_text())
assert public["services"]["api"]["environment"]["PUBLIC_DEMO"] == "true"
assert public["services"]["api"]["environment"]["PUBLIC_DEMO_LOOP"] == "true"
assert public["services"]["api"]["environment"]["DATA_MODE"] == "replay"
assert public["services"]["caddy"]["ports"] == ["80:80", "443:443"]
assert all(name not in public["services"] for name in ("postgres", "redis", "prometheus", "grafana"))
team = yaml.safe_load(Path("docker-compose.team-monitoring.yml").read_text())
assert set(team["services"]) == {"metrics-bridge"}
bridge = team["services"]["metrics-bridge"]
assert bridge["ports"] == ["127.0.0.1:9180:9180"]
assert bridge["depends_on"] == ["api"]
assert any("integrations/majed/MetricsCaddyfile" in mount for mount in bridge["volumes"])
bridge_routes = Path("integrations/majed/MetricsCaddyfile").read_text()
assert "handle /metrics" in bridge_routes
assert "handle /health/ready" in bridge_routes
assert "reverse_proxy api:8000" in bridge_routes
assert "respond 404" in bridge_routes
scrape = yaml.safe_load(Path("integrations/majed/prometheus-scrape.example.yml").read_text())
assert scrape["scrape_configs"][0]["static_configs"][0]["targets"] == ["127.0.0.1:9180"]
alerts = yaml.safe_load(Path("integrations/majed/alerts.example.yml").read_text())
assert any(rule["alert"] == "PaperLabMetricsUnavailable" for rule in alerts["groups"][0]["rules"])
objects = list(yaml.safe_load_all(Path("infrastructure/k8s/base.yaml").read_text()))
for obj in objects:
    if obj["kind"] == "Service":
        assert obj["spec"]["type"] == "ClusterIP"
    if obj["kind"] == "Deployment" and obj["metadata"]["name"] == "api":
        assert obj["spec"]["replicas"] == 1
        assert obj["spec"]["strategy"]["type"] == "Recreate"
dashboard = json.loads(Path("infrastructure/grafana/dashboards/paperlab.json").read_text())
assert len(dashboard["panels"]) >= 15
assert any(
    "paperlab_security_events_total" in target["expr"]
    for panel in dashboard["panels"]
    for target in panel["targets"]
)
print("Compose bindings, team monitoring files, Kubernetes structure and dashboard JSON validated.")
