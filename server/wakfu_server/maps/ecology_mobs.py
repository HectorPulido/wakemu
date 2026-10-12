"""External monster simulation planning with short world-owned commit fences.

Proposals are internal service messages, never client-supplied authority. The
worker and world use the same pinned catalog release. SQL receipts remain the
idempotency authority; publication is performed only by world.
"""
from copy import deepcopy
from contextlib import nullcontext
from functools import lru_cache
import random
import secrets
import json
import struct
import time
from .monster_habitat_cells import habitat_destination_allowed


MAX_WANDER_BATCH_GROUPS = 8
MAX_WANDER_BATCH_MOVED_MEMBERS = 40
MAX_WANDER_BATCH_PACKET_BYTES = 64 * 1024
MAX_WANDER_BATCH_JSON_BYTES = 224 * 1024
MAX_WANDER_BATCH_SECONDS = 0.025


@lru_cache(maxsize=16)
def _edges(map_id):
    from .combat_terrain import map_geometry
    from .monster_wander import edge_index

    return edge_index(map_geometry(map_id)["edges"])


def _sample():
    return secrets.randbelow(1 << 53) / (1 << 53)


def _scoped_players(players, scope):
    return [
        p
        for p in players
        if p.get("_ecology_active", True)
        and (p["map_id"], p.get("instance_id", 0)) == scope
    ]


def _path_cells(packets):
    """Decode our native movement packets for current occupancy validation."""
    import struct
    from protocol_codec import DIRECTIONS

    cells = set()
    for opcode, encoded in packets:
        if opcode != 13852:
            raise ValueError("Invalid ecology movement opcode")
        payload = bytes.fromhex(encoded)
        if len(payload) < 19:
            raise ValueError("Invalid ecology movement header")
        _, x, y, z, count = struct.unpack(">qiihB", payload[:19])
        if len(payload) != 19 + count:
            raise ValueError("Invalid ecology movement length")
        for delta in payload[19:]:
            _, dx, dy = DIRECTIONS[delta >> 5]
            dz = delta & 31
            if dz >= 16:
                dz -= 32
            x, y, z = x + dx, y + dy, z + dz
            cells.add((x, y, z))
    return cells


def _path_cells_by_actor(packets):
    """Decode every native step while retaining the actor that traverses it."""
    import struct
    from protocol_codec import DIRECTIONS

    result = {}
    for opcode, encoded in packets:
        if opcode != 13852:
            raise ValueError("Invalid ecology movement opcode")
        payload = bytes.fromhex(encoded)
        if len(payload) < 19:
            raise ValueError("Invalid ecology movement header")
        actor_id, x, y, z, count = struct.unpack(">qiihB", payload[:19])
        if len(payload) != 19 + count:
            raise ValueError("Invalid ecology movement length")
        cells = []
        for delta in payload[19:]:
            _, dx, dy = DIRECTIONS[delta >> 5]
            dz = delta & 31
            if dz >= 16:
                dz -= 32
            x, y, z = x + dx, y + dy, z + dz
            cells.append((x, y, z))
        result[actor_id] = cells
    return result


