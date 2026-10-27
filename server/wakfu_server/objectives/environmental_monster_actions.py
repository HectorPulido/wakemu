"""Original aMg DESTROY actions, separate from item-yielding aMi collection.

Each admission reads one immutable native breed record. Scenario templates do
not establish an original breed roster, item reward or profession requirement.
"""
from functools import lru_cache


def native_action_response(monster_id, character_id, action_id):
    """Original cyl12421: target UID, performing player UID, native action ID.

    The committed caller validates the target prototype's action and physical
    performer. Publish once before12304 removes the registered target; this
    packet only triggers the original animation/script, never progress or loot.
    """
    import struct

    if type(monster_id) is not int or not -(2**63) <= monster_id < 0:
        raise ValueError("Native action response requires its negative monster UID")
    if type(character_id) is not int or not 0 < character_id < 2**63:
        raise ValueError("Native action response requires its physical player UID")
    if type(action_id) is not int or not 0 < action_id < 2**31:
        raise ValueError("Native action response requires its original action ID")
    return 12421, struct.pack(">qqq", monster_id, character_id, action_id)


def decode_request(body):
    """cnT13222 writes target Sn and action d as two signed big-endian longs."""
    import struct

    if type(body) is not bytes or len(body) != 16:
        raise ValueError("Invalid native DESTROY request length")
    monster_id, action_id = struct.unpack(">qq", body)
    if not -(1 << 63) <= monster_id < 0 or not 0 < action_id < (1 << 31):
        raise ValueError("Invalid native DESTROY target or action identity")
    return dict(monster_id=monster_id, action_id=action_id)


def _positive(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError(f"Invalid native monster {label}")
    return value


def destroy_action_from_native(monster_reference, action_id, native):
    """Validate the installed aMb.csj/aMg descriptor without a breed allowlist."""
    _positive(monster_reference, "breed")
    _positive(action_id, "action identity")
    if (
        not isinstance(native, dict)
        or native.get("native_class") != "aMg"
        or type(native.get("d")) is not int
        or native["d"] != action_id
        or type(native.get("aGJ")) is not int
        or native["aGJ"] != 3
        or type(native.get("clT")) is not str
        or type(native.get("getDuration")) is not int
        or native["getDuration"] < 0
        or type(native.get("cbH")) is not int
        or type(native.get("clx")) is not int
        or any(type(native.get(key)) is not bool for key in ("csI", "csJ", "csK"))
    ):
        raise ValueError("Missing original native aMg DESTROY descriptor")
    # All 77 recovered type3 descriptors have these operands. New criteria or
    # occupation modes need their own real producer; harvest output/XP cannot
    # stand in for them merely because the target is a monster.
    if (
        native["clT"] != ""
        or native["getDuration"] != 0
        or native["cbH"] != 0
        or native["csI"] is not False
        or native["csJ"] is not True
        or native["csK"] is not False
    ):
        raise ValueError("Unsupported original native DESTROY context")
    return dict(
        monster_reference=monster_reference,
        action_id=action_id,
        monster_action_type=3,
        condition=native["clT"],
        duration_ms=native["getDuration"],
        native_visual_action=native["clx"],
        native=dict(native),
    )


@lru_cache(maxsize=256)
def _native_destroy_action(revision, monster_reference, action_id):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(revision, ("monster-encyclopedia.json",))
    row = native_catalog.record(
        DATA_ROOT / "monster-encyclopedia.json", "monsters", str(monster_reference)
    )
    if not isinstance(row, dict) or row.get("ref") != monster_reference:
        raise ValueError("Unknown original native DESTROY breed")
    actions = row.get("world_actions")
    if not isinstance(actions, list):
        raise ValueError("Missing original native monster world actions")
    selected = [
        action
        for action in actions
        if isinstance(action, dict) and action.get("d") == action_id
    ]
    if len(selected) != 1:
        raise ValueError("Native DESTROY action is absent or ambiguous")
    return destroy_action_from_native(monster_reference, action_id, selected[0])


def native_destroy_action(monster_reference, action_id):
    from wakfu_server import native_catalog

    # Return independent plain metadata; callers cannot mutate the cached
    # descriptor used by another action or source admission.
    from copy import deepcopy

    _positive(monster_reference, "breed")
    _positive(action_id, "action identity")
    return deepcopy(
        _native_destroy_action(native_catalog.release(), monster_reference, action_id)
    )


def admit_destroy_request(
    store,
    db,
    account_id,
    generation,
    character,
    body,
    *,
    groups,
    reachable,
    loaded=False,
    blocked=False,
    location_context=None,
):
    """Authenticate cnT against the selected owner and actual available target.

    Caller owns the transaction. This admission does not remove a monster,
    grant loot, synthesize a fight or convert a request into a progress fact.
    """
    from psycopg.pq import TransactionStatus
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.monster_collect import resolve_target
    from wakfu_server.simple_item_actions import _idle

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Native DESTROY admission requires its owner transaction")
    if loaded is not True or blocked is not False or not callable(reachable):
        raise ValueError("Native DESTROY requires its loaded exploration scene")
    request = decode_request(body)
    _leased_owner(store, db, account_id, generation, character)
    actual = store.character(account_id, character["id"], db)
    if location_context is not None:
        if not callable(location_context):
            raise ValueError("Invalid native DESTROY position authority")
        actual = location_context(actual)
    if any(
        actual.get(key, 0) != character.get(key, 0)
        for key in ("map_id", "instance_id", "x", "y", "z")
    ):
        raise ValueError("Native DESTROY actor location changed")
    _idle(db, actual["id"], store.now())
    if (
        db.execute(
            "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
            (actual["id"],),
        ).fetchone()
        is not None
    ):
        raise ValueError("Another native environment occupation is active")
    monster = resolve_target(groups, actual, request["monster_id"])
    if reachable(actual, monster) is not True:
        raise ValueError("Native DESTROY target is unreachable")
    rule = native_destroy_action(monster["ref"], request["action_id"])
    return dict(character=actual, monster=monster, rule=rule)
