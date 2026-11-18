"""Actual owned stage admission with explicitly authorized ordinary admin wins.

No combat/AI policy, synthetic quest event or private positioning is supplied.
The caller owns one persistent native TLS peer and real world mechanisms.
"""
from collections import deque
import struct, time
from tools.candidate_friendly_duel_socket_smoke import placement
from tools.line3_fields_native_tls_probe import play_administrative
from wakfu_server.combat_geometry import prepare_geometry


def capture(probe, mark):
    import uuid

    if not hasattr(probe.peer, "_qa_capture_scope"):
        probe.peer._qa_capture_scope = uuid.uuid4().hex
    scope = probe.peer._qa_capture_scope
    frames = probe.receipt.setdefault("line4_native_mission_frames", [])
    seen = {(r.get("scope"), r["sequence"], r["opcode"]) for r in frames}
    with probe.peer.observation_lock:
        rows = list(enumerate(probe.peer.records[mark:], start=mark))
    for sequence, (opcode, body) in rows:
        if (
            opcode in (13312, 13832, 13422, 12471, 13879)
            and (scope, sequence, opcode) not in seen
        ):
            frames.append(
                dict(scope=scope, sequence=sequence, opcode=opcode, body_hex=body.hex())
            )
    probe.receipt.setdefault("trace", []).extend(probe.peer.gameplay_trace(mark))
    probe.save()


def win_room(probe, expected_room=None):
    current = probe.current()
    instance = current["instance_id"]
    if instance <= 0:
        raise ValueError("No actual owned stage")
    with probe.store.connection() as db:
        progress = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
            (instance,),
        ).fetchone()
        if not progress or progress["status"] != "active":
            raise ValueError("No actual active room progress")
        order = progress["current_room"]
        if expected_room is not None and order != expected_room:
            raise ValueError(("Unexpected actual room", order, expected_room))
        group = db.execute(
            "SELECT g.* FROM dungeon_room_spawn_receipts r JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id WHERE r.instance_id=%s AND r.room_order=%s",
            (instance, order),
        ).fetchone()
    deadline = time.monotonic() + 12
    while group is None and time.monotonic() < deadline:
        probe.ack_loads(timeout=0.6)
        time.sleep(0.2)
        with probe.store.connection() as db:
            group = db.execute(
                "SELECT g.* FROM dungeon_room_spawn_receipts r JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id WHERE r.instance_id=%s AND r.room_order=%s",
                (instance, order),
            ).fetchone()
    if group is None:
        raise ValueError("No actual registered owned group after normal scene idle")
    mark = probe.peer.mark()
    try:
        if group["status"] == "fighting":
            fight_id = group["fight_id"]
        elif group["status"] == "available":
            config = probe.configuration()
            if config["topology"].get("exploration_geometry"):
                graph = prepare_geometry(
                    config["topology"]["exploration_geometry"]
                ).outgoing
            else:
                from wakfu_server.combat_terrain import published_geometry

                graph = published_geometry(current["map_id"]).outgoing
            if config["topology"].get("owned_story_controller"):
                from wakfu_server import owned_story_controller

                with probe.store.connection() as db:
                    selected, completed = owned_story_controller._scope(
                        db, probe.store, current, check_position=False, lock=False
                    )
                blocked = owned_story_controller.collision_projection(
                    selected, completed
                )["blocked"]
                graph = {
                    cell: tuple(target for target in targets if target not in blocked)
                    for cell, targets in graph.items()
                    if cell not in blocked
                }
            here = tuple(current[k] for k in ("x", "y", "z"))
            pending = deque([here])
            seen = {here}
            target = None
            occupied = {tuple(m[k] for k in ("x", "y", "z")) for m in group["members"]}
            while pending and target is None:
                cell = pending.popleft()
                for member in group["members"]:
                    if (
                        abs(cell[0] - member["x"]) + abs(cell[1] - member["y"]) <= 1
                        and abs(cell[2] - member["z"]) <= 1
                    ):
                        probe.walk(cell)
                        target = member
                        break
                for nxt in graph.get(cell, ()):
                    if nxt not in seen and nxt not in occupied:
                        seen.add(nxt)
                        pending.append(nxt)
            if target is None:
                raise ValueError(
                    "No reachable original target: traverse the native portal or gate first"
                )
            mark = probe.peer.mark()
            probe.peer.send(
                13130,
                struct.pack(
                    ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
                ),
            )
            opcode, body = probe.peer.matching_any(
                (13652, 674),
                mark,
                predicate=lambda op, frame: op == 13652
                or b"Native arena lacks" in frame
                or b"Fixed initial actor is outside" in frame,
                timeout=45,
            )
            if opcode != 13652:
                raise AssertionError(
                    (
                        "Actual owned admission rejected",
                        body.decode("utf-8", errors="ignore")[-300:],
                    )
                )
            fight_id, _ = placement(body)
        else:
            raise ValueError(("Actual owned group is not available", group["status"]))
        probe.note(
            "actual owned room admitted",
            map_id=current["map_id"],
            instance_id=instance,
            room=order,
            fight_id=fight_id,
            original_breeds=[m["ref"] for m in group["members"]],
        )
        play_administrative(
            probe,
            fight_id,
            mark,
            resume_existing=group["status"] == "fighting",
            scope=probe.receipt.get("line", "line4"),
        )
        probe.ack_loads(mark)
        probe.note(
            "ordinary owned room administrative win",
            map_id=current["map_id"],
            instance_id=instance,
            room=order,
            fight_id=fight_id,
            qualification="Explicit user-authorized !winfight; not a natural combat or AI test",
        )
        return fight_id
    finally:
        capture(probe, mark)


