"""Ordered native entry execution on a private, uncommitted fight.

Admission, ownership, resource payment and presentation remain native adapters.
Policies describe real route differences; a summon inherits its authorizing
player or NPC route rather than acquiring another actor's admission rules.
"""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType

from .combat_effect_dispatch import EffectInvocation
from .combat_geometry_snapshot import source_snapshot


@dataclass(frozen=True)
class EntryPolicy:
    active_spell: bool
    explicit_spell_level: bool
    paid_player_events: bool
    normal_root_context: bool
    explicit_point_target: bool


_PLAYER = EntryPolicy(True, True, True, True, True)
_NPC = EntryPolicy(True, False, False, True, False)
_WEAPON = EntryPolicy(False, False, False, False, False)
ENTRY_ROUTES = MappingProxyType(
    {
        "player": _PLAYER,
        "npc": _NPC,
        "summon.player": _PLAYER,
        "summon.npc": _NPC,
        "weapon": _WEAPON,
    }
)


def entry_route(caster, authority):
    """Classify only after the native adapter has authorized the actor."""
    if authority not in ("player", "npc", "weapon"):
        raise ValueError("Unknown native entry authority")
    if (
        authority != "weapon"
        and getattr(caster, "native_summon_source", None) is not None
    ):
        return "summon." + authority
    return authority


def private_entry_preview(fight, *, snapshot=source_snapshot, clone=deepcopy):
    """Capture the authoritative source before making an isolated preview."""
    return snapshot(fight), clone(fight)


def execute_entry_roots(
    preview,
    plan,
    caster,
    dispatcher,
    roots,
    *,
    route,
    execution_origin=None,
    invocation_factory=EffectInvocation,
    active_scope=None,
    event_scope=None,
    native_spell_id=None,
    native_level=None,
    native_cell=None,
    native_level_source=None,
    roots_source=None,
    pay_resources=None,
):
    """Dispatch native roots once, in source order and native scope order.

    An admitted player entry may delegate its owned payment until after1024.
    NPC and weapon policies cannot use this callback or replay player payments.
    No route publishes packets at this boundary.
    """
    try:
        policy = ENTRY_ROUTES[route]
    except (KeyError, TypeError):
        raise ValueError("Unknown native entry route") from None
    if pay_resources is not None and (
        not callable(pay_resources) or not policy.paid_player_events
    ):
        raise ValueError("Owned payment callback requires a player entry")
    with ExitStack() as scopes:
        if policy.active_spell:
            if active_scope is None:
                from .combat_active_spell import active_spell_scope

                active_scope = active_spell_scope
            kwargs = (
                {"level": plan["evaluation_level"]}
                if policy.explicit_spell_level
                else {}
            )
            scopes.enter_context(
                active_scope(
                    preview,
                    plan["spell_id"] if native_spell_id is None else native_spell_id,
                    **kwargs,
                )
            )
        scopes.enter_context(preview.effect_resolution())
        if policy.paid_player_events:
            if event_scope is None:
                from .combat_cast_events import cast_event_scope

                event_scope = cast_event_scope
            scopes.enter_context(event_scope(dispatcher, plan))
            if pay_resources is not None:
                pay_resources()
            from .combat_cost_payment_events import replay_paid_spell_costs

            replay_paid_spell_costs(dispatcher, plan)
            from .combat_breeze_payment_events import replay_paid_breeze_costs

            replay_paid_breeze_costs(dispatcher, plan)
        policies = {}
        if policy.explicit_point_target:
            from .combat_direct_target import native_direct_target_policies

            policies = native_direct_target_policies()
        outcomes = []
        # Player payment/cast reactions precede the historical root-list read.
        ordered_roots = roots if roots_source is None else roots_source()
        for reference in ordered_roots:
            # Preserve each adapter's original positional-argument reads before
            # calculating optional context and point-target keyword arguments.
            level = (
                native_level_source()
                if native_level_source is not None
                else plan["evaluation_level"]
                if native_level is None
                else native_level
            )
            caster_id = caster.id
            target_id = plan["target_id"]
            cell = plan["target"] if native_cell is None else native_cell
            kwargs = {}
            if policy.explicit_point_target:
                point_target_id = plan["target_id"]
                kwargs["native_explicit_target"] = (
                    point_target_id != caster.id
                    and point_target_id in preview.actors
                    and preview.actors[point_target_id].position
                    == tuple(plan["target"])
                    and dispatcher.effects[str(reference)].get("area_class") == "anD"
                    and dispatcher.effects[str(reference)].get("native_target_selector")
                    == {"class": "fcE", "mask": 3}
                    and policies.get(str(reference), (None, None))[1] is False
                )
            if policy.normal_root_context:
                from .combat_normal_execution_origin import normal_root_context

                kwargs["native_context_hex"] = normal_root_context(
                    execution_origin,
                    caster_id=caster.id,
                    spell_id=plan["spell_id"]
                    if native_spell_id is None
                    else native_spell_id,
                    level=plan["evaluation_level"]
                    if native_level is None
                    else native_level,
                ).hex()
            outcomes.append(
                dispatcher.execute(
                    invocation_factory(
                        reference,
                        level,
                        caster_id,
                        target_id,
                        cell,
                        **kwargs,
                    )
                )
            )
        return tuple(outcomes)


def seal_entry_transaction(
    preview, plan, wp_remaining, outcomes, packets, event_start, source_state, action_id
):
    """Seal the existing transaction schema without publishing or committing."""
    from .combat_spell_transaction import SpellTransaction

    return SpellTransaction(
        preview,
        plan,
        wp_remaining,
        outcomes,
        packets,
        tuple(preview.events[event_start:]),
        source_state,
        action_id,
    )
