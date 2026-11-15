"""Locally reconstructed, owner-scoped line-of-sight training scene.

The actor used for rocks, their positions and their motion are local choices.
The installed client identifies the target spell but does not preserve the
original server's encounter constructor. These helpers are not enabled until
the dispatcher wires the complete fight, grants and quest settlement together.
"""

from collections import deque
from itertools import combinations

from .rii_owned_lesson import Lesson

LOS = Lesson("rii-los-sack:", "reconstructed_rii_los_sack", 5466, 10608, 10576)
ROCK_REFERENCE = 4528
ROCKS = 3
ROCK_KEY = "rii-los-rock:"


def rock_payload(owner, actor, sack):
    if (
        type(owner) is not int
        or owner <= 0
        or type(actor) is not int
        or actor >= 0
        or type(sack) is not int
        or sack >= 0
        or actor == sack
    ):
        raise ValueError("Invalid line-of-sight rock identity")
    return {
        "kind": "reconstructed_rii_los_rock",
        "owner": owner,
        "actor_id": actor,
        "sack_id": sack,
        "ref": ROCK_REFERENCE,
    }


def bind(db, owner, monsters):
    """Bind the sack and all rocks only to their durable common owner."""
    if len(monsters) == 1:
        from .rii_los_native import bind as bind_native

        return bind_native(db, owner, monsters)
    from .rii_owned_lesson import bind as bind_sack

    contract = bind_sack(db, LOS, owner, monsters)
    if contract is None:
        return None
    rocks = [m["id"] for m in monsters if m.get("ref") == ROCK_REFERENCE]
    if (
        len(rocks) != ROCKS
        or len(set(rocks)) != ROCKS
        or any(type(identity) is not int or identity >= 0 for identity in rocks)
    ):
        raise ValueError("Line-of-sight encounter must contain its own rocks")
    for actor in rocks:
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (owner, ROCK_KEY + str(-actor)),
        ).fetchone()
        if not row or row["payload"] != rock_payload(owner, actor, contract["target"]):
            raise ValueError("Line-of-sight rock ownership does not match its sack")
    contract["rocks"] = sorted(rocks)
    return contract


def admit(db, owner, monsters):
    """Deny reuse of any receipted lesson actor by another character."""
    from .rii_owned_lesson import admit as admit_sack

    admit_sack(db, LOS, owner, monsters)
    for monster in monsters:
        actor = monster.get("id")
        if monster.get("ref") != ROCK_REFERENCE or type(actor) is not int or actor >= 0:
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (ROCK_KEY + str(-actor),),
        ).fetchall()
        for row in rows:
            payload = row["payload"]
            if (
                isinstance(payload, dict)
                and payload.get("kind") == "reconstructed_rii_los_rock"
                and payload.get("actor_id") == actor
                and payload.get("ref") == ROCK_REFERENCE
                and row["character_id"] != owner
            ):
                raise ValueError("This training rock belongs to another player")
    return True


def initialize(fight, packets, *, action_id):
    """Grant only the owner the installed native line-of-sight spell."""
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return True
    if contract is None:
        return False
    if (
        not isinstance(contract, dict)
        or fight.phase != "active"
        or contract.get("initialized") is not None
    ):
        raise ValueError("Invalid line-of-sight lesson start")
    owner, target = contract.get("owner"), contract.get("target")
    if (
        owner not in fight.actors
        or target not in fight.actors
        or fight.actors[owner].team == fight.actors[target].team
    ):
        raise ValueError("Invalid line-of-sight lesson participants")
    if contract.get("native_los_areas") is True:
        # The original 8003 carrier installs morphology 5521 and its 7968
        # spell. The native area engine owns obstacles and their lifecycle.
        contract["initialized"] = True
        return True
    ensure_initial_shot(fight, packets, action_id=action_id)
    from wakfu_server.rii_lesson_grants import install
    from wakfu_server.ecology_feedback import information

    contract["grant_uids"] = install(
        fight,
        owner,
        packets,
        action_id=action_id,
        allocate_uid=fight.allocate_effect_uid,
        lesson="los",
    )
    contract["initialized"] = True
    packets.append(
        information(
            "Hit the sack from at least 4 cells away with a clear line of sight."
        )
    )
    return True