def prepare(store, snapshot, limit=16):
    """Run geometry, native construction and policy decisions outside world."""
    from . import monster_maturation as maturation
    from . import monster_life_plans as life_plans
    from . import monster_reproduction as reproduction
    from . import monster_wander as wander
    from .monsters import owned_instance
    from .combat_monster_world import spawn_group

    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid ecology proposal limit")
    epoch = snapshot["world_epoch"]
    if type(epoch) is not str or not epoch:
        raise ValueError("Missing ecology world epoch")
    players = [p for p in snapshot["players"] if p.get("_ecology_active", True)]
    excluded = set(snapshot["excluded_ids"])
    locations = {tuple(scope) for scope in snapshot["locations"]}
    locations &= {(p["map_id"], p.get("instance_id", 0)) for p in players}
    allow_wander = bool(snapshot.get("allow_wander", True))
    scopes = sorted(locations)
    domain_tick = snapshot.get("domain_planning_tick", 0)
    if type(domain_tick) is not int or domain_tick < 0:
        domain_tick = 0
    if scopes:
        scope_start = domain_tick % len(scopes)
        scopes = scopes[scope_start:] + scopes[:scope_start]
    from .monster_population_cleanup import prepare as prepare_cleanup

    # The worker advances wander cadence after a successful planning pass. Reserve
    # one scope-batch slot so publications or lifecycle tickets cannot fill the
    # whole budget before movement gets examined.
    wander_slots = min(1, len(scopes)) if allow_wander else 0
    background_limit = limit - wander_slots
    proposals = (
        prepare_cleanup(store, snapshot, limit=background_limit)
        if background_limit
        else []
    )
    noops = []
    policies = dict(
        maturation=maturation.policy(store),
        reproduction=reproduction.policy(store),
        wander=wander.policy(store),
    )
    previous = {tuple(scope) for scope in snapshot.get("previous_locations", [])}
    for scope in sorted(previous - locations):
        for domain in (maturation, reproduction):
            domain.observe(
                store,
                *scope,
                present=False,
                generation=epoch,
                now_ms=snapshot["now_ms"],
            )
    for scope in scopes:
        if reproduction.dungeon_population(store, scope[1]):
            continue
        scoped = _scoped_players(players, scope)
        # A fresh occupancy episode resets elapsed time even if the worker never
        # sampled the intervening empty interval.
        episode = scoped[0].get("presence_generation")
        observation_generation = (
            epoch if episode is None else f"{epoch}:presence:{episode}"
        )
        with store.connection() as db:
            groups = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s ORDER BY group_id",
                    scope,
                )
            ]
            planted = {
                (r["x"], r["y"])
                for r in db.execute(
                    "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s",
                    scope,
                )
            }
        by_id = {g["group_id"]: g for g in groups}
        living_groups = [g for g in groups if g["status"] != "defeated"]
        zone_members = sum(len(g["members"]) for g in living_groups)
        ordered_domains = [("maturation", maturation), ("reproduction", reproduction)]
        category_offset = domain_tick % len(ordered_domains)
        ordered_domains = (
            ordered_domains[category_offset:] + ordered_domains[:category_offset]
        )
        for domain_name, domain in ordered_domains if background_limit else ():
            if _proposal_slots(proposals) >= background_limit:
                break
            for group_id in dict.fromkeys(
                e["group_id"] for e in domain.unpublished(store, *scope)
            ):
                if _proposal_slots(proposals) >= background_limit:
                    break
                group = by_id.get(group_id)
                if group is not None and group["status"] == "available":
                    proposals.append(
                        dict(
                            kind="publish_" + domain_name,
                            world_epoch=epoch,
                            scope=list(scope),
                            group_id=group_id,
                            expected_members=deepcopy(list(group["members"])),
                        )
                    )
        indexed = None
        for kind, domain in ordered_domains if background_limit else ():
            if _proposal_slots(proposals) >= background_limit:
                break
            domain.observe(
                store,
                *scope,
                present=True,
                generation=observation_generation,
                now_ms=snapshot["now_ms"],
                excluded_ids=excluded,
                configuration=policies[kind],
            )
            tickets = life_plans.attach(
                store, scope, kind, domain.pending(store, *scope), policies[kind]
            )
            for ticket in tickets:
                if _proposal_slots(proposals) >= background_limit:
                    break
                group = by_id.get(ticket["group_id"])
                if (
                    group is None
                    or group["status"] != "available"
                    or ticket["monster_id"] in excluded
                ):
                    continue
                members = list(group["members"])
                if kind == "reproduction" and (
                    zone_members >= policies[kind]["max_zone_members"]
                    or (
                        len(living_groups) >= policies[kind]["max_zone_groups"]
                        and len(members) >= policies[kind]["max_members"]
                    )
                ):
                    # Keep the due timer intact, but do not enqueue work that the
                    # authoritative apply path must reject at these live counts.
                    continue
                parent = next(
                    (m for m in members if m["id"] == ticket["monster_id"]), None
                )
                if parent is None or parent["ref"] != ticket["reference"]:
                    continue
                proposal = dict(
                    kind=kind,
                    world_epoch=epoch,
                    scope=list(scope),
                    ticket=ticket,
                    configuration=ticket["plan_policy"],
                    expected_members=deepcopy(members),
                    draw=ticket["decision"]["draw"],
                )
                if kind == "reproduction" and proposal[
                    "draw"
                ] >= reproduction.birth_probability(
                    parent["ref"], proposal["configuration"], group_size=len(members)
                ):
                    proposal.update(
                        child=None,
                        group_draw=ticket["decision"]["group_draw"],
                        noop=True,
                    )
                    noops.append(proposal)
                    continue
                if kind == "maturation":
                    candidate = maturation.choose_next(
                        parent["ref"],
                        proposal["configuration"],
                        draw=proposal["draw"],
                        choose=lambda candidates: life_plans.choose(
                            candidates, ticket["decision"]
                        ),
                        members=members,
                    )
                    grown = (
                        None
                        if candidate is None
                        else owned_instance(
                            candidate["reference"],
                            candidate["min_level"],
                            parent["id"],
                            map_id=scope[0],
                            instance_id=scope[1],
                            team=parent["team"],
                            **{k: parent[k] for k in ("x", "y", "z")},
                        )
                    )
                    proposal["grown"] = grown
                    if grown is None:
                        proposal["noop"] = True
                        noops.append(proposal)
                        continue
                    if grown is not None:
                        replaced = [
                            grown if m["id"] == grown["id"] else m for m in members
                        ]
                        spawn_group(replaced, group_id=ticket["group_id"])
                else:
                    if indexed is None:
                        indexed = _edges(scope[0])
                    blocked = planted | {(p["x"], p["y"]) for p in scoped}
                    blocked |= {
                        (m["x"], m["y"])
                        for g in groups
                        if g["status"] != "defeated"
                        for m in g["members"]
                    }
                    candidates = [
                        p
                        for p in indexed[1].get(wander.point(parent), ())
                        if p[:2] not in blocked
                        and habitat_destination_allowed(
                            scope[0],
                            scope[1],
                            p,
                            parent=parent,
                            family_id=maturation.STAGES[parent["ref"]][0]["family_id"],
                        )
                    ]
                    if not candidates:
                        continue
                    destination = life_plans.choose_destination(
                        candidates, ticket["decision"]
                    )
                    proposal.update(
                        destination=list(destination),
                        group_draw=ticket["decision"]["group_draw"],
                        child=None,
                    )
                    if proposal["draw"] < reproduction.birth_probability(
                        parent["ref"],
                        proposal["configuration"],
                        group_size=len(members),
                    ):
                        stage = maturation.STAGES[parent["ref"]]
                        from .monster_family_stages import initial_candidates

                        birth_pool = initial_candidates(stage[0]["family_id"])
                        if not birth_pool:
                            continue
                        candidate = life_plans.choose(birth_pool, ticket["decision"])
                        with store.connection() as db:
                            _, identity = reproduction.allocate_identity(db)
                        child = owned_instance(
                            candidate["reference"],
                            candidate["min_level"],
                            identity,
                            map_id=scope[0],
                            instance_id=scope[1],
                            team=parent["team"],
                            x=destination[0],
                            y=destination[1],
                            z=destination[2],
                        )
                        proposal["child"] = child
                        spawn_group([child], group_id=-identity)
                proposals.append(proposal)
        if indexed is None:
            indexed = _edges(scope[0])
        configuration = policies["wander"]
        if not allow_wander or _proposal_slots(proposals) >= limit:
            continue
        wander_groups = wander.visible_groups(
            groups,
            scoped,
            radius=configuration["radius"],
            tick=domain_tick,
            batch_size=MAX_WANDER_BATCH_GROUPS,
        )
        moves = []
        # Build the live occupancy once per scope. Rewalking every member in
        # every other group for each candidate costs O(population * moved).
        scope_occupied = {
            wander.point(member) for group in groups for member in group["members"]
        }
        moved_member_count = 0
        packet_bytes = 0
        plan_deadline = time.monotonic() + MAX_WANDER_BATCH_SECONDS
        for group in wander_groups:
            if time.monotonic() >= plan_deadline:
                break
            members = list(group["members"])
            if (
                group["status"] != "available"
                or not members
                or any(m["id"] in excluded for m in members)
            ):
                continue
            # One probability decision and native path search for the entire group.
            # Rigid translation preserves its formation instead of random walks
            # increasing the distance between companions on every cadence.
            if moved_member_count + len(members) > MAX_WANDER_BATCH_MOVED_MEMBERS:
                continue
            if random.random() >= configuration["move_probability"]:
                continue
            own_cells = {wander.point(member) for member in members}
            result = wander.plan_group_path(
                members,
                scoped,
                (),
                occupied=scope_occupied - own_cells,
                radius=configuration["radius"],
                min_steps=configuration["min_steps"],
                max_steps=configuration["max_steps"],
                indexed=indexed,
                destination_allowed=lambda cell: habitat_destination_allowed(
                    scope[0], scope[1], cell
                ),
            )
            if result is None:
                continue
            candidate = result["members"]
            packets = result["packets"]
            if packets:
                count = sum(
                    wander.point(before) != wander.point(after)
                    for before, after in zip(members, candidate)
                )
                group_packet_bytes = sum(len(payload) + 6 for _, payload in packets)
                if (
                    moved_member_count + count > MAX_WANDER_BATCH_MOVED_MEMBERS
                    or packet_bytes + group_packet_bytes > MAX_WANDER_BATCH_PACKET_BYTES
                ):
                    continue
                move = dict(
                    group_id=group["group_id"],
                    expected_members=members,
                    moved_members=candidate,
                    packets=[[opcode, payload.hex()] for opcode, payload in packets],
                )
                batch = dict(
                    kind="wander_bulk",
                    world_epoch=epoch,
                    scope=list(scope),
                    configuration=configuration,
                    moves=moves + [move],
                )
                if (
                    len(json.dumps(batch, separators=(",", ":")).encode("utf-8"))
                    > MAX_WANDER_BATCH_JSON_BYTES
                ):
                    continue
                moves.append(move)
                scope_occupied.difference_update(own_cells)
                scope_occupied.update(wander.point(member) for member in candidate)
                moved_member_count += count
                packet_bytes += group_packet_bytes
                if len(moves) >= MAX_WANDER_BATCH_GROUPS:
                    break
        if moves:
            proposals.append(
                dict(
                    kind="wander_bulk",
                    world_epoch=epoch,
                    scope=list(scope),
                    configuration=configuration,
                    moves=moves,
                )
            )
    return _pack_lifecycle(life_plans.resolve_noops(store, proposals + noops))


