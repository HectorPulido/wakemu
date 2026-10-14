import unittest
from types import SimpleNamespace as NS
from wakfu_server.combat_native_timing_context import (
    native_time_payload,
    native_state_timeline,
    NativeEffectTimingProvider,
    native_definition_timing,
)
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server import native_catalog


class NativeTimingTests(unittest.TestCase):
    def test_real_applicator_and_damage_native_clock_fields(self):
        import json
        from wakfu_server.paths import DATA_ROOT

        catalog = json.loads(
            native_catalog.read_text(DATA_ROOT / "spell-effect-trees.json")
        )
        for reference in ("167716", "339526"):
            effect = catalog["effects"][reference]
            for level in (0, 1, 200, 32767):
                self.assertEqual(
                    native_definition_timing(effect, level),
                    {"retained": False, "delay": False, "duration": 0},
                )
                check = effect["native_timing_checks"][str(level)]
                self.assertEqual(check["duration"], [0, False, 1, False])
                self.assertEqual(check["delay"], [0, False, 0, False])
        effect = dict(catalog["effects"]["167716"])
        effect["native_timing_definition"] = dict(
            effect["native_timing_definition"], ryH=1
        )
        with self.assertRaisesRegex(ValueError, "Delayed"):
            native_definition_timing(effect, 1)

    def test_native_qh_sentinel_and_absolute_end_clock(self):
        self.assertEqual(
            native_time_payload().hex(),
            "080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800",
        )
        self.assertEqual(
            native_time_payload(StateTimer(22, 3, "end"), realtime_remaining=0).hex(),
            "080010ffffffffffffffffff011a0608161003180120002800",
        )

    def test_real_state_context_uses_state_profile_clock_and_carrier_defaults(self):
        import json
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_state_ledger import StateLedger

        catalog = json.loads(
            native_catalog.read_bytes(DATA_ROOT / "combat-state-definitions.json")
        )
        with native_catalog.open(DATA_ROOT / "spell-effect-trees.json") as f:
            effect = json.load(f)["effects"]["167716"]
        first = NS(id=11, turn_count=2, hp=100, state_ledger=StateLedger(11))
        second = NS(id=22, turn_count=1, hp=100, state_ledger=StateLedger(22))
        fight = NS(
            phase="active",
            current=first,
            actors={11: first, 22: second},
            order=[11, 22],
            turn_index=0,
        )
        invocation = NS(level=1, caster_id=11, target_id=22, base_uid=9)
        context = NativeEffectTimingProvider(catalog).state(
            fight, None, effect, invocation
        )
        self.assertEqual(context.native_turn_clock, -1)
        self.assertEqual(context.parent_uid, 9)
        self.assertFalse(context.applying_effect_has_delay)
        self.assertFalse(context.flag17)
        self.assertFalse(context.flag18)
        self.assertIsInstance(context.timing_payload, bytes)

    def test_current_actor_round_not_global_turn_number(self):
        first = NS(id=11, turn_count=3, hp=100)
        second = NS(id=22, turn_count=2, hp=100)
        fight = NS(
            phase="active",
            current=first,
            actors={11: first, 22: second},
            order=[11, 22],
            turn_index=0,
            turn_id=5,
        )
        clock = native_state_timeline(fight, 22)
        self.assertEqual((clock.round_number, clock.clock_actor_index), (3, 1))
        fight.actors[33] = NS(id=33, turn_count=1, hp=0)
        self.assertEqual(native_state_timeline(fight, 22), clock)
        with self.assertRaises(ValueError):
            native_state_timeline(fight, 33)
        fight.order = [11]
        with self.assertRaises(ValueError):
            native_state_timeline(fight, 22)

    def off_play_clock_fixture(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        first = Actor(11, 0, (0, 0, 0), 100, 6, 3, 30, 1, 3, True)
        clock = Actor(22, 1, (1, 0, 0), 100, 6, 3, 20, 1)
        survivor = Actor(33, 1, (2, 0, 0), 100, 6, 3, 10, 1)
        fight = Fight(
            77,
            [first, clock, survivor],
            {first.position, clock.position, survivor.position},
            {0: {first.position}, 1: {clock.position, survivor.position}},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.ready(3)
        return fight

    def test_actual_registered_off_play_clock_uses_native_absent_index(self):
        fight = self.off_play_clock_fixture()
        fight.apply_effect_damage(11, 22, 100)
        self.assertEqual(fight.phase, "active")
        self.assertNotIn(22, fight.order)
        timeline = native_state_timeline(fight, 22)
        self.assertEqual(timeline.clock_actor_index, -1)
        self.assertEqual(timeline.current_actor_id, fight.current.id)
        self.assertEqual(timeline.current_actor_index, fight.turn_index)

    def test_unattested_zero_hp_and_forged_off_play_clock_still_reject(self):
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        fight = self.off_play_clock_fixture()
        fight.actors[22].hp = 0
        fight.order.remove(22)
        with self.assertRaisesRegex(ValueError, "Missing state clock actor"):
            native_state_timeline(fight, 22)
        set_global_fighter_status(fight, 22, "OFF_PLAY")
        with self.assertRaisesRegex(ValueError, "corpse registration"):
            native_state_timeline(fight, 22)
        with self.assertRaisesRegex(ValueError, "Missing state clock actor"):
            native_state_timeline(fight, 999)

    def test_mode_zero_owned_stat_without_timer_and_unknown_rejected(self):
        provider = NativeEffectTimingProvider({})
        context = provider.stat(
            NS(), None, {"native_execution_mode": 0}, NS(state_uid=0, level=1)
        )
        self.assertTrue(context.retained)
        self.assertEqual(context.timing_payload, native_time_payload())
        for effect in ({}, {"native_execution_mode": 1}, {"native_execution_mode": 2}):
            with self.assertRaises(ValueError):
                provider.stat(NS(), None, effect, NS(state_uid=0, level=1))
        with self.assertRaises(ValueError):
            provider.stat(
                NS(actors={}),
                None,
                {"native_execution_mode": 0},
                NS(state_uid=3, level=1),
            )
