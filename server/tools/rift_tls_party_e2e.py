"""Opt-in live Rift protocol scenarios on newly created QA accounts only.

The peer uses the real HTTP/dispatcher/World path. It does not replace the
official-client acceptance lane: packets are recorded, not rendered here.
No server restart, direct ticket minting, forged victory or player-state replay.
"""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request

from protocol_codec import DIRECTIONS


def text(value):
    raw = value.encode()
    return struct.pack(">I", len(raw)) + raw


class Peer:
    def __init__(self, host, port):
        self.socket = ssl._create_unverified_context().wrap_socket(
            socket.create_connection((host, port), timeout=15),
            server_hostname="localhost",
        )
        self.socket.settimeout(0.1)
        self.io_lock = threading.Lock()
        self.tls = self.socket.version()
        self.events, self.pending = queue.Queue(), []
        self.closed = False
        self.failure = None
        self.seen, self.sent = [], []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def exact(self, count):
        result = bytearray()
        while len(result) < count:
            try:
                with self.io_lock:
                    value = self.socket.recv(count - len(result))
            except TimeoutError:
                if self.closed:
                    raise EOFError("QA peer closed")
                time.sleep(0)
                continue
            if not value:
                raise EOFError("World closed the QA TLS connection")
            result.extend(value)
        return bytes(result)

    def _read(self):
        try:
            while not self.closed:
                size = struct.unpack(">I", self.exact(4))[0]
                if not 6 <= size <= 327670:
                    raise ValueError("Invalid native server frame length")
                packet = self.exact(size - 4)
                opcode = struct.unpack_from(">H", packet)[0]
                self.seen.append(opcode)
                self.events.put((opcode, packet[2:]))
        except BaseException as error:
            if not self.closed:
                self.failure = error
                self.events.put((None, error))

    def send(self, opcode, body=b""):
        self.sent.append(opcode)
        with self.io_lock:
            self.socket.sendall(struct.pack(">IBH", 7 + len(body), 3, opcode) + body)

    def wait(self, opcodes, timeout=45):
        wanted = {opcodes} if isinstance(opcodes, int) else set(opcodes)
        for index, (opcode, body) in enumerate(self.pending):
            if opcode in wanted:
                del self.pending[index]
                return opcode, body
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                opcode, body = self.events.get(
                    timeout=max(0.01, until - time.monotonic())
                )
            except queue.Empty:
                break
            if opcode is None:
                raise body
            if opcode in wanted:
                return opcode, body
            self.pending.append((opcode, body))
        raise TimeoutError(
            f"Missing native opcode {sorted(wanted)}; last={self.seen[-20:]}"
        )

    def close(self):
        self.closed = True
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
        self.reader.join(timeout=1)


def post(args, path, value, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        args.http_url + path,
        data=json.dumps(value).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def ticket(args, token):
    peer = Peer(args.host, args.dispatcher_port)
    try:
        peer.send(574)
        public = peer.wait(400)[1]
        raw = token.encode()
        clear = struct.pack(">qB", struct.unpack_from(">q", public)[0], len(raw)) + raw
        with tempfile.TemporaryDirectory(prefix="rift-qa-auth-") as directory:
            key = Path(directory) / "public.der"
            key.write_bytes(public[8:])
            encrypted = subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-encrypt",
                    "-pubin",
                    "-keyform",
                    "DER",
                    "-inkey",
                    str(key),
                    "-pkeyopt",
                    "rsa_padding_mode:pkcs1",
                ],
                input=clear,
                capture_output=True,
                check=True,
            ).stdout
        peer.send(584, struct.pack(">I", len(encrypted)) + encrypted)
        peer.wait(472)
        peer.send(402)
        peer.wait(453)
        peer.send(575, struct.pack(">iB", 10, 0))
        payload = peer.wait(466)[1]
        if payload[0] != 0:
            raise ValueError("Dispatcher rejected QA realm selection")
        size = struct.unpack_from(">I", payload, 1)[0]
        return payload[5 : 5 + size].decode()
    finally:
        peer.close()


def connect(args, owner, *, reconnect=False):
    login = post(args, "/login", {key: owner[key] for key in ("username", "password")})
    peer = Peer(args.host, args.world_port)
    peer.send(426, text(ticket(args, login["game_token"])) + text("rift-e2e-qa"))
    peer.wait(13873)
    character = owner["character"]
    peer.send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
    if not reconnect:
        peer.wait(630)
        peer.wait(711)
        peer.send(12449)
        peer.wait(12436)
        peer.wait(711)
        peer.send(12449)
        peer.wait(711)
    return peer


