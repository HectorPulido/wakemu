import itertools
import unittest
from wakfu_server.combat_character_copy_book import (
    CopyBookAction,
    copy_character_book,
    copy_spell_level,
)


class CharacterCopyBookTests(unittest.TestCase):
    def book(self, actions, **overrides):
        values = dict(
            availability_present=False,
            available_references=(),
            selector_present=False,
            selector_cap=-1,
            actor_cap=200,
            minimum=0,
            maximum=245,
            allocate_uid=itertools.count(100).__next__,
        )
        values.update(overrides)
        return copy_character_book(tuple(actions), **values)

    def test_fallback_neutral_first_preserves_source_order_and_clone_identity(self):
        actions = [
            CopyBookAction(i, i, 20, False, i % 2 == 0, i % 2 == 1)
            for i in range(1, 29)
        ]
        copied = self.book(actions)
        self.assertEqual(
            [a.reference for a in copied], [1, 3, 5, 7, 9] + list(range(2, 29, 2))
        )
        self.assertEqual([a.uid for a in copied[:5]], [100, 102, 104, 106, 108])
        self.assertEqual(actions[0].uid, 1)

    def test_selected_book_keeps_special_and_allocates_before_filtering(self):
        actions = [CopyBookAction(i, i, 200, True, True, False) for i in range(1, 5)]
        copied = self.book(
            actions,
            availability_present=True,
            available_references=(2, 4),
            selector_present=True,
            selector_cap=80,
        )
        self.assertEqual(
            [(a.reference, a.uid, a.level) for a in copied],
            [(2, 101, 80), (4, 103, 80)],
        )

    def test_empty_selected_book_reclones_fallback(self):
        action = CopyBookAction(10, 20, 200, False, True, False)
        self.assertEqual(self.book([action], availability_present=True)[0].uid, 101)

    def test_level_minimum_narrows_to_short_before_domain_clamp(self):
        values = dict(selector_present=True, actor_cap=200, minimum=0, maximum=245)
        self.assertEqual(copy_spell_level(245, selector_cap=-1, **values), 200)
        self.assertEqual(copy_spell_level(245, selector_cap=-32769, **values), 245)
        self.assertEqual(copy_spell_level(245, selector_cap=80, **values), 80)
        with self.assertRaises(ValueError):
            self.book(
                [CopyBookAction(1, 2, 200, False, None, False)],
                availability_present=None,
            )
