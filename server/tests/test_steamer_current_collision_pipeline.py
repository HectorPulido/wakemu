"""Corriente's paid native area hit may kill the rear collision participant."""
from random import Random
import struct
import unittest
from unittest.mock import patch


class SteamerCurrentCollisionPipelineTests(unittest.TestCase):
    def test_paid_current_kills_rear_then_push_collision_keeps_native_guard(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import (
            build_npc_snapshot,
            native_npc_creation_values,
        )
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_carrying import _publish_registry
        from wakfu_server.combat_global_pv_collections import register_global_fighter
        from wakfu_server.combat_timeline_snapshot import insert
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.spells import encode_deck

        character, front_source, fight = SpellTransactionTests().native_server_fixture(
            16,
            200,
            native_qi=True,
            target_hp=2000,
            target_distance=3,
            variation_seed=17,
        )
        front = fight.actors[-7]
        rear_cell = (front.position[0] + 1, front.position[1], front.position[2])
        self.assertIn(rear_cell, fight.walkable)
        values = native_npc_creation_values(5525, 1)
        # A controlled wounded source, not a claim about natural breed HP.
        rear = Actor(
            -8,
            1,
            rear_cell,
            2,
            values[2]["current"],
            values[3]["current"],
            5,
            1,
            max_hp=values[1]["maximum"],
            direction=3,
        )
        rear_source = dict(id=-8, ref=5525, level=1, map_id=1134)
        build_npc_snapshot(
            rear_source,
            rear,
            wp_current=0,
            wp_maximum=0,
            running_effects=(),
        ).install(rear)
        registry = current_registry(fight)
        rear.native_obstacle_id = registry.register(
            dict(
                identity=["actor", rear.id],
                position=list(rear.position[:2]),
                radius=rear.physical_radius,
                indexed=True,
                movement_blocking=True,
            )
        )
        self.assertGreaterEqual(rear.native_obstacle_id, 0)
        fight.actors[rear.id] = rear
        register_global_fighter(fight, rear.id)
        _publish_registry(fight, registry)
        insert(fight, rear.id, len(fight.order))
        fight.order.append(rear.id)

        monsters = {-7: front_source, -8: rear_source}
        deck, rng = encode_deck((6907,)), Random(17)
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        before = source_snapshot(fight)
        ap_before = fight.actors[7].ap
        from wakfu_server.combat_collision_resource import (
            NativeCollisionResourceExecutor,
        )
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        collision_attempts = []
        execute_collision = NativeCollisionResourceExecutor.__call__

        def observe_collision(executor, caster_id, recipient_id):
            recipient = executor.handler.fight.actors[recipient_id]
            collision_attempts.append(
                (
                    recipient_id,
                    recipient.hp,
                    global_fighter_guards(executor.handler.fight, recipient_id),
                )
            )
            return execute_collision(executor, caster_id, recipient_id)

        with patch.object(
            NativeCollisionResourceExecutor, "__call__", observe_collision
        ):
            tx = prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 6907, *front.position),
                character,
                monsters,
                fight,
                3,
                deck,
                action_id=2,
                line_of_sight=lambda source, target, preview: authoritative_visible(
                    1134,
                    source,
                    target,
                    preview,
                ),
                critical=False,
                rng=rng,
            )
        self.assertEqual(source_snapshot(fight), before)
        self.assertEqual(tx.fight.actors[-8].hp, 0)
        self.assertTrue(
            any(
                identity == -8 and hp == 0 and not guards["baF"]
                for identity, hp, guards in collision_attempts
            ),
            collision_attempts,
        )
        self.assertGreater(tx.fight.actors[-7].hp, 0)
        self.assertLess(tx.fight.actors[-7].hp, front.hp)
        self.assertEqual(tx.fight.actors[7].ap, ap_before - tx.plan["costs"]["ap"])
        self.assertTrue(any(tx.outcomes))
        self.assertTrue(any(opcode == 12613 for opcode, _ in tx.packets))


if __name__ == "__main__":
    unittest.main()