def observe(args, request):
    """Use the existing World image for bounded source/DB observations/setup."""
    script = r"""
import json,os,sys
from wakfu_server.store import Store
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.command_permissions import set_admin
request=json.load(sys.stdin)
store=Store(os.environ['WAKFU_DATABASE_URL'],password_file=os.environ.get('WAKFU_DATABASE_PASSWORD_FILE'))
try:
 with store.connection() as db:
  catalog=db.execute("SELECT value FROM settings WHERE name='rift_catalog'").fetchone()['value'][str(request['wave'])]
  if request['operation']=='catalog':
   print(json.dumps(catalog))
  elif request['operation']=='geometry':
   geometry=published_geometry(request['map_id'])
   print(json.dumps({'cells':sorted(geometry.cells),'edges':[[a,b] for a,rows in geometry.outgoing.items() for b in rows]}))
  elif request['operation']=='setup':
   account=db.execute('SELECT username FROM accounts WHERE id=%s',(request['account_id'],)).fetchone()
   if account is None or not account['username'].startswith('rfnetqa_'):
    raise ValueError('Only newly named transport QA accounts may be prepared')
   set_admin(store,request['account_id'],True,operator='rift-transport-e2e',reason='isolated QA account only')
   generation=store.begin_session(request['account_id'])
   store.select_character(request['account_id'],generation,request['character_id'])
   current=store.character(request['account_id'],request['character_id'],db)
   portal=catalog['entrances'][0]
   geometry=published_geometry(portal['map_id'])
   points=sorted((p for p in geometry.cells if max(abs(p[0]-portal['x']),abs(p[1]-portal['y']))<=2),key=lambda p:(abs(p[0]-portal['x'])+abs(p[1]-portal['y']),abs(p[2]-portal['z']),p))
   point=points[request['index']%len(points)]
   store.transition_map_in_transaction(db,request['account_id'],generation,request['character_id'],current,dict(map_id=portal['map_id'],instance_id=0,x=point[0],y=point[1],z=point[2]))
   print(json.dumps({'character_id':request['character_id'],'approach':point}))
  elif request['operation']=='state':
   ids=request['character_ids']
   characters=db.execute('SELECT id,account_id,level,map_id,instance_id,x,y,z,hp,max_hp FROM characters WHERE id=ANY(%s) ORDER BY id',(ids,)).fetchall()
   runs=db.execute('SELECT instance_id,fight_id,status,wave,completed_waves,defeated_monsters,members FROM rift_instances WHERE owner_character_id=%s ORDER BY instance_id DESC LIMIT 1',(ids[0],)).fetchall()
   result={'characters':characters,'runs':runs}
   if runs and runs[0]['fight_id']:
    result['fight']=db.execute('SELECT status FROM combat_fights WHERE id=%s',(runs[0]['fight_id'],)).fetchone()
    result['members']=db.execute('SELECT account_id,character_id,team FROM combat_fight_participants WHERE fight_id=%s ORDER BY character_id',(runs[0]['fight_id'],)).fetchall()
   print(json.dumps(result,default=str))
  elif request['operation']=='combat':
   row=db.execute('SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s',(request['fight_id'],)).fetchone()
   if row is None: raise ValueError('Missing actual fight checkpoint')
   saved=row['snapshot']
   fields=('id','phase','winner','turn_id','native_timeline_round','rift_wave_state','runtime')
   result={name:saved.get(name) for name in fields}
   result['actors']={identity:{name:actor.get(name) for name in ('id','team','controlled','owner_id','position','hp','ap','mp','turn_count','native_obstacle_id')} for identity,actor in saved['actors'].items()}
   print(json.dumps(result,default=str))
finally:store.close()
"""
    command = [
        "docker",
        "exec",
        "-i",
        "-e",
        "PYTHONPATH=/app",
        args.container,
        "python3",
        "-c",
        script,
    ]
    result = subprocess.run(
        command, input=json.dumps(request), capture_output=True, text=True, timeout=45
    )
    if result.returncode:
        raise RuntimeError("QA source observer failed: " + result.stderr[-1800:])
    return json.loads(result.stdout)


