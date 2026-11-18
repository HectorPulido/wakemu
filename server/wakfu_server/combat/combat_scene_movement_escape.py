"""Reviewed physical escape after genuine paid movement and native area callbacks.

A pursuer keeps its original actor, state and spells. This publisher adds only
an explicit encounter result at the source-pinned native exit. It cannot turn
an ordinary victory, a requested endpoint, a teleport or a client flag into an
escape. The movement adapter owns the before/after callback boundary.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json

SCHEMA = "owned-native-movement-escape-v1"
FIELD = "native_movement_escape_receipt"
_SEAL = object()


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def declaration(descriptor, room_cells=None):
    value = None if descriptor is None else descriptor.get("native_movement_escape")
    if value is None:
        return None
    keys = {
        "schema",
        "pursuer_reference",
        "pursuer_state",
        "pursuer_state_sha256",
        "exit_map_id",
        "exit_source_id",
        "exit_destination_id",
        "exit_source_sha256",
        "exit_cell",
        "evidence",
    }
    if (
        type(value) is not dict
        or set(value) != keys
        or value["schema"] != SCHEMA
        or descriptor.get("full_room_scope") is not True
        or any(
            type(value[k]) is not int or value[k] <= 0
            for k in (
                "pursuer_reference",
                "pursuer_state",
                "exit_map_id",
                "exit_source_id",
                "exit_destination_id",
            )
        )
        or any(
            type(value[k]) is not str
            or len(value[k]) != 64
            or any(c not in "0123456789abcdef" for c in value[k])
            for k in ("pursuer_state_sha256", "exit_source_sha256")
        )
        or type(value["exit_cell"]) is not list
        or len(value["exit_cell"]) != 3
        or any(type(n) is not int for n in value["exit_cell"])
        or type(value["evidence"]) is not str
        or not value["evidence"].strip()
        or room_cells is not None
        and tuple(value["exit_cell"]) not in set(map(tuple, room_cells))
    ):
        raise ValueError("Physical escape lacks its exact native source declaration")
    from wakfu_server import generic_transports

    source = generic_transports.source(value["exit_map_id"], value["exit_source_id"])
    choices = (
        []
        if source is None
        else [
            d
            for d in source["destinations"]
            if d["destination_id"] == value["exit_destination_id"]
        ]
    )
    if (
        source is None
        or digest(source) != value["exit_source_sha256"]
        or [int(source[k]) for k in ("x", "y", "z")] != value["exit_cell"]
        or len(choices) != 1
        or choices[0]["map_id"] == value["exit_map_id"]
        or choices[0]["cyW"] != 0
        or choices[0]["cyX"] != 0
        or choices[0]["cyZ"] >= 0
        or choices[0]["native_altitude_walkable"] is not True
    ):
        raise ValueError("Physical escape lost its original free native departure")
    return value


def _scope(fight):
    record = getattr(fight, "native_encounter_scene", None)
    if (
        record is None
        or record.get("descriptor", {}).get("native_movement_escape") is None
    ):
        return None
    from .combat_encounter_scene_policy import frozen_scene

    descriptor = frozen_scene(fight)
    policy = declaration(descriptor, record["room_cells"])
    if record["scope"]["map_id"] != policy["exit_map_id"]:
        raise ValueError("Physical escape left its admitted native map")
    return record, policy


def _pursuer(fight, record, policy):
    from .combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    bindings = [
        b
        for b in record["scope"].get("actor_bindings", ())
        if b.get("ref") == policy["pursuer_reference"]
    ]
    if len(bindings) != 1:
        raise ValueError("Physical escape requires its one genuine native pursuer")
    identity = bindings[0]["actor_id"]
    actor = fight.actors.get(identity)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(identity, {})
    if (
        actor is None
        or actor.controlled is not False
        or actor.team != roles.npc_team
        or not fight._in_play(actor)
        or receipt.get("ref") != policy["pursuer_reference"]
        or receipt.get("initialized") is not True
        or not any(
            e.reference == policy["pursuer_state"] for e in actor.state_ledger.entries
        )
    ):
        raise ValueError(
            "Physical escape lost its living native pursuer and innate state"
        )
    return actor


@dataclass(frozen=True)
class _CommittedEscape:
    fight: object
    actor_id: int
    owner_id: int
    turn_id: int
    origin: tuple
    destination: tuple
    scene_sha256: str
    policy: dict
    payment: dict
    seal: object = field(default=None, repr=False, compare=False)


def prepare_committed(fight, actor, origin, destination):
    """Capture only inside execute_steps' real QI move and PA debit scope."""
    scope = _scope(fight)
    if scope is None:
        return None
    record, policy = scope
    if tuple(destination) != tuple(policy["exit_cell"]):
        return None
    from .combat_encounter_roles import assigned_roles
    from .combat_movement_payment_events import _step_payment
    from .combat_encounter_scene_states import native_state_source_digest
    from .combat_server_spell import states_catalog

    roles = assigned_roles(fight)
    payment = _step_payment.get()
    if (
        fight.phase != "active"
        or fight.current is not actor
        or fight.actors.get(actor.id) is not actor
        or actor.controlled is not True
        or actor.owner_id is None
        or actor.team != roles.player_team
        or not fight._in_play(actor)
        or getattr(actor, "native_summon_source", None) is not None
        or payment is None
        or payment["fight"] is not fight
        or payment["actor_id"] != actor.id
        or payment["turn_id"] != fight.turn_id
        or payment["origin"] != tuple(origin)
        or payment["destination"] != tuple(destination)
        or actor.position != tuple(destination)
        or payment["mp_paid"] <= 0
    ):
        return None
    if (
        native_state_source_digest(states_catalog(), policy["pursuer_state"])
        != policy["pursuer_state_sha256"]
    ):
        raise ValueError("Physical escape original native state program changed")
    _pursuer(fight, record, policy)
    return _CommittedEscape(
        fight,
        actor.id,
        actor.owner_id,
        fight.turn_id,
        tuple(origin),
        tuple(destination),
        record["sha256"],
        deepcopy(policy),
        {
            k: payment[k]
            for k in ("index", "ap_paid", "mp_paid", "mp_before", "mp_after")
        },
        _SEAL,
    )


