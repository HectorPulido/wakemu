"""Reviewed native entrance paths with stable source-node identities.

The source catalog remains immutable. A path is only a projection of its own
six/or-more reviewed nodes; unrelated historical pins never acquire this policy.
Native stairs are source-bound free interactions, not fabricated victory gates.
"""
from copy import deepcopy
from hashlib import sha256
import json

HINT_PREFIX = "hint:"
POLICY = "native-entry-discriminated-encounter-paths-v1"
TRANSFER = "native_entry_transfer"
POSTBOSS = "qualified_native_postboss_route"


def digest(value):
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def validate_policy(topology, *, native_source=None):
    policy = topology.get("entry_path_policy")
    if policy is None:
        return {}
    if (
        type(policy) is not dict
        or policy.get("policy") != POLICY
        or topology.get("policy") != "native_mixed_victory_policy"
        or not isinstance(policy.get("provenance"), str)
        or not policy["provenance"].strip()
    ):
        raise ValueError("Missing reviewed native entry path authority")
    nodes = {row.get("source_order", row["order"]) for row in topology["rooms"]}
    if len(nodes) != len(topology["rooms"]) or any(
        type(node) is not int or node <= 0 for node in nodes
    ):
        raise ValueError("Native path source nodes are ambiguous")
    paths = policy.get("paths")
    if type(paths) is not list or len(paths) < 2:
        raise ValueError("Native entry alternatives require explicit paths")
    result = {}
    terminal = policy.get("shared_terminal_source_order")
    for path in paths:
        key = path.get("key") if type(path) is dict else None
        main = path.get("main_source_orders") if type(path) is dict else None
        postboss = path.get("postboss_source_orders") if type(path) is dict else None
        if (
            type(key) is not str
            or not key
            or key in result
            or type(main) is not list
            or not main
            or type(postboss) is not list
            or any(type(node) is not int for node in main + postboss)
            or len(set(main + postboss)) != len(main + postboss)
            or set(main + postboss) != nodes
            or terminal != main[-1]
            or path.get("terminal_source_order") != terminal
        ):
            raise ValueError("Native path must partition its actual source encounters")
        if path.get("review_status") not in ("qualified", "unresolved_native_roster"):
            raise ValueError("Native entry path lacks an explicit review status")
        expected = policy.get("native_required_count")
        if (
            path["review_status"] == "qualified"
            and expected is not None
            and (type(expected) is not int or len(main) != expected)
        ):
            raise ValueError(
                "Qualified native entry path contradicts its current source count"
            )
        result[key] = path
    identities = set()
    entries = policy.get("entry_sources")
    if type(entries) is not list or not entries:
        raise ValueError("Native path lacks entrance discriminators")
    for entry in entries:
        identity = tuple(
            entry.get(key) for key in ("map_id", "source_id", "destination_id")
        )
        if (
            any(type(value) is not int or value <= 0 for value in identity)
            or identity in identities
            or entry.get("path") not in result
        ):
            raise ValueError("Native entry path identity is ambiguous")
        identities.add(identity)
    transfers = policy.get("entry_transfers")
    if type(transfers) is not list:
        raise ValueError("Native entry transfers must be explicitly declared")
    seen = set()
    for transfer in transfers:
        identity = (
            transfer.get("map_id"),
            transfer.get("source_id"),
            transfer.get("destination_id"),
        )
        if (
            identity in seen
            or transfer.get("binding_kind") != TRANSFER
            or transfer.get("from_path") not in result
            or transfer.get("to_path") not in result
            or transfer["from_path"] == transfer["to_path"]
            or "progression_gate_room" in transfer
        ):
            raise ValueError("Native entrance transfer is not an alternative path")
        seen.add(identity)
        source = transfer.get("native_source")
        if native_source is not None:
            source = native_source(identity[0], identity[1])
        if (
            type(source) is not dict
            or source.get("map_id") != topology["asset_map_id"]
            or source.get("id") != identity[1]
            or digest(source) != transfer.get("source_sha256")
        ):
            raise ValueError("Native entrance transfer source changed")
        destinations = [
            row
            for row in source.get("destinations", ())
            if row.get("destination_id") == identity[2]
        ]
        if len(destinations) != 1:
            raise ValueError("Native entrance transfer has no unique destination")
        destination = destinations[0]
        expected = {key: destination[key] for key in ("map_id", "x", "y", "z")}
        if (
            destination.get("map_id") != topology["asset_map_id"]
            or destination.get("criterion", "").strip()
            or destination.get("item_reference", 0)
            or destination.get("cyW", 0)
            or destination.get("cyX", 0)
            or destination.get("cyZ", -1) >= 0
            or transfer.get("destination_position") != expected
        ):
            raise ValueError("Native entrance transfer is not a free same-map stair")
    return result


