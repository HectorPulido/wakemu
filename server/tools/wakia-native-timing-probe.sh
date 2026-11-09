#!/bin/sh
# Exercise a synthetic native turn timing against local World and WakIA.
set -eu

task_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$task_root"
case "${DOCKER_HOST:-}" in
    ''|unix://*|npipe://*) ;;
    *) printf '%s\n' 'Probe refuses a remote Docker host.' >&2; exit 1 ;;
esac
context_host=$(docker context inspect "$(docker context show)" --format '{{.Endpoints.docker.Host}}')
case "$context_host" in
    unix://*|npipe://*) ;;
    *) printf '%s\n' 'Probe refuses a remote Docker context.' >&2; exit 1 ;;
esac
world_id=$(docker compose ps -q world)
if [ -z "$world_id" ]; then
    printf '%s\n' 'Local World is not running.' >&2
    exit 1
fi
project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$world_id")
workdir=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$world_id")
network=$(docker inspect --format '{{if index .NetworkSettings.Networks "wakfu-local_isolated"}}yes{{end}}' "$world_id")
if [ "$project" != wakfu-local ] || [ "$workdir" != "$task_root" ] || [ "$network" != yes ]; then
    printf '%s\n' 'Probe only supports the local wakfu-local World and isolated network.' >&2
    exit 1
fi

remote_dir=''
cleanup() {
    if [ -n "$remote_dir" ]; then
        docker exec "$world_id" rm -rf "$remote_dir" >/dev/null 2>&1 || :
    fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
remote_dir=$(docker exec "$world_id" mktemp -d /tmp/wakia-timing-probe.XXXXXXXX)
docker cp server/tools/wakia_native_probe.py "$world_id:$remote_dir/wakia_native_probe.py"
docker cp server/tools/wakia_native_timing_probe.py "$world_id:$remote_dir/wakia_native_timing_probe.py"
docker cp server/wakfu_server/wakia_bridge/wakfu_ai "$world_id:$remote_dir/wakfu_ai"
docker exec -e "PYTHONPATH=/app:$remote_dir" -e "WAKIA_PROBE_DIR=$remote_dir" \
    "$world_id" python3 "$remote_dir/wakia_native_timing_probe.py"
