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


def prepare_configuration(
    plan, topology, route, *, version, provenance, level_policy=None
):
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
    from .dungeon_optional_rooms import main_room_orders

    main_room_orders(topology)
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
    from wakfu_server.dungeon_encounter_regions import encounter_room

    for room in topology["rooms"]:
        encounter_room(room)
        anchor = room["anchor"]
        if len(anchor) != 3 or any(type(value) is not int for value in anchor):
            raise ValueError("Native room anchor must be integral")
        if tuple(anchor) not in set(map(tuple, room["cells"])):
            raise ValueError("Native room anchor is not walkable")
        descriptor = room.get("encounter_scene", {})
        if descriptor.get("fixed_actor_placements") is not None:
            from wakfu_server.combat_fixed_actor_placement import member_positions
            from wakfu_server.combat_placement_footprints import covered_cells
            from wakfu_server.combat_actor_snapshot import native_actor_catalog

            if descriptor.get("full_room_scope") is not True:
                raise ValueError("Fixed initial actors require the full native room")
            roster = next(
                row["monsters"]
                for row in plan["rooms"]
                if row["order"] == room["order"]
            )
            members = [
                dict(ref=row["ref_id"]) for row in roster for _ in range(row["count"])
            ]
            positions = member_positions(descriptor, members, room_cells=room["cells"])
            profiles = native_actor_catalog()["npc_profiles"]
            occupied = set()
            native_cells = set(map(tuple, room["cells"]))
            for index, cell in positions.items():
                body = covered_cells(
                    cell,
                    profiles[str(members[index]["ref"])]["physical_radius"],
                    native_cells,
                )
                if body & occupied or tuple(anchor) in body:
                    raise ValueError(
                        "Fixed initial body overlaps another actor or room arrival"
                    )
                occupied.update(body)
    from wakfu_server.dungeon_auto_edges import validate_auto_edges

    validate_auto_edges(topology)
    for door in topology["doors"]:
        from wakfu_server import dungeon_native_flow

        dungeon_native_flow.validate_transport_binding(topology, door)
    from wakfu_server import dungeon_shared_arena

    dungeon_shared_arena.validate(topology)
    from wakfu_server import dungeon_branches, dungeon_entry_paths

    branches = dungeon_branches.validate(topology)
    for branch in branches.values():
        for room in branch["rooms"]:
            encounter_room(room)
    if topology.get("excavation_access"):
        from wakfu_server import dungeon_rotation

        dungeon_rotation.validate(dict(topology=topology, compiled_plan=plan))
    if topology.get("entry_path_policy") is not None:
        from wakfu_server import generic_transports

        dungeon_entry_paths.validate_policy(
            topology, native_source=generic_transports.source
        )
    if topology.get("resource_obstacles") is not None:
        from wakfu_server import dungeon_resource_obstacles

        dungeon_resource_obstacles.policy(dict(topology=topology))
    from wakfu_server import dungeon_exit

    dungeon_exit.validate_foreign_exterior(topology)
    from wakfu_server.dungeon_stage_levels import prepare_policy

    selected_level_policy = prepare_policy(level_policy, provenance=provenance)
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
        level_policy=selected_level_policy,
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
    from .dungeon_optional_rooms import main_room_orders

    main_orders = main_room_orders(config["topology"])
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
            if room["order"] in main_orders
        ),
    )


def level_selector(config, *, room_order=None):
    from wakfu_server.dungeon_stage_levels import selector

    return selector(config, room_order=room_order)


def require_monster_admission(config):
    """Validate every room's selected native grade before activating the plan.

    Structural roster evidence does not establish ordinary NPC admission. Use
    the same current authority as room spawning, including its source-qualified
    empty-book event controllers, before any configuration write can commit.
    """
    from wakfu_server import dungeon_entry_paths

    paths = dungeon_entry_paths.validate_policy(config["topology"])
    if paths and config["topology"].get("selected_entry_path") is None:
        qualified = [
            key for key, row in paths.items() if row["review_status"] == "qualified"
        ]
        if not qualified:
            raise ValueError("No native entry path has an admitted roster")
        for key in qualified:
            require_monster_admission(
                dungeon_entry_paths.project_configuration(config, key)
            )
        return
    from wakfu_server import dungeon_monster_admission
    from wakfu_server.monsters import reference

    policy = dungeon_monster_admission.current_policy()
    checked = set()
    for room in config["compiled_plan"]["rooms"]:
        select_level = level_selector(config, room_order=room["order"])
        for monster in room["monsters"]:
            native = reference(monster["ref_id"])
            level = select_level(
                native,
                dict(
                    min_level=monster["native_min_level"],
                    max_level=monster["native_max_level"],
                ),
            )
            identity = (monster["ref_id"], level)
            if identity not in checked:
                dungeon_monster_admission.require(
                    policy, monster["ref_id"], level, level, native=native
                )
                checked.add(identity)


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
        level_policy=config["level_policy"],
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
    # Re-activating an existing version needs the same current admission proof
    # as a new version; immutable history alone cannot authorize a future spawn.
    require_monster_admission(config)
    if config["topology"].get("optional_vote_access") is not None:
        from wakfu_server.dungeon_optional_votes import rule_for

        rule_for(config)
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
