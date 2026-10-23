"""Native faP bootstrap PV and its QI.P shape, independent of fighter owners."""

POLICY = "wakemu.compact-cardinal-perimeter-v1"
RECONSTRUCTED_POLICY = "wakemu.reconstructed-native-cardinal-perimeter-v1"
DECLARED_COMPONENT_POLICY = "wakemu.reconstructed-native-component-perimeter-v1"
SUPPORTED_POLICIES = frozenset(
    (POLICY, RECONSTRUCTED_POLICY, DECLARED_COMPONENT_POLICY)
)
SOURCE = "buS.cvb.fbm_null_owner.faP_h.Qs_a"


def validate_border_component(cells, edges, scope):
    """Require a whole native terrain component, preserving isolated platforms."""
    cells = set(cells)
    scope = frozenset(tuple(cell) for cell in scope)
    if not scope or not scope <= cells:
        raise ValueError("Declared border scope leaves native terrain")
    adjacency = {}
    for start, end in edges:
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)
    connected = set()
    pending = [min(scope)]
    while pending:
        cell = pending.pop()
        if cell not in connected:
            connected.add(cell)
            pending.extend(adjacency.get(cell, set()) - connected)
    if connected != scope:
        raise ValueError("Declared border scope is not a complete native component")
    return scope


def verify_battleground_border(fight, row):
    from .combat_qi_snapshot import NativeQISnapshot

    if (
        row.get("native_border_source") != SOURCE
        or row.get("native_border_policy") not in SUPPORTED_POLICIES
        or row.get("owner_id") is not None
        or row.get("level") != 0
        or row.get("direction") != -1
        or row.get("native_geometry_reference_source") != "faP.h.fbg.QI_P"
    ):
        raise ValueError("Missing native faP bootstrap provenance")
    qi = NativeQISnapshot(fight.native_qi_snapshot)
    actual = {
        (x, y)
        for y in range(qi.y, qi.y + qi.height)
        for x in range(qi.x, qi.x + qi.width)
        if qi.P(x, y)
    }
    cells = row.get("native_cells_xy")
    if (
        not isinstance(cells, (tuple, list))
        or any(
            not isinstance(cell, (tuple, list))
            or len(cell) != 2
            or any(type(v) is not int for v in cell)
            for cell in cells
        )
        or {tuple(cell) for cell in cells} != actual
    ):
        raise ValueError("Registered faP shape disagrees with native QI.P")


def ensure_battleground_border(fight):
    source = getattr(fight, "native_border_constructor", None)
    if source is None:
        return
    if not isinstance(source, dict) or set(source) != {
        "reference",
        "identity",
        "arena",
    }:
        raise ValueError("Missing battleground bootstrap constructor")
    existing = fight.native_effect_areas.get(source["identity"])
    if existing is None and getattr(fight, "native_border_installed", False):
        if source["identity"] in getattr(fight, "native_retired_area_managers", {}):
            return  # Actual Qs removal must not recreate the bootstrap object.
        raise ValueError("Missing previously registered battleground PV")
    if existing is not None:
        if (
            existing.get("native_border_source") != SOURCE
            or existing.get("reference") != source["reference"]
            or existing.get("native_border_policy")
            != source["arena"].get("native_border_policy")
        ):
            raise ValueError("Battleground constructor identity collision")
        verify_battleground_border(fight, existing)
        return
    install_battleground_border(
        fight,
        source["arena"],
        reference=source["reference"],
        identity=source["identity"],
    )


def install_battleground_border(fight, arena, *, reference, identity):
    """Mirror the faP clone constructed by buS from cvb.myo/myp.

    Perimeter selection is Wakemu policy. Prototype, null owner, level zero,
    direction NONE and shape membership follow the original client constructor.
    """
    if arena.get("native_border_policy") is None:
        return None
    if arena.get("native_border_policy") not in SUPPORTED_POLICIES:
        raise ValueError("Unknown battleground perimeter policy")
    from .combat_effect_area import native_effect_areas
    from .combat_qi_snapshot import NativeQISnapshot

    definition = native_effect_areas().get(str(reference))
    if (
        not isinstance(definition, dict)
        or definition.get("type") != "BATTLEGROUND_BORDER"
        or definition.get("native_class") != "bcF"
        or definition.get("raw_bdh") != []
    ):
        raise ValueError("Missing native nonblocking faP constructor")
    if type(identity) is not int or identity in fight.actors:
        raise ValueError("Battleground PV identity collides with fighter")
    supplied = arena.get("native_border_cells")
    if not isinstance(supplied, (set, frozenset, list, tuple)):
        raise ValueError("Missing selected battleground perimeter")
    cells = frozenset(tuple(cell) for cell in supplied)
    if any(len(cell) != 3 or any(type(v) is not int for v in cell) for cell in cells):
        raise ValueError("Invalid battleground perimeter coordinates")
    if arena["native_border_policy"] == RECONSTRUCTED_POLICY:
        from .combat_arena_selection import cardinal_border_cells

        if cells != cardinal_border_cells(fight.walkable):
            raise ValueError(
                "Reconstructed border differs from native room cardinal perimeter"
            )
    if arena["native_border_policy"] == DECLARED_COMPONENT_POLICY:
        from .combat_arena_selection import cardinal_border_cells

        scope = validate_border_component(
            fight.walkable,
            fight.edges,
            arena.get("native_border_scope_cells", ()),
        )
        if cells != cardinal_border_cells(scope):
            raise ValueError("Declared border differs from native component perimeter")
    qi = NativeQISnapshot(fight.native_qi_snapshot)
    actual = {
        (x, y)
        for y in range(qi.y, qi.y + qi.height)
        for x in range(qi.x, qi.x + qi.width)
        if qi.P(x, y)
    }
    if actual != {cell[:2] for cell in cells} or not cells <= fight.walkable:
        raise ValueError("Battleground perimeter disagrees with native QI.P")
    areas = fight.native_effect_areas
    if identity in areas:
        raise ValueError("Battleground border already registered")
    row = dict(
        uid=identity,
        reference=reference,
        level=0,
        cell=(qi.x, qi.y, arena["min_z"]),
        owner_id=None,
        direction=-1,
        keep_after=False,
        native_hour_contract=False,
        native_area_contract="faP",
        native_qq_bhi=False,
        native_qq_guard_source="Qq.constructor",
        native_obstacle_id=-1,
        native_obstacle_source="fbm.constructor",
        native_type_id=definition["native_type_id"],
        native_removal_masks=(),
        native_cells_xy=tuple(sorted(actual)),
        native_geometry_reference=None,
        native_geometry_reference_source="faP.h.fbg.QI_P",
        remaining_activations=definition["raw_bde"],
        native_running_effect_manager=False,
        child_effect_uids={},
        executing=False,
        native_fight_affiliation=-1,
        native_fight_affiliation_source="faV.constructor.null_owner",
        native_border_source=SOURCE,
        native_border_policy=arena["native_border_policy"],
    )
    areas[identity] = row
    from .combat_global_pv_collections import register_global_area

    register_global_area(fight, identity)
    fight.native_border_cells = tuple(sorted(cells))
    fight.native_border_policy = arena["native_border_policy"]
    fight.native_border_installed = True
    return row
