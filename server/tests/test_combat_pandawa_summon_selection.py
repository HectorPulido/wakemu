"""Fresh own-summon relationship selection preserves native chosen-PV replay."""
from dataclasses import replace
import unittest
import test_combat_effect_resolver as resolver_fixture


class PandawaSummonSelectionTests(unittest.TestCase):
    def test_fresh_own_summon_selector_replaces_transmitted_carrier(self):
        fixture = resolver_fixture.NativeResolverTests()
        fixture.setUp()
        fixture.effect.update(effect_class=330, area_class="anD", area_native="point")
        fixture.effect["native_target_selector"]["mask"] = 4096
        fixture.resolver.direct_target_policies = {"50": [330, False, False]}
        for identity in (1, 2, 3):
            fixture.native[identity].update(
                dTE=identity != 1,
                dpu_id=1 if identity == 2 else identity,
                baG=False,
                baK=False,
            )
        invocation = replace(
            fixture.invocation,
            target_id=1,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        selected = fixture.resolver(fixture.effect, invocation)
        self.assertEqual([row.target_id for row in selected], [2])
        # Actual Qe.g / event replay keeps its already selected PV.
        replay = fixture.resolver(
            fixture.effect, replace(invocation, wakemu_fresh_child_selection=False)
        )
        self.assertEqual([row.target_id for row in replay], [1])
        for flag in ("baG", "baK"):
            fixture.native[2][flag] = True
            self.assertEqual(fixture.resolver(fixture.effect, invocation), ())
            fixture.native[2][flag] = False