def _validate_bulk_wander_move(move):
    """Return decoded per-group movement data, or reject just this group."""
    from protocol_codec import decode_body

    if not isinstance(move, dict) or set(move) != {
        "group_id",
        "expected_members",
        "moved_members",
        "packets",
    }:
        raise ValueError("Invalid bulk wander group fields")
    group_id = move["group_id"]
    expected = move["expected_members"]
    moved = move["moved_members"]
    encoded_packets = move["packets"]
    if (
        type(group_id) is not int
        or not isinstance(expected, list)
        or not isinstance(moved, list)
        or not expected
        or len(expected) != len(moved)
        or not isinstance(encoded_packets, list)
        or not encoded_packets
    ):
        raise ValueError("Invalid bulk wander group roster")
    if any(
        not isinstance(member, dict) or type(member.get("id")) is not int
        for member in expected + moved
    ):
        raise ValueError("Invalid bulk wander actor identity")
    expected_ids = [member["id"] for member in expected]
    moved_ids = [member["id"] for member in moved]
    if len(set(expected_ids)) != len(expected_ids) or expected_ids != moved_ids:
        raise ValueError("Bulk wander changed group identity")
    moved_by_id = {member["id"]: member for member in moved}
    expected_by_id = {member["id"]: member for member in expected}
    changed_ids = {
        actor_id
        for actor_id, before in expected_by_id.items()
        if tuple(before.get(key) for key in ("x", "y", "z"))
        != tuple(moved_by_id[actor_id].get(key) for key in ("x", "y", "z"))
    }
    if not changed_ids or len(changed_ids) > MAX_WANDER_BATCH_MOVED_MEMBERS:
        raise ValueError("Invalid bulk wander moved-member count")
    packets = []
    packet_ids = set()
    packet_bytes = 0
    for packet in encoded_packets:
        if (
            not isinstance(packet, list)
            or len(packet) != 2
            or type(packet[0]) is not int
            or packet[0] != 13852
            or not isinstance(packet[1], str)
        ):
            raise ValueError("Invalid bulk wander movement packet")
        body = bytes.fromhex(packet[1])
        decoded = decode_body("in", packet[0], body)
        actor_id = decoded["actor_id"]
        if (
            actor_id not in changed_ids
            or actor_id in packet_ids
            or decoded["start_position"]
            != {key: expected_by_id[actor_id][key] for key in ("x", "y", "z")}
            or decoded["end_position"]
            != {key: moved_by_id[actor_id][key] for key in ("x", "y", "z")}
        ):
            raise ValueError("Bulk wander packet does not match its group CAS")
        packet_ids.add(actor_id)
        packet_bytes += len(body) + 6
        packets.append((packet[0], body))
    if packet_ids != changed_ids or packet_bytes > MAX_WANDER_BATCH_PACKET_BYTES:
        raise ValueError("Bulk wander packet set is incomplete or oversized")
    # Keep the existing path parser as the occupancy authority for every step.
    cells = _path_cells([[opcode, payload.hex()] for opcode, payload in packets])
    if not cells:
        raise ValueError("Bulk wander path is empty")
    return group_id, expected, moved, packets, cells, len(changed_ids), packet_bytes


