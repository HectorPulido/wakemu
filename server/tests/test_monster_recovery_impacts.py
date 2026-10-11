"""Impact expansion preserves scope and never becomes readiness evidence."""
import unittest
from audit_monster_recovery_impacts import affected_references


class RecoveryImpactTests(unittest.TestCase):
    def row(self, reference, effects, missing=None):
        return dict(
            ref=reference,
            name=f"Monster {reference}",
            dependencies=dict(effect_ids=effects, missing_definitions=missing or []),
        )

    def test_shared_native_effect_expands_across_monsters_only_in_scope(self):
        rows = affected_references(
            [self.row(1, [8]), self.row(2, [8, 9]), self.row(3, [8])], [1, 2], [8]
        )
        self.assertEqual([r["ref"] for r in rows], [1, 2])
        self.assertEqual([r["effect_ids"] for r in rows], [[8], [8]])
        self.assertTrue(
            all(r["status"] == "structural_dependency_replay_pending" for r in rows)
        )

    def test_missing_graph_edges_are_preserved_without_readiness_claim(self):
        rows = affected_references(
            [self.row(1, [8], ["spells:99"]), self.row(2, [])], [1, 2], [8]
        )
        self.assertEqual(rows[0]["missing_definitions"], ["spells:99"])
        self.assertNotIn("ready", rows[0])

    def test_duplicate_or_missing_scope_reference_rejects(self):
        for inventory in ([self.row(1, [8])] * 2, []):
            with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                affected_references(inventory, [1], [8])

    def test_unknown_effect_or_scope_identity_rejects(self):
        for scope, effects in (([True], [8]), ([1], [True]), ([1], [0])):
            with self.subTest(scope=scope, effects=effects), self.assertRaises(
                ValueError
            ):
                affected_references([self.row(1, [8])], scope, effects)

    def test_scope_deduplication_cannot_hide_boolean_identity(self):
        for scope in ([1, True], [1, 1]):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                affected_references([self.row(1, [8])], scope, [8])

    def test_inventory_boolean_cannot_match_integer_scope(self):
        with self.assertRaises(ValueError):
            affected_references([self.row(True, [8])], [1], [8])
