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

character_name=''
monster_level=''
monster_ref=1
timeout_seconds=180
while [ "$#" -gt 0 ]; do
    case "$1" in
        --character) [ "$#" -ge 2 ] || exit 2; character_name=$2; shift 2 ;;
        --monster-level) [ "$#" -ge 2 ] || exit 2; monster_level=$2; shift 2 ;;
        --monster-ref) [ "$#" -ge 2 ] || exit 2; monster_ref=$2; shift 2 ;;
        --timeout) [ "$#" -ge 2 ] || exit 2; timeout_seconds=$2; shift 2 ;;
        *) printf '%s\n' 'Usage: wakia-real-character-private-probe.sh --character NAME [--monster-ref ID] [--monster-level LEVEL] [--timeout SECONDS]' >&2; exit 2 ;;
    esac
done
if [ -z "$character_name" ]; then
    printf '%s\n' 'A character name is required.' >&2; exit 2
fi
case "$monster_ref" in
    ''|*[!0-9]*) printf '%s\n' 'Monster reference must be a positive integer.' >&2; exit 2 ;;
esac
if [ "$monster_ref" -lt 1 ] || [ "$monster_ref" -gt 2147483647 ]; then
    printf '%s\n' 'Monster reference must be a positive 32-bit integer.' >&2; exit 2
fi
case "$timeout_seconds" in
    ''|*[!0-9]*) printf '%s\n' 'Timeout must be an integer between 1 and 3600 seconds.' >&2; exit 2 ;;
esac
if [ "$timeout_seconds" -lt 1 ] || [ "$timeout_seconds" -gt 3600 ]; then
    printf '%s\n' 'Timeout must be an integer between 1 and 3600 seconds.' >&2; exit 2
fi
umask 077
export WAKIA_CHARACTER_NAME="$character_name"
remote_dir=''
local_dir=$(mktemp -d "${TMPDIR:-/tmp}/wakia-real-fight.XXXXXXXX")
host_pid=''
probe_pid=''
watchdog_pid=''
cleanup() {
    if [ -n "$watchdog_pid" ]; then kill "$watchdog_pid" >/dev/null 2>&1 || :; fi
    if [ -n "$remote_dir" ]; then
        docker exec -i "$world_id" python3 - "$remote_dir" "$probe_pid" >/dev/null 2>&1 <<'STOPCODE' || :
import json, os, signal, sys, time
from pathlib import Path
root = Path(sys.argv[1])
try:
    identity_path = root / 'worker-identity.json'
    # A worker can be starting just as a timeout arrives. Give its own
    # identity registration a bounded opportunity before removing the workspace.
    deadline = time.monotonic() + 2
    while sys.argv[2] and not identity_path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    identity = json.loads(identity_path.read_text())
    pid = identity['pid']
    if type(pid) is not int or pid <= 1:
        raise ValueError('Invalid worker identity')
    expected = str(root / 'wakia_real_character_private_probe.py').encode()
    def same_worker():
        try:
            stat = Path(f'/proc/{pid}/stat').read_text().split()
            command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            return stat[21] == identity['start'] and stat[2] != 'Z' and expected in command
        except (OSError, IndexError):
            return False
    if same_worker():
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 2
        while same_worker() and time.monotonic() < deadline:
            time.sleep(0.02)
        if same_worker():
            os.kill(pid, signal.SIGKILL)
except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
    pass
STOPCODE
    fi
    if [ -n "$probe_pid" ]; then kill "$probe_pid" >/dev/null 2>&1 || :; fi
    if [ -n "$host_pid" ]; then kill "$host_pid" >/dev/null 2>&1 || :; fi
    if [ -n "$remote_dir" ]; then docker exec "$world_id" rm -rf "$remote_dir" >/dev/null 2>&1 || :; fi
    rm -rf "$local_dir"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
remote_dir=$(docker exec "$world_id" mktemp -d /tmp/wakia-real-fight.XXXXXXXX)
python3 - "$$" "$timeout_seconds" <<'WATCHCODE' &
import os, signal, sys, time
time.sleep(int(sys.argv[2]))
os.kill(int(sys.argv[1]), signal.SIGTERM)
WATCHCODE
watchdog_pid=$!
docker cp server/tools/wakia_native_probe.py "$world_id:$remote_dir/wakia_native_probe.py"
docker cp server/tools/wakia_real_character_private_probe.py "$world_id:$remote_dir/wakia_real_character_private_probe.py"
docker cp server/wakfu_server/wakia_bridge/wakfu_ai "$world_id:$remote_dir/wakfu_ai"
dotnet build server/ai-jondo-service/HostStream/WakIA.HostStream.csproj -c Release --nologo >&2
mkfifo "$local_dir/in" "$local_dir/out"
exec 3<>"$local_dir/in"
exec 4<>"$local_dir/out"
dotnet server/ai-jondo-service/HostStream/bin/Release/net8.0/WakIA.HostStream.dll <"$local_dir/in" >"$local_dir/out" &
host_pid=$!
docker exec -e "PYTHONPATH=/app:$remote_dir" -e "WAKIA_PROBE_DIR=$remote_dir" \
    -e WAKIA_CHARACTER_NAME -e "WAKIA_MONSTER_REF=$monster_ref" -e "WAKIA_MONSTER_LEVEL=$monster_level" "$world_id" \
    python3 "$remote_dir/wakia_real_character_private_probe.py" >"$local_dir/fight.out" 2>"$local_dir/fight.err" &
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
    cat "$local_dir/fight.out"
else
    probe_pid=''
    cat "$local_dir/fight.out" >&2
    printf '%s\n' 'Private simulation failed; detailed runtime logs were not exported.' >&2
    exit 1
fi
