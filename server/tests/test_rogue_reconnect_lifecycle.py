"""Actual Rogue constructor receipts survive checkpoint and owned presentation."""
import json
import os
import struct
import unittest
from types import SimpleNamespace

import test_rogue_runtime_pipeline as pipeline
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_shared import Session
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueReconnectLifecycleTests(unittest.TestCase):
    fixture = pipeline.RogueRuntimePipelineTests.fixture
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def test_real_bomb_and_robot_reconnect_replays_receipts_without_gameplay(self):
        data = self.fixture()
        data, _ = self.cast(data, 7906)
        data, tx = self.cast(data, 7905, (-8, -8, -1), action_id=11)
        fight = data[2]
        creatures = self.summons(fight, (3795, 3796, 3797, 1236))
        self.assertEqual(len(creatures), 2)
        before = snapshot(fight)
        checkpoint = json.loads(json.dumps(before, allow_nan=False))
        for creature in creatures:
            saved = checkpoint["actors"][str(creature.id)]
            self.assertEqual(saved["position"], list(creature.position))
            self.assertEqual(saved["hp"], creature.hp)
            self.assertEqual(saved["native_summon_source"]["controller_id"], 7)
        arena = local_arena(1134, 7, (-8, -7, -1), (-5, -7, -1), variation_seed=17)
        runtime = SimpleNamespace(
            turn_deadline=None, native_action_id=20, awaiting_ack=None
        )
        shared = SimpleNamespace(
            fight=fight,
            map_id=1134,
            runtime=runtime,
            join_context={
                "arena": arena,
                "terrain_effect_id": 46,
                "terrain_instance_id": -300,
                "leaders": {0: 7, 1: -7},
            },
            ack=None,
        )

        # This isolates constructor replay/current-value overlays. Detailed PA
        # codec parity is covered by the shared summon/reconnect tests.
        def actor_payload(current_fight, actor, session):
            return struct.pack(">iii", actor.hp, actor.ap, actor.mp), b"effects"

        packets = owned_snapshot(
            fight,
            shared,
            Session(3, 7, "reconnect", 1134, 0),
            actor_payload=actor_payload,
        )
        self.assertEqual(snapshot(fight), before)
        for creature in creatures:
            receipt = fight.native_summon_creation_deliveries[creature.id]
            self.assertEqual(
                packets.count(
                    (receipt["opcode"], bytes.fromhex(receipt["payload_hex"]))
                ),
                1,
            )
        self.assertEqual(sum(opcode == 12847 for opcode, _ in packets), 1)
        self.assertEqual(sum(opcode == 12053 for opcode, _ in packets), 1)
