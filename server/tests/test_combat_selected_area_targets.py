"""Selected Qq projections retain complete validation and live geometry guards."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_effect_area_targets as targets
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_area,
    unregister_global_area,
)


class SelectedAreaTargetTests(unittest.TestCase):
    def fixture(self, count=3):
        definition = dict(type="GLYPH", raw_bcR=False)
        actor = SimpleNamespace(id=7, team=0, position=(0, 0, 0), direction=0)
        fight = SimpleNamespace(
            actors={7: actor}, native_effect_areas={}, native_retired_area_managers={}
        )
        initialize_global_pv_collections(fight, (7,))
        for index in range(count):
            identity = 901 + index
            fight.native_effect_areas[identity] = dict(
                uid=identity,
                reference=314,
                level=1,
                cell=(index, 0, 0),
                owner_id=7,
                direction=0,
                native_hour_contract=True,
                native_area_contract="faY",
                native_qq_bhi=False,
                native_qq_guard_source="Qq.constructor",
            )
            register_global_area(fight, identity)
        return fight, {"314": definition}

    def assert_differential(self, fight):
        baseline = targets.area_targets(fight)
        for target in baseline:
            self.assertEqual(targets.area_target(fight, target.id), target)
        for cell in {target.position for target in baseline} | {(999, 999, 0), None}:
            self.assertEqual(
                targets.area_targets_at_cell(fight, cell),
                tuple(target for target in baseline if target.position == cell),
            )
        self.assertIsNone(targets.area_target(fight, 123456789))

    def test_219_rows_project_only_selected_uid_or_cell_in_native_order(self):
        fight, definitions = self.fixture(219)
        fight.native_effect_areas[901]["cell"] = (-1, 0, 0)
        fight.native_effect_areas[902]["cell"] = (-1, 0, 0)
        target_type = targets.NativeAreaTarget
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            with patch.object(
                targets, "NativeAreaTarget", wraps=target_type
            ) as project:
                baseline = targets.area_targets(fight)
                self.assertEqual(project.call_count, 219)
                project.reset_mock()
                with patch.object(targets, "_rows", wraps=targets._rows) as validate:
                    selected = targets.area_target(fight, 901)
                    self.assertEqual(validate.call_count, 1)
                self.assertEqual(project.call_count, 1)
                self.assertEqual(
                    selected, next(target for target in baseline if target.id == 901)
                )
                project.reset_mock()
                selected_cell = targets.area_targets_at_cell(fight, (-1, 0, 0))
                self.assertEqual(project.call_count, 2)
                self.assertEqual(
                    selected_cell,
                    tuple(
                        target for target in baseline if target.position == (-1, 0, 0)
                    ),
                )

    def test_live_aura_anchor_callback_and_checkpoint_container_roundtrip(self):
        fight, definitions = self.fixture()
        definitions["315"] = dict(
            type="AURA",
            raw_bcR=True,
            native_shape_class="anD",
            native_shape_description="point",
            shape_parameters=[],
        )
        aura = fight.native_effect_areas[902]
        aura.update(
            reference=315,
            native_area_contract="faN",
            native_anchor_id=7,
            native_anchor_source="faN.bgZ",
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            self.assert_differential(fight)
            fight.actors[7].position = (
                14,
                5,
                2,
            )  # A completed actual-owner movement callback.
            self.assertEqual(
                tuple(
                    target.id
                    for target in targets.area_targets_at_cell(fight, (14, 5, 2))
                ),
                (902,),
            )
            self.assertFalse(targets.area_targets_at_cell(fight, (1, 0, 0)))
            from wakfu_server.fight_checkpoint_store import _plain

            # Use the production checkpoint value codec; no projection survives it.
            encoded = json.loads(json.dumps(_plain(fight.native_effect_areas)))
            fight.native_effect_areas = {int(uid): row for uid, row in encoded.items()}
            self.assert_differential(fight)
            fight.actors[7].position = (-2, 6, 9)
            self.assertEqual(targets.area_target(fight, 902).position, (-2, 6, 9))
            self.assert_differential(fight)

    def test_removal_and_new_uid_are_observed_without_retaining_query_results(self):
        fight, definitions = self.fixture()
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            before = targets.area_target(fight, 901)
            row = fight.native_effect_areas.pop(901)
            unregister_global_area(fight, 901)
            self.assertIsNone(targets.area_target(fight, 901))
            row = deepcopy(row)
            row.update(uid=999, cell=(5, 5, 5))
            fight.native_effect_areas[999] = row
            register_global_area(fight, 999)
            self.assertEqual(targets.area_target(fight, 999).position, (5, 5, 5))
            self.assertEqual(before.position, (0, 0, 0))
            self.assert_differential(fight)

    def test_faw_wall_and_simple_keep_native_constructor_and_blocking_facts(self):
        from wakfu_server.combat_fake_fighter import fake_fighter_constructor
        from wakfu_server.combat_wall_area import wall_constructor
        from wakfu_server.combat_simple_area import simple_area_constructor

        fight, definitions = self.fixture()
        faw = dict(
            type="FAKE_FIGHTER",
            native_class="bcQ",
            native_type_id=15,
            raw_bdh=[-1, -1, 0, 1, 1, 1, 0, 0, 0, -1],
            raw_bcR=True,
        )
        wall = dict(
            type="WALL",
            native_class="bcZ",
            native_type_id=7,
            native_container_type=3,
            raw_bdh=[10, 0, 1, 0],
            raw_bcR=False,
        )
        simple = dict(
            type="SIMPLE",
            native_class="bcW",
            native_type_id=6,
            native_container_type=3,
            raw_bcR=True,
            raw_bde=2,
            native_area_properties=[],
            native_fight_properties=[],
            properties=[],
            entry_masks=[],
            exit_masks=[],
            native_shape_class="anD",
            native_shape_description="point",
            native_hour_contract=False,
        )
        definitions.update({"316": faw, "317": wall, "318": simple})
        fight.native_effect_areas[901].update(
            reference=316,
            native_area_contract="faW",
            native_faw_constructor=fake_fighter_constructor(faw),
            native_obstacle_id=1,
            native_obstacle_source="QI.f(QK)",
        )
        constructor = wall_constructor(wall, 1)
        fight.native_effect_areas[902].update(
            reference=317,
            native_area_contract="fbd",
            native_type_id=7,
            native_running_effect_manager=True,
            native_wall_constructor=constructor,
            native_wall_hp_current=constructor["hp_initial"],
            native_wall_hp_source="fbd.PA.sgC.aYS",
            native_obstacle_id=2,
            native_obstacle_source="QI.f(QK)",
        )
        fight.native_effect_areas[903].update(
            reference=318,
            native_area_contract="fbb",
            native_type_id=6,
            native_simple_constructor=simple_area_constructor(simple),
            native_running_effect_manager=False,
            native_obstacle_id=-1,
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            self.assert_differential(fight)
            self.assertTrue(targets.area_target(fight, 901).native_movement_blocking)
            self.assertTrue(targets.area_target(fight, 902).native_movement_blocking)
            fight.native_effect_areas[901]["native_faw_constructor"]["height"] = 99
            # Even a query selecting a different UID still retains _rows' full guard.
            with self.assertRaisesRegex(ValueError, "faW constructor"):
                targets.area_target(fight, 903)

    def test_selected_lifecycle_owner_and_bcR_malformation_still_reject(self):
        fight, definitions = self.fixture()
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            row = fight.native_effect_areas[901]
            for field, value, message in (
                ("owner_id", 999, "owner"),
                ("native_qq_bhi", None, "guard"),
            ):
                old = row[field]
                row[field] = value
                with self.assertRaisesRegex(ValueError, message):
                    targets.area_target(fight, 901)
                row[field] = old
            definitions["314"]["raw_bcR"] = 1
            with self.assertRaisesRegex(ValueError, "bcR"):
                targets.area_targets_at_cell(fight, (0, 0, 0))

    def test_null_owner_border_and_declared_environment_are_preserved(self):
        from test_combat_battleground_border import BattlegroundBorderTests
        from wakfu_server.combat_battleground_border import install_battleground_border
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            SOURCE,
            point_glyph_row,
        )

        fight, arena = BattlegroundBorderTests().fixture()
        install_battleground_border(fight, arena, reference=46, identity=-100)
        source = dict(
            uid=-101,
            reference=1724,
            cell=(1, 0, 3),
            level=0,
            source=SOURCE,
            policy="wakemu.test.declared-point",
            authority="explicit-test-scene",
            source_url="https://example.invalid/source",
        )
        fight.native_environment_glyph_constructors = [source]
        fight.native_effect_areas[-101] = point_glyph_row(
            source, native_effect_areas()["1724"]
        )
        register_global_area(fight, -101)
        self.assert_differential(fight)
        self.assertEqual(targets.area_target(fight, -100).team, -1)
        self.assertEqual(targets.area_target(fight, -101).team, -1)
