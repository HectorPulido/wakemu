"""Fresh Rift facing follows opponents without changing existing combat state."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from wakfu_server.combat_spawn_facing import toward_nearest


class SpawnFacingTests(unittest.TestCase):
    def test_cardinal_sectors_nearest_height_tie_identity_and_empty_targets(self):
        position = (0, 0, 0)
        sectors = {
            (1, 0, 0): 1,
            (-1, 0, 0): 5,
            (0, 1, 0): 3,
            (0, -1, 0): 7,
            (4, 1, 0): 1,
            (1, 4, 0): 3,
            (-4, 1, 0): 5,
            (-1, 4, 0): 3,
            (-4, -1, 0): 5,
            (-1, -4, 0): 7,
            (4, -1, 0): 1,
            (1, -4, 0): 7,
        }
        for target, direction in sectors.items():
            with self.subTest(target=target):
                self.assertEqual(toward_nearest(position, ((1, target),)), direction)
        targets = [(1, (-10, 0, 0)), (2, (0, 2, 0))]
        before = deepcopy(targets)
        self.assertEqual(toward_nearest(position, targets), 3)
        self.assertEqual(targets, before)
        self.assertEqual(toward_nearest(position, ((2, (0, -2, 0)), (1, (2, 0, 0)))), 1)
        self.assertEqual(toward_nearest(position, ((1, (2, 0, 9)), (2, (0, -2, 1)))), 7)
        self.assertEqual(toward_nearest(position, ()), 3)
        self.assertEqual(toward_nearest(position, ((1, (0, 0, 5)),), default=5), 5)


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_ASSIGNMENT_COMPONENT") == "1",
    "Installed native publication required",
)
class RiftSpawnFacingComponentTests(unittest.TestCase):
    def fixture(self, quantity=1):
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry

        fixture = NativeRiftCarrierComponentTests()
        fixture.compiled = npc_runtime_catalog()
        fixture.registry = characteristic_registry()
        return fixture.fixture(quantity)

    def world_facing(self, payload):
        from protocol_codec import Reader

        outer = Reader(payload)
        self.assertEqual(outer.number("h"), 1)
        self.assertEqual(outer.number("B"), 1)
        identity = outer.number("q")
        reader = Reader(outer.take(outer.number("H")))
        outer.finish()
        self.assertEqual(reader.number("B"), 11)
        self.assertEqual(reader.number("q"), identity)
        reader.number("B")
        reader.number("q")
        reader.text("H")
        reader.number("h")
        for kind in ("i", "i", "h", "q"):
            reader.number(kind)
        return identity, reader.number("B")

    def test_initial_rift_bootstrap_faces_player_and_ordinary_default_is_preserved(
        self,
    ):
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_wire import arena, decode_bootstrap
        from wakfu_server.monsters import owned_instance
        from wakfu_server.rift_encounter_roles import roles_for_catalog

        component = self.fixture()
        character = deepcopy(component.characters[7])
        character.update(x=0, y=0, z=0)
        positions = ((2, 0, 0), (0, 2, 0), (-2, 0, 0), (0, -2, 0))
        sources = [
            owned_instance(
                5525,
                1,
                -200 - index,
                map_id=1134,
                instance_id=1,
                x=position[0],
                y=position[1],
                z=position[2],
            )
            for index, position in enumerate(positions)
        ]
        roles = roles_for_catalog(
            component.fight.rift_wave_state["catalog"],
            component.fight.rift_wave_state["policy"],
            monster_references=(5525,) * 4,
        )
        cells = {(x, y, 0) for x in range(-3, 4) for y in range(-3, 4)}
        edges = {
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        }
        placement = roles.placement_cells(((0, 0, 0),), positions)
        terrain = arena(1134, 1, sorted(cells), placement)
        terrain.update(
            validated_cells=cells,
            valid_edges=edges,
            placement_cells=placement,
            native_encounter_roles=roles.record(),
        )
        before = deepcopy(sources)
        fight, packets = create_placement(
            character,
            sources,
            terrain,
            fight_id=9001,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=10000,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        bootstrap = decode_bootstrap(
            next(body for opcode, body in packets if opcode == 12847)
        )
        wire = {row["actor_id"]: row["myE"] for row in bootstrap["participants"]}
        for source, direction in zip(sources, (5, 7, 1, 3)):
            actor = fight.actors[source["id"]]
            self.assertEqual(actor.direction, direction)
            self.assertEqual(wire[actor.id][19], direction)
            self.assertEqual(
                (actor.hp, actor.ap, actor.mp),
                (source["hp"], source["ap"], source["mp"]),
            )
        self.assertEqual(sources, before)
        ordinary = deepcopy(terrain)
        ordinary.pop("native_encounter_roles")
        ordinary.pop("placement_cells")
        ordinary_fight, _ = create_placement(
            character,
            sources,
            ordinary,
            fight_id=9002,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=10000,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        self.assertTrue(
            all(
                ordinary_fight.actors[source["id"]].direction == 3 for source in sources
            )
        )
        self.assertEqual(ordinary_fight.actors[7].direction, fight.actors[7].direction)

    def test_reinforcements_face_nearest_living_opponent_in_both_wires_and_replay(self):
        from wakfu_server import rift_npc_creation
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_multiplayer_wire import decode_added
        from wakfu_server.fight_checkpoint_store import snapshot

        component = self.fixture(3)
        fight = component.fight
        move_registered_actor(fight, fight.actors[8], (0, 5, 0))
        move_registered_actor(fight, fight.actors[9], (3, 5, 0))
        set_hp_raw_current(fight.actors[9], 0)
        self.assertTrue(fight._in_play(fight.actors[9]))
        fight.actors[7].direction = 5
        fight.actors[8].direction = 1
        for identity in (-200, -201):
            fight.apply_effect_damage(7, identity, fight.actors[identity].hp)
        fight.rift_wave_state["policy"]["ultimate_wave_size"] = 4
        positions = ((2, 5, 0), (-2, 5, 0), (0, 7, 0), (0, 3, 0))
        expected = dict(zip(range(-202, -206, -1), (5, 1, 7, 3)))
        sources = [
            owned_instance(
                5525,
                1,
                -202 - index,
                map_id=1134,
                instance_id=1,
                x=position[0],
                y=position[1],
                z=position[2],
            )
            for index, position in enumerate(positions)
        ]
        fight.rift_monsters.update({source["id"]: source for source in sources})
        before = {
            uid: (a.direction, a.hp, a.ap, a.mp) for uid, a in fight.actors.items()
        }
        initialize = rift_npc_creation.initialize_native_wave_actors
        observed = {}

        def observe(current, monsters):
            observed.update(
                {
                    source["id"]: current.actors[source["id"]].direction
                    for source in monsters
                }
            )
            return initialize(current, monsters)

        with patch.object(
            rift_npc_creation, "initialize_native_wave_actors", side_effect=observe
        ), patch("time.time_ns", return_value=1800000000000000000):
            packets = rift_npc_creation.install_native_wave(
                fight, sources, initialize_actor=lambda *args: ()
            )
        self.assertEqual(observed, expected)
        self.assertEqual(
            {
                uid: (a.direction, a.hp, a.ap, a.mp)
                for uid, a in fight.actors.items()
                if uid in before
            },
            before,
        )
        for index, source in enumerate(sources):
            actor = fight.actors[source["id"]]
            appearance, admission = packets[index * 2 : index * 2 + 2]
            self.assertEqual((appearance[0], admission[0]), (12608, 13091))
            self.assertEqual(
                self.world_facing(appearance[1]), (actor.id, expected[actor.id])
            )
            self.assertEqual(
                decode_added(admission[1])["stats"][19], expected[actor.id]
            )
            self.assertEqual((actor.ap, actor.mp), (source["ap"], source["mp"]))
            self.assertTrue(actor.native_controlled_by_ai)
        committed = snapshot(fight)
        with patch("time.time_ns", return_value=1800000000000000000):
            for index, source in enumerate(sources):
                actor = fight.actors[source["id"]]
                replay = rift_npc_creation.creation_packets(
                    source,
                    fight.id,
                    obstacle_id=actor.native_obstacle_id,
                    group_id=fight.rift_wave_state["world_group_id"],
                    actor=actor,
                    fight=fight,
                )
                self.assertEqual(replay, tuple(packets[index * 2 : index * 2 + 2]))
        self.assertEqual(snapshot(fight), committed)
