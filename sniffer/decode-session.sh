#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
JAVA_HOME_TASK=/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home
CAPTURE_TASK="${1:?Usage: ./decode-session.sh path/to/capture-directory}"
mkdir -p .runtime/classes
"$JAVA_HOME_TASK/bin/javac" -proc:none -source 21 -target 21 --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED -cp 'client/lib/*' -d .runtime/classes sniffer/java/ProtocolCatalog.java
"$JAVA_HOME_TASK/bin/java" --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED -cp '.runtime/classes:client/lib/*' ProtocolCatalog client/lib/wakfu-client.jar .runtime/protocol-catalog.json
"$JAVA_HOME_TASK/bin/javac" -proc:none --release 21 -cp 'client/lib/*' -d .runtime/classes sniffer/java/OfflineMessageDecoder.java sniffer/java/VerifyCapturedEncoders.java sniffer/java/ExportProtocolDescriptors.java
"$JAVA_HOME_TASK/bin/java" -cp '.runtime/classes:client/lib/*' ExportProtocolDescriptors .runtime/protocol-catalog.json server/protocol/descriptors.pb server/protocol/descriptors.json
python3 sniffer/decode-capture.py "$CAPTURE_TASK"
python3 - "$CAPTURE_TASK" <<'PY'
import json,sys
from pathlib import Path
capture=Path(sys.argv[1])
classes=sorted({r['class'] for line in (capture/'events.jsonl').open() if (r:=json.loads(line)).get('direction')=='in' and r.get('stage')=='aTm#0'})
(capture/'decoded/observed-classes.json').write_text(json.dumps(classes))
PY
"$JAVA_HOME_TASK/bin/java" -Djava.awt.headless=true -cp '.runtime/classes:client/lib/*' OfflineMessageDecoder .runtime/protocol-catalog.json "$CAPTURE_TASK/decoded/frames.jsonl" "$CAPTURE_TASK/decoded/observed-classes.json" "$CAPTURE_TASK/decoded/inbound.jsonl" > .runtime/offline-decode.log 2>&1
"$JAVA_HOME_TASK/bin/java" -Djava.awt.headless=true -cp '.runtime/classes:client/lib/*' VerifyCapturedEncoders "$CAPTURE_TASK/decoded/frames.jsonl"
python3 sniffer/summarize-protocol.py "$CAPTURE_TASK"
