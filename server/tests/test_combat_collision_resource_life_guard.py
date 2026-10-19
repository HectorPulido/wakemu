"""Direct collision calls preserve native corpse guards and prepared UID authority."""
from dataclasses import replace
import unittest

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)


class CollisionResourceLifeGuardTests(unittest.TestCase):
    def setUp(self):
        from test_combat_collision_resource import CollisionResourceTests

        fixture = CollisionResourceTests()
        fixture.setUp()
        self.fixture = fixture
        initialize_global_pv_collections(fixture.fight, tuple(fixture.fight.actors))

    def test_registered_corpse_skips_before_runner_allocation_and_lifecycle(self):
        fixture = self.fixture
        target = fixture.fight.actors[-7]
        target.hp = target.effect_stats[1] = 0
        set_global_fighter_status(fixture.fight, target.id, "OFF_PLAY")
        fixture.handler.allocate_uid = lambda: self.fail(
            "Ineligible corpse allocated UID"
        )
        self.assertFalse(fixture.executor(7, -7))
        self.assertEqual(target.ap, 6)
        self.assertEqual(fixture.phases, [])
        self.assertEqual(fixture.packets, [])
        self.assertEqual(fixture.states, [])
        self.assertEqual(fixture.handler.prepared, {})
        self.assertEqual(fixture.handler.runner_amounts, {})

    def test_live_zero_ap_keeps_native_calculation_without_resource_mutation(self):
        fixture = self.fixture
        target = fixture.fight.actors[-7]
        target.ap = target.effect_stats[2] = 0
        self.assertTrue(fixture.executor(7, -7))
        self.assertEqual(target.ap, 0)
        self.assertEqual(fixture.phases, [1, 2, 3, 4])
        self.assertEqual(fixture.packets, [])
        self.assertEqual(fixture.handler.prepared, {})
        self.assertEqual(fixture.handler.runner_amounts, {})

    def test_live_nonzero_ap_keeps_paid_loss_secondary_state_and_delivery(self):
        fixture = self.fixture
        fixture.test_shared_lifecycle_secondary_and_signed_registration()

    def test_unprepared_running_uid_remains_strictly_rejected(self):
        fixture = self.fixture
        invocation = EffectInvocation(
            -13,
            0,
            7,
            -7,
            fixture.fight.actors[-7].position,
            base_uid=0,
            native_retained_container={"present": False},
            native_explicit_target=True,
        )
        with self.assertRaisesRegex(
            ValueError, "Missing native prepared eVZ running effect"
        ):
            fixture.handler(
                fixture.definition,
                {},
                replace(invocation, native_running_uid=901),
            )
        self.assertEqual(fixture.fight.actors[-7].ap, 6)
        self.assertEqual(fixture.phases, [])
        self.assertEqual(fixture.packets, [])


if __name__ == "__main__":
    unittest.main()
