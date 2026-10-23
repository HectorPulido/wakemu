"""Constructor-proven neutral bcM remains distinct from owned faV.j captures."""
from copy import deepcopy
import unittest


class NativeNeutralAreaAffiliationTests(unittest.TestCase):
    def fixture(self):
        from test_encounter_glyph_bootstrap import EncounterGlyphBootstrapTests
        from wakfu_server.combat_encounter_glyph_bootstrap import point_glyph_row

        fixture = EncounterGlyphBootstrapTests()
        fixture.setUp()
        sources = fixture.prepare()
        fixture.fight.native_environment_glyph_constructors = sources
        row = point_glyph_row(sources[0], fixture.definition)
        fixture.fight.native_effect_areas[row["uid"]] = row
        return fixture.fight, row

    def test_declared_neutral_constructor_preserves_minus_one_without_owner_or_j_capture(
        self,
    ):
        from wakfu_server.combat_area_affiliation import area_affiliation

        fight, row = self.fixture()
        self.assertEqual(area_affiliation(fight, row), -1)
        self.assertIsNone(row["owner_id"])
        self.assertEqual(
            row["native_fight_affiliation_source"], "faV.constructor.null_owner"
        )
        self.assertNotIn("state_ledger", row)
        with self.assertRaises(ValueError):
            area_affiliation(fight, deepcopy(row))
        foreign, _other_row = self.fixture()
        with self.assertRaises(ValueError):
            area_affiliation(foreign, row)

    def test_invalid_neutral_capture_or_constructor_never_borrows_an_owner(self):
        from wakfu_server.combat_area_affiliation import area_affiliation

        for key, value in (
            ("native_fight_affiliation", 0),
            ("native_fight_affiliation", True),
            ("owner_id", 7),
            ("native_environment_source", "unknown"),
            ("native_fight_affiliation_source", "unknown"),
        ):
            with self.subTest(key=key, value=value):
                fight, row = self.fixture()
                row[key] = value
                with self.assertRaises(ValueError):
                    area_affiliation(fight, row)
        fight, row = self.fixture()
        fight.native_environment_glyph_constructors = []
        with self.assertRaises(ValueError):
            area_affiliation(fight, row)

    def test_actual_border_constructor_and_retired_native_pointer_preserve_neutral_bcM(
        self,
    ):
        from test_combat_battleground_border import BattlegroundBorderTests
        from wakfu_server.combat_area_affiliation import area_affiliation
        from wakfu_server.combat_battleground_border import install_battleground_border
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import selected_area_pv_scope

        fight, arena = BattlegroundBorderTests().fixture()
        row = install_battleground_border(fight, arena, reference=46, identity=-100)
        self.assertEqual(area_affiliation(fight, row), -1)
        with selected_area_pv_scope(fight, (-100,)):
            remove_owned_hour_area(fight, -100)
            self.assertNotIn(-100, fight.native_effect_areas)
            self.assertEqual(area_affiliation(fight, row), -1)
        with self.assertRaises(ValueError):
            area_affiliation(fight, row)
