"""Worker-side delivery loop for durable dungeon map transitions.

This module deliberately does not choose sockets, mutate WORLD/POSITIONS, or
construct map packets. Its worker callbacks own those operations. A transition
is ACKed only when the bootstrap callback returns exactly True after sending
the complete destination bootstrap. That records successful server writes, not
visual receipt by the client. Failed or interrupted writes remain retryable.
"""
from __future__ import annotations

from collections.abc import Mapping

from wakfu_server import dungeon_instances


_LOCATION_FIELDS = ("map_id", "instance_id", "x", "y", "z")


def deliver_pending_transitions(
    store,
    account_id,
    generation,
    character_id,
    *,
    worker_generation,
    current_location,
    in_fight,
    bootstrap,
):
    """Deliver pending transitions for one session-owning worker.

    ``current_location()`` returns the worker's loaded location. It must match
    the event's source or destination; another map is a stale worker snapshot
    and is deferred for authoritative reload. ``in_fight()`` is rechecked
    immediately before bootstrap. ``bootstrap(event)`` must reconcile runtime
    membership and send the complete map bootstrap, returning exactly True on
    completion. It should be safe to retry after partial network writes.

    The caller must invoke this only on the worker that owns ``generation``.
    The database ACK performs a second lease, generation, membership, and
    destination check after callback completion.
    """
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid dungeon transition account")
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid dungeon transition character")
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid dungeon transition generation")
    if worker_generation != generation:
        return _result("stale_generation")
    if (
        not callable(current_location)
        or not callable(in_fight)
        or not callable(bootstrap)
    ):
        raise ValueError("Dungeon transition worker callbacks are required")

    events = dungeon_instances.pending_transitions(
        store, account_id, generation, character_id
    )
    if not events:
        return _result("idle")

    acknowledged = []
    for raw_event in events:
        event = dict(raw_event)
        _validate_event(event, generation, character_id)

        fighting = in_fight()
        if type(fighting) is not bool:
            raise ValueError("Dungeon worker combat state must be boolean")
        if fighting:
            return _result("deferred_combat", acknowledged, events)

        location = current_location()
        _validate_location(location)
        if location not in (
            _location(event, "source"),
            _location(event, "destination"),
        ):
            return _result("deferred_map_mismatch", acknowledged, events)

        if bootstrap(event) is not True:
            return _result("bootstrap_incomplete", acknowledged, events)

        try:
            did_acknowledge = dungeon_instances.acknowledge_transition(
                store,
                account_id,
                generation,
                character_id,
                event["event_id"],
            )
        except ValueError:
            # A replacement session or a newer authoritative location won the
            # race while packets were being written. Leave durable state for
            # that session's bootstrap/reconciliation path.
            return _result("session_or_destination_changed", acknowledged, events)
        if did_acknowledge is not True:
            return _result("acknowledgement_already_changed", acknowledged, events)
        acknowledged.append(event["event_id"])

    return _result("delivered", acknowledged, events)


def _validate_event(event, generation, character_id):
    if (
        type(event.get("event_id")) is not int
        or event["event_id"] <= 0
        or event.get("character_id") != character_id
        or event.get("session_generation") != generation
    ):
        raise ValueError("Invalid dungeon transition event identity")
    if any(
        f"{side}_{field}" not in event
        for side in ("source", "destination")
        for field in _LOCATION_FIELDS
    ):
        raise ValueError("Incomplete dungeon transition event")
    for side in ("source", "destination"):
        _validate_location(_location(event, side))


def _location(event, prefix):
    return {field: event[f"{prefix}_{field}"] for field in _LOCATION_FIELDS}


def _validate_location(location):
    if not isinstance(location, Mapping) or set(location) != set(_LOCATION_FIELDS):
        raise ValueError("Invalid dungeon worker location")
    if any(type(location[field]) is not int for field in _LOCATION_FIELDS):
        raise ValueError("Invalid dungeon worker location")
    if location["map_id"] <= 0 or location["instance_id"] < 0:
        raise ValueError("Invalid dungeon worker location")


def _result(state, acknowledged=(), events=()):
    acknowledged_ids = tuple(acknowledged)
    acknowledged_set = set(acknowledged_ids)
    pending_ids = tuple(
        event["event_id"]
        for event in events
        if event["event_id"] not in acknowledged_set
    )
    return {
        "state": state,
        "acknowledged_event_ids": acknowledged_ids,
        "pending_event_ids": pending_ids,
    }
