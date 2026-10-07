#!/bin/sh
# Rebuild/restart only AI, using the complete catalogue of the live world image.
set -eu
ai_repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ai_repository_root"
ai_world_image=$(docker inspect wakfu-local-world-1 --format '{{.Image}}')
ai_source_tag="wakfu-world-catalog-source:${ai_world_image#sha256:}"
docker tag "$ai_world_image" "$ai_source_tag"
docker build --build-arg "WORLD_IMAGE=$ai_source_tag" -t wakfu-local-ai server/ai-service
ai_current_world_image=$(docker inspect wakfu-local-world-1 --format '{{.Image}}')
if [ "$ai_current_world_image" != "$ai_world_image" ]; then
    echo 'World image changed during AI build; rerun to copy its current catalogue.' >&2
    exit 1
fi
docker compose up -d --no-deps --no-build ai
python3 server/ai-service/scripts/provision_live_catalog.py