def walk(peer, geometry, start, target):
    goals = {
        tuple(cell)
        for cell in geometry["cells"]
        if max(abs(cell[0] - target["x"]), abs(cell[1] - target["y"])) <= 2
        and abs(cell[2] - target["z"]) <= 2
    }
    outgoing = {}
    for a, b in geometry["edges"]:
        outgoing.setdefault(tuple(a), []).append(tuple(b))
    pending, previous = deque([tuple(start)]), {tuple(start): None}
    while pending:
        point = pending.popleft()
        if point in goals:
            route = []
            while previous[point] is not None:
                route.append(point)
                point = previous[point]
            route.reverse()
            break
        for point_b in outgoing.get(point, ()):
            if point_b not in previous:
                previous[point_b] = point
                pending.append(point_b)
    else:
        raise ValueError("No original native route to the Rift activator")
    directions = {(x, y): key for key, (_, x, y) in DIRECTIONS.items()}
    if route:
        steps, point = bytearray(), tuple(start)
        for end in route:
            dx, dy, dz = end[0] - point[0], end[1] - point[1], end[2] - point[2]
            if not -16 <= dz <= 15:
                raise ValueError("Native walk altitude exceeds packet bound")
            steps.append((directions[(dx, dy)] << 5) | (dz & 31))
            point = end
        peer.send(13331, struct.pack(">iiihB", 0, *start, len(steps)) + steps)
    return route[-1] if route else tuple(start)


def combat_route(geometry, current, target, blocked, maximum):
    outgoing = {}
    for a, b in geometry["edges"]:
        outgoing.setdefault(tuple(a), []).append(tuple(b))
    queue_, previous = deque([tuple(current)]), {tuple(current): None}
    goal = None
    while queue_:
        position = queue_.popleft()
        if abs(position[0] - target[0]) + abs(position[1] - target[1]) == 1:
            goal = position
            break
        for destination in outgoing.get(position, ()):
            if destination not in previous and destination not in blocked:
                previous[destination] = position
                queue_.append(destination)
    if goal is None:
        return []
    route = []
    while previous[goal] is not None:
        route.append(goal)
        goal = previous[goal]
    return list(reversed(route))[:maximum]


