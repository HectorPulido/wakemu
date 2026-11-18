"""Authenticate conditional native exits against the pinned owned story.

The native criterion is evaluated on the locked durable quest ledger. A
literal source hash, endpoint, selected mode and native approach are required;
no empty-criterion rewrite or generic foreign-exit fallback is permitted.
"""

import re
import struct

from wakfu_server import dungeon_runtime, generic_transports, owned_story_controller
from wakfu_server.dungeon_runtime_config import canonical_hash
from wakfu_server.achievements import storage

_REQUEST = struct.Struct(">qiBi")
_COMPLETED = re.compile(
    r"(?P<negative>!|not\s+)?IsAchievementComplete\((?P<quest>[1-9][0-9]*)\)"
)


def criterion_allowed(criterion, completed):
    if criterion == "":
        return True
    matched = _COMPLETED.fullmatch(criterion)
    if matched is None:
        raise ValueError("Owned story exit has an unsupported native criterion")
    earned = int(matched["quest"]) in completed
    return not earned if matched["negative"] else earned


def _native_binding_target(source, binding, map_id):
    """Match the sealed source and free exterior endpoint, without admission."""
    if (
        source is None
        or source.get("id") != binding.get("source_id")
        or source.get("map_id") != map_id
        or canonical_hash(source) != binding.get("source_sha256")
        or [source[k] for k in ("x", "y", "z")] != binding.get("source_position")
    ):
        raise ValueError("Owned story exit lost its exact native source/approach")
    targets = [
        row
        for row in source["destinations"]
        if row["destination_id"] == binding.get("destination_id")
    ]
    if len(targets) != 1:
        raise ValueError("Owned story exit has no unique native destination")
    target = targets[0]
    if (
        target["map_id"] == map_id
        or target["criterion"] != binding.get("criterion")
        or {k: target[k] for k in ("map_id", "x", "y", "z")}
        != binding.get("destination")
        or target["cyZ"] >= 0
        or target["cyX"] != 0
        or target["cyW"] != 0
        or target["native_altitude_walkable"] is not True
    ):
        raise ValueError("Owned story exit endpoint or native cost changed")
    # Projection preserves the original criterion. Its route-specific departure
    # handler owns evaluation; other story routes have compound predicates.
    return target


def declared_sources(topology, sources, *, map_id):
    """Publish attested story exits before ordinary room-exit heuristics.

    Native client criteria and the locked departure transaction still authorize
    each branch. This projection must not reject a valid source merely because
    its sprite belongs to an intermediate component of a reviewed story map.
    """
    bindings = topology.get("native_story_exits", ())
    if not bindings:
        return frozenset()
    if not any(
        topology.get(name) is not None
        for name in ("owned_story_controller", "owned_object_trials")
    ):
        raise ValueError("Native story exits lack their owned story authority")
    indexed = {row["id"]: row for row in sources}
    seen = set()
    for binding in bindings:
        key = (binding["source_id"], binding["destination_id"])
        if key in seen:
            raise ValueError("Owned story exit repeats a native branch")
        seen.add(key)
        _native_binding_target(indexed.get(binding["source_id"]), binding, map_id)
    return frozenset(identity for identity, _ in seen)


def authenticate_exit(db, store, character, body, *, source_allowed):
    """Return the exact native binding; the caller still owns atomic departure."""
    if (
        not isinstance(body, (bytes, bytearray, memoryview))
        or len(body) != _REQUEST.size
        or not callable(source_allowed)
    ):
        raise ValueError("Invalid owned story exit request")
    source_id, destination_id, flag, mode = _REQUEST.unpack(body)
    if (flag, mode) != (0, 2):
        raise ValueError("Unsupported owned story exit mode")
    _, configuration = dungeon_runtime.configuration_for_instance(
        db, character["instance_id"]
    )
    from wakfu_server import owned_noncombat_context

    if configuration["topology"].get("owned_object_trials") is not None:
        from wakfu_server import owned_object_trials

        selected, _ = owned_object_trials._scope(db, store, character)
        completed_steps = set()
    else:
        selected, completed_steps = owned_story_controller._scope(db, store, character)
    choices = [
        row
        for row in configuration["topology"].get("native_story_exits", ())
        if row.get("source_id") == source_id
        and row.get("destination_id") == destination_id
    ]
    if len(choices) != 1:
        raise ValueError("Owned story exit has no unique pinned branch")
    binding = choices[0]
    source = generic_transports.source(character["map_id"], source_id)
    if (
        source is None
        or selected["map_id"] != character["map_id"]
        or source_allowed(character, dict(source)) is not True
    ):
        raise ValueError("Owned story exit lost its exact native source/approach")
    target = _native_binding_target(source, binding, character["map_id"])
    state = storage.load_locked(db, character["id"])
    if not criterion_allowed(target["criterion"], set(state["completed"])):
        raise ValueError("Owned story exit criterion is not fulfilled")
    return dict(
        source=dict(source),
        destination=dict(target),
        binding=dict(binding),
        controller=selected,
        completed_steps=completed_steps,
        configuration=configuration,
    )


def leave_unfinished(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    in_fight,
    positions=None
):
    """Use the literal unfinished native return with ordinary durable cleanup.

    Completed-story alternatives belong to their cinematic continuation
    producer. They cannot fall through this public-return path.
    """
    from wakfu_server import dungeon_exit

    def destination_for(db, character, _run):
        resolved = authenticate_exit(
            db, store, character, body, source_allowed=source_allowed
        )
        matched = _COMPLETED.fullmatch(resolved["destination"]["criterion"])
        if matched is None or not matched["negative"]:
            raise ValueError("Completed story exit requires its native continuation")
        return dict(resolved["destination"])

    return dungeon_exit._leave(
        store,
        account_id,
        generation,
        character_id,
        in_fight=in_fight,
        destination_for=destination_for,
        positions=positions,
    )
