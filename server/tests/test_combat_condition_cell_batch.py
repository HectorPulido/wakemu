"""Owned bulk inputs preserve G7 cell decisions, errors, RNG and lifetime."""
from dataclasses import replace
from random import Random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_condition_cell_batch as batch_module
from wakfu_server.combat_condition_cell_batch import (
    NativeConditionContextSource,
    native_cell_batch_factory,
    pure_cell_criteria,
)
from wakfu_server.combat_cell_group import select_cell_group
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_conditions import evaluate_condition
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server import combat_qi_fight


class CellBatchSyntaxTests(unittest.TestCase):
    def test_closed_static_calls_without_evaluator_or_catalog_access(self):
        allowed = (
            'GetEnnemyCountInRange(0,2,"target")==0 and not IsOnBorderCell("target")',
            'IsTargetCellFree(True) and HasLineOfSight() and GetAlliesCountInRange(3,"target")<1',
            'GetSpecificEffectAreaCountInRange("target",2114,-1,-1)<6',
        )
        with patch(
            "wakfu_server.combat_conditions.evaluate_condition",
            side_effect=AssertionError("No synthetic evaluator"),
        ):
            for criterion in allowed:
                self.assertTrue(pure_cell_criteria(criterion))
            for criterion in (
                "",
                "False",
                "GetRandomNumber(2)>0",
                "IsTargetCellFree() or Unknown()",
                "bad @ syntax",
            ):
                self.assertFalse(pure_cell_criteria(criterion))
            # Signature errors still belong to the original evaluator.
            self.assertTrue(pure_cell_criteria("HasLineOfSight(123)"))


