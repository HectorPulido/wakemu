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
    catalog, pair = _resolve(map_id, source, target)
    return pair in catalog["visible"]


def authoritative_visible(map_id, source, target, fight, *, blocking_footprints):
    """Native Sf probes + QI.h XY occupancy for explicit owned actor blockers.

    Every living actor needs a footprint; empty explicitly means nonblocking.
    Original endpoint handling is encoded in native probes, never guessed.
    """
    catalog, pair = _resolve(map_id, source, target)
    if pair not in catalog["visible"]:
        return False
    alive = {a.id for a in fight.actors.values() if a.hp > 0}
    if set(blocking_footprints) != alive:
        raise ValueError("LOS requires explicit footprints of every living actor")
    probes = catalog["probes"][pair]
    permitted = {(cell[0], cell[1]) for cell in fight.walkable}
    if not probes <= permitted:
        return False
    blocked = set()
    for cells in blocking_footprints.values():
        for cell in cells:
            if len(cell) != 2 or any(type(n) is not int for n in cell):
                raise ValueError("Invalid blocking footprint")
            blocked.add(tuple(cell))
    return not bool(probes & blocked)