def transfer_binding(topology, source_id, destination_id):
    validate_policy(topology)
    matches = [
        row
        for row in topology.get("entry_path_policy", {}).get("entry_transfers", ())
        if row["source_id"] == source_id and row["destination_id"] == destination_id
    ]
    if len(matches) != 1:
        raise ValueError("Native entrance transfer lacks a unique reviewed binding")
    return matches[0]


def validate_transfer(topology, binding):
    record = transfer_binding(topology, binding["source_id"], binding["destination_id"])
    expected = tuple(record["destination_position"][key] for key in ("x", "y", "z"))
    if (
        binding.get("binding_kind") != TRANSFER
        or "progression_gate_room" in binding
        or tuple(binding.get("destination_position", ())) != expected
    ):
        raise ValueError("Native entry transfer contradicts its literal source")
    return None


def entrance_path(topology, instance):
    paths = validate_policy(topology)
    if not paths:
        return None
    identity = tuple(
        instance[key]
        for key in ("entry_map_id", "entry_object_id", "entry_destination_id")
    )
    matches = [
        row["path"]
        for row in topology["entry_path_policy"]["entry_sources"]
        if tuple(row[key] for key in ("map_id", "source_id", "destination_id"))
        == identity
    ]
    if len(matches) != 1:
        raise ValueError("Pinned native entrance has no reviewed path")
    return matches[0]


def project_configuration(source, path_key):
    """Produce one full logical path while retaining every source roster/cell."""
    paths = validate_policy(source["topology"])
    if not paths:
        return source
    if (
        path_key not in paths
        or source["topology"].get("selected_entry_path") is not None
    ):
        raise ValueError(
            "Native entry projection requires its immutable source catalog"
        )
    path = paths[path_key]
    if path["review_status"] != "qualified":
        raise ValueError("Native entry route requires its unresolved encounter roster")
    order = path["main_source_orders"] + path["postboss_source_orders"]
    remap = {node: index + 1 for index, node in enumerate(order)}
    plan, topology = deepcopy(source["compiled_plan"]), deepcopy(source["topology"])
    for container in (plan, topology):
        rows = {
            row.get("source_order", row["order"]): row for row in container["rooms"]
        }
        container["rooms"] = []
        for node in order:
            row = rows[node]
            row.update(source_order=node, order=remap[node])
            container["rooms"].append(row)
    for collection in (
        "doors",
        "physical_doors",
        "physical_exit_objects",
        "position_trigger_gates",
    ):
        for binding in topology.get(collection, ()):
            for key in ("source_room", "destination_room", "room_order"):
                if key in binding:
                    binding[key] = remap[binding[key]]
            if collection == "physical_doors":
                binding["source_room"], binding["destination_room"] = sorted(
                    (binding["source_room"], binding["destination_room"])
                )
    topology["auto_edges"] = []
    bind_transfer_approaches(topology)
    assign_native_gate_cells(topology)
    main = list(range(1, len(path["main_source_orders"]) + 1))
    evidence = dict(
        authority=topology["entry_path_policy"]["provenance"],
        source_configuration_sha256=digest(source),
        path=path_key,
    )
    postboss_status = (
        POSTBOSS
        if path.get("postboss_review_status") == "qualified"
        else "unresolved_native_access"
    )
    topology["optional_room_policy"] = dict(
        policy="reviewed-main-and-optional-rooms-v1",
        main_room_orders=main,
        main_source_orders=path["main_source_orders"],
        optional_rooms=[
            dict(
                order=remap[node],
                source_order=node,
                access=dict(status=postboss_status, evidence=deepcopy(evidence)),
            )
            for node in path["postboss_source_orders"]
        ],
        source_evidence={
            str(node): deepcopy(evidence) for node in path["postboss_source_orders"]
        },
        removed_automatic_edges=[],
    )
    plan["original_source_document_sha256"] = source["compiled_plan"]["document_sha256"]
    plan["document_sha256"] = digest(
        dict(
            source_configuration_sha256=digest(source),
            source_document_sha256=plan["original_source_document_sha256"],
            entry_path=path_key,
            main_source_orders=path["main_source_orders"],
            postboss_source_orders=path["postboss_source_orders"],
        )
    )
    from wakfu_server.dungeon_runtime_config import prepare_configuration

    topology["selected_entry_path"] = path_key
    topology["entry_path_source_sha256"] = digest(source)
    return prepare_configuration(
        plan,
        topology,
        source["route"],
        version=source["version"],
        provenance=source["provenance"],
        level_policy=source["level_policy"],
    )


