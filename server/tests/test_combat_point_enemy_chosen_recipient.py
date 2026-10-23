"""Original chosen-PV delivery survives ordered-group relationship flags."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_effect_resolver import (
    NativeEffectResolver,
    EffectResolutionContext,
)


class PointEnemyChosenRecipientTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "point_enemy_chosen_recipient_native.json"
            ).read_text()
        )
        self.actors = [
            SimpleNamespace(id=99, team=0, position=(0, 0, 0), hp=0, physical_radius=0)
        ] + [
            SimpleNamespace(
                id=i,
                team=1,
                position=(1, 0, 0),
                hp=0 if i == 2 else 100,
                physical_radius=0,
            )
            for i in range(1, 7)
        ]
        self.contexts = {
            actor.id: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for actor in self.actors
        }
        self.policies = dict(self.source["direct_target_policies"])
        self.resolver = NativeEffectResolver(
            actors=lambda effect, invocation: self.actors,
            native_context=lambda effect, invocation: self.contexts,
            context=lambda effect, invocation: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
            direct_target_policies=self.policies,
        )
        self.effect = self.source["effects"]["407770"]
        self.invocation = EffectInvocation(
            407770,
            1,
            99,
            3,
            (1, 0, 0),
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )

    def targets(self, effect=None, invocation=None):
        return [
            row.target_id
            for row in self.resolver(
                self.effect if effect is None else effect,
                self.invocation if invocation is None else invocation,
            )
        ]

    def test_original_polary_ordered_child_keeps_transmitted_killer(self):
        # Project the AP child of the zero-parameter original actor-group
        # route: the death subscription already selected its killer PV.
        parent = dict(
            self.effect,
            effect_class=330,
            parameters=[],
            parameter_count=0,
            children=[407770],
            native_target_selector={"class": "fcE", "mask": 1},
        )
        self.policies["90"] = [330, False, False]
        seen = []
        dispatcher = EffectDispatcher(
            {"90": parent, "407770": self.effect},
            {31: lambda effect, values, invocation: seen.append(invocation) or True},
            resolve=self.resolver,
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: next(
                a.position for a in self.actors if a.id == identity
            ),
        )
        self.assertTrue(dispatcher.execute(replace(self.invocation, reference=90)))
        self.assertEqual([row.target_id for row in seen], [3])
        self.assertTrue(seen[0].native_explicit_target)
        self.assertTrue(seen[0].wakemu_fresh_child_selection)
        self.assertEqual(self.policies["407770"], [31, False, False])
        self.assertEqual(self.effect["native_target_selector"]["mask"], 8200)

    def test_original_enemy_leaves_choose_only_when_native_route_requests_it(self):
        for reference, effect in self.source["effects"].items():
            with self.subTest(reference=reference):
                invocation = replace(self.invocation, reference=int(reference))
                policy = self.policies[reference]
                self.assertEqual(self.targets(effect, invocation), [3])
                # Replaying a selected PV and making an ordered fresh child
                # agree; the latter flag alone does not authorize fan-out.
                self.assertEqual(
                    self.targets(
                        effect, replace(invocation, wakemu_fresh_child_selection=False)
                    ),
                    [3],
                )
                self.assertEqual(
                    self.targets(
                        effect,
                        replace(
                            invocation, target_id=None, native_explicit_target=False
                        ),
                    ),
                    list(range(1, 7)),
                )
                self.policies[reference] = [policy[0], True, False]
                self.assertEqual(self.targets(effect, invocation), list(range(1, 7)))
                self.policies[reference] = policy

    def test_nonpoint_area_and_actor_group_keep_fresh_population(self):
        area = dict(self.effect, area_class="anu", area_native="circle-2")
        self.assertEqual(self.targets(area), list(range(1, 7)))
        group = dict(self.effect, effect_class=330, parameters=[], parameter_count=0)
        self.policies["407770"] = [330, False, False]
        self.assertEqual(self.targets(group), list(range(1, 7)))

    def test_rushu_chosen_population_keeps_each_point_recipient_and_cell(self):
        for actor in self.actors:
            actor.position = (actor.id, 0, 0)
        self.policies["90"] = [330, False, False]
        for reference in ("319215", "319303"):
            with self.subTest(reference=reference):
                leaf = self.source["effects"][reference]
                self.assertEqual(leaf["native_target_selector"]["mask"], 9)
                parent = dict(
                    self.effect,
                    effect_class=330,
                    parameters=[],
                    parameter_count=0,
                    children=[int(reference)],
                    native_target_selector={"class": "fcE", "mask": 1},
                )
                seen = []
                dispatcher = EffectDispatcher(
                    {"90": parent, reference: leaf},
                    {
                        leaf[
                            "effect_class"
                        ]: lambda effect, values, invocation: seen.append(
                            (invocation.target_id, invocation.cell)
                        )
                        or True
                    },
                    resolve=self.resolver,
                    condition_context=lambda invocation: ConditionContext({}),
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: (),
                    actor_position=lambda identity: next(
                        a.position for a in self.actors if a.id == identity
                    ),
                )
                for identity in (1, 3, 5):
                    self.assertTrue(
                        dispatcher.execute(
                            replace(
                                self.invocation,
                                reference=90,
                                target_id=identity,
                                cell=(identity, 0, 0),
                            )
                        )
                    )
                self.assertEqual(seen, [(i, (i, 0, 0)) for i in (1, 3, 5)])
