#!/bin/sh
# Exercise the prepared local WakIA image with a native, in-memory fight.
set -eu

case "${1:-native}" in
    native|control|dispatch|shared) mode=${1:-native} ;;
    *) printf '%s\n' 'Usage: wakia-native-probe.sh [native|control|dispatch|shared]' >&2; exit 2 ;;
esac

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
image=$(docker compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["wakia"]["image"])')
name=''
temporary=''
cleanup() {
    if [ -n "$temporary" ]; then
        docker exec "$world_id" python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' "$temporary" >/dev/null 2>&1 || :
    fi
    if [ -n "$name" ]; then
        docker stop "$name" >/dev/null 2>&1 || :
    fi
}
trap cleanup EXIT
# A signal handler that only runs cleanup would then return to the script,
# potentially starting more probe work after the caller requested cancellation.
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if [ "$mode" = dispatch ] || [ "$mode" = shared ]; then
    # Dispatch uses the endpoint pinned by the real selector.
    planner=$(docker compose ps -q wakia)
    if [ -z "$planner" ]; then
        printf '%s\n' 'Local WakIA is not running.' >&2
        exit 1
    fi
    endpoint=tcp://wakia:8091
    probe=native
    dispatch=1
else
    # The playable World and its planner are neither restarted nor renamed.
    name="wakia-probe-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:16])')"
    docker run -d --rm --pull=never --name "$name" --network wakfu-local_isolated "$image" >/dev/null
    planner=$name
    endpoint="tcp://$name:8091"
    probe=$mode
    dispatch=0
fi
temporary=$(docker exec "$world_id" mktemp -d /tmp/wakia-native-probe.XXXXXXXX)
docker cp server/tools/wakia_native_probe.py "$world_id:$temporary/wakia_native_probe.py"
docker cp server/tools/wakia_control_probe.py "$world_id:$temporary/wakia_control_probe.py"
docker cp server/wakfu_server/wakia_bridge/wakfu_ai "$world_id:$temporary/wakfu_ai"
ready=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if docker exec "$planner" dotnet WakIA.dll --health >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
if [ "$ready" != 1 ]; then
    printf '%s\n' 'Prepared WakIA service did not become ready.' >&2
    exit 1
fi
printf '%s\n' 'Using the running local World engine and the current source bridge.' >&2
docker exec -e PYTHONPATH=/app \
    -e WAKFU_COMBAT_INCIDENT_DIR= \
    -e "WAKIA_PROBE_ENDPOINT=$endpoint" \
    -e "WAKIA_PROBE_DISPATCH=$dispatch" \
    -e "WAKIA_PROBE_SHARED=$([ "$mode" = shared ] && printf 1 || printf 0)" \
    -e "WAKFU_LEGACY_AI_SDK_DIR=/nonexistent/wakia-no-legacy" \
    -e "WAKIA_PROBE_BRIDGE=$temporary/wakfu_ai" \
    "$world_id" python3 "$temporary/wakia_${probe}_probe.py"
