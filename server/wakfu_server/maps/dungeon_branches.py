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
        physical_entry = branch.get("entry_physical_source_id")
        physical_selector = (
            entry is None
            and type(physical_entry) is int
            and physical_entry in physical
            and physical[physical_entry]["destination_room"]
            == physical[physical_entry]["source_room"] + 1
        )
        transport_selector = (
            physical_entry is None
            and type(entry) is int
            and entry in identities
            and entry in doors
            and (doors[entry]["source_room"], doors[entry]["destination_room"])
            == (1, 1)
        )
        if (
            not isinstance(key, str)
            or not key.strip()
            or key in result
            or not isinstance(identities, list)
            or (not identities and not physical_selector)
            or any(type(i) is not int or i not in doors for i in identities)
            or len(set(identities)) != len(identities)
            or owned.intersection(identities)
            or not (physical_selector or transport_selector)
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
            or (physical_selector and physical_entry not in physical_ids)
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
    shared = topology.get("shared_physical_source_ids", [])
    if (
        not isinstance(shared, list)
        or len(set(shared)) != len(shared)
        or any(type(value) is not int or value not in physical for value in shared)
        or physical_owned.intersection(shared)
    ):
        raise ValueError("Shared native physical gate ownership is invalid")
    for identity in shared:
        gate = physical[identity]
        for order in (gate["source_room"], gate["destination_room"]):
            variants = [
                next(row for row in branch["rooms"] if row["order"] == order)
                for branch in result.values()
            ]
            expected = (
                {tuple(cell) for cell in variants[0]["cells"]},
                tuple(variants[0]["anchor"]),
                variants[0].get("encounter_component"),
            )
            if any(
                (
                    {tuple(cell) for cell in row["cells"]},
                    tuple(row["anchor"]),
                    row.get("encounter_component"),
                )
                != expected
                for row in variants[1:]
            ):
                raise ValueError(
                    "Shared native gate endpoints differ between branch arenas"
                )
    checkpoint = topology.get("branch_selection_checkpoint")
    if checkpoint is None and any(
        b.get("entry_physical_source_id") is not None for b in result.values()
    ):
        raise ValueError(
            "Physical native branch requires an explicit shared-prefix checkpoint"
        )
    if checkpoint is not None:
        if type(checkpoint) is not int or not 1 <= checkpoint < len(rooms):
            raise ValueError("Invalid native shared-prefix selection checkpoint")
        variants = list(result.values())
        for order in range(1, checkpoint + 1):
            prefix = [
                next(r for r in b["rooms"] if r["order"] == order) for b in variants
            ]
            if any(row != prefix[0] for row in prefix):
                raise ValueError(
                    "Native branch choice cannot rewrite its shared prefix"
                )
        for branch in variants:
            gate = physical.get(branch.get("entry_physical_source_id"))
            if gate is None or (gate["source_room"], gate["destination_room"]) != (
                checkpoint,
                checkpoint + 1,
            ):
                raise ValueError(
                    "Physical choice does not bind the shared-prefix frontier"
                )
    if physical_owned | set(shared) != set(physical):
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


def select(
    db,
    instance_id,
    topology,
    source_id,
    *,
    source_kind="transport",
    expected_catalog_hash=None,
    expected_rooms=None
):
    """Lock the shared route choice in the same transaction as travel/spawn."""
    if source_kind not in ("transport", "physical"):
        raise ValueError("Unknown native branch selector kind")
    branches = validate(topology)
    if not branches:
        return None
    lock = " FOR UPDATE NOWAIT" if source_kind == "physical" else " FOR UPDATE"
    progress = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s" + lock,
        (instance_id,),
    ).fetchone()
    if progress is None:
        raise ValueError("Native branch selection lacks dungeon progression")
    if source_kind == "physical":
        if (
            type(expected_catalog_hash) is not str
            or len(expected_catalog_hash) != 64
            or not isinstance(expected_rooms, list)
            or not expected_rooms
            or progress.get("catalog_hash") != expected_catalog_hash
            or progress.get("rooms") != expected_rooms
        ):
            raise ValueError(
                "Physical native choice differs from its pinned source roster"
            )
    selected = progress["branch_key"]
    owners = [
        key
        for key, branch in branches.items()
        if source_id
        in branch.get(
            "physical_source_ids" if source_kind == "physical" else "source_ids", []
        )
    ]
    if selected is not None:
        if selected not in branches or owners and owners != [selected]:
            raise ValueError("Native transport belongs to a different selected branch")
        return selected
    choices = [
        key
        for key, branch in branches.items()
        if branch.get(
            "entry_physical_source_id"
            if source_kind == "physical"
            else "entry_source_id"
        )
        == source_id
    ]
    if source_kind == "physical":
        gates = {gate["source_id"]: gate for gate in topology["physical_doors"]}
        expected_room = (
            gates[source_id]["destination_room"] if len(choices) == 1 else None
        )
    else:
        expected_room = 1
    if len(choices) != 1 or progress["current_room"] != expected_room:
        raise ValueError("Select a native entrance branch before room travel")
    if source_kind == "physical":
        checkpoint = topology.get("branch_selection_checkpoint")
        if (
            type(checkpoint) is not int
            or expected_room != checkpoint + 1
            or progress.get("status") != "active"
        ):
            raise ValueError(
                "Physical native choice lacks its shared-prefix checkpoint"
            )
        existing = db.execute(
            "SELECT room_order,status,result FROM dungeon_room_encounters WHERE instance_id=%s "
            "AND encounter_scope='main' ORDER BY room_order,fight_id",
            (instance_id,),
        ).fetchall()
        if any(
            row["room_order"] > checkpoint or row["status"] == "active"
            for row in existing
        ):
            raise ValueError(
                "Physical native choice already has an admitted suffix encounter"
            )
        victories = {
            row["room_order"]
            for row in existing
            if row["status"] == "victory"
            and isinstance(row.get("result"), dict)
            and row["result"].get("victory") is True
            and row["result"].get("current_room") == row["room_order"] + 1
            and row["result"].get("completed") is False
        }
        if victories != set(range(1, checkpoint + 1)):
            raise ValueError(
                "Physical native choice lacks committed shared-prefix victories"
            )
        receipts = db.execute(
            "SELECT room_order,asset_map_id,group_id FROM dungeon_room_spawn_receipts WHERE instance_id=%s ORDER BY room_order",
            (instance_id,),
        ).fetchall()
        if {row["room_order"] for row in receipts} != set(
            range(1, checkpoint + 1)
        ) or any(
            row["asset_map_id"] != topology["asset_map_id"]
            or type(row["group_id"]) is not int
            or row["group_id"] <= 0
            for row in receipts
        ):
            raise ValueError(
                "Physical native choice cannot replace admitted room groups"
            )
    selected = choices[0]
    statement = (
        "UPDATE dungeon_room_runs SET branch_key=%s,revision=revision+1 WHERE instance_id=%s"
        if source_kind == "physical"
        else "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s"
    )
    db.execute(statement, (selected, instance_id))
    return selected