def hit(
    fight, *, source_id, target_id, effect_reference, damage, actor_authority, spell_id
):
    """Qualify this hit using the current fight's real native casting ray."""
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if not isinstance(contract, dict) or target_id != contract.get("target"):
        return None
    if contract.get("native_los_areas") is True:
        # Preserve actual native damage, healing and win resolution. In the
        # official fight the 8005 sack heals, so four hits are not a win rule.
        return None
    from .lesson_line_of_sight import DAMAGE_EFFECT, SPELL, observe

    if (
        spell_id != SPELL
        or effect_reference != DAMAGE_EFFECT
        or source_id != contract.get("owner")
        or damage <= 0
    ):
        return 0
    actor, target = fight.actors.get(source_id), fight.actors.get(target_id)
    if actor is None or target is None or actor_authority is None:
        raise ValueError("Missing line-of-sight lesson authority")
    from wakfu_server.combat_casting_los import native_casting_los

    los = native_casting_los(fight, actor_authority, source_id, target.position, target)
    previous = {"hits": contract.get("hits", 0)}
    after = observe(
        previous,
        owner_id=contract["owner"],
        target_id=target_id,
        source_id=source_id,
        hit_target_id=target_id,
        spell_id=SPELL,
        effect_reference=effect_reference,
        source_xy=actor.position[:2],
        target_xy=target.position[:2],
        damage=damage,
        casting_los=los,
    )
    contract.update(after)
    return 25 if after["hits"] > previous["hits"] else 0


class _ConservativeFormationAuthority:
    """Treat every indexed actor as a LOS blocker when planning a lesson."""

    def __call__(self, fight, actor):
        from types import SimpleNamespace

        return SimpleNamespace(native_instance_id=1388)

    def properties(self, fight, actor):
        return frozenset({6})


def ensure_initial_shot(fight, packets, *, action_id):
    """Validate actual placement; relocate owned rocks if it obstructs play."""
    from wakfu_server.combat_qi_fight import move_registered_actor
    from wakfu_server.combat_movement import hour_movement

    authority = _ConservativeFormationAuthority()
    if has_reachable_native_shot(fight, authority):
        return True
    contract = fight.rii_los_lesson_contract
    owner, target = fight.actors[contract["owner"]], fight.actors[contract["target"]]
    occupied = {
        tuple(actor.position) for actor in fight.actors.values() if actor.hp > 0
    }
    free = set(map(tuple, fight.walkable)) - occupied
    candidates = sorted(
        free,
        key=lambda p: (
            -(
                abs(p[0] - owner.position[0])
                + abs(p[1] - owner.position[1])
                + abs(p[0] - target.position[0])
                + abs(p[1] - target.position[1])
            ),
            p,
        ),
    )
    # Usually one obstruction is sufficient. Try a bounded deterministic set,
    # preserving all other actors and restoring every rejected QI update.
    for identity in contract.get("rocks", ()):
        actor = fight.actors[identity]
        origin = tuple(actor.position)
        for destination in candidates[:24]:
            move_registered_actor(fight, actor, destination)
            if has_reachable_native_shot(fight, authority):
                fight._event(
                    "movement",
                    actor_id=identity,
                    path=[destination],
                    cost=0,
                    reconstructed_los_rock=True,
                )
                packets.append(
                    hour_movement(
                        fight.id,
                        action_id,
                        identity,
                        origin,
                        destination,
                        actor.direction,
                    )
                )
                return True
            move_registered_actor(fight, actor, origin)
    raise ValueError("Line-of-sight training formation has no reachable clear shot")


