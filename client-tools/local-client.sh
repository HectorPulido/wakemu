#!/bin/bash
set -euo pipefail
umask 077
experiment_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$experiment_dir"
export PYTHONPATH="$experiment_dir/server${PYTHONPATH:+:$PYTHONPATH}"
check_only=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) export WAKFU_LOCAL_PROFILE="$2"; shift 2 ;;
    --token-file) export WAKFU_GAME_LOGIN_FILE="$2"; shift 2 ;;
    --check) check_only=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ -n "${WAKFU_LAUNCHER_CONFIG:-}" ]] && python3 -c 'import json,os,sys; sys.exit("server_host" not in json.load(open(os.environ["WAKFU_LAUNCHER_CONFIG"])))'; then
  args=()
  if [[ "$check_only" == "1" ]]; then args+=(--check); fi
  exec python3 "$experiment_dir/client-tools/runtime/run-configured-client.py" ${args[@]+"${args[@]}"}
fi
mkdir -p .runtime/local/classes .runtime/local/logs
python3 client-tools/runtime/prepare-local-client.py
jdk_dir="$(/usr/libexec/java_home -v '21+' 2>/dev/null)"
"$jdk_dir/bin/javac" -proc:none --release 21 -d .runtime/local/classes client-tools/java/LocalNetworkGuard.java client-tools/java/LocalNetworkGuardTest.java
printf 'Manifest-Version: 1.0\nPremain-Class: LocalNetworkGuard\n\n' > .runtime/local/guard-manifest.mf
"$jdk_dir/bin/jar" cfm .runtime/local/network-guard.jar .runtime/local/guard-manifest.mf -C .runtime/local/classes LocalNetworkGuard.class
"$jdk_dir/bin/javac" -proc:none -source 21 -target 21 \
  --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  -d .runtime/local/classes client-tools/java/LocalDesktopFix.java
printf 'Manifest-Version: 1.0\nPremain-Class: LocalDesktopFix\n\n' > .runtime/local/desktop-manifest.mf
"$jdk_dir/bin/jar" cfm .runtime/local/desktop-fix.jar .runtime/local/desktop-manifest.mf -C .runtime/local/classes .
bash client-tools/runtime/build-open-planting-agent.sh
export WAKFU_OPEN_PLANTING="$(python3 - <<'PYCFG'
import json,os
from pathlib import Path
p=os.environ.get("WAKFU_LAUNCHER_CONFIG")
v=json.loads(Path(p).read_text()).get("open_planting",True) if p else os.environ.get("WAKFU_OPEN_PLANTING","true").lower() in ("1", "true", "yes")
if type(v) is not bool: raise ValueError("open_planting must be boolean")
print(str(v).lower())
PYCFG
)"
bash sniffer/build-capture-agent.sh
unset _JAVA_OPTIONS JAVA_TOOL_OPTIONS JDK_JAVA_OPTIONS HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
LOCAL_TEST_JAVA="$experiment_dir/client/jre/Contents/Home/bin/java" python3 client-tools/runtime/verify-local-network.py
if [[ "$check_only" == "1" ]]; then exit 0; fi
if [[ -z "${WAKFU_GAME_LOGIN_FILE:-}" ]]; then
  python3 client-tools/runtime/local-login.py
  export WAKFU_GAME_LOGIN_FILE="$(python3 -c 'from wakfu_server.profiles import profile_root; print(profile_root()/"login-session.json")')"
fi
exec /usr/bin/sandbox-exec -f "$experiment_dir/client-tools/runtime/local-network.sb" python3 client-tools/runtime/local-launcher-bridge.py
