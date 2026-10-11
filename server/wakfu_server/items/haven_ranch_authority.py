"""Authorize installed RanchEntrance choices without trusting client destinations."""
import struct

from wakfu_server import world_static
from wakfu_server.haven_ranch import ACTIONS, destination


def portal_target(character, bag, body, *, validate_lease, geometry, installed=None):
    """Resolve a native choice after current connection and scene authorization.

    The caller validates the live actor lease under its existing transaction.
    Geometry is the current immutable native map export, prepared beforehand.
    """
    if len(body) != 12:
        raise ValueError("Invalid native ranch interaction length")
    source_id, action, parameter = struct.unpack(">qHH", body)
    if bag is None or not bag.owns(character) or not bag.is_owner:
        raise ValueError("Ranch choices require the owned live haven bag")
    validate_lease()
    sources = [
        row
        for row in world_static.objects(9)
        if row["id"] == source_id and row["type"] == "RanchEntrance"
    ]
    if len(sources) != 1 or action not in ACTIONS or parameter != 0:
        raise ValueError("Unknown native ranch source or choice")
    source = sources[0]
    if source.get("map_id") != 9 or geometry.get("map_id") != 9:
        raise ValueError("Ranch source geometry identity mismatch")
    actor_cell = tuple(character[key] for key in ("x", "y", "z"))
    if actor_cell not in {tuple(cell) for cell in geometry["cells"]}:
        raise ValueError("Ranch actor is outside native walkable terrain")
    if (
        character["z"] != source["z"]
        or abs(character["x"] - source["x"]) + abs(character["y"] - source["y"]) > 1
    ):
        raise ValueError("Ranch entrance is out of reach")
    return destination(action, installed)


def biome_target(character, session, body, *, validate_lease, installed=None):
    """Native12380 may switch only an already authorized owned ranch scene."""
    if len(body) != 4 or session is None or not session.owns(character):
        raise ValueError("Ranch biome change requires an active owned ranch")
    validate_lease()
    (biome,) = struct.unpack(">i", body)
    actions = [action for action, candidate in ACTIONS.items() if candidate == biome]
    if len(actions) != 1:
        raise ValueError("Unknown installed ranch biome")
    return destination(actions[0], installed)


def validate_return(character, session, body, *, validate_lease):
    """Native13982 false exits; never accept a guessed context or trailing bytes."""
    if body != b"\x00" or session is None or not session.owns(character):
        raise ValueError("Invalid native ranch return")
    validate_lease()
