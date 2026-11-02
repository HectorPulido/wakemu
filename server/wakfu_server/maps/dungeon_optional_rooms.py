"""Reviewed required encounters, with unresolved optional content kept intact."""
from copy import deepcopy

POLICY = "reviewed-main-and-optional-rooms-v1"


def main_room_orders(topology):
    orders = [room["order"] for room in topology["rooms"]]
    if not orders or any(type(n) is not int for n in orders):
        raise ValueError("Dungeon rooms require integral encounter orders")
    record = topology.get("optional_room_policy")
    if record is None:
        return tuple(orders)
    main = record.get("main_room_orders")
    optional = record.get("optional_rooms")
    if (
        record.get("policy") != POLICY
        or not isinstance(main, list)
        or not main
        or any(type(n) is not int for n in main)
        or main != list(range(1, len(main) + 1))
        or not isinstance(optional, list)
        or not optional
        or not record.get("source_evidence")
        or [r.get("order") for r in optional] != orders[len(main) :]
        or orders != list(range(1, len(orders) + 1))
        or len(main) >= len(orders)
    ):
        raise ValueError("Invalid reviewed main/optional room partition")
    for room in optional:
        access = room.get("access", {})
        if (
            type(room.get("source_order")) is not int
            or access.get("status")
            not in (
                "unresolved_native_access",
                "qualified_native_ground_item",
                "qualified_native_vote",
                "qualified_native_postboss_route",
            )
            or (
                access.get("status")
                in ("qualified_native_ground_item", "qualified_native_vote")
                and not access.get("rule_key")
            )
            or not access.get("evidence")
        ):
            raise ValueError("Optional native access must remain explicitly unresolved")
    optional_orders = {room["order"] for room in optional}
    if any(
        edge.get("source_room") in optional_orders
        or edge.get("destination_room") in optional_orders
        for edge in topology.get("auto_edges", ())
    ):
        raise ValueError("Optional encounters cannot be automatic progression")
    return tuple(main)


def require_main_room(topology, order):
    if order not in main_room_orders(topology):
        raise ValueError("Optional room requires unresolved native access")


def cell_rooms(topology, *, reject_ambiguous=False):
    """Keep a shared optional floor owned by its required main encounter.

    Legacy lookup callers retain their existing last-room behavior; strict
    object-state validation retains its old duplicate rejection. Only reviewed
    optional metadata authorizes main/optional floor sharing.
    """
    optional = topology.get("optional_room_policy") is not None
    main = set(main_room_orders(topology)) if optional else set()
    result = {}
    for room in topology["rooms"]:
        order = room["order"]
        for raw in room["cells"]:
            cell = tuple(raw)
            previous = result.get(cell)
            if previous is not None:
                if optional:
                    if (previous in main) == (order in main):
                        raise ValueError("Ambiguous required or optional room terrain")
                    if previous in main:
                        continue
                elif reject_ambiguous:
                    raise ValueError("Dungeon terrain belongs to multiple rooms")
            result[cell] = order
    return result


def validate_movement(topology, request):
    """Block entry into optional-only terrain; retain legacy occupants' egress.

    Shared main-room floor is not an invented physical gate. Its optional
    encounter remains closed separately by required-room spawn admission.
    """
    if topology.get("optional_room_policy") is None:
        return
    main = set(main_room_orders(topology))
    from wakfu_server.dungeon_optional_vote_geometry import optional_room_allowed

    main.update(
        r["order"]
        for r in topology["rooms"]
        if optional_room_allowed(topology, r["order"])
    )
    main_cells = {
        tuple(c) for r in topology["rooms"] if r["order"] in main for c in r["cells"]
    }
    optional_cells = {
        tuple(c)
        for r in topology["rooms"]
        if r["order"] not in main
        for c in r["cells"]
    } - main_cells
    if topology.get("_entry_main_completed") is True:
        qualified = {
            row["order"]
            for row in topology["optional_room_policy"]["optional_rooms"]
            if row["access"]["status"] == "qualified_native_postboss_route"
        }
        optional_cells -= {
            tuple(cell)
            for room in topology["rooms"]
            if room["order"] in qualified
            for cell in room["cells"]
        }
    current = tuple(request["start_position"][axis] for axis in ("x", "y", "z"))
    inside = current in optional_cells
    for step in request["steps"]:
        current = tuple(
            current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
        )
        if current in optional_cells and not inside:
            raise ValueError("Optional native access is unresolved")
        inside = current in optional_cells


