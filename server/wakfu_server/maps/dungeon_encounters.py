"""Build dungeon room groups from frozen rosters and native walkable geometry.

Room anchors and grade selection are authoritative inputs. This adapter never
interprets a guide screenshot as coordinates or conflates an asset with a run.
"""
from collections import deque
from .dungeon_capacity import MAX_DUNGEON_MONSTERS

from wakfu_server.monsters import owned_instance, reference


def reachable_cells(geometry, anchor, quantity, *, occupied=()):
    """Use the same reachable-neighbor policy as the local monster console."""
    anchor = tuple(anchor)
    cells = {tuple(cell) for cell in geometry["cells"]}
    if anchor not in cells or type(quantity) is not int or quantity <= 0:
        raise ValueError("Invalid dungeon room anchor or quantity")
    blocked = {tuple(cell) for cell in occupied} | {anchor}
    edges = {}
    for start, end in geometry["edges"]:
        start, end = tuple(start), tuple(end)
        if start not in cells or end not in cells:
            raise ValueError("Native edge leaves walkable geometry")
        edges.setdefault(start, set()).add(end)
    queue, seen, selected = deque([anchor]), {anchor}, []
    while queue and len(selected) < quantity:
        for neighbor in sorted(edges.get(queue.popleft(), ())):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append(neighbor)
            if neighbor not in blocked:
                selected.append(neighbor)
                if len(selected) == quantity:
                    break
    if len(selected) != quantity:
        raise ValueError("Dungeon room lacks reachable free native cells")
    return tuple(selected)


def enemy_formation(geometry, anchor, quantity, *, occupied=(), player_slots=6):
    """Separate NPC seeds from a reachable party formation on native terrain."""
    from wakfu_server.combat_placement_cells import generate
    from wakfu_server.combat_arena_selection import bounded_arena

    if type(player_slots) is not int or not 2 <= player_slots <= 127:
        raise ValueError("Invalid dungeon party formation capacity")
    if type(quantity) is not int or not 1 <= quantity <= MAX_DUNGEON_MONSTERS:
        raise ValueError("Invalid dungeon enemy formation quantity")
    anchor = tuple(anchor)
    # Reuse combat's reachable-floor selector before forming either team.
    # Topology sections may legitimately contain stacked native floors; the
    # combat wire permits only unambiguous reachable heights in its rectangle.
    neighbors = sorted(
        {
            tuple(end)
            for start, end in geometry["edges"]
            if tuple(start) == anchor and tuple(end) != anchor
        }
    )
    safe = None
    for neighbor in neighbors:
        try:
            safe = bounded_arena(geometry, anchor, [neighbor], radius=89)
            break
        except ValueError:
            continue
    if safe is None:
        raise ValueError("Dungeon anchor has no safe reachable combat terrain")
    geometry = dict(geometry, cells=safe["cells"], edges=safe["edges"])
    reserved = {anchor, *reachable_cells(geometry, anchor, player_slots - 1)}
    blocked = reserved | set(map(tuple, occupied))
    edges = {}
    for start, end in geometry["edges"]:
        edges.setdefault(tuple(start), set()).add(tuple(end))
    distances, queue = {anchor: 0}, deque([anchor])
    while queue:
        cell = queue.popleft()
        for neighbor in sorted(edges.get(cell, ())):
            if neighbor not in distances:
                distances[neighbor] = distances[cell] + 1
                queue.append(neighbor)
    # Center the visible group in its reachable room, not the entry or a remote
    # corner. Exact integer centroid distances keep the policy deterministic.
    room_cells = set(map(tuple, geometry["cells"]))
    count = len(room_cells)
    center_x = sum(cell[0] for cell in room_cells)
    center_y = sum(cell[1] for cell in room_cells)
    for center in sorted(
        set(distances) - blocked,
        key=lambda cell: (
            (cell[0] * count - center_x) ** 2 + (cell[1] * count - center_y) ** 2,
            distances[cell],
            cell,
        ),
    ):
        try:
            positions = (
                (center,)
                if quantity == 1
                else (
                    center,
                    *reachable_cells(geometry, center, quantity - 1, occupied=blocked),
                )
            )
            placement = generate(
                geometry["cells"],
                geometry["edges"],
                {0: [anchor], 1: positions},
                slots_per_team=player_slots,
            )
        except ValueError:
            continue
        if len(placement[0]) >= player_slots:
            return positions
    raise ValueError("Dungeon room cannot separate party and enemy formations")


def room_members(
    run,
    *,
    asset_map_id,
    anchor,
    geometry,
    group_id,
    select_level,
    occupied=(),
    team=1,
    player_slots=0,
    actor_id_base=None,
):
    """Prepare actors without writes; caller registers them transactionally.

    `select_level(native_reference, frozen_roster_entry)` is the common runtime
    grade policy, not dungeon-specific code. Every returned level is validated
    against native statistics. The frozen roster must still match that catalog.
    """
    if run.get("status") != "active":
        raise ValueError("Dungeon run is not active")
    instance_id = run.get("instance_id")
    if type(instance_id) is not int or not 0 < instance_id < 2**63:
        raise ValueError("Dungeon encounter requires an owned runtime instance")
    if type(group_id) is not int or not 0 < group_id < 2**63:
        raise ValueError("Invalid dungeon encounter group identity")
    if not callable(select_level):
        raise ValueError("Authoritative dungeon grade policy required")
    order = run.get("current_room")
    rooms = run.get("rooms", ())
    matches = [room for room in rooms if room["order"] == order]
    if len(matches) != 1 or type(order) is not int:
        raise ValueError("Dungeon current room is absent or ambiguous")
    roster = matches[0]["monsters"]
    from wakfu_server.dungeon_monster_admission import current_policy, require

    admission_policy = current_policy()
    selected = {}
    expanded = []
    for row in roster:
        native = reference(row["ref_id"])
        if (row["min_level"], row["max_level"]) != (
            native["min_level"],
            native["max_level"],
        ):
            raise ValueError("Frozen dungeon roster differs from native level bounds")
        level = select_level(native, row)
        require(admission_policy, row["ref_id"], level, level, native=native)
        selected[id(row)] = level
        count = row["count"]
        if type(count) is not int or count <= 0:
            raise ValueError("Dungeon roster has an unresolved monster count")
        if len(expanded) + count > MAX_DUNGEON_MONSTERS:
            raise ValueError("Dungeon encounter exceeds supported placement capacity")
        expanded.extend((row, native) for _ in range(count))
    if not 1 <= len(expanded) <= MAX_DUNGEON_MONSTERS:
        raise ValueError("Dungeon encounter exceeds supported placement capacity")
    actor_id_base = group_id if actor_id_base is None else actor_id_base
    if type(actor_id_base) is not int or not 0 < actor_id_base < 2**63:
        raise ValueError("Invalid dungeon actor identity block")
    if actor_id_base + len(expanded) - 1 >= 2**63:
        raise ValueError("Dungeon monster identity exceeds signed wire range")
    positions = (
        enemy_formation(
            geometry,
            anchor,
            len(expanded),
            occupied=occupied,
            player_slots=player_slots,
        )
        if player_slots
        else reachable_cells(geometry, anchor, len(expanded), occupied=occupied)
    )
    return tuple(
        owned_instance(
            row["ref_id"],
            selected[id(row)],
            -(actor_id_base + index),
            map_id=asset_map_id,
            instance_id=instance_id,
            x=cell[0],
            y=cell[1],
            z=cell[2],
            team=team,
        )
        for index, ((row, native), cell) in enumerate(zip(expanded, positions))
    )
