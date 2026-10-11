"""eZd controller book stable level ranking and pre-insertion slices."""
import unittest
from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.combat_target_copy_book import TargetCopyBookAction
from wakfu_server.combat_controller_spellbook import controller_spellbook


class ControllerSpellbookTests(unittest.TestCase):
    def action(
        self, uid, level, *, elemental=True, neutral=False, special=False, roots=()
    ):
        action = CopyBookAction(uid, 4000 + uid, level, special, elemental, neutral)
        return TargetCopyBookAction(action, roots, elemental)

    def test_stable_levels_special_roots_and_neutral_priority(self):
        rows = tuple(self.action(uid, level) for uid, level in ((1, 5), (2, 8), (3, 8)))
        rows += (
            self.action(4, 2, elemental=False, neutral=True),
            self.action(5, 10, roots=(347,)),
            self.action(6, 20, special=True),
            self.action(7, 30, elemental=None),
        )
        selected = controller_spellbook(rows)
        self.assertEqual([row.uid for row in selected], [4, 2, 3, 1])
        self.assertIs(selected[1], rows[1].action)

    def test_native_slices_before_duplicate_insertion_do_not_backfill(self):
        # A known non-elemental/non-neutral kind can enter both native lists.
        rows = (self.action(1, 100, elemental=False),) + tuple(
            self.action(uid, 100 - uid) for uid in range(2, 11)
        )
        self.assertEqual(
            [row.uid for row in controller_spellbook(rows)], list(range(1, 8))
        )
        with self.assertRaises(ValueError):
            controller_spellbook((rows[0], rows[0]))
