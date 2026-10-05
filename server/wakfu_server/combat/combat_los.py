"""Native Sf ray evidence by map; explicit dynamic actor blockers required."""
from .paths import DATA_ROOT
import gzip
import json
from functools import lru_cache


@lru_cache(maxsize=16)
def _load(map_id, adjacent):
    path = (
        DATA_ROOT / "combat-los" / f"{map_id}.json.gz"
        if adjacent
        else DATA_ROOT / "amakna-combat-los.json"
    )
    if not path.exists():
        return None
    opener = gzip.open if adjacent else open
    with opener(path, "rt") as stream:
        value = json.load(stream)
    if value["map_id"] != map_id:
        return None
    return dict(
        index={tuple(c): i for i, c in enumerate(value["cells"])},
        visible=set(map(tuple, value["visible_pairs"])),
        probes={
            (i, j): set(map(tuple, cells))
            for i, j, cells in value["dynamic_probe_cells"]
        },
        scope=value.get("scope", "all-exported-pairs"),
    )


def _resolve(map_id, source, target):
    source, target = tuple(source), tuple(target)
    # Preserve the previously validated full ray catalog for its known endpoints.
    candidates = ([_load(map_id, False)] if map_id == 1134 else []) + [
        _load(map_id, True)
    ]
    for catalog in candidates:
        if (
            catalog is None
            or source not in catalog["index"]
            or target not in catalog["index"]
        ):
            continue
        if (
            catalog["scope"] == "cardinal-adjacent-only"
            and abs(source[0] - target[0]) + abs(source[1] - target[1]) != 1
        ):
            continue  # No evidence for distant rays; never imply clear or blocked.
        return catalog, (catalog["index"][source], catalog["index"][target])
    raise ValueError("No native LOS evidence for these endpoints or distance")


def static_visible(map_id, source, target):
    if (DATA_ROOT / "native-los-topology" / f"{map_id}.json.gz").is_file():
        from .combat_native_los_ray import static_ray

        return static_ray(map_id, tuple(source), tuple(target))[0]
    catalog, pair = _resolve(map_id, source, target)
    return pair in catalog["visible"]


def authoritative_visible(map_id, source, target, fight, *, blocking_footprints):
    """Native Sf probes + QI.h XY occupancy for explicit owned actor blockers.

    Every living actor needs a footprint; empty explicitly means nonblocking.
    Original endpoint handling is encoded in native probes, never guessed.
    """
    alive = {a.id for a in fight.actors.values() if a.hp > 0}
    if set(blocking_footprints) != alive:
        raise ValueError("LOS requires explicit footprints of every living actor")
    permitted = {(cell[0], cell[1]) for cell in fight.walkable}
    blocked = set()
    ignored = getattr(fight, "native_los_ignored_affiliations", frozenset())
    if not isinstance(ignored, frozenset) or any(
        type(v) is not int or not -128 <= v <= 127 for v in ignored
    ):
        raise ValueError("Invalid native QI ignored affiliations")
    for identity, cells in blocking_footprints.items():
        if fight.actors[identity].native_obstacle_id in ignored:
            continue
        for cell in cells:
            if len(cell) != 2 or any(type(n) is not int for n in cell):
                raise ValueError("Invalid blocking footprint")
            blocked.add(tuple(cell))
    if (DATA_ROOT / "native-los-topology" / f"{map_id}.json.gz").is_file():
        from .combat_native_los_ray import cast_rays

        sources = [
            actor
            for actor in fight.actors.values()
            if actor.hp > 0 and tuple(actor.position) == tuple(source)
        ]
        targets = [
            actor
            for actor in fight.actors.values()
            if actor.hp > 0 and tuple(actor.position) == tuple(target)
        ]
        if len(sources) != 1 or len(targets) > 1:
            raise ValueError(
                "Native cast LOS requires unique source/target actor context"
            )
        source_height = getattr(sources[0], "native_los_height", None)
        # fcr null target uses offset6; signed height0 also produces max(6,0).
        target_height = (
            0 if not targets else getattr(targets[0], "native_los_height", None)
        )
        rays = cast_rays(
            map_id,
            tuple(source),
            tuple(target),
            source_height=source_height,
            target_height=target_height,
        )
        return any(
            visible and probes <= permitted and not probes & blocked
            for visible, probes in rays
        )
    # Preserve existing exported ray evidence on maps whose complete Vz
    # columns have not been exported; missing pairs continue to fail closed.
    catalog, pair = _resolve(map_id, source, target)
    if pair not in catalog["visible"]:
        return False
    probes = catalog["probes"][pair]
    return probes <= permitted and not bool(probes & blocked)
