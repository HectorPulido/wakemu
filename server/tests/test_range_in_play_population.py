"""Native range selection excludes OUT before expensive actor projection."""
from contextlib import nullcontext
import sys
import unittest
from unittest.mock import patch

from test_combat_range_selection_projection import RangeSelectionProjectionTests
from test_combat_range_population_input import RangePopulationInputTests
from wakfu_server import combat_range_native_population as population
from wakfu_server import combat_range_conditions as ranges
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority


class NativeRangePopulationTests(unittest.TestCase):
    def test_public_ranges_preserve_false_areas_custom_and_shared_population(self):
        fixture = RangeSelectionProjectionTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, 8, "OFF_PLAY")
        set_global_fighter_status(fight, -7, "OUT_OF_PLAY")
        # Native membership is independent of current HP (dead vs retired).
        fight.actors[8].hp = 0
        fight.actors[8].effect_stats[1] = 0

        def run(enabled):
            calls = []
            code = OrdinaryActorAuthority.__call__.__code__

            def observe(frame, event, arg):
                if event == "call" and frame.f_code is code:
                    calls.append(frame.f_locals["actor"].id)

            with (
                nullcontext()
                if enabled
                else patch.object(
                    population, "native_range_population", return_value=None
                )
            ):
                ctx = fixture.context()
                sys.setprofile(observe)
                try:
                    values = [
                        ctx.enemy_range_query(0, 99, "caster", False, False),
                        ctx.allies_range_query(0, 99, "caster", False, False, True),
                    ]
                finally:
                    sys.setprofile(None)
                values.append(
                    ctx.allies_range_query(0, 99, "caster", False, False, False)
                )
                values.append(
                    ctx.human_enemies_range_query(0, 99, "caster", False, False)
                )
                # Isolate the public adapter population from carrier decoding:
                # the Qq population must contribute regardless of fighter flag.
                with patch(
                    "wakfu_server.combat_retained_runtime.native_retained_condition_reader",
                    return_value=lambda _: (),
                ), patch.object(
                    ranges, "registered_state_carriers", return_value=((3442, 1, 7),)
                ), patch.object(
                    ranges,
                    "attest_state_area_population",
                    return_value=(((0, 0, 0), ((3442, 1, 7),)),),
                ):
                    values.extend(
                        ctx.state_range_query(99, "caster", 3442, -1, flag, "")
                        for flag in (True, False)
                    )
            return values, calls

        baseline, original_calls = run(False)
        actual, calls = run(True)
        self.assertEqual(actual, baseline)
        self.assertEqual(actual, [0, 1, 2, 0, 2, 4])
        self.assertIn(-7, original_calls)
        self.assertNotIn(-7, calls)
        self.assertNotIn(8, calls)
        self.assertLess(len(calls), len(original_calls))
        # Custom callbacks and participation hooks keep their legacy path.
        with patch.object(
            fixture.native, "properties", wraps=fixture.native.properties
        ):
            self.assertIsNone(population.native_range_population(fight, fixture.native))
        with patch.object(fight, "_in_play", return_value=True):
            self.assertIsNone(population.native_range_population(fight, fixture.native))
        custom_books = []
        original_book = fixture.ordinary.npc_spellbook
        fixture.ordinary.npc_spellbook = lambda *args: custom_books.append(args)
        try:
            self.assertIsNone(population.native_range_population(fight, fixture.native))
            self.assertEqual(custom_books, [])
        finally:
            fixture.ordinary.npc_spellbook = original_book
        actors = fight.actors

        class CustomActors(dict):
            def values(self):
                raise AssertionError("opaque population must not be materialized")

        try:
            fight.actors = CustomActors(actors)
            self.assertIsNone(population.native_range_population(fight, fixture.native))
        finally:
            fight.actors = actors
        with patch.object(
            actors, "values", side_effect=AssertionError("opaque getter")
        ):
            self.assertIsNone(population.native_range_population(fight, fixture.native))
        set_global_fighter_status(fight, -7, "IN_PLAY")
        self.assertEqual(
            fixture.context().enemy_range_query(0, 99, "caster", False, False), 1
        )
        # Existing relation-neutral cell input must keep all actors even when
        # an enemy query is followed by ally(False) in the same batch.
        bulk = RangePopulationInputTests()
        # The existing cell batch intentionally accepts only plain area maps.
        # Its legacy empty-area fixture predates Fight's native OwnedMap birth.
        # Use that supported empty representation before constructing the frame;
        # do not widen production admission merely to exercise shared input.
        from test_combat_condition_cell_batch import CellBatchOwnedTests

        bulk.fixture = CellBatchOwnedTests()
        bulk.fixture.setUp()
        bulk.fight = bulk.fixture.fight
        bulk.fight.native_effect_areas = {}
        bulk.frame = bulk.fixture.frame()
        initialize_global_pv_collections(bulk.fight, tuple(bulk.fight.actors))
        set_global_fighter_status(bulk.fight, 8, "OFF_PLAY")
        from wakfu_server.combat_condition_selection_scope import (
            condition_actor_selection_scope,
        )

        with bulk.frame, condition_actor_selection_scope():
            ctx = bulk.context()
            ctx.enemy_range_query(0, 99, "caster", False, False)
            self.assertEqual(len(bulk.frame.range_population), len(bulk.fight.actors))
            self.assertEqual(
                ctx.allies_range_query(0, 99, "caster", False, False, False), 2
            )
