#!/usr/bin/env python3
"""Send a normal left mouse click to the client's canvas (logical coordinates)."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
rows = subprocess.check_output(["ps", "-axo", "pid,comm"], text=True).splitlines()[1:]
clients = [
    row.strip().split(None, 1)[0]
    for row in rows
    if row.strip().endswith("./jre/Contents/Home/bin/java")
]
if len(clients) != 1:
    raise SystemExit("Expected one experiment client.")
args = str(root / ".runtime")
if len(sys.argv) == 3:
    x, y = map(int, sys.argv[1:])
    args += f"|click|{x}|{y}"
elif len(sys.argv) == 4 and sys.argv[1] == "resize":
    args += f"|resize|{int(sys.argv[2])}|{int(sys.argv[3])}"
subprocess.run(
    ["bash", str(root / "client-tools/runtime/build-ui-agent.sh")], check=True
)
jdk = subprocess.check_output(
    ["/usr/libexec/java_home", "-v", "21+"], text=True
).strip()
subprocess.run(
    [
        str(Path(jdk) / "bin/java"),
        "-cp",
        str(root / ".runtime/ui-agent-classes"),
        "AttachAgent",
        clients[0],
        str(root / ".runtime/ui-agent.jar"),
        args,
    ],
    check=True,
)
