#!/usr/bin/env bash
# Run on the demo VM only. Stops one Compose service briefly, then restores it.
set -euo pipefail

usage() {
  echo "Usage: bash integrations/majed/demo-fault.sh {caddy|web|api|postgres|redis} [seconds: 30-600]" >&2
  exit 2
}

service="${1:-}"
duration="${2:-180}"
case "$service" in
  caddy|web|api|postgres|redis) ;;
  *) usage ;;
esac
[[ "$duration" =~ ^[0-9]+$ ]] || usage
(( duration >= 30 && duration <= 600 )) || usage

cd "$(dirname "$0")/../.."
compose=(docker compose -f docker-compose.yml -f docker-compose.public.yml -f docker-compose.team-monitoring.yml)
"${compose[@]}" config --quiet
if ! "${compose[@]}" ps --status running --services | grep -Fxq "$service"; then
  echo "Refusing to test: $service is not running. No service was changed." >&2
  exit 1
fi

restore() {
  result=$?
  trap - EXIT INT TERM
  echo "Restoring $service..."
  "${compose[@]}" start "$service" || result=1
  exit "$result"
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Stopping $service for $duration seconds. Press Ctrl-C to restore early."
"${compose[@]}" stop "$service"
sleep "$duration"
