"""World-owned monster proposal validation, commits, and native publication.

Rust owns autonomous planning. SQL receipts and current World occupancy remain
the authoritative fences for accepting and publishing each proposal."""

import json
import struct
import time
from .monster_habitat_cells import habitat_destination_allowed

MAX_WANDER_BATCH_GROUPS = 8
MAX_WANDER_BATCH_MOVED_MEMBERS = 40
MAX_WANDER_BATCH_PACKET_BYTES = 64 * 1024
MAX_WANDER_BATCH_JSON_BYTES = 224 * 1024
MAX_WANDER_BATCH_SECONDS = 0.025


def _edges(map_id):
    from .spatial_geometry import catalog_edges

    return catalog_edges(map_id)


def _scripted_intro_scope(scope):
    return (
        len(scope) == 2
        and scope[0] == 1361
        and type(scope[1]) is int
        and (1 << 62) < scope[1] < (1 << 62) + (1 << 48)
    )


def _path_cells(packets):
    from .spatial_native import get_spatial

    return set(map(tuple, get_spatial().call("geometry.path_cells", packets=packets)))


def _path_cells_by_actor(packets):
    from .spatial_native import get_spatial

    return {
        actor: list(map(tuple, path))
        for actor, path in get_spatial().call(
            "geometry.path_cells_by_actor", packets=packets
        )
    }


def _validate_bulk_wander_move(move):
    from .spatial_native import get_spatial

    result = get_spatial().call("geometry.validate_bulk_move", move=move)
    return (
        result["group_id"],
        result["expected"],
        result["moved"],
        [(opcode, bytes.fromhex(payload)) for opcode, payload in result["packets"]],
        set(map(tuple, result["cells"])),
        result["moved_count"],
        result["packet_bytes"],
        result["dispersal"],
        result["overlap_escape"],
    )


def _valid_dispersal_path(expected, moved, paths_by_actor, current_groups):
    from .spatial_native import get_spatial
    from .spatial_geometry import member_rows, group_rows

    return get_spatial().call(
        "geometry.valid_dispersal_path",
        expected=member_rows(expected),
        moved=member_rows(moved),
        paths=list(paths_by_actor.items()),
        groups=group_rows(current_groups),
    )


def _path_occupied(packets, expected, players, current_groups):
    from .spatial_native import get_spatial
    from .spatial_geometry import member_rows, actor_position, group_rows

    return get_spatial().call(
        "geometry.path_occupied",
        packets=packets,
        members=member_rows(expected),
        players=[actor_position(player) for player in players],
        groups=group_rows(current_groups),
    )


def _native_paths_allowed(map_id, expected, paths_by_actor, max_steps):
    from .spatial_geometry import member_rows

    return _edges(map_id).native_index.call(
        "geometry.paths_allowed",
        expected=member_rows(expected),
        paths=list(paths_by_actor.items()),
        max_steps=max_steps,
    )


def _native_habitat_paths_allowed(scope, paths_by_actor):
    from .spatial_geometry import habitats, surfaces

    if not habitats().call(
        "geometry.habitat_tracked", map_id=scope[0], instance_id=scope[1]
    ):
        return True
    return surfaces(scope[0]).call(
        "geometry.surface_paths_allowed", paths=list(paths_by_actor.items())
    )


def _warm_spatial_scope(scope):
    from .spatial_geometry import habitats, surfaces

    if habitats().call(
        "geometry.habitat_tracked", map_id=scope[0], instance_id=scope[1]
    ):
        surfaces(scope[0])


