#!/bin/bash
set -euo pipefail
umask 077
experiment_dir="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
if [[ -n "${WAKFU_AGENT_ROOT:-}" ]]; then
  exec python3 "$experiment_dir/client-tools/dropin/run-client.py" --use-local-auth --profile "${WAKFU_LOCAL_PROFILE:-main}"
fi
export PYTHONPATH="$experiment_dir/server${PYTHONPATH:+:$PYTHONPATH}"
runtime_dir="$(python3 -c 'from wakfu_server.profiles import profile_root; print(profile_root())')"
agents_dir="$experiment_dir/.runtime/local"
mkdir -p "$runtime_dir/preferences" "$runtime_dir/cache" "$runtime_dir/logs"
export WAKFU_LANGUAGE=es
export WAKFU_PREF_FILE_DIRECTORY="$runtime_dir/preferences"
export WAKFU_CACHE_FILE_DIRECTORY="$runtime_dir/cache"
if [[ "${1:-}" == "--use-local-auth" ]]; then
  shift
  : "${ZAAP_PORT:?Missing local bridge}" "${ZAAP_HASH:?Missing local bridge hash}"
else
  unset ZAAP_PORT ZAAP_HASH ZAAP_INSTANCE_ID ZAAP_GAME ZAAP_RELEASE
fi
unset _JAVA_OPTIONS JAVA_TOOL_OPTIONS JDK_JAVA_OPTIONS HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
cd "$runtime_dir/client"
exec /usr/bin/sandbox-exec -f "$experiment_dir/client-tools/runtime/local-network.sb" ./jre/Contents/Home/bin/java \
  -Djava.security.manager=allow \
  "-javaagent:$agents_dir/network-guard.jar=$runtime_dir/logs/network-blocked.log" \
  --add-exports=java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  "-javaagent:$agents_dir/desktop-fix.jar" \
  "-Dwakfu.local.openPlanting=${WAKFU_OPEN_PLANTING:-true}" \
  "-javaagent:$agents_dir/open-planting.jar" \
  "-javaagent:$experiment_dir/.runtime/capture-agent.jar=$runtime_dir/captures" \
  -Xms512m -Xmx2G -Djava.net.preferIPv4Stack=true \
  -Dsun.awt.noerasebackground=true -Dsun.java2d.noddraw=true \
  -Djogl.disable.openglarbcontext -Dsun.java2d.metal=false -Dsun.java2d.opengl=true \
  --add-opens=java.desktop/sun.awt=ALL-UNNAMED \
  --add-opens=java.desktop/com.apple.eawt=ALL-UNNAMED \
  -Dsun.java2d.uiScale.enabled=true -Djava.library.path=natives/ \
  @classpath com.ankamagames.wakfu.client.WakfuClient \
  --partner=default --install-folder . \
  -p "$runtime_dir/preferences" -n "$runtime_dir/cache" -L es \
  "$@" >> "$runtime_dir/logs/client-console.log" 2>&1
