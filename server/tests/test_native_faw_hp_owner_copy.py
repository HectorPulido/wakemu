"""Native combined PA constructor and typed FFE regressions; no mocked catalog."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from wakfu_server.combat_fake_fighter import fake_fighter_constructor
from wakfu_server.combat_fake_fighter_resources import (
    install_fake_fighter_hp,
    fake_fighter_characteristics,
    update_fake_fighter_hp,
)
from wakfu_server.combat_fake_fighter_owner_copy import install as install_damage_only
from wakfu_server.combat_area_property import (
    area_properties,
    area_fight_properties,
    add_kill_suppression_property,
)


class NativeCombinedFakeFighterTests(unittest.TestCase):
    def setUp(self):
        self.definition = json.loads(
            (
                Path(__file__).parent / "fixtures/native_faw_hp_owner_copy1284.json"
            ).read_text()
        )

    def row(self, definition=None):
        definition = self.definition if definition is None else definition
        return dict(
            uid=901,
            level=1,
            native_area_contract="faW",
            native_faw_constructor=fake_fighter_constructor(
                definition, 1, allow_hp=True
            ),
        )

    def test_combined_hp_owner_snapshot_roundtrip_and_independent_setters(self):
        owner = {21: 321}
        row = self.row()
        install_fake_fighter_hp(row, self.definition, owner_stats=owner)
        owner[21] = 9999
        restored = json.loads(json.dumps(row))
        values = fake_fighter_characteristics(restored, self.definition)
        self.assertEqual((values[1]["current"], values[20]["current"]), (1, 321))
        update_fake_fighter_hp(restored, self.definition, 0)
        self.assertEqual(
            (
                fake_fighter_characteristics(restored, self.definition)[1]["current"],
                fake_fighter_characteristics(restored, self.definition)[20]["current"],
            ),
            (0, 321),
        )
        restored["native_faw_hp_owner_copy_constructor"]["owner_stats"]["21"] = 12
        with self.assertRaises(ValueError):
            fake_fighter_characteristics(restored, self.definition)

    def test_existing_constructor_branches_and_missing_owner_keep_their_guards(self):
        for selector, expected in [(-1, {1}), (0, {1, 20})]:
            definition = deepcopy(self.definition)
            definition["raw_bdh"][9] = selector
            row = self.row(definition)
            install_fake_fighter_hp(row, definition)
            self.assertEqual(
                set(fake_fighter_characteristics(row, definition)), expected
            )
        definition = deepcopy(self.definition)
        definition["raw_bdh"][1] = -1
        row = self.row(definition)
        install_damage_only(row, definition, {21: 321})
        self.assertEqual(set(fake_fighter_characteristics(row, definition)), {20})
        row = self.row()
        before = deepcopy(row)
        with self.assertRaises(ValueError):
            install_fake_fighter_hp(row, self.definition)
        self.assertEqual(row, before)

    def test_ffe_suppression_is_idempotent_and_does_not_become_fbo(self):
        row = self.row()
        initial = area_properties(row, self.definition)
        self.assertFalse(area_fight_properties(row, self.definition))
        add_kill_suppression_property(row, self.definition)
        add_kill_suppression_property(row, self.definition)
        self.assertEqual(area_fight_properties(row, self.definition), {65})
        self.assertEqual(area_properties(row, self.definition), initial)
        for changes in [
            dict(native_current_fight_properties=[65, "65"]),
            dict(native_current_fight_properties=[64]),
            dict(native_fight_property_source="unknown"),
        ]:
            changed = dict(row, **changes)
            with self.assertRaises(ValueError):
                area_fight_properties(changed, self.definition)
