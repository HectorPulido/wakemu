#!/bin/bash
# Build the default local planner and World without restarting either service.
set -euo pipefail
if (( $# != 0 )); then
    printf 'Usage: %s\n' "$0" >&2
    exit 2
fi
project_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$project_dir"
docker compose build world wakia