def _apply_wander_bulk(store, groups, harvests, world, proposal, *, world_epoch):
    from . import monster_maturation as maturation
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
        expected_by_id = {member["id"]: member for member in decoded[1]}
        try:
            paths_by_actor = _path_cells_by_actor(
                [[opcode, payload.hex()] for opcode, payload in decoded[3]]
            )
            family_ids = {
                actor_id: maturation.STAGES[member["ref"]][0]["family_id"]
                if member["ref"] in maturation.STAGES
                else None
                for actor_id, member in expected_by_id.items()
            }
            habitat_valid = not any(
                not habitat_destination_allowed(
                    scope[0],
                    scope[1],
                    cell,
                    parent=expected_by_id[actor_id],
                    family_id=family_ids[actor_id],
                )
                for actor_id, path in paths_by_actor.items()
                for cell in path
            )
        except (KeyError, TypeError, ValueError):
            habitat_valid = False
        seen_group_ids.add(decoded[0])
        moved_members += decoded[5]
        packet_bytes += decoded[6]
        decoded_moves.append((*decoded, habitat_valid))

    with groups.lock, harvests.lock, getattr(world, "lock", nullcontext()):
        players = _scoped_players(world.snapshot(), tuple(scope))
        if not players:
            return {"status": "absent"}
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
            habitat_valid,
        ) in enumerate(decoded_moves):
            if time.monotonic() >= deadline:
                skipped_groups += len(decoded_moves) - index
                budget_exhausted = True
                break
            expected_ids = {member["id"] for member in expected}
            if expected_ids & excluded:
                skipped_groups += 1
                continue
            current_groups = groups.snapshot(*scope)
            current = next(
                (
                    group
                    for group in current_groups
                    if group.get("group_id", group.get("key", (None, None, None))[2])
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
            occupied = {wander.point(player) for player in players}
            occupied |= {
                wander.point(member)
                for group in current_groups
                if group["status"] != "defeated"
                for member in group["members"]
                if member["id"] not in expected_ids
            }
            if cells & occupied:
                skipped_groups += 1
                continue
            if not groups.move_members((*scope, group_id), expected, moved):
                skipped_groups += 1
                continue
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
                else "cas_or_guard"
                if skipped_groups
                else None
            ),
        }


