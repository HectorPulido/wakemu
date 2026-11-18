"""Bounded native2014 training actions on the owner's existing TLS peer.

The real3174 temporary book, actual3173 enemy, native state resources and
original117956 capture own the outcome. No checkpoint or runtime is modified.
"""
import struct
import time
from types import SimpleNamespace

from tools.line3_fields_combat import _in_shape, path_to_cast
from tools.line4_owned_actions import capture

# Read-only export from the active BF4B World native8028 zero-level tables.
# Exact five-row metadata (ranges, roots, criteria and flags) canonical SHA256:
# e914f8f27fa607abab8984cfb274416d0aca0a79782ee35255d9675fb13ff432
# This is client movement planning only; World still validates every real cast.
# It intentionally avoids the owner's older host catalogue cache.
TRAINER_NATIVE_SHAPES = {
    4476: ((0, 0, False, False),),
    4477: ((1, 5, False, False),),
    4480: ((1, 3, False, False),),
    4479: ((1, 1, False, False),),
    4478: ((1, 1, False, False),),
}
# Actual BF4B native-spell-limits.json: per-turn1; table-round intervals.
TRAINER_INTERVALS = {4476: 3, 4477: 3, 4480: 4, 4479: 3, 4478: 0}
# Literal source-verified132-cell arena witness; every cycle cell has degree>=3.
RETREAT_ENTRY = [(2, y, 0) for y in range(-8, -3)]
RETREAT_CYCLE = (
    [(x, -4, 0) for x in range(2, 9)]
    + [(8, y, 0) for y in range(-3, 3)]
    + [(x, 2, 0) for x in range(7, 1, -1)]
    + [(2, y, 0) for y in range(1, -4, -1)]
)


def _fixed_retreat(snapshot, owner_id):
    """Four literal legal steps; no greedy movement or new path search."""
    here = tuple(snapshot["actors"][str(owner_id)]["position"])
    edges = {tuple(map(tuple, edge)) for edge in snapshot["edges"]}
    occupied = {
        tuple(row["position"])
        for row in snapshot["actors"].values()
        if row["hp"] > 0 and row["id"] != owner_id
    }
    if here in RETREAT_ENTRY[:-1]:
        route = RETREAT_ENTRY[RETREAT_ENTRY.index(here) + 1 :] + RETREAT_CYCLE[1:]
        choices = [route[:4]]
    elif here in RETREAT_CYCLE:
        index = RETREAT_CYCLE.index(here)
        choices = [
            [
                RETREAT_CYCLE[(index + direction * step) % len(RETREAT_CYCLE)]
                for step in range(1, 5)
            ]
            for direction in (1, -1)
        ]
    else:
        # A real native PUSH may change the owner position. Reuse the existing
        # native-edge path helper to rejoin the declared open cycle, not a new
        # retreat solver or a fictional reset of the owner's position.
        from tools.line4_archaeology_actions import _path

        safe_edges = [
            [list(left), list(right)]
            for left, right in edges
            if left not in occupied and right not in occupied
        ]
        goals = [point for point in RETREAT_CYCLE if point not in occupied]
        rejoin = list(map(tuple, _path(safe_edges, here, goals)))[1:]
        if not rejoin or len(rejoin) > 8:
            raise AssertionError(
                (
                    "Native push needs an owner-reviewed route back to the open cycle",
                    here,
                )
            )
        if len(rejoin) >= 4:
            choices = [rejoin[:4]]
        else:
            index = RETREAT_CYCLE.index(rejoin[-1])
            choices = [
                rejoin
                + [
                    RETREAT_CYCLE[(index + direction * step) % len(RETREAT_CYCLE)]
                    for step in range(1, 5 - len(rejoin))
                ]
                for direction in (1, -1)
            ]
    for path in choices:
        if not any(point in occupied for point in path) and all(
            (left, right) in edges for left, right in zip([here] + path, path)
        ):
            return path
    raise AssertionError(
        (
            "Both literal native retreat directions are blocked; stop instead of camping",
            here,
        )
    )


