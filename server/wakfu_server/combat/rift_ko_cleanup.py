"""Scoped Wakemu reconstruction for native Ultimate NPC KO cleanup children.

The original local1010 listeners and their321 definitions are unchanged.
The original client Qe chosen-PV path does not recover the missing server
fanout: this explicit policy selects living opponents only for ENEMY/no-AREA
321 descendants of the defeated NPC's own local KO listener. Ordinary Qe
selection, selector8192 and all other event publications remain unchanged.
"""
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

POLICY = "wakemu.rift.ultimate-owned-local-ko-cleanup.v1"
_CURRENT = ContextVar("rift_owned_local_ko_cleanup", default=None)
_BOUNDARY = ContextVar("rift_actual_owned_ko_boundary", default=None)


@dataclass(frozen=True)
class _Cleanup:
    fight: object
    manager_id: int
    state_uid: int
    source_identity: tuple
    descendants: frozenset


def _source_identity(source):
    return (
        source.uid,
        source.generic_effect,
        source.caster_id,
        source.target_id,
        source.manager_actor_id,
        source.channel,
        tuple(source.event_ids),
    )


@contextmanager
def owned_ko_boundary(fight, source):
    """Open only around the actual once-only death producer's local1010 call."""
    from wakfu_server.combat_event_replay import NativeEventSource

    state = getattr(fight, "rift_wave_state", None)
    if (
        not isinstance(state, dict)
        or state.get("catalog", {}).get("type") != "ULTIMATE_INFINITE_WAVE"
    ):
        yield
        return
    if (
        not isinstance(source, NativeEventSource)
        or source.channel != 6
        or source.event_ids != (1010,)
        or source.target_id != source.manager_actor_id
    ):
        raise ValueError("Actual local native KO source required")
    source.validate()
    events = [
        row
        for row in fight.events
        if row.get("kind") == "death" and row.get("actor_id") == source.manager_actor_id
    ]
    receipt = (
        getattr(fight, "native_death_event_deliveries", {}).get(
            str(events[-1]["sequence"])
        )
        if events
        else None
    )
    if (
        not isinstance(receipt, Mapping)
        or receipt.get("actor_id") != source.manager_actor_id
        or receipt.get("policy") != "wakemu.owned-ko-and-death-v3"
        or receipt.get("ko_event_id") != 1010
    ):
        raise ValueError("Actual registered once-only KO delivery required")
    token = _BOUNDARY.set((fight, _source_identity(source)))
    try:
        yield
    finally:
        _BOUNDARY.reset(token)


@contextmanager
def cleanup_scope(
    retention, dispatcher, source, *, entry, original, effect, definition
):
    """Bind one real local KO clone to its owned state and immutable children."""
    from wakfu_server.combat_event_replay import NativeEventSource

    if (
        not isinstance(source, NativeEventSource)
        or source.channel != 6
        or source.event_ids != (1010,)
        or effect.get("effect_class") != 330
        or definition.get("event_global_subscription") is not False
        or definition.get("event_reverse_subscription") is not False
        or definition.get("event_caster_code") != 2
        or definition.get("event_target_code") != 2
    ):
        yield
        return
    fight = retention.fight
    boundary = _BOUNDARY.get()
    if (
        boundary is None
        or boundary[0] is not fight
        or boundary[1] != _source_identity(source)
    ):
        yield
        return
    state = getattr(fight, "rift_wave_state", None)
    if (
        not isinstance(state, dict)
        or state.get("catalog", {}).get("type") != "ULTIMATE_INFINITE_WAVE"
    ):
        yield
        return
    from wakfu_server.rift_native_gameplay import policy
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.combat_ordinary_death import (
        registered_ordinary_death,
        owned_fighter_guards,
    )

    if policy(fight) is None:
        yield
        return
    actor = fight.actors.get(source.manager_actor_id)
    if (
        actor is None
        or actor.controlled
        or actor.team != assigned_roles(fight).npc_team
        or actor.id not in getattr(fight, "rift_monsters", {})
        or actor.id in getattr(fight, "native_summon_registrations", {})
        or source.target_id != actor.id
        or entry.manager_id != actor.id
        or original.caster_id != actor.id
        or original.target_id != actor.id
        or original.state_uid is None
        or not any(
            row.uid == original.state_uid and row.target_id == actor.id
            for row in actor.state_ledger.entries
        )
        or registered_ordinary_death(fight, actor) is not True
        or owned_fighter_guards(fight, actor) != dict(baF=False, baG=True, baK=False)
    ):
        yield
        return
    masks = effect.get("target_masks")
    if (
        not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or 1010 not in (masks[5] or ())
        or entry.generic_effect != original.reference
    ):
        raise ValueError("Rift KO cleanup requires the actual owned local listener")
    pending, seen, descendants = list(effect.get("children", ())), set(), set()
    while pending:
        reference = pending.pop()
        if reference in seen:
            continue
        seen.add(reference)
        child = dispatcher.effects.get(str(reference))
        if not isinstance(child, Mapping) or len(seen) > 4096:
            raise ValueError("Rift KO cleanup child graph is incomplete or excessive")
        if child.get("effect_class") == 321:
            descendants.add(reference)
        # State application owns another native source; never borrow its tree.
        if child.get("effect_class") != 304:
            pending.extend(child.get("children", ()))
    token = _CURRENT.set(
        _Cleanup(
            fight,
            actor.id,
            original.state_uid,
            _source_identity(source),
            frozenset(descendants),
        )
    )
    try:
        yield
    finally:
        _CURRENT.reset(token)


def cleanup_population(effect, invocation, actors, *, direct_policy):
    """Return the complete living fighter population only in the typed scope.

    The normal resolver still applies original fcE relationships/exclusions,
    criteria, probability, timing and the original native321 handler. No state
    reference, actor breed or map is selected by this policy.
    """
    scope = _CURRENT.get()
    if scope is None:
        return None
    selector = effect.get("native_target_selector")
    if (
        effect.get("effect_class") != 321
        or invocation.reference not in scope.descendants
        or not isinstance(selector, Mapping)
        or selector.get("class") != "fcE"
        or type(selector.get("mask")) is not int
        or not selector["mask"] & 8
        or selector["mask"] & (1 | 2 | 4 | 128)
        or tuple(direct_policy or ()) != (321, False, False)
        or invocation.native_preselected_target
        or invocation.caster_id != scope.manager_id
        or invocation.target_id != scope.manager_id
        or invocation.state_uid != scope.state_uid
    ):
        return None
    trigger = invocation.native_trigger_context
    if not isinstance(trigger, dict):
        return None
    identity = (
        trigger.get("uid"),
        trigger.get("generic_effect"),
        trigger.get("caster_id"),
        trigger.get("target_id"),
        trigger.get("manager_actor_id"),
        trigger.get("channel"),
        tuple(trigger.get("event_ids", ())),
    )
    if identity != scope.source_identity:
        return None
    fight = scope.fight
    source = fight.actors[scope.manager_id]
    expected = {
        actor.id
        for actor in fight.actors.values()
        if actor.team != source.team
        and not getattr(actor, "pve_withdrawn", False)
        and fight._in_play(actor)
    }
    available = {actor.id: actor for actor in actors if actor.id in expected}
    if set(available) != expected or any(
        fight.actors[uid] is not actor for uid, actor in available.items()
    ):
        raise ValueError(
            "Rift KO cleanup requires the complete registered opponent population"
        )
    return tuple(actor for actor in actors if actor.id in expected)