def apply(store, groups, harvests, world, proposal, *, world_epoch):
    """Validate fresh live fences, commit CAS/receipts, then publish locally."""
    from . import monster_maturation as maturation
    from . import monster_reproduction as reproduction
    from . import monster_wander as wander
    from .combat_monster_world import remove_message, spawn_group

    if proposal["world_epoch"] != world_epoch:
        return {"status": "stale_epoch"}
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
    with groups.lock, harvests.lock, getattr(world, "lock", nullcontext()):
        players = _scoped_players(world.snapshot(), scope)
        if not players:
            return {"status": "absent"}
        excluded = set(harvests.targets)
        if any(m["id"] in excluded for m in proposal["expected_members"]):
            return {"status": "harvesting"}
        if kind == "wander" and not publication:
            current_groups = groups.snapshot(*scope)
            own_ids = {m["id"] for m in proposal["expected_members"]}
            occupied = {wander.point(p) for p in players}
            occupied |= {
                wander.point(m)
                for g in current_groups
                if g["status"] != "defeated"
                for m in g["members"]
                if m["id"] not in own_ids
            }
            if _path_cells(proposal["packets"]) & occupied:
                return {"status": "occupied"}
            if not groups.move_members(
                (*scope, proposal["group_id"]),
                proposal["expected_members"],
                proposal["moved_members"],
            ):
                return {"status": "stale_group"}
            for opcode, payload in proposal["packets"]:
                world.emit_location(*scope, opcode, bytes.fromhex(payload))
            return {"status": "applied"}
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
        # Re-read durable outbox and current group while claims remain fenced.
        for group_id in () if affected_group is None else (affected_group,):
            batch = domains[kind].unpublished(store, *scope, group_id=group_id)
            if not batch:
                continue
            current = batch[-1]
            if current["status"] != "available" or any(
                m["id"] in excluded for m in current["members"]
            ):
                continue
            world.emit_location(
                *scope, *remove_message([m["id"] for m in current["members"]])
            )
            world.emit_location(
                *scope, 12608, spawn_group(current["members"], group_id=group_id)
            )
            for event in batch:
                domains[kind].acknowledge(store, event)
        return {
            "status": "duplicate"
            if receipt is not None and receipt["duplicate"]
            else "applied"
        }