def _cast_rounds(probe, fight_id):
    """Resolve retained successful action starts against original wire rounds."""
    from wakfu_server.combat_core_reconstruction import decode_core_packet

    with probe.peer.observation_lock:
        records = list(probe.peer.records)
    boundaries, current = [], None
    for index, (opcode, body) in enumerate(records):
        if len(body) < 4 or struct.unpack_from(">i", body)[0] != fight_id:
            continue
        if opcode == 13477 and len(body) == 14:
            current = struct.unpack_from(">h", body, 12)[0]
        elif opcode in (12847, 12053):
            try:
                current = decode_core_packet(opcode, body)["timeline"]["round"]
            except (ValueError, KeyError):
                continue
        else:
            continue
        boundaries.append((index, current))
    last = {}
    for attempt in probe.receipt.get("mount2014_training_attempts", ()):
        if attempt["fight_id"] != fight_id:
            continue
        for action in attempt["operations"]:
            if action.get("kind") not in ("native_training_cast", "native_sprint"):
                continue
            spell = action.get("spell")
            if spell not in TRAINER_INTERVALS:
                continue
            round_id = action.get("native_round")
            if round_id is None and "wire_start" in action:
                before = [
                    round_id
                    for index, round_id in boundaries
                    if index < action["wire_start"]
                ]
                round_id = before[-1] if before else None
            if round_id is None:
                raise ValueError(
                    ("Successful training cast lacks its actual native round", action)
                )
            last[spell] = max(last.get(spell, round_id), round_id)
    return last


def training_status(probe, runner):
    """Read-only source/state/cooldown inspection; sends no packet or turn."""
    _selected, originals = _source(probe, runner)
    snapshot = runner.checkpoint()
    level, _witnesses = _wire_states(probe, runner.fight_id)
    round_id = snapshot["runtime"]["round"]
    last = _cast_rounds(probe, runner.fight_id)
    return dict(
        native_round=round_id,
        last_successful_round=last,
        available={
            spell: spell not in last or round_id - last[spell] >= max(1, interval)
            for spell, interval in TRAINER_INTERVALS.items()
        },
        endurance=level(probe.character["id"], 2999),
        panic=level(originals[0]["id"], 3000),
        exhaustion=level(originals[0]["id"], 3003),
        harness=level(originals[0]["id"], 3002),
    )


def inspect_training_wire(probe, runner, *, start=0):
    """Read existing packets/checkpoint only; never ACK, move or advance a turn."""
    from collections import Counter
    from wakfu_server.combat_protocol_reconstruction import decode_packet

    with probe.peer.observation_lock:
        records = list(enumerate(probe.peer.records[start:], start=start))
    families, relevant, errors = Counter(), [], []
    for sequence, (opcode, body) in records:
        if len(body) < 4 or struct.unpack_from(">i", body)[0] != runner.fight_id:
            continue
        if opcode not in (12613, 13497, 13560, 13624):
            continue
        try:
            decoded = decode_packet(opcode, body)
        except ValueError as error:
            errors.append(dict(sequence=sequence, opcode=opcode, error=str(error)))
            continue
        effect = decoded.get("effect", {})
        if effect:
            families[effect.get("family")] += 1
        if (
            opcode == 13624
            or effect.get("definition") in (117976, 117977, 117978, 119895)
            or effect.get("state_id") in (2999, 3000, 3001, 3002, 3003)
        ):
            relevant.append(
                dict(
                    sequence=sequence,
                    opcode=opcode,
                    decoded=decoded,
                    body_hex=body.hex(),
                )
            )
    snapshot = runner.checkpoint() or {}
    return dict(
        fight_id=runner.fight_id,
        start=start,
        status=training_status(probe, runner),
        effect_family_counts=dict(families),
        relevant_frames=relevant,
        decode_errors=errors,
        checkpoint_schema=snapshot.get("checkpoint_schema"),
        checkpoint_has_events="events" in snapshot,
        checkpoint_relevant_events=[
            row
            for row in snapshot.get("events", ())
            if row.get("generic_effect") in (117976, 117977, 117978, 119895)
            or row.get("state_id") == 3003
        ],
        qualification="Only retained wire/checkpoint observations; compact recovery snapshots omit ordinary event ledgers",
    )


