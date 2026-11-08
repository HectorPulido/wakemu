"""Single-use manager reads retain fresh authority without snapshot copies."""
import unittest
from unittest.mock import patch
from test_retained_local_query import fixture, add_parent
from wakfu_server import combat_retained_runtime as retained
from wakfu_server.combat_retained_query import manager_query
from wakfu_server.combat_selected_retained_values import SelectedRetainedValues


class SelectedSingleReadTests(unittest.TestCase):
    def test_selected_and_parent_unique_reads_cold_warm_mutation_and_errors(self):
        fight, retention = fixture()
        add_parent(fight)
        observed = []
        original = SelectedRetainedValues.read

        def read(values, owner, uid, record):
            result = original(values, owner, uid, record)
            observed.append((values, uid))
            return result

        with patch.object(SelectedRetainedValues, "read", read):
            cold = manager_query(fight, 1)
        self.assertIsNotNone(cold)
        self.assertEqual([uid for _, uid in observed], [10, 30])
        self.assertTrue(
            all(
                not values.keep_current and values.current == {}
                for values, _ in observed
            )
        )
        expected = retention.view().manager_entries(1)
        self.assertEqual(cold.entries, expected)
        self.assertEqual(manager_query(fight, 1).entries, expected)
        # In-place metadata mutations remain visible even with a borrowed full cache.
        record = fight.native_retained_records[10]
        record["state_unremovable"] = True
        self.assertTrue(manager_query(fight, 1).by_uid[10].state_unremovable)
        fight.native_owned_group_effects[20]["payload"] = "zz"
        self.assertIsNotNone(manager_query(fight, 1))
        fight.state_wire_payloads[30] = "zz"
        with self.assertRaises(ValueError):
            manager_query(fight, 1)
        # The general reusable reader keeps its previous behavior.
        values = SelectedRetainedValues(fight)
        values.read(fight, 10, record)
        self.assertIn(10, values.current)


if __name__ == "__main__":
    unittest.main()
