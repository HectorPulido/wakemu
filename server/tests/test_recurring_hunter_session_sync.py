import struct
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from wakfu_server.objectives import environmental_recurring_storage as recurring


class RecurringHunterSessionSyncTests(unittest.TestCase):
    def test_cached_future_boundary_needs_no_database_or_session_lock(self):
        store = Mock()
        self.assertEqual(
            recurring.synchronize_owned(
                store, 2, 3, 4, next_boundary_ms=200, now_ms=199
            ),
            (200, []),
        )
        store.connection.assert_not_called()

    def test_first_checkpoint_publishes_expiration_and_schedules_earliest_period(self):
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {"anchor_ms": 0, "period_ms": 86400000},
            {"anchor_ms": 0, "period_ms": 604800000},
        ]
        store = Mock()
        store.connection.return_value = nullcontext(db)
        packets = [
            (13205, struct.pack(">qi", 4, 4113)),
            (13371, struct.pack(">qiB", 4, 4113, 0)),
        ]
        with patch.object(recurring, "_now", return_value=86400000), patch.object(
            recurring, "synchronize", return_value=packets
        ) as sync:
            boundary, emitted = recurring.synchronize_owned(
                store, 2, 3, 4, now_ms=86400000
            )
        self.assertEqual(boundary, 86400000 + 3_600_000)
        self.assertEqual(emitted, packets)
        store.lock_character.assert_called_once_with(db, 2, 3, 4)
        sync.assert_called_once_with(db, store, {"id": 4, "account_id": 2})

    def test_failed_synchronization_propagates_and_does_not_advance_boundary(self):
        store = Mock()
        store.connection.return_value = nullcontext(Mock())
        with patch.object(recurring, "_now", return_value=200), patch.object(
            recurring, "synchronize", side_effect=ValueError("retry")
        ):
            with self.assertRaisesRegex(ValueError, "retry"):
                recurring.synchronize_owned(
                    store, 2, 3, 4, next_boundary_ms=200, now_ms=200
                )

    def test_company_heroes_are_reconciled_with_owned_main(self):
        db = Mock()
        account_row, heroes, contracts = Mock(), Mock(), Mock()
        heroes.fetchall.return_value = [{"character_id": 5}, {"character_id": 6}]
        contracts.fetchall.return_value = [{"anchor_ms": 0, "period_ms": 86400000}]
        db.execute.side_effect = [account_row, heroes, contracts]
        store = Mock()
        store.connection.return_value = nullcontext(db)
        with patch.object(recurring, "_now", return_value=1000), patch.object(
            recurring, "synchronize", side_effect=lambda db, store, actor: [actor["id"]]
        ) as sync:
            _, packets = recurring.synchronize_owned(
                store, 2, 3, 4, now_ms=1000, include_company=True
            )
        self.assertEqual(packets, [4, 5, 6])
        self.assertEqual(
            [call.args[2]["id"] for call in sync.call_args_list], [4, 5, 6]
        )
        self.assertEqual(db.execute.call_args_list[1].args[1], (2, 4))


if __name__ == "__main__":
    unittest.main()
