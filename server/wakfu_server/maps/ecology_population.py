"""Region-local population snapshots from durable server entities.

Unknown native surfaces remain explicit: callers must not use an incomplete
snapshot to grant ecological rewards or certify equilibrium.
"""
from collections import Counter
from .planting_cells import surface
from .planting import RESOURCES
from .monsters import reference
from .resource_domains import is_mineral


def snapshot(db, map_id, instance_id, *, locate=surface, kinds=("plant", "monster")):
    if type(map_id) is not int or not 0 < map_id < 2**31:
        raise ValueError("Invalid ecology map")
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid ecology instance")
    if (
        type(kinds) is not tuple
        or not kinds
        or len(set(kinds)) != len(kinds)
        or any(kind not in ("plant", "monster") for kind in kinds)
    ):
        raise ValueError("Invalid ecology population kinds")
    regions, unresolved = {}, []

    def add(kind, identity, family, position):
        try:
            region_id = locate(map_id, *position)["region_id"]
        except ValueError:
            unresolved.append((kind, identity))
            return
        if type(region_id) is not int or region_id <= 0:
            unresolved.append((kind, identity))
            return
        counts = regions.setdefault(
            region_id, {"plant": Counter(), "monster": Counter()}
        )
        counts[kind][family] += 1

    plants = (
        db.execute(
            "SELECT resource_uid,resource_reference,x,y,z FROM planted_resources "
            "WHERE map_id=%s AND instance_id=%s AND stage NOT IN (0,16)",
            (map_id, instance_id),
        )
        if "plant" in kinds
        else ()
    )
    for row in plants:
        definition = RESOURCES[row["resource_reference"]]
        # A planted monster seed is not yet a living monster.
        if not definition["monster_resource"] and not is_mineral(
            row["resource_reference"]
        ):
            add(
                "plant",
                row["resource_uid"],
                definition["family_id"],
                tuple(row[key] for key in ("x", "y", "z")),
            )
    groups = (
        db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND status!='defeated'",
            (map_id, instance_id),
        )
        if "monster" in kinds
        else ()
    )
    for group in groups:
        for member in group["members"]:
            add(
                "monster",
                member["id"],
                reference(member["ref"])["family_id"],
                tuple(member[key] for key in ("x", "y", "z")),
            )
    return {"regions": regions, "unresolved": unresolved, "complete": not unresolved}
