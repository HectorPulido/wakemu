"""Original scenario1340 presentation for the Astrub cat-house story.

Scene events, argument counts, visible species and scripted coordinates come
from installed scenario/1340.lua. The initial cat layout and exterior player's
approach are explicit reconstructions on installed map312 cells: no later
cat-house combat was present in the preserved official Rii capture.

These functions encode owner-only presentation. They do not register combat
groups, select fight winners, award objectives or change durable positions.
The story orchestrator owns those actions and retires presentation actors.
"""

from dataclasses import dataclass
import struct

SCENARIO_ID = 1340
MAP_ID = 312
LUA_SHA256 = "fbff192c335c1e1e948dc41ce547713a1ddfd9d243ed7cc41f2ca55a8b0af8f6"
BOOTSTRAP_EVENT = 10021
ROOM_VICTORY_SCENES = {1: 23922, 2: 23924, 3: 23926}
FIGHT_START_EVENTS = {1: 23904, 2: 23905, 3: 23906}
AFTER_SCENE_EVENTS = {
    23920: 23921,
    23922: 23923,
    23924: 23925,
    23926: 23927,
    23928: 23929,
}
ARGUMENT_COUNTS = {
    BOOTSTRAP_EVENT: 12,
    23920: 0,
    23921: 0,
    23922: 0,
    23923: 0,
    23924: 3,
    23925: 0,
    23926: 0,
    23927: 0,
    23928: 5,
    23929: 0,
    23904: 0,
    23905: 0,
    23906: 0,
}
# The Lua itself sets all but the entry and exterior approach positions. Those
# two reconstructed anchors are walkable native map312 cells beside its actors.
PLAYER_POSITIONS = {
    23920: (0, 0, 0),
    23922: (6, 1, 0),
    23924: (15, -8, 0),
    23926: (21, -5, -11),
    23928: (149, 125, 0),
}
NATIVE_SCENE_DURATIONS_MS = {
    23920: 14000,
    23922: 19000,
    23924: 36500,
    23926: 35500,
    23928: 51500,
}
TRISTEPIN_COMBAT_REFERENCE = 4691
TRISTEPIN_COMBAT_LEVEL = 6
TRISTEPIN_VISUAL_REFERENCE = 4687


@dataclass(frozen=True)
class VisualActor:
    role: str
    reference_id: int
    level: int
    position: tuple[int, int, int]
    direction: int = 3


# The original entry event has twelve unique actor arguments. Preserve those
# roles independently from the reviewed three-fighter-per-room combat policy.
# Unbound environmental roles are presentation-only and must not be attackable.
CAT_LAYOUT = (
    VisualActor("catOne", 2616, 4, (2, -1, 0), 1),
    VisualActor("catTwo", 2616, 4, (3, -2, 0), 3),
    VisualActor("catThree", 2616, 4, (6, -1, 1), 3),
    VisualActor("catFour", 2616, 4, (7, 0, 0), 5),
    VisualActor("catFive", 2616, 5, (10, -7, 0), 5),
    VisualActor("catSix", 2616, 5, (10, -5, 0), 1),
    VisualActor("catSeven", 2617, 5, (13, -8, 0), 3),
    VisualActor("catEight", 2616, 5, (14, -5, 0), 3),
    VisualActor("catNine", 2616, 5, (15, -7, 0), 1),
    VisualActor("catTen", 2616, 6, (20, -7, -11), 1),
    VisualActor("catEleven", 2617, 6, (22, -7, -11), 5),
    VisualActor("catBoss", 1816, 10, (21, -8, -11), 7),
)
# Tentacle coordinates are assigned verbatim by event23928. Nekark's center
# occupies the native three-by-three underwater body cells of this exterior.
NEKARK_LAYOUT = (
    VisualActor("nekark", 4135, 50, (154, 136, -4)),
    VisualActor("tentacleA", 4133, 45, (150, 132, -4)),
    VisualActor("tentacleB", 4133, 45, (155, 129, -4)),
    VisualActor("tentacleC", 4133, 45, (154, 140, -4)),
    VisualActor("tentacleD", 4133, 45, (157, 141, -4)),
)


