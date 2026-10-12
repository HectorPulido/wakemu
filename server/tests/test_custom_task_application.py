"""Application authorization order and post-commit native packet publication."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch
from wakfu_server.custom_tasks import application, presentation


class StoreDouble:
    def __init__(self, *, reject=False, fail_commit=False):
        self.events = []
        self.db = object()
        self.reject = reject
        self.fail_commit = fail_commit

    @contextmanager
    def connection(self):
        self.events.append("begin")
        yield self.db
        if self.fail_commit:
            self.events.append("commit_failed")
            raise RuntimeError("Simulated commit failure")
        self.events.append("committed")

    def lock_character(self, db, account, generation, character, *, selected):
        self.events.append(("lock", account, generation, character, selected))
        if self.reject:
            raise ValueError("Rejected owned selected session")


class CustomTaskApplicationTests(unittest.TestCase):
    def test_selected_authorization_precedes_snapshot_and_return_follows_commit(self):
        store = StoreDouble()
        rows = [
            {
                "key": "task",
                "title": "Hunter",
                "description": "Kill20",
                "target": 20,
                "count": 1,
                "completed": False,
            }
        ]

        def snapshot(db, account, character, definitions):
            self.assertEqual(store.events[-1], ("lock", 1, "a" * 32, 2, True))
            store.events.append("snapshot")
            return rows

        gift = presentation.GiftPackage(
            "Genuine gift", "Earned", (presentation.GiftItem("real:1", 12686, 2),)
        )
        with patch.object(application.service, "snapshot", side_effect=snapshot):
            packet = application.publication(
                store, 1, "a" * 32, 2, existing_packages=(gift,), cap_reached=True
            )
        self.assertEqual(store.events[-1], "committed")
        self.assertEqual(packet[0], 13369)
        self.assertEqual(packet[1][:2], b"\0\2")
        self.assertIn(b"Genuine gift", packet[1])
        self.assertIn(b"real:1", packet[1])
        self.assertIn(b"In progress: 1/20", packet[1])
        self.assertEqual(packet[1][-1], 1)

    def test_failed_authorization_never_reads_snapshot(self):
        store = StoreDouble(reject=True)
        with patch.object(application.service, "snapshot") as snapshot:
            with self.assertRaises(ValueError):
                application.publication(
                    store, 1, "a" * 32, 2, existing_packages=(), cap_reached=False
                )
            snapshot.assert_not_called()

    def test_commit_failure_propagates_without_returning_packet(self):
        store = StoreDouble(fail_commit=True)
        returned = []
        with patch.object(application.service, "snapshot", return_value=[]):
            with self.assertRaises(RuntimeError):
                returned.append(
                    application.publication(
                        store, 1, "a" * 32, 2, existing_packages=(), cap_reached=False
                    )
                )
        self.assertEqual(returned, [])
        self.assertEqual(store.events[-1], "commit_failed")

    def test_explicit_gift_authority_and_strict_identity_required(self):
        store = StoreDouble()
        with self.assertRaises(TypeError):
            application.publication(store, 1, "a" * 32, 2)
        for account, generation, character in (
            (True, "a" * 32, 2),
            (1, "bad", 2),
            (1, "a" * 32, False),
        ):
            with self.subTest(
                account=account, generation=generation, character=character
            ):
                with self.assertRaises(ValueError):
                    application.publication(
                        store,
                        account,
                        generation,
                        character,
                        existing_packages=(),
                        cap_reached=False,
                    )
        self.assertEqual(store.events, [])
