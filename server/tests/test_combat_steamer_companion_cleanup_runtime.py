"""Mechanical companion retirement follows the real owner's start event."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerCompanionCleanupRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_owner_start_retires_actual_companion_without_removing_other_actors(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_kill import NativeKillHandler

        data = self.fixture((6931,), actives=(6912,))
        created = self.cast(data, 6912)
        data = self.adopt(data, created.fight)
        companions = {
            a.id
            for a in data[2].actors.values()
            if any(s.reference == 6288 for s in a.state_ledger.entries)
        }
        self.assertTrue(companions)
        self.assertTrue(all(data[2].actors[uid].hp > 0 for uid in companions))
        survivors = {
            uid
            for uid, actor in data[2].actors.items()
            if uid not in companions and actor.hp > 0
        }
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (344217, 344218):
                trace.append((invocation.reference, invocation.target_id, result))
            return result

        kills = []
        kill = NativeKillHandler.__call__

        def observe_kill(handler, effect, values, invocation):
            result = kill(handler, effect, values, invocation)
            if invocation.reference == 344218:
                kills.append((invocation.target_id, result))
            return result

        with patch.object(EffectDispatcher, "execute", observe), patch.object(
            NativeKillHandler, "__call__", observe_kill
        ):
            final = self.next_owned_turn(data)[2]
        # The dispatcher entry is the carrier owner; the native selector
        # resolves real companion recipients before invoking the handler.
        self.assertTrue(
            any(target in companions and ok for target, ok in kills),
            dict(trace=trace, kills=kills),
        )
        self.assertTrue(
            all(
                uid not in final.actors or final.actors[uid].hp == 0
                for uid in companions
            ),
            trace,
        )
        self.assertTrue(
            all(uid in final.actors and final.actors[uid].hp > 0 for uid in survivors),
            trace,
        )
