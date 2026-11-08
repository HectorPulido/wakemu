"""Bounded reclamation retries, without caching reachability or changing roots."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from unittest.mock import patch
from test_gc_owned_collections import OwnedCollectionGCTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import group_payload


class RetiredGCRoundRetryTests(unittest.TestCase):
    def fixture(self):
        boundary._CURSORS.clear()
        previous, fight, runtime, dead, inert = OwnedCollectionGCTests().fixture()
        previous.native_timeline_round = fight.native_timeline_round = 4
        for uid, manager, base in ((10002, dead, 10002), (10003, 7, 10002)):
            payload = group_payload(
                uid=uid,
                base_uid=base,
                generic_effect=350552,
                caster_id=manager,
                target_id=None,
                cell=fight.actors[manager].position,
                container_type=None,
                container_id=None,
                timing_payload=b"",
            ).hex()
            fight.native_owned_group_effects[uid] = dict(
                target_id=None, effect_class=949, state_uid=None, payload=payload
            )
            fight.native_retained_records.install_owned(
                uid,
                asdict(
                    RetainedEffect(
                        uid,
                        None,
                        949,
                        350552,
                        manager_id=manager,
                        container_present=False,
                    )
                ),
            )
            fight.native_retained_order.append(uid)
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertNotIn(inert, fight.native_retained_records)
        self.assertIn(10002, fight.native_retained_records)
        self.assertEqual(boundary._CURSORS[fight][1:], (False, True, 4))
        return fight, runtime

    def test_round_retry_adoption_immediate_triggers_and_conservative_unknown(self):
        fight, runtime = self.fixture()
        before = deepcopy(fight.native_retained_records)
        # Each clone is the exact newly adopted publication owner, as Registry
        # does; cursor state must follow it through multiple actor turns.
        for _ in range(3):
            candidate, copied = deepcopy((fight, runtime))
            candidate.turn_id += 1
            with patch.object(
                boundary, "_canonical_graph", wraps=boundary._canonical_graph
            ) as graph:
                boundary.prepare_retired_gc(fight, candidate, copied, ((13497, b""),))
            self.assertEqual(graph.call_count, 0)
            self.assertEqual(candidate.native_retained_records, before)
            self.assertEqual(boundary._CURSORS[candidate], boundary._CURSORS[fight])
            fight, runtime = candidate, copied
        candidate, copied = deepcopy((fight, runtime))
        candidate.native_timeline_round += 1
        candidate.turn_id += 1
        with patch.object(
            boundary, "_canonical_graph", wraps=boundary._canonical_graph
        ) as graph:
            boundary.prepare_retired_gc(fight, candidate, copied, ())
        self.assertEqual(graph.call_count, 1)
        self.assertEqual(candidate.native_retained_records, before)
        self.assertEqual(boundary._CURSORS[candidate][3], 5)

        for trigger in (
            "shrink",
            "packet",
            "retirement_count",
            "pending",
            "unknown_round",
            "unknown_previous_round",
            "unknown_checked_round",
            "application_unarmed",
        ):
            with self.subTest(trigger=trigger):
                fight, runtime = self.fixture()
                candidate, copied = deepcopy((fight, runtime))
                packets = ()
                if trigger == "shrink":
                    candidate.native_owned_group_effects.pop(10003)
                    candidate.native_retained_records.pop(10003)
                    candidate.native_retained_order.remove(10003)
                elif trigger == "packet":
                    packets = ((13560, b""),)
                elif trigger == "retirement_count":
                    # Test scheduling only: the duplicate descriptor is not
                    # presented as canonical death authority to the collector.
                    rows = candidate.native_ordinary_qi_retirements
                    rows[999999] = deepcopy(next(iter(rows.values())))
                    copied.awaiting_ack = candidate.turn_id
                elif trigger == "pending":
                    copied.awaiting_ack = candidate.turn_id
                    boundary._CURSORS[fight] = (
                        len(fight.native_ordinary_qi_retirements),
                        True,
                        True,
                        4,
                    )
                elif trigger == "application_unarmed":
                    boundary._CURSORS[fight] = (
                        len(fight.native_ordinary_qi_retirements),
                        False,
                        False,
                        4,
                    )
                    packets = ((13497, b""),)
                elif trigger == "unknown_previous_round":
                    fight.native_timeline_round = None
                    packets = ((13497, b""),)
                elif trigger == "unknown_checked_round":
                    boundary._CURSORS[fight] = (
                        len(fight.native_ordinary_qi_retirements),
                        False,
                        True,
                        None,
                    )
                    packets = ((13497, b""),)
                else:
                    packets = ((13497, b""),)
                    candidate.native_timeline_round = None
                    candidate.turn_id += 1
                    copied.awaiting_ack = candidate.turn_id
                with patch.object(
                    boundary, "_quiescent", wraps=boundary._quiescent
                ) as quiescent:
                    boundary.prepare_retired_gc(fight, candidate, copied, packets)
                batched = trigger in (
                    "shrink",
                    "packet",
                    "retirement_count",
                    "application_unarmed",
                )
                self.assertEqual(quiescent.call_count, 0 if batched else 1)
                if trigger == "shrink":
                    self.assertIn(10002, candidate.native_retained_records)
                if trigger == "pending":
                    self.assertTrue(boundary._CURSORS[candidate][1])
                    resumed, resumed_runtime = deepcopy((candidate, copied))
                    resumed_runtime.awaiting_ack = None
                    with patch.object(
                        boundary, "_canonical_graph", wraps=boundary._canonical_graph
                    ) as graph:
                        boundary.prepare_retired_gc(
                            candidate, resumed, resumed_runtime, ()
                        )
                    self.assertEqual(graph.call_count, 1)
                    self.assertFalse(boundary._CURSORS[resumed][1])


if __name__ == "__main__":
    unittest.main()
