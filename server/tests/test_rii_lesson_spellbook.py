"""Training fights own the spell set their encounter accepts."""

import unittest
from unittest.mock import patch
from types import SimpleNamespace

from wakfu_server.combat.rii_lesson_spellbook import (
    accepts,
    lesson_contract,
    lesson_spells,
)


class LessonSpellbookTests(unittest.TestCase):
    def fight(self, **extra):
        fight = SimpleNamespace(actors={7: SimpleNamespace(id=7)})
        fight.rii_distance_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        del extra
        return fight

    def test_ordinary_fights_keep_the_full_book(self):
        fight = SimpleNamespace(actors={7: SimpleNamespace(id=7)})
        self.assertIsNone(lesson_contract(fight))
        self.assertTrue(accepts(fight, 7, 1234))

    def test_multiple_bound_lessons_are_rejected(self):
        fight = self.fight()
        fight.rii_area_lesson_contract = {"owner": 7, "targets": [-7]}
        with self.assertRaises(ValueError):
            lesson_contract(fight)

    def test_visitor_spells_are_outside_the_lesson_book(self):
        fight = self.fight()
        with patch.dict(
            "sys.modules",
            {
                "wakfu_server.combat.combat_spell_grant": SimpleNamespace(
                    granted_spells=lambda *_: {7967: {"uid": 7967}}
                ),
                "wakfu_server.combat.combat_morph_spellbook": SimpleNamespace(
                    morph_record=lambda *_: None
                ),
            },
        ):
            self.assertEqual(lesson_spells(fight), {7967})
            self.assertTrue(accepts(fight, 7, 7967))
            self.assertFalse(accepts(fight, 7, 4779))
            # Controlled actors keep their own books inside the lesson.
            self.assertTrue(accepts(fight, -40, 4779))

    def test_native_morph_book_and_grants_are_the_only_owner_spells(self):
        fight = self.fight()
        with patch.dict(
            "sys.modules",
            {
                "wakfu_server.combat.combat_spell_grant": SimpleNamespace(
                    granted_spells=lambda *_: {7967: {"uid": 7967}}
                ),
                "wakfu_server.combat.combat_morph_spellbook": SimpleNamespace(
                    morph_record=lambda *_: {
                        "levels": {7967: 1, 17777: 1, 18888: 1},
                        "removed_raw_uids": {18888},
                    }
                ),
            },
        ):
            self.assertEqual(lesson_spells(fight), {7967, 17777})
            self.assertTrue(accepts(fight, 7, 17777))
            self.assertFalse(accepts(fight, 7, 4779))

    def test_orientation_lesson_keeps_the_visitor_class_spellbook(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7)},
            rii_orientation_contract={"owner": 7, "target": -7},
        )
        with patch.dict(
            "sys.modules",
            {
                "wakfu_server.combat.combat_spell_grant": SimpleNamespace(
                    granted_spells=lambda *_: (_ for _ in ()).throw(
                        AssertionError("orientation has no temporary grants")
                    )
                ),
                "wakfu_server.combat.combat_morph_spellbook": SimpleNamespace(
                    morph_record=lambda *_: (_ for _ in ()).throw(
                        AssertionError("orientation has no morphology")
                    )
                ),
            },
        ):
            self.assertIsNone(lesson_spells(fight))
            self.assertTrue(accepts(fight, 7, 5562))


if __name__ == "__main__":
    unittest.main()