def _pack_lifecycle(proposals):
    """Bound lifecycle envelopes while preserving original operation order."""
    result = []
    for proposal in proposals:
        if proposal["kind"] not in ("maturation", "reproduction"):
            result.append(proposal)
            continue
        batch = (
            result[-1] if result and result[-1]["kind"] == "lifecycle_bulk" else None
        )
        if (
            batch is None
            or batch["scope"] != proposal["scope"]
            or len(batch["operations"]) >= 16
        ):
            batch = dict(
                kind="lifecycle_bulk",
                scope=proposal["scope"],
                world_epoch=proposal["world_epoch"],
                operations=[],
            )
            result.append(batch)
        candidate = dict(batch, operations=batch["operations"] + [proposal])
        if len(json.dumps(candidate, separators=(",", ":")).encode()) > 224 * 1024:
            batch = dict(
                kind="lifecycle_bulk",
                scope=proposal["scope"],
                world_epoch=proposal["world_epoch"],
                operations=[],
            )
            result.append(batch)
        batch["operations"].append(proposal)
    return result


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


def _proposal_slots(proposals):
    counts = {}
    other = 0
    for p in proposals:
        if p.get("noop"):
            continue
        if p["kind"] in ("maturation", "reproduction"):
            key = tuple(p["scope"])
            counts[key] = counts.get(key, 0) + 1
        else:
            other += 1
    return other + sum((count + 15) // 16 for count in counts.values())
