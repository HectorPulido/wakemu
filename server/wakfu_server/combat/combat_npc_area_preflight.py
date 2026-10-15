"""Wakemu NPC-only area-recipient preflight; not original server recovery.

Client fcj checks the anchor fighter. Ordinary NPC self-centered immediate AoE
instead requires actual recipients selected by the unchanged shared resolver.
All other native casting checks and the actual spell transaction still run.
"""
from copy import deepcopy
from dataclasses import replace


def qualified_roots(fight, request, rule, effects):
    """Keep the policy limited to attested immediate actor AoE/callback groups."""
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
        if not isinstance(effect, dict):
            return None
        if effect.get("children") and transfer_children(effect, effects) is None:
            from .combat_npc_area_groups import immediate_state_group

            if immediate_state_group(effect, effects) is None:
                return None
        selector = effect.get("native_target_selector")
        if not isinstance(selector, dict) or selector.get("class") != "fcE":
            return None
        mask = selector.get("mask")
        policy = native_selector_policy(effect)
        if not policy["relations"]:
            # Contradictory native relation flags cannot select any fighter.
            # Keep the root in the real transaction, but do not let a dormant
            # branch disqualify other immediate area roots in the same spell.
            if (
                effect.get("application_flag") != "NONE"
                or effect.get("removal_flag") != "NONE"
            ):
                return None
            continue
        if "self" in policy["relations"]:
            return None
        if mask in (9, 25, 129, 257, (1 << 50) | 9):
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


def qualified_area_roots(fight, request, rule, effects):
    """Recognize immediate zero-range roots selecting actual native Qq areas.

    fcj's anchor fighter cannot satisfy an area-only selector. This NPC policy
    asks the unchanged resolver for real registered area recipients instead.
    It does not turn an empty cell or a fighter into an area.
    """
    caster = fight.actors.get(request.get("actor_id"))
    if (
        caster is None
        or caster.controlled
        or caster.hp <= 0
        or getattr(caster, "native_summon_source", None) is not None
        or getattr(caster, "is_summon", False)
        or getattr(caster, "pve_withdrawn", False)
        or tuple(request.get("target", ())) != tuple(caster.position)
        or rule.get("minimum") != 0
        or rule.get("maximum") != 0
    ):
        return None
    roots = rule.get("roots")
    if not isinstance(roots, (list, tuple)) or not roots:
        return None
    selected = {}
    for reference in roots:
        effect = effects.get(str(reference))
        # Immediate area removal may accompany ordinary fighter roots.
        # Keep its actual geometry and area selector; never substitute actors.
        if isinstance(effect, dict) and effect.get("effect_class") == 1021:
            from .combat_effect_targets import area_offsets

            if (
                effect.get("children")
                or effect.get("native_target_selector") != {"class": "fcE", "mask": 65}
                or effect.get("application_flag") != "NONE"
                or effect.get("removal_flag") != "NONE"
                or not isinstance(effect.get("target_masks"), (list, tuple))
                or len(effect["target_masks"]) != 7
                or any(effect["target_masks"])
            ):
                return None
            offsets = area_offsets(
                effect,
                origin=caster.position,
                reference=request["target"],
                direction=caster.direction,
            )
            if not offsets:
                return None
            selected[reference] = effect
            continue
        if (
            not isinstance(effect, dict)
            or effect.get("effect_class") != 330
            or effect.get("parameter_count") != 0
            or not isinstance(effect.get("parameters"), (list, tuple))
            or bool(effect["parameters"])
            or not effect.get("children")
            or effect.get("native_target_selector")
            not in (
                {"class": "fcE", "mask": 64},
                {"class": "fcE", "mask": (1 << 51) | 64},
            )
            or effect.get("area_class") != "anD"
            or effect.get("area_native") != "point"
            or effect.get("application_flag") != "NONE"
            or effect.get("removal_flag") != "NONE"
            or not isinstance(effect.get("target_masks"), (list, tuple))
            or len(effect["target_masks"]) != 7
            or any(effect["target_masks"])
        ):
            return None
        selected[reference] = effect
    return selected


def eligible_area_recipients(dispatcher, effect, invocation, fight):
    from .combat_conditions import evaluate_condition
    from .combat_state_managers import registered_area_pv

    recipients = []
    for selected in dispatcher.resolve(effect, invocation):
        identity = selected.target_id
        if identity in fight.actors or identity not in getattr(
            fight, "native_effect_areas", {}
        ):
            continue
        if registered_area_pv(fight, identity) is None:
            continue
        if evaluate_condition(
            effect["criteria"], dispatcher.condition_context(selected)
        ):
            recipients.append(identity)
    return tuple(recipients)


