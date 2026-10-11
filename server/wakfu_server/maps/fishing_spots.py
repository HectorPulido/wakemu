"""Durable fixed-identity fishing spots and their 300-second refill lifecycle."""
from datetime import timedelta

from psycopg.types.json import Jsonb

from .resource_domains import is_fish


def _supported_stage(reference, stage):
    from .fishing_products import supports_stage

    if not is_fish(reference):
        raise ValueError("Fishing spot references a non-fish resource")
    if stage not in (2, 3) or not supports_stage(reference, stage):
        raise ValueError("Fishing spot has no supported native fishing action")


def validate_placements(placements, *, navigation_surface=None):
    """Validate fixed public placements against native fish terrain and range."""
    from .fishing_navigation import surface

    navigation_surface = navigation_surface or surface
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
    validated = []
    for row in list(placements):
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError("Invalid fishing spot placement fields")
        if any(
            type(row[key]) is not int
            for key in expected - {"provenance", "respawn_seconds"}
        ):
            raise ValueError("Invalid fishing spot placement identity")
        if not 0 < row["resource_uid"] < 2**63 or row["instance_id"] != 0:
            raise ValueError("Fishing spots require public world identities")
        if not isinstance(row["provenance"], dict) or not row["provenance"]:
            raise ValueError("Fishing spot provenance is required")
        if row["respawn_seconds"] is not None:
            _delay(None, row["respawn_seconds"])
        reference, stage = row["resource_reference"], row["stage"]
        if stage not in (2, 3):
            raise ValueError("Fishing placement must target an active native stage")
        _supported_stage(reference, stage)
        ground = navigation_surface(row["map_id"], row["x"], row["y"], row["z"])
        fallback = (
            row["provenance"].get("species_ground_policy")
            == "local-fishing-ground-fallback"
        )
        if reference not in ground["eligible_refs"] and not (
            fallback
            and ground["ground_id"] > 0
            and any(is_fish(candidate) for candidate in ground["eligible_refs"])
        ):
            raise ValueError("Fishing spot is incompatible with native terrain")
        if not ground["approaches"]:
            raise ValueError("Fishing spot has no native harvesting approach")
        validated.append(row)
    if len({row["resource_uid"] for row in validated}) != len(validated) or len(
        {(row["map_id"], row["x"], row["y"]) for row in validated}
    ) != len(validated):
        raise ValueError("Duplicate fishing spot identities or cells")
    return validated


def install(store, placements):
    """Install reviewed spots idempotently without changing an exhaustion timer."""
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
        for row in sorted(validated, key=lambda value: value["resource_uid"]):
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (
                    f"planting-cell:{row['map_id']}:{row['instance_id']}:{row['x']}:{row['y']}",
                ),
            )
            existing = db.execute(
                "SELECT * FROM fishing_spot_slots WHERE resource_uid=%s FOR UPDATE",
                (row["resource_uid"],),
            ).fetchone()
            if existing is not None:
                if (
                    any(existing[key] != row[key] for key in keys)
                    or existing["provenance"] != row["provenance"]
                ):
                    raise ValueError("Cannot replace an existing fishing placement")
                continue
            if db.execute(
                "SELECT 1 FROM mining_vein_slots WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s AND enabled",
                tuple(row[key] for key in ("map_id", "instance_id", "x", "y")),
            ).fetchone():
                raise ValueError("Fishing spot cell is reserved for a mineral vein")
            if db.execute(
                "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
                tuple(row[key] for key in ("map_id", "instance_id", "x", "y")),
            ).fetchone():
                raise ValueError("Fishing spot cell already contains a resource")
            db.execute(
                "INSERT INTO fishing_spot_slots(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,respawn_seconds,provenance,available_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(row[key] for key in keys)
                + (Jsonb(row["provenance"]), store.now()),
            )
            added += 1
    return added


def _delay(db, override):
    if override is None:
        row = db.execute(
            "SELECT value FROM settings WHERE name='fishing_spot_policy'"
        ).fetchone()
        policy = None if row is None else row["value"]
        if (
            not isinstance(policy, dict)
            or set(policy) != {"version", "respawn_seconds"}
            or type(policy["version"]) is not int
            or policy["version"] != 1
        ):
            raise ValueError("Invalid fishing spot policy")
        override = policy["respawn_seconds"]
    if type(override) is not int or not 1 <= override <= 2678400:
        raise ValueError("Invalid fishing spot respawn delay")
    return override


def deplete(db, resource, now):
    """Exhaust an installed spot inside the successful harvest transaction."""
    slot = db.execute(
        "SELECT * FROM fishing_spot_slots WHERE resource_uid=%s FOR UPDATE",
        (resource["resource_uid"],),
    ).fetchone()
    if slot is None:
        return False
    keys = (
        "map_id",
        "instance_id",
        "x",
        "y",
        "z",
        "resource_reference",
        "stage",
    )
    if not slot["active"] or any(slot[key] != resource[key] for key in keys):
        raise ValueError("Fishing spot slot does not match its active resource")
    _supported_stage(slot["resource_reference"], slot["stage"])
    delay = _delay(db, slot["respawn_seconds"])
    db.execute(
        "UPDATE fishing_spot_slots SET active=FALSE,available_at=%s WHERE resource_uid=%s",
        (now + timedelta(seconds=delay), resource["resource_uid"]),
    )
    return True


def refill(store, *, limit=100, resource_uid=None, expected_available_at=None):
    """Restore due spots once, reviving the same exhausted stage-1 row when present."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid fishing refill batch size")
    now = store.now()
    restored = 0
    with store.connection() as db:
        slots = db.execute(
            "SELECT * FROM fishing_spot_slots WHERE enabled AND NOT active "
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
            _supported_stage(slot["resource_reference"], slot["stage"])
            from .fixed_resource_slots import restore_resource

            if not restore_resource(
                db,
                slot,
                now,
                spawn_flag="fishing_spawn",
                empty_stage=1,
            ):
                continue
            db.execute(
                "UPDATE fishing_spot_slots SET active=TRUE WHERE resource_uid=%s",
                (slot["resource_uid"],),
            )
            restored += 1
    return restored
