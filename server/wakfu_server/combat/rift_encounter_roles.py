"""Scoped native Rift constructor roles from frozen SQL policy.

Original orb criteria use player affiliation1 and enemy affiliation0. The
original server role constructor is unavailable: this explicit Wakemu policy
uses the existing EncounterRoles path, before actors or placement are built.
It never changes an actor's team or overrides a criterion after construction.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import json

from wakfu_server.combat_encounter_roles import EncounterRoles, _ordinary, _scope

SCHEMA = "wakemu-rift-encounter-roles-v1"
POLICY = "wakemu.rift.ultimate-encounter-roles.v1"
AUTHORITY = "SQL.rift_native_gameplay_policy.original-consumer-role-reconstruction"
ULTIMATE = "ULTIMATE_INFINITE_WAVE"
_FIELDS = frozenset(
    (
        "schema",
        "policy",
        "authority",
        "map_id",
        "monster_references",
        "player_team",
        "npc_team",
        "rift_scope",
    )
)


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class RiftEncounterRoles(EncounterRoles):
    frozen_scope_json: str

    def record(self):
        result = super().record()
        result["schema"] = SCHEMA
        result["rift_scope"] = json.loads(self.frozen_scope_json)
        return result


def _native_policy(catalog, policy):
    if not isinstance(catalog, Mapping) or catalog.get("type") not in (
        "INFINITE_WAVE",
        ULTIMATE,
    ):
        return None
    if not isinstance(policy, Mapping):
        raise ValueError("Ultimate Rift roles require their frozen SQL policy")
    native = policy.get("native_gameplay")
    if native is None:
        return None
    if not isinstance(native, Mapping):
        raise ValueError("Invalid frozen native Rift gameplay policy")
    if native.get("enabled") is not True:
        return None
    from wakfu_server.rift_native_gameplay_policy import POLICY as GAMEPLAY_POLICY

    kinds = native.get("enabled_types")
    if (
        native.get("policy") != GAMEPLAY_POLICY
        or native.get("authority") != "native_consumers_with_reconstructed_producers"
        or not isinstance(kinds, (tuple, list))
        or not kinds
        or any(
            type(kind) is not str or kind not in ("INFINITE_WAVE", ULTIMATE)
            for kind in kinds
        )
        or len(set(kinds)) != len(kinds)
    ):
        raise ValueError("Unreviewed Ultimate Rift role policy scope")
    if catalog["type"] not in kinds:
        return None
    roles = native.get("encounter_roles")
    if (
        not isinstance(roles, Mapping)
        or set(roles) != {"policy", "player_team", "npc_team"}
        or roles.get("policy") != POLICY
        or type(roles.get("player_team")) is not int
        or type(roles.get("npc_team")) is not int
        or (roles["player_team"], roles["npc_team"]) != (1, 0)
    ):
        raise ValueError("Ultimate Rift roles lack their reviewed constructor contract")
    return native


def roles_for_catalog(catalog, policy, *, monster_references=None):
    """Return constructor sides, optionally bound to the exact initial roster.

    Before NPC allocation, callers may request only player_team/npc_team. Such
    an unscoped object cannot produce a record. Supply actual initial refs to
    freeze the record consumed by placement, bootstrap and durable admission.
    Types excluded by the frozen policy retain the ordinary0/1 constructor.
    This includes historical classic runs admitted before native activation.
    """
    native = _native_policy(catalog, policy)
    references = () if monster_references is None else tuple(monster_references)
    map_id = catalog.get("map_id") if isinstance(catalog, Mapping) else None
    if references:
        references = _scope(map_id, references)
    if native is None:
        return _ordinary(map_id if references else None, references)
    from wakfu_server.rift_policy import species_pools

    original_species, milestone_species = species_pools(catalog)
    species = list(dict.fromkeys((*original_species, *milestone_species)))
    if (
        type(map_id) is not int
        or map_id <= 0
        or not isinstance(species, (tuple, list))
        or not species
        or any(type(reference) is not int or reference <= 0 for reference in species)
        or any(reference not in species for reference in references)
    ):
        raise ValueError("Ultimate Rift role roster differs from its original catalog")
    scope = dict(
        catalog=dict(type=catalog["type"], map_id=map_id, species_refs=sorted(species)),
        native_gameplay=_plain(native),
    )
    return RiftEncounterRoles(
        POLICY,
        AUTHORITY,
        map_id if references else None,
        references,
        1,
        0,
        json.dumps(scope, sort_keys=True, separators=(",", ":"), allow_nan=False),
    )


def roles_from_record(record, *, map_id=None, monster_references=None):
    """Validate the frozen type/catalog/SQL role contract without active lookup."""
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or record.get("schema") != SCHEMA
        or record.get("policy") != POLICY
        or record.get("authority") != AUTHORITY
        or type(record.get("map_id")) is not int
        or type(record.get("player_team")) is not int
        or type(record.get("npc_team")) is not int
        or not isinstance(record.get("monster_references"), list)
    ):
        raise ValueError("Invalid frozen Ultimate Rift encounter roles")
    scope = record.get("rift_scope")
    if (
        not isinstance(scope, dict)
        or set(scope) != {"catalog", "native_gameplay"}
        or not isinstance(scope["catalog"], dict)
        or set(scope["catalog"]) != {"type", "map_id", "species_refs"}
    ):
        raise ValueError("Missing frozen Ultimate Rift SQL/catalog scope")
    expected = roles_for_catalog(
        scope["catalog"],
        {"native_gameplay": scope["native_gameplay"]},
        monster_references=record["monster_references"],
    )
    if type(expected) is not RiftEncounterRoles or record != expected.record():
        raise ValueError("Frozen Ultimate Rift roles differ from their reviewed scope")
    if map_id is not None and map_id != expected.map_id:
        raise ValueError("Ultimate Rift roles belong to another map")
    if (
        monster_references is not None
        and _scope(expected.map_id, monster_references) != expected.monster_references
    ):
        raise ValueError("Ultimate Rift roles belong to another initial roster")
    return expected


def prepare_rift_arena(character, members, arena, catalog, policy):
    """Bind enabled native Rift roles before scene/placement/actor construction."""
    from wakfu_server.combat_encounter_scene_layout import apply_role_assignment

    roles = roles_for_catalog(
        catalog, policy, monster_references=[member["ref"] for member in members]
    )
    if type(roles) is not RiftEncounterRoles:
        return arena  # Preserve the ordinary scene's existing admission path.
    if character.get("map_id") != roles.map_id or arena.get("map_id") != roles.map_id:
        raise ValueError("Ultimate Rift actors and native arena belong to another map")
    return apply_role_assignment(arena, roles)
