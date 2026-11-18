"""Bounded native School seed actions on the caller's existing QA peer.

No connection, fixture, quest grant, transformation or outcome is created here.
The server owns movement, the temporary book, collection and normal settlement.
"""
import struct
import time


def _original_seed(probe, fight_id):
    current = probe.current()
    if current["map_id"] != 1018 or current.get("instance_id", 0) <= 0:
        raise ValueError("The real private School seed context is required")
    selected = probe.configuration()["topology"].get("owned_story_controller", {})
    if selected.get("id") != "huppermage-seed-1018":
        raise ValueError("The pinned native seed controller is required")
    with probe.store.connection() as db:
        groups = db.execute(
            "SELECT map_id,instance_id,members FROM combat_groups WHERE fight_id=%s",
            (fight_id,),
        ).fetchall()
    if (
        len(groups) != 1
        or groups[0]["map_id"] != 1018
        or groups[0]["instance_id"] != current["instance_id"]
        or len(groups[0]["members"]) != 1
        or groups[0]["members"][0]["ref"] != 3907
    ):
        raise ValueError("The fight lacks its one original native3907 seed")
    return groups[0]["members"][0]["id"], current


def _morph_removals(probe, fight_id, mark):
    from wakfu_server.combat_protocol_reconstruction import decode_packet

    with probe.peer.observation_lock:
        records = list(enumerate(probe.peer.records[mark:], start=mark))
    result = []
    for sequence, (opcode, body) in records:
        if (
            opcode != 13560
            or len(body) < 16
            or struct.unpack_from(">i", body)[0] != fight_id
            or struct.unpack_from(">i", body, 12)[0] != 933
        ):
            continue
        row = decode_packet(opcode, body)
        if (
            row.get("removal_target") == probe.character["id"]
            and row.get("effect", {}).get("family") == 933
        ):
            result.append(dict(sequence=sequence, opcode=opcode, body_hex=body.hex()))
    return result