def _move_one(runner, owner_id, point):
    """The existing native paid movement action, without peer.view planning."""
    return runner.action(
        12161,
        struct.pack(">q", owner_id) + struct.pack(">iih", *point),
        label="native training move %s" % (tuple(point),),
    )


def _source(probe, runner):
    current = probe.current()
    if current["map_id"] != 879 or current.get("instance_id", 0) <= 0:
        raise ValueError("Enter the actual owned879 training enclosure first")
    selected = probe.configuration()["topology"].get("owned_story_controller", {})
    if selected.get("id") != "astrub-mount-training-879":
        raise ValueError("The exact native2014 training controller is required")
    with probe.store.connection() as db:
        groups = db.execute(
            "SELECT map_id,instance_id,members FROM combat_groups WHERE fight_id=%s",
            (runner.fight_id,),
        ).fetchall()
    if (
        len(groups) != 1
        or groups[0]["map_id"] != 879
        or groups[0]["instance_id"] != current["instance_id"]
        or len(groups[0]["members"]) != 1
        or groups[0]["members"][0]["ref"] != 3173
    ):
        raise ValueError("Training requires its one admitted original3173 target")
    return selected, groups[0]["members"]


def _wire_states(probe, fight_id):
    """Observe original310 carriers, including current native bootstrap myF."""
    from wakfu_server.combat_protocol_reconstruction import decode_packet, _effect
    from wakfu_server.combat_remote_effects import decode_remote_effects
    from wakfu_server.combat_wire import decode_bootstrap

    states, witnesses = {}, set()
    with probe.peer.observation_lock:
        records = list(probe.peer.records)
    for opcode, body in records:
        if len(body) < 4 or struct.unpack_from(">i", body)[0] != fight_id:
            continue
        if opcode == 12847:
            bootstrap = decode_bootstrap(body)
            for actor in bootstrap["participants"]:
                if bootstrap["compact"]:
                    continue
                identity = actor["actor_id"]
                witnesses.add(identity)
                states = {
                    uid: effect
                    for uid, effect in states.items()
                    if effect.get("target") != identity
                }
                for row in decode_remote_effects(actor["myF"]):
                    if row.effect_class == 310:
                        effect = _effect(row.payload, 310)
                        states[effect["uid"]] = effect
        elif opcode in (12613, 13497, 13560):
            row = decode_packet(opcode, body)
            effect = row.get("effect", {})
            if effect.get("family") == 310:
                if opcode == 13560:
                    states.pop(effect["uid"], None)
                else:
                    states[effect["uid"]] = effect
                    witnesses.add(effect.get("target"))

    def level(actor, reference):
        values = [
            row["level"]
            for row in states.values()
            if row.get("target") == actor and row.get("state_id") == reference
        ]
        if len(values) > 1:
            raise ValueError(
                ("Ambiguous original wire state carriers", actor, reference, values)
            )
        return values[0] if values else 0

    return level, witnesses


