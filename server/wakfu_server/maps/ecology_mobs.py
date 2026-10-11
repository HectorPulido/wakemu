"""External monster simulation planning with short world-owned commit fences.

Proposals are internal service messages, never client-supplied authority. The
worker and world use the same pinned catalog release. SQL receipts remain the
idempotency authority; publication is performed only by world.
"""
from copy import deepcopy
from functools import lru_cache
import random
import secrets


@lru_cache(maxsize=16)
def _edges(map_id):
    from .combat_terrain import map_geometry
    from .monster_wander import edge_index

    return edge_index(map_geometry(map_id)["edges"])


def _sample():
    return secrets.randbelow(1 << 53) / (1 << 53)


def _scoped_players(players, scope):
    return [p for p in players if (p["map_id"], p.get("instance_id", 0)) == scope]


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


def prepare(store, snapshot, limit=16):
    """Run geometry, native construction and policy decisions outside world."""
    from . import monster_maturation as maturation
    from . import monster_reproduction as reproduction
    from . import monster_wander as wander
    from .monsters import owned_instance
    from .combat_monster_world import spawn_group

    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid ecology proposal limit")
    epoch = snapshot["world_epoch"]
    if type(epoch) is not str or not epoch:
        raise ValueError("Missing ecology world epoch")
    players = snapshot["players"]
    excluded = set(snapshot["excluded_ids"])
    locations = {tuple(scope) for scope in snapshot["locations"]}
    locations &= {(p["map_id"], p.get("instance_id", 0)) for p in players}
    proposals = []
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
                now_ms=snapshot["now_ms"]
            )
    for scope in sorted(locations):
        if reproduction.dungeon_population(store, scope[1]):
            continue
        scoped = _scoped_players(players, scope)
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
        for domain_name, domain in (
            ("maturation", maturation),
            ("reproduction", reproduction),
        ):
            for group_id in dict.fromkeys(
                e["group_id"] for e in domain.unpublished(store, *scope)
            ):
                if len(proposals) >= limit:
                    return proposals
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
        for kind, domain in (
            ("maturation", maturation),
            ("reproduction", reproduction),
        ):
            domain.observe(
                store,
                *scope,
                present=True,
                generation=epoch,
                now_ms=snapshot["now_ms"],
                excluded_ids=excluded,
                configuration=policies[kind]
            )
            for ticket in domain.pending(store, *scope):
                if len(proposals) >= limit:
                    return proposals
                group = by_id.get(ticket["group_id"])
                if (
                    group is None
                    or group["status"] != "available"
                    or ticket["monster_id"] in excluded
                ):
                    continue
                members = list(group["members"])
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
                    configuration=policies[kind],
                    expected_members=deepcopy(members),
                    draw=_sample(),
                )
                if kind == "maturation":
                    candidate = maturation.choose_next(
                        parent["ref"], policies[kind], draw=proposal["draw"]
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
                            **{k: parent[k] for k in ("x", "y", "z")}
                        )
                    )
                    proposal["grown"] = grown
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
                    ]
                    if not candidates:
                        continue
                    destination = secrets.choice(candidates)
                    proposal.update(
                        destination=list(destination), group_draw=_sample(), child=None
                    )
                    if proposal["draw"] < reproduction.birth_probability(
                        parent["ref"], policies[kind]
                    ):
                        stage = maturation.STAGES[parent["ref"]]
                        candidate = secrets.choice(stage[0]["tiers"][0]["candidates"])
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
        for group in groups if snapshot.get("allow_wander", True) else ():
            if len(proposals) >= limit:
                return proposals
            members = list(group["members"])
            if group["status"] != "available" or any(
                m["id"] in excluded for m in members
            ):
                continue
            candidate = deepcopy(members)
            packets = []
            for i, member in enumerate(candidate):
                if random.random() >= configuration["move_probability"]:
                    continue
                blocked = {
                    wander.point(m)
                    for g in groups
                    for m in g["members"]
                    if m["id"] != member["id"]
                }
                blocked |= {
                    wander.point(m) for m in candidate if m["id"] != member["id"]
                }
                result = wander.plan_path(
                    [member],
                    scoped,
                    (),
                    occupied=blocked,
                    radius=configuration["radius"],
                    min_steps=configuration["min_steps"],
                    max_steps=configuration["max_steps"],
                    indexed=indexed,
                )
                if result is not None:
                    candidate[i] = result["members"][0]
                    packets.extend(result["packets"])
            if packets:
                proposals.append(
                    dict(
                        kind="wander",
                        world_epoch=epoch,
                        scope=list(scope),
                        group_id=group["group_id"],
                        expected_members=members,
                        moved_members=candidate,
                        packets=[
                            [opcode, payload.hex()] for opcode, payload in packets
                        ],
                        configuration=configuration,
                    )
                )
    return proposals


def apply(store, groups, harvests, world, proposal, *, world_epoch):
    """Validate fresh live fences, commit CAS/receipts, then publish locally."""
    from . import monster_maturation as maturation
    from . import monster_reproduction as reproduction
    from . import monster_wander as wander
    from .combat_monster_world import remove_message, spawn_group

    if proposal["world_epoch"] != world_epoch:
        return {"status": "stale_epoch"}
    publication = proposal["kind"].startswith("publish_")
    kind = proposal["kind"][8:] if publication else proposal["kind"]
    domains = dict(maturation=maturation, reproduction=reproduction, wander=wander)
    if kind not in domains or (publication and kind == "wander"):
        raise ValueError("Unknown monster ecology proposal")
    # Policy IO occurs before live registry locks; the received plan must match.
    if not publication and domains[kind].policy(store) != proposal["configuration"]:
        return {"status": "stale_policy"}
    scope = tuple(proposal["scope"])
    with groups.lock, harvests.lock:
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
                    indexed=None, players=players, group_draw=proposal["group_draw"]
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
