"""Native world guard rendering and actual13130 rear-strike admission.

Only an owner-scoped pinned stealth trial may consume its isolated actor IDs.
Ordinary groups and every other map retain the existing battle admission path.
"""

import struct
from uuid import uuid4

from wakfu_server import owned_object_trials as trials
from wakfu_server import owned_world_stealth_program as program
from wakfu_server.owned_object_trial_effects import executor


def _trial(selected):
    matches = [row for row in selected["trials"] if row["kind"] == "stealth_course"]
    if len(matches) > 1:
        raise ValueError("One owned scene cannot publish competing guard sets")
    return matches[0] if matches else None


def actor_id(instance_id, guard_id):
    if (
        type(instance_id) is not int
        or not (1 << 57) < instance_id < (1 << 60)
        or type(guard_id) is not int
        or not 0 < guard_id < 16
    ):
        raise ValueError(
            "Stealth actor identity requires its exact native instance and guard"
        )
    # Namespace distinct from ordinary durable group actors and dialogue NPCs.
    return -(1 << 60) - (instance_id - (1 << 57)) * 16 - guard_id


def _guard_records(selected, state, character):
    trial = _trial(selected)
    if trial is None:
        return []
    config = program.validate(trial)
    if config["map_id"] != character["map_id"] or character.get("instance_id", 0) <= 0:
        raise ValueError("Stealth actors escaped their pinned private map")
    current = state["trials"].get(trial["id"], {}).get("program")
    if current is None or current["stage"] in {"failed", "declined"}:
        current = program.stealth.begin(config, config["start"])
    if current["profile_sha256"] != program.stealth.digest(config):
        raise ValueError("Stealth actor state differs from its pinned profile")
    if current["stage"] == "success":
        return []
    return [
        (
            guard,
            current["guards"][str(guard["id"])],
            guard["patrol"][current["guards"][str(guard["id"])]["patrol_index"]],
        )
        for guard in config["guards"]
        if current["guards"][str(guard["id"])]["hits"] < config["rear_hits"]
    ]


def render(selected, state, character):
    """Publish authoritative guard positions only after the caller's commit."""
    trial = _trial(selected)
    if trial is None:
        return []
    from wakfu_server import monsters
    from wakfu_server.combat_monster_world import spawn_monster, remove_message

    config = program.validate(trial)
    packets = [
        remove_message(
            [
                actor_id(character["instance_id"], guard["id"])
                for guard in config["guards"]
            ]
        )
    ]
    for guard, status, pose in _guard_records(selected, state, character):
        native = monsters.reference(guard["reference"])
        if (
            program.stealth.digest(native) != guard["native_profile_sha256"]
            or not native["min_level"] <= guard["level"] <= native["max_level"]
        ):
            raise ValueError("Stealth guard appearance differs from its original breed")
        identity = actor_id(character["instance_id"], guard["id"])
        monster = monsters.owned_instance(
            guard["reference"],
            guard["level"],
            identity,
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            x=pose["position"][0],
            y=pose["position"][1],
            z=pose["position"][2],
            team=1,
        )
        packets.append(
            (
                12608,
                spawn_monster(monster, group_id=-identity, direction=pose["direction"]),
            )
        )
    return packets


def render_current(db, store, character):
    selected, current = trials._scope(db, store, character)
    return render(selected, trials._load_state(db, current, selected), current)


def decode_attack(selected, state, character, body):
    if not isinstance(body, bytes) or len(body) != 19:
        raise ValueError("Stealth attack needs the original native13130 layout")
    target, x, y, z, auto_lock = struct.unpack(">qiihB", body)
    trial = _trial(selected)
    if trial is None:
        return None
    candidates = {
        actor_id(character["instance_id"], guard["id"]): guard
        for guard in trial["program"]["guards"]
    }
    if target not in candidates:
        return None
    current = next(
        (
            (guard, status, pose)
            for guard, status, pose in _guard_records(selected, state, character)
            if guard["id"] == candidates[target]["id"]
        ),
        None,
    )
    if (
        current is None
        or auto_lock not in (0, 1)
        or [x, y, z] != current[2]["position"]
    ):
        raise ValueError("Stealth attack target is stale or already neutralized")
    if [character[axis] for axis in ("x", "y", "z")] != current[2]["rear_cell"]:
        raise ValueError("Approach the guard's current rear floor before attacking")
    return dict(kind="stealth_attack", guard_id=current[0]["id"])


def handle_attack(session):
    """Consume a real native attack only for the selected owner's guard set."""
    state, runtime = session.state, session.runtime
    if (
        state.opcode != 13130
        or state.character is None
        or not state.loaded
        or not getattr(state.connection, "owned_object_trials_active", False)
        or not isinstance(state.body, bytes)
        or len(state.body) != 19
    ):
        return False
    from . import owned_object_trial_dispatch
    from wakfu_server.inventory_items import _lease
    from wakfu_server.environment_interactions import _guard

    if (
        state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
        or session.environment_blocked()
    ):
        raise ValueError("Stealth attack requires its ready idle owner")
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            selected, _ = trials._scope(db, runtime.STORE, current)
            trial = _trial(selected)
            if trial is None:
                return False
            _lease(runtime.STORE, db, state.account_id, state.generation, current["id"])
            _guard(db, current["id"])
            event = decode_attack(
                selected, trials._load_state(db, current, selected), current, state.body
            )
            if event is None:
                return False
            result = trials._settle(
                db,
                runtime.STORE,
                current,
                selected,
                event,
                uuid4().hex,
                executor(selected),
            )
            character = runtime.STORE.character(state.account_id, current["id"], db)
            packets = list(result["packets"])
            packets.extend(
                render(selected, trials._load_state(db, character, selected), character)
            )
        owned_object_trial_dispatch._publish(session, character, packets)
    return True
