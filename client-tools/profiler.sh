#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
compose=(docker compose -f compose.yaml -f compose.profiler.yaml --profile observability)
action="${1:-status}"
case "$action" in
  start)
    "${compose[@]}" build profiler
    "${compose[@]}" up -d --no-deps --no-build --force-recreate profiler
    ;;
  resume)
    curl --fail --silent --show-error --max-time 3 -X POST http://127.0.0.1:18082/start
    ;;
  pause)
    curl --fail --silent --show-error --max-time 3 -X POST http://127.0.0.1:18082/stop
    ;;
  artifacts)
    curl --fail --silent --show-error --max-time 3 http://127.0.0.1:18082/artifacts
    ;;
  stop)
    "${compose[@]}" stop profiler
    ;;
  status)
    curl --fail --silent --show-error --max-time 3 http://127.0.0.1:18082/status
    ;;
  capture)
    seconds="${2:-30}"
    mode="${3:-cpu}"
    if [[ ! "$seconds" =~ ^[0-9]+$ ]] || ((seconds < 5 || seconds > 120)); then
      echo 'Duration must be an integer between 5 and 120 seconds.' >&2
      exit 2
    fi
    if [[ "$mode" != cpu && "$mode" != waits ]]; then
      echo 'Mode must be cpu or waits.' >&2
      exit 2
    fi
    curl --fail --silent --show-error --max-time 3 \
      -H 'Content-Type: application/json' \
      --data "{\"seconds\":$seconds,\"mode\":\"$mode\"}" \
      http://127.0.0.1:18082/capture
    ;;
  report)
    python3 server/tools/performance_report.py .runtime/local/logs/profiles/performance-latest.json "${@:2}"
    ;;
  *)
    echo 'Usage: bash client-tools/profiler.sh start|stop|pause|resume|status|artifacts|capture [5-120] [cpu|waits]|report [--sort cpu|wait|total|max]' >&2
    exit 2
    ;;
esac
