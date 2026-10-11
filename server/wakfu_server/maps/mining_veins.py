"""Durable fixed mineral slots; harvest and timed refill never reproduce flora."""
from datetime import timedelta

from psycopg.types.json import Jsonb

from .planting import RESOURCES
from .resource_domains import is_mineral


def _harvest_stage(reference, stage):
    from .mining_products import supports_action

    if not is_mineral(reference):
        raise ValueError("Mining slot references a non-mineral resource")
    step = next(
        (
            row
            for row in RESOURCES[reference]["stage_definitions"]
            if row["stage_id"] == stage
        ),
        None,
    )
    if step is None or not any(supports_action(action) for action in step["actions"]):
        raise ValueError("Mining slot has no supported terminal mineral harvest")


def validate_placements(placements, *, navigation_surface=None):
    """Validate reviewed placement identity, native terrain and access edges."""
    from .mining_navigation import surface

    navigation_surface = navigation_surface or surface

    rows = list(placements)
    validated = []
    for row in rows:
        expected = {
            "resource_uid",
            "map_id",
            "instance_id",
            "x",
            "y",
            "z",
            "resource_reference",
            "stage",
            "respawn_seconds",
            "provenance",
        }
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError("Invalid mining placement fields")
        if any(
            type(row[k]) is not int
            for k in expected - {"provenance", "respawn_seconds"}
        ):
            raise ValueError("Invalid mining placement identity")
        if not 0 < row["resource_uid"] < 2**63 or row["instance_id"] != 0:
            raise ValueError("Mining placements require public world identities")
        if not isinstance(row["provenance"], dict) or not row["provenance"]:
            raise ValueError("Mining placement provenance is required")
        if row["respawn_seconds"] is not None:
            _delay(None, row["respawn_seconds"])
        ref = row["resource_reference"]
        if not is_mineral(ref):
            raise ValueError("Mining placement references a non-mineral")
        position = tuple(row[k] for k in ("x", "y", "z"))
        ground = navigation_surface(row["map_id"], *position)
        native_refs = ground["eligible_refs"]
        fallback = (
            row["provenance"].get("species_ground_policy")
            == "local-mineral-ground-fallback"
        )
        if ref not in native_refs and not (
            fallback
            and ground["ground_id"] > 0
            and any(is_mineral(candidate) for candidate in native_refs)
        ):
            raise ValueError(
                "Mining placement is incompatible with native terrain or explicit local policy"
            )
        if not ground["approaches"]:
            raise ValueError("Mining placement has no native harvesting approach")
        _harvest_stage(ref, row["stage"])
        validated.append(row)
    if len({row["resource_uid"] for row in validated}) != len(validated) or len(
        {(r["map_id"], r["x"], r["y"]) for r in validated}
    ) != len(validated):
        raise ValueError("Duplicate mining placement identities or cells")
    return validated


def install(store, placements):
    """Install fixed slots idempotently without resetting exhaustion deadlines."""
    validated = validate_placements(placements)
    added = 0
    keys = (
        "resource_uid",
        "map_id",
        "instance_id",
        "x",
        "y",
        "z",
        "resource_reference",
        "stage",
        "respawn_seconds",
    )
    with store.connection() as db:
        for row in sorted(validated, key=lambda r: r["resource_uid"]):
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (
                    f"planting-cell:{row['map_id']}:{row['instance_id']}:{row['x']}:{row['y']}",
                ),
            )
            existing = db.execute(
                "SELECT * FROM mining_vein_slots WHERE resource_uid=%s FOR UPDATE",
                (row["resource_uid"],),
            ).fetchone()
            if existing is not None:
                if (
                    any(existing[k] != row[k] for k in keys)
                    or existing["provenance"] != row["provenance"]
                ):
                    raise ValueError("Cannot replace an existing mining placement")
                continue
            if db.execute(
                "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
                tuple(row[k] for k in ("map_id", "instance_id", "x", "y")),
            ).fetchone():
                raise ValueError("Mining placement cell already contains a resource")
            if db.execute(
                "SELECT 1 FROM fishing_spot_slots WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s AND enabled",
                tuple(row[k] for k in ("map_id", "instance_id", "x", "y")),
            ).fetchone():
                raise ValueError("Mining placement cell is reserved for a fishing spot")
            db.execute(
                "INSERT INTO mining_vein_slots(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,respawn_seconds,provenance,available_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(row[k] for k in keys) + (Jsonb(row["provenance"]), store.now()),
            )
            added += 1
    return added


def _delay(db, override):
    if override is None:
        row = db.execute(
            "SELECT value FROM settings WHERE name='mining_vein_policy'"
        ).fetchone()
        policy = None if row is None else row["value"]
        if (
            not isinstance(policy, dict)
            or not {"version", "respawn_seconds"} <= set(policy)
            or set(policy)
            - {"version", "respawn_seconds", "distribution", "product_selection"}
            or type(policy["version"]) is not int
            or policy["version"] != 1
        ):
            raise ValueError("Invalid mining vein policy")
        override = policy["respawn_seconds"]
    if type(override) is not int or not 1 <= override <= 2678400:
        raise ValueError("Invalid mining vein respawn delay")
    return override


def deplete(db, resource, now):
    """Called inside the reward transaction after locking the resource row."""
    slot = db.execute(
        "SELECT * FROM mining_vein_slots WHERE resource_uid=%s FOR UPDATE",
        (resource["resource_uid"],),
    ).fetchone()
    if slot is None:
        # Historical/test resources may exist without a durable placement.
        return False
    keys = ("map_id", "instance_id", "x", "y", "z", "resource_reference", "stage")
    if not slot["active"] or any(slot[k] != resource[k] for k in keys):
        raise ValueError("Mining vein slot does not match its active resource")
    delay = _delay(db, slot["respawn_seconds"])
    db.execute(
        "UPDATE mining_vein_slots SET active=FALSE,available_at=%s WHERE resource_uid=%s",
        (now + timedelta(seconds=delay), resource["resource_uid"]),
    )
    return True


def refill(store, *, limit=100, resource_uid=None, expected_available_at=None):
    """Restore due placements exactly once and queue full resource publication.

    Fixed slots preserve identity across deletion, restarts and concurrent ticks.
    Conflicting resources retain their cell; the placement retries next tick.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid mining refill batch size")
    now = store.now()
    restored = 0
    with store.connection() as db:
        slots = db.execute(
            "SELECT * FROM mining_vein_slots WHERE enabled AND NOT active "
            "AND available_at<=%s "
            + ("AND resource_uid=%s " if resource_uid is not None else "")
            + ("AND available_at=%s " if expected_available_at is not None else "")
            + "ORDER BY available_at,resource_uid LIMIT %s FOR UPDATE SKIP LOCKED",
            (now,)
            + (() if resource_uid is None else (resource_uid,))
            + (() if expected_available_at is None else (expected_available_at,))
            + (limit,),
        ).fetchall()
        for slot in slots:
            reference = slot["resource_reference"]
            _harvest_stage(reference, slot["stage"])
            from .fixed_resource_slots import restore_resource

            if not restore_resource(db, slot, now, spawn_flag="mining_spawn"):
                continue
            db.execute(
                "UPDATE mining_vein_slots SET active=TRUE WHERE resource_uid=%s",
                (slot["resource_uid"],),
            )
            restored += 1
    return restored