class CellBatchOwnedTests(unittest.TestCase):
    def setUp(self):
        from test_combat_range_selection_projection import RangeSelectionProjectionTests

        fixture = RangeSelectionProjectionTests()
        fixture.setUp()
        self.fight, self.native = fixture.fight, fixture.native
        terrain = dict(x=0, y=0, width=4, height=4, cell_masks=[256] * 16)
        slots = [None] * 127
        for i, actor in enumerate(self.fight.actors.values()):
            actor.native_obstacle_id = i
            slots[i] = dict(
                identity=["actor", actor.id],
                position=list(actor.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        qi = NativeQIRegistry(terrain, slots)
        qi.capture_fresh_cell_topology(list(range(len(self.fight.actors))))
        self.fight.native_qi_snapshot = terrain
        self.fight.native_qi_slots = qi.serialized_slots()
        self.fight.native_qi_touched_cells = qi.serialized_cells()
        self.fight.native_qi_byte_topology = qi.serialized_byte_topology()
        cast = ordinary_cast_authority(
            actors=self.native,
            timing=SimpleNamespace(state=lambda *a: None),
            rng=Random(7),
            critical=False,
        )
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=self.native, cast=cast
        )
        self.plan = {}
        self.effect = dict(criteria='GetEnnemyCountInRange(0,5,"target")>=0')
        self.effects = {"410765": self.effect}
        self.provider = self.adapter.contexts()
        source = NativeConditionContextSource(
            self.provider.condition, self.fight, self.plan, self.effects
        )
        self.dispatcher = EffectDispatcher(
            self.effects,
            {},
            resolve=lambda *a: (),
            condition_context=source,
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: (),
            actor_position=lambda i: self.fight.actors[i].position,
            group_random=lambda: 0.25,
        )
        self.factory = native_cell_batch_factory(
            self.provider, self.fight, self.plan, self.dispatcher
        )
        self.assertIsNotNone(self.factory)
        self.original = EffectInvocation(
            410765, 1, 7, None, (2, 2, 0), native_target_cell_argument=True
        )

    def frame(self):
        reasons = []
        with patch.object(batch_module, "batch_admission", side_effect=reasons.append):
            frame = self.factory(self.effect, self.original, activation=None)
        self.assertIsNotNone(frame, reasons)
        return frame

    def test_matched_original_decisions_rng_and_one_registry_for_whole_filter(self):
        cells = [(0, 0, 0), (2, 2, 0), (3, 3, 0), (1, 2, 0)]
        results, counts, draws, evaluations = [], [], [], []
        for bulk in (False, True):
            frame = self.frame() if bulk else None
            seen, random_draws = [], []

            def condition(cell):
                invocation = replace(self.original, cell=cell)
                context = (
                    frame.condition(invocation)
                    if frame
                    else self.dispatcher.condition_context(invocation)
                )
                seen.append(
                    (cell, evaluate_condition(self.effect["criteria"], context))
                )
                return seen[-1][1]

            def rng():
                if frame:
                    self.assertFalse(frame.active)
                    self.assertIsNone(frame.registry)
                random_draws.append(0.25)
                return 0.25

            with patch.object(
                combat_qi_fight,
                "current_registry",
                wraps=combat_qi_fight.current_registry,
            ) as reads:
                result = select_cell_group(
                    dict(parameters=[2, 0, 1, 0, 0, 0, 1]),
                    cells,
                    caster_position=(0, 0, 0),
                    condition=condition,
                    rng=rng,
                    reuse_condition_actors=True,
                    condition_batch=frame,
                )
                counts.append(reads.call_count)
            results.append(result)
            draws.append(random_draws)
            evaluations.append(seen)
        self.assertEqual(results[0], results[1])
        self.assertEqual(draws[0], draws[1])
        self.assertEqual(evaluations[0], evaluations[1])
        self.assertEqual(counts, [8, 1])
        self.assertNotIn("condition_cell_batch", vars(self.fight))
        self.assertNotIn("condition_cell_batch", vars(self.original))

    def test_metadata_entry_lazy_query_error_order_and_exception_close(self):
        frame = self.frame()
        with patch.object(
            combat_qi_fight, "current_registry", wraps=combat_qi_fight.current_registry
        ) as reads:
            with self.assertRaisesRegex(ValueError, "original retained prefix"):
                with frame:
                    self.assertEqual(reads.call_count, 0)
                    with patch(
                        "wakfu_server.combat_retained_runtime.native_retained_condition_reader",
                        side_effect=ValueError("original retained prefix"),
                    ):
                        frame.condition(self.original)
            self.assertEqual(reads.call_count, 0)
        self.assertFalse(frame.active)
        self.assertIsNone(frame.registry)
        self.fight.native_qi_byte_topology = None
        frame = self.frame()
        with self.assertRaises(ValueError), frame:
            frame.condition(self.original)
        self.assertFalse(frame.active)
        self.assertIsNone(frame.registry)

    def test_empty_no_filter_or_no_criterion_never_enter_batch(self):
        for cells, filtering, criterion in (
            ([], True, True),
            ([(2, 2, 0)], False, True),
            ([(2, 2, 0)], True, False),
        ):
            frame = self.frame()
            with patch.object(
                type(frame), "__enter__", side_effect=AssertionError("must not enter")
            ):
                with patch.object(
                    combat_qi_fight,
                    "current_registry",
                    side_effect=AssertionError("must not read QI"),
                ):
                    select_cell_group(
                        dict(parameters=[1, 0, int(filtering), 0, 0, 0, 0]),
                        cells,
                        caster_position=(0, 0, 0),
                        condition=lambda c: self.fail("No filter"),
                        rng=lambda: self.fail("No RNG"),
                        criterion_present=criterion,
                        reuse_condition_actors=True,
                        condition_batch=frame,
                    )
            self.assertFalse(frame.active)

    def test_unknown_callbacks_capture_and_activation_decline(self):
        self.assertIsNone(
            self.factory(self.effect, self.original, activation=("native clone",))
        )
        self.effect["criteria"] = "Unknown() or IsTargetCellFree()"
        self.assertIsNone(self.factory(self.effect, self.original, activation=None))
        self.effect["criteria"] = "IsTargetCellFree()"
        from wakfu_server.combat_input_observation import _active, _replaying

        for variable in (_active, _replaying):
            token = variable.set(object())
            try:
                self.assertIsNone(
                    self.factory(self.effect, self.original, activation=None)
                )
            finally:
                variable.reset(token)
        source = self.dispatcher.condition_context
        source.callback = lambda *a, **k: self.fail(
            "Untrusted callback not invoked by admission"
        )
        self.assertIsNone(self.factory(self.effect, self.original, activation=None))

    def test_nested_deck_area_stats_and_qi_callbacks_decline_without_invocation(self):
        invoked = []

        class EvilIterable:
            def __iter__(self):
                invoked.append("iterated")
                return iter([6266])

        class EvilDict(dict):
            def get(self, *a):
                invoked.append("get")
                return super().get(*a)

        from wakfu_server.combat_characteristic_link import (
            ObservableCharacteristicStats,
        )

        ordinary = self.native.ordinary
        for kind in ("deck", "area", "maxima", "stats_method", "qi"):
            with self.subTest(kind=kind):
                self.setUp()
                ordinary = self.native.ordinary
                if kind == "deck":
                    ordinary.decks[7] = EvilIterable()
                elif kind == "area":
                    self.fight.native_effect_areas[900] = EvilDict(uid=900)
                elif kind == "maxima":
                    self.fight.actors[7].effect_maxima = EvilDict(
                        self.fight.actors[7].effect_maxima
                    )
                elif kind == "qi":
                    self.fight.native_qi_snapshot = EvilDict(
                        self.fight.native_qi_snapshot
                    )
                else:
                    actor = self.fight.actors[7]
                    actor.effect_stats = ObservableCharacteristicStats(
                        actor.effect_stats, self.fight, actor.id
                    )
                    actor.effect_stats.items = lambda: invoked.append("stats") or iter(
                        ()
                    )
                self.assertIsNone(
                    self.factory(self.effect, self.original, activation=None)
                )
        self.assertEqual(invoked, [])

    def test_custom_callable_and_invocation_metadata_are_not_read_by_admission(self):
        observed = []

        class CustomCondition:
            def __getattr__(self, name):
                observed.append(name)
                raise AttributeError(name)

            def __call__(self, *args, **kwargs):
                observed.append("called")

        provider = replace(self.provider, condition=CustomCondition())
        self.assertIsNone(
            native_cell_batch_factory(provider, self.fight, self.plan, self.dispatcher)
        )

        class CustomInvocation(EffectInvocation):
            def __getattribute__(self, name):
                if name in ("reference", "cell"):
                    observed.append(name)
                return super().__getattribute__(name)

        invocation = CustomInvocation(410765, 1, 7, None, (2, 2, 0))
        self.assertIsNone(self.factory(self.effect, invocation, activation=None))
        frame = self.frame()
        with frame:
            self.assertIsNone(frame.read(invocation))
            self.assertIsNone(
                batch_module.read_condition_cell_batch(
                    self.adapter, self.fight, self.plan, self.effect, invocation, frame
                )
            )
        self.assertEqual(observed, [])
