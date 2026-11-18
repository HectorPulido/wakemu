"""One real Bovis admission and bounded class-action pillar observation.

The existing owner supplies TLS. This module never wins a fight, mutates a
checkpoint or changes a character; ordinary server legality owns every action.
"""
from collections import deque
import struct

from tools.candidate_friendly_duel_socket_smoke import placement
from tools.line2_rank23_native_tls_probe import Rank23NativeRun, _owned_class_spell_ids
from tools.line3_fields_combat import _in_shape, _spell_shapes, path_to_cast
from tools.line4_owned_actions import capture
from wakfu_server.combat_geometry import prepare_geometry


def _wire_pillars(probe, fight_id):
    """Read actual appearance/removal wire; active DB checkpoints omit pillars."""
    from wakfu_server.combat_wire import decode_bootstrap

    pillars = {}
    with probe.peer.observation_lock:
        records = list(probe.peer.records)
    for opcode, body in records:
        if (
            opcode == 12847
            and len(body) >= 4
            and struct.unpack_from(">i", body)[0] == fight_id
        ):
            for section in decode_bootstrap(body)["myK"]:
                if len(section) < struct.calcsize(">qqiihqhib"):
                    continue
                reference, identity, x, y, z = struct.unpack_from(">qqiih", section)
                if reference == 986:
                    pillars[str(identity)] = dict(reference=reference, cell=(x, y, z))
        elif (
            opcode == 13726
            and len(body) == 20
            and struct.unpack_from(">i", body)[0] == fight_id
        ):
            pillars.pop(str(struct.unpack_from(">q", body, 12)[0]), None)
    return pillars


def _pillar_damage(probe, fight_id, identity, mark):
    from wakfu_server.combat_protocol_reconstruction import decode_packet

    rows = []
    with probe.peer.observation_lock:
        records = list(enumerate(probe.peer.records[mark:], start=mark))
    for sequence, (opcode, body) in records:
        if (
            opcode != 12613
            or len(body) < 4
            or struct.unpack_from(">i", body)[0] != fight_id
        ):
            continue
        try:
            effect = decode_packet(opcode, body).get("effect", {})
        except ValueError:
            continue
        if (
            effect.get("target") == identity
            and effect.get("family") in (1, 2, 3, 4, 5, 917, 1083)
            and effect.get("value", 0) > 0
        ):
            rows.append(
                dict(
                    sequence=sequence, opcode=opcode, body_hex=body.hex(), effect=effect
                )
            )
    return rows


def admit_room4(probe):
    """Approach the actual registered Bovis, admit normally, await owned turn."""
    current = probe.current()
    if current["map_id"] != 1002 or current["instance_id"] <= 0:
        raise ValueError("Enter the actual Bovis instance before room4 admission")
    with probe.store.connection() as db:
        progress = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
            (current["instance_id"],),
        ).fetchone()
        if (
            not progress
            or progress["current_room"] != 4
            or progress["status"] != "active"
        ):
            raise ValueError(("Actual room4 is not ready", progress))
        group = db.execute(
            "SELECT g.* FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
            "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
            "WHERE r.instance_id=%s AND r.room_order=4",
            (current["instance_id"],),
        ).fetchone()
    if group is None or [m["ref"] for m in group["members"]] != [3845]:
        raise ValueError("No actual original Bovis group")
    mark = probe.peer.mark()
    resumed = group["status"] == "fighting"
    if resumed:
        fight_id = group["fight_id"]
    elif group["status"] == "available":
        from wakfu_server import owned_story_controller

        with probe.store.connection() as db:
            selected, completed = owned_story_controller._scope(
                db, probe.store, current, check_position=False, lock=False
            )
        blocked = owned_story_controller.collision_projection(selected, completed)[
            "blocked"
        ]
        graph = prepare_geometry(
            probe.configuration()["topology"]["exploration_geometry"]
        ).outgoing
        target = group["members"][0]
        here = tuple(current[k] for k in ("x", "y", "z"))
        pending, seen, goal = deque([here]), {here}, None
        while pending:
            cell = pending.popleft()
            if (
                abs(cell[0] - target["x"]) + abs(cell[1] - target["y"]) <= 1
                and abs(cell[2] - target["z"]) <= 1
            ):
                goal = cell
                break
            for nxt in graph.get(cell, ()):
                if (
                    nxt not in seen
                    and nxt not in blocked
                    and nxt != tuple(target[k] for k in ("x", "y", "z"))
                ):
                    seen.add(nxt)
                    pending.append(nxt)
        if goal is None:
            raise ValueError(
                "Traverse the original open final passage before approaching Bovis"
            )
        probe.walk(goal)
        mark = probe.peer.mark()
        probe.peer.send(
            13130,
            struct.pack(
                ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
            ),
        )
        fight_id, _ = placement(probe.peer.matching(13652, mark, timeout=45))
    else:
        raise ValueError(("Actual Bovis group unavailable", group["status"]))
    runner = Rank23NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    runner.wire_cursor = 0 if resumed else mark
    runner.native_global_turn = 0
    runner.native_turn_actor = None
    runner.native_timeline_phase = None
    runner.native_timeline_members = frozenset()
    runner.last_begin_identity = None
    runner.last_acked_turn = None
    if resumed:
        probe.peer.send(13332, struct.pack(">i", fight_id))
    else:
        probe.peer.send(12523, b"\x01")
    snapshot = runner.ready_for_input()
    probe.note(
        "actual Bovis admitted without administrative outcome",
        fight_id=fight_id,
        resumed=resumed,
    )
    capture(probe, mark)
    return runner, snapshot


