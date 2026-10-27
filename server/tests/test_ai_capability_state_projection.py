"""Advisory state roots retain complete native validation and source identity."""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from wakfu_server import combat_ai_capability_projection as projection
from wakfu_server.combat_definitions import state_profile
from wakfu_server.combat_published_catalogs import POLICY, PublishedStaticMapping, _SEAL


class AdvisoryStateProjectionTests(unittest.TestCase):
    def setUp(self):
        projection.clear()
        self.addCleanup(projection.clear)

    def source(self, rows, name, revision, reads):
        class Reader:
            representation = "native_json"

            def record_bytes(self, key):
                reads.append((name, key))
                return json.dumps(rows[key], separators=(",", ":")).encode()

        descriptor = dict(
            policy=POLICY,
            revision=revision * 64,
            manifest_sha256=revision * 64,
            collection=name,
            count=len(rows),
            ordered_keys_sha256=hashlib.sha256(
                json.dumps(list(rows)).encode()
            ).hexdigest(),
        )
        return PublishedStaticMapping(descriptor, Reader(), _seal=_SEAL)

    def fixture(self, revision="a"):
        states = {
            "5": dict(
                maximum_level=200,
                duration_base=1,
                duration_per_level=0,
                realtime_duration_base=0,
                realtime_duration_per_level=0,
                clock_actor=0,
                tick_at_turn_end=False,
                additive=False,
                replace=False,
                refresh=False,
                protected=False,
                skip_turn_timer=False,
                effect_ids=[11, 12],
            )
        }
        effects = {
            "11": dict(minimum_level=1, maximum_level=30),
            "12": dict(minimum_level=100),
        }
        reads = []
        return (
            states,
            effects,
            reads,
            dict(
                states=self.source(states, "shared.states", revision, reads),
                effects=self.source(effects, "shared.state_effects", revision, reads),
            ),
        )

    def test_selected_roots_keep_short_circuit_revisions_and_live_private_inputs(self):
        states, effects, reads, source = self.fixture()
        expected = tuple(state_profile(source, 5, 23)["effects"])
        self.assertEqual(expected, (11,))
        reads.clear()
        self.assertEqual(projection.selected_state_roots(source, 5, 23), expected)
        # The shared row is fetched once for min/max; an excluded row never
        # evaluates its deliberately missing maximum field.
        self.assertEqual(
            reads,
            [
                ("shared.states", "5"),
                ("shared.state_effects", "11"),
                ("shared.state_effects", "12"),
            ],
        )
        reads.clear()
        self.assertEqual(projection.selected_state_roots(source, 5, 23), expected)
        self.assertFalse(reads)
        for function in (
            lambda: state_profile(source, 5, 100),
            lambda: projection.selected_state_roots(source, 5, 100),
        ):
            with self.assertRaises(KeyError):
                function()
        other_states, other_effects, other_reads, other = self.fixture("b")
        other_effects["11"]["minimum_level"] = 30
        self.assertEqual(projection.selected_state_roots(other, 5, 23), ())
        self.assertTrue(other_reads)
        # Both independent pins belong to the result, including mixed views.
        mixed = dict(states=source["states"], effects=other["effects"])
        self.assertEqual(projection.selected_state_roots(mixed, 5, 23), ())
        private = dict(states=deepcopy(states), effects=deepcopy(effects))
        self.assertEqual(projection.selected_state_roots(private, 5, 23), (11,))
        private["effects"]["11"]["minimum_level"] = 30
        self.assertEqual(projection.selected_state_roots(private, 5, 23), ())
        zero_states, zero_effects, _, zero = self.fixture("0")
        self.assertEqual(projection.selected_state_roots(zero, 5, 23), (11,))
        zero_effects["11"]["minimum_level"] = 30
        self.assertEqual(projection.selected_state_roots(zero, 5, 23), ())

    def test_malformed_state_validation_and_cache_bounds_are_not_skipped(self):
        states, effects, reads, source = self.fixture()
        del states["5"]["clock_actor"]
        for function in (
            lambda: state_profile(source, 5, 23),
            lambda: projection.selected_state_roots(source, 5, 23),
        ):
            with self.assertRaises(KeyError):
                function()
        states["5"]["clock_actor"] = 0
        with patch.object(projection, "_MAX_BYTES", 1):
            self.assertEqual(projection.selected_state_roots(source, 5, 23), (11,))
            self.assertFalse(projection._CACHE)
        with patch.object(projection, "_MAX_ENTRIES", 1):
            self.assertEqual(projection.selected_state_roots(source, 5, 23), (11,))
            self.assertEqual(len(projection._CACHE), 1)
        for level in (True, 1.5, -32769, 32768):
            with self.subTest(level=level), self.assertRaises(ValueError):
                projection.selected_state_roots(source, 5, level)

    def test_large_state_streams_verified_batches_without_truncating_roots(self):
        states, effects, reads, source = self.fixture()
        states["5"]["effect_ids"] = list(range(1000, 1130))
        effects.clear()
        effects.update(
            {
                str(ref): dict(minimum_level=1, maximum_level=200)
                for ref in states["5"]["effect_ids"]
            }
        )
        batches = []

        def many(keys):
            batches.append(tuple(keys))
            return {
                key: json.dumps(effects[key]).encode() for key in keys if key in effects
            }

        source["effects"]._reader.get_many_bytes = many
        expected = tuple(state_profile(source, 5, 23)["effects"])
        reads.clear()
        actual = projection.selected_state_roots(source, 5, 23)
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 130)
        self.assertEqual([len(batch) for batch in batches], [64, 64, 2])
        self.assertEqual(reads, [("shared.states", "5")])
        projection.clear()
        del effects["1005"]
        for function in (
            lambda: state_profile(source, 5, 23),
            lambda: projection.selected_state_roots(source, 5, 23),
        ):
            with self.assertRaises(KeyError):
                function()

    def test_effect_projection_preserves_native_parameter_arithmetic_and_isolation(
        self,
    ):
        from wakfu_server.combat_definitions import effect_profile

        rows = {
            "7": dict(
                effect_class=304,
                criteria="True",
                children=[8, 9],
                native_area=dict(future=True),
                area=False,
                parameter_count=2,
                parameters=[4404, 0, 1, 0.25],
                probability_base=100,
                probability_per_level=0,
            )
        }
        reads = []
        source = self.source(rows, "npc_imported.effects", "c", reads)
        first = projection.advisory_effect(source, 7)
        self.assertEqual(effect_profile(first, 23), effect_profile(rows["7"], 23))
        self.assertEqual(first["children"], (8, 9))
        self.assertTrue(first["criteria"])
        self.assertTrue(first["native_area"])
        with self.assertRaises(TypeError):
            first["effect_class"] = 1
        projection.advisory_effect(source, 7)
        self.assertEqual(reads, [("npc_imported.effects", "7")])
        raw = projection.advisory_effect(rows, 7)
        self.assertIs(raw, rows["7"])
