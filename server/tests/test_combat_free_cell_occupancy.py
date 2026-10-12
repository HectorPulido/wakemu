"""Native fcj free-center gate consumes registered QK occupancy."""
import unittest
from server.tests import test_combat_casting_eligibility as eligibility_fixture
from server.tests import test_combat_use_gate_conditions as context_fixture
from wakfu_server.combat_casting_eligibility import (
    NativeCastingFlags,
    native_casting_eligibility,
)


class FreeCellOccupancyTests(unittest.TestCase):
    def evaluate(self, context):
        fixture = eligibility_fixture.NativeCastingEligibilityTests()
        return native_casting_eligibility(
            fixture.hooks(qi_g=context.qi_g), NativeCastingFlags(free_cell=True)
        )

    def test_registered_fighter_center_rejects_before_target_selector(self):
        context, fight = context_fixture.NativeUseGateConditionsTests().context()
        for hp in (100, 0):
            with self.subTest(hp=hp):
                fight.actors[8].hp = hp
                self.assertEqual(self.evaluate(context), "twT")

    def test_adjacent_occupancy_does_not_forbid_a_free_cast_center(self):
        context, _ = context_fixture.NativeUseGateConditionsTests().context()
        context.cell = (2, 0, 0)
        self.assertEqual(self.evaluate(context), "twD")
        context.cell = (1, 0, 0)
        context._registry.slots[1]["movement_blocking"] = False
        self.assertEqual(self.evaluate(context), "twD")
