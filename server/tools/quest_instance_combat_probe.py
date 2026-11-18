"""Ordinary local TLS combat for a reviewed owned quest instance.

Uses an already authenticated isolated QA probe. Never creates encounters,
changes stats/HP, advances quests, or controls a human client. The caller owns
fixture setup, actual native entry/stairs, journal checks and exterior return.
"""

from collections import deque
import struct
import time

from tools.candidate_friendly_duel_socket_smoke import placement
from tools.hunter_archetype_tls_probe import NativeRun
from wakfu_server.combat_geometry import prepare_geometry
from protocol_codec import DIRECTIONS


def walk_native(probe, configuration, goal):
    """Walk the frozen native exploration graph, including warehouse stairs."""
    current = probe.current()
    if (
        current["map_id"] != configuration["route"]["start_map_id"]
        or current["instance_id"] <= 0
    ):
        raise AssertionError("Quest walking probe is outside its owned native map")
    start = tuple(current[k] for k in ("x", "y", "z"))
    goal = tuple(goal)
    if start == goal:
        return
    graph = prepare_geometry(configuration["topology"]["exploration_geometry"]).outgoing
    previous, pending = {start: None}, deque([start])
    while pending and goal not in previous:
        point = pending.popleft()
        for target in graph.get(point, ()):
            if target not in previous:
                previous[target] = point
                pending.append(target)
    if goal not in previous:
        raise AssertionError(("No native quest exploration path", start, goal))
    path, point = [], goal
    while point != start:
        path.append(point)
        point = previous[point]
    path.reverse()
    directions = {(dx, dy): key for key, (_, dx, dy) in DIRECTIONS.items()}
    point, encoded = start, bytearray()
    for cell in path:
        encoded.append(
            (directions[(cell[0] - point[0], cell[1] - point[1])] << 5)
            | ((cell[2] - point[2]) & 31)
        )
        point = cell
    probe.peer.send(13331, struct.pack(">iiihB", 0, *start, len(path)) + encoded)
    deadline = time.monotonic() + min(15, len(path) * 0.3 + 3)
    while time.monotonic() < deadline:
        if tuple(probe.current()[k] for k in ("x", "y", "z")) == goal:
            time.sleep(0.15)
            return
        time.sleep(0.05)
    raise AssertionError(("Quest walk did not settle", start, goal, probe.current()))


def fight_owned_room(probe, configuration, *, room_order=None, timeout=180):
    current = probe.current()
    instance = current["instance_id"]
    assert instance > 0 and current["map_id"] == configuration["route"]["start_map_id"]
    with probe.store.connection() as db:
        progress = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
            (instance,),
        ).fetchone()
        if progress is None or progress["status"] != "active":
            raise AssertionError(("Dungeon room progression is not active", progress))
        selected_order = progress["current_room"] if room_order is None else room_order
        if (
            type(selected_order) is not int
            or selected_order != progress["current_room"]
        ):
            raise AssertionError(
                ("Requested room is not current", selected_order, progress)
            )
        group = db.execute(
            "SELECT g.* FROM dungeon_room_spawn_receipts r JOIN combat_groups g ON "
            "g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
            "WHERE r.instance_id=%s AND r.room_order=%s",
            (instance, selected_order),
        ).fetchone()
    assert group and group["status"] == "available", group
    walking = prepare_geometry(configuration["topology"]["exploration_geometry"])
    here = tuple(current[k] for k in ("x", "y", "z"))
    occupied = {tuple(m[k] for k in ("x", "y", "z")) for m in group["members"]}
    pending, seen, target = deque([here]), {here}, None
    while pending and target is None:
        point = pending.popleft()
        for member in group["members"]:
            cell = tuple(member[k] for k in ("x", "y", "z"))
            if (
                abs(point[0] - cell[0]) + abs(point[1] - cell[1]) <= 1
                and abs(point[2] - cell[2]) <= 1
            ):
                walk_native(probe, configuration, point)
                target = member
                break
        for nxt in walking.outgoing.get(point, ()):
            if nxt not in seen and nxt not in occupied:
                seen.add(nxt)
                pending.append(nxt)
    assert target is not None, "No native quest encounter approach"
    start = probe.peer.mark()
    probe.peer.send(
        13130,
        struct.pack(">qiihB", target["id"], target["x"], target["y"], target["z"], 0),
    )
    fight_id, _ = placement(probe.peer.matching(13652, start, timeout=30))
    runner = NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    runner.wire_cursor, runner.native_global_turn = start, 0
    probe.peer.send(12523, b"\x01")
    deadline = time.monotonic() + timeout
    casts = 0
    while time.monotonic() < deadline:
        snap = runner.ready_for_input()
        if snap["phase"] == "finished":
            break
        hero = snap["actors"][str(probe.character["id"])]
        enemies = [
            a
            for a in snap["actors"].values()
            if a["team"] != hero["team"] and a["hp"] > 0
        ]
        assert enemies, ("No living quest enemy", fight_id)
        enemy = min(
            enemies,
            key=lambda a: (
                abs(a["position"][0] - hero["position"][0])
                + abs(a["position"][1] - hero["position"][1]),
                a["hp"],
            ),
        )
        here, target = tuple(hero["position"]), tuple(enemy["position"])
        if hero["ap"] < 2:
            runner.end_turn()
            continue
        if abs(here[0] - target[0]) + abs(here[1] - target[1]) == 1:
            try:
                runner.cast(5562, target, class_spell=True)
            except AssertionError as error:
                if "Native spell maximum casts per turn reached" not in str(error):
                    raise
                # Dynamic native class states can lower the current turn's
                # cast cap. Honor the rejection with an ordinary turn end.
                runner.end_turn()
                continue
            casts += 1
            continue
        graph = {}
        for a, b in snap["edges"]:
            graph.setdefault(tuple(a), []).append(tuple(b))
        occupied = {
            tuple(a["position"])
            for a in snap["actors"].values()
            if a["hp"] > 0 and tuple(a["position"]) != here
        }
        previous, pending = {here: None}, deque([here])
        goal = None
        while pending:
            point = pending.popleft()
            if abs(point[0] - target[0]) + abs(point[1] - target[1]) == 1:
                goal = point
                break
            for nxt in graph.get(point, ()):
                if nxt not in previous and nxt not in occupied:
                    previous[nxt] = point
                    pending.append(nxt)
        assert goal is not None, ("No native rat approach", here, target)
        path = []
        while goal != here:
            path.append(goal)
            goal = previous[goal]
        path.reverse()
        if hero["mp"] <= 0:
            runner.end_turn()
        else:
            runner.action(
                12161,
                struct.pack(">q", probe.character["id"])
                + b"".join(struct.pack(">iih", *p) for p in path[: hero["mp"]]),
                label="ordinary quest-rat approach",
            )
    snap = runner.checkpoint()
    assert (
        snap["phase"] == "finished"
        and snap["winner"] == snap["actors"][str(probe.character["id"])]["team"]
    ), ("Quest battle did not win", fight_id, snap.get("phase"))
    start = probe.peer.mark()
    probe.peer.send(12925, struct.pack(">iB", fight_id, 0))
    probe.peer.matching(13974, start, timeout=30)
    return dict(
        fight_id=fight_id,
        instance_id=instance,
        casts=casts,
        original_actor_ids=[m["id"] for m in group["members"]],
        native_monsters=[
            dict(reference=m["ref"], level=m["level"]) for m in group["members"]
        ],
    )
