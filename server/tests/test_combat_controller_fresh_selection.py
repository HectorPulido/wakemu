from dataclasses import replace
from test_combat_effect_resolver import NativeResolverTests


class ControllerSelectionTests(NativeResolverTests):
    def test_fresh_controller_relationship_reselects_but_replay_keeps_chosen_pv(self):
        self.effect.update(
            effect_class=330,
            area_class="anD",
            area_native="point",
            parameters=[],
            parameter_count=0,
        )
        self.effect["native_target_selector"] = {
            "class": "fcE",
            "mask": (1 << 13) | (1 << 42),
        }
        self.native[1]["dpu_id"] = 2
        self.resolver.direct_target_policies = {"50": [330, False, False]}
        invocation = replace(
            self.invocation,
            target_id=3,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        self.assertEqual(
            [row.target_id for row in self.resolver(self.effect, invocation)], [2]
        )
        self.assertEqual(
            [
                row.target_id
                for row in self.resolver(
                    self.effect, replace(invocation, wakemu_fresh_child_selection=False)
                )
            ],
            [3],
        )
        self.native[1]["dpu_id"] = 99
        self.assertEqual(self.resolver(self.effect, invocation), ())
