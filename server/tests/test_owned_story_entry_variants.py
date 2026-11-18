"""Exclusive native entry variants do not confer physical visit authority."""

import unittest
from wakfu_server import owned_story_entry_variants as variants


class EntryVariantTests(unittest.TestCase):
    def test_exclusive_native_variants_and_legacy_single_admission(self):
        admission = dict(
            alternatives=[
                dict(quest_id=2773, objective_id=5592),
                dict(quest_id=2774, objective_id=5593),
            ],
            continuation_quest_id=2775,
        )
        for running, completed, expected in [
            ({2773}, set(), 5592),
            ({2774}, set(), 5593),
            (set(), set(), None),
            ({2775}, {2773}, None),
            ({2774}, {2773}, 5593),
            (set(), {2773, 2775}, None),
        ]:
            with self.subTest(running=running, completed=completed):
                actual = variants.running_variant(
                    admission, dict(running=running, completed=completed)
                )
                self.assertEqual(
                    None if actual is None else actual["objective_id"], expected
                )
        with self.assertRaisesRegex(ValueError, "Multiple mutually exclusive"):
            variants.running_variant(
                admission, dict(running={2773, 2774}, completed=set())
            )
        self.assertEqual(variants.quest_ids(admission), {2773, 2774, 2775})
        old = dict(quest_id=2166, objective_id=4288, continuation_quest_id=2170)
        self.assertEqual(
            variants.running_variant(old, dict(running={2166}, completed=set())),
            dict(quest_id=2166, objective_id=4288),
        )
        self.assertFalse(variants.admitted(old, dict(running=set(), completed=set())))
        self.assertTrue(variants.admitted(old, dict(running={2170}, completed={2166})))
