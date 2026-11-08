"""Bounded native-JSON row-cache regressions; no compiled catalog is loaded."""
from collections import Counter
from copy import deepcopy
from itertools import count
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_native_timing_context as timing
from wakfu_server import combat_published_catalogs as published
from wakfu_server import combat_published_row_cache as row_cache
from wakfu_server import combat_state
from wakfu_server import combat_state_handler as state_handler
from wakfu_server import combat_definitions
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_published_catalogs import PublishedStaticMapping
from wakfu_server.combat_state_handler import NativeStateHandler, StateCarrierContext


class TinyReader:
    representation = "native_json"

    def __init__(self, descriptor, rows):
        self.descriptor = dict(descriptor)
        self._rows = {
            str(key): json.dumps(value, separators=(",", ":")).encode("utf-8")
            for key, value in rows.items()
        }
        self.reads = Counter()

    def __contains__(self, key):
        return key in self._rows

    def __iter__(self):
        return iter(self._rows)

    def __len__(self):
        return len(self._rows)

    def record_bytes(self, key):
        self.reads[key] += 1
        return self._rows[key]


def sealed_mapping(collection, rows, revision_char):
    revision = revision_char * 64
    descriptor = {
        "policy": published.POLICY,
        "revision": revision,
        "manifest_sha256": revision,
        "collection": collection,
        "count": len(rows),
        "ordered_keys_sha256": "e" * 64,
    }
    reader = TinyReader(descriptor, rows)
    return PublishedStaticMapping(descriptor, reader, _seal=published._SEAL), reader


def dummy_state_handler(catalog):
    return NativeStateHandler(
        SimpleNamespace(),
        [],
        catalog,
        action_id=1,
        allocate_uid=lambda: 1,
        context=lambda *args: None,
        execute_child=lambda invocation: None,
    )


