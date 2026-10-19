"""Fresh ordinary NPC property profiles preserve roster/timeline semantics."""
import unittest
import struct
from unittest.mock import patch

from test_combat_actor_snapshot import ActorSnapshotTests
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.monsters import owned_instance


class OrdinaryNpcPropertySnapshotTests(unittest.TestCase):
    def test_pb114_roots_keep_native_profile_targetability_but_never_take_turns(self):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        character, player = ActorSnapshotTests().player()
        monster_rows = {
            -5403: owned_instance(5403, 50, -5403, map_id=1, x=2, y=0, z=0),
            -5404: owned_instance(5404, 50, -5404, map_id=1, x=3, y=0, z=0),
            -5525: owned_instance(5525, 1, -5525, map_id=1, x=4, y=0, z=0),
        }
        actors = [player]
        for identity, monster in monster_rows.items():
            actors.append(
                Actor(
                    identity,
                    1,
                    (monster["x"], monster["y"], monster["z"]),
                    monster["hp"],
                    monster["ap"],
                    monster["mp"],
                    monster["initiative"],
                    monster["level"],
                )
            )
        fight = Fight(
            190982471,
            actors,
            {actor.position for actor in actors},
            {
                0: {player.position},
                1: {actor.position for actor in actors if actor.team == 1},
            },
        )
        fight.native_qi_snapshot = dict(x=0, y=0, width=5, height=1, cell_masks=[0] * 5)

        # Keep the actual NPC property catalog, snapshots and QI constructors,
        # while avoiding an unrelated offensive-ability catalog load.
        with patch(
            "wakfu_server.combat.combat_npc_initialization.initial_plans",
            return_value={},
        ), patch(
            "wakfu_server.combat_npc_ai_initialization.initial_ai_actors",
            return_value=frozenset(),
        ), patch(
            "wakfu_server.combat_initial_finite_clock_policy.bind_initial_finite_clocks"
        ):
            initialize_fight_snapshots(
                fight,
                characters={player.id: character},
                monsters=monster_rows,
                wp_resources={
                    player.id: (6, 6),
                    **{
                        identity: (monster["wp"], monster["wp"])
                        for identity, monster in monster_rows.items()
                    },
                },
                running_effects={identity: () for identity in fight.actors},
                initial_effect_uid=1,
            )
        with patch(
            "wakfu_server.combat_initial_finite_clock_policy.bind_initial_finite_clocks"
        ):
            fight.ready(1)

        from wakfu_server.combat_runtime_messages import RuntimeMessages

        runtime = RuntimeMessages(fight, turn_duration_ms=30_000)
        visited = []
        for _ in range(4):
            current = fight.current
            self.assertNotIn(current.id, (-5403, -5404))
            visited.append(current.id)
            old_turn = fight.turn_id
            if current.controlled:
                packets = runtime.end_turn(
                    current.owner_id, current.id, current.turn_count
                )
            else:
                packets = runtime.end_server_turn(current.id, old_turn)
            self.assertIn(12502, [opcode for opcode, _ in packets])
            self.assertEqual(runtime.awaiting_ack, old_turn)
            runtime.acknowledge_turn(struct.pack(">i", old_turn))
            self.assertNotIn(fight.current.id, (-5403, -5404))
        self.assertIn(-5525, visited)

        property_catalog = __import__(
            "wakfu_server.combat_ordinary_authority",
            fromlist=["native_property_catalog"],
        ).native_property_catalog()["npc"]
        for identity in (-5403, -5404):
            actor = fight.actors[identity]
            expected = frozenset(property_catalog[str(-identity)]["fight_properties"])
            self.assertEqual(expected, frozenset({114, 3, 11}))
            self.assertEqual(actor.native_fight_properties, expected)
            self.assertIn(identity, fight.actors)
            slot = fight.native_qi_slots[actor.native_obstacle_id]
            self.assertEqual(slot["identity"], ["actor", identity])
            self.assertNotIn(identity, fight.order)

        ordinary = fight.actors[-5525]
        self.assertNotIn(114, ordinary.native_fight_properties)
        self.assertIn(ordinary.id, fight.order)
        self.assertIn(player.id, fight.order)

        # Native property114 alone is not native CANNOT_BE_EFFECT_TARGET (42),
        # UNTARGETTABLE_BY_OTHER (21), or a summon relationship.
        target = fight.actors[-5403]
        selector = {
            "effect_class": 258,
            "area_class": "anA",
            "area_native": "empty",
            "native_target_selector": {"class": "fcE", "mask": 8},
        }
        contexts = {
            player.id: dict(is_amO=True, bEe=True, is_Qq=False),
            target.id: dict(
                is_amO=True,
                bEe=42 not in target.native_fight_properties,
                is_Qq=False,
                is_eHH=False,
            ),
        }
        self.assertEqual(
            select_native_effect_targets(
                selector,
                player,
                player.position,
                (player, target),
                native_context=contexts,
            ),
            (target,),
        )


if __name__ == "__main__":
    unittest.main()
