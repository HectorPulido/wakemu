"""Explicit, versioned local dungeon configuration from reviewed JSON evidence."""
import hashlib
import json

from .dungeon_catalog import DungeonPlan, MonsterRoster, RoomPlan
from .dungeon_capacity import MAX_DUNGEON_MONSTERS


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def prepare_configuration(plan, topology, route, *, version, provenance):
    # Freeze JSON-owned values before hashing. Integer metadata keys become
    # strings on persistence and must not change canonical ordering on reload.
    plan, topology, route = json.loads(json.dumps([plan, topology, route]))
    if (
        type(version) is not int
        or version <= 0
        or not isinstance(provenance, str)
        or not provenance.strip()
    ):
        raise ValueError("Explicit configuration version and provenance required")
    if plan.get("roster_ready") is not True or plan.get("diagnostics"):
        raise ValueError("Reviewed dungeon roster is not ready")
    if (plan["definition_id"], plan["template_id"], plan["asset_map_id"]) != (
        route["definition_id"],
        route["template_id"],
        route["start_map_id"],
    ):
        raise ValueError("Compiled dungeon identities contradict the native route")
    orders = [room["order"] for room in plan["rooms"]]
    if orders != list(range(1, len(orders) + 1)) or not orders:
        raise ValueError("Dungeon room orders must be contiguous")
    if (
        topology["asset_map_id"] != plan["asset_map_id"]
        or [room["order"] for room in topology["rooms"]] != orders
    ):
        raise ValueError("Native topology does not match the reviewed rooms")
    for room in plan["rooms"]:
        if room.get("diagnostics") or not room["monsters"]:
            raise ValueError("Room roster is incomplete")
        total = 0
        for monster in room["monsters"]:
            values = [
                monster[key]
                for key in ("ref_id", "count", "native_min_level", "native_max_level")
            ]
            if (
                any(type(value) is not int or value <= 0 for value in values)
                or values[2] > values[3]
            ):
                raise ValueError(
                    "Unresolved native monster identity, quantity or grade range"
                )
            total += monster["count"]
        if not 1 <= total <= MAX_DUNGEON_MONSTERS:
            raise ValueError("Dungeon room exceeds supported placement capacity")
    for room in topology["rooms"]:
        anchor = room["anchor"]
        if len(anchor) != 3 or any(type(value) is not int for value in anchor):
            raise ValueError("Native room anchor must be integral")
        if tuple(anchor) not in set(map(tuple, room["cells"])):
            raise ValueError("Native room anchor is not walkable")
    for door in topology["doors"]:
        from wakfu_server import dungeon_native_flow

        dungeon_native_flow.validate_transport_binding(topology, door)
    from wakfu_server import dungeon_shared_arena

    dungeon_shared_arena.validate(topology)
    from wakfu_server import dungeon_branches

    dungeon_branches.validate(topology)
    from wakfu_server import dungeon_exit

    dungeon_exit.validate_foreign_exterior(topology)
    context = dict(
        route_key=route["key"],
        policy_version=version,
        template_id=route["template_id"],
        definition_id=route["definition_id"],
        max_level=0,
        min_level=0,
        difficulty_level=2,
        is_difficulty_available=False,
        can_increase_difficulty=False,
        is_competitive_cancelled=False,
        allowed_ids=[],
        provenance=provenance,
    )
    return dict(
        schema_version=1,
        version=version,
        slug=plan["slug"],
        route=route,
        compiled_plan=plan,
        topology=topology,
        context_policy=context,
        level_policy={"mode": "native_minimum", "provenance": provenance},
        provenance=provenance,
        evidence_hashes={
            "plan": canonical_hash(plan),
            "topology": canonical_hash(topology),
            "route": canonical_hash(route),
        },
    )


def plan_from_configuration(config):
    plan = config["compiled_plan"]
    if canonical_hash(plan) != config["evidence_hashes"]["plan"]:
        raise ValueError("Frozen dungeon plan hash mismatch")
    return DungeonPlan(
        slug=plan["slug"],
        source_url=plan["source_url"],
        source_sha256=plan["source_sha256"],
        document_sha256=plan["document_sha256"],
        definition_id=plan["definition_id"],
        template_id=plan["template_id"],
        asset_map_id=plan["asset_map_id"],
        diagnostics=tuple(plan["diagnostics"]),
        rooms=tuple(
            RoomPlan(
                order=room["order"],
                diagnostics=tuple(room["diagnostics"]),
                monsters=tuple(
                    MonsterRoster(**monster) for monster in room["monsters"]
                ),
            )
            for room in plan["rooms"]
        ),
    )


