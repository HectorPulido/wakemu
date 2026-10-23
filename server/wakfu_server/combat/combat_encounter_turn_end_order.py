"""Versioned encounter reconstruction of owned regeneration/end ordering.

This orders existing native publications. It does not reinterpret their event
IDs, channels, suppression, native criteria, resource costs or table counter.
"""
from copy import deepcopy
from functools import lru_cache

DEFAULT_ORDER = (1002, 1037)
_FIELDS = frozenset(
    (
        "policy",
        "authority",
        "catalog_revision",
        "map_id",
        "monster_references",
        "boss_reference",
        "boss_constructor_state",
        "table_turns",
        "event_ids",
    )
)


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(policy):
    if not isinstance(policy, str) or not policy:
        raise ValueError("Invalid encounter turn-end policy version")
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_turn_end_order_versions WHERE policy=%s", (policy,)
        ).fetchone()
    if row is None:
        raise ValueError("Unknown encounter turn-end policy version")
    result = dict(row)
    for key in ("monster_references", "table_turns", "event_ids"):
        result[key] = list(result[key])
    if (
        set(result) != _FIELDS
        or result["policy"] != policy
        or not isinstance(result["authority"], str)
        or not result["authority"]
        or not isinstance(result["catalog_revision"], str)
        or len(result["catalog_revision"]) != 64
        or type(result["map_id"]) is not int
        or any(
            type(result[key]) is not int or result[key] <= 0
            for key in ("boss_reference", "boss_constructor_state")
        )
        or not result["monster_references"]
        or any(
            type(value) is not int or value <= 0
            for value in result["monster_references"]
        )
        or sorted(set(result["monster_references"])) != result["monster_references"]
        or result["boss_reference"] not in result["monster_references"]
        or not result["table_turns"]
        or any(type(value) is not int or value <= 0 for value in result["table_turns"])
        or sorted(set(result["table_turns"])) != result["table_turns"]
        or any(type(value) is not int for value in result["event_ids"])
        or tuple(result["event_ids"])
        not in (DEFAULT_ORDER, tuple(reversed(DEFAULT_ORDER)))
    ):
        raise ValueError("Malformed immutable encounter turn-end policy")
    return result


def freeze_turn_end_order_policy(fight, *, roles):
    """Read the active pointer only during fresh participant admission."""
    from wakfu_server import native_catalog

    if fight.phase != "placement":
        raise ValueError("Encounter turn-end policy requires fresh placement")
    if hasattr(fight, "native_turn_end_order_policy"):
        record = fight.native_turn_end_order_policy
        if record is None:
            return None
        frozen = order_policy_from_record(record)
    else:
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_turn_end_order_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Encounter turn-end policy differs from admission or catalog")
    # Absence is also an admission decision; a retry must never opt in after
    # another transaction changes the active pointer.
    fight.native_turn_end_order_policy = frozen
    return deepcopy(frozen)


def order_policy_from_record(record):
    """Verify a frozen version without following the mutable active pointer."""
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or record != _version(record.get("policy"))
    ):
        raise ValueError("Frozen encounter turn-end policy changed")
    return deepcopy(record)


def turn_end_event_order(fight, *, actor_id):
    """Apply the frozen order only to its actual owned boss and exact cycles."""
    record = getattr(fight, "native_turn_end_order_policy", None)
    if record is None:
        return DEFAULT_ORDER
    frozen = order_policy_from_record(record)
    from .combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError(
            "Encounter turn-end order differs from frozen participant scope"
        )
    actor = fight.actors.get(actor_id)
    if actor is None or actor.controlled or actor.team != roles.npc_team:
        return DEFAULT_ORDER
    table = getattr(fight, "native_table_turn", None)
    if type(table) is not int:
        raise ValueError("Encounter turn-end order requires its native integer table")
    if table not in frozen["table_turns"]:
        return DEFAULT_ORDER
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor_id, {})
    if receipt.get("ref") != frozen["boss_reference"]:
        return DEFAULT_ORDER
    if (
        fight.phase != "active"
        or fight.current is None
        or fight.current.id != actor_id
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == frozen["boss_constructor_state"]
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Encounter turn-end order lacks its actual owned native boss")
    return tuple(frozen["event_ids"])
