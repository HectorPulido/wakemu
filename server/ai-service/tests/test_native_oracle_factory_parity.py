"""Oracle factories preserve real fight-pinned definitions and RNG ownership."""
import random
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_native_oracle as oracle_fixtures
import test_combat_owned_equipment_pin as equipment_fixtures
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class NativeOracleFactoryParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        equipment_fixtures.OwnedEquipmentPinTests.setUpClass()
        cls.equipment = equipment_fixtures.OwnedEquipmentPinTests(
            "test_actual_plan_pin_is_immutable_detached_and_used_by_later_factory"
        )

    def fixture(self):
        character, (fight, preparation) = self.equipment.pin()
        oracle = oracle_fixtures.NativeOracleTests.oracle_for(
            RuntimeMessages(fight),
            character,
            self.equipment.native.monster,
            encode_deck(),
        )
        return oracle, fight, preparation

    def test_actual_pinned_item_definitions_survive_oracle_factory_rebinding(self):
        oracle, fight, preparation = self.fixture()
        original = snapshot(fight)
        rng = random.Random(73)
        factory, _ = oracle.factory(fight, 2, rng)
        source = preparation["sources"][0]
        root = str(source["roots"][0])
        self.assertEqual(source["source_reference"], 27152)
        dispatcher, packets = factory(
            deepcopy(fight), {"native_retained_container": {"present": False}}
        )
        self.assertTrue(
            root in dispatcher.effects,
            f"Pinned item27152 root {root} missing from oracle definitions "
            f"(definition count {len(dispatcher.effects)})",
        )
        self.assertEqual(
            dispatcher.effects[root]["effect_class"],
            source["effects"][root]["effect_class"],
        )
        self.assertEqual(len(packets), 0)
        self.assertTrue(snapshot(fight) == original, "Source fight was mutated")

    def test_oracle_displacement_handler_owns_the_actual_transaction_rng(self):
        from wakfu_server.combat_displacement import NativeDisplacementHandler

        oracle, fight, _ = self.fixture()
        rng = random.Random(73)
        expected = random.Random(73)
        factory, _ = oracle.factory(fight, 2, rng)
        constructed = []
        initialize = NativeDisplacementHandler.__init__

        def observe(instance, *args, **kwargs):
            initialize(instance, *args, **kwargs)
            constructed.append(instance)

        # Retention wraps dispatcher handlers as callables. Observe the actual
        # native constructor without replacing its implementation or metadata.
        with patch.object(NativeDisplacementHandler, "__init__", observe):
            factory(deepcopy(fight), {"native_retained_container": {"present": False}})
        self.assertEqual(len(constructed), 1)
        handler = constructed[0]
        self.assertTrue(
            callable(handler.draw_direction),
            "Oracle displacement handler has no transaction-owned RNG callback",
        )
        self.assertEqual(handler.draw_direction(), expected.randint(1, 4))
        self.assertTrue(
            rng.getstate() == expected.getstate(),
            "Oracle displacement consumed a different RNG stream",
        )


if __name__ == "__main__":
    unittest.main()