def level_selector(config):
    if config["level_policy"]["mode"] != "native_minimum":
        raise ValueError("Unsupported explicit dungeon grade policy")

    def select(native, roster):
        if (native["min_level"], native["max_level"]) != (
            roster["min_level"],
            roster["max_level"],
        ):
            raise ValueError("Native monster grade bounds changed")
        return native["min_level"]

    return select


def install_configuration(db, config):
    """Call inside a transaction; freeze version before selecting it as active."""
    route = config["route"]
    version = config["version"]
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f'dungeon_runtime_config:{route["key"]}',),
    )
    expected = prepare_configuration(
        config["compiled_plan"],
        config["topology"],
        route,
        version=version,
        provenance=config["provenance"],
    )
    if config != expected:
        raise ValueError("Configuration content differs from validated local policy")
    current = db.execute(
        "SELECT configuration AS value FROM dungeon_runtime_configurations "
        "WHERE route_key=%s AND policy_version=%s FOR UPDATE",
        (route["key"], version),
    ).fetchone()
    if current is not None and current["value"] != config:
        raise ValueError("Existing configuration version is immutable")
    if current is None:
        db.execute(
            "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) "
            "VALUES(%s,%s,%s::jsonb)",
            (route["key"], version, json.dumps(config)),
        )
    context = config["context_policy"]
    existing = db.execute(
        "SELECT * FROM dungeon_context_policy_versions WHERE route_key=%s AND policy_version=%s",
        (route["key"], version),
    ).fetchone()
    if existing is not None and any(
        existing[field] != value for field, value in context.items()
    ):
        raise ValueError("Existing context policy version conflicts")
    if existing is None:
        fields = tuple(context)
        db.execute(
            "INSERT INTO dungeon_context_policy_versions("
            + ",".join(fields)
            + ") VALUES("
            + ",".join(["%s"] * len(fields))
            + ")",
            tuple(context[field] for field in fields),
        )
    db.execute(
        "INSERT INTO dungeon_context_active_policies(route_key,policy_version) VALUES(%s,%s) "
        "ON CONFLICT(route_key) DO UPDATE SET policy_version=EXCLUDED.policy_version",
        (route["key"], version),
    )
    db.execute(
        "INSERT INTO dungeon_runtime_active_configurations(route_key,policy_version) VALUES(%s,%s) "
        "ON CONFLICT(route_key) DO UPDATE SET policy_version=EXCLUDED.policy_version",
        (route["key"], version),
    )


def active_configuration(db, route_key):
    selected = db.execute(
        "SELECT policy_version FROM dungeon_runtime_active_configurations WHERE route_key=%s",
        (route_key,),
    ).fetchone()
    if selected is None:
        raise ValueError("Dungeon runtime configuration is not installed")
    return pinned_configuration(db, route_key, selected["policy_version"])


def pinned_configuration(db, route_key, version, *, expected_plan_hash=None):
    if type(version) is not int or version <= 0:
        raise ValueError("Invalid pinned dungeon configuration version")
    row = db.execute(
        "SELECT configuration AS value FROM dungeon_runtime_configurations "
        "WHERE route_key=%s AND policy_version=%s",
        (route_key, version),
    ).fetchone()
    if row is None:
        raise ValueError("Selected dungeon runtime configuration is missing")
    config = row["value"]
    if config["route"]["key"] != route_key or config["version"] != version:
        raise ValueError("Selected dungeon runtime identity conflicts")
    plan_from_configuration(config)
    if (
        expected_plan_hash is not None
        and config["compiled_plan"]["document_sha256"] != expected_plan_hash
    ):
        raise ValueError("Pinned dungeon roster differs from existing run")
    if (
        canonical_hash(config["topology"]) != config["evidence_hashes"]["topology"]
        or canonical_hash(config["route"]) != config["evidence_hashes"]["route"]
    ):
        raise ValueError("Frozen dungeon topology or route hash mismatch")
    return config
