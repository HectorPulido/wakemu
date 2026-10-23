"""Native eWN/eWO/eZI source PVs retain strict target/resource authority."""
from dataclasses import replace
import unittest


class NativeMaximumPvSourceTests(unittest.TestCase):
    def fixture(self, family):
        from test_combat_percentage_hp import PercentageHPTests
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            SOURCE,
            point_glyph_row,
            validate_point_prototype,
        )
        from wakfu_server.combat_maximum_resource import NativeMaximumReductionHandler

        fixture = PercentageHPTests()
        fixture.setUp()
        original = fixture.f
        fight = original.fight
        definition = native_effect_areas()["910"]
        validate_point_prototype(definition, level=0)
        source = dict(
            uid=901,
            reference=910,
            cell=(2, 3, 0),
            level=0,
            policy="wakemu.unit.maximum-source.v1",
            source=SOURCE,
            authority="explicit-unit-constructor",
        )
        fight.walkable.add(source["cell"])
        row = point_glyph_row(source, definition)
        fight.native_effect_areas = {901: row}
        if family == 31:
            # Original Nox402174 fixed+1AP values and native cap-bypass flags.
            handler, parameters = original.handler, [1, 0, 1, 0, 0, 0]
        elif family == 57:
            handler = NativeMaximumReductionHandler(
                fight,
                original.packets,
                action_id=1,
                allocate_uid=original.handler.allocate_uid,
                context=original.handler.context,
            )
            parameters = [1, 0]
        else:
            handler, parameters = fixture.handler, [-30, 0]
        invocation = replace(original.invocation, caster_id=901)
        return (
            original,
            row,
            handler,
            dict(
                effect_class=family,
                parameters=parameters,
                native_effect_flags=[9, 15, 17] if family == 31 else [],
            ),
            invocation,
        )

    def assert_applied(
        self, family, fixture, row, handler, effect, invocation, *, retained=True
    ):
        self.assertTrue(handler(effect, {}, invocation))
        actor = fixture.actor
        expected = {31: (7, 7), 57: (2, 2), 986: (30, 70)}[family]
        actual = {
            31: (actor.ap, actor.max_ap),
            57: (actor.mp, actor.max_mp),
            986: (actor.hp, actor.max_hp),
        }[family]
        self.assertEqual(actual, expected)
        if retained:
            self.assertEqual(fixture.fight.owned_stat_effects[101]["caster_id"], 901)
        else:
            self.assertFalse(fixture.fight.owned_stat_effects)
        self.assertNotIn("state_ledger", row)
        self.assertFalse(row["native_running_effect_manager"])

    def test_neutral_null_qf_sources_apply_real_resource_changes_in_all_three_runners(
        self,
    ):
        for family in (31, 57, 986):
            with self.subTest(family=family):
                fixture, row, handler, effect, invocation = self.fixture(family)
                self.assert_applied(family, fixture, row, handler, effect, invocation)

    def test_retired_actual_selected_source_remains_valid_only_with_its_native_scope(
        self,
    ):
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import (
            registered_source_pv,
            selected_area_pv_scope,
        )

        for family in (31, 57, 986):
            with self.subTest(family=family):
                fixture, row, handler, effect, invocation = self.fixture(family)
                fight = fixture.fight
                context = handler.context
                handler.context = lambda *args: replace(context(*args), retained=False)
                with selected_area_pv_scope(fight, (901,)):
                    remove_owned_hour_area(fight, 901)
                    self.assertNotIn(901, fight.native_effect_areas)
                    self.assertIsNotNone(registered_source_pv(fight, 901))
                    self.assert_applied(
                        family,
                        fixture,
                        row,
                        handler,
                        effect,
                        invocation,
                        retained=False,
                    )
                self.assertIsNone(registered_source_pv(fight, 901))
                before = (
                    fixture.actor.ap,
                    fixture.actor.mp,
                    fixture.actor.hp,
                    len(fixture.packets),
                )
                with self.assertRaises(ValueError):
                    handler(effect, {}, invocation)
                self.assertEqual(
                    (
                        fixture.actor.ap,
                        fixture.actor.mp,
                        fixture.actor.hp,
                        len(fixture.packets),
                    ),
                    before,
                )

    def test_foreign_unknown_and_malformed_sources_cannot_mutate_target_resources(self):
        from wakfu_server.combat_effect_area import remove_owned_hour_area

        for family in (31, 57, 986):
            with self.subTest(family=family):
                fixture, row, handler, effect, invocation = self.fixture(family)
                # Removing the only local source does not admit the same UID
                # merely because a different fixture owns an actual901 PV.
                _foreign = self.fixture(family)
                remove_owned_hour_area(fixture.fight, 901)
                before = (
                    fixture.actor.ap,
                    fixture.actor.mp,
                    fixture.actor.hp,
                    len(fixture.packets),
                )
                for identity in (901, 99999, None, True):
                    with self.subTest(source=identity), self.assertRaises(ValueError):
                        handler(effect, {}, replace(invocation, caster_id=identity))
                self.assertEqual(
                    (
                        fixture.actor.ap,
                        fixture.actor.mp,
                        fixture.actor.hp,
                        len(fixture.packets),
                    ),
                    before,
                )
                # A supplied but invalid Qf checkpoint is rejected, rather
                # than accepted as a generic zero-stat source.
                fixture.fight.native_effect_areas[901] = row
                row["native_running_effect_manager"] = True
                with self.assertRaises(ValueError):
                    handler(effect, {}, invocation)
                self.assertEqual(len(fixture.packets), before[-1])
