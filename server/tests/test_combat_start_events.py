import unittest
from types import SimpleNamespace
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_start_events import deliver_fight_start


class FightStartEventsTests(unittest.TestCase):
    def fixture(self):
        actors = [Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
                  Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)]
        fight = Fight(77, actors, {a.position for a in actors},
                      {0: {(0, 0, 0)}, 1: {(1, 0, 0)}})
        fight.ready(3)
        fight.native_class_initializations = {7: {'breed': 11}}
        delivered = []
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight),
                                     native_clone_authority=object(),
                                     replay_event=lambda event, **kw: (delivered.append(event) or (True,)))
        return fight, dispatcher, delivered

    def test_ready_boundary_all_managers_once_without_source_uid(self):
        fight, dispatcher, delivered = self.fixture()
        self.assertEqual(deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7)), (True, True))
        self.assertEqual([e.manager_actor_id for e in delivered], [7, -7])
        self.assertTrue(all(e.uid is None and e.event_ids == (1003,) and e.channel == 6 for e in delivered))
        self.assertTrue(fight.native_start_event_delivered)
        with self.assertRaises(ValueError):
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))

    def test_incomplete_install_rejected_before_delivery(self):
        fight, dispatcher, delivered = self.fixture()
        fight.native_class_initializations.clear()
        with self.assertRaises(ValueError):
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))
        self.assertEqual(delivered, [])
        self.assertFalse(fight.native_start_event_delivered)

    def test_failure_does_not_commit_marker(self):
        fight, dispatcher, delivered = self.fixture()
        def fail(*args, **kwargs):
            raise RuntimeError('child failed')
        dispatcher.replay_event = fail
        with self.assertRaises(RuntimeError):
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))
        self.assertFalse(fight.native_start_event_delivered)
