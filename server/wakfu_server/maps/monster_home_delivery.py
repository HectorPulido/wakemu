"""Fence queued ecology output before sending it to an unchanged World.

Birth-home policy is checked again at delivery so pre-upgrade pending packets
cannot bypass new planning. Accepted historical lifecycle receipts are untouched.
"""
import struct

from .monster_birth_home import (
    ensure_homes,
    home_destination_allowed,
)
from .monster_idle_distribution import native_physical_radius
from .monster_wander import point


def _tracked_scope(scope):
    from .territory_cells import maps

    return scope[1] == 0 and scope[0] in maps()


def _home(store, scope, group_id, members):
    homes = ensure_homes(store, *scope, [dict(group_id=group_id, members=members)])
    return homes.get(group_id)


def _movement_allowed(store, scope, move):
    from .ecology_mobs import _edges, _path_cells_by_actor, _validate_bulk_wander_move
    from .monster_home_paths import MAX_HOME_DISTANCE, _distance_field

    decoded = _validate_bulk_wander_move(move)
    group_id, expected, moved = decoded[:3]
    if not _tracked_scope(scope):
        return True
    home = _home(store, scope, group_id, expected)
    if home is None:
        return False
    indexed = _edges(scope[0])
    paths = _path_cells_by_actor(move["packets"])
    moved_by_id = {member["id"]: member for member in moved}
    radii = tuple(
        sorted({native_physical_radius(member["ref"]) for member in expected})
    )

    def in_home(cell):
        return home_destination_allowed(scope[0], home, cell, radii=radii)

    distances = None
    for member in expected:
        origin = point(member)
        path = paths.get(member["id"], ())
        if not path:
            # An outside companion may hold while another one returns home.
            continue
        returning = not in_home(origin)
        if returning and distances is None:
            distances = _distance_field(
                indexed,
                home,
                lambda cell: home if in_home(cell) else 0,
                (scope[0], radii),
                MAX_HOME_DISTANCE,
            )
        previous = origin
        arrived = not returning
        for destination in path:
            if (previous, destination) not in indexed[0]:
                return False
            if arrived:
                if not in_home(destination):
                    return False
            else:
                before = distances.get(previous)
                after = distances.get(destination)
                if before is None or after is None or after >= before:
                    return False
                arrived = in_home(destination)
            previous = destination
        if previous != point(moved_by_id[member["id"]]):
            return False
    return True


def _reproduction_allowed(store, proposal):
    scope = tuple(proposal["scope"])
    if not _tracked_scope(scope):
        return True
    ticket = proposal["ticket"]
    members = proposal["expected_members"]
    home = _home(store, scope, ticket["group_id"], members)
    if home is None:
        return False
    destination = tuple(proposal["destination"])
    child = proposal.get("child")
    radius = 0 if child is None else native_physical_radius(child["ref"])
    if child is not None and point(child) != destination:
        return False
    return home_destination_allowed(scope[0], home, destination, radii=(radius,))


def validate_proposal(store, row):
    """Return False for obsolete home-violating work without sending it onward.

    Catalog/shape failures are rejected closed; database failures propagate so
    temporary storage outages never acknowledge unvalidated durable work.
    """
    if row["domain"] != "mobs":
        return True
    proposal = row["payload"]
    kind = proposal.get("kind")
    try:
        if kind == "wander_bulk":
            scope = tuple(proposal["scope"])
            return all(
                _movement_allowed(store, scope, move) for move in proposal["moves"]
            )
        if kind == "wander":
            move = {
                key: proposal[key]
                for key in ("group_id", "expected_members", "moved_members", "packets")
            }
            return _movement_allowed(store, tuple(proposal["scope"]), move)
        if kind == "reproduction":
            return _reproduction_allowed(store, proposal)
        if kind == "lifecycle_bulk":
            return all(
                _reproduction_allowed(store, operation)
                for operation in proposal["operations"]
                if operation["kind"] == "reproduction"
            )
        if kind == "idle_distribution":
            from .monster_idle_distribution_store import home_chunk_allowed, cancel

            if home_chunk_allowed(store, proposal):
                return True
            cancel(
                store,
                epoch=proposal["world_epoch"],
                scope=proposal["scope"],
                generation=proposal["empty_generation"],
            )
            return False
        return True
    except (ValueError, KeyError, TypeError, struct.error):
        return False
