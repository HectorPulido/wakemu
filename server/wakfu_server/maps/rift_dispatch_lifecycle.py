"""Native rift arrival and roster preparation, independent from the dispatcher."""
from wakfu_server.rift_policy import select_wave
from collections import deque


def reachable_cells(geometry, anchor, quantity, *, occupied=()):
    """Traverse only exported native directed edges, without inferred neighbors."""
    anchor = tuple(anchor)
    cells = set(map(tuple, geometry["cells"]))
    if anchor not in cells or type(quantity) is not int or quantity <= 0:
        raise ValueError("Invalid rift formation anchor or capacity")
    edges = {}
    for start, end in geometry["edges"]:
        start, end = tuple(start), tuple(end)
        if start not in cells or end not in cells:
            raise ValueError("Rift native edge leaves its arena")
        edges.setdefault(start, set()).add(end)
    blocked = set(map(tuple, occupied)) | {anchor}
    queue, seen, selected = deque([anchor]), {anchor}, []
    while queue and len(selected) < quantity:
        for cell in sorted(edges.get(queue.popleft(), ())):
            if cell in seen:
                continue
            seen.add(cell)
            queue.append(cell)
            if cell not in blocked:
                selected.append(cell)
                if len(selected) == quantity:
                    break
    if len(selected) != quantity:
        raise ValueError("Rift arena lacks reachable free native cells")
    return tuple(selected)


def resolve_destination(db, catalog, members, geometry):
    """Choose a reachable native floor near the unique interior start activator.

    Geometry must come from the installed native asset map. This local arrival
    policy does not claim to recover an official spawn coordinate.
    """
    activators = [
        o
        for o in catalog["objects"]
        if o["type"] == "GenericActivableInteractiveElement"
        and o["map_id"] == catalog["map_id"]
    ]
    if len(activators) != 1 or not members:
        raise ValueError("Missing native rift start activator or party")
    obj = activators[0]
    cells = set(map(tuple, geometry["cells"]))
    for cell in sorted(
        cells,
        key=lambda c: (
            abs(c[0] - obj["x"]) + abs(c[1] - obj["y"]),
            abs(c[2] - obj["z"]),
            c,
        ),
    ):
        if len(members) > 1:
            try:
                reachable_cells(geometry, cell, len(members) - 1)
            except ValueError:
                continue
        return dict(map_id=catalog["map_id"], x=cell[0], y=cell[1], z=cell[2])
    raise ValueError("Rift has no verified walkable arrival formation")


def _members(db, run, wave, positions):
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.monsters import owned_instance, reference

    refs = select_wave(run["catalog"], run["policy"], run["seed"], wave)
    if len(positions) != len(refs):
        raise ValueError("Rift spawn formation differs from frozen roster")
    magnitude = allocate_block(db, len(refs))
    return tuple(
        owned_instance(
            ref,
            reference(ref)["min_level"],
            -(magnitude + index),
            map_id=run["catalog"]["map_id"],
            instance_id=run["instance_id"],
            x=cell[0],
            y=cell[1],
            z=cell[2],
            team=1,
        )
        for index, (ref, cell) in enumerate(zip(refs, positions))
    )


def initial_members(db, run, geometry, anchor, *, occupied=()):
    """Prepare verified native base-grade enemies with separated placement."""
    from wakfu_server.dungeon_encounters import enemy_formation

    if run["status"] != "entered":
        raise ValueError("Rift initial roster requires an entered run")
    refs = select_wave(run["catalog"], run["policy"], run["seed"], run["wave"])
    positions = enemy_formation(
        geometry,
        anchor,
        len(refs),
        occupied=occupied,
        player_slots=max(2, len(run["members"])),
    )
    return _members(db, run, run["wave"], positions)


def wave_members(db, run, wave, geometry, anchor, *, occupied=()):
    """Prepare fresh exact IDs on free reachable arena cells in the same fight."""
    if run["status"] != "running":
        raise ValueError("Rift wave admission requires a running fight")
    refs = select_wave(run["catalog"], run["policy"], run["seed"], wave)
    positions = reachable_cells(geometry, anchor, len(refs), occupied=occupied)
    return _members(db, run, wave, positions)


def disabled_rewards(db, run, result):
    """Explicit local reward authority; unknown official rewards never guessed."""
    row = db.execute(
        "SELECT value FROM settings WHERE name='rift_reward_policy'"
    ).fetchone()
    if row is None or row["value"] != {"kind": "disabled", "xp": 0, "kamas": 0}:
        raise ValueError("Unsupported rift reward policy; explicit authority required")
    return dict(xp=0, kamas=0, items=())


