import unittest
from types import SimpleNamespace
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_start_events import deliver_fight_start


class FightStartEventsTests(unittest.TestCase):
    def fixture(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        fight = Fight(
            77, actors, {a.position for a in actors}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.ready(3)
        fight.native_class_initializations = {7: {"breed": 11}}
        delivered = []
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            native_clone_authority=object(),
            replay_event=lambda event, **kw: (delivered.append(event) or (True,)),
        )
        return fight, dispatcher, delivered

    def test_ready_boundary_all_managers_once_without_source_uid(self):
        fight, dispatcher, delivered = self.fixture()
        self.assertEqual(
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7)), (True,) * 9
        )
        self.assertEqual([e.manager_actor_id for e in delivered], [7] * 6 + [-7] * 3)
        self.assertEqual(
            [e.event_ids for e in delivered], [(1028,)] * 3 + [(1003,)] * 6
        )
        self.assertTrue(
            all(e.uid is None and e.channel in (6, 60, 61) for e in delivered)
        )
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
            raise RuntimeError("child failed")

        dispatcher.replay_event = fail
        with self.assertRaises(RuntimeError):
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))
        self.assertFalse(fight.native_start_event_delivered)

    def test_native_subscription_routes_are_disjoint(self):
        from wakfu_server.combat_native_events import subscription_selection

        for global_subscription, reversed_subscription, expected in (
            (False, False, 6),
            (False, True, 60),
            (True, False, 61),
        ):
            accepted = [
                channel
                for channel in (6, 60, 61)
                if subscription_selection(
                    masks=[None] * 5 + [[1003], None],
                    event_ids=(1003,),
                    channel=channel,
                    global_subscription=global_subscription,
                    reversed_subscription=reversed_subscription,
                    flags=[17],
                    source_present=False,
                )
                == "activate"
            ]
            self.assertEqual(accepted, [expected])
