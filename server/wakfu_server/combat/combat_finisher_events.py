"""Wakemu finisher boundaries using original 4464 subscriptions and eZR source.

Original server callers for 1018/1012/1015 are unavailable. This policy arms
non-spell owned lethal actions, evaluates the native finisher tree before the
lethal delivery, and cleans its temporary listener after that delivery.
"""
from dataclasses import replace
from .combat_cosmetic_conditions import NativeCosmeticState, active_cosmetic_id
from .combat_event_replay import NativeEventSource

POLICY = "wakemu.owned-finisher-boundaries-v1"


def _cosmetic_listener_uids(fight, caster_id):
    """Only descendants of the actual owned native innate4464 carrier."""
    if fight is None:
        return frozenset()
    caster = fight.actors.get(caster_id)
    if caster is None:
        return frozenset()
    carriers = {
        entry.uid
        for entry in getattr(getattr(caster, "state_ledger", None), "entries", ())
        if entry.reference == 4464
        and entry.caster_id == caster_id
        and entry.target_id == caster_id
    }
    return frozenset(
        uid
        for uid, row in getattr(fight, "native_owned_group_effects", {}).items()
        if row.get("state_uid") in carriers
        and row.get("invocation", {}).get("state_uid") in carriers
        and row["invocation"].get("caster_id") == caster_id
    )


def prepare_owned_finisher(fight, source, *, replay, authority):
    if not isinstance(source, NativeEventSource):
        raise ValueError("Finisher requires actual lethal running source")
    source.validate()
    caster = fight.actors.get(source.caster_id)
    if caster is None:
        return None
    state = getattr(caster, "native_cosmetic_state", None)
    if state is None:
        return None  # No owned cosmetic producer: never opt into this policy.
    if not isinstance(state, dict):
        raise ValueError("Malformed owned finisher cosmetic component")
    cosmetic = NativeCosmeticState(
        True, state.get("selected_values"), state.get("active_cosmetics")
    )
    if active_cosmetic_id(cosmetic, 5) <= 0:
        return None
    from .combat_active_spell import active_spell_container

    scope = active_spell_container(fight)
    if not scope.get("present"):
        # Spell1024 already arms the original listener. Outside a cast, the
        # local policy uses1018; it does not label that ID as a native melee event.
        replay(
            replace(source, event_ids=(1018,), channel=60, manager_actor_id=caster.id),
            authority=authority,
            eligible_uids=_cosmetic_listener_uids(fight, caster.id),
        )
    event = replace(source, event_ids=(1012,), channel=60, manager_actor_id=caster.id)
    replay(
        event,
        authority=authority,
        eligible_uids=_cosmetic_listener_uids(fight, caster.id),
    )
    # Native target code5 resolves source.target; caster code2 resolves this
    # manager. Last-enemy/round/KO/PvP and exact cosmetic guards remain in AST.
    return event


def finish_owned_finisher(source, *, replay, authority):
    """Run removal-mask2 after the actual lethal packet, never before it."""
    if not isinstance(source, NativeEventSource) or source.event_ids != (1012,):
        raise ValueError("Finisher cleanup requires its owned source")
    retention = getattr(replay, "retention", None)
    fight = None if retention is None else retention.fight
    return replay(
        replace(source, event_ids=(1015,), channel=40),
        authority=authority,
        eligible_uids=_cosmetic_listener_uids(fight, source.caster_id),
    )
