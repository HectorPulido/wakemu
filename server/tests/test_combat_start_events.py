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
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7)), (True,) * 12
        )
        self.assertEqual(
            [e.manager_actor_id for e in delivered],
            [7] * 3 + [-7] * 3 + [7] * 3 + [-7] * 3,
        )
        self.assertEqual(
            [e.event_ids for e in delivered], [(1028,)] * 6 + [(1003,)] * 6
        )
        self.assertTrue(
            all(e.uid is None and e.channel in (6, 60, 61) for e in delivered)
        )
        self.assertTrue(fight.native_start_event_delivered)
        with self.assertRaises(ValueError):
            deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))

    def test_all_initial_callbacks_observe_existing_native_first_round(self):
        fight, dispatcher, delivered = self.fixture()
        observed = []
        original = dispatcher.replay_event

        def observe(event, **kwargs):
            observed.append((fight.native_table_turn, fight.native_timeline_round))
            return original(event, **kwargs)

        dispatcher.replay_event = observe
        self.assertEqual(fight.native_table_turn, 0)
        deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))
        self.assertEqual(observed, [(1, 1)] * 12)

    def test_invalid_native_round_rejects_without_counter_or_event_mutation(self):
        for native_round, table_turn in (
            (0, 0),
            (2, 0),
            (True, 0),
            (1, -1),
            (1, 2),
            (1, 32768),
            (1, True),
            (1, None),
        ):
            with self.subTest(native_round=native_round, table_turn=table_turn):
                fight, dispatcher, delivered = self.fixture()
                fight.native_timeline_round = native_round
                fight.native_table_turn = table_turn
                with self.assertRaisesRegex(ValueError, "native first-round counter"):
                    deliver_fight_start(dispatcher, initialized_actor_ids=(7, -7))
                self.assertEqual(delivered, [])
                self.assertIs(fight.native_table_turn, table_turn)
                self.assertFalse(fight.native_start_event_delivered)

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
