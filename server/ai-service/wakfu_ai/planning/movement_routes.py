"""Bounded native-edge route alternatives for known hazardous cells."""

from ..native.native_deadline import check


def hazard_route_alternatives(adjacency, origin, occupied, movement_points, hazards):
    """Retain nondominated (steps, hazard entries) routes to each endpoint.

    At most one label per cell and step count survives. A shorter route
    dominates a longer route only when it has no more hazardous entries.
    These are navigation candidates; native previews certify actual effects.
    """
    if not hazards or movement_points <= 0:
        return ()
    labels = {origin: {0: (0, ())}}
    frontier = {origin: (0, ())}
    steps = 0
    inspected = 0
    while frontier and steps < movement_points:
        check()
        steps += 1
        following = {}
        for start, (exposure, path) in sorted(frontier.items()):
            for end in sorted(adjacency.get(start, ())):
                if inspected % 256 == 0:
                    check()
                inspected += 1
                if end in occupied:
                    continue
                cost = exposure + int(end in hazards)
                cell_labels = labels.setdefault(end, {})
                if any(
                    old_steps <= steps and old_cost <= cost
                    for old_steps, (old_cost, _) in cell_labels.items()
                ):
                    continue
                route = path + (end,)
                cell_labels[steps] = (cost, route)
                following[end] = (cost, route)
        frontier = following
    check()
    return tuple(
        route
        for cell in sorted(labels)
        for steps, (_, route) in sorted(labels[cell].items())
        if steps
    )