def _apply_wander_bulk(store, groups, harvests, world, proposal, *, world_epoch):
    from . import monster_wander as wander

    scope = proposal.get("scope")
    moves = proposal.get("moves")
    configuration = proposal.get("configuration")
    if (
        not isinstance(scope, list)
        or len(scope) != 2
        or any(type(value) is not int for value in scope)
        or not isinstance(moves, list)
        or not 1 <= len(moves) <= MAX_WANDER_BATCH_GROUPS
        or not isinstance(configuration, dict)
        or len(json.dumps(proposal, separators=(",", ":")).encode("utf-8"))
        > MAX_WANDER_BATCH_JSON_BYTES
    ):
        raise ValueError("Invalid bulk wander envelope")
    if wander.policy(store) != configuration:
        return {"status": "stale_policy"}
    decoded_moves = []
    seen_group_ids = set()
    moved_members = 0
    packet_bytes = 0
    invalid_groups = 0
    for move in moves:
        try:
            decoded = _validate_bulk_wander_move(move)
        except (TypeError, ValueError, struct.error):
            invalid_groups += 1
            continue
        if (
            decoded[0] in seen_group_ids
            or moved_members + decoded[5] > MAX_WANDER_BATCH_MOVED_MEMBERS
            or packet_bytes + decoded[6] > MAX_WANDER_BATCH_PACKET_BYTES
        ):
            invalid_groups += 1
            continue
        paths_by_actor = {}
        try:
            paths_by_actor = _path_cells_by_actor(
                [[opcode, payload.hex()] for opcode, payload in decoded[3]]
            )
            habitat_valid = _native_habitat_paths_allowed(scope, paths_by_actor)
            if decoded[7] or decoded[8]:
                if not _native_paths_allowed(
                    scope[0], decoded[1], paths_by_actor, configuration["max_steps"]
                ):
                    habitat_valid = False
        except (KeyError, TypeError, ValueError):
            habitat_valid = False
        seen_group_ids.add(decoded[0])
        moved_members += decoded[5]
        packet_bytes += decoded[6]
        decoded_moves.append((*decoded, habitat_valid, paths_by_actor))

    with groups.lock, harvests.lock:
        # Claims and local group mutations remain serialized by groups.lock.
        # Read this map once, then update its captured rosters after each CAS.
        # The native spatial reservation below fences only one group's SQL
        # commit, never the whole batch or socket publication.
        current_groups = groups.snapshot(*scope)
        excluded = set(harvests.targets)
        published_packets = []
        applied_groups = 0
        skipped_groups = invalid_groups
        deadline = time.monotonic() + MAX_WANDER_BATCH_SECONDS
        budget_exhausted = False
        for index, (
            group_id,
            expected,
            moved,
            packets,
            cells,
            _count,
            _size,
            dispersal,
            overlap_escape,
            habitat_valid,
            paths_by_actor,
        ) in enumerate(decoded_moves):
            if time.monotonic() >= deadline:
                skipped_groups += len(decoded_moves) - index
                budget_exhausted = True
                break
            expected_ids = {member["id"] for member in expected}
            if expected_ids & excluded:
                skipped_groups += 1
                continue
            with world.scope_barrier(*scope):
                players = world.ecology_snapshot(*scope)
                if not players:
                    if not applied_groups:
                        return {"status": "absent"}
                    skipped_groups += len(decoded_moves) - index
                    break
                current = next(
                    (
                        group
                        for group in current_groups
                        if group.get(
                            "group_id", group.get("key", (None, None, None))[2]
                        )
                        == group_id
                    ),
                    None,
                )
                if current is None or current["status"] != "available":
                    skipped_groups += 1
                    continue
                if not habitat_valid:
                    skipped_groups += 1
                    continue
                if dispersal:
                    if not _valid_dispersal_path(
                        expected, moved, paths_by_actor, current_groups
                    ) or not wander.clear_destination(moved, players, current_groups):
                        skipped_groups += 1
                        continue
                if overlap_escape and not wander.overlap_escape_valid(
                    expected, moved, players, current_groups
                ):
                    skipped_groups += 1
                    continue
                if not (dispersal or overlap_escape) and _path_occupied(
                    [[opcode, payload.hex()] for opcode, payload in packets],
                    expected,
                    players,
                    current_groups,
                ):
                    skipped_groups += 1
                    continue
                if not groups.move_members((*scope, group_id), expected, moved):
                    skipped_groups += 1
                    continue
                current["members"] = moved
                applied_groups += 1
                published_packets.extend(packets)
        if published_packets:
            world.emit_location_batch(scope[0], scope[1], published_packets)
        if not applied_groups:
            return {
                "status": "applied" if budget_exhausted else "stale_group",
                "skipped_groups": skipped_groups,
                "skip_reason": "budget" if budget_exhausted else "cas_or_guard",
            }
        return {
            "status": "applied",
            "applied_groups": applied_groups,
            "skipped_groups": skipped_groups,
            "skip_reason": (
                "budget"
                if budget_exhausted
                else "cas_or_guard" if skipped_groups else None
            ),
        }


