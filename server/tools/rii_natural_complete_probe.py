"""Local Rii acceptance through native creation and requests, without fixtures."""

import json, os, secrets, struct, time, base64
from functools import lru_cache
from protocol_codec import DIRECTIONS
from pathlib import Path
from collections import deque
from tools.rii_guardian_complete_probe import (
    ObservedPeer,
    Store,
    storage,
    wait_packet,
    text,
)
from tools.rii_lessons_complete_probe import Run
from wakfu_server import npc_world, generic_transports
from wakfu_server.combat_terrain import published_geometry

PATH = Path(".local-state/wakemu/qa/rii-natural-complete.json")
s = Store(
    os.environ["WAKFU_DATABASE_URL"],
    password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
)
r = (
    json.loads(PATH.read_text())
    if PATH.exists()
    else {
        "steps": [],
        "lessons": [],
        "scope": "native22296 creation flagFalse, then protocol requests only; no fixture writes",
    }
)
if "error" in r:
    r.setdefault("prior_errors", []).append(r.pop("error"))
p = ObservedPeer()


def save():
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(r, indent=2, default=str))


def progress():
    with s.connection() as db:
        return storage.load_locked(db, c["id"])


def current():
    return s.character(a["id"], c["id"])


def mark(step):
    if step not in r["steps"]:
        r["steps"].append(step)
    r["progress"] = progress()
    save()
    print("STEP", step, flush=True)


@lru_cache(maxsize=4)
def world_graph(map_id):
    graph = {
        key: set(values) for key, values in published_geometry(map_id).outgoing.items()
    }
    capture = Path(
        "/Users/hectorpulido/Documents/Wakfu-captures-private/official-incarnam-20261112/analysis/decoded/frames.jsonl"
    )
    active = None
    for line in capture.open():
        row = json.loads(line)
        body = base64.b64decode(row["body_base64"])
        if row["direction"] == "in" and row["opcode"] == 13974:
            active = struct.unpack_from(">BqBqiihqBBiihq", body, 2)[7]
        if active != map_id or row["direction"] != "out" or row["opcode"] != 13331:
            continue
        _, x, y, z, count = struct.unpack_from(">iiihB", body)
        point = (x, y, z)
        for value in body[15 : 15 + count]:
            _, dx, dy = DIRECTIONS[value >> 5]
            dz = value & 31
            dz = dz - 32 if dz > 15 else dz
            target = (point[0] + dx, point[1] + dy, point[2] + dz)
            graph.setdefault(point, set()).add(target)
            point = target
    return graph


def goto(goal):
    v = current()
    start = tuple(v[k] for k in ("x", "y", "z"))
    if start == goal:
        return
    graph = world_graph(v["map_id"])
    # Retain the exact native altitude steps observed in world movement.
    q = deque([start])
    previous = {start: None}
    while q and goal not in previous:
        point = q.popleft()
        for cell in graph.get(point, ()):
            if cell not in previous:
                previous[cell] = point
                q.append(cell)
    if goal not in previous:
        raise ValueError(("No reviewed world walking route", start, goal))
    path = []
    point = goal
    while point != start:
        path.append(point)
        point = previous[point]
    path.reverse()
    encoded = bytearray()
    point = start
    dirs = {(dx, dy): key for key, (_, dx, dy) in DIRECTIONS.items()}
    for cell in path:
        dz = cell[2] - point[2]
        encoded.append(
            (dirs[(cell[0] - point[0], cell[1] - point[1])] << 5) | (dz & 31)
        )
        point = cell
    p.send(13331, struct.pack(">iiihB", 0, *start, len(path)) + encoded)
    time.sleep(min(30, 0.18 * len(path) + 0.2))


