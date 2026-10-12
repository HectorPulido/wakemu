"""Advisory firing corridors from the exact native LOS probes, never XY rays."""
from ..native.native_control import effective_affiliation


def draft(fight, actor, action, map_id, *, rays=None, legacy=None, footprint=None):
    if rays is None or legacy is None or footprint is None:
        from wakfu_server.combat_native_los_ray import cast_rays
        from wakfu_server.combat_los import _resolve
        from wakfu_server.combat_obstacle_condition import footprint as native_footprint
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server import native_catalog

        rays = (
            cast_rays
            if native_catalog.exists(
                DATA_ROOT / "native-los-topology" / f"{map_id}.json"
            )
            else None
        )
        legacy = _resolve
        footprint = native_footprint
    source, target = tuple(actor.position), tuple(action["target"])
    targets = [
        a for a in fight.actors.values() if a.hp > 0 and tuple(a.position) == target
    ]
    if len(targets) > 1:
        raise ValueError("Ambiguous native corridor target")
    if not targets or effective_affiliation(fight, targets[0]) == effective_affiliation(
        fight, actor
    ):
        return None
    permitted = {tuple(cell[:2]) for cell in fight.walkable}
    ignored = getattr(fight, "native_los_ignored_affiliations", frozenset())
    if not isinstance(ignored, frozenset) or any(
        type(v) is not int or not -128 <= v <= 127 for v in ignored
    ):
        raise ValueError("Invalid native corridor ignored affiliations")
    blocked = set()
    for other in fight.actors.values():
        if other.hp > 0 and other.native_obstacle_id not in ignored:
            blocked.update(footprint(other.position, other.physical_radius))
    if rays is not None:
        alternatives = rays(
            map_id,
            source,
            target,
            source_height=actor.native_los_height,
            target_height=targets[0].native_los_height if targets else 0,
        )
    else:
        catalog, pair = legacy(map_id, source, target)
        alternatives = ((pair in catalog["visible"], catalog["probes"][pair]),)
    clear = [
        set(probes)
        for visible, probes in alternatives
        if visible and set(probes) <= permitted and not set(probes) & blocked
    ]
    if not clear:
        raise ValueError("No clear authoritative native firing corridor")
    # Preserve the first successful native ray, including its XY blocker
    # semantics. Every walkable Z at a probed XY is reserved; no interpolation.
    probes = clear[0]
    if not probes:
        return None
    return dict(
        ownerId=actor.id,
        team=effective_affiliation(fight, actor),
        source=list(source),
        target=list(target),
        targetId=targets[0].id,
        mapId=map_id,
        cells=[
            list(cell) for cell in sorted(fight.walkable) if tuple(cell[:2]) in probes
        ],
        basis="native_los_probes",
        spellId=action["spellId"],
        level=action["level"],
        ownerTurnCount=getattr(actor, "turn_count", None),
        probes=[list(cell) for cell in sorted(probes)],
    )


def valid(record, fight, team, *, footprint=None):
    if not isinstance(record, dict) or record.get("basis") != "native_los_probes":
        return False
    if (
        type(record.get("ownerId")) is not int
        or type(record.get("targetId")) is not int
        or type(record.get("team")) is not int
        or record["team"] != team
        or type(record.get("sourceRevision")) is not int
        or not 0 <= record["sourceRevision"] <= fight.sequence
    ):
        return False
    if any(
        not isinstance(record.get(name), (list, tuple))
        or len(record[name]) != 3
        or any(type(value) is not int for value in record[name])
        for name in ("source", "target")
    ):
        return False
    owner = fight.actors.get(record.get("ownerId"))
    if (
        owner is None
        or owner.hp <= 0
        or effective_affiliation(fight, owner) != team
        or tuple(owner.position) != tuple(record.get("source", ()))
        or getattr(owner, "turn_count", None) != record.get("ownerTurnCount")
        or type(record.get("expiresRound")) is not int
        or record["expiresRound"] < getattr(fight, "native_table_turn", 0)
    ):
        return False
    target_id = record.get("targetId")
    if target_id is not None:
        target = fight.actors.get(target_id)
        if (
            target is None
            or target.hp <= 0
            or effective_affiliation(fight, target) == team
            or tuple(target.position) != tuple(record.get("target", ()))
        ):
            return False
    cells, probes = record.get("cells"), record.get("probes")
    if (
        not isinstance(cells, list)
        or not isinstance(probes, list)
        or any(
            not isinstance(cell, (list, tuple))
            or len(cell) != 2
            or any(type(v) is not int for v in cell)
            for cell in probes
        )
        or any(
            not isinstance(cell, (list, tuple))
            or len(cell) != 3
            or any(type(v) is not int for v in cell)
            for cell in cells
        )
    ):
        return False
    probes = set(map(tuple, probes))
    if set(map(tuple, cells)) != {
        tuple(cell) for cell in fight.walkable if tuple(cell[:2]) in probes
    }:
        return False
    if footprint is None:
        from wakfu_server.combat_obstacle_condition import footprint
    ignored = getattr(fight, "native_los_ignored_affiliations", frozenset())
    if not isinstance(ignored, frozenset) or any(
        type(v) is not int or not -128 <= v <= 127 for v in ignored
    ):
        return False
    try:
        blocked = set()
        for actor in fight.actors.values():
            if actor.hp > 0 and actor.native_obstacle_id not in ignored:
                blocked.update(footprint(actor.position, actor.physical_radius))
        return not probes & blocked
    except (ValueError, AttributeError, TypeError):
        return False