def paid_cast_at_pillar(probe, runner):
    """Observe one paid damaging class action, with at most three real casts."""
    spells = _owned_class_spell_ids(probe)
    shapes = _spell_shapes(probe, spells)
    attempts = []
    mark = probe.peer.mark()
    try:
        for spell in spells[:3]:
            snapshot = runner.ready_for_input()
            hero = snapshot["actors"][str(probe.character["id"])]
            pillars = list(_wire_pillars(probe, runner.fight_id).items())
            pillars.sort(
                key=lambda entry: abs(entry[1]["cell"][0] - hero["position"][0])
                + abs(entry[1]["cell"][1] - hero["position"][1])
            )
            if not pillars:
                raise AssertionError(
                    "Actual bootstrap wire lacks an unremoved native986 pillar"
                )
            key, row = pillars[0]
            cell = tuple(row["cell"])
            if not _in_shape(hero["position"], cell, shapes[spell]):
                path = path_to_cast(
                    snapshot,
                    hero,
                    dict(id=int(key), position=cell, physical_radius=0),
                    {spell: shapes[spell]},
                )
                if not path:
                    attempts.append(
                        dict(spell=spell, rejected="No original reachable firing cell")
                    )
                    continue
                runner.move(path[-1])
            before = runner.ready_for_input()
            ap = before["actors"][str(probe.character["id"])]["ap"]
            cast_mark = probe.peer.mark()
            try:
                after = runner.cast(spell, cell, class_spell=True)
            except AssertionError as error:
                attempts.append(dict(spell=spell, cell=list(cell), rejected=str(error)))
                continue
            damage_frames = _pillar_damage(probe, runner.fight_id, int(key), cast_mark)
            paid = after["actors"][str(probe.character["id"])]["ap"] < ap
            damaged = bool(damage_frames)
            observation = dict(
                spell=spell,
                cell=list(cell),
                pillar_id=int(key),
                damage_frames=damage_frames,
                ap_before=ap,
                ap_after=after["actors"][str(probe.character["id"])]["ap"],
                retired=key not in _wire_pillars(probe, runner.fight_id),
                paid=paid,
                damaged=damaged,
                qualification="Actual positive native damage receipt; compact recovery checkpoint omits faW HP",
            )
            attempts.append(observation)
            if paid and damaged:
                probe.note(
                    "actual paid class action damaged Bovis native pillar",
                    **observation
                )
                return observation
        raise AssertionError(
            ("Bounded real pillar action did not show paid HP damage", attempts)
        )
    finally:
        probe.receipt.setdefault("bovis_pillar_action_attempts", []).extend(attempts)
        capture(probe, mark)