def apply(store, groups, harvests, world, proposal, *, world_epoch):
    """Validate fresh live fences, commit CAS/receipts, then publish locally."""
    if proposal["world_epoch"] != world_epoch:
        return {"status": "stale_epoch"}
    if _scripted_intro_scope(tuple(proposal.get("scope", ()))):
        return {"status": "stale"}

    from . import monster_maturation as maturation
    from . import monster_reproduction as reproduction
    from . import monster_wander as wander
    from .combat_monster_world import remove_message, spawn_group

    if proposal["kind"] == "idle_distribution":
        from .monster_idle_distribution_store import commit, validate_chunk

        prepared = validate_chunk(store, proposal)
        scope = tuple(proposal["scope"])
        with groups.lock, harvests.lock, world.scope_barrier(*scope):
            episode_current = world.empty_scope_generation(*scope) == proposal[
                "empty_generation"
            ] and not world.registered_scope_snapshot(*scope)
            outcomes = commit(
                store,
                groups,
                proposal,
                episode_current=episode_current,
                prepared=prepared,
            )
            return dict(
                status=(
                    "applied"
                    if outcomes
                    else "duplicate" if episode_current else "stale"
                ),
                applied_groups=sum(row["status"] == "applied" for row in outcomes),
                skipped_groups=sum(row["status"] == "skipped" for row in outcomes),
            )
    if proposal["kind"] == "cleanup_unassigned":
        from .monster_population_cleanup import apply as apply_cleanup

        return apply_cleanup(
            store, groups, harvests, world, proposal, world_epoch=world_epoch
        )
    if proposal["kind"] == "lifecycle_bulk":
        return _apply_lifecycle_bulk(
            store, groups, harvests, world, proposal, world_epoch=world_epoch
        )
    if proposal["kind"] == "wander_bulk":
        return _apply_wander_bulk(
            store, groups, harvests, world, proposal, world_epoch=world_epoch
        )
    publication = proposal["kind"].startswith("publish_")
    kind = proposal["kind"][8:] if publication else proposal["kind"]
    domains = dict(maturation=maturation, reproduction=reproduction, wander=wander)
    if kind not in domains or (publication and kind == "wander"):
        raise ValueError("Unknown monster ecology proposal")
    # Policy IO occurs before live registry locks; the received plan must match.
    if (
        not publication
        and "plan_incarnation" not in proposal.get("ticket", {})
        and domains[kind].policy(store) != proposal["configuration"]
    ):
        return {"status": "stale_policy"}
    scope = tuple(proposal["scope"])
    # Geometry stays outside the world registry locks even for prepared births.
    birth_edges = (
        _edges(scope[0]) if kind == "reproduction" and not publication else None
    )
    _warm_spatial_scope(scope)
    with groups.lock, harvests.lock:
        packets_to_publish = []
        acknowledgements = []
        with world.scope_barrier(*scope):
            players = world.ecology_snapshot(*scope)
            if not players:
                return {"status": "absent"}
            excluded = set(harvests.targets)
            if any(m["id"] in excluded for m in proposal["expected_members"]):
                return {"status": "harvesting"}
            if kind == "wander" and not publication:
                current_groups = groups.snapshot(*scope)
                if _path_occupied(
                    proposal["packets"],
                    proposal["expected_members"],
                    players,
                    current_groups,
                ):
                    return {"status": "occupied"}
                if not groups.move_members(
                    (*scope, proposal["group_id"]),
                    proposal["expected_members"],
                    proposal["moved_members"],
                ):
                    return {"status": "stale_group"}
                packets_to_publish.extend(
                    (opcode, bytes.fromhex(payload))
                    for opcode, payload in proposal["packets"]
                )
                outcome = {"status": "applied"}
            else:
                receipt = None
                if publication:
                    affected_group = proposal["group_id"]
                else:
                    kwargs = dict(
                        present=True,
                        excluded_ids=excluded,
                        draw=proposal["draw"],
                        configuration=proposal["configuration"],
                        prepared=proposal,
                    )
                    if kind == "reproduction":
                        kwargs.update(
                            indexed=birth_edges,
                            players=players,
                            group_draw=proposal["group_draw"],
                        )
                    receipt = domains[kind].attempt(store, proposal["ticket"], **kwargs)
                    if receipt is None:
                        return {"status": "stale_group"}
                    affected_group = (
                        receipt.get("child_group_id")
                        if kind == "reproduction"
                        else receipt.get("group_id")
                    )
                # The durable group/outbox stays claim-fenced; sockets do not
                # retain the native map reservation while a peer is slow.
                for group_id in () if affected_group is None else (affected_group,):
                    batch = domains[kind].unpublished(store, *scope, group_id=group_id)
                    if not batch:
                        continue
                    current = batch[-1]
                    if current["status"] != "available" or any(
                        m["id"] in excluded for m in current["members"]
                    ):
                        continue
                    packets_to_publish.append(
                        remove_message([m["id"] for m in current["members"]])
                    )
                    packets_to_publish.append(
                        (12608, spawn_group(current["members"], group_id=group_id))
                    )
                    acknowledgements.extend((domains[kind], event) for event in batch)
                outcome = {
                    "status": (
                        "duplicate"
                        if receipt is not None and receipt["duplicate"]
                        else "applied"
                    )
                }
        for opcode, payload in packets_to_publish:
            world.emit_location(*scope, opcode, payload)
        for domain, event in acknowledgements:
            domain.acknowledge(store, event)
        return outcome


