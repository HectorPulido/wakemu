"""Real native group374328 retains the detached constructor no-clock sentinel."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat.combat_state import Actor
from wakfu_server.combat.combat_summon_creation import native_fresh_summon_authority
from wakfu_server.combat.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat.combat_native_timing_context import (
    NativeEffectTimingProvider,
    native_time_payload,
)


class ConstructorCellGroupClockTests(unittest.TestCase):
    def setUp(self):
        self.effect = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "native_constructor_cell_group374328.json"
            ).read_text()
        )
        self.actor = Actor(-3, 1, (0, 0, 0), 10, 6, 3, 1, 143)
        self.fight = SimpleNamespace(actors={}, phase="placement", current=None)
        self.authority = native_fresh_summon_authority(self.actor, 5471)
        self.actor.team = -1
        self.invocation = SimpleNamespace(
            caster_id=-3,
            target_id=None,
            level=1,
            state_uid=None,
            native_target_cell_argument=True,
        )
        self.provider = NativeEffectTimingProvider({})

    def test_actual_finite_native_cell_group_retains_without_invented_clock(self):
        self.assertEqual(self.effect["native_timing_definition"]["ryE"], 1)
        with detached_summon_scope(self.fight, self.actor, self.authority):
            context = self.provider.stat(self.fight, {}, self.effect, self.invocation)
        self.assertTrue(context.retained)
        self.assertIsNone(context.timer)
        self.assertEqual(context.timing_payload, native_time_payload())
        self.assertIsNone(self.fight.current)
        self.assertEqual(self.fight.actors, {})

    def test_nondetached_null_target_still_requires_actual_turn(self):
        with self.assertRaisesRegex(ValueError, "active actor turn"):
            self.provider.stat(self.fight, {}, self.effect, self.invocation)

    def test_unknown_or_unverified_cell_target_still_requires_actual_turn(self):
        with detached_summon_scope(self.fight, self.actor, self.authority):
            for family, cell_flag in ((1, True), (330, False), (330, 1)):
                with self.subTest(family=family, cell_flag=cell_flag):
                    effect = dict(self.effect, effect_class=family)
                    self.invocation.native_target_cell_argument = cell_flag
                    with self.assertRaisesRegex(ValueError, "active actor turn"):
                        self.provider.stat(self.fight, {}, effect, self.invocation)


if __name__ == "__main__":
    unittest.main()
