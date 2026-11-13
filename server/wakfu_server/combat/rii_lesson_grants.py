"""Scoped temporary native spell grants for Rii's elemental lesson.

No encounter calls this adapter until that encounter owns a complete contract.
The eWn source is reconstructed from the installed client; its parameters
are supplied by the server-owned lesson contract, never by the client.
"""
from .combat_effect_dispatch import EffectInvocation
from .combat_spell_grant import NativeSpellGrantHandler, remove_spell_grant
from .combat_stat_handler import StatExecutionContext
from .rii_lesson_spell_catalog import GRANT_EFFECT


SPELLS = (7963, 7964, 7965, 7966)
LESSONS = {
    "element": ("rii_element_lesson_contract", SPELLS),
    "distance": ("rii_distance_lesson_contract", (7967,)),
    "los": ("rii_los_lesson_contract", (7968,)),
    "area": ("rii_area_lesson_contract", (7969, 7970, 7971)),
    "movement": ("rii_movement_lesson_contract", (7972, 7973, 7974, 7975)),
    "states": ("rii_states_lesson_contract", (7967,)),
}


# A native eWn649 effect reference; its payload explicitly carries the spell,
# shortcut bar and slot. Association with this lesson is a reconstruction.
def install(fight, actor_id, packets, *, action_id, allocate_uid, lesson="element"):
    """Install four native temporary spells on an authenticated lesson actor.

    The caller must own a transaction/preview and publish its packets only on
    commit. Existing permanent spells and the player's saved deck are untouched.
    """
    if lesson not in LESSONS:
        raise ValueError("Unknown Rii lesson")
    contract_name, spells = LESSONS[lesson]
    contract = getattr(fight, contract_name, None)
    if (
        not isinstance(contract, dict)
        or contract.get("owner") != actor_id
        or actor_id not in fight.actors
        or fight.phase != "active"
    ):
        raise ValueError("Missing elemental lesson encounter authority")
    from .combat_morph_spellbook import morph_record

    if morph_record(fight, actor_id) is not None:
        raise ValueError("Elemental lesson cannot replace a transformed spellbook")
    actor = fight.actors[actor_id]
    if any(
        spell in getattr(fight, "native_spell_grants", {}).get(actor_id, {})
        for spell in spells
    ):
        raise ValueError("Elemental lesson spells already installed")
    handler = NativeSpellGrantHandler(
        fight,
        packets,
        action_id=action_id,
        allocate_uid=allocate_uid,
        context=lambda *_: StatExecutionContext(True, True, None, True, None),
    )
    invocation = EffectInvocation(GRANT_EFFECT, 1, actor_id, actor_id, actor.position)
    from .combat_retained_runtime import NativeRetainedRuntime, native_retained_metadata
    from .combat_retained_effects import RetainedEffect

    metadata = native_retained_metadata()
    definition = metadata.get("effects", {}).get(str(GRANT_EFFECT))
    if (
        not isinstance(definition, dict)
        or definition.get("effect_class") != 649
        or type(definition.get("definition_type")) is not int
        or type(definition.get("definition_dispellable")) is not bool
        or definition.get("subscription") is not False
    ):
        raise ValueError("Unexpected elemental lesson grant carrier definition")
    # The original lesson's grant producer is not present in the client.
    # This explicit non-subscribing local producer registers each carrier with
    # its native class/definition metadata and no invented spell container.
    retention = NativeRetainedRuntime(
        fight,
        packets,
        plan={"native_retained_container": {"present": False}},
        state_catalog={},
        action_id=action_id,
        timing=None,
        metadata=metadata,
    )
    before = set(fight.owned_stat_effects)
    for slot, spell in enumerate(spells):
        previous = set(fight.owned_stat_effects)
        handler(
            {
                "effect_class": 649,
                "parameters": [
                    2.0,
                    0.0,
                    float(slot),
                    0.0,
                    float(spell),
                    0.0,
                    -1.0,
                    0.0,
                ],
            },
            [],
            invocation,
        )
        added = set(fight.owned_stat_effects) - previous
        if len(added) != 1:
            raise ValueError("Elemental lesson grant has no unique carrier")
        uid = added.pop()
        retention.record(
            RetainedEffect(
                uid,
                actor_id,
                649,
                GRANT_EFFECT,
                manager_id=actor_id,
                definition_type=definition["definition_type"],
                definition_dispellable=definition["definition_dispellable"],
                container_present=False,
            )
        )
    installed = set(fight.owned_stat_effects) - before
    if len(installed) != len(spells):
        raise ValueError("Incomplete elemental lesson spell grants")
    return sorted(installed)


