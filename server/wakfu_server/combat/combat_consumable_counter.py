"""Preserve an owned event-food binding across its attested self321 decrement."""


def capture(fight, invocation, eligible, reference, parameters):
    """Attest the actual old carrier before native decurse removes it."""
    if (reference, invocation.reference, tuple(parameters)) != (
        2786,
        114510,
        (2786, 1),
    ):
        return None
    if len(eligible) != 1 or invocation.caster_id != invocation.target_id:
        return None
    old = eligible[0]
    if (
        old.uid != invocation.state_uid
        or old.caster_id != invocation.target_id
        or old.target_id != invocation.target_id
    ):
        return None
    rows = getattr(fight, "native_consumable_initializations", {}).get(
        old.target_id, ()
    )
    matches = [
        row
        for row in rows
        if row["combat_uid"] == old.uid
        and row["state_id"] == reference
        and row["clock"] == "event"
        and row.get("self_counter_effect_id") == invocation.reference
    ]
    if len(matches) != 1:
        return None
    return dict(
        actor_id=old.target_id,
        binding=matches[0],
        old_uid=old.uid,
        old_level=old.level,
        reference=reference,
    )


def reconcile(fight, evidence, previous_uids, remainder):
    """Bind only the newly created native remainder; never search by reference alone."""
    if evidence is None:
        return
    actor = fight.actors[evidence["actor_id"]]
    created = [
        entry for entry in actor.state_ledger.entries if entry.uid not in previous_uids
    ]
    if (
        len(created) != 1
        or created[0].reference != evidence["reference"]
        or created[0].level != remainder
        or remainder != evidence["old_level"] - 1
        or created[0].uid == evidence["old_uid"]
        or created[0].caster_id != actor.id
        or created[0].target_id != actor.id
        or created[0].timer is not None
        or created[0].realtime_duration > 0
    ):
        raise ValueError(
            "Native consumable counter remainder lacks its actual new carrier"
        )
    rows = fight.native_consumable_initializations[actor.id]
    if not any(row is evidence["binding"] for row in rows):
        raise ValueError(
            "Native consumable counter ownership changed during reapplication"
        )
    fight.native_consumable_initializations[actor.id] = tuple(
        dict(row, combat_uid=created[0].uid) if row is evidence["binding"] else row
        for row in rows
    )
