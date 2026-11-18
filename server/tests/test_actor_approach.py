"""Exploration clicks approach actors through directed native map terrain."""

import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from protocol_codec import decode_body
from wakfu_server.actor_approach import (
    ApproachUnavailable,
    approach_path,
    movement_request,
    combat_approach,
)
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.application.dispatch_result import DispatchResult
from wakfu_server.application.session_actor_approach import ActorApproachMixin
from wakfu_server.application.session_dispatch import SessionDispatchMixin
from wakfu_server import npc_approach_target


def graph(cells, edges):
    return prepare_geometry(dict(map_id=527, cells=cells, edges=edges))


def corridor(length):
    cells = [(x, 0, 0) for x in range(length)]
    return graph(cells, [(a, b) for a, b in zip(cells, cells[1:])])


class ActorApproachPathTests(unittest.TestCase):
    def test_far_actor_routes_to_first_accepted_cell(self):
        path = approach_path(corridor(8), (0, 0, 0), lambda cell: cell[0] >= 6)
        self.assertEqual(path, tuple((x, 0, 0) for x in range(7)))
        request = decode_body("out", 13331, movement_request(path))
        self.assertEqual(request["mode"], "WALK")
        self.assertEqual(request["end_position"], dict(x=6, y=0, z=0))

    def test_wall_is_not_replaced_by_geometric_adjacency(self):
        terrain = graph([(0, 0, 0), (1, 0, 0)], [])
        with self.assertRaisesRegex(ValueError, "camino"):
            approach_path(terrain, (0, 0, 0), lambda cell: cell == (1, 0, 0))

    def test_real_detour_and_directed_edges(self):
        cells = [(0, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0), (2, 0, 0)]
        terrain = graph(cells, list(zip(cells, cells[1:])))
        self.assertEqual(
            approach_path(terrain, cells[0], lambda cell: cell == cells[-1]),
            tuple(cells),
        )
        with self.assertRaises(ValueError):
            approach_path(terrain, cells[-1], lambda cell: cell == cells[0])

    def test_same_cell_npc_stays_and_blocked_enemy_cell_can_be_exited(self):
        start, end = (0, 0, 0), (1, 0, 0)
        terrain = corridor(2)
        self.assertEqual(
            approach_path(terrain, start, lambda cell: cell == start), (start,)
        )
        self.assertEqual(
            approach_path(terrain, start, lambda cell: cell == end, blocked=[start]),
            (start, end),
        )
        with self.assertRaises(ValueError):
            approach_path(terrain, start, lambda cell: cell == end, blocked=[end])

    def test_signed_heights_roundtrip_and_unencodable_steps_are_rejected(self):
        path = ((0, 0, -3), (1, 0, 12), (1, 1, -4))
        terrain = graph(path, list(zip(path, path[1:])))
        result = approach_path(terrain, path[0], lambda cell: cell == path[-1])
        request = decode_body("out", 13331, movement_request(result))
        self.assertEqual([step["dz"] for step in request["steps"]], [15, -16])
        self.assertEqual(request["end_position"], dict(x=1, y=1, z=-4))
        invalid = ((0, 0, 0), (1, 0, 16))
        with self.assertRaises(ValueError):
            approach_path(
                graph(invalid, [invalid]), invalid[0], lambda cell: cell == invalid[1]
            )
        with self.assertRaises(ValueError):
            movement_request(invalid)

    def test_native_step_limit_and_invalid_movement_paths(self):
        terrain = corridor(257)
        self.assertEqual(
            len(approach_path(terrain, (0, 0, 0), lambda cell: cell[0] == 255)), 256
        )
        with self.assertRaises(ValueError):
            approach_path(terrain, (0, 0, 0), lambda cell: cell[0] == 256)
        for path in (
            (),
            ((0, 0, 0),),
            ((0, 0, 0), (2, 0, 0)),
            tuple((x, 0, 0) for x in range(257)),
        ):
            with self.subTest(path_length=len(path)), self.assertRaises(ValueError):
                movement_request(path)
        with self.assertRaises(ValueError):
            approach_path(terrain, (-1, 0, 0), lambda cell: True)