def frozen_rooms(configuration):
    """Use the ordinary plan adapter: optional nodes never inflate main count."""
    from wakfu_server.dungeon_runtime_config import plan_from_configuration

    plan = plan_from_configuration(configuration)
    return [
        dict(
            order=room.order,
            monsters=[
                dict(
                    ref_id=monster.ref_id,
                    count=monster.count,
                    min_level=monster.native_min_level,
                    max_level=monster.native_max_level,
                    role=monster.role,
                )
                for monster in room.monsters
            ],
        )
        for room in plan.rooms
    ]


def projected_for_instance(db, instance, source, progress):
    """Validate the source pin, then its selected projection fingerprint."""
    paths = validate_policy(source["topology"])
    if not paths:
        if (
            progress is not None
            and progress["catalog_hash"] != source["compiled_plan"]["document_sha256"]
        ):
            raise ValueError("Pinned dungeon roster differs from existing run")
        return source
    selected = None if progress is None else progress.get("branch_key")
    selected = path_key(selected) or entrance_path(source["topology"], instance)
    projected = project_configuration(source, selected)
    if (
        progress is not None
        and progress["catalog_hash"] != projected["compiled_plan"]["document_sha256"]
    ):
        raise ValueError(
            "Dungeon entry path projection differs from committed progress"
        )
    return projected


