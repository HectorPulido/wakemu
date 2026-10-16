"""PostgreSQL update hints wake only the owning socket subscription."""
import select
import threading
import unittest

from wakfu_server.custom_tasks.external_updates import Listener, Subscription


class ObjectivesUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.listener = Listener.__new__(Listener)
        self.listener.lock = threading.Lock()
        self.listener.subscriptions = set()
        self.first = Subscription(self.listener)
        self.second = Subscription(self.listener)
        self.first.character_id = 11
        self.second.character_id = 22
        self.listener.subscriptions.update((self.first, self.second))
        self.addCleanup(self.first.close)
        self.addCleanup(self.second.close)

    def test_notification_routes_to_matching_character_only(self):
        self.listener.notify("11")
        self.assertTrue(self.first.dirty.is_set())
        self.assertFalse(self.second.dirty.is_set())
        self.assertTrue(select.select([self.first.reader], [], [], 0)[0])
        self.assertFalse(select.select([self.second.reader], [], [], 0)[0])

    def test_broadcast_payload_and_object_payload_wake_subscribers(self):
        self.listener.notify("0")
        self.assertTrue(self.first.dirty.is_set())
        self.assertTrue(self.second.dirty.is_set())
        self.first.dirty.clear()
        self.second.dirty.clear()
        self.first.drain()
        self.second.drain()
        self.listener.notify('{"character_id":22}')
        self.assertFalse(self.first.dirty.is_set())
        self.assertTrue(self.second.dirty.is_set())

    def test_malformed_and_negative_ids_do_not_wake_any_socket(self):
        for payload in ("not-json", "-1", "true", '{"character_id":"11"}'):
            self.listener.notify(payload)
        self.assertFalse(self.first.dirty.is_set())
        self.assertFalse(self.second.dirty.is_set())
        self.assertFalse(
            select.select([self.first.reader, self.second.reader], [], [], 0)[0]
        )


if __name__ == "__main__":
    unittest.main()
