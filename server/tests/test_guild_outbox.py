"""Outbox recovery contract without a live database or server."""
from contextlib import contextmanager
import unittest

from wakfu_server.characters.guild_outbox import drain


class FakeStore:
    def __init__(self, events):
        self.events = events
        self.in_transaction = False
        self.acked = []

    @contextmanager
    def connection(self):
        self.in_transaction = True
        try:
            yield self
        finally:
            self.in_transaction = False

    def execute(self, sql, args):
        if sql.startswith("SELECT"):
            self.result = self.events[: args[0]]
        else:
            ids, guild, revision = args
            self.result = [
                {"id": e["id"]}
                for e in self.events
                if e["id"] in ids
                and e["guild_id"] == guild
                and e["revision"] <= revision
            ]
            self.acked.extend(r["id"] for r in self.result)
        return self

    def fetchall(self):
        return self.result


def event(identity, guild, revision, **payload):
    return dict(id=identity, guild_id=guild, revision=revision, payload=payload)


class GuildOutboxTests(unittest.TestCase):
    def test_coalesces_refresh_and_retains_events_added_during_publication(self):
        store = FakeStore(
            [
                event(1, 5, 1, character_id=10),
                event(2, 5, 2, member_ids=[11, 12]),
                event(3, 9, 1, target_id=20),
            ]
        )
        calls = []

        def publish(guild, revision, affected):
            self.assertFalse(store.in_transaction)
            calls.append((guild, revision, affected))
            if guild == 5:
                store.events.append(event(4, 5, 3, character_id=30))

        self.assertEqual(drain(store, publish), 3)
        self.assertEqual(calls, [(5, 2, (10, 11, 12)), (9, 1, (20,))])
        self.assertEqual(store.acked, [1, 2, 3])

    def test_failed_publication_is_not_acknowledged(self):
        store = FakeStore([event(1, 5, 1, character_id=10)])

        def fail(*args):
            self.assertFalse(store.in_transaction)
            raise RuntimeError("Network unavailable")

        with self.assertRaises(RuntimeError):
            drain(store, fail)
        self.assertEqual(store.acked, [])

    def test_bounded_batch_and_invalid_limits(self):
        store = FakeStore([event(1, 5, 1), event(2, 5, 2)])
        self.assertEqual(drain(store, lambda *args: None, limit=1), 1)
        self.assertEqual(store.acked, [1])
        for value in (0, 1025, True, 1.5):
            with self.assertRaises(ValueError):
                drain(store, lambda *args: None, limit=value)
