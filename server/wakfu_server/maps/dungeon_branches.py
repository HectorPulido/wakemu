"""Explicit native alternative routes with one durable choice per instance."""


def validate(topology):
    branches = topology.get("branch_routes", [])
    if not isinstance(branches, list):
        raise ValueError("Native branch routes must be an explicit list")
    if not branches:
        return {}
    if topology.get("policy") != "native_mixed_victory_policy" or not isinstance(
        branches, list
    ):
        raise ValueError("Native branch routes require a reviewed mixed policy")
    rooms = {room["order"]: room for room in topology["rooms"]}
    doors = {door["source_id"]: door for door in topology["doors"]}
    physical = {door["source_id"]: door for door in topology.get("physical_doors", [])}
    result, owned, physical_owned = {}, set(), set()
    for branch in branches:
        if not isinstance(branch, dict):
            raise ValueError("Native branch route must be an explicit object")
        key = branch.get("key")
        identities = branch.get("source_ids", [])
        entry = branch.get("entry_source_id")
        if (
            not isinstance(key, str)
            or not key.strip()
            or key in result
            or not isinstance(identities, list)
            or not identities
            or any(type(i) is not int or i not in doors for i in identities)
            or len(set(identities)) != len(identities)
            or owned.intersection(identities)
            or type(entry) is not int
            or entry not in identities
            or (doors[entry]["source_room"], doors[entry]["destination_room"]) != (1, 1)
        ):
            raise ValueError(
                "Native branch selector identities are invalid or ambiguous"
            )
        variants = branch.get("rooms", [])
        physical_ids = branch.get("physical_source_ids", [])
        if (
            not isinstance(physical_ids, list)
            or any(type(i) is not int or i not in physical for i in physical_ids)
            or len(set(physical_ids)) != len(physical_ids)
            or physical_owned.intersection(physical_ids)
        ):
            raise ValueError(
                "Native branch physical gate ownership is invalid or ambiguous"
            )
        physical_owned.update(physical_ids)
        if [room["order"] for room in variants] != list(rooms):
            raise ValueError("Native branch variants must cover every encounter")
        for variant in variants:
            cells = set(map(tuple, variant["cells"]))
            if (
                not cells
                or not cells.issubset(set(map(tuple, rooms[variant["order"]]["cells"])))
                or tuple(variant["anchor"]) not in cells
                or tuple(variant["native_arrival"]) not in cells
            ):
                raise ValueError(
                    "Native branch variant leaves its reviewed room terrain"
                )
        result[key] = branch
        owned.update(identities)
    if len(result) < 2:
        raise ValueError("Native alternatives require at least two reviewed branches")
    if physical_owned != set(physical):
        raise ValueError("Every native physical gate needs explicit branch ownership")
    return result


def unselected_gate_ids(topology):
    branches = validate(topology)
    selected = topology.get("selected_branch")
    if not branches or selected is None:
        return frozenset()
    if selected not in branches:
        raise ValueError("Unknown durable native branch")
    return frozenset(
        identity
        for key, branch in branches.items()
        if key != selected
        for identity in branch.get("physical_source_ids", [])
    )


def allowed_cells(topology):
    """Retain selected arenas and shared lobby terrain, never the other route."""
    branches = validate(topology)
    selected = topology.get("selected_branch")
    if not branches or selected is None:
        return None
    if selected not in branches:
        raise ValueError("Unknown durable native branch")
    all_cells = {tuple(c) for room in topology["rooms"] for c in room["cells"]}
    variants = {
        tuple(c)
        for branch in branches.values()
        for room in branch["rooms"]
        for c in room["cells"]
    }
    chosen = {tuple(c) for room in branches[selected]["rooms"] for c in room["cells"]}
    gates = unselected_gate_ids(topology)
    return (
        (all_cells - variants)
        | chosen
        | {
            tuple(gate["position"])
            for gate in topology.get("physical_doors", [])
            if gate["source_id"] not in gates
        }
    )


def select(db, instance_id, topology, source_id):
    """Lock the shared route choice in the same transaction as travel/spawn."""
    branches = validate(topology)
    if not branches:
        return None
    progress = db.execute(
        "SELECT branch_key,current_room FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if progress is None:
        raise ValueError("Native branch selection lacks dungeon progression")
    selected = progress["branch_key"]
    owners = [
        key for key, branch in branches.items() if source_id in branch["source_ids"]
    ]
    if selected is not None:
        if selected not in branches or owners and owners != [selected]:
            raise ValueError("Native transport belongs to a different selected branch")
        return selected
    choices = [
        key
        for key, branch in branches.items()
        if branch["entry_source_id"] == source_id
    ]
    if len(choices) != 1 or progress["current_room"] != 1:
        raise ValueError("Select a native entrance branch before room travel")
    selected = choices[0]
    db.execute(
        "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s",
        (selected, instance_id),
    )
    return selected


def selected_room(topology, order):
    branches = validate(topology)
    if not branches:
        return next(room for room in topology["rooms"] if room["order"] == order)
    selected = topology.get("selected_branch")
    if selected is None and order == 1:
        return None
    if selected not in branches:
        raise ValueError("Dungeon encounter has no durable selected branch")
    return next(room for room in branches[selected]["rooms"] if room["order"] == order)
