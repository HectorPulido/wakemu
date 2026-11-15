"""Admit only the captured Rii speakers while generic NPC dialogue is disabled.

Admission merely selects the existing NPC dispatcher. Scene ownership, range,
native choices and the observed graph are still validated by that dispatcher.
"""

import struct

_ACTORS = {
    1385: frozenset((-1706442046308322, -1706442046308330, -1706442046308328)),
    1387: frozenset((-1706442035962340,)),
    1388: frozenset((-1706442046308339,)),
}
_SPEAKERS = {
    1385: frozenset((-1706442046308322, 424, -1706442046308328)),
    1387: frozenset((-1706442035962340,)),
    1388: frozenset((-1706442046308339,)),
}
_PLACEMENTS = {
    (1385, -1706442046308322): 5461,
    (1385, -1706442046308330): 5459,
    (1385, -1706442046308328): 5467,
    (1387, -1706442035962340): 5458,
    (1388, -1706442046308339): 5460,
}


def qualified_placement(row):
    """Identify exactly the native Rii placements whose actions are dispatched."""
    return (
        row.get("instance_id") == 0
        and _PLACEMENTS.get((row.get("map_id"), row.get("actor_id")))
        == row.get("reference_id")
        and row.get("reference_id") is not None
    )


def allow(opcode, body, character, session):
    """Return whether the native Rii dispatcher may authenticate this request."""
    from wakfu_server.achievements import npc_dialogue_actions

    if npc_dialogue_actions.allow(opcode, body, character, session):
        return True
    if character.get("instance_id") != 0:
        return False
    map_id = character.get("map_id")
    if opcode == 13222 and len(body) == 16:
        actor_id, _ = struct.unpack(">qq", body)
        return actor_id in _ACTORS.get(map_id, ())
    if opcode == 12535 and len(body) == 13:
        _, _, speaker_id = struct.unpack(">ibq", body)
        return speaker_id in _SPEAKERS.get(map_id, ())
    if opcode == 12058 and len(body) == 8 and session is not None:
        return getattr(session, "speaker_id", None) in _SPEAKERS.get(map_id, ())
    return False
