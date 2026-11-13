"""Owned Rii displacement training, reconstructed from the client and guide.

The original marker selection and fight script were not recovered.  A valid
native displacement into the server-selected marked cell counts once; all
mutations belong to the caller's fight preview and are discarded on rollback.
"""

EFFECTS = frozenset({367262, 367263, 367264, 367265, 367383})
REQUIRED_HITS = 4


def _native_plan_valid(fight, owner, target, marker, stand, *, require_swap=False):
    """Read the fight's actual QI, surfaces and native sight before choosing.

    The plan teleports the owner to ``stand`` if necessary, then pushes or
    pulls the sack by one cell. Nothing is moved by this check.
    """
    from wakfu_server.combat_casting_los import native_casting_ray
    from wakfu_server.combat_displacement import NativeDisplacementHandler
    from wakfu_server.combat_forced_terrain import next_surface
    from wakfu_server.combat_ordinary_authority import native_property_catalog

    provenance = getattr(fight, "native_qi_surface_provenance", None)
    map_id = provenance.get("map_id") if isinstance(provenance, dict) else None
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Movement lesson needs native QI surface authority")
    ignored = getattr(fight, "native_qi_visibility_ignored_slots", None)
    if not isinstance(ignored, list):
        raise ValueError("Movement lesson needs native visibility exclusions")

    class Visibility:
        def properties(self, current, actor):
            live = getattr(actor, "native_fight_properties", None)
            if live is not None:
                return frozenset(live)
            catalog = native_property_catalog()
            if actor.controlled:
                return frozenset(catalog["player"]["fight_properties"])
            if actor.id == target.id:
                return frozenset(catalog["npc"]["5466"]["fight_properties"])
            raise ValueError("Unknown movement lesson visibility actor")

    handler = NativeDisplacementHandler(
        fight, [], action_id=0, allocate_uid=lambda: None, authority=None
    )
    if (
        next_surface(
            map_id,
            target.native_los_height,
            tuple(target.position),
            marker[:2],
            radius=target.physical_radius,
            jump=4,
        )
        != marker
    ):
        return False
    blocked, _ = handler._forced_obstruction(
        target, (marker[0], marker[1], target.position[2])
    )
    if blocked:
        return False
    ignore_owner = tuple((*ignored, owner.native_obstacle_id))
    if tuple(stand) != tuple(owner.position):
        if handler._selected_surface(stand) is None or not handler._teleport_free(
            owner, stand
        ):
            return False
        if not native_casting_ray(
            fight,
            Visibility(),
            map_id,
            owner.position,
            stand,
            source_height=owner.native_los_height,
            target_height=0,
            ignored_slots=ignore_owner,
        ):
            return False
    if not native_casting_ray(
        fight,
        Visibility(),
        map_id,
        stand,
        target.position,
        source_height=owner.native_los_height,
        target_height=target.native_los_height,
        ignored_slots=ignore_owner,
    ):
        return False
    if require_swap:
        # The next marker is the owner's cell, so transposition must be legal
        # after this planned move. Ignore the sack's *old* registered QK: it
        # will occupy `marker` after this displacement.
        if abs(stand[0] - marker[0]) + abs(stand[1] - marker[1]) > 6:
            return False
        return native_casting_ray(
            fight,
            Visibility(),
            map_id,
            stand,
            marker,
            source_height=owner.native_los_height,
            target_height=target.native_los_height,
            ignored_slots=(*ignore_owner, target.native_obstacle_id),
        )
    return True


def choose_cell(fight, target, owner, *, previous=None, require_swap=False):
    """Choose a target with a free, reachable caster cell for push or pull."""
    x, y, z = target.position
    occupied = {
        tuple(actor.position)
        for actor in fight.actors.values()
        if actor.hp > 0 and actor.id != owner.id
    }
    obstacles = getattr(fight, "native_obstacle_cells", None) or ()
    edges = getattr(fight, "edges", None)
    candidates = []
    for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
        cell = (x + dx, y + dy, z)
        if (
            cell not in fight.walkable
            or cell in occupied
            or cell in obstacles
            or cell == previous
            or cell == tuple(owner.position)
        ):
            continue
        if edges is not None and (tuple(target.position), cell) not in edges:
            continue
        # Push from behind, or pull from beyond the new sack location.  A
        # caster with zero MP can use the temporary 7974 teleport (range 4).
        positions = ((x - dx, y - dy, z), (x + 2 * dx, y + 2 * dy, z))
        if any(
            pos in fight.walkable
            and pos not in occupied
            and pos not in obstacles
            and abs(pos[0] - owner.position[0]) + abs(pos[1] - owner.position[1]) <= 4
            and _native_plan_valid(
                fight, owner, target, cell, pos, require_swap=require_swap
            )
            for pos in positions
        ):
            candidates.append(cell)
    if not candidates:
        raise ValueError("No available displacement training marker")
    return tuple(sorted(candidates)[0])