def travel(probe, source_id, destination_id, *, expected_map=None):
    """Use the actual native portal from its exact bEG/bEm approach."""
    from wakfu_server import generic_transports

    current = probe.current()
    source = generic_transports.source(current["map_id"], source_id)
    if source is None:
        raise ValueError(
            ("Missing original portal source", current["map_id"], source_id)
        )
    if current["instance_id"]:
        geometry = prepare_geometry(
            probe.configuration()["topology"]["exploration_geometry"]
        )
    else:
        from wakfu_server.combat_terrain import published_geometry

        geometry = published_geometry(current["map_id"])
    approved = {
        tuple(row[k] for k in ("x", "y", "z"))
        for row in source.get("approach_positions", ())
    }
    candidates = approved or {
        p for p in geometry.cells if p[:2] == (source["x"], source["y"])
    }
    if not candidates:
        raise ValueError(("Native portal has no original approach floor", source_id))
    goal = min(
        candidates,
        key=lambda p: (
            abs(p[2] - source["z"]),
            abs(p[0] - current["x"]) + abs(p[1] - current["y"]),
        ),
    )
    probe.walk(goal)
    before = {k: probe.current()[k] for k in ("map_id", "instance_id", "x", "y", "z")}
    mark = probe.peer.mark()
    try:
        probe.peer.send(12296, struct.pack(">qiBi", source_id, destination_id, 0, 2))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            probe.ack_loads(mark, timeout=0.6)
            current = probe.current()
            after = {k: current[k] for k in before}
            if after != before and (
                expected_map is None or current["map_id"] == expected_map
            ):
                break
            time.sleep(0.1)
        else:
            raise AssertionError(
                (
                    "Actual native portal did not commit",
                    source_id,
                    destination_id,
                    after,
                )
            )
        probe.note(
            "actual native portal committed",
            source_id=source_id,
            destination_id=destination_id,
            source_position=before,
            destination=after,
        )
        return current
    finally:
        capture(probe, mark)


def shore_debrief(probe):
    """Accept the actual post-voyage Hully acknowledgement after its scene."""
    if 2684 in probe.progress()["completed"]:
        return
    from wakfu_server import owned_story_npcs

    deadline = time.monotonic() + 15
    row = None
    while time.monotonic() < deadline:
        probe.ack_loads(0, timeout=0.6)
        with probe.store.connection() as db:
            candidates = owned_story_npcs.rows(db, probe.store, probe.current())
        matches = [r for r in candidates if r["reference_id"] == 3801]
        if len(matches) == 1:
            row = matches[0]
            break
        time.sleep(0.1)
    if row is None:
        raise ValueError("Actual Hully source is not yet present after voyage")
    probe.walk((17, -1, -6))
    mark = probe.peer.mark()
    try:
        probe.peer.send(13222, struct.pack(">qq", row["actor_id"], 697))
        probe.peer.matching(
            12969,
            mark,
            lambda body: len(body) == 13 and struct.unpack_from(">i", body)[0] == 3212,
            timeout=20,
        )
        probe.peer.send(12058, struct.pack(">ii", 3212, 7974))
        probe.peer.matching(
            13832,
            mark,
            lambda body: body == struct.pack(">qi", probe.character["id"], 5305),
            timeout=20,
        )
        if (
            2684 not in probe.progress()["completed"]
            or 2687 not in probe.progress()["running"]
        ):
            raise AssertionError(
                "Actual Hully hand-in did not advance the earned chapter"
            )
        probe.note(
            "actual Hully shore acknowledgement",
            actor_id=row["actor_id"],
            quest_id=2684,
            objective_id=5305,
            choice_id=7974,
        )
    finally:
        capture(probe, mark)


