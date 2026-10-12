"""Actual application facade commits before generation-fenced task-card delivery."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch
from wakfu_server.custom_tasks import hooks, application


class Store:
    def __init__(self):
        self.in_transaction = False
        self.current = True
        self.reads = 0

    @contextmanager
    def connection(self):
        self.in_transaction = True
        try:
            yield object()
        finally:
            self.in_transaction = False

    def lock_character(self, *args, **kwargs):
        if not self.current:
            raise ValueError("Invalid selected lease")

    def current_character_session(self, *args):
        self.assert_outside()
        return self.current

    def assert_outside(self):
        if self.in_transaction:
            raise AssertionError("Publication attempted within transaction")


class World:
    def __init__(self, store):
        self.store = store
        self.sent = []
        self.delivered = True

    def send_batch_to(self, character, generation, packets):
        self.store.assert_outside()
        self.sent.append((character, generation, packets))
        return self.delivered


class SelectedTaskCardsTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.world = World(self.store)
        self.cards = hooks.SelectedTaskCards()
        self.rows = [
            {
                "key": "task",
                "title": "Hunter",
                "description": "Kill20",
                "target": 20,
                "count": 1,
                "completed": False,
            }
        ]
        self.snapshot = patch.object(
            application.service, "snapshot", return_value=self.rows
        ).start()
        self.addCleanup(patch.stopall)

    def refresh(self, character=2, ready=True):
        return self.cards.refresh(
            self.store,
            self.world,
            1,
            "a" * 32,
            character,
            ready=ready,
            existing_packages=(),
            cap_reached=False,
        )

    def test_commit_precedes_delivery_and_replaced_selection_never_sends(self):
        def replace(*args):
            self.store.current = False
            return self.rows

        self.snapshot.side_effect = replace
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.world.sent, [])

    def test_loading_and_offscreen_hero_do_not_publish_or_query(self):
        self.assertFalse(self.refresh(ready=False))
        self.snapshot.assert_not_called()
        self.assertTrue(self.refresh())
        self.cards.changed(2, [3])
        self.assertFalse(self.refresh())
        self.assertEqual(self.snapshot.call_count, 1)
        self.assertEqual([call[0] for call in self.world.sent], [2])

    def test_delivery_failure_retries_and_unchanged_dirty_snapshot_does_not_redraw(
        self,
    ):
        self.world.delivered = False
        self.assertFalse(self.refresh())
        self.world.delivered = True
        self.assertTrue(self.refresh())
        self.cards.changed(2, [2])
        self.assertFalse(self.refresh())
        self.assertEqual(len(self.world.sent), 2)

    def test_selected_identity_switch_refreshes_actual_selected_actor_only(self):
        self.assertTrue(self.refresh())
        self.assertTrue(self.refresh(character=3))
        self.assertEqual([call[0] for call in self.world.sent], [2, 3])
