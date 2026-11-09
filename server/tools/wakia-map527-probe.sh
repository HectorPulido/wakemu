#!/bin/sh
# Exercise a native map fixtures with Host and World movement.
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

fixture_file=''
export_dir=''
while [ "$#" -gt 0 ]; do
    case "$1" in
        --fixture) [ "$#" -ge 2 ] || exit 2; fixture_file=$2; shift 2 ;;
        --export-dir) [ "$#" -ge 2 ] || exit 2; export_dir=$2; shift 2 ;;
        *) printf '%s\n' 'Usage: wakia-map527-probe.sh [--fixture FILE] [--export-dir DIR]' >&2; exit 2 ;;
    esac
done
if [ -n "$fixture_file" ] && [ ! -f "$fixture_file" ]; then
    printf '%s\n' 'Synthetic fixture file does not exist.' >&2; exit 1
fi
if [ -n "$export_dir" ] && [ ! -d "$export_dir" ]; then
    printf '%s\n' 'Export directory does not exist.' >&2; exit 1
fi
if [ -n "$export_dir" ]; then
    if [ -n "$fixture_file" ]; then export_scenarios='custom'; else export_scenarios='455 456'; fi
    for export_scenario in $export_scenarios; do
        if [ -e "$export_dir/wakia-map-$export_scenario.json" ]; then
            printf '%s\n' 'Export destination already exists.' >&2; exit 1
        fi
    done
fi
remote_dir=''
local_dir=$(mktemp -d "${TMPDIR:-/tmp}/wakia-map527-probe.XXXXXXXX")
probe_pid=''
cleanup() {
    if [ -n "$probe_pid" ]; then
        kill "$probe_pid" >/dev/null 2>&1 || :
    fi
    if [ -n "$remote_dir" ]; then
        docker exec "$world_id" rm -rf "$remote_dir" >/dev/null 2>&1 || :
    fi
    rm -rf "$local_dir"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
remote_dir=$(docker exec "$world_id" mktemp -d /tmp/wakia-map527-probe.XXXXXXXX)
docker cp server/tools/wakia_native_probe.py "$world_id:$remote_dir/wakia_native_probe.py"
docker cp server/tools/wakia_map527_probe.py "$world_id:$remote_dir/wakia_map527_probe.py"
docker cp server/wakfu_server/wakia_bridge/wakfu_ai "$world_id:$remote_dir/wakfu_ai"
docker cp server/wakfu_server/combat/combat_walk_surface_policy.py "$world_id:$remote_dir/combat_walk_surface_policy.py"
scenarios='455 456'
if [ -n "$fixture_file" ]; then
    docker cp "$fixture_file" "$world_id:$remote_dir/fixture.json"
    scenarios='custom'
fi
for scenario in $scenarios; do
    docker exec -e "PYTHONPATH=/app:$remote_dir" -e "WAKIA_PROBE_DIR=$remote_dir" \
        -e "WAKIA_MAP527_SCENARIO=$scenario" "$world_id" \
        python3 "$remote_dir/wakia_map527_probe.py" >"$local_dir/worker-$scenario.out" &
    probe_pid=$!
    attempt=0
    while ! docker exec "$world_id" test -s "$remote_dir/snapshot-$scenario.json"; do
        if ! kill -0 "$probe_pid" 2>/dev/null; then
            wait "$probe_pid" || :
            cat "$local_dir/worker-$scenario.out" >&2
            printf '%s\n' 'Synthetic fixture failed before producing a snapshot.' >&2
            exit 1
        fi
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 240 ]; then
            printf '%s\n' 'Synthetic fixture timed out.' >&2
            exit 1
        fi
        sleep 0.25
    done
    docker cp "$world_id:$remote_dir/snapshot-$scenario.json" "$local_dir/snapshot.json"
    if [ -n "$export_dir" ]; then
        python3 - "$local_dir/snapshot.json" "$export_dir/wakia-map-$scenario.json" <<'EXPORTCODE'
import shutil, sys
with open(sys.argv[1], 'rb') as source, open(sys.argv[2], 'xb') as target:
    shutil.copyfileobj(source, target)
EXPORTCODE
    fi
    dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- \
        --request "$local_dir/snapshot.json" >"$local_dir/host.out"
    python3 - "$local_dir/host.out" "$local_dir/action.json" <<'PYCODE'
import json, sys
with open(sys.argv[1]) as source:
    rows = [json.loads(line) for line in source if line.startswith('{')]
if len(rows) != 1 or rows[0].get('status') != 200:
    raise SystemExit('Host did not accept the synthetic snapshot')
action = rows[0].get('response', {}).get('action')
if not isinstance(action, dict) or action.get('type') not in ('move', 'cast', 'end_turn'):
    raise SystemExit('Host did not select a supported action')
with open(sys.argv[2], 'w') as target:
    json.dump(action, target)
PYCODE
    docker cp "$local_dir/action.json" "$world_id:$remote_dir/action-$scenario.tmp"
    docker exec "$world_id" mv "$remote_dir/action-$scenario.tmp" "$remote_dir/action-$scenario.json"
    wait "$probe_pid"
    probe_pid=''
    cat "$local_dir/worker-$scenario.out"
done
