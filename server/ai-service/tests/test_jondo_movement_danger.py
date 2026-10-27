"""Perimeter risk export uses active native geometry without changing the fight."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from wakfu_ai.bridge.jondo_snapshot import movement_danger
from wakfu_server.combat_battleground_border import POLICY, SOURCE


class MovementDangerTests(unittest.TestCase):
    def fixture(self):
        row = dict(
            native_area_contract="faP",
            native_border_source=SOURCE,
            native_border_policy=POLICY,
            owner_id=None,
            level=0,
            direction=-1,
            native_geometry_reference_source="faP.h.fbg.QI_P",
            native_cells_xy=((0, 0),),
            remaining_activations=-1,
        )
        fight = SimpleNamespace(
            native_effect_areas={-100: row},
            native_border_cells=((0, 0, 0),),
            native_qi_snapshot=dict(
                x=0, y=0, width=3, height=1, cell_masks=[128 | 4, 5, 5]
            ),
        )
        actor = SimpleNamespace(physical_radius=0, mp=4, ap=6)
        indices = {(0, 0, 0): 0, (0, 0, 3): 1, (1, 0, 0): 2, (2, 0, 0): 3}
        return fight, actor, indices

    def test_active_border_uses_native_xy_and_radius_without_mutation(self):
        fight, actor, indices = self.fixture()
        before = deepcopy(vars(fight)), deepcopy(vars(actor))
        self.assertEqual(
            movement_danger(fight, actor, indices),
            [dict(cell=0, cost=3), dict(cell=1, cost=3)],
        )
        self.assertEqual((vars(fight), vars(actor)), before)
        actor.physical_radius = 1
        self.assertEqual(
            movement_danger(fight, actor, indices),
            [dict(cell=0, cost=3), dict(cell=1, cost=3), dict(cell=2, cost=3)],
        )

    def test_retired_exhausted_and_beneficial_areas_have_no_border_penalty(self):
        fight, actor, indices = self.fixture()
        row = fight.native_effect_areas.pop(-100)
        self.assertEqual(movement_danger(fight, actor, indices), [])
        fight.native_effect_areas[-100] = dict(row, remaining_activations=0)
        self.assertEqual(movement_danger(fight, actor, indices), [])
        fight.native_effect_areas[-100] = dict(row, native_area_contract="faN")
        self.assertEqual(movement_danger(fight, actor, indices), [])

    def test_unverified_border_geometry_is_rejected(self):
        fight, actor, indices = self.fixture()
        fight.native_effect_areas[-100]["native_cells_xy"] = ((2, 0),)
        with self.assertRaisesRegex(ValueError, "shape disagrees"):
            movement_danger(fight, actor, indices)

    def glyph_fixture(self, *, family=1, selector=1, owner_team=1, traveler_team=0):
        owner = SimpleNamespace(id=10, team=owner_team)
        actor = SimpleNamespace(id=20, team=traveler_team, physical_radius=0)
        row = dict(
            uid=-200,
            reference=123,
            native_area_contract="faY",
            owner_id=10,
            level=1,
            remaining_activations=-1,
            native_fight_affiliation=owner_team,
            cell=(1, 1, 0),
            native_cells_xy=((1, 1),),
        )
        fight = SimpleNamespace(
            actors={10: owner, 20: actor}, native_effect_areas={-200: row}
        )
        definition = dict(
            type="GLYPH",
            entry_masks=[10001, 10008, 10000],
            effect_ids=[1],
            native_area_properties=[],
        )
        effect = dict(
            effect_class=family,
            native_target_selector=dict(class_="unused"),
            children=[],
            criteria="",
        )
        effect["native_target_selector"] = {"class": "fcE", "mask": selector}
        indices = {(1, 1, 0): 0, (2, 1, 0): 1}
        return fight, actor, indices, definition, effect

    def classify_fixture(self, fixture):
        fight, actor, indices, definition, effect = fixture
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"123": definition},
        ), patch(
            "wakfu_server.combat_effect_area_catalog.area_effect_catalog",
            return_value={"effects": {"1": effect}},
        ), patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value={
                "effects": {"48": {"fixed_stat_id": 2, "operation": "lose_current"}}
            },
        ):
            return movement_danger(fight, actor, indices)

    def test_interior_damage_and_resource_loss_are_soft_hazards(self):
        for family in (1, 48):
            with self.subTest(family=family):
                fixture = self.glyph_fixture(family=family)
                before = deepcopy(vars(fixture[0])), deepcopy(vars(fixture[1]))
                self.assertEqual(self.classify_fixture(fixture), [dict(cell=0, cost=3)])
                self.assertEqual((vars(fixture[0]), vars(fixture[1])), before)

    def test_healing_and_positive_glyphs_are_not_hazards(self):
        for family in (25, 160):
            with self.subTest(family=family):
                self.assertEqual(
                    self.classify_fixture(self.glyph_fixture(family=family)), []
                )

    def test_enemy_only_damage_glyph_respects_actual_traveler_relation(self):
        self.assertEqual(
            self.classify_fixture(self.glyph_fixture(selector=1 | 8)),
            [dict(cell=0, cost=3)],
        )
        self.assertEqual(
            self.classify_fixture(self.glyph_fixture(selector=1 | 8, traveler_team=1)),
            [],
        )

    def test_native_area_ally_exemption_and_retirement_are_preserved(self):
        fixture = self.glyph_fixture(traveler_team=1)
        fixture[3]["native_area_properties"] = [1]
        self.assertEqual(self.classify_fixture(fixture), [])
        fixture = self.glyph_fixture()
        fixture[0].native_effect_areas[-200]["remaining_activations"] = 0
        self.assertEqual(self.classify_fixture(fixture), [])

    def test_only_real_contact_or_turn_start_subscriptions_add_risk(self):
        fixture = self.glyph_fixture()
        fixture[3]["entry_masks"] = [10016]
        self.assertEqual(self.classify_fixture(fixture), [])
        fixture = self.glyph_fixture()
        fixture[3]["type"] = "PORTAL"
        self.assertEqual(self.classify_fixture(fixture), [])

    def test_conditional_damage_remains_possible_risk(self):
        fixture = self.glyph_fixture()
        fixture[4]["criteria"] = 'SomeNativeCondition("target")'
        self.assertEqual(self.classify_fixture(fixture), [dict(cell=0, cost=3)])

    def test_actual_environment_910_is_a_beneficial_range_glyph(self):
        fight, actor, indices, _, _ = self.glyph_fixture()
        row = fight.native_effect_areas[-200]
        row.update(reference=910, owner_id=None, native_fight_affiliation=-1)
        self.assertEqual(movement_danger(fight, actor, indices), [])

    def test_actual_sram_trap_778_projects_damage_on_interior_cells(self):
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_trap_area import install_trap_characteristics

        fight, actor, indices, _, _ = self.glyph_fixture()
        row = fight.native_effect_areas[-200]
        row.update(reference=778, native_area_contract="fbc", native_type_id=3)
        install_trap_characteristics(row, native_effect_areas()["778"])
        before = deepcopy(vars(fight)), deepcopy(vars(actor))
        self.assertEqual(movement_danger(fight, actor, indices), [dict(cell=0, cost=3)])
        self.assertEqual((vars(fight), vars(actor)), before)


if __name__ == "__main__":
    unittest.main()
