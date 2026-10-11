"""Wakemu NPC-only area-recipient preflight; not original server recovery.

Client fcj checks the anchor fighter. Ordinary NPC self-centered direct AoE
instead requires actual recipients selected by the unchanged shared resolver.
All other native casting checks and the actual spell transaction still run.
"""
from copy import deepcopy
from dataclasses import replace


def qualified_roots(fight, request, rule, effects):
    """Keep the policy deliberately limited to attested immediate actor AoE."""
    from .combat_effect_targets import area_offsets, native_selector_policy

    caster = fight.actors.get(request.get("actor_id"))
    if (
        caster is None
        or caster.controlled
        or getattr(caster, "native_summon_source", None) is not None
        or getattr(caster, "is_summon", False)
        or caster.hp <= 0
        or getattr(caster, "pve_withdrawn", False)
        or tuple(request.get("target", ())) != tuple(caster.position)
        or rule.get("minimum") != 0
        or rule.get("maximum") != 0
    ):
        return None
    roots = rule.get("roots")
    if not isinstance(roots, (list, tuple)) or not roots:
        return None
    result = {}
    for reference in roots:
        effect = effects.get(str(reference))
        if not isinstance(effect, dict) or effect.get("children"):
            return None
        selector = effect.get("native_target_selector")
        if not isinstance(selector, dict) or selector.get("class") != "fcE":
            return None
        mask = selector.get("mask")
        policy = native_selector_policy(effect)
        if "self" in policy["relations"] or not policy["relations"]:
            return None
        if mask in (9, 129, 257):
            if policy["in_area"] is not True:
                return None
            # Parse the real geometry, never turn an unknown area into a radius.
            offsets = area_offsets(
                effect,
                origin=caster.position,
                reference=request["target"],
                direction=caster.direction,
            )
            if not offsets or set(offsets) <= {(0, 0)}:
                return None
        elif mask in (8, (1 << 47) | 256):
            # fcE without bit1 selects the actual PV population. Native empty
            # geometry is authoritative here, never an invented infinite AoE.
            if (
                policy["in_area"] is not False
                or effect.get("area_class") != "anA"
                or effect.get("area_native") != "empty"
            ):
                return None
        else:
            return None
        if (
            effect.get("application_flag") != "NONE"
            or effect.get("removal_flag") != "NONE"
        ):
            return None
        result[reference] = effect
    return result


def eligible_recipients(dispatcher, effect, invocation, fight):
    """Reuse native resolution and criteria without applying or allocating effects."""
    from .combat_conditions import evaluate_condition

    recipients = []
    for selected in dispatcher.resolve(effect, invocation):
        actor = fight.actors.get(selected.target_id)
        if (
            actor is None
            or actor.hp <= 0
            or getattr(actor, "pve_withdrawn", False)
            or actor.id == invocation.caster_id
        ):
            continue
        handler = dispatcher.handlers.get(effect["effect_class"])
        if handler is None:
            raise ValueError("Missing mandatory NPC area handler")
        eligibility = getattr(handler, "native_eligibility", None)
        if callable(eligibility) and not eligibility(effect, selected):
            continue
        if not evaluate_condition(
            effect["criteria"], dispatcher.condition_context(selected)
        ):
            continue
        if effect["effect_class"] == 258:
            if type(actor.max_hp) is not int or not 0 < actor.hp < actor.max_hp:
                continue
        recipients.append(actor.id)
    return tuple(recipients)


def npc_cast_condition(adapter, fight, request, *, factory, enabled):
    """Called only after NPC spell ownership and activation have been checked."""
    conditions = adapter.cast_condition(fight, request)
    if not enabled:
        return conditions
    original_query = conditions.native_casting_query

    def query(rule, spell_id, level):
        decision = original_query(rule, spell_id, level)
        if decision.get("result") != "twE" or decision.get("aligned") is not True:
            return decision
        effects = factory.effects
        roots = qualified_roots(fight, request, rule, effects)
        if roots is None:
            return decision
        from .combat_casting_context import (
            NativeOwnedCastingContext,
            cast_cell_condition,
        )
        from .combat_effect_dispatch import EffectInvocation

        preview = deepcopy(fight)
        plan = dict(
            request,
            spell_id=spell_id,
            evaluation_level=level,
            target_id=request["actor_id"],
            effect_ids=tuple(rule["roots"]),
            costs=rule["costs"],
        )
        dispatcher, _packets = factory(preview, plan)
        recipients = {}
        for reference, effect in roots.items():
            invocation = EffectInvocation(
                reference,
                level,
                request["actor_id"],
                request["actor_id"],
                tuple(request["target"]),
            )
            recipients[reference] = eligible_recipients(
                dispatcher, effect, invocation, preview
            )
        if not any(recipients.values()):
            return decision
        actual_conditions, invocation = cast_cell_condition(
            adapter,
            fight,
            request,
            request["actor_id"],
            request["target"],
            return_invocation=True,
        )

        class NpcAreaCastingContext(NativeOwnedCastingContext):
            def root_selector_accepts(self, root):
                return bool(recipients[root])

        casting = NpcAreaCastingContext(
            adapter, fight, plan, invocation, actual_conditions, rule
        )
        casting.normal_mode = True
        trace = []
        result = casting.eligibility(trace=trace)
        diagnostic = dict(decision.get("diagnostic") or {})
        diagnostic["wakemu_npc_area_policy"] = dict(
            producer="wakemu-npc-direct-self-centered-recipients-v1",
            original_anchor_result=decision["result"],
            recipients=recipients,
            trace=trace,
            original_server_recovery=False,
        )
        return dict(decision, result=result, diagnostic=diagnostic)

    return replace(conditions, native_casting_query=query)