class CombatClickApproachTests(unittest.TestCase):
    def test_owned_nest_attack_filters_only_final_goal_not_native_walk_graph(self):
        import json
        from pathlib import Path

        from wakfu_server import dungeon_runtime
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.combat_walk_surface_policy import (
            ordinary_owned_attack_goal_filter,
        )

        configuration = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/owned_story_profiles/astrub-nest-728.configuration.json"
            ).read_text()
        )
        base = prepare_geometry(published_geometry(728))
        room = configuration["topology"]["rooms"][1]
        room_cells = {tuple(cell) for cell in room["cells"]}
        edges = {
            edge
            for edge in base.edges
            if edge[0] in room_cells and edge[1] in room_cells
        }
        terrain = prepare_geometry(
            dict(map_id=728, cells=sorted(room_cells), edges=sorted(edges))
        )
        original_edges = set(terrain.edges)
        member = dict(id=-125, ref=125, x=0, y=19, z=0)
        profiles = dict(
            npc_profiles={"125": dict(physical_radius=0)}, default_actor_radius=0
        )
        goals, blocked = combat_approach(terrain, [member], -125, profiles)
        forbidden = (0, 20, 0)
        self.assertIn(forbidden, goals)

        query = Mock()
        query.fetchone.return_value = dict(
            current_room=2, asset_map_id=728, group_id=77
        )
        db = Mock()
        db.execute.return_value = query
        character = dict(map_id=728, instance_id=91, x=1, y=20, z=0)
        group_key = (728, 91, 77)
        with patch.object(
            dungeon_runtime,
            "configuration_for_instance",
            return_value=(None, configuration),
        ), patch.object(dungeon_runtime, "combat_room_scene", return_value=None):
            allowed = ordinary_owned_attack_goal_filter(
                db, character, group_key, [member], 0
            )
            self.assertIsNotNone(allowed)
            self.assertFalse(allowed(forbidden))
            self.assertTrue(allowed((0, 18, 0)))
            filtered, _ = combat_approach(
                terrain,
                [member],
                -125,
                profiles,
                final_cell_allowed=allowed,
            )

            # A full body keeps its existing goal policy, and authored scene
            # geometry is not filtered by the ordinary point-placement rule.
            self.assertIsNone(
                ordinary_owned_attack_goal_filter(db, character, group_key, [member], 1)
            )
            with patch.object(
                dungeon_runtime,
                "combat_room_scene",
                return_value={"native": "authored-scene"},
            ):
                self.assertIsNone(
                    ordinary_owned_attack_goal_filter(
                        db, character, group_key, [member], 0
                    )
                )

        self.assertNotIn(forbidden, filtered)
        self.assertEqual(set(terrain.edges), original_edges)
        path = approach_path(
            terrain, (1, 20, 0), filtered.__contains__, blocked=blocked
        )
        self.assertIn(path[-1], filtered)
        self.assertNotEqual(path[-1], forbidden)

    def test_far_wall_and_shared_cell_use_the_admission_approach_policy(self):
        cells = [(x, 0, 0) for x in range(7)]
        edges = [(a, b) for a, b in zip(cells, cells[1:])]
        terrain = graph(cells, edges + [(b, a) for a, b in edges])
        member = dict(id=-7, ref=1, x=3, y=0, z=0)
        profiles = dict(
            npc_profiles={"1": dict(physical_radius=0)}, default_actor_radius=0
        )
        goals, blocked = combat_approach(terrain, [member], -7, profiles)
        self.assertEqual(goals, {(2, 0, 0), (4, 0, 0)})
        self.assertEqual(blocked, {(3, 0, 0)})
        for start in ((0, 0, 0), (3, 0, 0)):
            with self.subTest(start=start):
                path = approach_path(
                    terrain, start, goals.__contains__, blocked=blocked
                )
                self.assertIn(path[-1], goals)
                self.assertNotIn(path[-1], blocked)
                self.assertNotIn((3, 0, 0), path[1:])
        wall = graph(
            cells,
            [(a, b) for a, b in terrain.edges if {a, b} != {(2, 0, 0), (3, 0, 0)}],
        )
        goals, blocked = combat_approach(wall, [member], -7, profiles)
        self.assertNotIn((2, 0, 0), goals)
        with self.assertRaises(ValueError):
            approach_path(wall, (0, 0, 0), goals.__contains__, blocked=blocked)

    def test_platform_drop_walks_to_the_lower_combat_floor_before_attack(self):
        upper, lower, near, target = (0, 0, 3), (0, 1, 0), (1, 1, 0), (1, 0, 0)
        terrain = graph(
            [upper, lower, near, target],
            [
                (upper, target),
                (upper, lower),
                (lower, near),
                (near, lower),
                (near, target),
                (target, near),
            ],
        )
        profiles = dict(
            npc_profiles={"1": dict(physical_radius=0)}, default_actor_radius=0
        )
        member = dict(id=-7, ref=1, x=target[0], y=target[1], z=target[2])
        goals, blocked = combat_approach(terrain, [member], -7, profiles)
        self.assertNotIn(upper, goals)
        path = approach_path(terrain, upper, goals.__contains__, blocked=blocked)
        self.assertEqual(path, (upper, lower, near))
        request = decode_body("out", 13331, movement_request(path))
        self.assertEqual([step["dz"] for step in request["steps"]], [-3, 0])
        self.assertEqual(request["end_position"], dict(x=1, y=1, z=0))
        self.assertNotIn(target, path)

    def test_platform_without_free_descent_does_not_attack_through_the_drop(self):
        upper, lower, near, target = (0, 0, 3), (0, 1, 0), (1, 1, 0), (1, 0, 0)
        terrain = graph(
            [upper, lower, near, target],
            [
                (upper, target),
                (lower, near),
                (near, lower),
                (near, target),
                (target, near),
            ],
        )
        profiles = dict(
            npc_profiles={"1": dict(physical_radius=0)}, default_actor_radius=0
        )
        member = dict(id=-7, ref=1, x=target[0], y=target[1], z=target[2])
        goals, blocked = combat_approach(terrain, [member], -7, profiles)
        self.assertNotIn(upper, goals)
        with self.assertRaisesRegex(ValueError, "camino"):
            approach_path(terrain, upper, goals.__contains__, blocked=blocked)

    def test_platform_still_descends_when_a_return_path_connects_both_levels(self):
        upper, lower, near, target = (0, 0, 3), (0, 1, 0), (1, 1, 0), (1, 0, 0)
        terrain = graph(
            [upper, lower, near, target],
            [
                (upper, target),
                (upper, lower),
                (lower, upper),
                (lower, near),
                (near, lower),
                (near, target),
                (target, near),
            ],
        )
        profiles = dict(
            npc_profiles={"1": dict(physical_radius=0)}, default_actor_radius=0
        )
        member = dict(id=-7, ref=1, x=target[0], y=target[1], z=target[2])
        goals, blocked = combat_approach(terrain, [member], -7, profiles)
        self.assertNotIn(upper, goals)
        self.assertEqual(
            approach_path(terrain, upper, goals.__contains__, blocked=blocked),
            (upper, lower, near),
        )

    def test_large_monster_body_cannot_be_an_attack_destination(self):
        cells = [(x, 0, 0) for x in range(7)]
        edges = [(a, b) for a, b in zip(cells, cells[1:])]
        terrain = graph(cells, edges + [(b, a) for a, b in edges])
        profiles = dict(
            npc_profiles={"1": dict(physical_radius=1)}, default_actor_radius=0
        )
        goals, blocked = combat_approach(
            terrain, [dict(id=-7, ref=1, x=3, y=0, z=0)], -7, profiles
        )
        self.assertEqual(blocked, {(2, 0, 0), (3, 0, 0), (4, 0, 0)})
        self.assertEqual(goals, {(1, 0, 0), (5, 0, 0)})


