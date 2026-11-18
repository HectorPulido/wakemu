"""World-owned initial population commits and idempotent native publication.

Rust prepares configured region plans. World checks the current policy, native
catalog, population capacity, and durable scope before committing each plan."""

from wakfu_server import native_catalog as protocol_catalog
import json
import hashlib
from psycopg.types.json import Jsonb
from .paths import DATA_ROOT
from .monsters import owned_instance

REGIONS = {
    (world["map_id"], region["region_id"]): region
    for world in protocol_catalog.load(DATA_ROOT / "ecology-regions.json")
    for region in world["regions"]
}


def _has_population_capacity(db, map_id, instance_id, members):
    """Check the live map budget while the caller holds its population lock."""
    from .monster_population_capacity import has_capacity, snapshot as capacity_snapshot
    from .monster_reproduction import validate_policy

    row = db.execute(
        "SELECT value FROM settings WHERE name='monster_reproduction'"
    ).fetchone()
    policy = validate_policy(None if row is None else row["value"])
    return has_capacity(
        capacity_snapshot(db, map_id, instance_id),
        add_members=members,
        add_groups=1,
        max_members=policy["max_zone_members"],
        max_groups=policy["max_zone_groups"],
    )


def _scope_state(db, map_id, instance_id):
    groups = [
        dict(row)
        for row in db.execute(
            "SELECT group_id,status,members FROM combat_groups WHERE map_id=%s "
            "AND instance_id=%s ORDER BY group_id",
            (map_id, instance_id),
        )
    ]
    plants = [
        dict(row)
        for row in db.execute(
            "SELECT resource_uid,resource_reference,stage,x,y,z FROM planted_resources "
            "WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid",
            (map_id, instance_id),
        )
    ]
    return groups, plants


def _scope_digest(state):
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def proposal_dependencies(map_id):
    """Native inputs read by the configured Rust/world population proposal."""
    if type(map_id) is not int or not 0 < map_id < 2**31:
        raise ValueError("Invalid initial population source map")
    return (
        "initial-monster-population.json",
        "ecology-regions.json",
        "monsters.json",
        "native-actor-characteristics.json",
        "monster-encyclopedia.json",
        f"combat-maps/{map_id}.json",
        f"planting-maps/{map_id}.json",
    )


def apply_prepared(store, groups, proposal):
    """World-only bounded registration; all geometry was checked by worker."""
    plan, policy = proposal["plan"], proposal["policy"]
    from wakfu_server.native_catalog_compatibility import require_source_revision

    try:
        require_source_revision(
            proposal["catalog_revision"], proposal_dependencies(plan["map_id"])
        )
    except ValueError:
        return "stale"
    catalog = protocol_catalog.load(DATA_ROOT / "initial-monster-population.json")
    if plan not in catalog["plans"]:
        raise ValueError("Initial monster proposal is not configured")
    if (
        type(policy) is not dict
        or policy.get("enabled") is not True
        or type(policy.get("members_per_zone")) is not int
        or not 1 <= policy["members_per_zone"] <= 8
        or len(plan["members"]) != policy["members_per_zone"]
    ):
        raise ValueError("Invalid prepared initial monster population policy")
    map_id, instance_id, region_id = (
        plan[key] for key in ("map_id", "instance_id", "region_id")
    )
    with store.connection() as db, db.transaction():
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"monster-population:{map_id}:{instance_id}",),
        )
        if db.execute(
            "SELECT 1 FROM monster_initial_population WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            (map_id, instance_id, region_id),
        ).fetchone():
            return "stale"
        row = db.execute(
            "SELECT value FROM settings WHERE name='monster_initial_population'"
        ).fetchone()
        if row is None or row["value"] != policy or not policy["enabled"]:
            return "stale"
        if (
            _scope_digest(_scope_state(db, map_id, instance_id))
            != proposal["scope_digest"]
        ):
            return "stale"
        if not _has_population_capacity(db, map_id, instance_id, len(plan["members"])):
            return "stale"
        from .npc_actor_identity import allocate_block

        members = [
            owned_instance(
                row["reference"],
                row["level"],
                -allocate_block(db, 1),
                map_id=map_id,
                instance_id=instance_id,
                **{key: row[key] for key in ("x", "y", "z")},
            )
            for row in plan["members"]
        ]
        key = groups.register_transaction(
            db, map_id, instance_id, -members[0]["id"], members
        )
        db.execute(
            "INSERT INTO monster_initial_population VALUES(%s,%s,%s,%s,%s,%s)",
            (map_id, instance_id, region_id, policy["version"], key[2], Jsonb(members)),
        )
        db.execute(
            "INSERT INTO monster_initial_population_publication(map_id,instance_id,region_id,group_id) "
            "VALUES(%s,%s,%s,%s)",
            (map_id, instance_id, region_id, key[2]),
        )
        return "applied"


def publish_prepared(store, proposal, emit):
    """Publish latest available roster after durable birth; failed emits retry."""
    scope = tuple(proposal[key] for key in ("map_id", "instance_id", "region_id"))
    with store.connection() as db, db.transaction():
        row = db.execute(
            "SELECT group_id,published_at FROM monster_initial_population_publication "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s FOR UPDATE",
            scope,
        ).fetchone()
        if (
            row is None
            or row["published_at"] is not None
            or row["group_id"] != proposal["group_id"]
        ):
            return "stale"
        group = db.execute(
            "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND group_id=%s FOR UPDATE",
            (*scope[:2], row["group_id"]),
        ).fetchone()
        if group is None:
            raise ValueError("Initial monster publication lost its durable group")
        if group["status"] == "available":
            from wakfu_server.combat_monster_world import remove_message, spawn_group

            members = group["members"]
            # Idempotent replacement covers a crash after emit but before SQL
            # acknowledgment, and peers that loaded the durable group already.
            emit(
                *scope[:2],
                (
                    remove_message(tuple(member["id"] for member in members)),
                    (12608, spawn_group(members, group_id=row["group_id"])),
                ),
            )
        # Reserved/defeated groups are already owned by a combat lifecycle;
        # never resurrect or replace their exploration projection here.
        db.execute(
            "UPDATE monster_initial_population_publication SET published_at=CURRENT_TIMESTAMP "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            scope,
        )
        return "applied"