def train_existing(probe, runner, *, max_operations=96, timeout=240):
    """Pay actual endurance, chase legally, harness and genuinely capture."""
    if not 1 <= max_operations <= 128 or not 1 <= timeout <= 600:
        raise ValueError("Use bounded training operations and deadline")
    from wakfu_server.owned_story_capture_qualification import qualified

    selected, originals = _source(probe, runner)
    target_id, owner_id = originals[0]["id"], probe.character["id"]
    shapes = TRAINER_NATIVE_SHAPES
    mark, operations, deadline = probe.peer.mark(), [], time.monotonic() + timeout
    last_cast = _cast_rounds(probe, runner.fight_id)
    blocked = set()
    try:
        while len(operations) < max_operations and time.monotonic() < deadline:
            snapshot = runner.checkpoint()
            if snapshot and snapshot.get("phase") == "finished":
                break  # Inspect terminal state before waiting for another turn.
            snapshot = runner.ready_for_input()
            if snapshot.get("phase") == "finished":
                break
            hero, target = snapshot["actors"][str(owner_id)], snapshot["actors"].get(
                str(target_id)
            )
            if target is None or hero["hp"] <= 0 or target["hp"] <= 0:
                raise AssertionError(
                    "The original living trainer and3173 target are required"
                )
            level, witnesses = _wire_states(probe, runner.fight_id)
            if owner_id not in witnesses or target_id not in witnesses:
                raise AssertionError(
                    "Current native bootstrap/state observations are incomplete; resynchronize normally"
                )
            endurance = level(owner_id, 2999)
            panic, exhaustion, harness = (
                level(target_id, ref) for ref in (3000, 3003, 3002)
            )
            facts = dict(
                endurance=endurance, panic=panic, exhaustion=exhaustion, harness=harness
            )
            round_id = snapshot["runtime"]["round"]
            facts["native_round"] = round_id

            def available(spell):
                return (round_id, spell) not in blocked and (
                    spell not in last_cast
                    or round_id - last_cast[spell] >= max(1, TRAINER_INTERVALS[spell])
                )

            if hero["turn_count"] <= 3 and exhaustion == 0 and not harness:
                if panic > 20:
                    raise AssertionError(
                        (
                            "The initial three-turn charge no longer matches its healthy witness",
                            facts,
                        )
                    )
                operations.append(
                    dict(kind="bounded_initial_endurance_charge", **facts)
                )
                runner.end_turn()
                continue
            # These are native criteria/costs, not AP substitutes or guessed rates.
            candidates = []
            if harness and exhaustion >= 12 and endurance >= 5:
                candidates.append(4478)
            if panic >= 18 and endurance >= 4:
                candidates.append(4477)
            if exhaustion >= 12 and not harness and endurance >= 10:
                candidates.append(4479)  # Preserve capture's further5 endurance.
            # Do not cancel ordinary running fatigue by continually removingMP.
            # At10/11, one legal restriction can reach the actual12 threshold;
            # reserve its3 endurance plus the native5+5 harness/capture costs.
            if 10 <= exhaustion < 12 and endurance >= 13:
                candidates.append(4480)
            spell = next((spell for spell in candidates if available(spell)), None)
            if spell is None:
                if panic >= 28:
                    raise AssertionError(
                        (
                            "Panic approaches native30; no blind end turn while Soothing is unavailable",
                            facts,
                            last_cast,
                            TRAINER_INTERVALS,
                        )
                    )
                path = _fixed_retreat(snapshot, owner_id)
                if hero["mp"] < 4:
                    if endurance < 6 or not available(4476):
                        raise AssertionError(
                            (
                                "Insufficient paidMP for literal retreat; do not camp",
                                facts,
                                hero["mp"],
                            )
                        )
                    runner.cast(4476, tuple(hero["position"]), class_spell=False)
                    last_cast[4476] = round_id
                    operations.append(
                        dict(
                            kind="native_sprint", spell=4476, casting_uid=4476, **facts
                        )
                    )
                for point in path:
                    before_move = runner.checkpoint()
                    if (
                        before_move.get("phase") != "active"
                        or before_move["actors"][str(owner_id)]["mp"] <= 0
                    ):
                        raise AssertionError(
                            "Actual nativeMP exhausted before the literal retreat finished"
                        )
                    _move_one(runner, owner_id, point)
                    operations.append(
                        dict(
                            kind="literal_open_cycle_retreat", cell=list(point), **facts
                        )
                    )
                operations.append(dict(kind="normal_end_turn", **facts))
                runner.end_turn()
                continue
            here, destination = tuple(hero["position"]), tuple(target["position"])
            if _in_shape(here, destination, shapes[spell]):
                cast_mark = probe.peer.mark()
                try:
                    after = runner.cast(spell, destination, class_spell=False)
                except AssertionError as error:
                    if not any(
                        message in str(error)
                        for message in (
                            "Native spell cast interval has not elapsed",
                            "Native spell maximum casts per turn reached",
                            "Native spell maximum casts per target reached",
                        )
                    ):
                        raise
                    blocked.add((round_id, spell))
                    operations.append(
                        dict(
                            kind="observed_native_usage_guard",
                            rejected=str(error),
                            spell=spell,
                            wire_start=cast_mark,
                            **facts
                        )
                    )
                    continue  # Reobserve, then choose a different legal action.
                last_cast[spell] = round_id
                operations.append(
                    dict(
                        kind="native_training_cast",
                        spell=spell,
                        casting_uid=spell,
                        target_id=target_id,
                        cell=list(destination),
                        wire_start=cast_mark,
                        **facts
                    )
                )
                if after.get("phase") == "finished":
                    snapshot = after
                    break
                continue
            if hero["mp"] <= 0:
                if endurance >= 6 and available(4476):
                    runner.cast(4476, here, class_spell=False)
                    last_cast[4476] = round_id
                    operations.append(
                        dict(
                            kind="native_sprint", spell=4476, casting_uid=4476, **facts
                        )
                    )
                else:
                    if panic >= 28:
                        raise AssertionError(
                            (
                                "Native panic30 risk before another turn",
                                facts,
                                last_cast,
                            )
                        )
                    operations.append(dict(kind="normal_end_turn", **facts))
                    runner.end_turn()
                continue
            path = path_to_cast(snapshot, hero, target, {spell: shapes[spell]})
            if not path:
                raise AssertionError(
                    ("No actual native chase path", here, destination, spell, facts)
                )
            # One paid movement step; reobserve actual endurance and target each time.
            _move_one(runner, owner_id, path[0])
            operations.append(dict(kind="native_movement", cell=list(path[0]), **facts))
        snapshot = runner.checkpoint()
        if not snapshot or snapshot.get("phase") != "finished":
            raise AssertionError(
                (
                    "Native training operation/deadline bound reached",
                    len(operations),
                    snapshot,
                )
            )
        actors = {
            int(identity): SimpleNamespace(**row)
            for identity, row in snapshot["actors"].items()
        }
        evidence = SimpleNamespace(
            actors=actors,
            phase=snapshot["phase"],
            winner=snapshot["winner"],
            events=snapshot.get("events", ()),
            native_summon_registrations=snapshot.get("native_summon_registrations", {}),
        )
        if not qualified(selected, evidence, owner_id, originals, 1):
            raise AssertionError(
                "Terminal evidence lacks actual original-owner117956 capture followed by death"
            )
        close_mark = probe.peer.mark()
        probe.peer.send(12925, struct.pack(">iB", runner.fight_id, 1))
        probe.ack_loads(close_mark)
        due = time.monotonic() + 10
        while time.monotonic() < due:
            if 4074 in probe.progress()["objectives"]:
                result = dict(
                    fight_id=runner.fight_id,
                    original_target_id=target_id,
                    operations=operations,
                    native_capture_effect=117956,
                    objective_id=4074,
                    qualification="Actual native training resources and original117956 capture; no administrative outcome",
                )
                probe.receipt.setdefault("mount2014_native_training", []).append(result)
                probe.note(
                    "actual original Dragoturkey capture completed2014 training",
                    **result
                )
                return result
            time.sleep(0.05)
        raise AssertionError(
            "Qualified actual capture did not settle4074 after ordinary finished return"
        )
    finally:
        probe.receipt.setdefault("mount2014_training_attempts", []).append(
            dict(fight_id=runner.fight_id, operations=operations)
        )
        capture(probe, mark)


def play_existing(
    probe,
    fight_id,
    wire_start=0,
    *,
    resume_existing=False,
    max_operations=96,
    timeout=240
):
    """Attach the established runner to the sole existing authenticated peer."""
    from tools.line2_rank23_native_tls_probe import Rank23NativeRun

    runner = Rank23NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    _source(probe, runner)
    runner.wire_cursor = 0 if resume_existing else wire_start
    runner.native_global_turn, runner.native_turn_actor = 0, None
    runner.native_timeline_phase, runner.native_timeline_members = None, frozenset()
    runner.last_begin_identity = runner.last_acked_turn = None
    if not (runner.checkpoint() or {}).get("phase") == "finished":
        probe.peer.send(
            13332, struct.pack(">i", fight_id)
        ) if resume_existing else probe.peer.send(12523, b"\x01")
    return train_existing(probe, runner, max_operations=max_operations, timeout=timeout)