class ActorApproachSessionTests(unittest.TestCase):
    def session(self):
        session = ActorApproachMixin()
        session.state = SimpleNamespace(
            character=dict(id=7, map_id=527, instance_id=0, x=0, y=0, z=0),
            loaded=True,
            fight=None,
            spectator_session=None,
            generation="lease",
            opcode=13222,
            body=b"original",
            connection=object(),
            service="world",
            pending_actor_approach=None,
        )
        session.runtime = SimpleNamespace(
            send=Mock(), wire=SimpleNamespace(movement_path=Mock(return_value=b"relay"))
        )
        session.dispatch_request = Mock()
        session.prepare_request = Mock(return_value=DispatchResult.FALLTHROUGH)
        session.handle_world_movement = Mock(return_value=DispatchResult.FALLTHROUGH)
        return session

    def pending(self, session):
        return dict(
            generation="lease",
            identity=(7, 527, 0),
            position=(0, 0, 0),
            opcode=13222,
            body=b"click",
            due=10,
        )

    def test_approach_reuses_validator_echoes_owner_and_restores_request(self):
        session = self.session()
        path = ((0, 0, 0), (1, 0, 0))
        with patch(
            "wakfu_server.actor_approach.approach_path", return_value=path
        ), patch(
            "wakfu_server.combat_terrain.map_geometry",
            return_value=dict(map_id=527, cells=path, edges=[path]),
        ), patch(
            "wakfu_server.application.session_actor_approach.time.monotonic",
            return_value=5,
        ):
            self.assertTrue(session.approach_actor(lambda cell: cell == path[-1]))
        session.handle_world_movement.assert_called_once_with()
        session.runtime.send.assert_called_once_with(
            session.state.connection, "world", 13852, b"relay"
        )
        self.assertEqual(
            (session.state.opcode, session.state.body), (13222, b"original")
        )
        self.assertEqual(session.state.pending_actor_approach["position"], path[-1])

    def test_unreachable_attack_falls_through_without_movement_or_pending_action(self):
        target = (1, 0, 0)
        for start in ((0, 0, 0), (9, 9, 0)):
            with self.subTest(start=start):
                session = self.session()
                session.state.opcode = 13130
                session.state.character.update(dict(zip(("x", "y", "z"), start)))
                disconnected = graph([(0, 0, 0), target], [])
                self.assertFalse(
                    session.approach_actor(
                        target.__eq__,
                        geometry=disconnected,
                        allow_unreachable=True,
                    )
                )
                session.handle_world_movement.assert_not_called()
                session.runtime.send.assert_not_called()
                self.assertIsNone(session.state.pending_actor_approach)
                self.assertEqual(
                    (session.state.opcode, session.state.body), (13130, b"original")
                )

    def test_unreachable_npc_keeps_strict_approach_failure(self):
        session = self.session()
        target = (1, 0, 0)
        with self.assertRaises(ApproachUnavailable):
            session.approach_actor(
                target.__eq__,
                geometry=graph([(0, 0, 0), target], []),
            )
        session.handle_world_movement.assert_not_called()
        session.runtime.send.assert_not_called()
        self.assertIsNone(session.state.pending_actor_approach)

    def test_attack_fallback_still_walks_when_a_real_path_exists(self):
        session = self.session()
        session.state.opcode = 13130
        target = (1, 0, 0)
        self.assertTrue(
            session.approach_actor(
                target.__eq__,
                geometry=corridor(2),
                allow_unreachable=True,
            )
        )
        session.handle_world_movement.assert_called_once_with()
        session.runtime.send.assert_called_once_with(
            session.state.connection, "world", 13852, b"relay"
        )
        self.assertEqual(session.state.pending_actor_approach["position"], target)
        self.assertEqual(session.state.pending_actor_approach["opcode"], 13130)

    def test_attack_fallback_does_not_hide_other_planner_value_errors(self):
        session = self.session()

        def accepts(cell):
            if cell == (0, 0, 0):
                return False
            raise ValueError("Invalid interaction authority")

        with self.assertRaisesRegex(ValueError, "Invalid interaction authority"):
            session.approach_actor(
                accepts, geometry=corridor(2), allow_unreachable=True
            )
        session.handle_world_movement.assert_not_called()
        session.runtime.send.assert_not_called()
        self.assertIsNone(session.state.pending_actor_approach)

    def test_rejected_movement_does_not_echo_or_queue_interaction(self):
        session = self.session()
        session.handle_world_movement.return_value = DispatchResult.CONTINUE
        path = ((0, 0, 0), (1, 0, 0))
        with patch(
            "wakfu_server.actor_approach.approach_path", return_value=path
        ), patch(
            "wakfu_server.combat_terrain.map_geometry",
            return_value=dict(map_id=527, cells=path, edges=[path]),
        ):
            self.assertTrue(session.approach_actor(lambda cell: cell == path[-1]))
        session.runtime.send.assert_not_called()
        self.assertIsNone(session.state.pending_actor_approach)

    def test_resume_waits_then_dispatches_once_and_restores_current_request(self):
        session = self.session()
        session.state.pending_actor_approach = self.pending(session)
        seen = []
        session.dispatch_request.side_effect = lambda: seen.append(
            (session.state.opcode, session.state.body)
        )
        with patch(
            "wakfu_server.application.session_actor_approach.time.monotonic",
            return_value=9,
        ):
            session.resume_actor_approach()
        session.dispatch_request.assert_not_called()
        with patch(
            "wakfu_server.application.session_actor_approach.time.monotonic",
            return_value=10,
        ):
            session.resume_actor_approach()
            session.resume_actor_approach()
        self.assertEqual(seen, [(13222, b"click")])
        self.assertEqual(
            (session.state.opcode, session.state.body), (13222, b"original")
        )
        self.assertIsNone(session.state.pending_actor_approach)

    def test_replaced_actor_scene_position_or_combat_cancels_arrival(self):
        changes = [dict(id=8), dict(map_id=528), dict(instance_id=1), dict(x=1)]
        for change in changes:
            session = self.session()
            session.state.pending_actor_approach = self.pending(session)
            session.state.character.update(change)
            with self.subTest(change=change), patch(
                "wakfu_server.application.session_actor_approach.time.monotonic",
                return_value=11,
            ):
                session.resume_actor_approach()
                session.dispatch_request.assert_not_called()
                self.assertIsNone(session.state.pending_actor_approach)
        for field in ("fight", "spectator_session"):
            session = self.session()
            session.state.pending_actor_approach = self.pending(session)
            setattr(session.state, field, object())
            with self.subTest(field=field), patch(
                "wakfu_server.application.session_actor_approach.time.monotonic",
                return_value=11,
            ):
                session.resume_actor_approach()
                session.dispatch_request.assert_not_called()


