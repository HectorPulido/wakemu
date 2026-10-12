"""Server-only adapters over durable native receipts; caller owns gameplay lease.

Plant bindings are trusted prepare/commit values, never client-selected facts.
No inventory or live world resource lookup: last seeds may be consumed and a
successfully planted resource may later be harvested or destroyed.
"""
import uuid
from . import service, engine


def _noop():
    return {"replayed": False, "updated": [], "completed": []}


def original_kills(db, account_id, character_id, fight_id, *, definitions=None):
    """Call after native achievements.service.settle in its same transaction."""
    service._owner(db, account_id, character_id, True)
    if type(fight_id) is not int or not 0 < fight_id < 2**63:
        raise ValueError("Invalid native fight identity")
    key = "fight:" + str(fight_id)
    row = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character_id, key),
    ).fetchone()
    if row is None:
        raise ValueError("Missing accredited native combat receipt")
    payload = row["payload"]
    if (
        type(payload) is not dict
        or type(payload.get("fight_id")) is not int
        or payload["fight_id"] != fight_id
    ):
        raise ValueError("Native combat receipt identity mismatch")
    originals = payload.get("original_monsters")
    if type(originals) is not list:
        raise ValueError("Missing accredited original monster roster")
    actors = []
    for monster in originals:
        if type(monster) is not list or len(monster) != 2:
            raise ValueError("Invalid native original monster receipt")
        actors.append({"actor_id": monster[0], "reference": monster[1]})
    if not actors:
        return _noop()
    event = engine.event_payload(
        {"kind": "original_monster_killed", "fight_id": fight_id, "actors": actors}
    )
    return service.settle(db, account_id, character_id, key, event, definitions)


def monster_planting(
    db,
    account_id,
    character_id,
    operation_id,
    *,
    request,
    resource,
    seed,
    definition,
    actual_seed_reference,
    definitions=None
):
    """Call in creation transaction with owned item ref and validated prepare data.

    This adapter does not independently authenticate a catalog supplied by its
    caller. Only the server prepare/commit path may supply seed/definition and
    actual_seed_reference. Frozen receipt validates request and created resource;
    custom event then freezes the family binding for future replay.
    """
    service._owner(db, account_id, character_id, True)
    try:
        parsed = uuid.UUID(operation_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Invalid planting operation UUID") from exc
    if parsed.hex != operation_id or parsed.int == 0:
        raise ValueError("Noncanonical planting operation UUID")
    row = db.execute(
        "SELECT character_id,item_uid,request,resource,resource_uid,success "
        "FROM planting_receipts WHERE operation_id=%s",
        (operation_id,),
    ).fetchone()
    if row is None or row["character_id"] != character_id:
        raise ValueError("Missing owned planting receipt")
    if (
        type(request) is not dict
        or row["request"] != request
        or row["item_uid"] != request.get("item_uid")
    ):
        raise ValueError("Planting request receipt mismatch")
    if row["success"] is False:
        return _noop()
    if row["success"] is not True:
        raise ValueError("Invalid planting success receipt")
    if (
        type(resource) is not dict
        or row["resource"] != resource
        or type(resource.get("resource_uid")) is not int
        or resource["resource_uid"] <= 0
        or row["resource_uid"] != resource["resource_uid"]
    ):
        raise ValueError("Planting resource receipt mismatch")
    if (
        type(seed) is not dict
        or type(definition) is not dict
        or type(actual_seed_reference) is not int
        or actual_seed_reference <= 0
        or seed.get("item_reference") != actual_seed_reference
        or seed.get("action_id") != request.get("action_id")
        or seed.get("resource_reference") != resource.get("resource_reference")
        or definition.get("resource_reference") != resource.get("resource_reference")
    ):
        raise ValueError("Validated seed/resource binding mismatch")
    if definition.get("monster_resource") is False:
        return _noop()
    if definition.get("monster_resource") is not True:
        raise ValueError("Invalid native resource classification")
    event = engine.event_payload(
        {
            "kind": "monster_seed_planted",
            "operation_id": operation_id,
            "seed_reference": actual_seed_reference,
            "resource_reference": resource["resource_reference"],
            "family_ids": definition.get("monster_family_ids"),
        }
    )
    # No guessed map exclusion: private garden policy matches successful placement.
    return service.settle(
        db, account_id, character_id, "planting:" + operation_id, event, definitions
    )
