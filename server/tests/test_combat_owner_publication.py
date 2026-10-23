"""Company admission captures the actual authenticated peer, never its leader."""
import threading
import unittest
from types import SimpleNamespace

from wakfu_server.combat_owner_publication import publication_for_world_member


class OwnerPublicationTests(unittest.TestCase):
    def setUp(self):
        self.member = dict(id=7, account_id=2, generation="session7")
        self.scope = (2, "session7", 7, 99, 71)
        self.tracker = object()
        self.peer = SimpleNamespace(
            native_instance_scope=lambda: self.scope, instance_publications=self.tracker
        )
        self.world = SimpleNamespace(
            lock=threading.RLock(),
            players={
                7: ("session7", self.peer, dict(id=7, account_id=2)),
                8: (
                    "other",
                    SimpleNamespace(instance_publications=object()),
                    dict(id=8, account_id=3),
                ),
            },
        )

    def resolve(self):
        return publication_for_world_member(
            self.world, self.member, map_id=99, instance_id=71
        )

    def test_resolves_exact_owner_connection_without_modifying_publication(self):
        tracker, scope = self.resolve()
        self.assertIs(tracker, self.tracker)
        self.assertEqual(scope, self.scope)

    def test_rejects_stale_registry_generation_or_foreign_owned_identity(self):
        for entry in (
            ("old", self.peer, dict(id=7, account_id=2)),
            ("session7", self.peer, dict(id=8, account_id=2)),
            ("session7", self.peer, dict(id=7, account_id=3)),
        ):
            with self.subTest(entry=entry):
                self.world.players[7] = entry
                with self.assertRaises(ValueError):
                    self.resolve()

    def test_rejects_replaced_connection_scope_or_missing_owner_without_leader_fallback(
        self,
    ):
        for scope in (
            None,
            (2, "new", 7, 99, 71),
            (3, "session7", 7, 99, 71),
            (2, "session7", 8, 99, 71),
            (2, "session7", 7, 98, 71),
            (2, "session7", 7, 99, 72),
        ):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.scope = scope
                self.resolve()
        self.world.players.pop(7)
        with self.assertRaises(ValueError):
            self.resolve()