def reserve_actor_ids(db, quantity):
    """Preallocate exact native IDs; unused sequence values are never recycled."""
    from wakfu_server.npc_actor_identity import allocate_block, BLOCK_SIZE

    if type(quantity) is not int or not 1 <= quantity <= 16384:
        raise ValueError("Invalid rift actor reservation size")
    ids = []
    while len(ids) < quantity:
        count = min(BLOCK_SIZE, quantity - len(ids))
        start = allocate_block(db, count)
        ids.extend(-(start + i) for i in range(count))
    return tuple(ids)


def actor_reservation_shortfall(fight):
    """Return the next accepted wave's shortage without allocating identities."""
    state = getattr(fight, "rift_wave_state", None)
    if state is None or fight.phase != "active":
        return 0
    pending = state.get("pending_wave")
    if pending is None:
        return 0
    if not isinstance(pending, dict) or pending.get("completed_wave") != state.get(
        "wave"
    ):
        raise ValueError("Rift actor reservation requires its actual pending wave")
    pool = state.get("actor_id_pool")
    from wakfu_server.npc_actor_identity import lua_exact_identity

    if (
        not isinstance(pool, list)
        or len(set(pool)) != len(pool)
        or any(
            not lua_exact_identity(uid) or uid >= 0 or uid in fight.actors
            for uid in pool
        )
    ):
        raise ValueError("Invalid pending Rift actor reservation")
    references = select_wave(
        state["catalog"], state["policy"], state["seed"], pending["completed_wave"] + 1
    )
    return max(0, len(references) - len(pool))


def replenish_actor_ids(db, fight):
    """Reserve another ordinary block onto the caller's private candidate only.

    Sequence gaps after rejected previews are intentional: identities are never
    recycled. The normal accepted checkpoint persists only the adopted pool.
    """
    shortage = actor_reservation_shortfall(fight)
    if not shortage:
        return ()
    from wakfu_server.npc_actor_identity import BLOCK_SIZE

    fresh = reserve_actor_ids(db, max(BLOCK_SIZE, shortage))
    pool = fight.rift_wave_state["actor_id_pool"]
    if len(set(fresh)) != len(fresh) or set(fresh) & (set(pool) | set(fight.actors)):
        raise ValueError("Fresh Rift reservation conflicts with an existing actor")
    fight.rift_wave_state["actor_id_pool"] = pool + list(fresh)
    return fresh


def next_roster(fight, pending):
    """Pure accepted-action provider using a caller-reserved actor-ID pool.

    Frozen catalog/policy/seed and unused identities live in the checkpoint.
    The caller may replenish the pool transactionally before it is exhausted;
    this provider never queries a database or publishes packets.
    """
    from wakfu_server.monsters import owned_instance, reference
    from wakfu_server.npc_actor_identity import lua_exact_identity

    state = fight.rift_wave_state
    wave = pending["completed_wave"] + 1
    refs = select_wave(state["catalog"], state["policy"], state["seed"], wave)
    pool = state.get("actor_id_pool", [])
    if not isinstance(pool, list) or len(pool) < len(refs):
        raise ValueError("Rift actor ID reservation requires replenishment")
    identities = pool[: len(refs)]
    if len(set(identities)) != len(identities) or any(
        not lua_exact_identity(uid) or uid >= 0 or uid in fight.actors
        for uid in identities
    ):
        raise ValueError("Invalid reserved rift actor identity")
    from wakfu_server.combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    players = sorted(
        (
            a
            for a in fight.actors.values()
            if a.team == roles.player_team and fight._in_play(a)
        ),
        key=lambda a: a.id,
    )
    if not players or fight.edges is None:
        raise ValueError("Missing live player or native rift arena edges")
    from wakfu_server.rift_reinforcement_placement import select_positions

    positions = select_positions(fight, references=refs, seed=state["seed"], wave=wave)
    members = tuple(
        owned_instance(
            ref,
            reference(ref)["min_level"],
            uid,
            map_id=state["catalog"]["map_id"],
            instance_id=state["instance_id"],
            x=cell[0],
            y=cell[1],
            z=cell[2],
            team=1,
        )
        for ref, uid, cell in zip(refs, identities, positions)
    )
    state["actor_id_pool"] = pool[len(refs) :]
    return members
