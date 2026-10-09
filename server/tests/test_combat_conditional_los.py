import unittest
from types import SimpleNamespace

from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_native_spell_casting import definition
from wakfu_server.combat_casting_eligibility import (
    NativeCastingFlags,
    native_casting_eligibility,
)


class NativeConditionalLosTests(unittest.TestCase):
    def context(self, state_present, state_level, passive):
        return ConditionContext(
            {
                "caster": ConditionActor(
                    actor_id=7,
                    is_player=True,
                    is_native_fighter=True,
                    deck_spell_ids=frozenset({6949} if passive else ()),
                    excluded_deck_spell_ids=frozenset(),
                    state_ids=frozenset({7792, 7757} if state_present else {7792}),
                    state_levels=((7792, state_level),)
                    + (((7757, 1),) if state_present else ()),
                )
            }
        )

    def test_installed_complete_tables_preserve_state_threshold_and_passive_range(self):
        # Installed content.3.4813 and state namespace content.8.7757/7792.
        # This is a regression case for generic complete-fyP table selection.
        for level in (1, 20, 200):
            for present in (False, True):
                for precision in (-1, 0, 29, 30, 31, 100):
                    for passive in (False, True):
                        with self.subTest(
                            level=level,
                            present=present,
                            precision=precision,
                            passive=passive,
                        ):
                            rule = definition(
                                4813,
                                level,
                                self.context(present, precision, passive),
                                {},
                            )
                            self.assertEqual(
                                rule["line_of_sight"], not (present and precision >= 30)
                            )
                            self.assertEqual(
                                (rule["minimum"], rule["maximum"]),
                                (6, 11) if passive else (4, 9),
                            )

    def test_selected_los_false_does_not_query_ray_but_retains_native_surface_gate(
        self,
    ):
        for required in (False, True):
            calls = []
            values = dict(
                container_present=True,
                current_turn_matches=True,
                effective_range=(1, 4),
                cell_and_qi_present=True,
                resolve_target_fighter=None,
                range_distance=2,
                qi_in_bounds=True,
                qi_r=True,
                qi_j=True,
                native_los=False,
                criterion_present=False,
                criterion_objects=[],
                roots=[],
                target_fighter_present=False,
            )

            def callback(name, value):
                def query(*args):
                    calls.append(name)
                    return value

                return query

            hooks = SimpleNamespace(
                **{name: callback(name, value) for name, value in values.items()}
            )
            result = native_casting_eligibility(
                hooks, NativeCastingFlags(line_of_sight=required)
            )
            self.assertEqual(result, "twG" if required else "twD")
            self.assertEqual("native_los" in calls, required)
            self.assertEqual("qi_j" in calls, not required)

    def test_state_removal_and_threshold_loss_reselect_table_on_next_cast(self):
        for before, after in (
            (self.context(True, 30, False), self.context(False, 30, False)),
            (self.context(True, 30, True), self.context(True, 29, True)),
        ):
            self.assertFalse(definition(4813, 1, before, {})["line_of_sight"])
            self.assertTrue(definition(4813, 1, after, {})["line_of_sight"])
