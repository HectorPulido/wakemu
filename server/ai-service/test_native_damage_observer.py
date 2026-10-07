from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import random
import unittest
from unittest.mock import patch

from native_context import NativeGraph
from native_damage_observer import capture, current, observe, evidence
from native_facings import measure
from query_search import _diverse_beam
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority


def fixture(direction=1):
    source = SimpleNamespace(
        id=-1, position=(0, 0, 0), direction=1, hp=20, future={"bytes": b"\x00\xff"}
    )
    target = SimpleNamespace(id=7, position=(1, 0, 0), direction=direction, hp=30)
    preview = SimpleNamespace(actors={-1: source, 7: target})
    invocation = EffectInvocation(987654, 1, -1, 7, target.position)
    effect = {"native_localization_enabled": True, "future_native_parameters": [b"all"]}
    rng = random.Random(15)
    authority = ordinary_cast_authority(
        actors=lambda *args: None,
        timing=SimpleNamespace(state=lambda *args: None),
        rng=rng,
        critical=False,
    )
    return preview, invocation, effect, authority.damage, rng


class NativeDamageObserverTests(unittest.TestCase):
    def test_capture_failure_preserves_native_callback_result_and_declares_unknown(
        self,
    ):
        preview, invocation, effect, _, _ = fixture()
        context, calls, samples = object(), [], []

        def callback(*args):
            calls.append(args)
            return context

        with patch(
            "native_damage_observer.encode", side_effect=TypeError("future opaque type")
        ):
            returned = observe(callback, samples)(preview, {}, effect, invocation)
        self.assertIs(returned, context)
        self.assertEqual(len(calls), 1)
        row = evidence(samples)[0]
        self.assertTrue(row["observationUnavailable"])
        self.assertFalse(row["complete"])
        self.assertNotIn("arithmeticLocalization", row)

    def test_snapshot_native_locator_is_explicitly_distinct_from_damage_calculation(
        self,
    ):
        preview, _, _, _, _ = fixture()
        preview.actors[-1].team, preview.actors[7].team = 1, 0
        preview.current = preview.actors[-1]
        self.assertEqual(
            measure(preview), dict(nativeFacingActorId=-1, nativeFacings={"7": "BACK"})
        )
        preview.actors[7].direction = None
        self.assertEqual(measure(preview)["nativeFacings"], {"7": None})
        preview.actors[7].hp = 0
        self.assertEqual(measure(preview)["nativeFacings"], {})

    def test_beam_keeps_back_position_branch_without_awarding_it_utility(self):
        def option(key, score, facing):
            return dict(
                key=key,
                score=score,
                actions=[{}],
                intent="position",
                target=None,
                state=dict(
                    key=key, nativeFacingActorId=-1, nativeFacings={"7": facing}
                ),
            )

        options = [
            option("front-a", 1, "FRONT"),
            option("front-b", 0.9, "FRONT"),
            option("back", 0.8, "BACK"),
        ]
        selected = _diverse_beam(options, 2, -1)
        self.assertEqual([node["key"] for node in selected], ["front-a", "back"])
        self.assertEqual(selected[1]["score"], 0.8)
        self.assertEqual(
            [node["key"] for node in _diverse_beam(options, 2, 99)],
            ["front-a", "front-b"],
        )

    def test_actual_native_callback_records_front_back_and_side_at_calculation_time(
        self,
    ):
        for direction, expected in ((1, "BACK"), (5, "FRONT"), (3, "SIDE")):
            with self.subTest(direction=direction):
                preview, invocation, effect, callback, rng = fixture(direction)
                before = rng.getstate()
                with capture() as samples:
                    context = observe(callback, current())(
                        preview, {"spell_id": 100}, effect, invocation
                    )
                self.assertIsNone(current())
                self.assertEqual(context.localization, expected)
                self.assertEqual(evidence(samples)[0]["observedLocalization"], expected)
                self.assertEqual(
                    evidence(samples)[0]["arithmeticLocalization"], expected
                )
                self.assertEqual(rng.getstate(), before)

    def test_disabled_localization_keeps_observed_back_without_inventing_damage_advantage(
        self,
    ):
        preview, invocation, effect, callback, _ = fixture()
        effect["native_localization_enabled"] = False
        samples = []
        context = observe(callback, samples)(
            preview, {"spell_id": 100}, effect, invocation
        )
        row = evidence(samples)[0]
        self.assertEqual(context.localization, "BACK")
        self.assertEqual(row["observedLocalization"], "BACK")
        self.assertFalse(row["localizationEnabled"])
        self.assertEqual(row["arithmeticLocalization"], "FRONT")

    def test_future_fields_and_intermediate_orientation_are_frozen_before_later_effects(
        self,
    ):
        preview, invocation, effect, callback, _ = fixture()
        samples = []
        observe(callback, samples)(preview, {"spell_id": 100}, effect, invocation)
        preview.actors[7].direction = 5
        preview.actors[-1].future["bytes"] = b"changed"
        effect["future_native_parameters"].append(b"later")
        effect["native_localization_enabled"] = False
        graph = NativeGraph(samples[0])
        source = graph.field(graph.data["root"], "source")
        self.assertEqual(
            graph.plain(graph.field(source, "future")), {"bytes": b"\x00\xff"}
        )
        original_effect = graph.field(graph.data["root"], "effect")
        self.assertEqual(
            graph.plain(graph.field(original_effect, "future_native_parameters")),
            [b"all"],
        )
        self.assertEqual(evidence(samples)[0]["arithmeticLocalization"], "BACK")

    def test_original_callback_runs_once_and_its_context_identity_and_rng_are_preserved(
        self,
    ):
        preview, invocation, effect, callback, rng = fixture()
        calls, contexts, samples = [], [], []

        def native(*args):
            calls.append(rng.randrange(1000))
            context = callback(*args)
            contexts.append(context)
            return context

        returned = observe(native, samples)(
            preview, {"spell_id": 100}, effect, invocation
        )
        expected = random.Random(15)
        self.assertEqual(calls, [expected.randrange(1000)])
        self.assertEqual(rng.getstate(), expected.getstate())
        self.assertIs(returned, contexts[0])

    def test_exception_and_nested_scope_restore_previous_observer(self):
        with capture() as outer:
            with self.assertRaises(ValueError):
                with capture() as inner:
                    self.assertIs(current(), inner)
                    raise ValueError("native unsupported branch")
            self.assertIs(current(), outer)
        self.assertIsNone(current())

    def test_parallel_encounters_have_independent_observation_scopes(self):
        def worker(direction):
            preview, invocation, effect, callback, _ = fixture(direction)
            with capture() as samples:
                observe(callback, current())(
                    preview, {"spell_id": 100}, effect, invocation
                )
            return evidence(samples)[0]["observedLocalization"], current()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, (1, 5)))
        self.assertEqual(results, [("BACK", None), ("FRONT", None)])
        self.assertIsNone(current())