def settle_committed(fight, witness):
    """Run after unchanged native movement callbacks, including lethal aura."""
    if witness is None:
        return False
    if (
        type(witness) is not _CommittedEscape
        or witness.seal is not _SEAL
        or witness.fight is not fight
    ):
        raise ValueError(
            "Physical escape requires its sealed committed movement witness"
        )
    scope = _scope(fight)
    if scope is None:
        raise ValueError("Physical escape lost its admitted scene")
    record, policy = scope
    actor = fight.actors.get(witness.actor_id)
    if (
        record["sha256"] != witness.scene_sha256
        or policy != witness.policy
        or fight.turn_id != witness.turn_id
        or actor is None
        or actor.owner_id != witness.owner_id
    ):
        raise ValueError("Physical escape changed during its native callbacks")
    # Native catches/death, displacement or another terminal result take priority.
    if (
        fight.phase != "active"
        or not fight._in_play(actor)
        or actor.position != witness.destination
    ):
        return False
    if getattr(fight, FIELD, None) is not None:
        return False
    pursuer = _pursuer(fight, record, policy)
    from .combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    receipt = dict(
        schema=SCHEMA,
        scene_sha256=record["sha256"],
        scope=deepcopy(record["scope"]),
        actor_id=actor.id,
        owner_id=actor.owner_id,
        pursuer_id=pursuer.id,
        origin=list(witness.origin),
        destination=list(witness.destination),
        turn_id=witness.turn_id,
        payment=deepcopy(witness.payment),
        native_exit=dict(
            map_id=policy["exit_map_id"],
            source_id=policy["exit_source_id"],
            destination_id=policy["exit_destination_id"],
        ),
    )
    setattr(fight, FIELD, receipt)
    fight.phase, fight.winner = "finished", roles.player_team
    fight._event(
        "finished",
        winner=roles.player_team,
        reason="owned_scene_native_physical_escape",
        actor_id=actor.id,
        exit_source_id=policy["exit_source_id"],
    )
    return True


def outcome_qualified(fight):
    """A normal win or kill is never this declared challenge's success."""
    scope = _scope(fight)
    if scope is None:
        return True
    record, policy = scope
    receipt = getattr(fight, FIELD, None)
    if not isinstance(receipt, dict):
        return False
    actor = fight.actors.get(receipt.get("actor_id"))
    from .combat_encounter_roles import assigned_roles

    return (
        fight.phase == "finished"
        and fight.winner == assigned_roles(fight).player_team
        and receipt.get("schema") == SCHEMA
        and receipt.get("scene_sha256") == record["sha256"]
        and receipt.get("scope") == record["scope"]
        and actor is not None
        and actor.controlled is True
        and actor.owner_id == receipt.get("owner_id")
        and actor.hp > 0
        and list(actor.position) == policy["exit_cell"]
        and receipt.get("destination") == policy["exit_cell"]
        and receipt.get("native_exit")
        == dict(
            map_id=policy["exit_map_id"],
            source_id=policy["exit_source_id"],
            destination_id=policy["exit_destination_id"],
        )
    )
