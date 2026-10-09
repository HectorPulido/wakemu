#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$project_dir"
ui_jdk="$(/usr/libexec/java_home -v '21+')"
mkdir -p .runtime/ui-agent-classes
"$ui_jdk/bin/javac" -proc:none --release 21 -cp 'client/lib/*' \
  -d .runtime/ui-agent-classes sniffer/java/AttachAgent.java sniffer/java/UiSnapshotAgent.java
printf 'Manifest-Version: 1.0\nAgent-Class: UiSnapshotAgent\n\n' > .runtime/ui-agent-manifest.mf
"$ui_jdk/bin/jar" cfm .runtime/ui-agent.jar .runtime/ui-agent-manifest.mf \
  -C .runtime/ui-agent-classes .
