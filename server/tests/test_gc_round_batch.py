"""Native reclamation batches within a round without delaying pending drains."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_retired_gc_round_retry import RetiredGCRoundRetryTests
from wakfu_server import combat_retained_gc_boundary as boundary


class GCRoundBatchTests(unittest.TestCase):
    def test_same_round_batch_next_round_sweep_and_immediate_fallbacks(self):
        def fixture():
            return RetiredGCRoundRetryTests().fixture()

        for trigger in ("removal", "new_retirement", "shrink"):
            fight, runtime = fixture()
            candidate, copied = deepcopy((fight, runtime))
            candidate.turn_id += 1
            packets = ((13560, b""),) if trigger == "removal" else ()
            if trigger == "new_retirement":
                # Scheduling only: never submit this duplicate to canonical GC.
                candidate.native_ordinary_qi_retirements[999999] = deepcopy(
                    next(iter(candidate.native_ordinary_qi_retirements.values()))
                )
            if trigger == "shrink":
                candidate.native_owned_group_effects.pop(10003)
                candidate.native_retained_records.pop(10003)
                candidate.native_retained_order.remove(10003)
            before = deepcopy(dict(candidate.native_retained_records))
            with patch.object(
                boundary, "_canonical_graph", wraps=boundary._canonical_graph
            ) as graph:
                boundary.prepare_retired_gc(fight, candidate, copied, packets)
            self.assertEqual(graph.call_count, 0, trigger)
            self.assertEqual(dict(candidate.native_retained_records), before)
            self.assertEqual(boundary._CURSORS[candidate][1:], (False, True, 4))
            if trigger == "shrink":
                self.assertIn(10002, candidate.native_retained_records)
                later, later_runtime = deepcopy((candidate, copied))
                later.native_timeline_round = 5
                later.turn_id += 1
                with patch.object(
                    boundary, "_canonical_graph", wraps=boundary._canonical_graph
                ) as graph:
                    boundary.prepare_retired_gc(candidate, later, later_runtime, ())
                self.assertEqual(graph.call_count, 1)
                self.assertNotIn(10002, later.native_retained_records)
                self.assertIn(10002, candidate.native_retained_records)

        # A deferred ACK barrier must drain in this round as soon as quiescent.
        fight, runtime = fixture()
        boundary._CURSORS[fight] = (boundary._CURSORS[fight][0], True, True, 4)
        candidate, copied = deepcopy((fight, runtime))
        with patch.object(
            boundary, "_canonical_graph", wraps=boundary._canonical_graph
        ) as graph:
            boundary.prepare_retired_gc(fight, candidate, copied, ())
        self.assertEqual(graph.call_count, 1)
        self.assertFalse(boundary._CURSORS[candidate][1])

        for trigger in ("unknown_round", "custom_packet_row", "finished"):
            fight, runtime = fixture()
            candidate, copied = deepcopy((fight, runtime))
            candidate.turn_id += 1
            packets = ()
            if trigger == "unknown_round":
                candidate.native_timeline_round = None
            elif trigger == "custom_packet_row":
                packets = ([13560, b""],)
            else:
                candidate.phase = "finished"
            with patch.object(
                boundary, "_canonical_graph", wraps=boundary._canonical_graph
            ) as graph:
                boundary.prepare_retired_gc(fight, candidate, copied, packets)
            self.assertEqual(graph.call_count, 1, trigger)
            self.assertIn(10002, candidate.native_retained_records)
