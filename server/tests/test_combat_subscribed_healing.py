"""Source-qualified eXs deferred registration and same-UID applied retention."""
import json
import unittest
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import test_combat_healing_handler as fixtures
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_subscription_runners import deferred_payload


class SubscribedHealingTests(unittest.TestCase):
    def test_real_definition_registers_without_healing_then_applies_and_removes_without_reversal(
        self,
    ):
        base = Path(__file__).parent / "fixtures"
        effect = json.loads(
            (base / "native_subscribed_healing340227_effect.json").read_text()
        )["row"]
        metadata = json.loads(
            (base / "native_subscribed_healing340227_metadata.json").read_text()
        )["row"]
        fixture = fixtures.HealingHandlerTests()
        fixture.setUp()
        fight, packets, handler = fixture.fight, fixture.packets, fixture.handler
        # Explicit test-owned fresh UID producer, as in native event fixtures.
        fight.native_effect_uid_next = 900
        invocation = replace(fixture.invocation, reference=340227)
        timer = StateTimer(-7, -1, "end")
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=SimpleNamespace(
                stat=lambda *args: StatExecutionContext(
                    True, True, None, True, native_time_payload(timer), timer
                )
            ),
            metadata={"states": {}, "spells": {}, "effects": {"340227": metadata}},
        )
        handler.retention = retention
        wrapped = retention.wrap(handler)
        dispatcher = EffectDispatcher(
            {"340227": effect},
            {25: wrapped},
            resolve=lambda effect, inv: (inv,),
            condition_context=lambda *args: self.fail(
                "Fresh subscription must defer criteria"
            ),
            probability_accepts=lambda *args: self.fail(
                "Fresh subscription must defer RNG"
            ),
            group_cells=lambda *args: (),
            actor_position=lambda identity: fight.actors[identity].position,
            group_retention=retention,
        )
        before = fight.actors[-7].hp
        self.assertTrue(dispatcher.execute(invocation))
        self.assertEqual(fight.actors[-7].hp, before)
        self.assertFalse(handler.prepared)
        registered = next(iter(fight.native_owned_group_effects.values()))
        fields = _identity_fields(bytes.fromhex(registered["payload"]))
        self.assertEqual(fields[4], 0)
        # eXs has no subclass b(iP): fresh wire equals audited inherited eZR.
        args = dict(
            uid=901,
            base_uid=800,
            generic_effect=340227,
            caster_id=7,
            target_id=-7,
            cell=(1, 0, 0),
            timing_payload=native_time_payload(timer),
            container_type=None,
            container_id=None,
        )
        self.assertEqual(
            deferred_payload(family=25, **args), deferred_payload(family=421, **args)
        )
        # A selected event's clone invokes the real healing handler; own its
        # actual UID and applied value, preserving the original listener.
        activation = replace(invocation, native_running_uid=None)
        self.assertTrue(wrapped(effect, {}, activation))
        self.assertGreater(fight.actors[-7].hp, before)
        applied = fight.native_owned_group_effects[99]
        self.assertGreater(_identity_fields(bytes.fromhex(applied["payload"]))[4], 0)
        from wakfu_server.wire import proto_fields

        wire = {
            tag >> 3: value
            for tag, value in proto_fields(bytes.fromhex(applied["payload"]))
        }
        timing = {tag >> 3: value for tag, value in proto_fields(wire[11])}
        self.assertEqual((timing[2], timing[5]), (0, 1))
        self.assertEqual(_identity_fields(packets[-1][1][19:])[1], 99)
        self.assertEqual(
            _identity_fields(packets[-1][1][19:])[4],
            _identity_fields(bytes.fromhex(applied["payload"]))[4],
        )
        after = fight.actors[-7].hp
        retention.stat_handler = SimpleNamespace(fight=fight)
        retention.removal(retention.view()).remove([99])
        self.assertEqual(fight.actors[-7].hp, after)
        self.assertNotIn(99, fight.native_retained_records)
        self.assertEqual(packets[-1][0], 13560)


if __name__ == "__main__":
    unittest.main()
