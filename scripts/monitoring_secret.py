"""Emit Grafana Kubernetes Secret to a pipe; never commit its output."""

import json
from pathlib import Path

values = dict(
    line.split("=", 1)
    for line in Path(".env").read_text().splitlines()
    if line and not line.startswith("#") and "=" in line
)
password = values.get("GRAFANA_PASSWORD")
if not password:
    raise SystemExit("Run scripts/init_env.py first")
print(
    json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "monitoring-grafana", "namespace": "monitoring"},
            "type": "Opaque",
            "stringData": {"admin-user": "admin", "admin-password": password},
        }
    )
)
