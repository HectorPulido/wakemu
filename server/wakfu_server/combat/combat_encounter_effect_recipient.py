"""Versioned encounter reconstruction of a descendant's original boss recipient.

This changes only a qualified invocation. Native Qe, selectors, definitions,
retained source rows and ordinary chosen-PV behavior remain untouched.
"""

from .combat_encounter_source_revision import source_revision_matches

SOURCE_DEPENDENCIES = (
    "combat-state-definitions.json",
    "native-retained-effect-metadata.json",
    "native-direct-target-policies.json",
)
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(policy):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_effect_recipient_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
        rules = (
            [
                dict(item)
                for item in db.execute(
                    "SELECT * FROM encounter_effect_recipient_rules WHERE policy=%s ORDER BY effect_reference",
                    (policy,),
                ).fetchall()
            ]
            if row is not None
            else []
        )
    if row is None:
        raise ValueError("Unknown immutable encounter effect recipient policy")
    result = dict(row)
    for key in ("monster_references", "effect_references"):
        result[key] = list(result[key])
    if (
        result["mode"] != "ORIGINAL_BOSS_RECIPIENT"
        or not result["authority"]
        or len(result["catalog_revision"]) != 64
        or not result["effect_references"]
        or not rules
        or result["effect_references"] != sorted(set(result["effect_references"]))
        or [rule["effect_reference"] for rule in rules] != result["effect_references"]
    ):
        raise ValueError("Invalid encounter effect recipient inventory")
    for rule in rules:
        for key in ("native_parameters", "native_children", "native_effect_flags"):
            rule[key] = list(rule[key])
        if (
            rule["effect_family"] not in (304, 321)
            or rule["selector_mask"] != 8200
            or rule["area_class"] != "anD"
            or rule["channel"] != 60
            or (rule["phase"], rule["event_id"])
            not in (("end", 1002), ("regeneration", 1037))
            or len(rule["native_parameters"]) != 2 * rule["parameter_count"]
        ):
            raise ValueError("Invalid encounter effect recipient rule")
    result["rules"] = rules
    return result


def _matches_effect(rule, effect):
    from .combat_encounter_owned_start_binding import _same_sequence

    return (
        effect.get("effect_class") == rule["effect_family"]
        and effect.get("native_target_selector")
        == {"class": "fcE", "mask": rule["selector_mask"]}
        and effect.get("area_class") == rule["area_class"]
        and effect.get("criteria") == rule["criterion"]
        and effect.get("parameter_count") == rule["parameter_count"]
        and effect.get("native_execution_mode") == rule["native_execution_mode"]
        and _same_sequence(effect.get("parameters"), rule["native_parameters"])
        and _same_sequence(effect.get("children"), rule["native_children"])
        and _same_sequence(
            effect.get("native_effect_flags"), rule["native_effect_flags"]
        )
    )


def _frozen(fight):
    from .combat_encounter_owned_start_binding import _same_record

    row = getattr(fight, "native_encounter_effect_recipient_policy", None)
    if row is not None and (
        not isinstance(row, dict) or not _same_record(row, _version(row.get("policy")))
    ):
        raise ValueError("Frozen encounter effect recipient policy changed")
    return row


def freeze_effect_recipient_policy(fight, *, roles):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    if fight.phase != "placement":
        raise ValueError("Encounter effect recipient requires fresh placement")
    if hasattr(fight, "native_encounter_effect_recipient_policy"):
        row = _frozen(fight)
    else:
        with _database().connection() as db:
            active = db.execute(
                "SELECT policy FROM encounter_effect_recipient_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        row = None if active is None else deepcopy(_version(active["policy"]))
    if row is not None:
        if (
            row["map_id"] != roles.map_id
            or row["monster_references"] != list(roles.monster_references)
            or not source_revision_matches(row["catalog_revision"], SOURCE_DEPENDENCIES)
        ):
            raise ValueError("Encounter effect recipient differs from admission")
        carrier = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "states", row["carrier_state"]
        )
        if not carrier or row["source_start_listener"] not in carrier.get(
            "effect_ids", ()
        ):
            raise ValueError(
                "Encounter effect recipient lacks its native source carrier"
            )
        for rule in row["rules"]:
            effect = native_catalog.record(
                DATA_ROOT / "combat-state-definitions.json",
                "effects",
                rule["effect_reference"],
            )
            direct = native_catalog.record(
                DATA_ROOT / "native-direct-target-policies.json",
                "effects",
                rule["effect_reference"],
            )
            parent = native_catalog.record(
                DATA_ROOT / "combat-state-definitions.json",
                "effects",
                rule["parent_reference"],
            )
            if (
                not effect
                or not _matches_effect(rule, effect)
                or direct != [rule["effect_family"], False, False]
                or not parent
                or rule["effect_reference"] not in parent.get("children", ())
                or rule["event_id"] not in (parent["target_masks"][5] or ())
            ):
                raise ValueError("Encounter recipient differs from original descendant")
    fight.native_encounter_effect_recipient_policy = deepcopy(row)
    return deepcopy(row)


