"""Frozen value reuse cannot bypass complete native population validation."""
import gc
import unittest
import weakref
from unittest.mock import patch

from wakfu_server import combat_retained_runtime as runtime


class RetainedPopulationReuseTests(unittest.TestCase):
    def test_population_above_global_lru_reuses_exact_values_and_observes_mutation(
        self,
    ):
        owner = runtime.NativeRetainedRuntime.__new__(runtime.NativeRetainedRuntime)
        records = {
            uid: dict(
                uid=uid,
                target_id=7,
                manager_id=7,
                effect_class=400,
                generic_effect=1,
                definition_dispellable=True,
            )
            for uid in range(1, 2170)
        }
        order = tuple(records)
        with patch.object(
            runtime, "_cached_retained_record", wraps=runtime._cached_retained_record
        ) as build:
            first = runtime._retained_population(owner, records, order)
            self.assertEqual(build.call_count, 2169)
            for _ in range(3):
                again = runtime._retained_population(owner, records, order)
                self.assertTrue(all(a is b for a, b in zip(first, again)))
            self.assertEqual(build.call_count, 2169)
            records[1]["generic_effect"] = 2
            records[2]["definition_dispellable"] = 1
            changed = runtime._retained_population(owner, records, order)
            self.assertEqual(build.call_count, 2171)
            self.assertEqual(changed[0].generic_effect, 2)
            self.assertIs(type(changed[1].definition_dispellable), int)
            self.assertIs(type(first[1].definition_dispellable), bool)
            del records[1]
            runtime._retained_population(owner, records, tuple(records))
            self.assertNotIn(1, runtime._RETAINED_POPULATIONS[owner])
            records[2]["container_kind"] = []
            fallback = runtime._retained_population(owner, records, tuple(records))
            self.assertEqual(fallback[0].container_kind, [])
            self.assertNotIn(2, runtime._RETAINED_POPULATIONS[owner])
        self.assertEqual(vars(owner), {})
        reference = weakref.ref(owner)
        del owner
        gc.collect()
        self.assertIsNone(reference())

    def test_cached_values_still_receive_full_view_authority_validation(self):
        import test_combat_event_replay as fixture

        fixture.NativeEventReplayTests.setUpClass()
        case = fixture.NativeEventReplayTests()
        case.setUp()
        case.retention.view()
        case.retention.view()
        uid = next(iter(case.fight.native_retained_records))
        case.fight.native_retained_records[uid]["generic_effect"] = True
        with self.assertRaisesRegex(ValueError, "generic definition"):
            case.retention.view()
