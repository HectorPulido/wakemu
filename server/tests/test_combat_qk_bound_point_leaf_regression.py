"""Generic bound point recipients; production source is loaded from staged copy."""
import unittest
from dataclasses import replace
import test_combat_effect_resolver as baseline
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_damage_handler import NativeDamageHandler
import test_combat_damage_handler as damage
from wakfu_server.combat_effect_resolver import NativeEffectResolver


class BoundPointLeafTests(unittest.TestCase):
    def setUp(self):
        fixture = baseline.NativeResolverTests()
        fixture.setUp()
        self.actors = fixture.actors
        self.native = fixture.native
        self.context = fixture.context
        for row in self.native.values():
            row["bcN"] = 1
            row["bcR"] = True
        self.resolver = NativeEffectResolver(
            actors=lambda e, i: self.actors,
            native_context=lambda e, i: self.native,
            context=lambda e, i: self.context,
            direct_target_policies={"50": [3, False, False]},
        )
        self.effect = dict(
            fixture.effect,
            effect_class=3,
            area_class="anD",
            area_native="point",
            native_target_selector={"class": "fcE", "mask": (1 << 50) | 1},
        )
        self.invocation = replace(
            fixture.invocation,
            target_id=3,
            cell=self.actors[2].position,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )

    def test_point_damage_keeps_registered_pv_after_displacement(self):
        old = self.actors[2].position
        self.actors[2].position = (old[0] - 1, old[1], old[2])
        selected = self.resolver(self.effect, self.invocation)
        self.assertEqual([i.target_id for i in selected], [3])
        self.assertEqual(selected[0].cell, old)
        self.assertEqual(
            self.resolver(
                self.effect,
                replace(self.invocation, target_id=None, native_explicit_target=False),
            ),
            (),
        )

    def test_actor_group_retains_fresh_geometry_and_qk_eligibility(self):
        effect = dict(self.effect, effect_class=330, parameter_count=0, parameters=[])
        self.resolver.direct_target_policies = {"50": [330, False, False]}
        self.native[3]["bcN"] = -1
        self.assertEqual(self.resolver(effect, self.invocation), ())
        self.native[3]["bcN"] = 2
        self.assertEqual(
            [i.target_id for i in self.resolver(effect, self.invocation)], [3]
        )
        self.actors[2].position = (-2, 0, 0)
        self.assertEqual(self.resolver(effect, self.invocation), ())

    def test_removed_recipient_does_not_retarget_another_actor(self):
        self.actors[:] = [a for a in self.actors if a.id != 3]
        self.assertEqual(self.resolver(self.effect, self.invocation), ())

    def test_bound_zero_hp_keeps_identity_and_native_handler_guard(self):
        self.actors[2].hp = 0
        self.assertEqual(
            [i.target_id for i in self.resolver(self.effect, self.invocation)], [3]
        )
        # Selection does not authorize an absent death lifecycle contract.
        fixture = damage.DamageHandlerTests()
        fixture.setUp()
        fixture.fight.actors[-7].hp = 0
        with self.assertRaisesRegex(ValueError, "native HP0 runner target status"):
            fixture.handler(
                dict(fixture.effect, native_effect_flags=[15]), {}, fixture.invocation
            )
        self.assertEqual(fixture.packets, [])
