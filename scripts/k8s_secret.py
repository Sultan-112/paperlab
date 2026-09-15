"""Pipe stdout to kubectl apply -f -. Never save or commit the generated secret."""

import json
from pathlib import Path
from urllib.parse import quote

values = {}
for line in Path(".env").read_text().splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        values[k] = v
required = ["POSTGRES_PASSWORD", "APP_TOKEN"]
if not all(values.get(k) for k in required):
    raise SystemExit("Run scripts/init_env.py first")
data = {k: values.get(k, "") for k in required + ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"]}
data["DATABASE_URL"] = (
    "postgresql+psycopg://paperlab:" + quote(values["POSTGRES_PASSWORD"], safe="") + "@postgres:5432/paperlab"
)
print(
    json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "paperlab-secrets", "namespace": "paperlab"},
            "type": "Opaque",
            "stringData": data,
        }
    )
)
