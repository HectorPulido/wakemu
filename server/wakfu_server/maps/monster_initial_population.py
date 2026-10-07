"""One-time, transactional world seeding; never called on player entry.

Plans are explicit region-verified positions, not native spawn-definition IDs
misinterpreted as coordinates. Defeating/deleting a group preserves its marker.
"""
import json
from psycopg.types.json import Jsonb
from .paths import DATA_ROOT
from .planting_cells import surface
from .monsters import owned_instance, reference
from .ecology_population import snapshot

REGIONS = {
    (world["map_id"], region["region_id"]): region
    for world in json.loads((DATA_ROOT / "ecology-regions.json").read_text())
    for region in world["regions"]
}


def seed_zone(store, groups, map_id, instance_id, region_id, plan, *, locate=surface):
    """Caller supplies geometry-vetted startup plan; no network publication."""
    for value, maximum in ((map_id, 2**31), (region_id, 2**31)):
        if type(value) is not int or not 0 < value < maximum:
            raise ValueError("Invalid initial monster region")
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid initial monster instance")
    region = REGIONS.get((map_id, region_id))
    if region is None or region.get("monster_capacity", 0) <= 0:
        raise ValueError("No native monster habitat for initial population")
    allowed = {row["family_id"] for row in region["monster_families"]}
    if not isinstance(plan, (list, tuple)) or not plan:
        raise ValueError("Missing initial monster plan")
    positions, families = set(), set()
    for row in plan:
        if not isinstance(row, dict) or set(row) != {
            "reference",
            "level",
            "x",
            "y",
            "z",
        }:
            raise ValueError("Invalid initial monster plan entry")
        # Validate types, native level range and living statistics before any
        # SQL mutation or sequence allocation (bool is not a coordinate).
        owned_instance(
            row["reference"],
            row["level"],
            -1,
            map_id=map_id,
            instance_id=instance_id,
            **{key: row[key] for key in ("x", "y", "z")},
        )
        family = reference(row["reference"])["family_id"]
        position = tuple(row[key] for key in ("x", "y", "z"))
        if family not in allowed or locate(map_id, *position)["region_id"] != region_id:
            raise ValueError("Initial monster is outside its native habitat")
        if position in positions:
            raise ValueError("Initial monsters cannot share a cell")
        positions.add(position)
        families.add(family)
    if len(families) != 1:
        raise ValueError("Initial group must contain one native family")
    with groups.lock, store.connection() as db, db.transaction():
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"monster-population:{map_id}:{instance_id}",),
        )
        prior = db.execute(
            "SELECT * FROM monster_initial_population WHERE map_id=%s "
            "AND instance_id=%s AND region_id=%s",
            (map_id, instance_id, region_id),
        ).fetchone()
        if prior is not None:
            return {"duplicate": True, "marker": dict(prior)}
        row = db.execute(
            "SELECT value FROM settings WHERE name='monster_initial_population'"
        ).fetchone()
        policy = row["value"] if row else None
        if (
            type(policy) is not dict
            or type(policy.get("version")) is not int
            or policy["version"] <= 0
            or type(policy.get("enabled")) is not bool
            or type(policy.get("members_per_zone")) is not int
            or not 1 <= policy["members_per_zone"] <= 8
        ):
            raise ValueError("Invalid initial monster population policy")
        if not policy["enabled"]:
            return {"disabled": True}
        if (
            len(plan) != policy["members_per_zone"]
            or len(plan) > region["monster_capacity"]
        ):
            raise ValueError("Initial monster plan violates population policy")
        population = snapshot(
            db, map_id, instance_id, locate=locate, kinds=("monster",)
        )
        if not population["complete"]:
            raise ValueError("Initial monster population has unresolved native regions")
        current = sum(
            population["regions"].get(region_id, {}).get("monster", {}).values()
        )
        if current + len(plan) > region["monster_capacity"]:
            raise ValueError("Initial monster plan exceeds existing regional capacity")
        occupied = {
            tuple(member[key] for key in ("x", "y", "z"))
            for group in db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND status!='defeated'",
                (map_id, instance_id),
            )
            for member in group["members"]
        }
        if positions & occupied:
            raise ValueError("Initial monster cells are occupied")
        vegetation = {
            tuple(resource[key] for key in ("x", "y", "z"))
            for resource in db.execute(
                "SELECT x,y,z FROM planted_resources WHERE map_id=%s AND instance_id=%s",
                (map_id, instance_id),
            )
        }
        if positions & vegetation:
            raise ValueError("Initial monster cells contain planted resources")
        identities = [
            db.execute("SELECT nextval('monster_entity_uid') AS id").fetchone()["id"]
            for _ in plan
        ]
        members = [
            owned_instance(
                row["reference"],
                row["level"],
                -identity,
                map_id=map_id,
                instance_id=instance_id,
                **{key: row[key] for key in ("x", "y", "z")},
            )
            for row, identity in zip(plan, identities)
        ]
        key = groups.register_transaction(
            db, map_id, instance_id, identities[0], members
        )
        db.execute(
            "INSERT INTO monster_initial_population VALUES(%s,%s,%s,%s,%s,%s)",
            (map_id, instance_id, region_id, policy["version"], key[2], Jsonb(members)),
        )
        return {"duplicate": False, "key": key, "members": members}


