"""Source-only queue boundaries and exact native book identity."""
import unittest
from qualify_monster_low50_queue import selected_jobs, exact_book_complete


class Low50QueueTests(unittest.TestCase):
    def queue(self):
        return {
            "jobs": [
                dict(
                    reference=7,
                    state="no_published_low50_overlap",
                    exception=None,
                    uncovered_intervals=[[8, 18]],
                    owned_spell_ids=[3, 4],
                ),
                dict(
                    reference=8,
                    state="partly_published_low50_range",
                    exception=None,
                    uncovered_intervals=[[50, 50]],
                    owned_spell_ids=[5],
                ),
            ]
        }

    def test_first_level_only_never_published_not_active_tail(self):
        rows = selected_jobs(self.queue(), set(), set(), True)
        self.assertEqual(
            [(r["reference"], r["execution_levels"]) for r in rows], [(7, [8])]
        )

    def test_explicit_exclusion_preserves_other_owners(self):
        self.assertEqual(selected_jobs(self.queue(), set(), {7}, True), [])

    def test_full_owned_identity_accepts_passive_via_original_qualifier(self):
        cases = [dict(level=8, spell_id=3, spell_level=1, status="passive")]
        self.assertTrue(
            exact_book_complete(
                cases,
                [dict(spell_id=3, spell_level=1)],
                8,
                lambda c: c["status"] == "passive",
            )
        )

    def test_missing_duplicate_or_wrong_spell_level_rejected(self):
        cases = [dict(level=8, spell_id=3, spell_level=1)]
        owned = [dict(spell_id=3, spell_level=2)]
        self.assertFalse(exact_book_complete(cases, owned, 8, lambda c: True))
        self.assertFalse(
            exact_book_complete(
                cases * 2, [dict(spell_id=3, spell_level=1)], 8, lambda c: True
            )
        )
