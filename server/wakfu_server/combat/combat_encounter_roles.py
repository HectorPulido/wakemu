"""Versioned encounter roles shared by arena, actor and durable admission.

Content assignments are explicit database-backed Wakemu reconstructions. Native
criteria stay unchanged; a committed fight retains its immutable policy version.
"""
from dataclasses import dataclass
from functools import lru_cache

SCHEMA = "wakemu-encounter-roles-v1"
ORDINARY_POLICY = "wakemu-ordinary-player0-npc1-v1"
_RECORD_FIELDS = frozenset(
    (
        "schema",
        "policy",
        "authority",
        "map_id",
        "monster_references",
        "player_team",
        "npc_team",
    )
)


@dataclass(frozen=True)
class EncounterRoles:
    policy: str
    authority: str
    map_id: int | None
    monster_references: tuple
    player_team: int
    npc_team: int

    def record(self):
        if self.map_id is None or not self.monster_references:
            raise ValueError("Unscoped default roles cannot be frozen as an encounter")
        return dict(
            schema=SCHEMA,
            policy=self.policy,
            authority=self.authority,
            map_id=self.map_id,
            monster_references=list(self.monster_references),
            player_team=self.player_team,
            npc_team=self.npc_team,
        )

    def placement_cells(self, player_cells, npc_cells):
        """Supply role-keyed inputs before the native arena mask is encoded."""
        players = {tuple(cell) for cell in player_cells}
        npcs = {tuple(cell) for cell in npc_cells}
        if (
            not players
            or not npcs
            or players & npcs
            or any(
                len(cell) != 3 or any(type(value) is not int for value in cell)
                for cell in players | npcs
            )
        ):
            raise ValueError("Encounter roles require distinct native placement cells")
        return {self.player_team: players, self.npc_team: npcs}


def _scope(map_id, monster_references):
    references = tuple(monster_references)
    if (
        type(map_id) is not int
        or not -(1 << 31) <= map_id < 1 << 31
        or not references
        or any(type(value) is not int or value <= 0 for value in references)
    ):
        raise ValueError("Native encounter map and initial NPC references required")
    return tuple(sorted(references))


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


def _active_policy(map_id, references):
    with _database().connection() as db:
        row = db.execute(
            "SELECT policy FROM encounter_role_active "
            "WHERE map_id=%s AND monster_references=%s::integer[]",
            (map_id, list(references)),
        ).fetchone()
    return None if row is None else row["policy"]