def collect_seed(probe, runner, *, max_operations=128, timeout=240):
    """Use actual paid movement and raw native UID5599, then normal return.

    `runner` is the owner's already initialized Rank23NativeRun. A compact
    checkpoint is used only for planning; it is never modified or persisted.
    """
    from tools.line3_fields_combat import path_to_cast

    if type(max_operations) is not int or not 1 <= max_operations <= 128:
        raise ValueError("Seed action bound must be between1 and128")
    seed_id, initial = _original_seed(probe, runner.fight_id)
    mark = probe.peer.mark()
    operations = []
    deadline = time.monotonic() + timeout
    shapes = {5599: ((1, 1, False, False),)}
    while len(operations) < max_operations and time.monotonic() < deadline:
        snapshot = runner.ready_for_input()
        if snapshot["phase"] == "finished":
            break
        hero = snapshot["actors"][str(probe.character["id"])]
        seed = snapshot["actors"].get(str(seed_id))
        if seed is None or seed["hp"] <= 0:
            raise AssertionError(
                ("Original seed disappeared without terminal outcome", runner.fight_id)
            )
        if hero["hp"] <= 0 or hero["team"] == seed["team"]:
            raise AssertionError("The actual living player and enemy seed are required")
        here, target = tuple(hero["position"]), tuple(seed["position"])
        if (
            here[2] == target[2]
            and abs(here[0] - target[0]) + abs(here[1] - target[1]) == 1
        ):
            runner.cast(5599, target, class_spell=False)
            operations.append(
                dict(
                    kind="native_collection",
                    spell=5599,
                    casting_uid=5599,
                    seed_id=seed_id,
                    cell=list(target),
                )
            )
            continue
        if hero["mp"] <= 0:
            runner.end_turn()
            operations.append(dict(kind="normal_end_turn"))
            continue
        wrong_height = {
            tuple(cell)
            for edge in snapshot["edges"]
            for cell in edge
            if cell[2] != target[2]
        }
        path = path_to_cast(
            snapshot, hero, seed, shapes, rejected_positions=wrong_height
        )
        if not path:
            raise AssertionError(
                ("No native paid route to the original seed", here, target)
            )
        segment = path[: hero["mp"]]
        runner.action(
            12161,
            struct.pack(">q", hero["id"])
            + b"".join(struct.pack(">iih", *cell) for cell in segment),
            label="School native seed paid movement",
        )
        operations.append(
            dict(kind="paid_native_movement", cells=[list(cell) for cell in segment])
        )
    snapshot = runner.checkpoint()
    hero = snapshot["actors"][str(probe.character["id"])]
    if snapshot["phase"] != "finished" or snapshot.get("winner") != hero["team"]:
        raise AssertionError(
            (
                "Bounded native seed attempt did not win",
                runner.fight_id,
                snapshot["phase"],
                operations,
            )
        )
    if any(
        event.get("kind") == "administrative_outcome"
        for event in snapshot.get("events", ())
    ):
        raise AssertionError(
            "Administrative outcomes cannot prove native seed collection"
        )
    if not any(row["kind"] == "native_collection" for row in operations):
        raise AssertionError(
            "This helper did not observe an actual native5599 collection action"
        )
    close_mark = probe.peer.mark()
    probe.peer.send(12925, struct.pack(">iB", runner.fight_id, 1))
    probe.peer.matching(
        13046,
        close_mark,
        lambda body: len(body) == 15
        and struct.unpack_from(">q", body)[0] == hero["id"]
        and body[10] == 17
        and struct.unpack_from(">i", body, 11)[0] == -1,
        timeout=30,
    )
    probe.ack_loads(close_mark)
    returned = probe.current()
    with probe.store.connection() as db:
        progress = db.execute(
            "SELECT state FROM character_achievement_progress WHERE character_id=%s",
            (probe.character["id"],),
        ).fetchone()
    if progress is None or 5670 not in progress["state"].get("objectives", ()):
        raise AssertionError("The actual native seed outcome did not publish5670")
    if returned["map_id"] != 1018 or returned.get("instance_id", 0) != 0:
        raise AssertionError(
            ("Seed outcome has not returned to the native public exterior", returned)
        )
    removals = _morph_removals(probe, runner.fight_id, mark)
    result = dict(
        fight_id=runner.fight_id,
        original_seed_id=seed_id,
        operations=operations,
        winner=snapshot["winner"],
        objective_id=5670,
        initial_instance_id=initial["instance_id"],
        returned={
            key: returned.get(key)
            for key in ("map_id", "instance_id", "x", "y", "z", "breed")
        },
        native933_unapplication_frames=removals,
        form_restoration_verified=bool(removals),
        qualification="Actual native5599 action and normal finished return; no administrative outcome. Visual/deck restoration is only claimed when native933 unapplication was observed.",
    )
    probe.receipt.setdefault("school_seed_actions", []).append(result)
    probe.note("actual native School seed collection and normal return", **result)
    return result


def play_existing(
    probe,
    fight_id,
    wire_start=0,
    *,
    resume_existing=False,
    max_operations=128,
    timeout=240
):
    """Attach the normal runner to the caller's sole existing native TLS peer."""
    from tools.line2_rank23_native_tls_probe import Rank23NativeRun

    _original_seed(probe, fight_id)
    runner = Rank23NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    runner.wire_cursor = 0 if resume_existing else wire_start
    runner.native_global_turn, runner.native_turn_actor = 0, None
    runner.native_timeline_phase, runner.native_timeline_members = None, frozenset()
    runner.last_begin_identity = runner.last_acked_turn = None
    probe.peer.send(
        13332, struct.pack(">i", fight_id)
    ) if resume_existing else probe.peer.send(12523, b"\x01")
    return collect_seed(probe, runner, max_operations=max_operations, timeout=timeout)
