#!/bin/bash
set -euo pipefail
umask 077
experiment_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$experiment_dir"
mkdir -p .runtime/agent-classes
if [[ -n "${JAVA_HOME:-}" ]]; then
  jdk_dir="$JAVA_HOME"
elif [[ "$(uname -s)" == "Darwin" ]]; then
  jdk_dir="$(/usr/libexec/java_home -v '21+' 2>/dev/null)"
else
  javac_path="$(command -v javac)" || { echo "Install JDK 21+ or set JAVA_HOME" >&2; exit 1; }
  jdk_dir="$(dirname "$(dirname "$(readlink -f "$javac_path")")")"
fi
"$jdk_dir/bin/javac" -proc:none -source 21 -target 21 \
  --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  -cp 'client/lib/*' -d .runtime/agent-classes sniffer/java/CaptureAgent.java sniffer/java/NativeSpellAvailability.java sniffer/java/NativeSpellPreflight.java sniffer/java/NativeMovementStop.java
printf 'Manifest-Version: 1.0\nPremain-Class: CaptureAgent\n\n' > .runtime/capture-agent-manifest.mf
"$jdk_dir/bin/jar" cfm .runtime/capture-agent.jar .runtime/capture-agent-manifest.mf -C .runtime/agent-classes .
