"""Immutable contribution facts from authenticated gameplay settlement.

An entity reference is not event membership. The lifecycle must join the exact
world entity identity to its frozen event roster before awarding contribution.
These builders run inside the existing gameplay transaction after its durable
receipt has been written; they do not accept network completion as authority.
"""
from dataclasses import dataclass
from . import environmental_presence as presence


def _integer(value, field, *, minimum=1, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid environmental " + field)
    return value


def _receipt(value):
    if type(value) is not str or not 1 <= len(value) <= 160:
        raise ValueError("Invalid environmental receipt")
    return value


@dataclass(frozen=True)
class GameplayFact:
    kind: str
    receipt_key: str
    account_id: int
    character_id: int
    map_id: int
    instance_id: int
    entity_kind: str
    entity_id: int
    reference: int
    occurred_at_ms: int
    region_id: int | None = None
    quantity: int = 1
    interaction_count: int = 1
    action_id: int | None = None
    before_step: int | None = None
    after_step: int | None = None
    fight_id: int | None = None

    def __post_init__(self):
        if self.kind not in (
            "monster_defeated",
            "group_defeated",
            "resource_collected",
            "resource_planted",
            "monster_collected",
            "monster_destroyed",
        ):
            raise ValueError("Unsupported environmental gameplay fact")
        expected = (
            "group"
            if self.kind == "group_defeated"
            else "resource"
            if self.kind.startswith("resource_")
            else "monster"
        )
        if self.entity_kind != expected:
            raise ValueError("Environmental entity family mismatch")
        _receipt(self.receipt_key)
        for field in ("account_id", "character_id", "map_id", "reference"):
            _integer(getattr(self, field), field)
        _integer(self.instance_id, "instance", minimum=0)
        _integer(self.occurred_at_ms, "occurrence timestamp", minimum=0)
        _integer(self.quantity, "quantity", minimum=0)
        if self.interaction_count != 1 or type(self.interaction_count) is not int:
            raise ValueError("A gameplay fact represents one committed interaction")
        if self.region_id is not None:
            _integer(self.region_id, "region")
        _integer(self.entity_id, "entity", minimum=-(2**63))
        if self.entity_id == 0:
            raise ValueError("Missing environmental entity")
        for field in ("action_id", "fight_id"):
            value = getattr(self, field)
            if value is not None:
                _integer(value, field)
        for field in ("before_step", "after_step"):
            value = getattr(self, field)
            if value is not None:
                _integer(value, field, minimum=0, maximum=2**31 - 1)
        victory = self.kind in ("monster_defeated", "group_defeated")
        if victory != (self.fight_id is not None):
            raise ValueError("Environmental victory requires its fight receipt")
        if not victory and self.action_id is None:
            raise ValueError("Environmental interaction requires its native action")


def fight_facts(
    *,
    account_id,
    character_id,
    map_id,
    instance_id,
    fight_id,
    receipt,
    occurred_at_ms,
    region_id=None
):
    """Project the original roster from an accredited winning-owner receipt.

    Caller obtains ``receipt`` from character_achievement_events for this owner,
    not from a client or the final dynamic actor population. Each original is
    one fact; group credit is derived by the lifecycle's frozen group membership.
    """
    _integer(fight_id, "fight")
    if (
        type(receipt) is not dict
        or type(receipt.get("fight_id")) is not int
        or receipt["fight_id"] != fight_id
    ):
        raise ValueError("Environmental fight receipt mismatch")
    roster = receipt.get("original_monsters")
    if type(roster) is not list:
        raise ValueError("Missing original environmental combat roster")
    result, seen = [], set()
    for monster in roster:
        if type(monster) is not list or len(monster) != 2:
            raise ValueError("Invalid original environmental monster")
        identity, reference = monster
        if type(identity) is not int or identity in seen:
            raise ValueError("Duplicate original environmental monster")
        seen.add(identity)
        result.append(
            GameplayFact(
                "monster_defeated",
                "fight:" + str(fight_id),
                account_id,
                character_id,
                map_id,
                instance_id,
                "monster",
                identity,
                reference,
                occurred_at_ms,
                region_id=region_id,
                fight_id=fight_id,
            )
        )
    return tuple(result)


def resource_fact(
    *,
    account_id,
    character_id,
    token,
    receipt,
    resource,
    occurred_at_ms,
    region_id=None
):
    """Freeze a completed flora action with its pre-action resource snapshot.

    Preserve product yield and interaction count separately. The lifecycle's
    declared objective unit decides which is counted, not an implicit bonus
    yield multiplier. Native stages/actions remain distinct from planting.
    """
    if type(receipt) is not dict or type(resource) is not dict:
        raise ValueError("Missing environmental resource receipt")
    for field, expected in (
        ("token", token),
        ("account_id", account_id),
        ("character_id", character_id),
        ("resource_uid", resource.get("resource_uid")),
    ):
        if type(receipt.get(field)) is not type(expected) or receipt[field] != expected:
            raise ValueError("Environmental resource receipt mismatch")
    outcome = receipt.get("result")
    if type(outcome) is not dict:
        raise ValueError("Missing environmental resource outcome")
    return GameplayFact(
        "resource_collected",
        "harvest:" + _receipt(token),
        account_id,
        character_id,
        resource["map_id"],
        resource.get("instance_id", 0),
        "resource",
        resource["resource_uid"],
        resource["resource_reference"],
        occurred_at_ms,
        region_id=region_id,
        quantity=outcome["quantity"],
        action_id=receipt["action_id"],
        before_step=resource["stage"],
        after_step=outcome["stage"],
    )


def planting_fact(
    *, account_id, character_id, operation_id, receipt, occurred_at_ms, region_id=None
):
    """Failed planting produces no contribution; successful receipts own UID."""
    if type(receipt) is not dict or receipt.get("operation_id") != operation_id:
        raise ValueError("Environmental planting receipt mismatch")
    if (
        type(receipt.get("character_id")) is not int
        or receipt["character_id"] != character_id
    ):
        raise ValueError("Foreign environmental planting receipt")
    if type(receipt.get("success")) is not bool:
        raise ValueError("Invalid environmental planting result")
    if not receipt["success"]:
        return None
    resource, request = receipt.get("resource"), receipt.get("request")
    if type(resource) is not dict or type(request) is not dict:
        raise ValueError("Missing successful environmental planting snapshot")
    return GameplayFact(
        "resource_planted",
        "planting:" + _receipt(operation_id),
        account_id,
        character_id,
        resource["map_id"],
        resource.get("instance_id", 0),
        "resource",
        resource["resource_uid"],
        resource["resource_reference"],
        occurred_at_ms,
        region_id=region_id,
        action_id=request["action_id"],
        after_step=resource["stage"],
    )


def monster_action_fact(
    *, account_id, character_id, token, receipt, monster, occurred_at_ms, region_id=None
):
    """Renewable collection and original DESTROY3 are separate committed facts.

    A destroy receipt must explicitly attest the destroyed result. A victorious
    fight receipt, corpse product extraction, or client request cannot supply it.
    """
    if type(receipt) is not dict or type(monster) is not dict:
        raise ValueError("Missing environmental monster action receipt")
    for field, expected in (
        ("token", token),
        ("character_id", character_id),
        ("monster_id", monster.get("id")),
        ("map_id", monster.get("map_id")),
        ("instance_id", monster.get("instance_id", 0)),
    ):
        if type(receipt.get(field)) is not type(expected) or receipt[field] != expected:
            raise ValueError("Environmental monster action receipt mismatch")
    action_kind = receipt.get("action_kind")
    if action_kind == "destroy":
        if (
            type(receipt.get("monster_action_type")) is not int
            or receipt["monster_action_type"] != 3
        ):
            raise ValueError("Monster DESTROY requires original native action3")
        if receipt.get("destroyed") is not True:
            raise ValueError("Monster DESTROY requires a committed destruction")
        kind = "monster_destroyed"
    elif action_kind == "collect":
        if receipt.get("destroyed") is not False or receipt.get("corpse") is not False:
            raise ValueError("Living monster collection requires its own receipt")
        kind = "monster_collected"
    else:
        raise ValueError("Unsupported environmental monster action family")
    return GameplayFact(
        kind,
        "monster-action:" + _receipt(token),
        account_id,
        character_id,
        monster["map_id"],
        monster.get("instance_id", 0),
        "monster",
        monster["id"],
        monster["ref"],
        occurred_at_ms,
        region_id=region_id,
        quantity=receipt["quantity"],
        action_id=receipt["action_id"],
    )


def consume(db, facts):
    """Contribute in the caller's gameplay transaction, without committing it."""
    from . import environmental_storage

    facts = tuple(facts)
    if any(type(fact) is not GameplayFact for fact in facts):
        raise ValueError("Environmental contribution requires authenticated facts")
    changes, pending = [], {}
    # Freeze every entity in a settled victory before its first objective can
    # complete a participant or close a limited-slot event.
    for fact in facts:
        if fact.kind in ("monster_defeated", "group_defeated", "monster_destroyed"):
            environmental_storage.contribute(db, fact, record_entities_only=True)
    for fact in facts:
        deltas = environmental_storage.contribute(db, fact, shared_completions=pending)
        changes.extend(deltas)
    for instance_id, now_ms in pending.items():
        environmental_storage.finish_shared(db, instance_id, now_ms=now_ms)
    return tuple(changes)


def _milliseconds(timestamp):
    from datetime import datetime, timezone

    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("Missing authoritative gameplay completion timestamp")
    delta = timestamp.astimezone(timezone.utc) - datetime(
        1970, 1, 1, tzinfo=timezone.utc
    )
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def _native_region(map_id, entity):
    """Resolve the original world XY, never the current selected position."""
    from wakfu_server.territory_cells import region_at

    if any(type(entity.get(key)) is not int for key in ("x", "y")):
        return None
    try:
        region = region_at(map_id, entity["x"], entity["y"])
    except ValueError:
        return None
    return region if type(region) is int and region > 0 else None


def admission_origin(character):
    """Freeze authenticated world coordinates before combat placement moves actors."""
    keys = ("map_id", "instance_id", "x", "y", "z")
    if any(type(character.get(key)) is not int for key in keys):
        raise ValueError("Missing original environmental admission coordinates")
    origin = {key: character[key] for key in keys}
    origin["region_id"] = _native_region(origin["map_id"], origin)
    return origin


def remember_admission(shared, account_id, character):
    """Capture a genuine newly joined owner's origin, never overwrite on retry."""
    origin = admission_origin(character)
    if (origin["map_id"], origin["instance_id"]) != (shared.map_id, shared.instance_id):
        raise ValueError("Environmental admission leaves the original fight scene")
    with shared.lock:
        context = dict(shared.join_context or {})
        origins = dict(context.get("environmental_admission_origins", {}))
        origins.setdefault(account_id, origin)
        context["environmental_admission_origins"] = origins
        shared.join_context = context


def scene_from_admission(shared):
    """Build settlement authority from frozen admission, including legacy fights.

    The old native fight marker is trusted only for the original team leader's
    matching owner. It never supplies the current location of a travelling
    player, or the admission of a different account joining that fight.
    """
    context = shared.join_context or {}
    origins = context.get("environmental_admission_origins", {})
    if type(origins) is not dict:
        raise ValueError("Invalid environmental admission origins")
    regions = {}
    for owner, origin in origins.items():
        if (
            type(owner) is not int
            or owner <= 0
            or type(origin) is not dict
            or (origin.get("map_id"), origin.get("instance_id"))
            != (shared.map_id, shared.instance_id)
        ):
            raise ValueError("Environmental admission origin changed its scene")
        region = origin.get("region_id")
        if region is not None and (type(region) is not int or region <= 0):
            raise ValueError("Invalid original environmental admission region")
        regions[owner] = region
    marker = context.get("world_marker_origin")
    leaders = context.get("leaders", {})
    if (
        isinstance(marker, (tuple, list))
        and len(marker) == 3
        and all(type(value) is int for value in marker)
        and isinstance(leaders, dict)
    ):
        region = _native_region(shared.map_id, dict(zip(("x", "y", "z"), marker)))
        for owner, session in shared.participants.items():
            if session.character_id in leaders.values():
                regions.setdefault(owner, region)
    return dict(
        map_id=shared.map_id,
        instance_id=shared.instance_id,
        group_lease=shared.group_lease,
        admission_regions=regions,
    )


def settled_fight(
    db, *, account_id, character_id, fight_id, source_scene, deferred_facts=None
):
    """Consume the owned durable winning receipt in its existing transaction.

    ``source_scene`` is frozen at fight admission. Never substitute the selected
    character's current location after a dungeon exit or reconnect. Storage
    additionally matches the event's persisted exact entity/scene membership.
    """
    if type(source_scene) is not dict:
        raise ValueError("Missing admitted environmental fight scene")
    if presence.capture(source_scene["map_id"], source_scene["instance_id"]) is None:
        return ()
    row = db.execute(
        "SELECT e.payload,e.created_at FROM character_achievement_events e "
        "JOIN characters c ON c.id=e.character_id "
        "WHERE e.character_id=%s AND e.event_key=%s AND c.account_id=%s "
        "AND c.deleted_at IS NULL",
        (character_id, "fight:" + str(_integer(fight_id, "fight")), account_id),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned accredited environmental fight receipt")
    facts = fight_facts(
        account_id=account_id,
        character_id=character_id,
        map_id=source_scene["map_id"],
        instance_id=source_scene["instance_id"],
        region_id=source_scene.get("region_id"),
        fight_id=fight_id,
        receipt=row["payload"],
        occurred_at_ms=_milliseconds(row["created_at"]),
    )
    original = source_scene.get("original_entities")
    if original is not None:
        from dataclasses import replace

        indexed = {entity["id"]: entity for entity in original}
        if len(indexed) != len(original):
            raise ValueError("Duplicate environmental original scene entity")
        located = []
        for fact in facts:
            entity = indexed.get(fact.entity_id)
            if entity is None or entity["ref"] != fact.reference:
                raise ValueError(
                    "Environmental victory differs from its original scene roster"
                )
            located.append(
                replace(fact, region_id=_native_region(source_scene["map_id"], entity))
            )
        facts = tuple(located)
    from .environmental_groups import winning_facts

    facts += winning_facts(
        db,
        receipt=row["payload"],
        source_scene=source_scene,
        account_id=account_id,
        character_id=character_id,
        occurred_at_ms=_milliseconds(row["created_at"]),
    )
    # Entity ownership cannot enroll a travelling participant into another
    # region's event. Admission froze the actor's original native region;
    # selection changes after combat must neither revoke nor invent credit.
    facts = tuple(
        fact for fact in facts if fact.region_id == source_scene.get("region_id")
    )
    if deferred_facts is not None:
        if type(deferred_facts) is not list:
            raise ValueError("Environmental settlement batch requires a fact list")
        deferred_facts.extend(facts)
        return ()
    return consume(db, facts)


def committed_resource(
    db, *, account_id, character_id, token, resource, region_id=None
):
    """Called after resource_harvest_receipts insertion with its frozen snapshot."""
    if presence.capture(resource["map_id"], resource.get("instance_id", 0)) is None:
        return ()
    row = db.execute(
        "SELECT * FROM resource_harvest_receipts WHERE token=%s "
        "AND account_id=%s AND character_id=%s",
        (_receipt(token), account_id, character_id),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned environmental resource completion")
    if region_id is None:
        region_id = _native_region(resource["map_id"], resource)
    from .environmental_company import project_interaction

    return consume(
        db,
        project_interaction(
            db,
            resource_fact(
                account_id=account_id,
                character_id=character_id,
                token=token,
                receipt=dict(row),
                resource=resource,
                region_id=region_id,
                occurred_at_ms=_milliseconds(row["completed_at"]),
            ),
        ),
    )


def committed_planting(
    db, *, account_id, character_id, operation_id, region_id=None, source_scene=None
):
    """Planting's character-only receipt must be joined to its actual owner."""
    if (
        source_scene is not None
        and presence.capture(source_scene["map_id"], source_scene["instance_id"])
        is None
    ):
        return ()
    row = db.execute(
        "SELECT p.* FROM planting_receipts p JOIN characters c ON c.id=p.character_id "
        "WHERE p.operation_id=%s AND p.character_id=%s AND c.account_id=%s "
        "AND c.deleted_at IS NULL",
        (_receipt(operation_id), character_id, account_id),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned environmental planting completion")
    if row["success"] is False:
        return ()
    resource = row["resource"]
    if type(resource) is not dict:
        raise ValueError("Missing committed environmental planted resource")
    if region_id is None:
        region_id = _native_region(resource["map_id"], resource)
    fact = planting_fact(
        account_id=account_id,
        character_id=character_id,
        operation_id=operation_id,
        receipt=dict(row),
        region_id=region_id,
        occurred_at_ms=resource["creation_time"],
    )
    from .environmental_bindings import committed_planting as bind_planting

    from .environmental_company import project_interaction

    facts = project_interaction(db, fact)
    for member_fact in facts:
        bind_planting(db, member_fact)
    return consume(db, facts)


def committed_monster_destroy(db, receipt):
    """Project a committed native removal to its eligible loaded company."""
    from .environmental_company import project_interaction
    from .environmental_storage import _transaction

    _transaction(db)
    if type(receipt) is not dict or type(receipt.get("replayed")) is not bool:
        raise ValueError("Missing committed native destruction receipt")
    if receipt["replayed"]:
        return ()
    monster = receipt.get("monster")
    if type(monster) is not dict:
        raise ValueError("Native destruction requires its frozen pre-action target")
    fact = monster_action_fact(
        account_id=receipt["account_id"],
        character_id=receipt["character_id"],
        token=receipt["token"],
        receipt=receipt,
        monster=monster,
        occurred_at_ms=receipt["occurred_at_ms"],
        region_id=_native_region(monster["map_id"], monster),
    )
    return consume(db, project_interaction(db, fact))
