"""Wakemu finisher boundaries using original 4464 subscriptions and eZR source.

Original server callers for 1018/1012/1015 are unavailable. This policy arms
non-spell owned lethal actions, evaluates the native finisher tree before the
lethal delivery, and cleans its temporary listener after that delivery.
"""
from dataclasses import replace
from .combat_cosmetic_conditions import NativeCosmeticState, active_cosmetic_id
from .combat_event_replay import NativeEventSource

POLICY = "wakemu.owned-finisher-boundaries-v1"


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
        )
    event = replace(source, event_ids=(1012,), channel=60, manager_actor_id=caster.id)
    replay(event, authority=authority)
    # Native target code5 resolves source.target; caster code2 resolves this
    # manager. Last-enemy/round/KO/PvP and exact cosmetic guards remain in AST.
    return event


def finish_owned_finisher(source, *, replay, authority):
    """Run removal-mask2 after the actual lethal packet, never before it."""
    if not isinstance(source, NativeEventSource) or source.event_ids != (1012,):
        raise ValueError("Finisher cleanup requires its owned source")
    return replay(replace(source, event_ids=(1015,), channel=40), authority=authority)
