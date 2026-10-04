"""Live eYv cost resolution for the receiving listener, not the source payer.

Emitter stores the native source container descriptor. Resolution happens only
in the transaction preview after event rebinding, using the listener's actual
caster/target and its current eHl snapshot. No payment event is fabricated.
"""
from copy import deepcopy
from .paths import DATA_ROOT
import json
from functools import lru_cache
from .combat_conditional_costs import resolve_costs, native_modifiers


@lru_cache(maxsize=1)
def cost_catalog():
    return json.loads((DATA_ROOT / "spell-costs.json").read_text())["spells"]


def source_cost_descriptor(retention, invocation):
    descriptor, _ = retention.container(invocation)
    spell = dict(present=descriptor["container_present"])
    if spell["present"]:
        spell["container_type"] = descriptor["container_type"]
        if spell["container_type"] == 11:
            spell["spell_id"] = retention.plan.get("spell_id")
            spell["level"] = retention.plan.get("evaluation_level")
            if type(spell["spell_id"]) is not int or type(spell["level"]) is not int:
                raise ValueError("Missing native fyG spell descriptor")
    return dict(runner_class="other", spell_context=spell)


class LiveEventCostAuthority:
    def __init__(self, preview, *, actor_authority, condition_context, catalog=None):
        self.preview, self.actors, self.conditions = (
            preview,
            actor_authority,
            condition_context,
        )
        self.catalog = cost_catalog() if catalog is None else catalog

    def __call__(self, effect, invocation, cost_source):
        source = deepcopy(cost_source)
        if effect["effect_class"] != 910:
            return source
        if not isinstance(source, dict):
            raise ValueError("Missing native source cost descriptor")
        spell = source.get("spell_context")
        if not isinstance(spell, dict) or type(spell.get("present")) is not bool:
            raise ValueError("Missing native source spell presence")
        if not spell["present"] or spell.get("container_type") != 11:
            return source
        identity, level = spell.get("spell_id"), spell.get("level")
        row = self.catalog.get(str(identity))
        if (
            type(identity) is not int
            or type(level) is not int
            or not 1 <= level <= 200
            or row is None
            or level > len(row["levels"])
        ):
            raise ValueError("Missing installed native source spell cost table")
        actor = self.preview.actors.get(invocation.caster_id)
        if actor is None:
            raise ValueError("Missing native listener cost caster")
        authority = self.actors(self.preview, actor)
        if authority.targeting.get("is_eGj") is not True:
            raise ValueError("Unverified native listener eGj cost branch")
        base = dict(zip(("ap", "mp", "wp"), row["levels"][level - 1]))
        base["conditional_rules"] = row["conditional"]
        # fyF costs are resolved against LISTENER actors, even if the spell
        # belongs to a different breed. Do not ownership-gate that source spell.
        context = self.conditions(
            effect, invocation, dict(spell_id=identity, evaluation_level=level)
        )
        modifiers = native_modifiers(identity, actor.spell_ap_cost_modifiers)
        result = resolve_costs(identity, level, base, context, modifiers=modifiers)
        spell["resolved_costs"] = {key: result[key] for key in ("ap", "mp", "wp")}
        return source