def _apply_lifecycle_bulk(store, groups, harvests, world, proposal, *, world_epoch):
    from .monster_life_plans import failure

    operations = proposal.get("operations")
    scope = proposal.get("scope")
    if (
        not isinstance(scope, list)
        or len(scope) != 2
        or any(type(value) is not int for value in scope)
        or not isinstance(operations, list)
        or not 1 <= len(operations) <= 16
        or len(json.dumps(proposal, separators=(",", ":")).encode()) > 224 * 1024
    ):
        raise ValueError("Invalid lifecycle bulk envelope")
    seen = set()
    for operation in operations:
        if (
            not isinstance(operation, dict)
            or operation.get("kind") not in ("maturation", "reproduction")
            or operation.get("scope") != scope
            or operation.get("world_epoch") != proposal.get("world_epoch")
            or not isinstance(operation.get("configuration"), dict)
            or not isinstance(operation.get("expected_members"), list)
            or not operation["expected_members"]
            or any(
                not isinstance(member, dict) or type(member.get("id")) is not int
                for member in operation["expected_members"]
            )
            or type(operation.get("draw")) not in (int, float)
            or not 0 <= operation["draw"] < 1
        ):
            raise ValueError("Invalid lifecycle bulk operation")
        ticket = operation.get("ticket")
        if (
            not isinstance(ticket, dict)
            or any(
                type(ticket.get(key)) is not int
                for key in (
                    "map_id",
                    "instance_id",
                    "monster_id",
                    "group_id",
                    "reference",
                    "cycle",
                )
            )
            or [ticket["map_id"], ticket["instance_id"]] != scope
            or ticket["cycle"] < 1
            or not isinstance(ticket.get("plan_incarnation"), str)
            or not isinstance(ticket.get("decision"), dict)
        ):
            raise ValueError("Invalid lifecycle bulk ticket")
        identity = (
            operation["kind"],
            ticket["monster_id"],
            ticket["cycle"],
            ticket["plan_incarnation"],
        )
        if identity in seen:
            raise ValueError("Duplicate lifecycle bulk event")
        seen.add(identity)
        if operation["kind"] == "maturation":
            if "grown" not in operation or (
                operation["grown"] is not None
                and not isinstance(operation["grown"], dict)
            ):
                raise ValueError("Invalid lifecycle bulk maturation")
            from .monster_maturation import validate_policy
        else:
            if (
                not isinstance(operation.get("destination"), list)
                or len(operation["destination"]) != 3
                or any(type(value) is not int for value in operation["destination"])
                or "child" not in operation
                or (
                    operation["child"] is not None
                    and not isinstance(operation["child"], dict)
                )
                or type(operation.get("group_draw")) not in (int, float)
                or not 0 <= operation["group_draw"] < 1
            ):
                raise ValueError("Invalid lifecycle bulk reproduction")
            from .monster_reproduction import validate_policy
        validate_policy(operation["configuration"])
    results = []
    deadline = time.monotonic() + MAX_WANDER_BATCH_SECONDS
    for operation in operations:
        if time.monotonic() >= deadline:
            break
        try:
            results.append(
                apply(
                    store, groups, harvests, world, operation, world_epoch=world_epoch
                )
            )
        except Exception:
            failure(store, operation["ticket"], operation["kind"])
            raise
    return dict(
        status="applied",
        operations=results,
        skipped_operations=len(operations) - len(results),
        skip_reason="budget" if len(results) < len(operations) else None,
    )
