"""Select native reachable passive fixtures without changing encounter geometry."""
from collections import deque

from wakfu_server.combat_geometry import coordinate, prepare_geometry
from wakfu_server.combat_arena_selection import compact_encounter

_COMPACT_PLACEMENT_FAILURES = frozenset(
    (
        "Compact arena cannot preserve participant positions",
        "Player is outside native encounter terrain",
        "Player occupies ambiguous native encounter surface",
        "Native reachable encounter component lacks participant capacity",
    )
)


def passive_fixture_context(cells, source, fixture_factory, geometry_loader):
    """Keep a valid supplied fixture; recover only explicit compact placement failures."""
    source = coordinate(source)
    cells = tuple(coordinate(cell) for cell in cells)
    destination = next((cell for cell in cells if cell != source), None)
    if destination is None:
        raise ValueError("missing actual fixture cell")
    try:
        return fixture_factory(destination)
    except ValueError as exc:
        if str(exc) not in _COMPACT_PLACEMENT_FAILURES:
            raise
    destination = passive_witness_destination(geometry_loader(), source, cells)
    return fixture_factory(destination)


def directed_witness_candidates(data, source):
    """Stable breadth-first traversal over actual exported directed edges."""
    geometry = prepare_geometry(data)
    source = coordinate(source)
    if source not in geometry.cells:
        raise ValueError("Passive fixture source is outside native geometry")
    pending = deque([source])
    visited = {source}
    while pending:
        current = pending.popleft()
        for target in geometry.outgoing.get(current, ()):
            if target in visited:
                continue
            visited.add(target)
            pending.append(target)
            yield target


def passive_witness_destination(data, source, allowed_cells):
    """Require the existing compact9x9 fixture to preserve both participants."""
    geometry = prepare_geometry(data)
    source = coordinate(source)
    allowed = {coordinate(cell) for cell in allowed_cells}
    if not allowed <= geometry.cells:
        raise ValueError("Passive fixture cells lack native geometry authority")
    for target in directed_witness_candidates(geometry, source):
        if target not in allowed:
            continue
        try:
            selected = compact_encounter(
                geometry,
                target,
                [source],
                minimum_cells=81,
                minimum_dimensions=(9, 9),
                spread_opponents=False,
            )
        except ValueError:
            continue
        if (
            source in selected["cells"]
            and target in selected["cells"]
            and all(
                original == actual
                for original, actual in selected["participant_positions"]
            )
        ):
            return target
    raise ValueError("No native reachable participant-preserving passive fixture")
