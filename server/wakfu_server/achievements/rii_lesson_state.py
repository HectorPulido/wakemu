"""Scoped construction of native informational state carriers for Rii.

The original encounter producer is unknown. The caller owns a reconstructed
lesson contract and a discardable fight preview; this is not a client API.
"""
from dataclasses import asdict


def install(fight, *, owner_id, target_id, reference, level, action_id, packets):
    """Install a verified, permanent marker-only native state and its carrier."""
    if (
        fight.phase != "active"
        or owner_id not in fight.actors
        or target_id not in fight.actors
        or reference not in (8011, 8013, 8014, 8015, 8016)
        or type(level) is not int
        or not 1 <= level <= 4
    ):
        raise ValueError("Invalid Rii lesson state producer")
    from wakfu_server.spell_audit import states_catalog
    from wakfu_server.combat_retained_runtime import native_retained_metadata
    from wakfu_server.combat_retained_effects import RetainedEffect
    from wakfu_server.combat_state_carrier import (
        STATE_CARRIER_APPLICATION_OPCODE,
        state_carrier_application,
        state_carrier_payload,
    )

    catalog = states_catalog()
    definition = catalog["states"].get(str(reference))
    flags = native_retained_metadata()["states"].get(str(reference))
    if (
        not isinstance(definition, dict)
        or not isinstance(flags, dict)
        or level > definition["maximum_level"]
        or definition["duration_base"] != -1
        or any(
            catalog["effects"][str(root)]["effect_class"] != 400
            for root in definition["effect_ids"]
        )
    ):
        raise ValueError("Rii lesson state is not a permanent marker")
    if any(
        row.reference == reference
        for row in fight.actors[target_id].state_ledger.entries
    ):
        raise ValueError("Rii lesson state already installed")
    uid = fight.allocate_effect_uid()
    change = fight.apply_state(
        owner_id, target_id, reference, level, uid=uid, catalog=catalog
    )
    if change.applied is None or not change.applied.retained or change.removed:
        raise ValueError("Rii lesson state was not installed uniquely")
    from wakfu_server.combat_running_container import running_container_scope

    # This local lesson producer explicitly has no native parent container.
    # It can run during an unrelated active spell; do not leak that spell's
    # scoped container into the carrier's serialized payload.
    with running_container_scope({"container_present": False}, None):
        payload = state_carrier_payload(
            uid=uid,
            base_uid=None,
            caster_id=owner_id,
            target_id=target_id,
            state_id=reference,
            level=level,
            native_turn_clock=-1,
            native_realtime_remaining=0,
        )
    fight.state_wire_payloads[uid] = payload.hex()
    fight.native_retained_records[uid] = asdict(
        RetainedEffect(
            uid,
            target_id,
            310,
            -1,
            manager_id=target_id,
            definition_type=0,
            state_unremovable=flags["unremovable"],
            state_dispellable=flags["dispellable"],
            container_present=False,
        )
    )
    fight.native_retained_order.append(uid)
    packets.append(
        (
            STATE_CARRIER_APPLICATION_OPCODE,
            state_carrier_application(
                fight.id,
                action_id,
                uid=uid,
                target_id=target_id,
                running_effect_payload=payload,
            ),
        )
    )
    return uid


def remove(fight, *, target_id, uid, action_id, packets):
    """Remove exactly one previously installed owned state and carrier."""
    from wakfu_server.combat_effect_removal import running_effect_removal

    target = fight.actors.get(target_id)
    payload = fight.state_wire_payloads.get(uid)
    entry = (
        next((row for row in target.state_ledger.entries if row.uid == uid), None)
        if target
        else None
    )
    record = fight.native_retained_records.get(uid)
    if (
        entry is None
        or entry.reference not in (8011, 8013, 8014, 8015, 8016)
        or not isinstance(payload, str)
        or not isinstance(record, dict)
        or record.get("target_id") != target_id
        or record.get("effect_class") != 310
        or uid not in fight.native_retained_order
    ):
        raise ValueError("Missing Rii lesson state carrier")
    packets.append(
        (
            13560,
            running_effect_removal(
                fight.id,
                action_id,
                effect_class=310,
                target_id=target_id,
                uid=uid,
                running_effect_payload=bytes.fromhex(payload),
            ),
        )
    )
    target.state_ledger.remove(uid)
    del fight.state_wire_payloads[uid]
    del fight.native_retained_records[uid]
    fight.native_retained_order.remove(uid)