def remove(fight, actor_id, grant_uids, packets, *, action_id, lesson="element"):
    """Remove remaining server-owned lesson grants and their shortcuts."""
    if lesson not in LESSONS:
        raise ValueError("Unknown Rii lesson")
    _, spells = LESSONS[lesson]
    handler = NativeSpellGrantHandler(
        fight,
        packets,
        action_id=action_id,
        allocate_uid=lambda: None,
        context=lambda *_: None,
    )
    if (
        not isinstance(grant_uids, (tuple, list))
        or len(grant_uids) != len(spells)
        or len(set(grant_uids)) != len(spells)
        or any(type(uid) is not int or uid <= 0 for uid in grant_uids)
    ):
        raise ValueError("Invalid elemental lesson grant ownership")
    present = [
        (uid, fight.owned_stat_effects[uid])
        for uid in grant_uids
        if uid in fight.owned_stat_effects
    ]
    if any(
        row["target_id"] != actor_id
        or row["spell_id"] not in spells
        or row["effect_class"] != 649
        for _, row in present
    ) or len({row["spell_id"] for _, row in present}) != len(present):
        raise ValueError("Invalid elemental lesson grant ownership")
    for uid, _ in present:
        remove_spell_grant(handler, uid)
        fight.native_retained_records.pop(uid, None)
        if uid in fight.native_retained_order:
            fight.native_retained_order.remove(uid)


def remove_distance_if_present(fight, packets, *, action_id, owner_ids=None):
    """Remove the owned distance grant on terminal or owner-withdraw paths."""
    contract = getattr(fight, "rii_distance_lesson_contract", None)
    if (
        not isinstance(contract, dict)
        or contract.get("initialized") is not True
        or (owner_ids is not None and contract.get("owner") not in owner_ids)
    ):
        return False
    remove(
        fight,
        contract["owner"],
        contract["grant_uids"],
        packets,
        action_id=action_id,
        lesson="distance",
    )
    return True


def remove_los_if_present(fight, packets, *, action_id, owner_ids=None):
    """Remove the owned line-of-sight grant on terminal or withdrawal paths."""
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_los_areas") is True:
        # Spell 7968 belongs to the native morphology carrier; its normal
        # retained-effect lifecycle removes it, not the local grant registry.
        return False
    if (
        not isinstance(contract, dict)
        or contract.get("initialized") is not True
        or (owner_ids is not None and contract.get("owner") not in owner_ids)
    ):
        return False
    remove(
        fight,
        contract["owner"],
        contract["grant_uids"],
        packets,
        action_id=action_id,
        lesson="los",
    )
    return True


def remove_area_if_present(fight, packets, *, action_id, owner_ids=None):
    """Remove the owned area grants on terminal or owner-withdraw paths."""
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if (
        not isinstance(contract, dict)
        or contract.get("initialized") is not True
        or (owner_ids is not None and contract.get("owner") not in owner_ids)
    ):
        return False
    remove(
        fight,
        contract["owner"],
        contract["grant_uids"],
        packets,
        action_id=action_id,
        lesson="area",
    )
    return True


def remove_movement_if_present(fight, packets, *, action_id, owner_ids=None):
    """Remove movement grants on terminal or owner-withdraw paths."""
    contract = getattr(fight, "rii_movement_lesson_contract", None)
    if (
        not isinstance(contract, dict)
        or contract.get("initialized") is not True
        or (owner_ids is not None and contract.get("owner") not in owner_ids)
    ):
        return False
    remove(
        fight,
        contract["owner"],
        contract["grant_uids"],
        packets,
        action_id=action_id,
        lesson="movement",
    )
    from wakfu_server.achievements.rii_lesson_state import remove as remove_lesson_state

    for target_id, key in (
        (contract["target"], "state_uid"),
        (contract["owner"], "owner_state_uid"),
    ):
        uid = contract.get(key)
        if uid is not None and uid in fight.state_wire_payloads:
            remove_lesson_state(
                fight,
                target_id=target_id,
                uid=uid,
                action_id=action_id,
                packets=packets,
            )
    return True


def remove_states_if_present(fight, packets, *, action_id, owner_ids=None):
    """Remove the owned state-lesson grant on terminal or withdrawal paths."""
    contract = getattr(fight, "rii_states_lesson_contract", None)
    if (
        not isinstance(contract, dict)
        or contract.get("initialized") is not True
        or (owner_ids is not None and contract.get("owner") not in owner_ids)
    ):
        return False
    state_uid = contract.get("state_uid")
    if state_uid is not None:
        target = fight.actors.get(contract.get("target"))
        state_present = target is not None and any(
            entry.uid == state_uid for entry in target.state_ledger.entries
        )
        if state_present:
            from wakfu_server.achievements.rii_lesson_state import (
                remove as remove_state,
            )

            remove_state(
                fight,
                target_id=contract["target"],
                uid=state_uid,
                action_id=action_id,
                packets=packets,
            )
        elif (
            state_uid in fight.state_wire_payloads
            or state_uid in fight.native_retained_records
            or state_uid in fight.native_retained_order
        ):
            raise ValueError("Incomplete state lesson carrier cleanup")
        contract.pop("state_uid", None)
        contract.pop("visible_state", None)
    remove(
        fight,
        contract["owner"],
        contract["grant_uids"],
        packets,
        action_id=action_id,
        lesson="states",
    )
    return True
