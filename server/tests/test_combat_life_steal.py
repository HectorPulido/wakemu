import unittest
from types import SimpleNamespace
from wakfu_server.combat_life_steal import life_steal_amount, life_steal_event_ids
from wakfu_server.combat_value_transfer import transfer_value_context


class LifeStealTests(unittest.TestCase):
    def test_original_probe_matrix(self):
        for amount, bonus, resistance, override, enabled, expected in (
            (10, 50, 200, 0, 1, 12),
            (1, 50, 0, 0, 1, 1),
            (7, 50, 100, 4, 1, 5),
            (7, 50, 100, 4, 0, 3),
            (10, 0, 1200, 0, 1, 0),
        ):
            self.assertEqual(
                life_steal_amount(
                    [amount, 0, enabled, 0],
                    1,
                    {53: bonus},
                    {32: resistance},
                    transfer_value_context(b"", override),
                ),
                expected,
            )

    def test_no_mastery_or_critical_bonus_is_fabricated(self):
        self.assertEqual(
            life_steal_amount([10, 0], 1, {53: 0, 20: 2000, 40: 2000}, {32: 0}), 10
        )
        with self.assertRaises(ValueError):
            life_steal_amount([10, 0], 1, {}, {32: 0})
        self.assertEqual(life_steal_amount([10, 0, 0, 0], 1, {}, {32: 0}), 10)

    def test_element_event_from_actual_container_not_healing_default(self):
        def retention(kind, ref=1542):
            return SimpleNamespace(
                container=lambda invocation: (
                    {"container_present": True, "container_type": kind},
                    (ref << 16) + 19,
                )
            )

        self.assertEqual(life_steal_event_ids(retention(11), None), (0, 1, 16, 20))
        self.assertEqual(
            life_steal_event_ids(retention(11, 6257), None), (0, 1, 13, 20)
        )
        self.assertEqual(life_steal_event_ids(retention(3), None), (0, 1, 20))
        self.assertEqual(life_steal_event_ids(retention(25), None), (0, 1, 20))
