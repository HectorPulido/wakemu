#!/bin/bash
# Build the complete source stack in dependency order without restarting it.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$project_dir"
docker compose build world
docker compose build ai cron