def near(row):
    v = current()
    start = tuple(v[k] for k in ("x", "y", "z"))
    graph = world_graph(v["map_id"])
    q = deque([start])
    seen = {start}
    while q:
        cell = q.popleft()
        if npc_world.nearby(dict(v, x=cell[0], y=cell[1], z=cell[2]), row):
            goto(cell)
            return
        for nxt in graph.get(cell, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    raise ValueError(("No native NPC approach", row["actor_id"]))


def speaker(ref):
    with s.connection() as db:
        rows = npc_world.load_scene(db, current()["map_id"], 0)
    return next(row for row in rows if row["reference_id"] == ref)


def talk(ref, action, edges):
    row = speaker(ref)
    near(row)
    before = len(p.records)
    p.send(13222, struct.pack(">qq", row["actor_id"], action))
    body = wait_packet(p, 12969, before)
    node = struct.unpack_from(">i", body)[0]
    for src, choice, target in edges:
        if node != src:
            raise ValueError(("Unexpected native dialogue", ref, node, src))
        before = len(p.records)
        p.send(12058, struct.pack(">ii", src, choice))
        body = wait_packet(p, 12218, before)
        node = struct.unpack_from(">i", body)[0]
        if node != target:
            raise ValueError(("Unexpected native continuation", node, target))
        save()


def portal(map_id):
    v = current()
    route = next(
        row
        for row in generic_transports._CATALOG
        if row["map_id"] == v["map_id"]
        and any(d["map_id"] == map_id for d in row["destinations"])
    )
    dst = next(d for d in route["destinations"] if d["map_id"] == map_id)
    if route["approach_positions"]:
        q = route["approach_positions"][0]
        goto(tuple(int(q[k]) for k in ("x", "y", "z")))
    else:
        goto((int(route["x"]), int(route["y"]) - 1, int(route["z"])))
    before = len(p.records)
    p.send(12296, struct.pack(">qiBi", route["id"], dst["destination_id"], 0, 2))
    wait_packet(p, 13974, before)
    p.send(12449)


def approach(row):
    def live():
        position = {key: row[key] for key in ("x", "y", "z")}
        identity = row.get("actor_id", row.get("id"))
        with p.observation_lock:
            records = list(p.records)
        for opcode, body in records:
            if (
                opcode in (13530, 13852)
                and len(body) >= 18
                and struct.unpack_from(">q", body)[0] == identity
            ):
                position.update(
                    zip(("x", "y", "z"), struct.unpack_from(">iih", body, 8))
                )
                if opcode == 13852 and len(body) >= 19:
                    for value in body[19 : 19 + body[18]]:
                        _, dx, dy = DIRECTIONS[value >> 5]
                        dz = value & 31
                        dz = dz - 32 if dz > 15 else dz
                        position["x"] += dx
                        position["y"] += dy
                        position["z"] += dz
        return position

    for attempt in range(12):
        target = live()
        v = current()
        start = tuple(v[k] for k in ("x", "y", "z"))
        q = deque([start])
        seen = {start}
        graph = world_graph(v["map_id"])
        goal = None
        while q:
            point = q.popleft()
            if tuple(target[k] for k in ("x", "y", "z")) in published_geometry(
                v["map_id"]
            ).outgoing.get(point, ()):
                goal = point
                break
            for nxt in graph.get(point, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        if goal is None:
            raise ValueError(("No native entity approach", target))
        goto(goal)
        latest = live()
        if (
            abs(goal[2] - latest["z"]) <= 1
            and abs(goal[0] - latest["x"]) + abs(goal[1] - latest["y"]) == 1
        ):
            return
    raise ValueError(("Moving native entity approach exhausted", row.get("id")))


class LiveRun(Run):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.live_cursor = 0
        self.live_ack = 1
        self.live_actor = None

    def ready_for_input(self):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            with self.peer.observation_lock:
                messages = list(self.peer.records[self.live_cursor :])
                self.live_cursor = len(self.peer.records)
            for op, raw in messages:
                if len(raw) < 20 or struct.unpack_from(">i", raw)[0] != self.fight_id:
                    continue
                if op == 12502:
                    self.peer.send(13510, struct.pack(">i", self.live_ack))
                    self.live_ack += 1
                    self.live_actor = None
                elif op == 13482:
                    self.live_actor = struct.unpack_from(">q", raw, 12)[0]
            snap = self.checkpoint()
            if snap and snap["phase"] == "finished":
                return snap
            if snap and (
                self.live_actor == self.char["id"]
                or (
                    snap.get("runtime", {}).get("awaiting_ack") is None
                    and snap["order"][snap["turn_index"]] == self.char["id"]
                )
            ):
                # The native start-turn packet is the client input authority. The SQL
                # evidence checkpoint can still describe the preceding acknowledged turn.
                snap["runtime"]["awaiting_ack"] = None
                if self.char["id"] in snap["order"]:
                    snap["turn_index"] = snap["order"].index(self.char["id"])
                return snap
            time.sleep(0.05)
        raise AssertionError(("No native owned input", self.fight_id, self.live_actor))


def outside_packet(body):
    return (
        len(body) == 15
        and struct.unpack_from(">q", body)[0] == c["id"]
        and body[10] == 17
        and struct.unpack_from(">i", body, 11)[0] == -1
    )


def kill(monster):
    from tools.candidate_friendly_duel_socket_smoke import placement

    retained = r.get("active_ordinary_fight")
    if retained:
        fid = retained
        before = 0
        run = LiveRun(s, a, c, {"lessons": []})
        run.peer = p
        run.fight_id = fid
        snap = run.checkpoint()
        if (
            snap["phase"] == "finished"
            and r.get("wire_runs")
            and any(
                op == 13046 and outside_packet(bytes.fromhex(raw))
                for op, raw in r["wire_runs"][-1]
            )
        ):
            r.setdefault("ordinary_fights", []).append(fid)
            r.pop("active_ordinary_fight", None)
            save()
            return
        run.live_ack = max(1, snap.get("turn_id", 1))
        run.targets = [
            int(i)
            for i, v in snap["actors"].items()
            if v["team"] != snap["actors"][str(c["id"])]["team"]
        ]
        # Resume the original received NPC end-turn boundary, never synthesize one.
        old = [
            (op, raw)
            for batch in r.get("wire_runs", [])
            for op, raw in batch
            if op == 12502 and struct.unpack_from(">i", bytes.fromhex(raw))[0] == fid
        ]
        if old and snap["order"][snap["turn_index"]] != c["id"]:
            counter = snap.get("runtime", {}).get("awaiting_ack") or snap.get(
                "turn_id", 1
            )
            p.send(13510, struct.pack(">i", counter))
            run.live_ack = counter + 1
    else:
        approach(monster)
        p.pending.clear()
        while not p.events.empty():
            p.events.get_nowait()
        for op, raw in p.records:
            if (
                op == 13852
                and len(raw) >= 19
                and struct.unpack_from(">q", raw)[0] == monster["id"]
            ):
                x, y, z = struct.unpack_from(">iih", raw, 8)
                for value in raw[19 : 19 + raw[18]]:
                    _, dx, dy = DIRECTIONS[value >> 5]
                    dz = value & 31
                    dz = dz - 32 if dz > 15 else dz
                    x += dx
                    y += dy
                    z += dz
                monster = dict(monster, x=x, y=y, z=z)
        before = len(p.records)
        p.send(
            13130,
            struct.pack(
                ">qiihB", monster["id"], monster["x"], monster["y"], monster["z"], 0
            ),
        )
        body = wait_packet(p, 13652, before)
        fid, actors = placement(body)
        wait_packet(p, 12847, before)
        run = LiveRun(s, a, c, {"lessons": []})
        run.peer = p
        run.fight_id = fid
        run.targets = [i for i in actors if i != c["id"]]
        r["active_ordinary_fight"] = fid
        save()
        p.send(12523, b"\x01")
    for _ in range(60):
        snap = run.ready_for_input()
        if snap["phase"] == "finished":
            break
        enemies = [
            (int(i), v)
            for i, v in snap["actors"].items()
            if v["team"] != snap["actors"][str(c["id"])]["team"] and v["hp"] > 0
        ]
        if not enemies:
            break
        hero = snap["actors"][str(c["id"])]
        here = tuple(hero["position"])
        if hero["ap"] < 2:
            run.end_turn()
            continue
        occupied = {
            tuple(v["position"])
            for identity, v in snap["actors"].items()
            if int(identity) != c["id"] and v["hp"] > 0
        }
        graph = {}
        for left, right in snap["edges"]:
            graph.setdefault(tuple(left), []).append(tuple(right))
        previous = {here: None}
        queue = deque([here])
        while queue:
            point = queue.popleft()
            for nxt in graph.get(point, ()):
                if nxt not in occupied and nxt not in previous:
                    previous[nxt] = point
                    queue.append(nxt)
        from wakfu_server.combat_native_los_ray import cast_rays

        options = []
        for target, enemy in enemies:
            cell = tuple(enemy["position"])
            for point in previous:
                distance = abs(point[0] - cell[0]) + abs(point[1] - cell[1])
                if distance != 1:
                    continue
                if not any(
                    clear and not ((set(probes) & occupied) - {cell})
                    for clear, probes in cast_rays(
                        1385,
                        point,
                        cell,
                        source_height=hero.get("native_los_height", 6),
                        target_height=enemy.get("native_los_height", 4),
                    )
                ):
                    continue
                path = []
                cursor = point
                while cursor != here:
                    path.append(cursor)
                    cursor = previous[cursor]
                options.append((len(path), target, cell, list(reversed(path))))
        if not options:
            raise ValueError(
                (
                    "No native reachable firing position",
                    fid,
                    here,
                    [v["position"] for _, v in enemies],
                )
            )
        _, target, cell, path = min(options)
        if path:
            if hero["mp"] <= 0:
                run.end_turn()
                continue
            segment = path[: hero["mp"]]
            run.action(
                12161,
                struct.pack(">q", c["id"])
                + b"".join(struct.pack(">iih", *point) for point in segment),
                label="ordinary native movement",
            )
            continue
        run.cast(5562, cell, class_spell=True)
    snap = run.poll(
        lambda value: value["phase"] == "finished",
        timeout=15,
        label="natural Wodent victory",
    )
    if snap["winner"] != snap["actors"][str(c["id"])]["team"]:
        raise ValueError(("Natural Wodent defeat", fid))
    reports = [
        (op, raw)
        for batch in r.get("wire_runs", [])
        for op, raw in batch
        if op == 12755 and struct.unpack_from(">i", bytes.fromhex(raw))[0] == fid
    ]
    if not reports:
        # The result is delivered after the terminal checkpoint; unrelated rejected
        # actions from earlier turns are not failures of result publication.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with p.observation_lock:
                received = any(
                    op == 12755 and struct.unpack_from(">i", raw)[0] == fid
                    for op, raw in p.records[before:]
                )
            if received:
                break
            time.sleep(0.05)
        if not received:
            raise AssertionError(("Missing native result", fid))
    returned = len(p.records)
    p.send(12925, struct.pack(">iB", fid, 1))
    wait_packet(p, 13046, returned, outside_packet)
    r.setdefault("ordinary_fights", []).append(fid)
    r.pop("active_ordinary_fight", None)
    save()


def guardian():
    from tools.candidate_friendly_duel_socket_smoke import placement

    if current()["map_id"] != 1387:
        portal(1387)
    before = len(p.records)
    talk(5458, 1238, [(5764, 13343, 5790), (5790, 13345, 5791), (5791, 13347, 0)])
    fid, actors = placement(wait_packet(p, 13652, before))
    wait_packet(p, 12847, before)
    run = Run(s, a, c, {"lessons": []})
    run.peer = p
    run.fight_id = fid
    run.poll(lambda value: True, timeout=10, label="guardian admission")
    r["guardian_fight"] = fid
    save()
    cursor = len(p.records)
    p.send(12523, b"\x01")
    ack = 1
    turns = 0
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        with p.observation_lock:
            messages = list(p.records[cursor:])
            cursor = len(p.records)
        for op, body in messages:
            if op in (349, 674):
                raise ValueError(("Guardian input rejected", op, body.hex()))
            if len(body) < 20 or struct.unpack_from(">i", body)[0] != fid:
                continue
            if op == 12502:
                p.send(13510, struct.pack(">i", ack))
                ack += 1
            elif op == 13482 and struct.unpack_from(">q", body, 12)[0] == c["id"]:
                turns += 1
                p.send(
                    12403,
                    struct.pack(
                        ">qh", c["id"], run.checkpoint().get("native_timeline_round", 1)
                    ),
                )
        snap = run.checkpoint()
        if snap and snap["phase"] == "finished":
            break
        time.sleep(0.05)
    snap = run.poll(
        lambda value: value["phase"] == "finished",
        timeout=10,
        label="guardian natural finish",
    )
    wait_packet(p, 12755, before)
    r["guardian_native_turns"] = snap.get("native_timeline_round")
    save()
    start = len(p.records)
    p.send(12925, struct.pack(">iB", fid, 1))
    wait_packet(
        p,
        13411,
        start,
        lambda body: len(body) >= 10 and struct.unpack_from(">i", body, 1)[0] == 22532,
    )
    start = len(p.records)
    p.send(12921, struct.pack(">i", 2))
    p.send(12921, struct.pack(">i", 22532))
    wait_packet(p, 13974, start)
    p.send(12449)
    mark("guardian-ending")
    goto((3, -22, 7))
    start = len(p.records)
    p.send(12870, struct.pack(">qi", 34644, 0))
    p.send(13686, struct.pack(">qq", 34644, 19249))
    wait_packet(p, 13974, start)
    p.send(12449)
    mark("astrub-zaap")


try:
    if "account_id" not in r:
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8))
        a = s.register("rii_natural_" + suffix, secrets.token_urlsafe(24))
        r.update(account_id=a["id"], name="Rii Natural " + suffix)
        save()
    a = {"id": r["account_id"]}
    gen = s.begin_session(a["id"])
    token = s.issue_token(a["id"], "ticket", generation=gen, realm_id=10)
    p.send(426, text(token) + text("rii-natural"))
    p.wait(13873)
    if "character_id" not in r:
        name = r["name"].encode()
        p.send(22296, struct.pack(">qhB", -1, 19, len(name)) + name + b"\x00\x00\x00")
        body = wait_packet(p, 22025, 0)
        if body != b"\x00":
            raise ValueError(("Native character creation failed", body.hex()))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            found = [v for v in s.characters(a["id"]) if v["name"] == r["name"]]
            if found:
                break
            time.sleep(0.05)
        c = found[0]
        r["character_id"] = c["id"]
        save()
    else:
        c = s.character(a["id"], r["character_id"])
        p.send(23664, struct.pack(">q", c["id"]) + text(c["name"]))
        p.wait(630)
    p.wait(711)
    p.send(12449)
    p.wait(12436)
    p.wait(711)
    p.send(12449)
    c = current()
    r["created_position"] = (
        {k: c[k] for k in ("map_id", "x", "y", "z", "level")}
        if "created_position" not in r
        else r["created_position"]
    )
    mark("native-creation-skip")
    if "huly" not in r["steps"]:
        talk(
            5461,
            1243,
            [
                (5765, 13275, 5766),
                (5766, 13278, 5767),
                (5767, 13280, 5768),
                (5768, 13281, 5769),
                (5769, 13282, 5783),
                (5783, 13306, 5770),
                (5770, 13283, 0),
            ],
        )
        mark("huly")
    if "otomai" not in r["steps"]:
        talk(
            5459,
            1244,
            [
                (5772, 13288, 5773),
                (5773, 13289, 5774),
                (5774, 13307, 5775),
                (5775, 13293, 0),
            ],
        )
        mark("otomai")
    if "combat-lessons" not in r["steps"]:
        if current()["map_id"] != 1388:
            portal(1388)
        goto((0, -18, 0))
        run = Run(s, a, c, r)
        run.peer = p
        for index in range(len(r["lessons"]), 7):
            p.pending.clear()
            while not p.events.empty():
                p.events.get_nowait()
            run.start(index)
            save()
            run.solve()
            run.finish()
            save()
        mark("combat-lessons")
        portal(1385)
    if r.get("active_ordinary_fight"):
        kill({})
    if "ecology" not in r["steps"]:
        if current()["map_id"] == 1388:
            portal(1385)
        if 10615 not in progress()["objectives"]:
            talk(5467, 1255, [(5782, 13305, 5786), (5786, 13318, 0)])
        from tools.rii_ecology_socket_actions import run_ecology

        for quest, index, node, terminal in (
            (5145, 0, 5788, 13338),
            (5155, 1, 5789, 13340),
            (5156, 2, 0, 0),
        ):
            if quest in progress()["completed"]:
                continue
            for transient_attempt in range(12):
                try:
                    run_ecology(p, s, a, c, goto, approach, kill, mark)
                    break
                except AssertionError as error:
                    if "Guardado de posición" not in str(
                        error
                    ) and "harvest target unreachable" not in str(error):
                        raise
                    if transient_attempt == 11:
                        raise
                    time.sleep(0.25)
            if index < 2:
                row = speaker(5467)
                near(row)
                start = len(p.records)
                p.send(13222, struct.pack(">qq", row["actor_id"], 1255))
                body = wait_packet(p, 12969, start)
                root = struct.unpack_from(">i", body)[0]
                choice = {
                    5762: (13337, 13339),
                    5799: (13360, 13361),
                    5800: (13364, 13365),
                }[root][index]
                start = len(p.records)
                p.send(12058, struct.pack(">ii", root, choice))
                wait_packet(p, 12218, start)
                start = len(p.records)
                p.send(12058, struct.pack(">ii", node, terminal))
                wait_packet(p, 12218, start)
                mark("ecosystem-turnin-" + str(quest))
        mark("ecology")
    if "astrub-zaap" not in r["steps"]:
        guardian()
    r["success"] = True
    r.pop("error", None)
    save()
    print("NATURAL_E2E_PASS", c["id"], flush=True)
except BaseException as error:
    r["error"] = repr(error)
    r["progress"] = progress() if "c" in globals() else None
    save()
    print("BLOCKER", repr(error), flush=True)
    raise
finally:
    r["wire_runs"] = r.get("wire_runs", []) + [[(op, b.hex()) for op, b in p.records]]
    save()
    p.close()
