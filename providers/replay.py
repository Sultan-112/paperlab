import csv
from decimal import Decimal
from pathlib import Path


def load_replay(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("Replay file is empty")
    previous = -1.0
    for row in rows:
        stamp = float(row["timestamp"])
        price = Decimal(row["price"])
        if stamp < previous or not price.is_finite() or price <= 0 or stamp < 0:
            raise ValueError("Replay must have ascending timestamps and finite positive prices")
        if row["market"] not in {"US", "KSA", "CRYPTO"}:
            raise ValueError("Invalid replay market")
        if not row["symbol"] or not row["currency"]:
            raise ValueError("Replay requires symbol and currency")
        previous = stamp
    return rows