def initialize(fight, packets, *, action_id):
    """Install four temporary movement spells and publish the first marker."""
    contract = getattr(fight, "rii_movement_lesson_contract", None)
    if contract is None:
        return False
    if (
        not isinstance(contract, dict)
        or fight.phase != "active"
        or contract.get("initialized") is not None
    ):
        raise ValueError("Invalid movement lesson start")
    owner, target = fight.actors.get(contract.get("owner")), fight.actors.get(
        contract.get("target")
    )
    if owner is None or target is None or owner.team == target.team:
        raise ValueError("Invalid movement lesson participants")
    from wakfu_server.rii_lesson_grants import install

    contract["grant_uids"] = install(
        fight,
        owner.id,
        packets,
        action_id=action_id,
        allocate_uid=fight.allocate_effect_uid,
        lesson="movement",
    )
    # This is scoped to the fight preview; the player's saved build is intact.
    from wakfu_server.combat_resource_pa_notifications import set_resource_maximum

    if getattr(owner, "effect_resource_raw_currents", None) is not None:
        set_resource_maximum(fight, owner, 3, 0)
    else:
        owner.max_mp = 0
        owner.mp = 0
        fight._sync_resources(owner)
    # The original 8011 producer is absent. Two independent native carriers
    # keep all four exercises available: sack level 3 admits push/pull and
    # teleport, while owner level 4 admits transposition. This lets the owner
    # reposition even if the final swap ray becomes obstructed.
    from .rii_lesson_state import install as install_state

    contract["state_uid"] = install_state(
        fight,
        owner_id=owner.id,
        target_id=target.id,
        reference=8011,
        level=3,
        action_id=action_id,
        packets=packets,
    )
    contract["owner_state_uid"] = install_state(
        fight,
        owner_id=owner.id,
        target_id=owner.id,
        reference=8011,
        level=4,
        action_id=action_id,
        packets=packets,
    )
    contract["marker"] = list(choose_cell(fight, target, owner))
    contract["initialized"] = True
    announce(fight, packets)
    return True


def announce(fight, packets, *, previous=None):
    """Identify the server-owned marker until native green-cell visuals are known."""
    from wakfu_server.ecology_feedback import information
    from wakfu_server.combat_tactical_markers import _marker_packet

    marker = fight.rii_movement_lesson_contract["marker"]
    owner = fight.rii_movement_lesson_contract["owner"]
    if previous is not None:
        packets.append(_marker_packet(fight.id, previous, owner, 0, False))
    packets.append(_marker_packet(fight.id, marker, owner, 0, True))
    packets.append(
        information(
            f"Movement lesson: move the sack to cell ({marker[0]}, {marker[1]})."
        )
    )


def observe(fight, *, caster_id, effect_reference, before, packets, action_id=0):
    """Count a qualified actual sack relocation onto its marked cell."""
    contract = getattr(fight, "rii_movement_lesson_contract", None)
    if not isinstance(contract, dict) or contract.get("initialized") is not True:
        return False
    if caster_id != contract.get("owner") or effect_reference not in EFFECTS:
        return False
    target = fight.actors.get(contract.get("target"))
    if target is None:
        return False
    hits = contract.get("hits")
    marker = contract.get("marker")
    if (
        type(hits) is not int
        or not 0 <= hits <= REQUIRED_HITS
        or not isinstance(marker, list)
        or len(marker) != 3
    ):
        raise ValueError("Invalid movement lesson state")
    if tuple(before) == tuple(target.position):
        if hits == REQUIRED_HITS - 1:
            owner = fight.actors.get(contract["owner"])
            if owner is not None and tuple(marker) != tuple(owner.position):
                contract["marker"] = list(owner.position)
                announce(fight, packets, previous=tuple(marker))
        return False
    if hits == REQUIRED_HITS or tuple(target.position) != tuple(marker):
        return False
    contract["hits"] = hits + 1
    if contract["hits"] < REQUIRED_HITS:
        owner = fight.actors[contract["owner"]]
        if contract["hits"] == REQUIRED_HITS - 1:
            # Native 7975 swaps the sack with the owner's occupied cell.
            contract["marker"] = list(owner.position)
        else:
            contract["marker"] = list(
                choose_cell(
                    fight,
                    target,
                    owner,
                    previous=tuple(marker),
                    require_swap=contract["hits"] == REQUIRED_HITS - 2,
                )
            )
        announce(fight, packets, previous=tuple(marker))
    else:
        from wakfu_server.combat_tactical_markers import _marker_packet

        packets.append(_marker_packet(fight.id, marker, contract["owner"], 0, False))
    return True


def finish_if_qualified(fight):
    """Finish after four committed qualifying moves, without a false sack death."""
    contract = getattr(fight, "rii_movement_lesson_contract", None)
    if (
        fight.phase != "active"
        or not isinstance(contract, dict)
        or contract.get("hits") != REQUIRED_HITS
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
