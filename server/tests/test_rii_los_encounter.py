import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from wakfu_server.achievements.rii_los_encounter import (
    bind,
    hit,
    move_one_rock,
    next_rock_step,
    rock_payload,
    scene_cells,
)


class LineOfSightSceneTests(unittest.TestCase):
    def test_reachable_cells_are_unique_and_avoid_occupied(self):
        origin = (0, 0, 0)
        graph = {
            (x, y, 0): [
                (nx, ny, 0)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                if -4 <= nx <= 4 and -4 <= ny <= 4
            ]
            for x in range(-4, 5)
            for y in range(-4, 5)
        }
        cells = scene_cells(graph, origin, {(1, 0, 0)}, rock_count=3)
        self.assertEqual(len(set(cells)), 4)
        self.assertNotIn(origin, cells)
        self.assertNotIn((1, 0, 0), cells)
        self.assertTrue(set(graph[origin]) - {(1, 0, 0), *cells})

    def test_insufficient_geometry_fails_without_fabricating_cells(self):
        with self.assertRaises(ValueError):
            scene_cells({(0, 0, 0): [(1, 0, 0)]}, (0, 0, 0), (), rock_count=3)

    def test_scene_requires_a_clear_native_ray(self):
        from wakfu_server.achievements.rii_los_encounter import native_scene_shot

        with patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, frozenset({(2, 0)})),),
        ):
            shot = native_scene_shot(1388, 6, 4)
            self.assertFalse(shot((0, 0, 0), (4, 0, 0), ((2, 0, 0),)))
            self.assertTrue(shot((0, 0, 0), (4, 0, 0), ((2, 1, 0),)))

    def test_reachable_shot_checks_native_ray_and_occupied_cells(self):
        from wakfu_server.achievements.rii_los_encounter import (
            has_reachable_native_shot,
        )

        owner = SimpleNamespace(
            id=7, position=(0, 0, 0), hp=100, native_los_height=6, native_obstacle_id=0
        )
        target = SimpleNamespace(id=-2, position=(0, 1, 0), hp=100, native_los_height=6)
        fight = SimpleNamespace(
            actors={7: owner, -2: target},
            rii_los_lesson_contract={"owner": 7, "target": -2},
            native_qi_visibility_ignored_slots=[],
            edges={((x, 0, 0), (x + 1, 0, 0)) for x in range(5)},
        )
        authority = lambda *_: SimpleNamespace(native_instance_id=1388)
        with patch(
            "wakfu_server.combat_casting_los.native_casting_ray", return_value=False
        ) as ray:
            self.assertFalse(has_reachable_native_shot(fight, authority))
            self.assertGreater(ray.call_count, 0)
        with patch(
            "wakfu_server.combat_casting_los.native_casting_ray", return_value=True
        ):
            self.assertTrue(has_reachable_native_shot(fight, authority))
        fight.actors[-3] = SimpleNamespace(id=-3, position=(1, 0, 0), hp=100)
        with patch(
            "wakfu_server.combat_casting_los.native_casting_ray", return_value=True
        ):
            self.assertFalse(has_reachable_native_shot(fight, authority))

    def test_initial_formation_relocates_a_rock_if_necessary(self):
        from wakfu_server.achievements.rii_los_encounter import ensure_initial_shot

        owner = SimpleNamespace(id=7, position=(0, 0, 0), hp=100)
        target = SimpleNamespace(id=-2, position=(1, 0, 0), hp=100)
        rock = SimpleNamespace(id=-3, position=(2, 0, 0), hp=100, direction=0)
        fight = SimpleNamespace(
            id=8,
            actors={7: owner, -2: target, -3: rock},
            rii_los_lesson_contract={"owner": 7, "target": -2, "rocks": [-3]},
            walkable={(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)},
            _event=Mock(),
        )
        packets = []

        def move(_fight, actor, cell):
            actor.position = cell

        with patch(
            "wakfu_server.achievements.rii_los_encounter.has_reachable_native_shot",
            side_effect=[False, True],
        ), patch(
            "wakfu_server.combat_qi_fight.move_registered_actor", side_effect=move
        ):
            self.assertTrue(ensure_initial_shot(fight, packets, action_id=4))
        self.assertEqual(rock.position, (3, 0, 0))
        self.assertEqual(packets[0][0], 13624)

    def test_rock_motion_stays_on_edges_and_avoids_every_occupied_actor(self):
        rocks = {-2: (0, 0, 0), -3: (2, 0, 0)}
        walkable = {(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0)}
        edges = {((0, 0, 0), (1, 0, 0)), ((2, 0, 0), (2, 1, 0))}
        self.assertEqual(
            next_rock_step(
                rocks, walkable, edges, {(0, 0, 0), (1, 0, 0), (2, 0, 0)}, 0
            ),
            (-3, (2, 0, 0), (2, 1, 0)),
        )
        self.assertIsNone(next_rock_step(rocks, walkable, edges, walkable, 0))

    def test_binding_requires_all_three_owner_receipts_for_this_sack(self):
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"payload": rock_payload(1, actor, -2)} for actor in (-3, -4, -5)
        ]
        monsters = [{"id": -2, "ref": 5466}] + [
            {"id": actor, "ref": 4528} for actor in (-3, -4, -5)
        ]
        with patch(
            "wakfu_server.achievements.rii_owned_lesson.bind",
            return_value={"owner": 1, "target": -2, "hits": 0},
        ):
            contract = bind(db, 1, monsters)
        self.assertEqual(contract["rocks"], [-5, -4, -3])
        db.execute.return_value.fetchone.side_effect = [
            {"payload": rock_payload(1, -3, -9)}
        ]
        with patch(
            "wakfu_server.achievements.rii_owned_lesson.bind",
            return_value={"owner": 1, "target": -2, "hits": 0},
        ):
            with self.assertRaises(ValueError):
                bind(db, 1, monsters)

    def test_qualified_rock_move_updates_authority_and_emits_native_packet(self):
        actors = {
            identity: SimpleNamespace(position=(index, 0, 0), hp=100, direction=0)
            for index, identity in enumerate((-2, -3, -4))
        }
        actors[7] = SimpleNamespace(position=(0, 1, 0), hp=100, direction=0)
        fight = SimpleNamespace(
            id=8,
            actors=actors,
            rii_los_lesson_contract={"owner": 7, "hits": 1, "rocks": [-2, -3, -4]},
            walkable={(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 1, 0), (0, 1, 0), (0, 2, 0)},
            edges={((1, 0, 0), (1, 1, 0)), ((0, 1, 0), (0, 2, 0))},
            _event=Mock(),
        )
        packets = []

        def move(_fight, actor, destination):
            actor.position = destination

        with patch(
            "wakfu_server.combat_qi_fight.move_registered_actor", side_effect=move
        ):
            self.assertTrue(move_one_rock(fight, packets, action_id=10))
        self.assertEqual(actors[-3].position, (1, 1, 0))
        self.assertEqual(packets[0][0], 13624)
        self.assertEqual(fight._event.call_args.kwargs["actor_id"], -3)

    def test_rock_move_updates_real_qi_registry_and_native_wire(self):
        from wakfu_server.combat_qi_fight import current_registry

        actors = {
            identity: SimpleNamespace(
                id=identity,
                position=(index, 0, 0),
                hp=100,
                direction=0,
                physical_radius=0,
                native_obstacle_id=index,
            )
            for index, identity in enumerate((-2, -3, -4))
        }
        actors[7] = SimpleNamespace(
            id=7,
            position=(0, 1, 0),
            hp=100,
            direction=0,
            physical_radius=0,
            native_obstacle_id=3,
        )
        slots = [None] * 127
        for actor in actors.values():
            slots[actor.native_obstacle_id] = dict(
                identity=["actor", actor.id],
                position=list(actor.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        fight = SimpleNamespace(
            id=8,
            actors=actors,
            rii_los_lesson_contract={"owner": 7, "hits": 1, "rocks": [-2, -3, -4]},
            walkable={(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 1, 0), (0, 1, 0), (0, 2, 0)},
            edges={((1, 0, 0), (1, 1, 0)), ((0, 1, 0), (0, 2, 0))},
            native_qi_snapshot=dict(x=0, y=0, width=3, height=3, cell_masks=[0] * 9),
            native_qi_slots=slots,
            native_qi_touched_cells=[],
            native_qi_movement_override=False,
            native_qi_ignored_slots=[],
            _event=Mock(),
        )
        registry = current_registry(fight)
        registry.capture_fresh_cell_topology([0, 1, 2, 3])
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        packets = []
        self.assertTrue(move_one_rock(fight, packets, action_id=10))
        self.assertEqual(actors[-3].position, (1, 1, 0))
        registry = current_registry(fight)
        self.assertIn(actors[-3].native_obstacle_id, registry.ordered_U(1, 1))
        self.assertNotIn(actors[-3].native_obstacle_id, registry.ordered_U(1, 0))
        self.assertEqual(packets[0][0], 13624)

        packets = []
        fight.edges.add(((1, 1, 0), (1, 0, 0)))
        with patch(
            "wakfu_server.achievements.rii_los_encounter.has_reachable_native_shot",
            return_value=False,
        ) as shot:
            self.assertFalse(
                move_one_rock(fight, packets, action_id=11, actor_authority=object())
            )
        shot.assert_called_once()
        self.assertEqual(actors[-3].position, (1, 1, 0))
        self.assertEqual(packets, [])
        # A legal area spell may defeat one or more rock actors; this must not
        # abort the following valid hit on the sack.
        actors[-2].hp = actors[-4].hp = 0

        def move_survivor(_fight, actor, cell):
            actor.position = cell

        with patch(
            "wakfu_server.combat_qi_fight.move_registered_actor",
            side_effect=move_survivor,
        ):
            self.assertTrue(move_one_rock(fight, packets, action_id=12))
        self.assertEqual(actors[-3].position, (1, 0, 0))
        actors[-3].hp = 0
        self.assertFalse(move_one_rock(fight, [], action_id=13))

    def test_hit_rechecks_real_ray_and_does_not_credit_other_spell(self):
        fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(position=(0, 0, 0)),
                -2: SimpleNamespace(position=(4, 0, 0)),
            },
            rii_los_lesson_contract={"owner": 7, "target": -2, "hits": 0},
        )
        event = dict(
            source_id=7,
            target_id=-2,
            effect_reference=361213,
            damage=25,
            actor_authority=object(),
            spell_id=7968,
        )
        with patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=False
        ):
            self.assertEqual(hit(fight, **event), 0)
        with patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ):
            self.assertEqual(hit(fight, **(event | {"spell_id": 7967})), 0)
            self.assertEqual(hit(fight, **event), 25)
        self.assertEqual(fight.rii_los_lesson_contract["hits"], 1)

    def test_rock_blocks_native_ray_until_moved_away(self):
        from wakfu_server.combat_casting_los import native_actor_visibility

        owner = SimpleNamespace(
            id=7, position=(0, 0, 0), native_obstacle_id=0, native_los_height=6
        )
        target = SimpleNamespace(id=-2, position=(4, 0, 0), native_los_height=6)
        rock = SimpleNamespace(id=-3, position=(2, 0, 0))
        fight = SimpleNamespace(
            actors={7: owner, -2: target, -3: rock},
            native_qi_visibility_ignored_slots=[],
            rii_los_lesson_contract={"owner": 7, "target": -2, "hits": 0},
        )
        terrain = SimpleNamespace(x=0, y=0, width=6, masks=[0] * 18)
        registry = SimpleNamespace(
            slots={0: {"identity": ["actor", 7]}, 1: {"identity": ["actor", -3]}},
            terrain=terrain,
            ordered_U=lambda x, y: (1,) if (x, y) == rock.position[:2] else (),
        )

        class Authority:
            def __call__(self, _fight, _actor):
                return SimpleNamespace(native_instance_id=1388)

            def properties(self, _fight, _actor):
                return frozenset({78, 15, 11, 51, 1, 88, 114})

        authority = Authority()
        self.assertTrue(native_actor_visibility(authority.properties(fight, rock)))
        event = dict(
            source_id=7,
            target_id=-2,
            effect_reference=361213,
            damage=25,
            actor_authority=authority,
            spell_id=7968,
        )
        with patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, ((2, 0),)),),
        ):
            self.assertEqual(hit(fight, **event), 0)
            self.assertEqual(fight.rii_los_lesson_contract["hits"], 0)
            rock.position = (2, 1, 0)
            self.assertEqual(hit(fight, **event), 25)
        self.assertEqual(fight.rii_los_lesson_contract["hits"], 1)


if __name__ == "__main__":
    unittest.main()
