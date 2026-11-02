"""Recovery policy preserves victory and retries temporary exit contention."""
import copy
import json
from datetime import datetime, timezone
import unittest

from wakfu_server import dungeon_transition_recovery as recovery


class DungeonTransitionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.result = dict(victory=True, completed=False, current_room=2)
        self.topology = dict(
            policy="local_accessible_anchor_policy",
            asset_map_id=1369,
            doors=[],
            rooms=[dict(order=2, anchor=[-5, -55, -15], cells=[[-5, -55, -15]])],
            auto_edges=[dict(source_room=1, destination_room=2, anchor=[-4, -55, -17])],
        )
        self.error = recovery.RecoverableDungeonDestination(
            "forward_anchor_mismatch", "mismatch"
        )

    def test_unique_native_anchor_only_and_no_input_mutation(self):
        original = copy.deepcopy((self.result, self.topology))
        destination, journal = recovery.forward_anchor(
            self.result,
            self.topology,
            self.error,
            verify_anchor=lambda map_id, cell: map_id == 1369
            and cell == (-5, -55, -15),
        )
        self.assertEqual(destination, dict(map_id=1369, x=-5, y=-55, z=-15))
        self.assertEqual(journal["obsolete_anchor"], [-4, -55, -17])
        self.assertEqual(original, (self.result, self.topology))
        self.assertIsNone(
            recovery.forward_anchor(
                self.result, self.topology, self.error, verify_anchor=lambda *_: False
            )
        )
        self.topology["auto_edges"] *= 2
        self.assertIsNone(
            recovery.forward_anchor(
                self.result, self.topology, self.error, verify_anchor=lambda *_: True
            )
        )

    def test_repeated_contention_never_exhausts_and_delay_is_bounded(self):
        now = datetime.fromtimestamp(100, timezone.utc)
        for _ in range(100):
            journal = recovery.failure_journal(
                self.result, self.topology, self.error, now
            )
            self.result["transition_recovery"] = journal
            self.assertLessEqual(journal["next_retry"] - now.timestamp(), 60)
            json.dumps(journal)
            self.assertFalse(recovery.retry_due(self.result, self.topology, now))
            now = datetime.fromtimestamp(journal["next_retry"], timezone.utc)
            self.assertTrue(recovery.retry_due(self.result, self.topology, now))
        journal["exhausted"] = True  # Upgrade an already blocked legacy journal.
        self.assertTrue(recovery.retry_due(self.result, self.topology, now))

    def test_changed_source_retries_and_ambiguous_exit_is_not_invented(self):
        self.result["transition_recovery"] = recovery.failure_journal(
            self.result,
            self.topology,
            self.error,
            datetime.fromtimestamp(100, timezone.utc),
        )
        self.topology["rooms"][0]["anchor"] = [1, 2, 3]
        self.assertTrue(
            recovery.retry_due(
                self.result, self.topology, datetime.fromtimestamp(100, timezone.utc)
            )
        )
        self.assertFalse(recovery.exit_authorized(self.topology, 1))
