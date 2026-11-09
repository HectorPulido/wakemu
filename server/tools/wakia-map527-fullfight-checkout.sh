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

case "${1:-all}" in
    all) scenarios='455 456' ;;
    455|456) scenarios=$1 ;;
    *) printf '%s\n' 'Usage: wakia-map527-fullfight-checkout.sh [455|456|all]' >&2; exit 2 ;;
esac
remote_dir=''
local_dir=$(mktemp -d "${TMPDIR:-/tmp}/wakia-fullfight.XXXXXXXX")
host_pid=''
probe_pid=''
cleanup() {
    if [ -n "$probe_pid" ]; then kill "$probe_pid" >/dev/null 2>&1 || :; fi
    if [ -n "$host_pid" ]; then kill "$host_pid" >/dev/null 2>&1 || :; fi
    if [ -n "$remote_dir" ]; then docker exec "$world_id" rm -rf "$remote_dir" >/dev/null 2>&1 || :; fi
    rm -rf "$local_dir"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
remote_dir=$(docker exec "$world_id" mktemp -d /tmp/wakia-fullfight.XXXXXXXX)
docker cp server/tools/wakia_native_probe.py "$world_id:$remote_dir/wakia_native_probe.py"
docker cp server/tools/wakia_map527_fullfight.py "$world_id:$remote_dir/wakia_map527_fullfight.py"
docker cp server/wakfu_server/wakia_bridge/wakfu_ai "$world_id:$remote_dir/wakfu_ai"
docker cp server/wakfu_server/combat/combat_walk_surface_policy.py "$world_id:$remote_dir/combat_walk_surface_policy.py"
dotnet build server/ai-jondo-service/HostStream/WakIA.HostStream.csproj -c Release --nologo >&2
mkfifo "$local_dir/in" "$local_dir/out"
exec 3<>"$local_dir/in"
exec 4<>"$local_dir/out"
dotnet server/ai-jondo-service/HostStream/bin/Release/net8.0/WakIA.HostStream.dll <"$local_dir/in" >"$local_dir/out" &
host_pid=$!
for scenario in $scenarios; do
    docker exec "$world_id" sh -c 'rm -f "$1"/request-*.json "$1"/response-*.json' sh "$remote_dir"
    docker exec -e "PYTHONPATH=/app:$remote_dir" -e "WAKIA_PROBE_DIR=$remote_dir" \
        -e "WAKIA_MAP527_SCENARIO=$scenario" -e WAKIA_PLANNER_TRANSPORT=file "$world_id" \
        python3 "$remote_dir/wakia_map527_fullfight.py" >"$local_dir/fight-$scenario.out" &
    probe_pid=$!
    request=1
    while kill -0 "$probe_pid" 2>/dev/null; do
        if ! kill -0 "$host_pid" 2>/dev/null; then
            printf '%s\n' 'Isolated C# host exited.' >&2; exit 1
        fi
        if docker exec "$world_id" test -s "$remote_dir/request-$request.json"; then
            docker cp "$world_id:$remote_dir/request-$request.json" "$local_dir/request.json"
            cat "$local_dir/request.json" >&3
            printf '\n' >&3
            IFS= read -r host_response <&4
            printf '%s\n' "$host_response" >"$local_dir/response.json"
            docker cp "$local_dir/response.json" "$world_id:$remote_dir/response-$request.tmp"
            docker exec "$world_id" mv "$remote_dir/response-$request.tmp" "$remote_dir/response-$request.json"
            request=$((request + 1))
        else
            sleep 0.1
        fi
    done
    if wait "$probe_pid"; then
        probe_pid=''
        cat "$local_dir/fight-$scenario.out"
    else
        probe_pid=''
        cat "$local_dir/fight-$scenario.out" >&2
        exit 1
    fi
done
