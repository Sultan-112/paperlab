"""python -m scripts.evaluate --asset US:AAPL --output data/research/aapl.json"""

import argparse
import asyncio
import csv
import json
from pathlib import Path

from providers.history import fetch_history
from services.evaluation import evaluate


def main():
    parser = argparse.ArgumentParser(description="Research only: no wallet writes or orders")
    parser.add_argument("--asset", required=True)
    parser.add_argument(
        "--csv", help="CSV with timestamp,open,close; completed daily bars in ascending order"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.csv:
        with open(args.csv, newline="", encoding="utf-8-sig") as handle:
            bars = [
                {k: float(row[k]) for k in ("timestamp", "open", "close")} for row in csv.DictReader(handle)
            ]
        source = "User-supplied daily CSV: " + Path(args.csv).name
    else:
        bars, source = asyncio.run(fetch_history(args.asset))
    report = evaluate(bars, args.asset, source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".bars.json").write_text(json.dumps(bars), encoding="utf-8")
    print(report["conclusion"])
    for name, result in report["segments"]["validation"]["results"].items():
        print(
            f"{name}: return={result['return_pct']:.3f}%, drawdown={result['max_drawdown_pct']:.3f}%, fills={result['fills']}"
        )


if __name__ == "__main__":
    main()
