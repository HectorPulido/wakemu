"""Current turn, clock and settled-death semantic contracts."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_turn_events import (
    deliver_turn_start,
    deliver_turn_end,
    deliver_turn_regeneration,
)
from wakfu_server.combat_turn_boundary import (
    prepare_turn_delivery,
    execute_turn_delivery,
)
from wakfu_server.combat_expiration_boundary import prepare_expiration_order
from wakfu_server.fight_checkpoint_store import snapshot


def active_fight():
    actors = [
        Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 20, 3, True),
        Actor(-7, 1, (1, 0, 0), 30, 6, 3, 5, 1),
        Actor(-8, 1, (2, 0, 0), 30, 6, 3, 4, 1),
    ]
    fight = Fight(
        77,
        actors,
        {actor.position for actor in actors},
        {0: {actors[0].position}, 1: {actors[1].position, actors[2].position}},
    )
    fight.ready(3)
    for actor in fight.actors.values():
        actor.native_turn_suppression_bits = 0
    fight.native_start_event_delivered = True
    return fight


class LifecycleBoundaryTests(unittest.TestCase):
    def dispatcher(self, fight, seen):
        return SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            native_clone_authority=object(),
            replay_event=lambda event, **kwargs: (
                seen.append(asdict(event)) or (True,)
            ),
        )

    def turn_result(self, original):
        fight = deepcopy(original)
        seen = []
        dispatcher = self.dispatcher(fight, seen)
        result = (
            deliver_turn_start(dispatcher, actor_id=7),
            deliver_turn_end(dispatcher, actor_id=7),
            deliver_turn_regeneration(dispatcher, actor_id=7),
        )
        return snapshot(fight), seen, result

    def test_three_owned_phases_preserve_recipient_order_and_markers(self):
        original = active_fight()
        before = snapshot(original)
        shared = self.turn_result(original)
        events = shared[1]
        self.assertEqual(
            [event["event_ids"] for event in events],
            [(1001,)] * 5 + [(1002,)] * 5 + [(1037,)] * 5,
        )
        self.assertEqual(
            [(event["manager_actor_id"], event["channel"]) for event in events[:5]],
            [(7, 6), (7, 60), (7, 61), (-7, 61), (-8, 61)],
        )
        self.assertEqual(snapshot(original), before)

    def test_suppressed_phases_still_record_exactly_once_without_replay(self):
        fight = active_fight()
        fight.actors[7].native_turn_suppression_bits = 6
        seen = []
        dispatcher = self.dispatcher(fight, seen)
        deliver_turn_end(dispatcher, actor_id=7)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            deliver_turn_end(dispatcher, actor_id=7)
        self.assertEqual(seen, [])
        self.assertTrue(fight.native_turn_event_deliveries["1:7:end"]["suppressed"])

    def test_completion_marker_retains_historical_post_callback_turn_observation(self):
        fight = active_fight()
        seen = []
        dispatcher = self.dispatcher(fight, seen)

        def replay(event, **kwargs):
            seen.append(asdict(event))
            if len(seen) == 5:
                fight.turn_id += 1
            return ()

        dispatcher.replay_event = replay
        deliver_turn_end(dispatcher, actor_id=7)
        self.assertEqual(fight.native_turn_event_deliveries["1:7:end"]["turn_id"], 2)

    def test_turn_plan_is_immutable_and_stale_turn_cannot_execute(self):
        fight = active_fight()
        plan = prepare_turn_delivery(fight, actor_id=7, phase="start", event_id=1001)
        with self.assertRaises(FrozenInstanceError):
            plan.phase = "end"
        fight.turn_id += 1
        seen = []
        with self.assertRaisesRegex(ValueError, "differ"):
            execute_turn_delivery(self.dispatcher(fight, seen), plan)
        self.assertEqual(seen, [])

    def test_registered_off_play_receives_global_but_out_of_play_does_not(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )

        fight = active_fight()
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, -7, "OFF_PLAY")
        set_global_fighter_status(fight, -8, "OUT_OF_PLAY")
        shared = self.turn_result(fight)
        self.assertIn(
            (-7, 61),
            [(event["manager_actor_id"], event["channel"]) for event in shared[1]],
        )
        self.assertNotIn(
            (-8, 61),
            [(event["manager_actor_id"], event["channel"]) for event in shared[1]],
        )

    def test_expiration_order_uses_retained_application_order_and_exact_clock(self):
        fight = active_fight()
        timer = dict(actor_id=7, expiration_round=2, phase="start")
        fight.owned_stat_effects = {50: {"timer": timer, "target_id": -7}}
        fight.native_owned_group_effects = {10: {"timer": timer, "target_id": 7}}
        fight.native_retained_tracking = True
        fight.native_retained_order[:] = [50, 10]
        plan = prepare_expiration_order(
            fight, actor_id=7, round_number=2, phase="start", round_cleanup=False
        )
        self.assertEqual(plan.entries, ((50, "stat", -7), (10, "group", 7)))
        self.assertEqual(
            prepare_expiration_order(
                fight, actor_id=-7, round_number=2, phase="start", round_cleanup=False
            ).entries,
            (),
        )
        self.assertEqual(
            prepare_expiration_order(
                fight, actor_id=-7, round_number=3, phase="end", round_cleanup=True
            ).entries,
            plan.entries,
        )
        with self.assertRaises(FrozenInstanceError):
            plan.entries = ()

    def death_result(self, original, *, damage_target):
        before = snapshot(original)
        fight = deepcopy(original)
        self.assertIsNot(fight.actors[7], original.actors[7])
        fight.apply_effect_damage(7, damage_target, fight.actors[damage_target].hp)
        self.assertEqual(snapshot(original), before)
        return snapshot(fight)

    def test_settled_death_preserves_surviving_timeline_and_defers_victory(self):
        fight = active_fight()
        shared = self.death_result(fight, damage_target=-7)
        self.assertEqual(shared["phase"], "active")

    def test_last_enemy_death_and_nested_resurrection_preserve_native_state(self):
        original = active_fight()
        fight = deepcopy(original)
        fight.apply_effect_damage(7, -7, 30)
        fight.apply_effect_damage(7, -8, 30)
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, 0)
        fight = deepcopy(original)
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 30)
            fight.actors[-7].hp = 1  # Explicit reaction input before settlement.
        self.assertIn(-7, fight.order)
        self.assertEqual(fight.phase, "active")

    def test_current_actor_death_advances_original_order_and_begins_successor_once(
        self,
    ):
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 20, 3, True),
            Actor(8, 0, (0, 1, 0), 30, 6, 3, 8, 20),
            Actor(-7, 1, (1, 0, 0), 30, 6, 3, 5, 1),
        ]
        original = Fight(
            77,
            actors,
            {actor.position for actor in actors},
            {0: {actors[0].position, actors[1].position}, 1: {actors[2].position}},
        )
        original.ready(3)
        successor = original.order[(original.order.index(7) + 1) % len(original.order)]
        fight = deepcopy(original)
        fight.apply_effect_damage(7, 7, 60)
        self.assertEqual(fight.current.id, successor)
        self.assertEqual(fight.turn_id, original.turn_id + 1)
        self.assertEqual(
            len(
                [event for event in fight.events if event.get("kind") == "turn_started"]
            ),
            2,
        )


class NativeLifecycleExpirationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_combat_timed_expiration as native_fixture

        native_fixture.TimedExpirationTests.setUpClass()
        cls.fixture_type = native_fixture.TimedExpirationTests

    def test_actual_native_expiration_preserves_payloads_events_and_original(self):
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration

        fixture = self.fixture_type()
        original, _ = fixture.make_stat()
        before = snapshot(original)
        preview, packets = prepare_timed_expiration(
            original,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry=fixture.registry,
        )
        self.assertEqual(preview.actors[-7].effect_stats[27], 80)
        self.assertEqual(preview.owned_stat_effects, {})
        self.assertEqual(packets[0][0], 13560)
        self.assertEqual(snapshot(original), before)

    def test_invalid_timer_discards_preview_without_adoption(self):
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration

        fixture = self.fixture_type()
        original, _ = fixture.make_stat()
        original.owned_stat_effects[200]["timer"]["actor_id"] = 9999
        before = snapshot(original)
        with self.assertRaisesRegex(ValueError, "timer"):
            prepare_timed_expiration(
                original,
                actor_id=7,
                round_number=2,
                phase="start",
                action_id=2,
                registry=fixture.registry,
            )
        self.assertEqual(snapshot(original), before)

    def test_state_child_expiration_preserves_owned_state_and_stats(self):
        import test_combat_state_child_removal as child_fixture
        from wakfu_server.combat_state_timing import StateTimer
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration

        fixture = child_fixture.StateChildRemovalTests()
        fixture.setUp()
        fixture.apply()
        original = fixture.fight
        entry = original.actors[7].state_ledger.entries[0]
        original.actors[7].state_ledger._entries = (
            replace(entry, timer=StateTimer(7, 2, "start")),
        )
        before = snapshot(original)
        preview, packets = prepare_timed_expiration(
            original,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry=self.fixture_type.registry,
        )
        self.assertEqual(preview.actors[7].state_ledger.entries, ())
        self.assertEqual(preview.actors[7].effect_stats[20], 80)
        self.assertEqual(snapshot(original), before)
        self.assertIsNot(preview.actors[7], original.actors[7])
