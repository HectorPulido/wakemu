"""Installed nation board admission to the existing native citizenship chooser."""
import math
import struct

from wakfu_server import nation_state, world_static
from wakfu_server.environment_interactions import _guard, _position
from wakfu_server.inventory_items import _lease


def definition(map_id, object_id):
    """Resolve only installed board identities, never a caller-provided template."""
    return next(
        (
            row
            for row in world_static.objects(map_id)
            if row["id"] == object_id and row["type"] == "NationSelectionBoard"
        ),
        None,
    )


def request(body):
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid nation board request")
    identity, action, parameter = struct.unpack(">qHH", body)
    if identity <= 0 or action != 28 or parameter:
        raise ValueError("Unsupported nation board action")
    return identity


def open_selection(store, account_id, generation, character, body, *, blocked=False):
    """Return14006 after selected-session, scene, occupation and citizenship checks.

    Geometry uses the existing environment interaction policy (four cardinal
    steps, one height unit), not a claim of native pathfinding equivalence.
    The live scene comes from the dispatcher; SQL may hold the exterior of a
    private scene, so private instances are excluded rather than substituted.
    """
    identity = request(body)
    if blocked:
        raise ValueError("Nation board is unavailable during an occupation")
    rule = definition(character["map_id"], identity)
    if rule is None:
        raise ValueError("Unsupported installed nation board")
    for axis in ("x", "y", "z"):
        coordinate = character[axis]
        if type(coordinate) not in (int, float) or not math.isfinite(coordinate):
            raise ValueError("Invalid nation board position")
    _position(character, rule)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        saved = store.character(account_id, character["id"], db)
        if nation_state.nation_id(saved) != 0:
            raise ValueError("Character already belongs to a nation")
        if saved["level"] < 1:
            raise ValueError("Character cannot select a nation yet")
        rows = db.execute(
            "SELECT n.nation_id,COUNT(*) AS population "
            "FROM character_chat_nations n JOIN characters c ON c.id=n.character_id "
            "WHERE c.deleted_at IS NULL GROUP BY n.nation_id"
        ).fetchall()
        return nation_state.selection_packet(
            {row["nation_id"]: row["population"] for row in rows}
        )