def rebind_original_boss_recipient(dispatcher, effect, invocation, ancestors):
    """Reconstruct only an attested descendant of this owned boundary clone."""
    fight = dispatcher.native_retention.fight
    frozen = _frozen(fight)
    if frozen is None:
        return invocation
    rule = next(
        (
            item
            for item in frozen["rules"]
            if item["effect_reference"] == invocation.reference
        ),
        None,
    )
    if rule is None:
        return invocation
    activation = dispatcher._active_activation
    if activation is None:
        return invocation
    parent, source, _condition, _allocate = activation
    if (
        parent.reference != rule["parent_reference"]
        or parent.reference not in ancestors
    ):
        return invocation
    from .combat_event_replay import NativeExternalEvent
    from .combat_external_turn_recipient import qualified_boundary_actor
    from wakfu_server.combat_encounter_roles import frozen_roles
    from .combat_encounter_owned_start_binding import binding_from_record

    context = invocation.native_turn_boundary_context
    if (
        not isinstance(source, NativeExternalEvent)
        or source.event_ids != (rule["event_id"],)
        or source.channel != rule["channel"]
        or not isinstance(context, dict)
        or context.get("phase") != rule["phase"]
        or source.turn_boundary_context != context
    ):
        return invocation
    participant = qualified_boundary_actor(fight, turn_context=context)
    roles = frozen_roles(fight)
    binding = getattr(fight, "native_encounter_owned_start_binding", None)
    if (
        binding is None
        or binding_from_record(binding)["policy"] != frozen["start_binding_policy"]
    ):
        raise ValueError("Encounter recipient lacks its frozen owned START producer")
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
        or participant is None
        or participant.controlled is not True
        or participant.hp <= 0
        or participant.team != roles.player_team
        or participant.id != source.manager_actor_id
        or type(participant.owner_id) is not int
        or participant.owner_id <= 0
        or participant.id in getattr(fight, "native_summon_registrations", {})
        or any(
            row.get("id") == participant.id
            for row in getattr(fight, "native_companion_sources", {}).values()
        )
        or invocation.caster_id != participant.id
        or invocation.target_id != participant.id
        or parent.caster_id != participant.id
        or parent.target_id != participant.id
        or parent.state_uid != invocation.state_uid
        or invocation.native_explicit_target is not True
        or invocation.native_trigger_context is not None
        or parent.native_trigger_context is not None
        or not _matches_effect(rule, effect)
    ):
        raise ValueError("Encounter recipient escaped its original owned descendant")
    carrier = next(
        (
            state
            for state in participant.state_ledger.entries
            if state.uid == invocation.state_uid
            and state.reference == frozen["carrier_state"]
            and state.target_id == participant.id
            and frozen["source_start_listener"] in state.effect_ids
        ),
        None,
    )
    if carrier is None:
        raise ValueError("Encounter recipient lacks its original carrier UID")
    boss = fight.actors.get(carrier.caster_id)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        carrier.caster_id, {}
    )
    retained = getattr(fight, "native_owned_group_effects", {}).get(parent.base_uid, {})
    original = retained.get("invocation", {})
    if (
        boss is None
        or boss.controlled
        or boss.team != roles.npc_team
        or receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
        or not any(
            item.get("state_id") == frozen["boss_constructor_state"]
            for item in receipt.get("resolved_states", ())
        )
        or original.get("reference") != parent.reference
        or original.get("state_uid") != carrier.uid
        or original.get("caster_id") != participant.id
        or original.get("target_id") != participant.id
    ):
        raise ValueError(
            "Encounter recipient lacks its original boss or retained caller"
        )
    start_proofs = getattr(fight, "native_owned_start_caster_deliveries", {}).values()
    if not any(
        row.get("policy") == frozen["start_binding_policy"]
        and row.get("turn_id") == fight.turn_id
        and row.get("actor_id") == participant.id
        and row.get("state_uid") == carrier.uid
        and row.get("original_caster") == boss.id
        and row.get("reconstructed_caster") == participant.id
        for row in start_proofs
    ):
        raise ValueError("Encounter recipient lacks the actual owned START lineage")
    key = f"{frozen['policy']}:{fight.turn_id}:{participant.id}:{parent.base_uid}:{invocation.reference}"
    journal = getattr(fight, "native_encounter_effect_recipient_deliveries", {})
    if key in journal:
        raise ValueError("Encounter descendant recipient already consumed")
    fight.native_encounter_effect_recipient_deliveries = {
        **journal,
        key: dict(
            policy=frozen["policy"],
            actor_id=participant.id,
            turn_id=fight.turn_id,
            state_uid=carrier.uid,
            parent_uid=parent.base_uid,
            parent_reference=parent.reference,
            effect_reference=invocation.reference,
            original_target=participant.id,
            reconstructed_target=boss.id,
        ),
    }
    return replace(invocation, target_id=boss.id, cell=tuple(boss.position))
