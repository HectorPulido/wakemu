"""Owned Grougaloragran encounter recovered from the official Rii capture.

The ordinary native NPC constructor owns state 8018, its illusion summons and
its lethal finisher. This module binds placement and presentation identity; it
does not alter HP, class spells, native spell effects or the battle outcome.
"""

SCHEMA = "wakemu-native-rii-guardian-v1"
POLICY = "wakemu-rii-guardian-player1-npc0-v1"
AUTHORITY = "official-incarnam-20261112-guardian-12985-12987"
MODEL = 71
TERRAIN = 378
PLACEMENT_DURATION_MS = 600000
REFERENCE = 5458
LEVEL = 300
PLAYER = (-8, 0, 0)
TARGET = (-16, 0, 0)
WORLD_TARGET = (-12, 0, 2)


def _validate(contract):
    if (
        not isinstance(contract, dict)
        or set(contract) != {"schema", "owner", "target"}
        or contract.get("schema") != SCHEMA
        or type(contract.get("owner")) is not int
        or contract["owner"] <= 0
        or type(contract.get("target")) is not int
        or contract["target"] >= 0
    ):
        raise ValueError("Invalid owned native Rii guardian contract")
    return contract


def identify(db, character, monsters):
    """Only an exact owner receipt can select the special model and team roles."""
    if (character.get("map_id"), character.get("instance_id", 0)) != (1387, 0) or len(
        monsters
    ) != 1:
        return None
    monster = monsters[0]
    target = monster.get("id")
    if monster.get("ref") != REFERENCE or type(target) is not int or target >= 0:
        return None
    row = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character["id"], f"rii-guardian-actor:{-target}"),
    ).fetchone()
    if row is None:
        return None
    expected = {
        "kind": "reconstructed_rii_guardian_actor",
        "owner": character["id"],
        "actor_id": target,
        "ref": REFERENCE,
    }
    if row["payload"] != expected:
        raise ValueError("Guardian receipt differs from its exact native owner")
    if monster.get("level") != LEVEL:
        raise ValueError("Owned guardian requires its captured native level 300")
    return _validate({"schema": SCHEMA, "owner": character["id"], "target": target})


def roles_record():
    from wakfu_server.combat_encounter_roles import EncounterRoles

    return EncounterRoles(POLICY, AUTHORITY, 1387, (REFERENCE,), 1, 0).record()


def arena(character, monsters, contract, *, cell_budget, size_range):
    """Use captured cells and native map heights, rather than adjacent staging."""
    from wakfu_server.combat_terrain import local_arena, published_geometry

    _validate(contract)
    if (
        character["id"] != contract["owner"]
        or len(monsters) != 1
        or monsters[0]["id"] != contract["target"]
        or monsters[0]["ref"] != REFERENCE
        or monsters[0]["level"] != LEVEL
        or (character["map_id"], character.get("instance_id", 0)) != (1387, 0)
    ):
        raise ValueError("Native guardian placement lost its owned roster")
    floor = {
        cell
        for cell in published_geometry(1387).cells
        if -18 <= cell[0] <= -6 and -5 <= cell[1] <= 5
    }
    result = local_arena(
        1387,
        character["id"],
        PLAYER,
        [TARGET],
        relocate_monsters=False,
        ordinary_npc_placement=True,
        allowed_cells=floor,
        automatic_cell_budget=cell_budget,
        size_range=size_range,
    )
    original = tuple(character[key] for key in ("x", "y", "z"))
    monster = monsters[0]
    result.update(
        native_rii_guardian_layout=dict(contract),
        native_encounter_roles=roles_record(),
        native_fight_model=MODEL,
        terrain_effect_id=TERRAIN,
        participant_player_position=(original, PLAYER),
        participant_positions=[
            (tuple(monster[key] for key in ("x", "y", "z")), TARGET)
        ],
        placement_cells={
            1: set(result["placement_cells"][0]),
            0: set(result["placement_cells"][1]),
        },
    )
    return result


def validated_player_position(character, arena):
    contract = _validate(arena.get("native_rii_guardian_layout"))
    pair = arena.get("participant_player_position")
    if (
        contract["owner"] != character.get("id")
        or (character.get("map_id"), character.get("instance_id", 0)) != (1387, 0)
        or not isinstance(pair, (list, tuple))
        or len(pair) != 2
        or tuple(pair[0]) != tuple(character[key] for key in ("x", "y", "z"))
        or tuple(pair[1]) != PLAYER
        or PLAYER not in arena["validated_cells"]
        or PLAYER not in arena["placement_cells"][1]
        or arena.get("native_encounter_roles") != roles_record()
    ):
        raise ValueError("Native guardian player placement changed its authority")
    return PLAYER


def bind(fight, contract):
    _validate(contract)
    owner, target = contract["owner"], contract["target"]
    if (
        getattr(fight, "native_fight_model", None) != MODEL
        or owner not in fight.actors
        or target not in fight.actors
        or fight.actors[owner].controlled is not True
        or fight.actors[owner].team != 1
        or fight.actors[target].team != 0
        or fight.actors[target].effective_level != LEVEL
        or tuple(fight.actors[owner].position) != PLAYER
        or tuple(fight.actors[target].position) != TARGET
    ):
        raise ValueError("Native guardian fight differs from its captured admission")
    fight.rii_guardian_contract = dict(contract)
    return fight.rii_guardian_contract


def is_owned(fight, character_id):
    contract = getattr(fight, "rii_guardian_contract", None)
    if contract is None:
        return False
    _validate(contract)
    return (
        getattr(fight, "native_fight_model", None) == MODEL
        and contract["owner"] == character_id
        and character_id in fight.actors
        and contract["target"] in fight.actors
        and fight.actors[character_id].controlled is True
        and fight.actors[character_id].team == 1
        and fight.actors[contract["target"]].team == 0
    )