def has_reachable_native_shot(fight, actor_authority):
    """Use native terrain and QI blockers to find a legal reachable cast cell."""
    from wakfu_server.combat_casting_eligibility import native_casting_distance
    from wakfu_server.combat_casting_los import native_casting_ray

    contract = fight.rii_los_lesson_contract
    owner, target = fight.actors[contract["owner"]], fight.actors[contract["target"]]
    metadata = actor_authority(fight, owner)
    ignored = tuple(fight.native_qi_visibility_ignored_slots) + (
        owner.native_obstacle_id,
    )
    occupied = {
        tuple(actor.position)
        for actor in fight.actors.values()
        if actor.hp > 0 and actor.id != owner.id
    }
    outgoing = {}
    for start, end in fight.edges:
        outgoing.setdefault(tuple(start), []).append(tuple(end))
    origin = tuple(owner.position)
    seen, queue = {origin}, deque([origin])
    while queue:
        position = queue.popleft()
        distance = native_casting_distance(position[:2], target.position[:2])
        if 4 <= distance <= 16 and native_casting_ray(
            fight,
            actor_authority,
            metadata.native_instance_id,
            position,
            target.position,
            source_height=owner.native_los_height,
            target_height=target.native_los_height,
            ignored_slots=ignored,
        ):
            return True
        for neighbor in outgoing.get(position, ()):
            if neighbor not in seen and neighbor not in occupied:
                seen.add(neighbor)
                queue.append(neighbor)
    return False


def move_one_rock(fight, packets, *, action_id, actor_authority=None):
    """Reposition one owned rock using the native QI registry and wire action.

    Rock identity and movement policy are a local reconstruction. This runs
    only within a transactional spell preview after a qualifying hit.
    """
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_los_areas") is True:
        return False
    if not isinstance(contract, dict) or contract.get("hits", 0) >= 4:
        return False
    rock_ids = contract.get("rocks")
    if (
        not isinstance(rock_ids, (list, tuple))
        or len(rock_ids) != ROCKS
        or len(set(rock_ids)) != ROCKS
        or any(type(identity) is not int or identity >= 0 for identity in rock_ids)
    ):
        raise ValueError("Missing owned line-of-sight rock identities")
    rocks = {
        identity: tuple(fight.actors[identity].position)
        for identity in rock_ids
        if identity in fight.actors and fight.actors[identity].hp > 0
    }
    if fight.edges is None:
        raise ValueError("Missing line-of-sight rock geometry")
    # Other legal spells can defeat the native rock actors. Their absence must
    # not prevent the owner from finishing the lesson after a valid hit.
    if not rocks:
        return False
    occupied = {
        tuple(actor.position) for actor in fight.actors.values() if actor.hp > 0
    }
    owner = fight.actors.get(contract.get("owner"))
    if owner is None or owner.hp <= 0:
        raise ValueError("Missing live line-of-sight lesson owner")
    step = next_rock_step(
        rocks,
        fight.walkable,
        fight.edges,
        occupied,
        contract.get("hits", 0),
        protected_position=owner.position,
    )
    if step is None:
        return False
    identity, origin, destination = step
    actor = fight.actors[identity]
    from wakfu_server.combat_qi_fight import move_registered_actor
    from wakfu_server.combat_movement import hour_movement

    move_registered_actor(fight, actor, destination)
    if actor_authority is not None and not has_reachable_native_shot(
        fight, actor_authority
    ):
        move_registered_actor(fight, actor, origin)
        return False
    fight._event(
        "movement",
        actor_id=identity,
        path=[destination],
        cost=0,
        reconstructed_los_rock=True,
    )
    packets.append(
        hour_movement(
            fight.id, action_id, identity, origin, destination, actor.direction
        )
    )
    return True


def finish_if_qualified(fight):
    """End the owned lesson after four hits, leaving rock actors alive."""
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_los_areas") is True:
        return False
    if (
        fight.phase != "active"
        or not isinstance(contract, dict)
        or contract.get("hits") != 4
    ):
        return False
    owner, target = fight.actors.get(contract.get("owner")), fight.actors.get(
        contract.get("target")
    )
    if owner is None or target is None or owner.hp <= 0 or owner.team == target.team:
        return False
    fight.phase = "finished"
    fight.winner = owner.team
    fight._event("finished", winner=owner.team)
    return True