def _identities(values, expected):
    values = tuple(values)
    if (
        len(values) != expected
        or len(set(values)) != expected
        or any(
            type(value) is not int or not -(2**53 - 1) <= value < 0 for value in values
        )
    ):
        raise ValueError(
            "Cat-house presentation requires unique owned actor identities"
        )
    return values


def packet(event_id, *arguments):
    """Encode cAU13411 with original signed64 actor arguments, without tags."""
    if type(event_id) is not int or event_id not in ARGUMENT_COUNTS:
        raise ValueError("Unqualified cat-house scenario event")
    identities = _identities(arguments, ARGUMENT_COUNTS[event_id])
    return 13411, struct.pack(
        ">BiiB", 0, event_id, SCENARIO_ID, len(identities)
    ) + b"".join(struct.pack(">q", identity) for identity in identities)


def bootstrap(cat_actor_ids):
    """Bind the original twelve visible roles; never create a combat roster."""
    return packet(BOOTSTRAP_EVENT, *_identities(cat_actor_ids, len(CAT_LAYOUT)))


def scene(event_id, player_id, *arguments):
    """Return the scene's required authoritative position and ordered packets.

    The caller persists ``position`` before publication.13530 brings the actor
    to that same location before the original Lua changes camera or animation.
    """
    if type(player_id) is not int or not 0 < player_id < 2**63:
        raise ValueError("Cat-house cinematic requires its player identity")
    presentation = packet(event_id, *arguments)
    position = PLAYER_POSITIONS.get(event_id)
    packets = []
    if position is not None:
        packets.append((13530, struct.pack(">qiihBi", player_id, *position, 3, -1)))
    packets.append(presentation)
    return {"position": position, "packets": tuple(packets)}


def visual_rows(layout, actor_ids):
    """Build noncombat native format11 rows, scoped to one owner's connection."""
    from wakfu_server.monsters import reference

    identities = _identities(actor_ids, len(layout))
    rows = []
    for native, identity in zip(layout, identities):
        monster = reference(native.reference_id)
        rows.append(
            {
                "actor_id": identity,
                "reference_id": native.reference_id,
                "map_id": MAP_ID,
                # Native NPC format11 has no instance field. These rows are only
                # encoded, never installed as public world placements.
                "instance_id": 0,
                **dict(zip(("x", "y", "z"), native.position)),
                "direction": native.direction,
                "level": native.level,
                "visual_id": monster["sprite_id"],
                "name_es": monster["name"],
                "native_action_ids": [],
                "source_sha256": LUA_SHA256,
            }
        )
    return tuple(rows)


def visual_packets(layout, actor_ids):
    from wakfu_server.npc_placements import spawn

    return tuple(spawn(row) for row in visual_rows(layout, actor_ids))


def remove_visuals(actor_ids):
    """Retire the owner's scene actors, including on abort and reconnect exits."""
    identities = tuple(actor_ids)
    _identities(identities, len(identities))
    if len(identities) > 255:
        raise ValueError("Too many cat-house presentation actors")
    # ctA removal: teleport flag, secondary flag, count, typed actor identities.
    return 12304, bytes((0, 0, len(identities))) + b"".join(
        struct.pack(">Bq", 1, identity) for identity in identities
    )


def nekark_scene(player_id, actor_ids):
    """Spawn five visual actors and run the native Goultard resolution scene.

    Nekark is resolved by the original cinematic; this creates no player fight.
    The orchestrator owns the callback23928 receipt and final transport.
    """
    identities = _identities(actor_ids, len(NEKARK_LAYOUT))
    result = scene(23928, player_id, *identities)
    return {
        **result,
        "actors": identities,
        # Hydrate the exterior partition before publishing its distant actors;
        # the native scene must begin only after all five identities exist.
        "packets": (
            *result["packets"][:-1],
            *visual_packets(NEKARK_LAYOUT, identities),
            result["packets"][-1],
        ),
    }
