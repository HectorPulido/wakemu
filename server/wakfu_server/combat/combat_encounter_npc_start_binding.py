"""Explicit DB-frozen reconstruction of an external owned-NPC-START caster.

Native eZR.l/m(null) and child selectors are unchanged. Only an admitted
retained subscription can acquire its attested owned NPC turn manager as caster.
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
            "SELECT * FROM encounter_npc_start_binding_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
        effects = db.execute(
            "SELECT * FROM encounter_npc_start_binding_effects WHERE policy=%s "
            "ORDER BY listener_reference",
            (policy,),
        ).fetchall()
    if row is None:
        raise ValueError("Unknown immutable owned NPC START binding")
    result = dict(row)
    for key in ("monster_references", "effect_references"):
        result[key] = list(result[key])
    result["effects"] = []
    for effect in effects:
        effect = dict(effect)
        effect.pop("policy")
        for key in ("native_parameters", "native_children", "native_effect_flags"):
            effect[key] = list(effect[key])
        if (
            effect["event_id"] != 1001
            or effect["channel"] != 60
            or effect["caster_code"] != 2
            or effect["target_code"] != 2
            or effect["effect_family"] != 330
            or effect["selector_mask"] != 1
            or len(effect["native_parameters"]) != 2 * effect["parameter_count"]
        ):
            raise ValueError("Invalid immutable NPC START effect descriptor")
        result["effects"].append(effect)
    if (
        result["binding"] != "actual_owned_npc_turn_manager_as_caster"
        or result["monster_references"] != sorted(set(result["monster_references"]))
        or result["boss_reference"] not in result["monster_references"]
        or len(result["catalog_revision"]) != 64
        or result["effect_references"]
        != [e["listener_reference"] for e in result["effects"]]
        or result["effect_references"] != sorted(set(result["effect_references"]))
    ):
        raise ValueError("Invalid immutable owned NPC START binding")
    return result


from .combat_encounter_owned_start_binding import _same_sequence, _same_record


def binding_from_record(record):
    if not isinstance(record, dict) or not _same_record(
        record, _version(record.get("policy"))
    ):
        raise ValueError("Frozen owned NPC START binding changed")
    return deepcopy(record)


def freeze_npc_start_binding(fight, *, roles):
    from wakfu_server import native_catalog

    if fight.phase != "placement":
        raise ValueError("Owned NPC START binding requires fresh placement")
    if hasattr(fight, "native_encounter_npc_start_binding"):
        previous = fight.native_encounter_npc_start_binding
        frozen = None if previous is None else binding_from_record(previous)
    else:
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_npc_start_binding_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Owned NPC START binding differs from admission or catalog")
    fight.native_encounter_npc_start_binding = frozen
    return deepcopy(frozen)


def npc_start_caster(fight, source, *, entry, original, definition, effect):
    """Bind only the admitted owned NPC START; preserve native null Qe."""
    frozen = getattr(fight, "native_encounter_npc_start_binding", None)
    if frozen is None:
        return None
    frozen = binding_from_record(frozen)
    rule = next(
        (
            effect
            for effect in frozen["effects"]
            if effect["listener_reference"] == original.reference
        ),
        None,
    )
    if rule is None:
        return None
    from .combat_event_replay import NativeExternalEvent

    if not isinstance(source, NativeExternalEvent):
        return None
    context = source.turn_boundary_context
    if (
        source.event_ids != (rule["event_id"],)
        or source.channel != rule["channel"]
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
        raise ValueError("Owned NPC START binding escaped frozen encounter scope")
    if (
        effect.get("effect_class") != rule["effect_family"]
        or effect.get("native_target_selector")
        != {"class": "fcE", "mask": rule["selector_mask"]}
        or not _same_sequence(effect.get("parameters"), rule["native_parameters"])
        or not _same_sequence(effect.get("children"), rule["native_children"])
        or effect.get("criteria") != rule["criterion"]
        or effect.get("area_class") != rule["area_class"]
        or effect.get("parameter_count") != rule["parameter_count"]
        or not _same_sequence(
            effect.get("native_effect_flags"), rule["native_effect_flags"]
        )
        or effect.get("native_execution_mode") != rule["native_execution_mode"]
        or not _same_sequence(
            effect.get("target_masks"),
            [None, None, None, None, None, [rule["event_id"]], None],
        )
        or definition.get("subscription") is not True
        or definition.get("event_reverse_subscription") is not True
        or definition.get("event_global_subscription") is not False
        or definition.get("owner_on_caster") is not False
        or definition.get("event_execution_count") != -1
        or definition.get("event_execution_count_per_level") != 0
        or definition.get("event_caster_code") != rule["caster_code"]
        or definition.get("event_target_code") != rule["target_code"]
    ):
        raise ValueError("Original owned NPC START subscription descriptor changed")
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        participant.id, {}
    )
    if (
        participant.controlled
        or participant.hp <= 0
        or participant.team != roles.npc_team
        or source.manager_actor_id != participant.id
        or entry.manager_id != participant.id
        or original.target_id != participant.id
        or entry.generic_effect != original.reference
        or receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == frozen["boss_constructor_state"]
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Owned NPC START binding lacks its actual native boss")
    if original.caster_id == participant.id:
        return None  # Native null-source replay already has the actual turn manager.
    from .combat_state_managers import registered_source_pv

    producer = registered_source_pv(fight, original.caster_id)
    if producer is None:
        raise ValueError("Owned NPC START binding lacks its original native source PV")
    if not any(
        state.uid == original.state_uid
        and state.reference == rule["carrier_state"]
        and state.target_id == participant.id
        and state.caster_id == original.caster_id
        and rule["owner_effect_reference"] in state.effect_ids
        for state in participant.state_ledger.entries
    ):
        raise ValueError("Owned NPC START binding lacks its original carrier state UID")
    retained = getattr(fight, "native_owned_group_effects", {}).get(entry.uid)
    if (
        not isinstance(retained, dict)
        or retained.get("invocation", {}).get("state_uid") != original.state_uid
        or retained.get("invocation", {}).get("reference") != original.reference
        or retained.get("invocation", {}).get("caster_id") != original.caster_id
        or retained.get("invocation", {}).get("target_id") != participant.id
    ):
        raise ValueError("Owned NPC START binding lacks its retained listener UID")
    key = f"{frozen['policy']}:{fight.turn_id}:{participant.id}:{entry.uid}"
    journal = getattr(fight, "native_npc_start_caster_deliveries", {})
    if key in journal:
        raise ValueError("Owned NPC START caster binding already consumed")
    fight.native_npc_start_caster_deliveries = {
        **journal,
        key: dict(
            policy=frozen["policy"],
            turn_id=fight.turn_id,
            actor_id=participant.id,
            listener_uid=entry.uid,
            state_uid=original.state_uid,
            original_caster=original.caster_id,
            reconstructed_caster=participant.id,
        ),
    }
    return participant.id
