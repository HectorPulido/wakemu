"""Complete operation inputs retain original native range checks and filters."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_combat_condition_cell_batch as batch_fixture
from wakfu_server.combat_condition_selection_scope import (
    condition_actor_selection_scope,
)
from wakfu_server.combat_conditions import evaluate_condition
from wakfu_server import combat_range_conditions as ranges
from wakfu_server.combat_cell_group import select_cell_group


class RangePopulationInputTests(unittest.TestCase):
    def setUp(self):
        self.fixture = batch_fixture.CellBatchOwnedTests()
        self.fixture.setUp()
        self.frame = self.fixture.frame()
        self.fight = self.fixture.fight

    def context(self, cell=(2, 2, 0), caster=7, bulk=True):
        invocation = replace(self.fixture.original, cell=cell, caster_id=caster)
        return (
            self.frame.condition(invocation)
            if bulk
            else self.fixture.dispatcher.condition_context(invocation)
        )

    def test_original_and_working_input_match_every_enemy_ally_query(self):
        results, populations, construction_counts = [], [], []
        original_init = ranges.RangeFighter.__init__
        for bulk in (False, True):
            values, inputs = [], []
            with self.frame, condition_actor_selection_scope(), patch.object(
                ranges.RangeFighter,
                "__init__",
                autospec=True,
                side_effect=original_init,
            ) as constructors, patch.object(
                ranges, "range_count", wraps=ranges.range_count
            ) as count:
                for cell in ((2, 2, 0), (0, 0, 0), (3, 3, 0)):
                    context = self.context(cell, bulk=bulk)
                    for relation in ("enemy_range_query", "allies_range_query"):
                        for minimum, maximum in ((0, 2), (1, 5), (-1, -1)):
                            values.append(
                                getattr(context, relation)(
                                    minimum, maximum, "target", False, False
                                )
                            )
                inputs = [call.args[0] for call in count.call_args_list]
                construction_counts.append(constructors.call_count)
                if bulk:
                    self.assertTrue(
                        all(rows is self.frame.range_population for rows in inputs)
                    )
                    self.assertEqual(len(inputs[0]), len(self.fight.actors))
                    self.assertIsNot(
                        count.call_args_list[0].kwargs["visible"],
                        count.call_args_list[-1].kwargs["visible"],
                    )
            results.append(values)
            populations.append(inputs)
        self.assertEqual(results[0], results[1])
        self.assertEqual(populations[0], populations[1])
        self.assertEqual(construction_counts, [54, 3])
        self.assertIsNone(self.frame.range_population)

    def test_first_reached_operand_builds_complete_rows_even_missing_center(self):
        with self.frame, condition_actor_selection_scope():
            context = self.context()
            self.assertIsNone(self.frame.range_population)
            self.assertFalse(
                evaluate_condition(
                    'False and GetEnnemyCountInRange(0,5,"target")>0', context
                )
            )
            self.assertIsNone(self.frame.range_population)
            saved = self.fight.actors[-7].effect_maxima
            self.fight.actors[-7].effect_maxima = {}
            with self.assertRaisesRegex(ValueError, "virtual HP maximum"):
                context.enemy_range_query(
                    "bad bounds", 5, "unknown selector", False, False
                )
            self.assertIsNone(self.frame.range_population)
            self.fight.actors[-7].effect_maxima = saved
            # Original range_count checks absent center before bad bounds,
            # but the adapter must still prepare ALL actor rows first.
            self.assertEqual(
                context.enemy_range_query(
                    "bad bounds", 5, "unknown selector", False, False
                ),
                0,
            )
            self.assertEqual(len(self.frame.range_population), 3)
            with self.assertRaisesRegex(ValueError, "range parameters"):
                context.enemy_range_query("bad bounds", 5, "target", False, False)

    def test_unfiltered_rows_preserve_radius_flags_affiliation_and_carry_filters(self):
        # These explicit native range facts isolate the consumer semantics;
        # they do not claim to produce carrying/death mechanics in a fight.
        rows = (
            ranges.RangeFighter((0, 0, 0), 0, 10, True, False, False),
            ranges.RangeFighter((3, 3, 0), 1, 20, True, False, False),  # 3x3 footprint.
            ranges.RangeFighter((1, 0, 0), 0, 20, True, True, False),  # property42.
            ranges.RangeFighter((1, 0, 0), 0, 10, True, False, False, True),  # 114.
            ranges.RangeFighter((1, 0, 0), 0, 20, True, False, True, breed_id=3794),
            ranges.RangeFighter((1, 0, 0), 0, 20, False, False, False),
        )
        self.assertEqual(
            ranges.range_count(
                rows, affiliation=10, center=(0, 0, 99), minimum=4, maximum=4
            ),
            1,
        )
        self.assertEqual(
            ranges.range_count(
                rows, affiliation=10, center=(0, 0, 0), minimum=0, maximum=99
            ),
            1,
        )
        self.assertEqual(
            ranges.range_count(
                rows,
                affiliation=10,
                center=(0, 0, 0),
                minimum=0,
                maximum=99,
                relation="ally",
            ),
            1,
        )
        self.assertEqual(len(rows), 6)

    def test_first_operand_reads_radius_withdrawal_and_native_affiliation(self):
        with self.frame, condition_actor_selection_scope():
            context = self.context()
            # The first actual range operand, not context creation, owns these
            # input facts. This isolates query behavior, not a QI resize or
            # withdrawal producer; no registry query follows these test edits.
            self.fight.actors[8].pve_withdrawn = True
            self.fight.actors[-7].physical_radius = 1
            self.fight.actors[-7].native_fight_affiliation = 0
            self.assertEqual(
                context.enemy_range_query(0, 99, "caster", False, False), 0
            )
            self.assertEqual(
                context.allies_range_query(0, 99, "caster", False, False), 2
            )
            rows = self.frame.range_population
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1].physical_radius, 1)
            self.assertEqual(rows[-1].affiliation, 0)
            self.assertNotEqual(rows[-1].affiliation, self.fight.actors[-7].team)

    def test_centers_casters_map_closures_and_validation_remain_query_local(self):
        with self.frame, condition_actor_selection_scope(), patch.object(
            ranges, "range_count", wraps=ranges.range_count
        ) as count:
            self.context((2, 2, 0), caster=7).enemy_range_query(
                0, 2, "target", False, False
            )
            self.context((1, 2, 0), caster=-7).allies_range_query(
                1, 5, "caster", True, False
            )
            one, two = count.call_args_list
            self.assertIs(one.args[0], two.args[0])
            self.assertEqual(one.kwargs["center"], (2, 2, 0))
            self.assertEqual(two.kwargs["center"], self.fight.actors[-7].position)
            self.assertEqual(one.kwargs["affiliation"], self.fight.actors[7].team)
            self.assertEqual(two.kwargs["affiliation"], self.fight.actors[-7].team)
            self.assertNotEqual(one.kwargs["relation"], two.kwargs["relation"])
            self.assertIsNot(one.kwargs["visible"], two.kwargs["visible"])
            self.assertEqual(
                (two.kwargs["minimum"], two.kwargs["maximum"], two.kwargs["aligned"]),
                (1, 5, True),
            )

    def test_unsupported_modes_and_closed_context_keep_fresh_rows(self):
        original_init = ranges.RangeFighter.__init__
        with self.frame, condition_actor_selection_scope():
            context = self.context()
            context.enemy_range_query(0, 5, "target", False, False)
            rows = self.frame.range_population
            with patch.object(
                ranges.RangeFighter,
                "__init__",
                autospec=True,
                side_effect=original_init,
            ) as constructors:
                context.fighters_breed_range_query(5, "target", 5525)
                self.assertGreater(constructors.call_count, 0)
            self.assertIs(self.frame.range_population, rows)
        self.assertIsNone(self.frame.range_population)
        with patch.object(
            ranges.RangeFighter, "__init__", autospec=True, side_effect=original_init
        ) as constructors:
            context.enemy_range_query(0, 5, "target", False, False)
            self.assertEqual(constructors.call_count, 3)

    def test_exception_releases_working_input_and_later_operation_refreshes(self):
        with self.assertRaisesRegex(
            RuntimeError, "child pending"
        ), self.frame, condition_actor_selection_scope():
            self.context().enemy_range_query(0, 5, "target", False, False)
            self.assertIsNotNone(self.frame.range_population)
            raise RuntimeError("child pending")
        self.assertFalse(self.frame.active)
        self.assertIsNone(self.frame.range_population)
        self.frame = self.fixture.frame()
        self.fight.actors[-7].native_fight_properties = frozenset({42})
        with self.frame, condition_actor_selection_scope():
            self.assertEqual(
                self.context().enemy_range_query(0, 99, "caster", False, False), 0
            )
            self.assertTrue(self.frame.range_population[-1].excluded_property)

    def test_opt_out_discards_input_during_and_after_callback(self):
        for query_inside in (False, True):
            with self.subTest(query_inside=query_inside):
                self.setUp()
                with self.frame, condition_actor_selection_scope():
                    context = self.context()
                    self.assertEqual(
                        context.enemy_range_query(0, 99, "caster", False, False), 1
                    )
                    old_rows = self.frame.range_population
                    with condition_actor_selection_scope(enabled=False):
                        self.fight.actors[-7].native_fight_properties = frozenset({42})
                        if query_inside:
                            self.assertEqual(
                                context.enemy_range_query(
                                    0, 99, "caster", False, False
                                ),
                                0,
                            )
                            self.assertIsNone(self.frame.range_population)
                    # A new full context can repopulate source metadata in the
                    # SAME memo dict. Its pair identity must invalidate input.
                    fresh = self.context()
                    self.assertEqual(
                        fresh.enemy_range_query(0, 99, "caster", False, False), 0
                    )
                    self.assertIsNot(self.frame.range_population, old_rows)

    def test_population_is_released_before_shuffle_rng(self):
        draws = []

        def condition(cell):
            return (
                self.context(cell).enemy_range_query(0, 99, "target", False, False) >= 0
            )

        def rng():
            self.assertFalse(self.frame.active)
            self.assertIsNone(self.frame.range_population)
            self.assertIsNone(self.frame.range_population_anchor)
            draws.append(0.25)
            return 0.25

        select_cell_group(
            dict(parameters=[2, 0, 1, 0, 0, 0, 1]),
            [(2, 2, 0), (2, 3, 0), (3, 2, 0)],
            caster_position=(0, 0, 0),
            condition=condition,
            rng=rng,
            reuse_condition_actors=True,
            condition_batch=self.frame,
        )
        self.assertEqual(draws, [0.25, 0.25])
