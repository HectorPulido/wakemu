"""Real enemy Microbot entry after read-only owned reconnect replay."""
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerHotWheelsReconnectWireTests(unittest.TestCase):
    def test_actual_enemy_entry_after_reconnect_damages_once(self):
        import test_combat_steamer_microbot_enemy_runtime as scenario
        from wakfu_server import combat_area_transaction, combat_terrain
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.fight_checkpoint_store import snapshot

        original_arena = combat_terrain.local_arena
        original_move = combat_area_transaction.prepare_area_movement
        original_execute = EffectDispatcher.execute
        observed, calls = {}, []
        successes = []

        def capture_arena(*args, **kwargs):
            arena = original_arena(*args, **kwargs)
            observed["arena"] = arena
            return arena

        def observe(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference == 344433 and result:
                successes.append((invocation.caster_id, invocation.target_id))
            return result

        def reconnect_then_enter(character, monsters, fight, deck, **kwargs):
            before = snapshot(fight)
            prior_successes = len(successes)
            runtime = SimpleNamespace(
                fight=fight, turn_deadline=None, native_action_id=918, awaiting_ack=None
            )
            shared = SimpleNamespace(
                runtime=runtime,
                map_id=1134,
                join_context={
                    "arena": observed["arena"],
                    "terrain_effect_id": 99,
                    "terrain_instance_id": 0,
                    "leaders": {0: 7, 1: -7},
                },
            )
            expected = set(fight.native_retained_records)
            for _ in range(2):
                packets = owned_snapshot(
                    fight,
                    shared,
                    SimpleNamespace(account_id=3),
                    actor_payload=lambda *_: (b"", b""),
                )
                uids = []
                for opcode, body in packets:
                    if opcode != 12613:
                        continue
                    self.assertEqual(
                        struct.unpack_from(">iiiB", body), (fight.id, 918, -1, 0)
                    )
                    uids.append(_identity_fields(body[19:])[1])
                self.assertEqual(set(uids), expected)
                self.assertEqual(len(uids), len(expected))
                self.assertEqual(snapshot(fight), before)
                self.assertEqual(len(successes), prior_successes)
            hp = fight.actors[-7].hp
            result = original_move(character, monsters, fight, deck, **kwargs)
            preview = result[0]
            calls.append((hp - preview.actors[-7].hp, successes[prior_successes:]))
            return result

        with patch.object(combat_terrain, "local_arena", capture_arena), patch.object(
            combat_area_transaction, "prepare_area_movement", reconnect_then_enter
        ), patch.object(EffectDispatcher, "execute", observe):
            scenario.SteamerMicrobotEnemyRuntimeTests(
                "test_hot_wheels_observes_actual_enemy_entry_movement"
            ).test_hot_wheels_observes_actual_enemy_entry_movement()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], [])
        self.assertEqual(len(calls[1][1]), 1)
        self.assertEqual(calls[1][1][0][1], -7)
        self.assertGreater(calls[1][0], calls[0][0])