def configured_plans(path=None, *, completed_habitats=()):
    """Load explicit pilot habitats and validate native walking geometry."""
    from .combat_terrain import map_geometry

    data = json.loads(
        (path or DATA_ROOT / "initial-monster-population.json").read_text()
    )
    if (
        type(data) is not dict
        or set(data) != {"version", "scope", "plans"}
        or type(data["version"]) is not int
        or data["version"] != 1
        or type(data["scope"]) is not str
        or type(data["plans"]) is not list
    ):
        raise ValueError("Invalid initial monster habitat catalog")
    plans, seen, indices = [], set(), {}
    for row in data["plans"]:
        if type(row) is not dict or set(row) != {
            "map_id",
            "instance_id",
            "region_id",
            "members",
        }:
            raise ValueError("Invalid configured initial monster habitat")
        key = tuple(row[k] for k in ("map_id", "instance_id", "region_id"))
        if (
            any(type(v) is not int for v in key)
            or not 0 < key[0] < 2**31
            or key[1] != 0
            or not 0 < key[2] < 2**31
            or key in seen
        ):
            raise ValueError("Invalid or repeated initial monster habitat identity")
        members = row["members"]
        if type(members) is not list or len(members) != 2:
            raise ValueError("Initial pilot requires two adjacent monsters")
        # Durable markers forbid reseeding even after all members disappear.
        # Validate catalog shape and member types, but avoid rebuilding terrain
        # for a habitat that will perform no population mutation.
        for member in members:
            if type(member) is not dict or set(member) != {
                "reference",
                "level",
                "x",
                "y",
                "z",
            }:
                raise ValueError("Invalid configured initial monster")
            owned_instance(
                member["reference"],
                member["level"],
                -1,
                map_id=key[0],
                instance_id=key[1],
                **{k: member[k] for k in ("x", "y", "z")},
            )
        if key in completed_habitats:
            seen.add(key)
            plans.append(row)
            continue
        if row["map_id"] not in indices:
            geometry = map_geometry(row["map_id"])
            indices[row["map_id"]] = (
                {tuple(cell) for cell in geometry["cells"]},
                {(tuple(a), tuple(b)) for a, b in geometry["edges"]},
            )
        walkable, edges = indices[row["map_id"]]
        points = []
        for member in members:
            if type(member) is not dict or set(member) != {
                "reference",
                "level",
                "x",
                "y",
                "z",
            }:
                raise ValueError("Invalid configured initial monster")
            owned_instance(
                member["reference"],
                member["level"],
                -1,
                map_id=key[0],
                instance_id=key[1],
                **{k: member[k] for k in ("x", "y", "z")},
            )
            position = tuple(member[k] for k in ("x", "y", "z"))
            if (
                position not in walkable
                or surface(key[0], *position)["region_id"] != key[2]
            ):
                raise ValueError(
                    "Initial pilot cell is outside walkable native habitat"
                )
            points.append(position)
        if (points[0], points[1]) not in edges or (points[1], points[0]) not in edges:
            raise ValueError(
                "Initial pilot members lack a bidirectional native walking edge"
            )
        seen.add(key)
        plans.append(row)
    return tuple(plans)


def seed_configured(store, groups, *, report, plans=None):
    """Run before listeners; log unavailable cells without blocking world boot.

    A failed initial attempt keeps no marker. A successful marker is permanent,
    so subsequent boots never refill that region after a defeat.
    """
    with store.connection() as db:
        completed = {
            (row["map_id"], row["instance_id"], row["region_id"]): dict(row)
            for row in db.execute("SELECT * FROM monster_initial_population")
        }
    plans = configured_plans(completed_habitats=completed) if plans is None else plans
    outcomes = []
    for plan in plans:
        scope = {key: plan[key] for key in ("map_id", "instance_id", "region_id")}
        try:
            key = tuple(scope[k] for k in ("map_id", "instance_id", "region_id"))
            if key in completed:
                result = {"duplicate": True, "marker": completed[key]}
            else:
                result = seed_zone(store, groups, **scope, plan=plan["members"])
        except ValueError as error:
            report(
                event="monster_initial_population_skipped", **scope, reason=str(error)
            )
            outcomes.append(dict(scope, applied=False, reason=str(error)))
        else:
            report(
                event="monster_initial_population_ready",
                **scope,
                duplicate=result.get("duplicate", False),
                disabled=result.get("disabled", False),
            )
            outcomes.append(dict(scope, result=result))
    return tuple(outcomes)
