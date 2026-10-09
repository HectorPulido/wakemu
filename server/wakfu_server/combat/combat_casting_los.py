"""Native QI.h visibility and fcr cast rays from owned QK authority."""
from .combat_conditions import UnknownCondition


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def native_qi_h(terrain, x, y, z, *, ordered_slots, visibility, ignored):
    """QI.h uses W/index bounds; z is unused and null QK returns false."""
    if any(type(v) is not int for v in (x, y, z)):
        raise ValueError("Invalid native QI.h coordinates")
    index = _i32(_i32(_i32(y - terrain.y) * terrain.width) + _i32(x - terrain.x))
    if not 0 <= index < len(terrain.masks):
        return True
    if terrain.masks[index] & 256:
        return True
    for slot in ordered_slots(x, y):
        blocks = visibility(slot)
        if blocks is None:
            return False  # An actual null biQ entry, not missing authority.
        if type(blocks) is not bool:
            raise UnknownCondition("Missing actual native QK.bcQ visibility")
        if blocks and slot not in ignored:
            return True
    return False


def native_actor_visibility(properties):
    """Actual eGj.bcQ against complete current ffe fight properties."""
    if not isinstance(properties, (frozenset, set)) or any(
        type(v) is not int for v in properties
    ):
        raise UnknownCondition("Missing complete native eGj visibility properties")
    return (
        18 not in properties
        and (6 in properties or 5 not in properties)
        and 54 not in properties
    )


def native_area_visibility(fight, identity):
    """Final faV.bcQ reads subtype fTq and current fbo.DONT_BLOCK_LOS."""
    from .combat_area_property import _target, area_properties
    from .combat_wall_area import verified_wall_constructor
    from .combat_fake_fighter import verified_fake_fighter

    row, definition = _target(fight, identity)
    if row is None:
        raise UnknownCondition("Missing actual registered area visibility target")
    if row["native_area_contract"] == "fbd":
        baseline = verified_wall_constructor(row, definition)["los_blocking"]
    elif row["native_area_contract"] == "faW":
        baseline = verified_fake_fighter(row, definition)["visibility_obstacle"]
    else:
        baseline = False  # Remaining verified faV subtypes inherit Qq.fTq=false.
    return baseline and 10 not in area_properties(row, definition)


def native_casting_ray(
    fight,
    actor_authority,
    map_id,
    source_cell,
    target_cell,
    *,
    source_height,
    target_height,
    ignored_slots,
    diagnostic=None,
):
    """Raw fcr coordinate overload: no implicit source QK exclusion/cleanup."""
    from .combat_qi_fight import current_registry
    from .combat_native_los_ray import cast_rays

    registry = current_registry(fight)
    if not isinstance(ignored_slots, (list, tuple, frozenset)) or any(
        type(v) is not int or not 0 <= v <= 126 for v in ignored_slots
    ):
        raise UnknownCondition("Missing complete native QI.biO visibility exclusions")
    ignored = frozenset(ignored_slots)
    snapshot = registry.snapshot()
    if diagnostic is not None:
        diagnostic.update(
            map_id=map_id,
            source_cell=list(source_cell),
            target_cell=list(target_cell),
            source_height=source_height,
            target_height=target_height,
            ignored_slots=sorted(ignored),
            rays=[],
        )
    evaluated_slots = []

    def visibility(slot):
        row = registry.slots[slot]
        if diagnostic is not None:
            evaluated_slots.append(
                dict(
                    slot=slot,
                    identity=None if row is None else list(row["identity"]),
                    position=None if row is None else list(row["position"]),
                    radius=None if row is None else row["radius"],
                )
            )
        if row is None:
            return None
        if row["identity"][0] == "effect_area":
            value = native_area_visibility(fight, row["identity"][1])
            if diagnostic is not None:
                evaluated_slots[-1]["blocks_los"] = value
            return value
        actor = fight.actors[row["identity"][1]]
        producer = getattr(actor_authority, "properties", None)
        if not callable(producer):
            raise UnknownCondition(
                "Missing current native actor visibility property producer"
            )
        value = native_actor_visibility(frozenset(producer(fight, actor)))
        if diagnostic is not None:
            evaluated_slots[-1]["blocks_los"] = value
        return value

    rays = cast_rays(
        map_id,
        tuple(source_cell),
        tuple(target_cell),
        source_height=source_height,
        target_height=target_height,
    )
    for clear, probes in rays:
        ray = dict(
            static_clear=clear,
            probes=[list(cell) for cell in sorted(probes)],
            blocked_probe=None,
            evaluated_slots=[],
        )
        if diagnostic is not None:
            diagnostic["rays"].append(ray)
        if not clear:
            continue
        blocked = False
        for x, y in probes:
            evaluated_slots.clear()
            blocked = native_qi_h(
                snapshot,
                x,
                y,
                0,
                ordered_slots=registry.ordered_U,
                visibility=visibility,
                ignored=ignored,
            )
            if blocked:
                ray["blocked_probe"] = [x, y]
                ray["evaluated_slots"] = list(evaluated_slots)
                index = _i32(
                    _i32(_i32(y - snapshot.y) * snapshot.width) + _i32(x - snapshot.x)
                )
                ray["terrain_mask"] = (
                    snapshot.masks[index] if 0 <= index < len(snapshot.masks) else None
                )
                break
        if not blocked:
            if diagnostic is not None:
                diagnostic["result"] = True
            return True
    if diagnostic is not None:
        diagnostic["result"] = False
    return False


def native_casting_los(
    fight, actor_authority, caster_id, target_cell, target_actor, *, diagnostic=None
):
    """Read-only amP fcr result; caller owns native bdM set cleanup."""
    from .combat_qi_fight import current_registry

    caster = fight.actors.get(caster_id)
    if caster is None:
        return False
    registry = current_registry(fight)
    metadata = actor_authority(fight, caster)
    ignored = getattr(fight, "native_qi_visibility_ignored_slots", None)
    if not isinstance(ignored, list):
        raise UnknownCondition("Missing complete native QI.biO visibility exclusions")
    slot = caster.native_obstacle_id
    if (
        type(slot) is not int
        or not 0 <= slot <= 126
        or registry.slots[slot] is None
        or registry.slots[slot]["identity"] != ["actor", caster.id]
    ):
        raise UnknownCondition("Unregistered native casting source QK")
    return native_casting_ray(
        fight,
        actor_authority,
        metadata.native_instance_id,
        caster.position,
        target_cell,
        source_height=caster.native_los_height,
        target_height=0 if target_actor is None else target_actor.native_los_height,
        ignored_slots=(*ignored, slot),
        diagnostic=diagnostic,
    )