def select_unfought_path(db, instance, source, target_key):
    """Change a first-room hint only before any durable encounter is admitted.

    The caller owns the same transaction as native transport and group hydration.
    NOWAIT avoids blocking on the canonical run while an account barrier is held.
    Nothing here changes character positions or grants an encounter result.
    """
    paths = validate_policy(source["topology"])
    if target_key not in paths or paths[target_key]["review_status"] != "qualified":
        raise ValueError("Native entry route requires its unresolved encounter roster")
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE NOWAIT",
        (instance["instance_id"],),
    ).fetchone()
    if (
        run is None
        or run["status"] != "active"
        or run["current_room"] != 1
        or not str(run.get("branch_key") or "").startswith(HINT_PREFIX)
    ):
        raise ValueError(
            "Native route choice is only available before the first encounter"
        )
    existing = db.execute(
        "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s LIMIT 1",
        (instance["instance_id"],),
    ).fetchone()
    if existing is not None:
        raise ValueError("Native route choice already has an admitted encounter")
    projected_for_instance(db, instance, source, run)
    old_key = path_key(run.get("branch_key")) or entrance_path(
        source["topology"], instance
    )
    if old_key == target_key:
        return project_configuration(source, target_key), False
    projected = project_configuration(source, target_key)
    receipt = db.execute(
        "SELECT asset_map_id,group_id FROM dungeon_room_spawn_receipts "
        "WHERE instance_id=%s AND room_order=1 FOR UPDATE",
        (instance["instance_id"],),
    ).fetchone()
    if receipt is not None:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                f"monster-population:{receipt['asset_map_id']}:{instance['instance_id']}",
            ),
        )
        group = db.execute(
            "SELECT members,status,ecology_admin_removed_ids FROM combat_groups "
            "WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
            (receipt["asset_map_id"], instance["instance_id"], receipt["group_id"]),
        ).fetchone()
        if group is None or group["status"] != "available":
            raise ValueError("Unfought native route group is no longer available")
        # Existing durable removal markers retire unused world actors without
        # manufacturing combat defeats, XP, drops or a victory receipt.
        from psycopg.types.json import Jsonb

        removed = sorted(
            set(group["ecology_admin_removed_ids"])
            | {row["id"] for row in group["members"]}
        )
        db.execute(
            "UPDATE combat_groups SET ecology_admin_removed_ids=%s,revision=revision+1 "
            "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            (
                Jsonb(removed),
                receipt["asset_map_id"],
                instance["instance_id"],
                receipt["group_id"],
            ),
        )
        identities = [row["id"] for row in group["members"]]
        for table in ("monster_maturation_timers", "monster_reproduction_timers"):
            db.execute(
                f"DELETE FROM {table} WHERE map_id=%s AND instance_id=%s AND monster_id=ANY(%s)",
                (receipt["asset_map_id"], instance["instance_id"], identities),
            )
        db.execute(
            "UPDATE monster_maturation_outbox SET published=TRUE WHERE map_id=%s "
            "AND instance_id=%s AND group_id=%s AND monster_id=ANY(%s)",
            (
                receipt["asset_map_id"],
                instance["instance_id"],
                receipt["group_id"],
                identities,
            ),
        )
        db.execute(
            "UPDATE monster_reproduction_outbox o SET published=TRUE "
            "FROM monster_reproduction_receipts r WHERE o.map_id=r.map_id "
            "AND o.instance_id=r.instance_id AND o.monster_id=r.monster_id AND o.cycle=r.cycle "
            "AND o.map_id=%s AND o.instance_id=%s AND o.group_id=%s "
            "AND (o.monster_id=ANY(%s) OR r.child_id=ANY(%s))",
            (
                receipt["asset_map_id"],
                instance["instance_id"],
                receipt["group_id"],
                identities,
                identities,
            ),
        )
        db.execute(
            "DELETE FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=1",
            (instance["instance_id"],),
        )
    from psycopg.types.json import Jsonb

    db.execute(
        "UPDATE dungeon_room_runs SET branch_key=%s,catalog_hash=%s,rooms=%s,revision=revision+1 "
        "WHERE instance_id=%s",
        (
            HINT_PREFIX + target_key,
            projected["compiled_plan"]["document_sha256"],
            Jsonb(frozen_rooms(projected)),
            instance["instance_id"],
        ),
    )
    return projected, True


def path_key(value):
    """Decode an unfought entrance hint; ordinary branch keys stay unchanged."""
    if value is None:
        return None
    if type(value) is not str or not value:
        raise ValueError("Invalid native entry path selection")
    return value[len(HINT_PREFIX) :] if value.startswith(HINT_PREFIX) else value


def commit_path(db, instance_id):
    """Freeze the selected path after its first successful encounter binding.

    The caller has already acquired the run lock and inserted the encounter in
    the same transaction. A later rollback therefore rolls back this lock too.
    No result, reward, room frontier or character position is manufactured.
    """
    db.execute(
        "UPDATE dungeon_room_runs SET branch_key=substring(branch_key FROM %s) "
        "WHERE instance_id=%s AND branch_key LIKE %s",
        (len(HINT_PREFIX) + 1, instance_id, HINT_PREFIX + "%"),
    )


def foyer_cells(topology):
    """Unconditional stairs retain access to both native entrance foyers.

    This affects exploration only. Encounter binding and room admission continue
    to require the selected path's durable group and exact pinned room.
    """
    paths = validate_policy(topology)
    first = {path["main_source_orders"][0] for path in paths.values()}
    return frozenset(
        tuple(cell)
        for room in topology["rooms"]
        if room.get("source_order", room["order"]) in first
        for cell in room["cells"]
    )


def accessible_postboss_orders(topology):
    if topology.get("_entry_main_completed") is not True:
        return frozenset()
    return frozenset(
        row["order"]
        for row in topology.get("optional_room_policy", {}).get("optional_rooms", ())
        if row.get("access", {}).get("status") == POSTBOSS
    )


