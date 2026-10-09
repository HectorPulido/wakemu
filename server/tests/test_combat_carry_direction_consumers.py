"""Registered carry pairs survive ordinary facing, orientation and movement."""
import struct
import unittest
from types import SimpleNamespace

from test_combat_carrying import CarryingLifecycleTests
from wakfu_server.combat_carrying import carry_registered, carrying_relations
from wakfu_server.combat_cast_facing import mirror_cast_facing
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_orientation import apply as orient
from wakfu_server.combat_orientation_effect import NativeOrientationHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_qi_fight import current_registry


class CarryDirectionConsumerTests(unittest.TestCase):
    def fixture(self):
        fight, carrier, carried = CarryingLifecycleTests().fixture()
        carrier.direction, carried.direction = 7, 2
        fight.ready(1)
        carry_registered(fight, carrier, carried, source_uid=1)
        return fight, carrier, carried

    def assert_pair(self, fight, carrier, carried, directions):
        self.assertEqual((carrier.direction, carried.direction), directions)
        self.assertTrue(carrying_relations(fight, carried)["is_carried"])
        self.assertFalse(
            current_registry(fight).slots[carried.native_obstacle_id]["indexed"]
        )

    def test_cast_facing_rotates_carried_once_and_rejects_detached_actor(self):
        fight, carrier, carried = self.fixture()
        plan = {"spell_id": 1, "target": (2, 0, 0)}
        contracts = {
            "1": {
                "status": "verified",
                "turnCasterTowardTargetCell": True,
                "useDiags": False,
            }
        }
        self.assertTrue(
            mirror_cast_facing(carrier, plan, fight=fight, contracts=contracts)
        )
        self.assert_pair(fight, carrier, carried, (1, 4))
        with self.assertRaisesRegex(ValueError, "actual registered"):
            mirror_cast_facing(
                SimpleNamespace(id=7, position=(0, 0, 0)),
                plan,
                fight=fight,
                contracts=contracts,
            )
        self.assert_pair(fight, carrier, carried, (1, 4))

    def test_owned_orientation_keeps_seal_and_does_not_spend_resources(self):
        fight, carrier, carried = self.fixture()
        before = carrier.ap, carrier.mp
        result = orient(RuntimeMessages(fight), 1, struct.pack(">qB", carrier.id, 1))
        self.assertEqual(result["packets"][0][0], 13494)
        self.assertEqual((carrier.ap, carrier.mp), before)
        self.assert_pair(fight, carrier, carried, (1, 4))

    def test_effect_orientation_on_carrier_and_carried_updates_same_pair(self):
        fight, carrier, carried = self.fixture()
        handler = NativeOrientationHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 9,
            context=lambda e, i: StatExecutionContext(True, True, None, False, None),
            authority=SimpleNamespace(property_counts=lambda f, a: {51: 0}),
            draw_mode=lambda *args: 2,
        )
        for target, expected in ((carrier.id, (1, 4)), (carried.id, (1, 1))):
            invocation = EffectInvocation(123, 1, carrier.id, target, (2, 0, 0))
            self.assertTrue(
                handler({"effect_class": 303}, {"parameters": [3]}, invocation)
            )
            self.assert_pair(fight, carrier, carried, expected)

    def test_movement_codec_failure_preserves_live_pair_then_commits_once(self):
        fight, carrier, carried = self.fixture()
        runtime = RuntimeMessages(fight)
        body = struct.pack(">qiih", carrier.id, 1, 0, 0)
        before = carrier.mp

        def fail(candidate):
            self.assertEqual((candidate.position, candidate.direction), ((1, 0, 0), 1))
            self.assertEqual(carrier.position, (0, 0, 0))
            raise ValueError("codec failure")

        with self.assertRaisesRegex(ValueError, "codec failure"):
            apply_client(runtime, 1, body, fail)
        self.assert_pair(fight, carrier, carried, (7, 2))
        self.assertEqual((carrier.mp, runtime.action_id), (before, 0))
        apply_client(runtime, 1, body, lambda a: b"owned")
        self.assertEqual((carrier.position, carried.position), ((1, 0, 0), (1, 0, 0)))
        self.assertEqual((carrier.mp, runtime.action_id), (before - 1, 1))
        self.assert_pair(fight, carrier, carried, (1, 4))
