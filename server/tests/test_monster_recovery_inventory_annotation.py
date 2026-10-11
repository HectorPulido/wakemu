"""Pattern annotations cannot promote historical proof or alter source inputs."""
import unittest
from annotate_monster_recovery_inventory import annotate


class InventoryAnnotationTests(unittest.TestCase):
    def fixture(self):
        inventory = dict(
            baseline_enabled=854,
            activated_by_this_work=0,
            monsters=[
                dict(ref=1, status="pending", enabled=False, full_book_qualified=False)
            ],
        )
        queue = dict(
            groups=[
                dict(
                    pattern="shared",
                    references=[dict(ref=1, status="native_replay_pending")],
                )
            ],
            unique_reference_count=1,
        )
        return inventory, queue

    def test_annotation_preserves_proof_and_does_not_mutate_input(self):
        inventory, queue = self.fixture()
        result = annotate(inventory, queue)
        self.assertEqual(result["baseline_enabled"], 854)
        self.assertEqual(result["activated_by_this_work"], 0)
        self.assertEqual(result["monsters"][0]["status"], "pending")
        self.assertFalse(result["monsters"][0]["full_book_qualified"])
        self.assertFalse(result["monsters"][0]["enabled"])
        self.assertNotIn("affected_source_patterns", inventory["monsters"][0])
        self.assertEqual(result["source_fix_affected_count"], 1)

    def test_out_of_scope_boolean_and_duplicate_references_reject(self):
        for refs in ([2], [True], [1, 1]):
            inventory, queue = self.fixture()
            queue["groups"][0]["references"] = [
                dict(ref=r, status="pending") for r in refs
            ]
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                annotate(inventory, queue)

    def test_stale_count_and_duplicate_patterns_reject(self):
        inventory, queue = self.fixture()
        queue["unique_reference_count"] = 9
        with self.assertRaises(ValueError):
            annotate(inventory, queue)
        queue["unique_reference_count"] = 1
        queue["groups"] *= 2
        with self.assertRaises(ValueError):
            annotate(inventory, queue)
