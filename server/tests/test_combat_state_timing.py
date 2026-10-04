import unittest
from wakfu_server.combat_state_timing import StateTimingDefinition, schedule_state_timer


class NativeStateTimingTests(unittest.TestCase):
    def schedule(self, definition, **overrides):
        args = dict(
            level=1,
            caster_id=10,
            target_id=20,
            round_number=3,
            current_actor_id=10,
            current_actor_index=0,
            clock_actor_index=0,
            current_phase="active",
        )
        args.update(overrides)
        return schedule_state_timer(definition, **args)

    def definition(self, *, end=False, caster=True, duration=1, skip=False):
        return StateTimingDefinition(duration, 0, 230, end, caster, skip)

    def test_self_active_turn_start_and_end(self):
        start = self.schedule(self.definition())
        end = self.schedule(self.definition(end=True))
        self.assertEqual(
            (start.actor_id, start.expiration_round, start.phase), (10, 4, "start")
        )
        self.assertEqual(
            (end.actor_id, end.expiration_round, end.phase), (10, 3, "end")
        )

    def test_other_actor_turn_before_and_after_clock_actor(self):
        definition = self.definition(caster=False)
        before = self.schedule(definition, clock_actor_index=1)
        after = self.schedule(definition, current_actor_index=1, clock_actor_index=0)
        self.assertEqual(before.expiration_round, 4)
        self.assertEqual(after.expiration_round, 5)
        self.assertEqual(after.actor_id, 20)
        end = self.schedule(
            self.definition(end=True, caster=False),
            current_actor_index=1,
            clock_actor_index=0,
        )
        self.assertEqual(end.expiration_round, 4)

    def test_beginning_and_ending_are_not_active_turn(self):
        for phase in ("start", "end", "between"):
            self.assertEqual(
                self.schedule(self.definition(), current_phase=phase).expiration_round,
                5,
            )

    def test_zero_negative_and_native_permanent_flag_have_no_timer(self):
        for definition in (
            self.definition(duration=0),
            self.definition(duration=-1),
            self.definition(skip=True),
        ):
            self.assertIsNone(self.schedule(definition))

    def test_level_scaling_cap_and_native_short_narrowing(self):
        definition = StateTimingDefinition(1, 2, 5, False, False)
        self.assertEqual(definition.duration(1), 3)
        self.assertEqual(definition.duration(10), 11)
        self.assertEqual(
            StateTimingDefinition(32767, 1, 2, False, False).duration(1), -32768
        )

    def test_expiration_matches_clock_exact_round_and_phase(self):
        timer = self.schedule(self.definition())
        self.assertTrue(timer.expires_on(actor_id=10, round_number=4, phase="start"))
        self.assertFalse(timer.expires_on(actor_id=20, round_number=4, phase="start"))
        self.assertFalse(timer.expires_on(actor_id=10, round_number=4, phase="end"))
        self.assertFalse(timer.expires_on(actor_id=10, round_number=5, phase="start"))
        self.assertTrue(timer.expires_at_round_cleanup(5))
        self.assertFalse(timer.expires_at_round_cleanup(4))

    def test_zero_is_transient_only_with_no_realtime_or_apply_delay(self):
        from wakfu_server.combat_state_timing import state_requires_retention

        def retains(turn=0, real=0, permanent=False, delay=False):
            return state_requires_retention(
                turn_duration=turn,
                realtime_duration=real,
                permanent_flag=permanent,
                applying_effect_has_delay=delay,
            )

        # Offline native3425@1: gtL=0, guH=0, cxj=false.
        self.assertFalse(retains())
        self.assertTrue(retains(delay=True))
        self.assertTrue(retains(real=1))
        self.assertTrue(retains(turn=-1))
        self.assertTrue(retains(real=-1))
        # cxj only selects which negative sentinel branch bbX checks.
        self.assertFalse(retains(turn=-1, permanent=True))
        self.assertFalse(retains(permanent=True))
