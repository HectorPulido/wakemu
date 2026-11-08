"""Run only after the candidate is reviewed/applied to a matching package."""
from copy import deepcopy
import gc
import unittest
import weakref
from unittest.mock import patch
from wakfu_server import combat_retained_runtime as runtime
from wakfu_server.combat_state import Fight


class ConditionPopulationTests(unittest.TestCase):
    def test_shared_owner_mutations_clone_and_gc_above_lru_capacity(self):
        fight = Fight.__new__(Fight)
        fight.native_retained_records = {
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
        fight.native_retained_order = list(fight.native_retained_records)
        first = runtime.NativeRetainedRuntime.__new__(runtime.NativeRetainedRuntime)
        second = runtime.NativeRetainedRuntime.__new__(runtime.NativeRetainedRuntime)
        first.fight = second.fight = fight
        with patch.object(
            runtime, "_retained_record", wraps=runtime._retained_record
        ) as build:
            original = runtime._retained_read_population(fight, runtime=first)
            runtime._retained_read_population(fight, runtime=second)
            runtime._retained_read_population(fight)
            self.assertEqual(build.call_count, 2169)
            fight.native_retained_records[1]["generic_effect"] = 2
            fight.native_retained_records[2]["definition_dispellable"] = 1
            changed = runtime._retained_read_population(fight)
            self.assertEqual(build.call_count, 2171)
            self.assertIs(type(changed[1].definition_dispellable), int)
            self.assertIs(type(original[1].definition_dispellable), bool)
            clone = deepcopy(fight)
            runtime._retained_read_population(clone)
            self.assertEqual(build.call_count, 4340)
            self.assertIsNot(
                runtime._RETAINED_POPULATIONS[fight],
                runtime._RETAINED_POPULATIONS[clone],
            )
            clone.native_retained_records.pop(1)
            clone.native_retained_order.remove(1)
            runtime._retained_read_population(clone)
            self.assertIn(1, runtime._RETAINED_POPULATIONS[fight])
            self.assertNotIn(1, runtime._RETAINED_POPULATIONS[clone])
        self.assertEqual(
            set(vars(fight)), {"native_retained_records", "native_retained_order"}
        )
        reference = weakref.ref(fight)
        del first, second, fight
        gc.collect()
        self.assertIsNone(reference())

    def test_custom_fight_condition_keeps_original_uncached_traversal(self):
        class CustomFight(Fight):
            pass

        fight = CustomFight.__new__(CustomFight)
        fight.native_retained_records = {
            1: dict(uid=1, target_id=7, effect_class=400, generic_effect=1)
        }
        fight.native_retained_order = [1]
        with patch.object(
            runtime, "_retained_record", wraps=runtime._retained_record
        ) as build:
            runtime._retained_read_population(fight)
            runtime._retained_read_population(fight)
            self.assertEqual(build.call_count, 2)
        self.assertNotIn(fight, runtime._RETAINED_POPULATIONS)

    def test_custom_metaclass_value_cannot_enter_weak_owner_cache(self):
        class Meta(type):
            def __eq__(self, other):
                return True

            __hash__ = type.__hash__

        class Custom(metaclass=Meta):
            pass

        fight = Fight.__new__(Fight)
        value = Custom()
        value.owner = fight
        fight.native_retained_records = {
            1: dict(uid=1, target_id=7, effect_class=400, generic_effect=value)
        }
        fight.native_retained_order = [1]
        with patch.object(
            runtime,
            "_retained_record",
            side_effect=lambda row: runtime.RetainedEffect(**row),
        ):
            runtime._retained_read_population(fight)
        self.assertEqual(runtime._RETAINED_POPULATIONS[fight], {})

    def test_class_descriptor_keeps_per_uid_condition_reads(self):
        fight = Fight.__new__(Fight)
        reads = []

        def ordered(owner):
            reads.append("order")
            return [1, 2]

        def records(owner):
            reads.append("records")
            return {
                uid: dict(
                    uid=uid, target_id=7, effect_class=400, generic_effect=len(reads)
                )
                for uid in (1, 2)
            }

        with patch.object(
            Fight, "native_retained_records", property(records), create=True
        ):
            with patch.object(
                Fight, "native_retained_order", property(ordered), create=True
            ):
                result = runtime._retained_read_population(fight)
        self.assertEqual(reads, ["order", "records", "records"])
        self.assertEqual([entry.generic_effect for entry in result], [2, 3])
        self.assertNotIn(fight, runtime._RETAINED_POPULATIONS)

    def test_two_real_views_then_condition_still_validate_live_authority(self):
        import test_combat_event_replay as fixture

        fixture.NativeEventReplayTests.setUpClass()
        case = fixture.NativeEventReplayTests()
        case.setUp()
        other = runtime.NativeRetainedRuntime.__new__(runtime.NativeRetainedRuntime)
        other.fight = case.fight
        first = case.retention.view()
        with patch.object(
            runtime, "_retained_record", wraps=runtime._retained_record
        ) as build:
            self.assertEqual(other.view().entries, first.entries)
            runtime._native_retained_condition_population(case.fight)
            self.assertEqual(build.call_count, 0)
        uid = next(iter(case.fight.native_retained_records))
        case.fight.native_retained_records[uid]["generic_effect"] = True
        for read in (
            other.view,
            lambda: runtime._native_retained_condition_population(case.fight),
        ):
            with self.assertRaisesRegex(ValueError, "generic definition"):
                read()


if __name__ == "__main__":
    unittest.main(verbosity=2)
