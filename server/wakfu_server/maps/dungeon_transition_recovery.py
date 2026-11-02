"""Bounded recovery of invalid automatic destinations after committed victory.

This module never changes victory, progress, configuration pins or resources.
Only a unique existing forward edge may use its verified destination-room anchor.
All other failures remain at the last committed location until normal exit.
"""
from datetime import datetime
import hashlib
import json


class RecoverableDungeonDestination(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class DungeonExitDeferred(ValueError):
    """A changed lease/member/combat state requires retry, not disconnection."""


class DungeonHydrationDeferred(ValueError):
    """Durable travel changed while its destination bootstrap was prepared."""


def _point(value):
    if (
        type(value) not in (tuple, list)
        or len(value) != 3
        or any(type(part) is not int for part in value)
    ):
        return None
    return tuple(value)


def native_anchor_allowed(map_id, cell):
    """Use installed physical and ordinary-ground policies, never proximity."""
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.combat_sn_path import NativeSnColumns
    from wakfu_server.combat_ground_support import supported

    columns = NativeSnColumns.from_published(map_id)
    surfaces = [row for row in columns.column(*cell[:2]) or () if row.z == cell[2]]
    return (
        cell in published_geometry(map_id).cells
        and bool(surfaces)
        and not surfaces[-1].blf & (1 << 3)
        and supported(map_id, cell, columns.source_sha256)
    )


def signature(result, topology):
    order = result.get("current_room")
    value = dict(
        policy=topology.get("policy"),
        map_id=topology.get("asset_map_id"),
        current_room=order,
        rooms=[
            room for room in topology.get("rooms", ()) if room.get("order") == order
        ],
        links=[
            edge
            for edge in topology.get("auto_edges", ())
            if edge.get("source_room") == order - 1
            and edge.get("destination_room") == order
        ]
        if type(order) is int
        else [],
    )
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def forward_anchor(result, topology, error, *, verify_anchor=native_anchor_allowed):
    """Repair precisely an obsolete edge anchor; ambiguity grants no travel."""
    if (
        error.code != "forward_anchor_mismatch"
        or result.get("victory") is not True
        or result.get("completed") is True
        or topology.get("policy") != "local_accessible_anchor_policy"
        or topology.get("doors")
    ):
        return None
    order = result.get("current_room")
    if type(order) is not int or order <= 1:
        return None
    rooms = [room for room in topology.get("rooms", ()) if room.get("order") == order]
    links = [
        edge
        for edge in topology.get("auto_edges", ())
        if edge.get("source_room") == order - 1
        and edge.get("destination_room") == order
    ]
    if len(rooms) != 1 or len(links) != 1:
        return None
    anchor = _point(rooms[0].get("anchor"))
    map_id = topology.get("asset_map_id")
    if (
        type(map_id) is not int
        or map_id <= 0
        or anchor is None
        or anchor not in {_point(cell) for cell in rooms[0].get("cells", ())}
        or verify_anchor(map_id, anchor) is not True
    ):
        return None
    destination = dict(map_id=map_id, **dict(zip(("x", "y", "z"), anchor)))
    journal = dict(
        mode="verified_room_anchor",
        code=error.code,
        source_room=order - 1,
        destination_room=order,
        obsolete_anchor=links[0].get("anchor"),
        verified_anchor=list(anchor),
        signature=signature(result, topology),
    )
    return destination, journal


def exit_authorized(topology, entry_map_id):
    """Only the already admitted exterior return may be used as fallback."""
    destination = topology.get("completion_destination")
    return (
        topology.get("policy") == "local_accessible_anchor_policy"
        and type(destination) is dict
        and destination.get("provenance", {}).get("policy")
        == "native_entry_approved_walkable_approach"
        and all(type(destination.get(key)) is int for key in ("map_id", "x", "y", "z"))
        and destination["map_id"] == entry_map_id
    )


def journal_timestamp(now):
    """Keep recovery metadata JSON-native without changing SQL timestamps."""
    return now.timestamp() if isinstance(now, datetime) else now


def failure_journal(result, topology, error, now):
    now = journal_timestamp(now)
    identity = signature(result, topology)
    previous = result.get("transition_recovery", {})
    attempts = (
        previous.get("attempts", 0) if previous.get("signature") == identity else 0
    )
    attempts += 1
    return dict(
        mode="exit_required",
        code=error.code,
        signature=identity,
        attempts=attempts,
        last_attempt=now,
        next_retry=now + min(60, 2 ** min(attempts, 6)),
    )


def retry_due(result, topology, now):
    now = journal_timestamp(now)
    previous = result.get("transition_recovery")
    if not isinstance(previous, dict) or previous.get("mode") != "exit_required":
        return True
    if previous.get("signature") != signature(result, topology):
        return True
    # Transient contention never permanently disables a safe exit, including
    # journals written by older workers with exhausted=True.
    return now >= previous.get("next_retry", 0)
