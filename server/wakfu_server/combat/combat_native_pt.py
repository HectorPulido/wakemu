"""Original eVE.a PT exclusion: amQ selection followed by QI.R/QI.V."""
from functools import lru_cache

from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def _preflight_catalog():
    data = protocol_catalog.load(DATA_ROOT / "native-pt-preflight.json")
    if (
        len(data["null_exclusion_references"]) + len(data["nonnull_exclusions"])
        != data["definitions_checked"]
    ):
        raise ValueError("Incomplete native PT preflight export")
    return dict(
        data, null_exclusion_references=frozenset(data["null_exclusion_references"])
    )


def null_exclusion_references():
    return _preflight_catalog()["null_exclusion_references"]


null_exclusion_references.cache_clear = _preflight_catalog.cache_clear


def exclusion_metadata(reference):
    """Read original fKX/aZF independently of the effect's application area."""
    from .combat_casting_context import casting_root_catalog

    kind = _preflight_catalog()["nonnull_exclusions"].get(str(reference))
    if kind is None:
        raise ValueError("Unknown native PT exclusion identity")
    row = casting_root_catalog()["roots"].get(str(reference))
    if not isinstance(row, dict):
        raise ValueError("Missing original native PT exclusion geometry")
    shape, selector = row.get("native_casting_collision_area"), row.get(
        "native_target_selector"
    )
    if (
        not isinstance(shape, dict)
        or shape.get("area_class") != kind
        or type(row.get("native_selector_present")) is not bool
        or row["native_selector_present"] != (selector is not None)
    ):
        raise ValueError("Conflicting original native PT exclusion geometry")
    return shape, selector


def native_pt_preflight(
    effect, invocation, *, fight=None, candidates=None, native_context=None
):
    if invocation.reference in null_exclusion_references():
        # eVE.a returns immediately: no PV/QI/selector lookup on this branch.
        return True
    shape, selector = exclusion_metadata(invocation.reference)
    if fight is None or not callable(candidates) or not callable(native_context):
        raise ValueError("Native PT exclusion requires its actual fight population")
    from .combat_effect_area_targets import (
        NativeAreaTarget,
        retained_area_source_target,
    )
    from .combat_native_actor_lookup import native_actor
    from .combat_effect_targets import (
        native_selector_policy,
        select_effect_targets,
        _native_target_valid,
        area_offsets,
        target_relation,
    )
    from .combat_area_geometry import native_area_shape, oriented_area_offsets
    from .combat_free_cell_condition import int32

    source = native_actor(fight, invocation.caster_id)
    if source is None:
        source = retained_area_source_target(fight, invocation.caster_id)
    if source is None:
        raise ValueError("Missing actual native PT source PV")
    cell = invocation.cell
    if (
        not isinstance(cell, (tuple, list))
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
        or any(not -(1 << 31) <= value < (1 << 31) for value in cell[:2])
        or not -32768 <= cell[2] <= 32767
    ):
        raise ValueError("Invalid native PT target cell")
    candidate = dict(effect, **shape, native_target_selector=selector)
    policy = native_selector_policy(candidate)
    population = tuple(candidates())
    if policy["in_area"]:
        population = select_effect_targets(
            candidate,
            source,
            source.position if selector is None else cell,
            population,
            relations=policy["relations"],
            orientation=cell if selector is None else source.position,
            native_radius=selector is not None,
            available=lambda actor: True,
        )
    else:
        population = tuple(
            target
            for target in population
            if target_relation(source, target) in policy["relations"]
        )
    contexts = None if selector is None else native_context()
    for target in population:
        if selector is not None and not _native_target_valid(
            selector["mask"], source, target, contexts, include_fah=False
        ):
            continue
        # eVE skips faV only when its actual bcP is false. Qq wrappers retain
        # this constructor value; ordinary eGj/non-faV PVs never get skipped.
        if isinstance(target, NativeAreaTarget):
            if type(target.native_movement_blocking) is not bool:
                raise ValueError("Missing native PT faV.bcP authority")
            if not target.native_movement_blocking:
                continue
        return False

    from .combat_qi_fight import current_registry
    from .combat_pointer_qi_registry import registered_terrain, registered_slot

    registry = current_registry(fight)
    terrain = registered_terrain(registry)
    offsets = (
        area_offsets(candidate)
        if native_area_shape(candidate) is None
        else oriented_area_offsets(
            candidate,
            origin=cell,
            reference=source.position,
            direction=source.direction,
        )
    )
    for dx, dy in offsets:
        x, y = int32(cell[0] + dx), int32(cell[1] + dy)
        if not terrain.R(x, y):
            return False
        order = registry.ordered_U(x, y)
        if order and registered_slot(registry, order[0]) is not None:
            return False
    return True