def scene_cells(graph, origin, occupied, *, rock_count=ROCKS, shot_is_clear=None):
    """Pick distinct reachable cells for a target and temporary rock actors.

    A bounded breadth-first walk keeps the reconstructed scene near Airyna.
    Existing actors and the player remain untouched; insufficient geometry
    fails closed rather than inventing walkable coordinates.
    """
    if (
        type(rock_count) is not int
        or not 1 <= rock_count <= 12
        or not isinstance(origin, tuple)
        or len(origin) != 3
    ):
        raise ValueError("Invalid line-of-sight scene request")
    occupied = set(map(tuple, occupied)) | {origin}
    seen, queue, target, rocks = {origin}, deque([(origin, 0)]), None, []

    def has_firing_position(selected):
        from wakfu_server.combat_casting_eligibility import native_casting_distance

        blocked = occupied | {target, *selected}
        reachable, pending = {origin}, deque([origin])
        while pending:
            cell = pending.popleft()
            distance = native_casting_distance(cell[:2], target[:2])
            if 4 <= distance <= 16 and (
                shot_is_clear is None or shot_is_clear(cell, target, selected)
            ):
                return True
            for neighbor in map(tuple, graph.get(cell, ())):
                if neighbor not in blocked and neighbor not in reachable:
                    reachable.add(neighbor)
                    pending.append(neighbor)
        return False

    while queue:
        cell, depth = queue.popleft()
        if cell not in occupied:
            if target is None and depth == 1:
                target = cell
            elif depth >= 2:
                rocks.append(cell)
            if target is not None and len(rocks) >= rock_count:
                # A reachable exit next to the starting cell is essential:
                # the native lesson spell requires at least four cells.
                exits = {tuple(candidate) for candidate in graph.get(origin, ())}
                if not exits - occupied - {target}:
                    break
                # Try a bounded, deterministic set of layouts: the stones
                # must not isolate the actor before the first legal cast.
                for selected in combinations(rocks[-8:], rock_count):
                    if has_firing_position(selected):
                        return (target, *selected)
        if depth >= 4:
            continue
        for candidate in sorted(map(tuple, graph.get(cell, ()))):
            if len(candidate) != 3 or candidate in seen or candidate in occupied:
                continue
            seen.add(candidate)
            queue.append((candidate, depth + 1))
    raise ValueError("Insufficient native geometry for line-of-sight lesson")


def native_scene_shot(map_id, source_height, target_height):
    """Build a native static-ray predicate accounting for proposed rocks."""
    from wakfu_server.combat_native_los_ray import cast_rays

    def clear(source, target, rocks):
        rock_cells = {tuple(rock[:2]) for rock in rocks}
        return any(
            static_clear and not rock_cells.intersection(probes)
            for static_clear, probes in cast_rays(
                map_id,
                source,
                target,
                source_height=source_height,
                target_height=target_height,
            )
        )

    return clear


def next_rock_step(
    rocks, walkable, edges, occupied, hit_index, *, protected_position=None
):
    """Pick one legal, unoccupied neighbor for a server-owned rock.

    This is a local movement policy, not recovered original rock placements.
    The caller must move the real QI actor and publish the corresponding
    movement action in the same combat preview. Return None when no rock has
    a legal neighbor; never fabricate terrain or move an unrelated actor.
    """
    if (
        not isinstance(rocks, dict)
        or not rocks
        or type(hit_index) is not int
        or hit_index < 0
        or any(
            type(identity) is not int
            or identity >= 0
            or not isinstance(cell, tuple)
            or len(cell) != 3
            for identity, cell in rocks.items()
        )
    ):
        raise ValueError("Invalid line-of-sight rock snapshot")
    free = set(map(tuple, walkable)) - set(map(tuple, occupied))
    ids = sorted(rocks)
    start = hit_index % len(ids)
    for index in range(len(ids)):
        identity = ids[(start + index) % len(ids)]
        origin = rocks[identity]
        possible = sorted(
            destination
            for source, destination in edges
            if tuple(source) == origin and tuple(destination) in free
        )
        if protected_position is not None:
            protected = tuple(protected_position)
            exits = {
                tuple(destination)
                for source, destination in edges
                if tuple(source) == protected
            }
            # Moving a rock frees its origin. Never block the owner's last
            # traversable neighbor when presenting the next challenge.
            free_after_departure = free | {origin}
            possible = [
                destination
                for destination in possible
                if exits & (free_after_departure - {tuple(destination)})
            ]
        if possible:
            return identity, origin, tuple(possible[hit_index % len(possible)])
    return None