@lru_cache(maxsize=256)
def _version(policy):
    """Cache only immutable definitions; never cache active admission pointers."""
    with _database().connection() as db:
        row = db.execute(
            "SELECT policy,authority,map_id,monster_references,player_team,npc_team "
            "FROM encounter_role_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
    if row is None:
        raise ValueError("Unknown frozen encounter role policy version")
    references = _scope(row["map_id"], row["monster_references"])
    if (
        not isinstance(row["policy"], str)
        or not row["policy"]
        or row["policy"] != policy
        or policy == ORDINARY_POLICY
        or not isinstance(row["authority"], str)
        or not row["authority"]
        or tuple(row["monster_references"]) != references
        or type(row["player_team"]) is not int
        or type(row["npc_team"]) is not int
        or {row["player_team"], row["npc_team"]} != {0, 1}
    ):
        raise ValueError("Malformed immutable encounter role policy")
    return EncounterRoles(
        policy,
        row["authority"],
        row["map_id"],
        references,
        row["player_team"],
        row["npc_team"],
    )


def _ordinary(map_id, references):
    return EncounterRoles(
        ORDINARY_POLICY,
        "ordinary-existing-constructor-role-policy",
        map_id,
        references,
        0,
        1,
    )


def role_assignment(map_id, monster_references):
    """Read the active policy only for a new exact-scope admission."""
    references = _scope(map_id, monster_references)
    policy = _active_policy(map_id, references)
    if policy is None:
        return _ordinary(map_id, references)
    roles = _version(policy)
    if (roles.map_id, roles.monster_references) != (map_id, references):
        raise ValueError("Active encounter role policy belongs to another scope")
    return roles


def roles_from_record(record, *, map_id=None, monster_references=None):
    """Reject drifted or forged role data before reconstructing a live actor."""
    if (
        not isinstance(record, dict)
        or set(record) != _RECORD_FIELDS
        or record["schema"] != SCHEMA
        or not isinstance(record["monster_references"], list)
        or type(record["player_team"]) is not int
        or type(record["npc_team"]) is not int
    ):
        raise ValueError("Invalid frozen encounter role record")
    references = _scope(record["map_id"], record["monster_references"])
    if not isinstance(record["policy"], str) or not record["policy"]:
        raise ValueError("Invalid frozen encounter role policy")
    expected = (
        _ordinary(record["map_id"], references)
        if record["policy"] == ORDINARY_POLICY
        else _version(record["policy"])
    )
    if record != expected.record():
        raise ValueError("Frozen encounter roles differ from the reviewed native scope")
    if map_id is not None and map_id != expected.map_id:
        raise ValueError("Frozen encounter roles belong to another map")
    if (
        monster_references is not None
        and tuple(sorted(monster_references)) != expected.monster_references
    ):
        raise ValueError("Frozen encounter roles belong to another initial roster")
    return expected


def frozen_roles(fight):
    record = getattr(fight, "native_encounter_roles", None)
    return None if record is None else roles_from_record(record)


def assigned_roles(fight):
    """Read strict frozen roles, or the unchanged unscoped legacy0/1 default."""
    roles = frozen_roles(fight)
    if roles is not None:
        return roles
    return _ordinary(None, ())


def validate_participant_role(fight, actor, *, player):
    """Fresh heroes/PCs/companions inherit the durable player side unchanged."""
    if type(player) is not bool:
        raise ValueError("Explicit encounter participant role required")
    roles = frozen_roles(fight)
    if roles is None:
        return  # Legacy fights and consented duels retain their existing teams.
    expected = roles.player_team if player else roles.npc_team
    if actor.team != expected:
        raise ValueError("Participant team differs from the frozen encounter role")


def bind_roles(fight, roles, *, player_ids, npc_ids):
    """Validate already-created teams and publish plain metadata before Ready.

    This function never retags actors, swaps teams after construction, or
    fabricates an alternate affiliation. The caller must have encoded the
    same role-keyed placement in its actual arena.
    """
    if (
        not isinstance(roles, EncounterRoles)
        or roles_from_record(roles.record()) != roles
    ):
        raise ValueError("Reviewed native encounter role assignment required")
    players, npcs = tuple(player_ids), tuple(npc_ids)
    if (
        fight.phase != "placement"
        or not players
        or not npcs
        or len(set((*players, *npcs))) != len(players) + len(npcs)
        or set((*players, *npcs)) != set(fight.actors)
    ):
        raise ValueError("Role binding requires the exact fresh participant roster")
    previous = getattr(fight, "native_encounter_roles", None)
    if previous is not None and previous != roles.record():
        raise ValueError("Encounter role assignment was already frozen differently")
    for identities, team in ((players, roles.player_team), (npcs, roles.npc_team)):
        if any(fight.actors[identity].team != team for identity in identities):
            raise ValueError("Actor was constructed on the wrong encounter side")
        if team not in fight.placement or any(
            fight.actors[identity].position not in fight.placement[team]
            for identity in identities
        ):
            raise ValueError("Actor placement differs from its encoded encounter side")
    fight.native_encounter_roles = roles.record()
    from .combat_encounter_area_activation import freeze_encounter_area_policy

    freeze_encounter_area_policy(fight, roles=roles)
    from .combat_encounter_group_selection import freeze_group_population_policy

    freeze_group_population_policy(fight, roles=roles)
    from .combat_encounter_table_listeners import freeze_encounter_table_listener_policy

    freeze_encounter_table_listener_policy(fight, roles=roles)
    from .combat_encounter_turn_end_order import freeze_turn_end_order_policy

    freeze_turn_end_order_policy(fight, roles=roles)
    from .combat_encounter_recipient_binding import (
        freeze_encounter_recipient_binding_policy,
    )

    freeze_encounter_recipient_binding_policy(fight, roles=roles)
    from .combat_encounter_owned_start_binding import freeze_owned_start_binding

    freeze_owned_start_binding(fight, roles=roles)
    from .combat_encounter_effect_recipient import freeze_effect_recipient_policy

    freeze_effect_recipient_policy(fight, roles=roles)
    from .combat_encounter_event_population import freeze_event_population_policy

    freeze_event_population_policy(fight, roles=roles)
    from .combat_encounter_movement_binding import freeze_movement_binding

    freeze_movement_binding(fight, roles=roles)
    from .combat_encounter_npc_start_binding import freeze_npc_start_binding

    freeze_npc_start_binding(fight, roles=roles)
    from .combat_encounter_area_callback_programs import (
        freeze_encounter_area_callback_programs,
    )

    freeze_encounter_area_callback_programs(fight, roles=roles)
    from .combat_encounter_terminal_cleanup import freeze_terminal_cleanup_policy

    freeze_terminal_cleanup_policy(fight, roles=roles)
    return roles