def transfer_children(effect, effects):
    """Recognize immediate eYy callback groups, never arbitrary nested roots."""
    if effect.get("effect_class") != 865:
        return None
    children = effect.get("children")
    if not isinstance(children, (list, tuple)) or len(children) != 2:
        return None
    result = []
    for reference in children:
        child = effects.get(str(reference))
        if (
            not isinstance(child, dict)
            or child.get("children")
            or child.get("criteria", "").strip()
            or child.get("area_native") != "point"
            or child.get("application_flag") != "NONE"
            or child.get("removal_flag") != "NONE"
        ):
            return None
        result.append(child)
    if result[0].get("native_target_selector") != effect.get("native_target_selector"):
        return None
    from .combat_effect_targets import native_selector_policy

    # Parse both real child selectors; missing/unknown metadata stays rejected.
    for child in result:
        native_selector_policy(child)
    return tuple(result)


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
        eligibility_effect, eligibility_invocation = effect, selected
        handler = dispatcher.handlers.get(effect["effect_class"])
        if effect["effect_class"] == 330:
            from .combat_npc_area_groups import immediate_state_group

            child = immediate_state_group(effect, dispatcher.effects)
            if child is None or dispatcher.handlers.get(child["effect_class"]) is None:
                raise ValueError("Missing native NPC ordered state group authority")
            # Class330 is an internal dispatcher branch, not a leaf handler.
            # Child selection and state application remain transaction-owned.
            handler = object()
        if effect["effect_class"] == 865:
            children = transfer_children(effect, dispatcher.effects)
            if (
                children is None
                or dispatcher.group_retention is None
                or not callable(dispatcher.transfer_probability)
            ):
                raise ValueError("Missing native NPC transfer group authority")
            first_handler = dispatcher.handlers.get(children[0]["effect_class"])
            second_handler = dispatcher.handlers.get(children[1]["effect_class"])
            if (
                getattr(first_handler, "native_runner_value_verified", False)
                is not True
                or second_handler is None
            ):
                raise ValueError("Missing native NPC transfer child handler")
            # The actual transaction retains eYy child-level/context, selector,
            # callback, transfer arithmetic and final execution authority.
            handler = first_handler
            eligibility_effect = children[0]
            eligibility_invocation = replace(selected, reference=effect["children"][0])
        if handler is None:
            raise ValueError("Missing mandatory NPC area handler")
        eligibility = getattr(handler, "native_eligibility", None)
        if callable(eligibility) and not eligibility(
            eligibility_effect, eligibility_invocation
        ):
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
        roots = {}
        area_references = set()
        references = rule.get("roots")
        if not isinstance(references, (tuple, list)) or not references:
            return decision
        for reference in references:
            root_rule = dict(rule, roots=(reference,))
            qualified = qualified_roots(fight, request, root_rule, effects)
            if qualified is None:
                qualified = qualified_area_roots(fight, request, root_rule, effects)
                if qualified is None:
                    return decision
                area_references.update(qualified)
            roots.update(qualified)
        area_only = bool(roots) and set(roots) == area_references
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
            recipient_query = (
                eligible_area_recipients
                if reference in area_references
                else eligible_recipients
            )
            recipients[reference] = recipient_query(
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
                return bool(recipients.get(root, ()))

        casting = NpcAreaCastingContext(
            adapter, fight, plan, invocation, actual_conditions, rule
        )
        casting.normal_mode = True
        trace = []
        result = casting.eligibility(trace=trace)
        diagnostic = dict(decision.get("diagnostic") or {})
        diagnostic["wakemu_npc_area_policy"] = dict(
            producer=(
                "wakemu-npc-zero-range-area-recipients-v1"
                if area_only
                else "wakemu-npc-mixed-area-fighter-recipients-v1"
                if area_references
                else "wakemu-npc-direct-self-centered-recipients-v1"
            ),
            original_anchor_result=decision["result"],
            recipients=recipients,
            trace=trace,
            original_server_recovery=False,
        )
        return dict(decision, result=result, diagnostic=diagnostic)

    return replace(conditions, native_casting_query=query)