def selected_room(topology, order):
    branches = validate(topology)
    if not branches:
        return next(room for room in topology["rooms"] if room["order"] == order)
    selected = topology.get("selected_branch")
    if selected is None:
        variants = [
            next(room for room in branch["rooms"] if room["order"] == order)
            for branch in branches.values()
        ]
        checkpoint = topology.get("branch_selection_checkpoint")
        if checkpoint is None:
            if order == 1:
                return None
            raise ValueError("Dungeon encounter has no durable selected branch")
        if order > checkpoint:
            return None
        # A source-identical prefix is playable before its physical choice.
        return variants[0] if all(room == variants[0] for room in variants) else None
    if selected not in branches:
        raise ValueError("Dungeon encounter has no durable selected branch")
    return next(room for room in branches[selected]["rooms"] if room["order"] == order)


def physical_selector(topology, request, *, unlocked_room):
    """Return a source-bound choice from an already validated native path.

    This does not acquire locks or commit movement. The caller must select with
    NOWAIT, revalidate against the selected topology, and publish position only
    after the owning transaction succeeds. Contention must preserve the prior
    position; no partial path or teleport is authorized by this helper.
    """
    branches = validate(topology)
    if not branches:
        return None
    physical = {gate["source_id"]: gate for gate in topology["physical_doors"]}
    current = tuple(request["start_position"][axis] for axis in ("x", "y", "z"))
    visited = [current]
    for step in request["steps"]:
        current = tuple(
            current[index] + step["d" + axis]
            for index, axis in enumerate(("x", "y", "z"))
        )
        visited.append(current)
    choices = []
    for branch in branches.values():
        identity = branch.get("entry_physical_source_id")
        if identity is None:
            continue
        gate = physical[identity]
        if tuple(gate["position"]) in visited:
            if unlocked_room < gate["destination_room"]:
                raise ValueError("Native physical branch lacks committed victory")
            choices.append(identity)
    if len(choices) > 1:
        raise ValueError(
            "Native movement crosses multiple alternative branch selectors"
        )
    return choices[0] if choices else None