def battle(args, peers, owners, geometry, fight_id, first_turn, result):
    """Real movement, ordinary unarmed attacks and actual turn ACKs only."""
    peer_by_owner = {owner["account_id"]: peer for owner, peer in zip(owners, peers)}
    current = first_turn
    boundaries = 0
    while boundaries < args.max_turns:
        actor_id = struct.unpack_from(">q", current, 12)[0]
        checkpoint = observe(
            args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
        )
        if checkpoint["phase"] == "finished":
            break
        actor = checkpoint["actors"].get(str(actor_id))
        if actor is None:
            raise ValueError("Turn actor missing from the durable checkpoint")
        if actor["controlled"] and actor["hp"] > 0:
            peer = peer_by_owner[actor["owner_id"]]
            should_attack = (
                args.phase == "battle"
                and checkpoint["rift_wave_state"]["wave"] < args.target_wave
            )
            if should_attack:
                targets = [
                    row
                    for row in checkpoint["actors"].values()
                    if row["team"] != actor["team"] and row["hp"] > 0
                ]
                if targets:
                    target = min(
                        targets,
                        key=lambda row: (
                            abs(row["position"][0] - actor["position"][0])
                            + abs(row["position"][1] - actor["position"][1]),
                            row["id"],
                        ),
                    )
                    blocked = {
                        tuple(row["position"])
                        for row in checkpoint["actors"].values()
                        if row["id"] != actor_id
                        and row["native_obstacle_id"] is not None
                        and row["native_obstacle_id"] >= 0
                    }
                    route = combat_route(
                        geometry,
                        actor["position"],
                        target["position"],
                        blocked,
                        actor["mp"],
                    )
                    if route:
                        peer.send(
                            12161,
                            struct.pack(">q", actor_id)
                            + b"".join(struct.pack(">iih", *point) for point in route),
                        )
                        peers[0].wait({13624, 13420})
                        checkpoint = observe(
                            args,
                            dict(operation="combat", wave=args.wave, fight_id=fight_id),
                        )
                        actor = checkpoint["actors"][str(actor_id)]
                    for _ in range(8):
                        living = [
                            row
                            for row in checkpoint["actors"].values()
                            if row["team"] != actor["team"]
                            and row["hp"] > 0
                            and abs(row["position"][0] - actor["position"][0])
                            + abs(row["position"][1] - actor["position"][1])
                            == 1
                        ]
                        if not living or actor["ap"] < 2:
                            break
                        target = min(living, key=lambda row: row["id"])
                        before = (actor["ap"], target["hp"])
                        peer.send(
                            12889,
                            struct.pack(
                                ">qqbiih", actor_id, -1, 15, *target["position"]
                            ),
                        )
                        time.sleep(0.15)
                        checkpoint = observe(
                            args,
                            dict(operation="combat", wave=args.wave, fight_id=fight_id),
                        )
                        if checkpoint["phase"] == "finished":
                            break
                        actor = checkpoint["actors"][str(actor_id)]
                        if before == (
                            actor["ap"],
                            checkpoint["actors"][str(target["id"])]["hp"],
                        ):
                            raise ValueError(
                                "Native unarmed action did not change AP or target HP"
                            )
            if checkpoint["phase"] != "finished":
                peer.send(
                    12403,
                    struct.pack(">qh", actor_id, checkpoint["native_timeline_round"]),
                )
        opcode, packet = peers[0].wait({12502, 12755}, timeout=90)
        if opcode == 12755:
            result["terminal_report_received"] = True
            break
        checkpoint = observe(
            args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
        )
        counter = checkpoint["runtime"].get("awaiting_ack")
        if type(counter) is not int:
            raise ValueError(
                "Actual native turn boundary lacks its durable ACK counter"
            )
        for peer in peers:
            peer.send(13510, struct.pack(">i", counter))
        opcode, current = peers[0].wait({13482, 12755}, timeout=90)
        if opcode == 12755:
            result["terminal_report_received"] = True
            break
        boundaries += 1
    else:
        raise TimeoutError(
            "QA reached its explicit real-turn bound without a terminal report"
        )
    result["real_turn_boundaries"] = boundaries
    result["combat_final"] = observe(
        args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-url", default="http://127.0.0.1:18081")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--container", default="wakfu-local-world-1")
    parser.add_argument("--owners", type=int, choices=(1, 4, 6), required=True)
    parser.add_argument("--heroes-per-owner", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--wave", type=int, default=3)
    parser.add_argument("--level", type=int, default=33)
    parser.add_argument(
        "--phase", choices=("entry", "ready", "loss", "battle"), default="ready"
    )
    parser.add_argument("--target-wave", type=int, default=4)
    parser.add_argument("--max-turns", type=int, default=320)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-new-qa", action="store_true")
    args = parser.parse_args()
    if not args.execute_new_qa:
        parser.error("No actions performed; --execute-new-qa is required")
    if args.owners * (1 + args.heroes_per_owner) > 6:
        parser.error("This acceptance runner uses at most six combat units")
    result = dict(
        status="RUNNING",
        channel="native_tls",
        official_client=False,
        owners=args.owners,
        heroes_per_owner=args.heroes_per_owner,
        stages=[],
    )
    owners, peers = [], []
    private = args.output.with_suffix(".credentials.private.json")
    try:
        catalog = observe(args, dict(operation="catalog", wave=args.wave))
        if catalog["type"] != "INFINITE_WAVE":
            raise ValueError("This first complete runner uses a classic native Rift")
        for index in range(args.owners):
            owner = dict(
                username="rfnetqa_" + secrets.token_hex(7),
                password=secrets.token_urlsafe(24),
            )
            account = post(args, "/register", owner)
            login = post(args, "/login", owner)
            owner["account_id"] = account["id"]
            owner["character"] = post(
                args,
                "/characters",
                {
                    "name": "Rfnet"
                    + "".join(
                        secrets.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(10)
                    ),
                    "breed": 19,
                },
                login["api_token"],
            )
            owner["heroes"] = [
                post(
                    args,
                    "/characters",
                    {
                        "name": "Rfhero"
                        + "".join(
                            secrets.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(9)
                        ),
                        "breed": 19,
                    },
                    login["api_token"],
                )
                for _ in range(args.heroes_per_owner)
            ]
            owners.append(owner)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            private.write_text(json.dumps(owners))
            os.chmod(private, 0o600)
            observe(
                args,
                dict(
                    operation="setup",
                    wave=args.wave,
                    account_id=owner["account_id"],
                    character_id=owner["character"]["id"],
                    index=index,
                ),
            )
            peer = connect(args, owner)
            peers.append(peer)
            if args.level != 1:
                command = f"!level {args.level}".encode()
                peer.send(12366, struct.pack(">H", len(command)) + command)
                peer.wait(674)
            for hero in owner["heroes"]:
                peer.send(12219, struct.pack(">q", hero["id"]))
                if peer.wait(12587)[1] != b"\x01":
                    raise ValueError("Native owned-hero addition rejected")
        result["qa_identities"] = [
            {
                "account_id": o["account_id"],
                "character_id": o["character"]["id"],
                "hero_ids": [h["id"] for h in o["heroes"]],
            }
            for o in owners
        ]
        result["stages"].append("http_dispatcher_world_selection")
        for owner, peer in zip(owners[1:], peers[1:]):
            peers[0].send(
                1156, struct.pack(">BqqBq", 1, -1, -1, 1, owner["character"]["id"])
            )
            invite = peer.wait(1072)[1]
            size = invite[1]
            inviter = invite[2 : 2 + size]
            identity = struct.unpack_from(">q", invite, 2 + size)[0]
            peer.send(
                1031,
                b"\x01\x01"
                + bytes((len(inviter),))
                + inviter
                + b"\x00"
                + struct.pack(">q", identity),
            )
            peer.wait(1184)
        result["stages"].append("native_party_and_heroes")
        portal = catalog["entrances"][0]
        peers[0].send(12870, struct.pack(">qHH", portal["object_id"], 11, 0))
        arrivals = []
        for peer in peers:
            bootstrap = peer.wait(13974)
            size = struct.unpack_from(">H", bootstrap[1])[0]
            fields = struct.unpack(">BqBqiihqBBiihq", bootstrap[1][2 : 2 + size])
            arrivals.append(tuple(fields[4:7]))
            peer.send(14689)
        result["stages"].append("native_party_rift_portal")
        portal_state = observe(
            args,
            dict(
                operation="state",
                wave=args.wave,
                character_ids=[o["character"]["id"] for o in owners],
            ),
        )
        rows = {row["id"]: row for row in portal_state["characters"]}
        arrivals = [
            tuple(rows[o["character"]["id"]][key] for key in ("x", "y", "z"))
            for o in owners
        ]
        result["portal_positions"] = arrivals
        geometry = observe(
            args, dict(operation="geometry", wave=args.wave, map_id=catalog["map_id"])
        )
        activators = [
            row
            for row in catalog["objects"]
            if row["type"] == "GenericActivableInteractiveElement"
        ]
        if len(activators) != 1:
            raise ValueError("Ambiguous original Rift start activator")
        walk(peers[0], geometry, arrivals[0], activators[0])
        time.sleep(0.5)
        peers[0].send(12870, struct.pack(">qHH", activators[0]["id"], 0, 0))
        for peer in peers:
            opcode, body = peer.wait(12847)
            peer.wait(13652)
        result["stages"].append("native_all_owner_placement")
        time.sleep(1)
        for peer in peers:
            if peer.failure is not None:
                raise peer.failure
        if args.phase != "entry":
            for peer in peers:
                peer.send(12523, b"\x01")
            starts = [peer.wait(13482)[1] for peer in peers]
            result["stages"].append("native_all_owner_ready")
            if args.phase in ("loss", "battle"):
                state = observe(
                    args,
                    dict(
                        operation="state",
                        wave=args.wave,
                        character_ids=[o["character"]["id"] for o in owners],
                    ),
                )
                fight_id = state["runs"][0]["fight_id"]
                battle(args, peers, owners, geometry, fight_id, starts[0], result)
        result["state"] = observe(
            args,
            dict(
                operation="state",
                wave=args.wave,
                character_ids=[o["character"]["id"] for o in owners],
            ),
        )
        result["status"] = "PARTIAL"
        result[
            "limit"
        ] = "Entry/Ready only until complete native turn/death/settlement loop is implemented; never counted as full matrix PASS."
    except BaseException as error:
        result.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        for peer in peers:
            peer.close()
        result["peer_opcodes"] = [
            {"received": p.seen, "sent": p.sent, "tls": p.tls} for p in peers
        ]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
