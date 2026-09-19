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
print("Compose bindings, Kubernetes structure and dashboard JSON validated.")