def assign_native_gate_cells(topology):
    """Give a reviewed gate's genuine ordinary floor to its destination node.

    Collision retains the raw native object altitude. This authoring projection
    adds no floor or edge: only source physical cells with an existing walking
    edge qualify. A closed native Door still rejects entry before its victory.
    """
    doors = topology.get("physical_doors", ())
    if not doors:
        return
    from wakfu_server.combat_sn_path import NativeSnColumns
    from wakfu_server.combat_walk_surface_policy import (
        native_npc_point_placement_allowed,
    )
    from wakfu_server.dungeon_native_door_collision import native_blocking_cells

    columns = NativeSnColumns.from_published(topology["asset_map_id"])
    geometry = topology["exploration_geometry"]
    raw_cells = set(map(tuple, geometry["cells"]))
    endpoints = {tuple(point) for edge in geometry["edges"] for point in edge}
    rooms = {room["order"]: room for room in topology["rooms"]}
    assignments = {}
    for door in doors:
        for cell in native_blocking_cells(
            topology["asset_map_id"],
            door["position"],
            columns=columns,
            expected_source_sha256=columns.source_sha256,
        ):
            if (
                cell not in raw_cells
                or cell not in endpoints
                or not native_npc_point_placement_allowed(columns, cell)
            ):
                continue  # Nonordinary centers are transit, not admission cells.
            target = door["destination_room"]
            if cell in assignments and assignments[cell] != target:
                raise ValueError(
                    "Reviewed native gates claim conflicting destination cells"
                )
            assignments[cell] = target
    for room in rooms.values():
        cells = {
            tuple(cell) for cell in room["cells"] if tuple(cell) not in assignments
        }
        cells.update(
            cell for cell, target in assignments.items() if target == room["order"]
        )
        room["cells"] = [list(cell) for cell in sorted(cells)]


def entrance_room_orders(topology):
    if topology.get("entry_path_policy") is None:
        return frozenset()
    paths = validate_policy(topology)
    first = {path["main_source_orders"][0] for path in paths.values()}
    return frozenset(
        room["order"]
        for room in topology["rooms"]
        if room.get("source_order", room["order"]) in first
    )


def bind_transfer_approaches(topology):
    """Bind existing literal native approach cells to their real source node."""
    from wakfu_server import generic_transports

    rooms = {
        room["order"]: set(map(tuple, room["cells"])) for room in topology["rooms"]
    }
    bindings = [
        (row, row["source_room"])
        for row in topology.get("doors", ())
        if row.get("binding_kind") == TRANSFER
    ]
    bindings += [
        (row, row["room_order"]) for row in topology.get("physical_exit_objects", ())
    ]
    for binding, room_order in bindings:
        source = generic_transports.source(
            topology["asset_map_id"], binding["source_id"]
        )
        if source is None:
            raise ValueError("Native entry interaction source is absent")
        center = tuple(source[key] for key in ("x", "y", "z"))
        literal = {
            tuple(point[key] for key in ("x", "y", "z"))
            for point in source.get("approach_positions", ())
        }
        if source.get("approach_blocks_center") is False:
            literal.add(center)
        approaches = literal & rooms[room_order]
        if not approaches:
            raise ValueError(
                "Native entry interaction has no literal source-node approach"
            )
        binding["native_approach_cells"] = [list(point) for point in sorted(approaches)]
        binding["source_position"] = list(center)


def pinned_reentry_path(db, instance, route):
    """Authorize an alternate entrance from this run's immutable policy only.

    Active route aliases identify an incoming native object, never authority to
    upgrade an old run. The recorded original entrance remains untouched.
    """
    from wakfu_server.dungeon_runtime_config import pinned_configuration

    source = pinned_configuration(
        db, instance["context_route_key"], instance["context_policy_version"]
    )
    topology = source["topology"]
    if topology.get("entry_path_policy") is None:
        return None
    from wakfu_server import generic_transports

    paths = validate_policy(topology, native_source=generic_transports.source)
    if (
        source["route"]["template_id"] != instance["template_id"]
        or source["route"]["definition_id"] != instance["definition_id"]
        or source["route"]["start_map_id"] != instance["start_map_id"]
        or route.template_id != instance["template_id"]
        or route.definition_id != instance["definition_id"]
        or route.start_map_id != instance["start_map_id"]
    ):
        raise ValueError("Native reentry route contradicts its pinned instance")
    original = entrance_path(topology, instance)
    identity = (route.entry_map_id, route.entry_object_id, route.destination_id)
    matches = [
        row["path"]
        for row in topology["entry_path_policy"]["entry_sources"]
        if tuple(row[key] for key in ("map_id", "source_id", "destination_id"))
        == identity
    ]
    if (
        len(matches) != 1
        or paths[original]["review_status"] != "qualified"
        or paths[matches[0]]["review_status"] != "qualified"
    ):
        return None
    progress = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
        (instance["instance_id"],),
    ).fetchone()
    if progress is None:
        raise ValueError("Native reentry has no pinned room progression")
    projected_for_instance(db, instance, source, progress)
    return matches[0]