def spawn(store, groups, account_id, generation, character, *, repeat=False):
    """Start the native roster; retain the historical path as an explicit fallback."""
    import os

    if os.environ.get("WAKFU_RII_NATIVE_LOS_ENABLED", "1") == "1":
        from .rii_los_native import spawn as spawn_native

        return spawn_native(
            store, groups, account_id, generation, character, repeat=repeat
        )
    return _spawn_legacy(store, groups, account_id, generation, character)


def _spawn_legacy(store, groups, account_id, generation, character):
    """Historical three-actor reconstruction, retained for existing receipts."""
    import secrets

    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.combat_monster_world import spawn_group
    from . import storage
    from .rii_owned_lesson import payload

    if (character.get("map_id"), character.get("instance_id")) != (1388, 0):
        return None
    origin = tuple(character[k] for k in ("x", "y", "z"))
    with groups.lock, store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if tuple(current[k] for k in ("map_id", "instance_id", "x", "y", "z")) != (
            1388,
            0,
            *origin,
        ):
            raise ValueError("Line-of-sight lesson position changed")
        state = storage.load_locked(db, current["id"])
        if (
            5143 not in state["running"]
            or LOS.prerequisite not in state["objectives"]
            or LOS.objective in state["objectives"]
        ):
            return None
        present = groups.available(1388, 0)
        for group in present:
            members = group["members"]
            if bind(db, current["id"], members) is None:
                continue
            # Keep a previously defeated or abandoned owned lesson reachable
            # instead of returning the player to Airyna's elevated platform.
            from .rii_training_arena import mark_setup_ready_in_transaction

            mark_setup_ready_in_transaction(db, character, LOS.objective)
            return 12608, spawn_group(members, group_id=group["key"][2])
        occupied = {
            tuple(m[k] for k in ("x", "y", "z"))
            for group in present
            for m in group["members"]
        }
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        actor_catalog = native_actor_catalog()
        source_height = actor_catalog.get("default_actor_los_height")
        target_height = actor_catalog["npc_profiles"][str(LOS.reference)].get(
            "native_los_height"
        )
        if type(source_height) is not int or type(target_height) is not int:
            raise ValueError("Missing native line-of-sight heights")
        cells = scene_cells(
            published_geometry(1388).outgoing,
            origin,
            occupied,
            shot_is_clear=native_scene_shot(1388, source_height, target_height),
        )
        # Allocate each actor through the existing globally owned UID service.
        actors = [-allocate_block(db, 1) for _ in cells]
        members = [
            owned_instance(
                LOS.reference if index == 0 else ROCK_REFERENCE,
                1,
                actor,
                map_id=1388,
                instance_id=0,
                x=cell[0],
                y=cell[1],
                z=cell[2],
            )
            for index, (actor, cell) in enumerate(zip(actors, cells))
        ]
        if not storage.record_event(
            db,
            current["id"],
            LOS.key + str(-actors[0]),
            payload(LOS, current["id"], actors[0]),
        ):
            raise ValueError("Duplicate line-of-sight encounter receipt")
        for actor in actors[1:]:
            if not storage.record_event(
                db,
                current["id"],
                ROCK_KEY + str(-actor),
                rock_payload(current["id"], actor, actors[0]),
            ):
                raise ValueError("Duplicate line-of-sight rock receipt")
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1388, 0, group_id, members)
        # The serialized scene and transit readiness commit with this group.
        # A crash therefore leaves either a usable owned group or a receipt
        # still marked for safe return, never an orphaned prepared group.
        scene = 12608, spawn_group(members, group_id=group_id)
        from .rii_training_arena import mark_setup_ready_in_transaction

        mark_setup_ready_in_transaction(db, character, LOS.objective)
    return scene
