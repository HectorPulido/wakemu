"""Captured initial combat placement for owner-qualified Rii lessons.

World coordinates remain unchanged. These positions are private to combat.
Line-of-sight uses one sack; its native area effects create the obstacles.
"""
from .rii_lesson_auto_start import KEYS

PLAYER = (0, -10, 0)
SACK = (0, -13, 0)
AREA = ((1, -13, 0), (0, -14, 0), (0, -12, 0), (-1, -13, 0))
SUPPORTED = frozenset((10574, 10575, 10576, 10608, 10609, 10610, 10611))
SCHEMA = "rii-observed-lesson-placement-v1"


def identify(db, character, monsters):
    """Admit only an exact owner receipt for each member of a lesson group."""
    if (character.get("map_id"), character.get("instance_id")) != (1388, 0):
        return None
    if not monsters or any(
        m.get("ref") != 5466 or type(m.get("id")) is not int or m["id"] >= 0
        for m in monsters
    ):
        return None
    for objective in SUPPORTED:
        if len(monsters) != (4 if objective == 10609 else 1):
            continue
        prefix, kind = KEYS[objective]
        for monster in monsters:
            actor = monster["id"]
            row = db.execute(
                "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (character["id"], prefix + str(-actor)),
            ).fetchone()
            expected = {
                "kind": kind,
                "owner": character["id"],
                "actor_id": actor,
                "ref": 5466,
            }
            if row is None or row["payload"] != expected:
                break
        else:
            return objective
    return None


def arena(character, monsters, objective, *, cell_budget, size_range):
    """Construct a native-terrain arena at positions seen in the official capture."""
    from wakfu_server.combat_terrain import local_arena, published_geometry

    if objective not in SUPPORTED or len(monsters) != (4 if objective == 10609 else 1):
        raise ValueError("Unsupported Rii lesson formation")
    targets = AREA if objective == 10609 else (SACK,)
    # All seven captures carry the same 11×11 map rectangle at z=0.
    floor = {
        cell
        for cell in published_geometry(1388).cells
        if -5 <= cell[0] <= 5 and -18 <= cell[1] <= -8 and cell[2] == 0
    }
    result = local_arena(
        1388,
        character["id"],
        PLAYER,
        list(targets),
        relocate_monsters=False,
        ordinary_npc_placement=True,
        allowed_cells=floor,
        automatic_cell_budget=cell_budget,
        size_range=size_range,
    )
    original = tuple(character[k] for k in ("x", "y", "z"))
    result["participant_positions"] = [
        (tuple(monster[k] for k in ("x", "y", "z")), destination)
        for monster, destination in zip(monsters, targets)
    ]
    result["participant_player_position"] = (original, PLAYER)
    result["native_rii_lesson_layout"] = {
        "schema": SCHEMA,
        "owner": character["id"],
        "objective": objective,
    }
    return result


def validated_player_position(character, arena):
    """Keep the capture-derived combat placement bound to its selected owner."""
    marker = arena.get("native_rii_lesson_layout")
    pair = arena.get("participant_player_position")
    if (
        not isinstance(marker, dict)
        or marker.get("schema") != SCHEMA
        or marker.get("owner") != character.get("id")
        or marker.get("objective") not in SUPPORTED
        or character.get("map_id") != 1388
        or character.get("instance_id") != 0
        or not isinstance(pair, (tuple, list))
        or len(pair) != 2
        or tuple(pair[0]) != tuple(character[k] for k in ("x", "y", "z"))
        or tuple(pair[1]) != PLAYER
        or PLAYER not in arena["validated_cells"]
        or PLAYER not in arena["placement_cells"][0]
    ):
        raise ValueError("Invalid Rii lesson placement")
    return PLAYER