def interact(probe, source_id, position, *, controller_id=None, step=None, timeout=20):
    """Perform one native world action and await only its authentic receipt."""
    probe.walk(tuple(position))
    mark = probe.peer.mark()
    instance = probe.current()["instance_id"]
    try:
        probe.peer.send(12870, struct.pack(">qHH", source_id, 0, 0))
        if step is not None:
            event_key = f"owned-story:{controller_id}:{instance}:{step}"
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                with probe.store.connection() as db:
                    event = db.execute(
                        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                        (probe.character["id"], event_key),
                    ).fetchone()
                if event:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(
                    (
                        "Actual native world action did not produce its receipt",
                        source_id,
                        step,
                    )
                )
        probe.note(
            "actual owned native world action",
            source_id=source_id,
            position=list(position),
            controller_id=controller_id,
            step=step,
            wire_action=0,
            wire_parameter=0,
        )
    finally:
        capture(probe, mark)


def win_world_for_level_objective(probe, quest_id=2692):
    """Fresh original-world battle for an actually assigned native frontier."""
    objective_id, minimum_level = {2692: (5312, 20), 2710: (5359, 23)}[quest_id]
    if objective_id in probe.progress()["objectives"]:
        return
    current = probe.current()
    if (
        current["instance_id"]
        or quest_id not in probe.progress()["running"]
        or current["level"] < minimum_level
    ):
        raise ValueError(
            (
                "Native frontier requires its assigned public owner and actual level",
                quest_id,
                minimum_level,
            )
        )
    with probe.store.connection() as db:
        groups = db.execute(
            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=0 AND status='available' ORDER BY group_id",
            (current["map_id"],),
        ).fetchall()
    groups = [g for g in groups if g["members"]]
    if not groups:
        raise ValueError(
            "No actual available original world group; do not synthesize one"
        )
    group = min(
        groups,
        key=lambda g: (
            min(
                abs(m["x"] - current["x"]) + abs(m["y"] - current["y"])
                for m in g["members"]
            ),
            len(g["members"]),
        ),
    )
    target = probe.approach(group)
    with probe.store.connection() as db:
        fresh = db.execute(
            "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=0 AND group_id=%s",
            (current["map_id"], group["group_id"]),
        ).fetchone()
    if fresh is None or fresh["status"] != "available":
        raise ValueError("Actual world group is no longer available")
    if fresh["members"] != group["members"]:
        group = dict(group, members=fresh["members"])
        target = probe.approach(group)
    mark = probe.peer.mark()
    try:
        probe.peer.send(
            13130,
            struct.pack(
                ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
            ),
        )
        fight_id, _ = placement(probe.peer.matching(13652, mark, timeout=45))
        play_administrative(probe, fight_id, mark, scope="line4")
        probe.ack_loads(mark)
        deadline = time.monotonic() + 20
        while objective_id not in probe.progress()["objectives"]:
            if time.monotonic() > deadline:
                raise AssertionError(
                    (
                        "Fresh native world outcome did not earn its assigned objective",
                        quest_id,
                        objective_id,
                    )
                )
            time.sleep(0.1)
        probe.note(
            "assigned level victory objective earned",
            quest_id=quest_id,
            objective_id=objective_id,
            minimum_level=minimum_level,
            fight_id=fight_id,
            original_group_id=group["group_id"],
            administrative_outcome=True,
        )
        return fight_id
    finally:
        capture(probe, mark)