def native_fight():
    actors = [
        combat_state.Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True),
        combat_state.Actor(8, 1, (1, 0, 0), 100, 6, 3, 5, 1),
    ]
    fight = combat_state.Fight(
        7701,
        actors,
        {(0, 0, 0), (1, 0, 0)},
        {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
    )
    fight.ready(3)
    return fight


def state_row(effect_ids=(901,)):
    return {
        "maximum_level": 5,
        "duration_base": 3,
        "duration_per_level": 0,
        "realtime_duration_base": 0,
        "realtime_duration_per_level": 0,
        "clock_actor": "caster",
        "tick_at_turn_end": True,
        "additive": False,
        "replace": False,
        "refresh": False,
        "protected": False,
        "skip_turn_timer": False,
        "effect_ids": list(effect_ids),
    }


def catalog_for(revision_state, revision_effect, state_rows=None):
    states, state_reader = sealed_mapping(
        "states", state_rows or {"321": state_row()}, revision_state
    )
    effects, effect_reader = sealed_mapping(
        "effects",
        {
            "901": {
                "minimum_level": 1,
                "maximum_level": 5,
                "target_masks": [0, 0, 0, 0, 0, 0, 0],
            }
        },
        revision_effect,
    )
    return {"states": states, "effects": effects}, state_reader, effect_reader


class PublishedRowCacheTests(unittest.TestCase):
    def test_decode_once_per_owner_and_bounded_per_collection(self):
        rows = {str(index): {"row": index} for index in range(130)}
        states, reader = sealed_mapping("states", rows, "a")
        catalog = {"states": states}
        handler = dummy_state_handler(catalog)
        provider = NativeEffectTimingProvider(catalog)

        first, eligible = handler._published_rows.row(catalog, "states", "0")
        same, _ = handler._published_rows.row(catalog, "states", "0")
        second, _ = handler._published_rows.row(catalog, "states", "1")
        self.assertTrue(eligible)
        self.assertIs(first, same)
        self.assertEqual((first, second), ({"row": 0}, {"row": 1}))
        self.assertEqual(reader.reads["0"], 1)
        self.assertEqual(reader.reads["1"], 1)

        other_owner, _ = provider._published_rows.row(catalog, "states", "0")
        self.assertEqual(other_owner, first)
        self.assertIsNot(other_owner, first)
        self.assertEqual(reader.reads["0"], 2)

        for index in range(2, 130):
            handler._published_rows.row(catalog, "states", str(index))
        self.assertLessEqual(
            len(handler._published_rows._rows["states"]),
            handler._published_rows.MAX_ROWS_PER_COLLECTION,
        )
        handler._published_rows.row(catalog, "states", "0")
        self.assertEqual(reader.reads["0"], 3)

    def test_catalog_and_collection_replacement_and_mutable_fallback(self):
        first_map, first_reader = sealed_mapping(
            "states", {"1": {"value": "first"}}, "b"
        )
        first_catalog = {"states": first_map}
        handler = dummy_state_handler(first_catalog)
        self.assertEqual(
            handler._published_rows.row(handler.catalog, "states", "1")[0]["value"],
            "first",
        )
        self.assertEqual(first_reader.reads["1"], 1)

        second_map, second_reader = sealed_mapping(
            "states", {"1": {"value": "second"}}, "c"
        )
        handler.catalog = {"states": second_map}
        self.assertEqual(
            handler._published_rows.row(handler.catalog, "states", "1")[0]["value"],
            "second",
        )
        self.assertEqual(second_reader.reads["1"], 1)

        replacement_map, replacement_reader = sealed_mapping(
            "states", {"1": {"value": "replacement"}}, "d"
        )
        handler.catalog["states"] = replacement_map
        self.assertEqual(
            handler._published_rows.row(handler.catalog, "states", "1")[0]["value"],
            "replacement",
        )
        self.assertEqual(replacement_reader.reads["1"], 1)

        effect_map_a, effect_reader_a = sealed_mapping(
            "effects", {"9": {"value": "effect-a"}}, "e"
        )
        handler.catalog["effects"] = effect_map_a
        handler._published_rows.row(handler.catalog, "effects", "9")
        effect_map_b, effect_reader_b = sealed_mapping(
            "effects", {"9": {"value": "effect-b"}}, "f"
        )
        handler.catalog["effects"] = effect_map_b
        value, _ = handler._published_rows.row(handler.catalog, "effects", "9")
        self.assertEqual(value["value"], "effect-b")
        self.assertEqual(
            (effect_reader_a.reads["9"], effect_reader_b.reads["9"]), (1, 1)
        )

        class MutableRows:
            def __init__(self):
                self.rows = {"1": {"value": "before"}}
                self.reads = 0

            def __getitem__(self, key):
                self.reads += 1
                return dict(self.rows[key])

        mutable_rows = MutableRows()
        mutable_catalog = {"states": mutable_rows}
        custom_handler = dummy_state_handler(mutable_catalog)
        before, cacheable = custom_handler._published_rows.row(
            mutable_catalog, "states", "1"
        )
        mutable_rows.rows["1"] = {"value": "after"}
        after, _ = custom_handler._published_rows.row(mutable_catalog, "states", "1")
        self.assertFalse(cacheable)
        self.assertEqual(
            (before["value"], after["value"], mutable_rows.reads),
            ("before", "after", 2),
        )

    def test_nonempty_state_child_keeps_full_catalog_and_matches_baseline_application(
        self,
    ):
        reference, level, child_uid = 321, 3, 901
        catalog, state_reader, effect_reader = catalog_for("1", "2")
        state_definition = state_row((child_uid,))
        # Rebuild the tiny immutable mapping with the actual nonempty child row.
        states, state_reader = sealed_mapping(
            "states", {str(reference): state_definition}, "1"
        )
        catalog["states"] = states
        effects = catalog["effects"]
        catalog_cache = row_cache.PublishedJsonRowCache()
        cached_state, cacheable = catalog_cache.row(catalog, "states", str(reference))
        profile_catalog = catalog_cache.catalog_with_published_row(
            catalog, "states", str(reference)
        )
        self.assertTrue(cacheable)
        self.assertIs(profile_catalog["effects"], effects)
        plain_catalog = {
            "states": {str(reference): deepcopy(state_definition)},
            "effects": {
                str(child_uid): {
                    "minimum_level": 1,
                    "maximum_level": 5,
                    "target_masks": [0, 0, 0, 0, 0, 0, 0],
                }
            },
        }
        expected_profile = combat_definitions.state_profile(
            plain_catalog, reference, level
        )

        actual_profiles = []
        scalar_module = published.static_row_scalar

        def capture_profile(actual_catalog, *args):
            actual_profiles.append(actual_catalog)
            return combat_definitions.state_profile(actual_catalog, *args)

        with patch.object(
            timing, "state_profile", side_effect=capture_profile
        ), patch.object(
            published, "static_row_scalar", wraps=scalar_module
        ) as scalar_reads, patch(
            "wakfu_server.combat_npc_initialization.constructor_stat_context",
            return_value=True,
        ):
            provider_fight = native_fight()
            invocation = EffectInvocation(92, 1, 7, 7, (0, 0, 0))
            candidate_context = NativeEffectTimingProvider(
                catalog
            ).direct_state_reference(
                provider_fight, invocation, reference, level, critical=False
            )
        self.assertIs(actual_profiles[0]["effects"], effects)
        self.assertEqual(
            combat_definitions.state_profile(actual_profiles[0], reference, level),
            expected_profile,
        )
        self.assertEqual(expected_profile["effects"], [child_uid])
        self.assertTrue(scalar_reads.call_args_list)
        self.assertTrue(
            all(call.args[0] is effects for call in scalar_reads.call_args_list)
        )

        def run_handler(handler_module, fight, handler_catalog):
            packets, executed = [], []
            uid_source = count(800)
            context_type = handler_module.StateCarrierContext
            handler = handler_module.NativeStateHandler(
                fight,
                packets,
                handler_catalog,
                action_id=7,
                allocate_uid=lambda: next(uid_source),
                context=lambda *args: context_type(
                    -1, 0, False, None, 100, False, False, False, 0, None
                ),
                execute_child=lambda invocation: executed.append(invocation),
            )
            result = handler.apply_reference(
                {"effect_class": 304},
                invocation,
                reference,
                level,
                carrier_context=context_type(
                    -1, 0, False, None, 100, False, False, False, 0, None
                ),
            )
            return result, packets, executed, fight

        candidate_catalog, _, _ = catalog_for(
            "3", "4", {str(reference): state_definition}
        )
        uncached_catalog = deepcopy(plain_catalog)
        candidate_result = run_handler(state_handler, native_fight(), candidate_catalog)
        uncached_result = run_handler(state_handler, native_fight(), uncached_catalog)
        self.assertEqual(candidate_result[0], uncached_result[0])
        self.assertEqual(candidate_result[1], uncached_result[1])
        self.assertEqual(candidate_result[2], uncached_result[2])
        self.assertEqual(
            candidate_result[3].actors[7].state_ledger.entries,
            uncached_result[3].actors[7].state_ledger.entries,
        )
        self.assertEqual(
            candidate_result[3].state_wire_payloads,
            uncached_result[3].state_wire_payloads,
        )
        entry = candidate_result[3].actors[7].state_ledger.entries[0]
        self.assertEqual(entry.effect_ids, (child_uid,))

    def test_unknown_state_preserves_original_catalog_and_validation_order(self):
        catalog, state_reader, _ = catalog_for("7", "8", {"321": state_row()})
        allocated = []
        fight = native_fight()
        packets = []
        handler = NativeStateHandler(
            fight,
            packets,
            catalog,
            action_id=3,
            allocate_uid=lambda: allocated.append(991) or 991,
            context=lambda *args: StateCarrierContext(
                -1, 0, False, None, 100, False, False, False, 0, None
            ),
            execute_child=lambda invocation: None,
        )
        invocation = EffectInvocation(93, 1, 7, 7, (0, 0, 0))

        from wakfu_server.combat_state_resistance_metadata import (
            native_state_absence_proven,
        )

        self.assertTrue(native_state_absence_proven(759))
        self.assertFalse(
            handler.apply_reference(
                {},
                invocation,
                759,
                1,
                carrier_context=StateCarrierContext(
                    -1, 0, False, None, 100, False, False, False, 0, None
                ),
            )
        )
        self.assertEqual(allocated, [])

        self.assertFalse(native_state_absence_proven(999999))
        original_states, original_effects = catalog["states"], catalog["effects"]
        original_apply = fight.apply_state
        seen_catalogs = []

        def capture_apply(*args, **kwargs):
            seen_catalogs.append(kwargs["catalog"])
            return original_apply(*args, **kwargs)

        fight.apply_state = capture_apply
        with self.assertRaisesRegex(ValueError, "Unknown state definition"):
            handler.apply_reference(
                {},
                invocation,
                999999,
                1,
                carrier_context=StateCarrierContext(
                    -1, 0, False, None, 100, False, False, False, 0, None
                ),
            )
        self.assertEqual(allocated, [991])
        self.assertEqual(seen_catalogs, [catalog])
        self.assertIs(catalog["states"], original_states)
        self.assertIs(catalog["effects"], original_effects)
        self.assertEqual(fight.actors[7].state_ledger.entries, ())
        self.assertEqual(packets, [])
        self.assertEqual(state_reader.reads["999999"], 1)


if __name__ == "__main__":
    unittest.main()