def lock_members_nowait(db, identities):
    """Use the existing party advisory keys without waiting while owning run."""
    if any(
        type(identity) is not int or not 0 < identity < 2**63
        for identity in identities
    ):
        raise ValueError("Invalid player party member")
    for identity in sorted(set(identities)):
        row = db.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
            (f"player-party-member:{identity}",),
        ).fetchone()
        if row is None or row["locked"] is not True:
            raise ValueError("Dungeon party is busy; retry interaction")


def owner_lock_query(db, statement, parameters, *, nonblocking):
    """Keep run-before-owner callers from waiting on settlement-owned rows."""
    if not nonblocking:
        return db.execute(statement, parameters)
    if not statement.endswith(("FOR UPDATE", "FOR UPDATE OF s,c")):
        raise ValueError("Native owner lock query has no reviewed lock clause")
    from psycopg.errors import LockNotAvailable

    try:
        return db.execute(statement + " NOWAIT", parameters)
    except LockNotAvailable as error:
        raise ValueError("Dungeon participant is busy; retry interaction") from error


def lock_accounts_nowait(db, account_ids):
    """Own company mutation fences before any session/hero expansion work."""
    identities = sorted(set(account_ids))
    if any(
        type(identity) is not int or not 0 < identity < 2**63
        for identity in identities
    ):
        raise ValueError("Invalid dungeon participant account")
    return owner_lock_query(
        db,
        "SELECT id FROM accounts WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
        (identities,),
        nonblocking=True,
    ).fetchall()


def lock_owned_heroes_nowait(db, mains):
    """Prelock company heroes before the existing owned expansion helper.

    Account/session/main locks are already held, so the hero roster cannot be
    changed by its normal mutation fence while these rows are enumerated.
    """
    for main in sorted(mains, key=lambda row: (row["account_id"], row["id"])):
        rows = db.execute(
            "SELECT h.character_id FROM account_hero_slots h "
            "JOIN account_hero_rosters r USING(account_id) "
            "WHERE h.account_id=%s AND r.leader_id=%s ORDER BY h.character_id",
            (main["account_id"], main["id"]),
        ).fetchall()
        identities = [row["character_id"] for row in rows]
        if identities:
            locked = owner_lock_query(
                db,
                "SELECT id FROM characters WHERE account_id=%s AND id=ANY(%s) "
                "AND deleted_at IS NULL ORDER BY id FOR UPDATE",
                (main["account_id"], identities),
                nonblocking=True,
            ).fetchall()
            if [row["id"] for row in locked] != identities:
                raise ValueError("Dungeon company changed during reentry")


def prelock_combat_owner_nowait(db, account_id, generation, character_id, now):
    """Let unchanged fight creation reacquire only its own owner locks.

    The caller already owns the run; every cross-domain owner lock must fail
    immediately rather than wait for a settlement that may need that run.
    """
    lock_accounts_nowait(db, [account_id])
    lease = owner_lock_query(
        db,
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, now),
        nonblocking=True,
    ).fetchone()
    if lease is None or lease["character_id"] != character_id:
        raise ValueError("Dungeon encounter session is stale")
    owner = owner_lock_query(
        db,
        "SELECT id FROM characters WHERE id=%s AND account_id=%s "
        "AND deleted_at IS NULL FOR UPDATE",
        (character_id, account_id),
        nonblocking=True,
    ).fetchone()
    if owner is None:
        raise ValueError("Dungeon encounter character is not owned")
