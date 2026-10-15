"""Focused mixed actor/area roots from native Missiz spell 3577."""
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from wakfu_server.combat.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat.combat_npc_area_preflight import (
    eligible_area_recipients,
    npc_cast_condition,
    qualified_area_roots,
    qualified_roots,
)


ACTOR_ROOT = 89766
AREA_ROOT = 89767


def native_roots():
    # Exact selector/geometry/flags from native spell 3577 levels 1-100.
    actor = dict(
        effect_class=304,
        native_target_selector={"class": "fcE", "mask": 25},
        area_class="anG",
        area_native="rectangle or square-3x3",
        children=[],
        criteria="",
        application_flag="NONE",
        removal_flag="NONE",
        target_masks=[None] * 7,
        parameter_count=3,
    )
    area = dict(
        effect_class=1021,
        native_target_selector={"class": "fcE", "mask": 65},
        area_class="anu",
        area_native="circle-2",
        children=[],
        criteria="!IsOwnArea()",
        application_flag="NONE",
        removal_flag="NONE",
        target_masks=[None] * 7,
        parameter_count=1,
    )
    return {str(ACTOR_ROOT): actor, str(AREA_ROOT): area}


@dataclass
class Conditions:
    native_casting_query: object


class MixedNpcAreaPreflightTests(unittest.TestCase):
    def setUp(self):
        self.caster = SimpleNamespace(
            id=-200,
            controlled=False,
            is_summon=False,
            hp=100,
            position=(0, 0, 0),
            direction=0,
        )
        self.ally = SimpleNamespace(id=7, hp=50, max_hp=100)
        self.fight = SimpleNamespace(
            actors={-200: self.caster, 7: self.ally},
            native_effect_areas={88: {"cell": (1, 0, 0)}},
        )
        self.request = {"actor_id": -200, "target": (0, 0, 0)}
        self.rule = {
            "minimum": 0,
            "maximum": 0,
            "roots": [ACTOR_ROOT, AREA_ROOT],
            "costs": {"ap": 3, "mp": 0, "wp": 1},
        }
        self.effects = native_roots()

    def test_native_mixed_actor_and_area_roots_qualify_independently(self):
        actor_root = qualified_roots(
            self.fight,
            self.request,
            dict(self.rule, roots=[ACTOR_ROOT]),
            self.effects,
        )
        area_root = qualified_area_roots(
            self.fight,
            self.request,
            dict(self.rule, roots=[AREA_ROOT]),
            self.effects,
        )
        self.assertEqual(actor_root, {ACTOR_ROOT: self.effects[str(ACTOR_ROOT)]})
        self.assertEqual(area_root, {AREA_ROOT: self.effects[str(AREA_ROOT)]})

    def test_mixed_spell_uses_both_real_recipient_queries_and_preserves_costs(self):
        decision = {"result": "twE", "aligned": True, "diagnostic": {"native": 1}}
        adapter = SimpleNamespace(
            cast_condition=lambda *_: Conditions(lambda *_: decision)
        )
        seen_plan = {}

        class Factory:
            effects = self.effects

            def __call__(_self, _preview, plan):
                seen_plan.update(plan)
                return SimpleNamespace(handlers={}), []

        cell_invocation = EffectInvocation(0, 1, -200, -200, (0, 0, 0))
        with patch(
            "wakfu_server.combat.combat_npc_area_preflight.eligible_recipients",
            return_value=(7,),
        ) as actor_query, patch(
            "wakfu_server.combat.combat_npc_area_preflight.eligible_area_recipients",
            return_value=(88,),
        ) as area_query, patch(
            "wakfu_server.combat.combat_casting_context.cast_cell_condition",
            return_value=(object(), cell_invocation),
        ), patch(
            "wakfu_server.combat.combat_casting_context.NativeOwnedCastingContext.eligibility",
            return_value="twE",
        ):
            context = npc_cast_condition(
                adapter, self.fight, self.request, factory=Factory(), enabled=True
            )
            result = context.native_casting_query(self.rule, 3577, 100)

        self.assertEqual(result["result"], "twE")
        actor_query.assert_called_once()
        area_query.assert_called_once()
        policy = result["diagnostic"]["wakemu_npc_area_policy"]
        self.assertEqual(
            policy["producer"], "wakemu-npc-mixed-area-fighter-recipients-v1"
        )
        self.assertEqual(policy["recipients"], {ACTOR_ROOT: (7,), AREA_ROOT: (88,)})
        self.assertEqual(seen_plan["costs"], self.rule["costs"])
        self.assertEqual(seen_plan["effect_ids"], tuple(self.rule["roots"]))

    def test_false_area_criterion_rejects_area_without_suppressing_actor_root(self):
        effect = self.effects[str(AREA_ROOT)]
        dispatcher = SimpleNamespace(
            resolve=lambda *_: [SimpleNamespace(target_id=88)],
            condition_context=lambda *_: object(),
        )
        with patch(
            "wakfu_server.combat.combat_state_managers.registered_area_pv",
            return_value=object(),
        ), patch(
            "wakfu_server.combat.combat_conditions.evaluate_condition",
            return_value=False,
        ) as evaluate:
            self.assertEqual(
                eligible_area_recipients(
                    dispatcher,
                    effect,
                    EffectInvocation(AREA_ROOT, 100, -200, -200, (0, 0, 0)),
                    self.fight,
                ),
                (),
            )
        evaluate.assert_called_once_with("!IsOwnArea()", unittest.mock.ANY)

    def test_mixed_roots_without_any_actual_recipients_preserve_anchor_rejection(self):
        decision = {"result": "twE", "aligned": True}
        adapter = SimpleNamespace(
            cast_condition=lambda *_: Conditions(lambda *_: decision)
        )
        factory = Mock()
        factory.effects = self.effects
        factory.return_value = (SimpleNamespace(handlers={}), [])
        with patch(
            "wakfu_server.combat.combat_npc_area_preflight.eligible_recipients",
            return_value=(),
        ), patch(
            "wakfu_server.combat.combat_npc_area_preflight.eligible_area_recipients",
            return_value=(),
        ):
            context = npc_cast_condition(
                adapter, self.fight, self.request, factory=factory, enabled=True
            )
            self.assertIs(context.native_casting_query(self.rule, 3577, 100), decision)

    def test_unknown_mixed_root_stays_rejected_before_dispatch(self):
        decision = {"result": "twE", "aligned": True}
        adapter = SimpleNamespace(
            cast_condition=lambda *_: Conditions(lambda *_: decision)
        )
        factory = Mock()
        factory.effects = self.effects
        rule = dict(self.rule, roots=[ACTOR_ROOT, AREA_ROOT, 999999])
        context = npc_cast_condition(
            adapter, self.fight, self.request, factory=factory, enabled=True
        )
        self.assertIs(context.native_casting_query(rule, 3577, 100), decision)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
