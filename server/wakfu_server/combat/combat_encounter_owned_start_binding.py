"""Explicit DB-frozen reconstruction of an external owned-START caster.

Native eZR.l/m(null) and child selectors are unchanged. Only an admitted
retained subscription can acquire its attested turn manager as caster.
"""
from copy import deepcopy
from functools import lru_cache


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(policy):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_owned_start_binding_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
    if row is None:
        raise ValueError("Unknown immutable owned START binding")
    result = dict(row)
    for key in (
        "monster_references",
        "native_parameters",
        "native_children",
        "native_effect_flags",
    ):
        result[key] = list(result[key])
    if (
        result["binding"] != "actual_owned_turn_manager_as_caster"
        or result["event_id"] != 1001
        or result["channel"] != 60
        or result["caster_code"] != 2
        or result["target_code"] != 2
        or result["effect_family"] != 330
        or result["selector_mask"] != 1
        or result["monster_references"] != sorted(set(result["monster_references"]))
        or result["boss_reference"] not in result["monster_references"]
        or len(result["catalog_revision"]) != 64
        or len(result["native_parameters"]) != 2 * result["parameter_count"]
    ):
        raise ValueError("Invalid immutable owned START binding")
    return result


def _same_sequence(actual, expected):
    """Accept raw/compiled containers without coercing values or their types."""
    if not isinstance(actual, (list, tuple)) or not isinstance(expected, (list, tuple)):
        return False
    if len(actual) != len(expected):
        return False
    return all(
        _same_sequence(left, right)
        if isinstance(right, (list, tuple))
        else type(left) is type(right) and left == right
        for left, right in zip(actual, expected)
    )


def _same_record(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same_record(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_record(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def binding_from_record(record):
    if not isinstance(record, dict) or not _same_record(
        record, _version(record.get("policy"))
    ):
        raise ValueError("Frozen owned START binding changed")
    return deepcopy(record)


def freeze_owned_start_binding(fight, *, roles):
    from wakfu_server import native_catalog

    if fight.phase != "placement":
        raise ValueError("Owned START binding requires fresh placement")
    if hasattr(fight, "native_encounter_owned_start_binding"):
        previous = fight.native_encounter_owned_start_binding
        frozen = None if previous is None else binding_from_record(previous)
    else:
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_owned_start_binding_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Owned START binding differs from admission or catalog")
    fight.native_encounter_owned_start_binding = frozen
    return deepcopy(frozen)


def owned_start_caster(fight, source, *, entry, original, definition, effect):
    """Return an explicitly reconstructed caster or None; never create a Qe."""
    frozen = getattr(fight, "native_encounter_owned_start_binding", None)
    if frozen is None:
        return None  # Historical/explicit None admissions do not gain a policy.
    frozen = binding_from_record(frozen)
    if original.reference != frozen["listener_reference"]:
        return None
    from .combat_event_replay import NativeExternalEvent

    if not isinstance(source, NativeExternalEvent):
        return None
    context = source.turn_boundary_context
    if (
        source.event_ids != (frozen["event_id"],)
        or source.channel != frozen["channel"]
        or not isinstance(context, dict)
        or context.get("phase") != "start"
    ):
        return None
    from .combat_external_turn_recipient import qualified_boundary_actor
    from .combat_encounter_roles import frozen_roles

    participant = qualified_boundary_actor(fight, turn_context=context)
    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Owned START binding escaped frozen encounter scope")
    if (
        effect.get("effect_class") != frozen["effect_family"]
        or effect.get("native_target_selector")
        != {"class": "fcE", "mask": frozen["selector_mask"]}
        or not _same_sequence(effect.get("parameters"), frozen["native_parameters"])
        or not _same_sequence(effect.get("children"), frozen["native_children"])
        or effect.get("criteria") != frozen["criterion"]
        or effect.get("area_class") != frozen["area_class"]
        or effect.get("parameter_count") != frozen["parameter_count"]
        or not _same_sequence(
            effect.get("native_effect_flags"), frozen["native_effect_flags"]
        )
        or effect.get("native_execution_mode") != frozen["native_execution_mode"]
        or not _same_sequence(
            effect.get("target_masks"),
            [None, None, None, None, None, [frozen["event_id"]], None],
        )
        or definition.get("subscription") is not True
        or definition.get("event_reverse_subscription") is not True
        or definition.get("event_global_subscription") is not False
        or definition.get("owner_on_caster") is not False
        or definition.get("event_execution_count") != -1
        or definition.get("event_execution_count_per_level") != 0
        or definition.get("event_caster_code") != frozen["caster_code"]
        or definition.get("event_target_code") != frozen["target_code"]
    ):
        raise ValueError("Original owned START subscription descriptor changed")
    if (
        participant is None
        or participant.controlled is not True
        or participant.hp <= 0
        or participant.team != roles.player_team
        or type(participant.owner_id) is not int
        or participant.owner_id <= 0
        or getattr(participant, "native_summon_source", None) is not None
        or participant.id in getattr(fight, "native_summon_registrations", {})
        or any(
            row.get("id") == participant.id
            for row in getattr(fight, "native_companion_sources", {}).values()
        )
        or source.manager_actor_id != participant.id
        or entry.manager_id != participant.id
        or original.target_id != participant.id
        or entry.generic_effect != original.reference
    ):
        raise ValueError("Owned START binding lacks its actual owned participant")
    boss = fight.actors.get(original.caster_id)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        original.caster_id, {}
    )
    if (
        boss is None
        or boss.controlled
        or boss.team != roles.npc_team
        or receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == frozen["boss_constructor_state"]
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Owned START binding lacks its original native boss")
    states = participant.state_ledger.entries
    if not any(
        state.uid == original.state_uid
        and state.reference == frozen["carrier_state"]
        and state.target_id == participant.id
        and state.caster_id == boss.id
        and original.reference in state.effect_ids
        for state in states
    ):
        raise ValueError("Owned START binding lacks its original carrier state UID")
    retained = getattr(fight, "native_owned_group_effects", {}).get(entry.uid)
    if (
        not isinstance(retained, dict)
        or retained.get("invocation", {}).get("state_uid") != original.state_uid
        or retained.get("invocation", {}).get("reference") != original.reference
        or retained.get("invocation", {}).get("caster_id") != boss.id
        or retained.get("invocation", {}).get("target_id") != participant.id
    ):
        raise ValueError("Owned START binding lacks its retained listener UID")
    key = f"{frozen['policy']}:{fight.turn_id}:{participant.id}:{entry.uid}"
    journal = getattr(fight, "native_owned_start_caster_deliveries", {})
    if key in journal:
        raise ValueError("Owned START caster binding already consumed")
    fight.native_owned_start_caster_deliveries = {
        **journal,
        key: dict(
            policy=frozen["policy"],
            turn_id=fight.turn_id,
            actor_id=participant.id,
            listener_uid=entry.uid,
            state_uid=original.state_uid,
            original_caster=boss.id,
            reconstructed_caster=participant.id,
        ),
    }
    return participant.id
