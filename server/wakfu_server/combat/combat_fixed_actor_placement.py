"""Source-bound initial actor positions; later native movement stays ordinary."""


def declarations(descriptor, *, room_cells=None):
    rows = descriptor.get("fixed_actor_placements", ())
    if not isinstance(rows, (list, tuple)):
        raise ValueError("Invalid fixed actor placement declarations")
    references, centers, result = set(), set(), []
    cells = None if room_cells is None else set(map(tuple, room_cells))
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid fixed actor placement")
        reference, cell, direction = (
            row.get("reference"),
            row.get("cell"),
            row.get("direction"),
        )
        source = row.get("source")
        occurrence = row.get("occurrence")
        if (
            type(reference) is not int
            or reference <= 0
            or "occurrence" in row
            and (type(occurrence) is not int or occurrence < 0)
            or (reference, occurrence) in references
            or not isinstance(cell, (list, tuple))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            or tuple(cell) in centers
            or cells is not None
            and tuple(cell) not in cells
            or type(direction) is not int
            or not 0 <= direction <= 7
            or not isinstance(source, dict)
            or source.get("kind")
            not in (
                "original_native_marker",
                "authorized_native_content_reconstruction",
            )
            or type(source.get("uri")) is not str
            or not source["uri"].strip()
            or type(source.get("sha256")) is not str
            or len(source["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in source["sha256"])
        ):
            raise ValueError(
                "Fixed actor placement lacks unique native terrain/source authority"
            )
        references.add((reference, occurrence))
        centers.add(tuple(cell))
        result.append(row)
    return tuple(result)


def member_positions(descriptor, members, *, room_cells):
    """Resolve only unique actors in the admitted initial roster."""
    result = {}
    for row in declarations(descriptor, room_cells=room_cells):
        matches = [
            index
            for index, member in enumerate(members)
            if member["ref"] == row["reference"]
        ]
        if "occurrence" in row:
            occurrence = row["occurrence"]
            matches = matches[occurrence : occurrence + 1]
        if len(matches) != 1 or matches[0] in result:
            raise ValueError(
                "Fixed actor placement requires one admitted initial actor without duplicate bindings"
            )
        result[matches[0]] = tuple(row["cell"])
    return result


def bind_initial_directions(fight, descriptor, monsters):
    """Apply declared constructor facing before initial native snapshots."""
    bound = set()
    for row in declarations(descriptor):
        matches = [
            identity
            for identity, monster in monsters.items()
            if monster["ref"] == row["reference"]
        ]
        if "occurrence" in row:
            occurrence = row["occurrence"]
            matches = matches[occurrence : occurrence + 1]
        if len(matches) != 1 or matches[0] in bound:
            raise ValueError(
                "Fixed actor facing lacks its admitted initial actor without duplicate bindings"
            )
        bound.add(matches[0])
        actor = fight.actors[matches[0]]
        if actor.controlled or tuple(actor.position) != tuple(row["cell"]):
            raise ValueError(
                "Fixed actor constructor differs from its admitted placement"
            )
        actor.direction = row["direction"]


def world_placement(member):
    """Validate the source declaration retained by an owned world group."""
    if "fixed_actor_placement" not in member:
        return None
    row = member["fixed_actor_placement"]
    declarations(dict(fixed_actor_placements=[row]))
    if row["reference"] != member["ref"] or tuple(row["cell"]) != tuple(
        member[key] for key in ("x", "y", "z")
    ):
        raise ValueError("Fixed world actor differs from its declared initial position")
    return row


def native_member_fields(member):
    """Remove only validated source metadata before exact native-stat checks."""
    placement = world_placement(member)
    ignored = set()
    if placement is not None:
        ignored.add("fixed_actor_placement")
    if "rii_practice_resistance" in member:
        from wakfu_server.achievements.rii_free_practice import RESISTANCE_POINTS

        percent = member["rii_practice_resistance"]
        if (
            type(percent) is not int
            or percent not in RESISTANCE_POINTS
            or member.get("ref") != 2335
            or member.get("map_id") != 1388
            or member.get("instance_id") != 0
            or type(member.get("id")) is not int
            or member["id"] >= 0
        ):
            raise ValueError("Invalid owned dojo resistance")
        ignored.add("rii_practice_resistance")
    return (
        {key: value for key, value in member.items() if key not in ignored}
        if ignored
        else member
    )
