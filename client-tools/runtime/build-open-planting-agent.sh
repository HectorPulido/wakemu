#!/bin/bash
set -euo pipefail
experiment_dir="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$experiment_dir"
planting_jdk="$(/usr/libexec/java_home -v '21+' 2>/dev/null)"
mkdir -p .runtime/local/open-planting-classes
PYTHONPATH=server python3 server/tools/build_dungeon_entry_overrides.py
cp client-tools/runtime/dungeon-entry-overrides.properties .runtime/local/open-planting-classes/
"$planting_jdk/bin/javac" -proc:none -source 21 -target 21 \
 --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
 -d .runtime/local/open-planting-classes client-tools/java/OpenPlantingAgent.java
printf 'Manifest-Version: 1.0\nPremain-Class: OpenPlantingAgent\n\n' > .runtime/local/open-planting-manifest.mf
"$planting_jdk/bin/jar" cfm .runtime/local/open-planting.jar \
 .runtime/local/open-planting-manifest.mf -C .runtime/local/open-planting-classes .