def partition_rooms(plan, topology, *, main_source_orders, access_evidence):
    """Reindex required rooms first; retain every source roster, cell and exit.

    Callers supply reviewed source orders, never infer optionality from bosses.
    Missing main transport bindings are not invented for non-prefix routes.
    """
    plan, topology = deepcopy(plan), deepcopy(topology)
    if topology.get("optional_room_policy") is not None:
        raise ValueError("Room semantics were already partitioned")
    by_order = {r["order"]: r for r in plan["rooms"]}
    terrain = {r["order"]: r for r in topology["rooms"]}
    main = list(main_source_orders)
    if (
        not main
        or any(type(n) is not int for n in main)
        or len(set(main)) != len(main)
        or len(by_order) != len(plan["rooms"])
        or len(terrain) != len(topology["rooms"])
        or not set(main) < set(by_order)
        or set(by_order) != set(terrain)
    ):
        raise ValueError("Reviewed main source orders must partition actual rooms")
    optional = sorted(set(by_order) - set(main))
    if set(access_evidence) != set(optional):
        raise ValueError("Every optional source room needs access evidence")
    order = main + optional
    remap = {source: index + 1 for index, source in enumerate(order)}
    for rows in (by_order, terrain):
        for source, row in rows.items():
            row["source_order"] = source
            row["order"] = remap[source]
    plan["rooms"] = [by_order[n] for n in order]
    topology["rooms"] = [terrain[n] for n in order]
    removed = []
    for key in ("doors", "physical_doors", "physical_exit_objects", "auto_edges"):
        kept = []
        for binding in topology.get(key, ()):
            if key == "auto_edges" and (
                binding["source_room"] in optional
                or binding["destination_room"] in optional
            ):
                removed.append(deepcopy(binding))
                continue
            for field in ("room_order", "source_room", "destination_room"):
                if field in binding:
                    binding[field] = remap[binding[field]]
            kept.append(binding)
        if key in topology:
            topology[key] = kept
    witness = topology.get("completed_exit_witness")
    if witness is not None:
        witness["room_order"] = remap[witness["room_order"]]
    topology["optional_room_policy"] = dict(
        policy=POLICY,
        main_room_orders=list(range(1, len(main) + 1)),
        main_source_orders=main,
        optional_rooms=[
            dict(
                order=remap[n],
                source_order=n,
                access=dict(
                    status="unresolved_native_access",
                    evidence=deepcopy(access_evidence[n]),
                ),
            )
            for n in optional
        ],
        source_evidence={str(k): deepcopy(v) for k, v in access_evidence.items()},
        removed_automatic_edges=removed,
    )
    from .dungeon_runtime_config import canonical_hash

    original_hash = plan["document_sha256"]
    plan["original_source_document_sha256"] = original_hash
    plan["document_sha256"] = canonical_hash(
        dict(
            original_source_document_sha256=original_hash,
            room_semantics=topology["optional_room_policy"],
        )
    )
    main_room_orders(topology)
    return plan, topology


def canonical_completion_preview(
    run, encounters, configuration, *, expected_old_hash, instance=None
):
    """Plan a bounded repair from durable victories without replaying settlement."""
    from .dungeon_runtime_config import plan_from_configuration

    plan = plan_from_configuration(configuration)
    rooms = [
        dict(
            order=r.order,
            monsters=[
                dict(
                    role=m.role,
                    count=m.count,
                    ref_id=m.ref_id,
                    min_level=m.native_min_level,
                    max_level=m.native_max_level,
                )
                for m in r.monsters
            ],
        )
        for r in plan.rooms
    ]
    count = len(rooms)
    victory_rows = [e for e in encounters if e["status"] == "victory"]
    victories = {e["room_order"]: e for e in victory_rows}
    if (
        run["catalog_hash"] != expected_old_hash
        or run["status"] != "active"
        or run["current_room"] != count + 1
        or run["rooms"][:count] != rooms
        or set(victories) != set(range(1, count + 1))
        or len(victory_rows) != count
        or any(e["room_order"] > count for e in encounters)
        or any(e["instance_id"] != run["instance_id"] for e in encounters)
    ):
        raise ValueError("Canonical completion lacks exact prior victory evidence")
    if instance is not None and instance["instance_id"] != run["instance_id"]:
        raise ValueError("Canonical completion instance differs from the frozen run")
    closed = instance is not None and instance["status"] == "closed"
    return dict(
        expected_revision=run["revision"],
        expected_catalog_hash=expected_old_hash,
        catalog_hash=plan.document_sha256,
        rooms=rooms,
        current_room=count,
        status="completed",
        revision=run["revision"] + 1,
        earned_fight_ids=[victories[n]["fight_id"] for n in range(1, count + 1)],
        reward_replay=False,
        encounter_updates=[],
        requires_idle_optional_group=True,
        historical_encounter_results_unchanged=True,
        requires_authoritative_transition_delivery=not closed,
        must_verify_no_members_or_characters_in_instance=closed,
    )
