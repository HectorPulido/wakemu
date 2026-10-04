#!/usr/bin/env python3
"""Save only the Zaap parameters of a Wakfu process started by the launcher."""
import json
import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parent.parent
rows = subprocess.check_output(["ps", "-axo", "pid,comm"], text=True).splitlines()[1:]
found = []
for row in rows:
    parts = row.strip().split(None, 1)
    if len(parts) != 2 or not parts[1].endswith("/java"):
        continue
    pid = int(parts[0])
    command = subprocess.check_output(
        ["ps", "-p", str(pid), "-o", "command="], text=True
    )
    if "com.ankamagames.wakfu.client.WakfuClient" not in command:
        continue
    env = subprocess.check_output(
        ["ps", "eww", "-p", str(pid), "-o", "command="], text=True
    )
    params = dict(re.findall(r"(?:^|\s)(ZAAP_[A-Z_]+)=([^\s]*)", env))
    if (
        params.get("ZAAP_GAME") == "wakfu"
        and params.get("ZAAP_HASH")
        and params.get("ZAAP_PORT") == "26116"
    ):
        found.append((pid, params))
if not found:
    raise SystemExit(
        "No hay un cliente Wakfu iniciado por el launcher en el puerto 26116."
    )
pid, params = max(found)
path = root / ".runtime/launcher-environment.json"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w") as out:
    json.dump(params, out)
print(f"Entorno Zaap guardado desde PID {pid}; valores omitidos.")
