import unittest
from unittest.mock import patch
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_state import Fight
from wakfu_server.combat_retained_collections import OwnedMap


class CountsTests(unittest.TestCase):
    def test_native_counts_bypass_callbacks_and_opaque_fields_are_omitted(self):
        class Opaque(dict):
            def __len__(self):
                raise AssertionError("custom length called")

            def __getattribute__(self, name):
                raise AssertionError("custom attribute called")

        fight = Fight.__new__(Fight)
        fight.id, fight.turn_id = 433, 1
        fight.actors = {1: object(), 2: object()}
        records = dict.__new__(OwnedMap)
        dict.__setitem__(records, 7, object())
        fight.native_retained_records = records
        with patch.object(boundary, "_GC_DIAGNOSTICS", True), patch.object(
            boundary._GC_DIAGNOSTIC_LOG, "warning"
        ) as log, patch.object(
            OwnedMap, "__len__", side_effect=AssertionError("virtual length called")
        ):
            boundary._GC_DIAGNOSTIC_SEEN.clear()
            boundary._gc_diagnostic(fight, "count_probe")
            self.assertIn("actor_count=2", log.call_args.args[-1])
            self.assertIn("retained_record_count=1", log.call_args.args[-1])
            fight.actors = Opaque()
            fight.native_retained_records = Opaque()
            boundary._gc_diagnostic(fight, "opaque_count_probe")
            self.assertNotIn("actor_count=", log.call_args.args[-1])
            self.assertNotIn("retained_record_count=", log.call_args.args[-1])
        with patch.object(boundary, "_GC_DIAGNOSTICS", False), patch.object(
            boundary._GC_DIAGNOSTIC_LOG, "warning"
        ) as log:
            boundary._gc_diagnostic(fight, "disabled")
            log.assert_not_called()
