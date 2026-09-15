"""Create local secrets once. Values are not printed and the file is gitignored."""

import secrets
from pathlib import Path

target = Path(".env")
if target.exists():
    raise SystemExit(".env already exists; leaving it unchanged")
text = Path(".env.example").read_text()
for key in ["POSTGRES_PASSWORD", "GRAFANA_PASSWORD", "APP_TOKEN"]:
    lines = text.splitlines()
    text = (
        "\n".join(f"{key}={secrets.token_hex(24)}" if line.startswith(key + "=") else line for line in lines)
        + "\n"
    )
target.write_text(text)
target.chmod(0o600)
print("Created .env. Keep it private. Copy APP_TOKEN into the dashboard when connecting.")
