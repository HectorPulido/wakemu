#!/usr/bin/env python3
"""Read the loopback inspector without exposing its authentication key."""
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from wakfu_server.profiles import profile_root

root = Path(__file__).resolve().parents[2]
profile = None
if len(sys.argv) > 2 and sys.argv[1] == "--profile":
    profile = sys.argv[2]
    del sys.argv[1:3]
local = profile is not None or (len(sys.argv) > 1 and sys.argv[1] == "--local")
if len(sys.argv) > 1 and sys.argv[1] == "--local":
    del sys.argv[1]
runtime = profile_root(profile) if local else root / ".runtime"
config = json.loads((runtime / "inspector.json").read_text())
action = sys.argv[1] if len(sys.argv) > 1 else "state"
payload = " ".join(sys.argv[2:]).encode() if action == "mark" else None
if action in ("click", "hover", "pick-cell"):
    payload = json.dumps({"x": int(sys.argv[2]), "y": int(sys.argv[3])}).encode()
if action == "drag":
    payload = json.dumps(
        dict(zip(("x", "y", "end_x", "end_y"), map(int, sys.argv[2:6])))
    ).encode()
if action == "double-click":
    action = "click"
    payload = json.dumps(
        {"x": int(sys.argv[2]), "y": int(sys.argv[3]), "count": 2}
    ).encode()
if action == "right-click":
    action = "click"
    payload = json.dumps(
        {"x": int(sys.argv[2]), "y": int(sys.argv[3]), "button": 3}
    ).encode()
if action == "project-cell":
    payload = json.dumps(dict(zip(("x", "y", "z"), map(float, sys.argv[2:5])))).encode()
if action == "combat-actor":
    payload = json.dumps({"actor_id": str(int(sys.argv[2]))}).encode()
if action == "spell-availability":
    payload = json.dumps(
        {
            "actor_id": str(int(sys.argv[2])),
            "spell_uid": str(int(sys.argv[3])),
        }
    ).encode()
if action == "type":
    payload = json.dumps({"text": " ".join(sys.argv[2:]), "submit": True}).encode()
if action == "interactive-registry":
    ids = [int(value, 10) for value in sys.argv[2:]] or [26865, 26842]
    payload = json.dumps({"object_ids": ids}).encode()
req = urllib.request.Request(
    f"http://127.0.0.1:{config['port']}/{action}",
    data=payload,
    headers={"X-Inspector-Key": config["secret"]},
)
if action == "click-actor":
    # Resolve and click in one process so wandering actors cannot make a
    # screenshot's coordinates stale between separate tool calls.
    def inspector_json(endpoint, value=None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{config['port']}/{endpoint}",
            data=json.dumps(value).encode() if value is not None else None,
            headers={"X-Inspector-Key": config["secret"]},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read()

    actor_id = int(sys.argv[2])
    actors = json.loads(inspector_json("actors"))
    actor = next((actor for actor in actors if actor["id"] == actor_id), None)
    if actor is None:
        raise SystemExit(f"Actor {actor_id} is not loaded in this client")
    point = json.loads(
        inspector_json("project-cell", {key: actor[key] for key in ("x", "y", "z")})
    )
    inspector_json(
        "click",
        {
            "x": point["x"],
            "y": point["y"] + (int(sys.argv[3]) if len(sys.argv) > 3 else 0),
            "button": int(sys.argv[4]) if len(sys.argv) > 4 else 1,
        },
    )
    print(f"Clicked actor {actor_id} at ({point['x']}, {point['y']})")
    raise SystemExit(0)
with urllib.request.urlopen(req, timeout=15) as response:
    body = response.read()
if action == "screen":
    path = runtime / "client-screen.png"
    path.write_bytes(body)
    print(path)
else:
    print(body.decode())
