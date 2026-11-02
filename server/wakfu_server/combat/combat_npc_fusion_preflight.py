"""Required partner admission for immediate NPC sacrifice-and-replace casts.

This is a Wakemu server admission policy, not recovered original AI. Native
runners remain unchanged: a missing target must not let independent caster
sacrifice and birth roots turn a two-body action into a one-body action.
"""


# Reconstructed Wakemu AI admission, not recovered original server AI.
# The guide specifies two wounded Pious; native307 recipes identify their
# base-species group. It does not require the two birds to have different colors.
FUSION_POLICIES = {
    5815: {
        "source": "https://wakfustrat.wixsite.com/wakfustrat/post/piou-lahoupe",
        "health_percent_below": 50,
        "partner_from_caster_recipes": True,
    },
}


def fusion_partner_contract(roots, effects, *, level=None):
    """Recognize the bounded native self/ally sacrifice plus birth shape."""
    import re

    if not effects or not isinstance(roots, (tuple, list)) or not roots:
        return None
    self_kill = False
    partner_kill = False
    births = []
    for reference in roots:
        effect = effects.get(str(reference))
        if (
            not isinstance(effect, dict)
            or effect.get("children")
            or effect.get("application_flag") != "NONE"
            or effect.get("removal_flag") != "NONE"
            or effect.get("native_execution_mode") != 2
            or (effect.get("area_class"), effect.get("area_native")) != ("anD", "point")
        ):
            return None
        selector = effect.get("native_target_selector")
        if not isinstance(selector, dict) or selector.get("class") != "fcE":
            return None
        family = effect.get("effect_class")
        if family == 28:
            if (
                type(effect.get("criteria")) is not str
                or effect["criteria"].strip()
                or effect.get("parameter_count") != 1
                or not isinstance(effect.get("parameters"), (tuple, list))
                or tuple(effect["parameters"]) != (1, 0)
                or effect.get("probability_base") != 100
                or effect.get("probability_per_level") != 0
                or (
                    level is not None
                    and (
                        type(level) is not int
                        or type(effect.get("minimum_level")) is not int
                        or type(effect.get("maximum_level")) is not int
                        or not effect["minimum_level"]
                        <= level
                        <= effect["maximum_level"]
                    )
                )
            ):
                return None
            if selector.get("mask") == 2:
                self_kill = True
            elif selector.get("mask") == (1 << 47) | 5:
                partner_kill = True
            else:
                return None
        elif family == 307:
            criterion = effect.get("criteria", "")
            match = (
                re.fullmatch(r'\s*IsBreedId\("caster",\s*(\d+)\)\s*', criterion)
                if type(criterion) is str
                else None
            )
            if selector.get("mask") != 1 or match is None:
                return None
            births.append(int(match[1]))
        elif family != 304 or selector.get("mask") != 1:
            return None
    if not self_kill or not partner_kill or not births:
        return None
    return frozenset(births)


def validate_fusion_partner(fight, plan, roots, effects, monsters, *, factory=None):
    """Reject missing allied NPC recipients before spending or killing anyone."""
    breeds = fusion_partner_contract(roots, effects, level=plan.get("evaluation_level"))
    policy = FUSION_POLICIES.get(plan.get("spell_id"))
    if breeds is None:
        if policy is not None:
            raise ValueError("NPC fusion recipe contract is unavailable")
        return
    caster = fight.actors[plan["actor_id"]]
    target = fight.actors.get(plan.get("target_id"))
    if (
        caster.hp <= 0
        or target is None
        or target.id == caster.id
        or target.team != caster.team
        or target.hp <= 0
        or target.controlled
        or getattr(target, "pve_withdrawn", False)
        or not isinstance(monsters, dict)
        or target.id not in monsters
        or monsters[target.id].get("id") != target.id
    ):
        raise ValueError("NPC fusion requires another living allied monster")
    from .combat_effect_targets import (
        select_effect_targets,
        select_native_effect_targets,
    )
    from .combat_effect_dispatch import EffectInvocation

    # Use the same point/body geometry as the actual selector, including large
    # physical footprints. The validated target ID alone is not a recipient.
    for reference in roots:
        effect = effects[str(reference)]
        if effect["effect_class"] != 28:
            continue
        recipient = caster if effect["native_target_selector"]["mask"] == 2 else target
        center = plan["target"]
        contexts = getattr(factory, "contexts", None)
        if contexts is not None:
            invocation = EffectInvocation(
                reference, plan["evaluation_level"], caster.id, recipient.id, center
            )
            from .combat_runtime_adapter import native_point_target_projection

            projection = native_point_target_projection(contexts.native_targets)
            native = (
                contexts.native_targets(fight, plan, effect, invocation)
                if projection is None
                else projection(fight, plan, effect, invocation, (recipient,))
            )
            selected = select_native_effect_targets(
                effect, caster, center, (recipient,), native_context=native
            )
            eligibility = contexts.stat(fight, plan, effect, invocation)
            if (
                eligibility.source_guards_verified is not True
                or eligibility.executable is not True
            ):
                raise ValueError("NPC fusion sacrifice is not natively executable")
        else:
            selected = select_effect_targets(
                effect,
                caster,
                caster.position if recipient is caster else center,
                (recipient,),
                relations={"self"} if recipient is caster else {"ally"},
                native_radius=True,
            )
        if not any(actor.id == recipient.id for actor in selected):
            raise ValueError("NPC fusion requires an actual native point recipient")
    if policy is None:
        return
    if policy["partner_from_caster_recipes"]:
        caster_source = monsters.get(caster.id)
        if (
            not isinstance(caster_source, dict)
            or caster_source.get("ref") not in breeds
            or monsters[target.id].get("ref") not in breeds
        ):
            raise ValueError(
                "NPC fusion requires a partner from its native recipe group"
            )
    threshold = policy["health_percent_below"]
    if any(
        type(actor.hp) is not int
        or type(actor.max_hp) is not int
        or actor.max_hp <= 0
        or actor.hp * 100 >= actor.max_hp * threshold
        for actor in (caster, target)
    ):
        raise ValueError("NPC fusion requires both partners below its health threshold")


from collections import OrderedDict
import re as _recipe_regex

_FUSION_CONTRACT_CACHE = OrderedDict()
_SOURCE_RECIPE_MATCH = _recipe_regex.fullmatch
_uncached_fusion_partner_contract = fusion_partner_contract


def fusion_partner_contract(roots, effects, *, level=None):
    from .combat_npc_consumption_preflight import (
        published_contract_key,
        cached_published_contract,
    )

    key = published_contract_key(effects, roots, level)
    if _recipe_regex.fullmatch is not _SOURCE_RECIPE_MATCH:
        key = None
    return cached_published_contract(
        _FUSION_CONTRACT_CACHE,
        key,
        lambda: _uncached_fusion_partner_contract(roots, effects, level=level),
    )
