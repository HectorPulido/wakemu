"""Detached big.a(eGH.cle) execution before controller/fdt/QI registration.

The scoped PV is the real freshly constructed actor, not an alias inserted in
the fight roster. Only synchronous construction sees its Qf; ordinary event
iteration continues to use the actual registered collections.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class DetachedSummonConstruction:
    fight: object
    actor: object
    authority: object


_construction = ContextVar("native_detached_summon_construction", default=())


def detached_actor(fight, identity):
    for construction in reversed(_construction.get()):
        if construction.fight is fight and construction.actor.id == identity:
            return construction.actor
    return None


def registered_or_detached_actor(fight, identity):
    actor = fight.actors.get(identity)
    return actor if actor is not None else detached_actor(fight, identity)


def detached_actors(fight):
    return tuple(item.actor for item in _construction.get() if item.fight is fight)


def detached_actor_authority(fight, actor):
    for construction in reversed(_construction.get()):
        if construction.fight is fight and construction.actor is actor:
            return construction.authority
    return None


@contextmanager
def detached_summon_scope(fight, actor, authority):
    from .combat_runtime_adapter import NativeActorAuthority
    from .combat_state_ledger import StateLedger

    if (
        not isinstance(authority, NativeActorAuthority)
        or actor.id in fight.actors
        or detached_actor(fight, actor.id) is not None
        or actor.team != -1
        or not isinstance(actor.state_ledger, StateLedger)
        or actor.state_ledger.actor_id != actor.id
        or authority.is_player is not False
        or authority.native_controller_id != actor.id
        or authority.targeting.get("dpu_id") != actor.id
        or authority.targeting.get("dpr_id") != actor.id
        or authority.targeting.get("bcN") != -1
    ):
        raise ValueError("Missing detached native summon construction authority")
    token = _construction.set(
        (*_construction.get(), DetachedSummonConstruction(fight, actor, authority))
    )
    try:
        yield
    finally:
        _construction.reset(token)


def install_initial_states(
    fight, actor, plan, *, runtime_factory, application_results=None
):
    """Execute direct eWu2226 with null PL, SELF caster and rBr resistance bypass.

    The factory must already be inside the source-qualified detached scope.
    Ordinary304 parameters/chance/resistance are deliberately never constructed.
    """
    from .combat_summon_initial_states import NativeSummonInitialState
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    if detached_actor(fight, actor.id) is not actor:
        raise ValueError("Initial states require the actual detached summon PV")
    if not isinstance(plan, tuple) or any(
        not isinstance(item, NativeSummonInitialState) or item.native_rBr is not True
        for item in plan
    ):
        raise ValueError("Missing native eGH.cle initial-state construction plan")
    dispatcher, outbox = runtime_factory(
        fight, {"native_retained_container": {"present": False}}
    )
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if handler.fight is not fight or retention is None:
        raise ValueError("Missing detached summon state/Qf runtime")
    if application_results is not None and not isinstance(application_results, list):
        raise ValueError("Initial-state application results require an owned list")
    for item in plan:
        profile = state_profile(handler.catalog, item.state_id, item.level)
        # eWu.D passes its eZQ/PO PN into eZk.a. The state-specific
        # eZk.bbT returns before fyW.guG when PN.bac() is null, retaining
        # Ts.biM even for a positive turn duration. Only the actual scoped
        # constructor attests that absent SU; a detached lookup alone cannot.
        realtime = profile["realtime_duration"] > 0
        realtime_supported = (
            realtime
            and profile["duration"] < 0
            and profile["skip_turn_timer"] is True
            and detached_actor_authority(fight, actor) is not None
            and fight.phase in ("placement", "active")
        )
        if (realtime and not realtime_supported) or (
            profile["duration"] > 0 and detached_actor_authority(fight, actor) is None
        ):
            raise ValueError("Initial summon state requires an audited finite timeline")
        invocation = EffectInvocation(
            2226, item.level, actor.id, actor.id, actor.position
        )
        context = StateCarrierContext(
            profile["duration"],
            profile["realtime_duration"],
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=profile["realtime_duration"]),
        )
        existing_uids = (
            {entry.uid for entry in actor.state_ledger.entries}
            if realtime_supported
            else set()
        )
        applied = retention.apply_state_reference(
            handler,
            invocation,
            item.state_id,
            item.level,
            carrier_context=context,
            protected=True if item.native_rBq else None,
        )
        if applied and realtime_supported:
            # big's eZQ constructor precedes its real combat registration.
            # eGj.g/eZk.h migrate the remaining realtime clock to eVw; its
            # state310 timer callback explicitly suppresses combat removal.
            from .combat_realtime_state_clock import (
                register_realtime_state,
                migrate_realtime_state,
            )

            entries = tuple(
                entry
                for entry in actor.state_ledger.entries
                if entry.uid not in existing_uids and entry.reference == item.state_id
            )
            if len(entries) != 1 or entries[0].timer is not None:
                raise ValueError("Missing actual constructor realtime carrier")
            entry = entries[0]
            from .combat_input_observation import wall_time_ns

            now = wall_time_ns("summon.initialize.realtime") // 1000000
            clocks = {}
            register_realtime_state(
                clocks,
                uid=entry.uid,
                duration_ms=entry.realtime_duration,
                now_ms=now,
                in_combat=False,
            )
            migrate_realtime_state(clocks, entry.uid, now_ms=now, in_combat=True)
            actor.state_ledger.install_realtime_clock(
                entry.uid,
                deadline_ms=clocks[entry.uid]["deadline_ms"],
                in_combat=True,
            )
        if application_results is not None:
            application_results.append(
                dict(
                    state_id=item.state_id,
                    level=item.level,
                    applied=applied,
                )
            )
    return outbox


def summon_initializer(runtime_factory, packets):
    """Connect the real builder's before-registration hook to its runtime."""
    if not callable(runtime_factory) or not isinstance(packets, list):
        raise ValueError("Missing native summon initialization runtime/outbox")

    def initialize(fight, actor, plan):
        from .combat_summon_creation import native_fresh_summon_authority

        book = getattr(actor, "native_summon_action_book", None)
        reference = book.get("profile") if isinstance(book, dict) else None
        authority = native_fresh_summon_authority(actor, reference)
        with detached_summon_scope(fight, actor, authority):
            # eZl.c reconstructs big through eGj.b before its own notification.
            # That client constructor runs these exact cle states and bcx
            # visual/Qf notifications locally. Sending the nested outbox again
            # would duplicate them (and precede the actor's307 application).
            # Keep authoritative ledger/children writes; discard only this
            # newly created constructor runtime's outbox, never parent packets.
            install_initial_states(fight, actor, plan, runtime_factory=runtime_factory)

    return initialize