class ActorApproachCancellationTests(unittest.TestCase):
    def test_manual_movement_cancels_pending_but_checkpoints_preserve_it(self):
        session = SessionDispatchMixin()
        session.runtime = SimpleNamespace(
            COMBAT_TEST=False, record=Mock(), GUILD_REQUEST_OPCODES=()
        )
        session.state = SimpleNamespace(
            opcode=13331,
            loaded=True,
            service="world",
            pending_actor_approach=object(),
            fight=None,
            artifact_action_request=False,
            ranch_session=None,
        )
        session.handle_world_movement = Mock(return_value=DispatchResult.FALLTHROUGH)
        session.handle_position_save = Mock(return_value=DispatchResult.FALLTHROUGH)
        session.handle_position_checkpoint = Mock(
            return_value=DispatchResult.FALLTHROUGH
        )
        session.dispatch_request()
        self.assertIsNone(session.state.pending_actor_approach)
        session.handle_world_movement.assert_called_once_with()
        for opcode in (13932, 12239):
            pending = object()
            session.state.opcode = opcode
            session.state.pending_actor_approach = pending
            session.dispatch_request()
            self.assertIs(session.state.pending_actor_approach, pending)

    def test_replaced_lease_and_rejected_prepare_do_not_dispatch(self):
        fixtures = ActorApproachSessionTests()
        for generation, preparation in (
            ("new-lease", DispatchResult.FALLTHROUGH),
            ("lease", DispatchResult.CONTINUE),
        ):
            session = fixtures.session()
            session.state.pending_actor_approach = fixtures.pending(session)
            session.state.generation = generation
            session.prepare_request.return_value = preparation
            with self.subTest(generation=generation, preparation=preparation), patch(
                "wakfu_server.application.session_actor_approach.time.monotonic",
                return_value=11,
            ):
                session.resume_actor_approach()
                session.dispatch_request.assert_not_called()
                self.assertIsNone(session.state.pending_actor_approach)


class NpcApproachTargetTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(id=7, map_id=527, instance_id=0, x=0, y=0, z=0)
        self.row = dict(
            actor_id=-4000000000000000,
            reference_id=123,
            map_id=527,
            instance_id=0,
            x=9,
            y=0,
            z=0,
            action_ids=[42],
            dialogue_root=10,
            interaction_range=2,
        )
        self.store = Mock()
        self.db = Mock()

    def test_npc_approaches_require_edges_and_allow_the_same_cell(self):
        row = dict(self.row, x=3, interaction_range=1)
        terrain = corridor(5)
        goals = npc_approach_target.approach_cells(terrain, row)
        self.assertEqual(goals, {(2, 0, 0), (3, 0, 0)})
        self.assertEqual(
            approach_path(terrain, (0, 0, 0), goals.__contains__)[-1], (2, 0, 0)
        )
        self.assertEqual(
            approach_path(terrain, (3, 0, 0), goals.__contains__), ((3, 0, 0),)
        )
        wall = graph(
            terrain.cells,
            [(a, b) for a, b in terrain.edges if (a, b) != ((2, 0, 0), (3, 0, 0))],
        )
        goals = npc_approach_target.approach_cells(wall, row)
        self.assertNotIn((2, 0, 0), goals)
        with self.assertRaises(ValueError):
            approach_path(wall, (0, 0, 0), goals.__contains__)

    def test_malformed_and_choice_packets_do_not_resolve_or_access_store(self):
        for opcode, body in ((13222, b"short"), (12535, bytes(12)), (12058, bytes(8))):
            with self.subTest(opcode=opcode):
                self.assertIsNone(
                    npc_approach_target.resolve(
                        self.store, self.character, opcode, body
                    )
                )
        self.store.connection.assert_not_called()

    def test_generic_click_and_native_open_resolve_same_published_actor(self):
        from contextlib import nullcontext

        self.store.connection.return_value = nullcontext(self.db)
        from wakfu_server import quest_npc

        with patch(
            "wakfu_server.npc_world.load_scene", return_value=[self.row]
        ), patch.object(quest_npc, "publication", return_value=None):
            for opcode, body in (
                (13222, struct.pack(">qq", self.row["actor_id"], 42)),
                (12535, struct.pack(">ibq", 10, 2, self.row["actor_id"])),
            ):
                self.store.connection.return_value = nullcontext(self.db)
                with self.subTest(opcode=opcode):
                    self.assertEqual(
                        npc_approach_target.resolve(
                            self.store, self.character, opcode, body
                        ),
                        self.row,
                    )

    def test_quest_target_uses_published_interaction_anchor(self):
        from contextlib import nullcontext
        from wakfu_server import quest_npc

        anchor = dict(x=8, y=0, z=1)
        row = dict(self.row, provenance=quest_npc.PREFIX + "fixture")
        row["_quest_publication"] = (
            dict(placements=[dict(row=self.row, interaction_anchor=anchor)]),
        )
        self.store.connection.return_value = nullcontext(self.db)
        with patch("wakfu_server.npc_world.load_scene", return_value=[row]):
            result = npc_approach_target.resolve(
                self.store,
                self.character,
                13222,
                struct.pack(">qq", row["actor_id"], 42),
            )
        self.assertEqual(tuple(result[key] for key in ("x", "y", "z")), (8, 0, 1))
        self.assertEqual(row["x"], 9)

    def test_native_magnum_story_overlay_uses_attested_anchor_and_real_floor(self):
        import json
        from contextlib import nullcontext
        from pathlib import Path

        from wakfu_server import quest_npc
        from wakfu_server.combat_geometry import published_geometry

        contract_path = (
            Path(__file__).parents[1]
            / "wakfu_server/maps/native_quest_conversation_contracts.json"
        )
        contract = json.loads(contract_path.read_text())
        placement = next(
            item
            for item in contract["placements"]
            if item["row"]["actor_id"] == -1724034232352753
        )
        physical = placement["row"]
        native = dict(
            actor_id=physical["actor_id"],
            reference_id=physical["reference_id"],
            map_id=physical["map_id"],
            instance_id=physical["instance_id"],
            x=physical["x"],
            y=physical["y"],
            z=physical["z"],
            direction=physical["direction"],
            action_ids=[703],
            dialogue_root=physical["dialogue_root"],
            interaction_range=physical["interaction_range"],
            provenance="native-provider",
        )
        native_source = dict(
            actor_id=physical["actor_id"],
            reference_id=physical["reference_id"],
            map_id=physical["map_id"],
            instance_id=physical["instance_id"],
            x=physical["x"],
            y=physical["y"],
            z=physical["z"],
            direction=physical["direction"],
            level=100,
            visual_id=117903819,
            name_es="Magnum Deskhalzo",
            native_action_ids=[703],
            enabled=True,
            source_sha256=placement["existing_native_actor"]["source_sha256"],
        )
        self.character = dict(id=7, map_id=1134, instance_id=0, x=15, y=7, z=0)
        self.store.connection.return_value = nullcontext(self.db)
        self.db.execute.return_value.fetchone.return_value = native_source
        with patch(
            "wakfu_server.npc_world.load_scene", return_value=[native]
        ), patch.object(quest_npc, "publication", return_value=(contract,)):
            result = npc_approach_target.resolve(
                self.store,
                self.character,
                13222,
                struct.pack(">qq", physical["actor_id"], 703),
            )

        # The clicked actor stays on its native waypoint; only this response is
        # projected onto the source-attested, reachable approach floor.
        self.assertEqual(tuple(native[key] for key in ("x", "y", "z")), (16, 8, 0))
        self.assertEqual(tuple(result[key] for key in ("x", "y", "z")), (16, 7, 0))
        geometry = published_geometry(1134)
        goals = npc_approach_target.approach_cells(geometry, result)
        self.assertIn((16, 7, 0), goals)
        self.assertIn((15, 7, 0), goals)
        self.assertEqual(
            approach_path(geometry, (15, 7, 0), goals.__contains__),
            ((15, 7, 0),),
        )

        # Reattestation of the existing physical source rejects drift before
        # the published overlay can redirect a click.
        changed_source = dict(native_source, x=17)
        self.db.execute.return_value.fetchone.return_value = changed_source
        with patch(
            "wakfu_server.npc_world.load_scene", return_value=[native]
        ), patch.object(
            quest_npc, "publication", return_value=(contract,)
        ), self.assertRaisesRegex(
            ValueError, "source changed"
        ):
            npc_approach_target.resolve(
                self.store,
                self.character,
                13222,
                struct.pack(">qq", physical["actor_id"], 703),
            )

        # With no active overlay, the native provider remains authoritative.
        self.db.execute.return_value.fetchone.return_value = native_source
        from wakfu_server import weekly_hunter_npc

        with patch.object(
            weekly_hunter_npc, "_actor", return_value=native_source
        ), patch.object(quest_npc, "publication", return_value=None):
            fallback = npc_approach_target.resolve(
                self.store,
                self.character,
                13222,
                struct.pack(">qq", physical["actor_id"], 703),
            )
        self.assertEqual(fallback["actor_id"], physical["actor_id"])
        self.assertEqual(tuple(fallback[key] for key in ("x", "y", "z")), (16, 8, 0))

    def test_special_ruel_requires_enablement_and_current_scene(self):
        from contextlib import nullcontext
        from wakfu_server import ruel_hunt_npc

        row = ruel_hunt_npc.placement()
        body = struct.pack(">qq", ruel_hunt_npc.ACTOR, ruel_hunt_npc.ACTION)
        for enabled, scene, expected in (
            (True, row["map_id"], row),
            (False, row["map_id"], None),
            (True, row["map_id"] + 1, None),
        ):
            self.store.connection.return_value = nullcontext(self.db)
            with self.subTest(enabled=enabled, scene=scene), patch(
                "wakfu_server.ruel_hunt_npc._enabled", return_value=enabled
            ):
                self.assertEqual(
                    npc_approach_target.resolve(
                        self.store, dict(self.character, map_id=scene), 13222, body
                    ),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
