import ast
import struct
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _function(tree, name):
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name} definition, got {len(matches)}")
    return matches[0]


def _calls(function, attribute):
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


class ExternalMarkerDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf8")
        cls.tree = ast.parse(cls.source)

    def test_join_and_world_resync_replay_only_current_map_markers(self):
        join = _function(self.tree, "join_world")
        snapshots = _calls(join, "world_snapshots")
        self.assertTrue(snapshots)
        self.assertTrue(
            any(
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "EXTERNAL_FIGHT_MARKERS"
                for node in snapshots
            )
        )

        refresh = _function(self.tree, "send_loaded_world_snapshot")
        self.assertTrue(
            any(
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "EXTERNAL_FIGHT_MARKERS"
                for node in _calls(refresh, "world_snapshots")
            )
        )

    def test_marker_changes_are_drained_from_current_shared_fight_only(self):
        from types import SimpleNamespace

        from wakfu_server import monsters
        from wakfu_server.combat.combat_external_markers import ExternalFightMarkers

        drain = _function(self.tree, "drain_shared_combat")
        self.assertTrue(
            any(
                isinstance(node.func, ast.Name)
                and node.func.id == "publish_external_marker"
                for node in ast.walk(drain)
                if isinstance(node, ast.Call)
            )
        )
        publisher = _function(self.tree, "publish_external_marker")
        marker = ExternalFightMarkers()
        npc = monsters.owned_instance(5525, 1, -201, map_id=1134, x=14, y=9, z=2)
        shared = SimpleNamespace(
            fight=SimpleNamespace(
                id=53,
                phase="placement",
                native_table_turn=0,
                actors={
                    17: SimpleNamespace(id=17, team=0),
                    -201: SimpleNamespace(id=-201, team=1),
                },
            ),
            map_id=1134,
            instance_id=0,
            is_duel=False,
            participants={
                1: SimpleNamespace(character_id=17, generation="owner-generation")
            },
            group_lease=((1134, 0, 77), "owner-generation", 53, 1),
            join_context={
                "arena": {
                    "map_id": 1134,
                    "instance_id": 17,
                    "x": 1,
                    "y": 2,
                    "width": 1,
                    "height": 1,
                    "min_z": -1,
                    "max_z": 0,
                    "cell_masks": [0],
                    "team_values": [],
                },
                "terrain_effect_id": 46,
                "leaders": {0: 17, 1: -201},
                "monsters": {-201: npc},
                "world_marker_cells": ((14, 9),),
                "world_marker_origin": (14, 9, 2),
                "fight_started_at": 99.5,
            },
        )
        batches = []

        class WorldCapture:
            @staticmethod
            def emit_location_batch(map_id, instance_id, packets, *, exclude_sessions):
                batches.append((map_id, instance_id, tuple(packets), exclude_sessions))

        observer = SimpleNamespace(character_id=88, generation="observer-generation")
        namespace = {
            "COMBAT_TEST": True,
            "EXTERNAL_FIGHT_MARKERS": marker,
            "SPECTATORS": SimpleNamespace(sessions=lambda _fight_id: (observer,)),
            "WORLD": WorldCapture(),
            "record": lambda **event: None,
        }
        exec(
            compile(ast.Module(body=[publisher], type_ignores=[]), str(SERVER), "exec"),
            namespace,
        )
        namespace["publish_external_marker"](shared)
        self.assertEqual(len(batches), 1)
        map_id, instance_id, packets, excluded = batches[-1]
        self.assertEqual((map_id, instance_id), (1134, 0))
        self.assertEqual([opcode for opcode, _body in packets], [12608, 13753])
        self.assertEqual(packets[0], marker.actor_packet(53))
        self.assertEqual(struct.unpack_from(">q", packets[0][1], 3)[0], -201)
        self.assertEqual(
            excluded,
            frozenset(
                {
                    (17, "owner-generation"),
                    (88, "observer-generation"),
                }
            ),
        )

        # Existing public observers get the native ACTION transition; they
        # must not receive another 13753 create for this fight ID.
        shared.fight.phase = "active"
        namespace["publish_external_marker"](shared)
        self.assertEqual(len(batches), 2)
        self.assertEqual([opcode for opcode, _body in batches[-1][2]], [12233])
        self.assertEqual(batches[-1][2][0][1], struct.pack(">i", 53))
        self.assertEqual(batches[-1][3], excluded)

        shared.fight.phase = "finished"
        namespace["publish_external_marker"](shared)
        self.assertEqual(len(batches), 3)
        self.assertEqual([opcode for opcode, _body in batches[-1][2]], [12238])
        self.assertEqual(marker.snapshots(1134, 0), ())

    def test_initial_placement_captures_starter_world_cell_for_marker(self):
        marker_contexts = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Dict)
            and any(
                isinstance(key, ast.Constant) and key.value == "world_marker_cells"
                for key in node.keys
            )
        ]
        self.assertTrue(marker_contexts)
        self.assertTrue(
            any(
                isinstance(value, ast.Tuple)
                and len(value.elts) == 1
                and isinstance(value.elts[0], ast.Tuple)
                and len(value.elts[0].elts) == 2
                and all(
                    isinstance(coordinate, ast.Subscript)
                    for coordinate in value.elts[0].elts
                )
                for context in marker_contexts
                for key, value in zip(context.keys, context.values)
                if isinstance(key, ast.Constant) and key.value == "world_marker_cells"
            )
        )
        self.assertIn("EXTERNAL_FIGHT_MARKERS = ExternalFightMarkers()", self.source)

    def test_fresh_world_join_replays_marker_leader_actors_before_13753(self):
        """Exercise join_world ordering against a real marker and World registry.

        This catches a dependency the AST-only check misses: the external
        marker references both leaders, and its NPC leader must already be in
        the entrant's world actor registry before the marker is decoded.
        """
        import threading
        from types import SimpleNamespace

        from wakfu_server import profession_store
        from wakfu_server import monsters
        from wakfu_server.combat.combat_external_markers import ExternalFightMarkers
        from wakfu_server.combat.combat_multiplayer_wire import decode_external
        from wakfu_server.maps.world import World

        markers = ExternalFightMarkers()
        player_actor = SimpleNamespace(id=17, team=0)
        monster_actor = SimpleNamespace(id=-201, team=1)
        shared = SimpleNamespace(
            fight=SimpleNamespace(
                id=53,
                phase="placement",
                native_table_turn=0,
                actors={17: player_actor, -201: monster_actor},
            ),
            map_id=1134,
            instance_id=0,
            is_duel=False,
            participants={
                1: SimpleNamespace(
                    character_id=17, account_id=1, generation="owner-generation"
                )
            },
            group_lease=((1134, 0, 77), "owner-generation", 53, 1),
            join_context={
                "arena": {
                    "map_id": 1134,
                    "instance_id": 17,
                    "x": 1,
                    "y": 2,
                    "width": 1,
                    "height": 1,
                    "min_z": -1,
                    "max_z": 0,
                    "cell_masks": [0],
                    "team_values": [],
                },
                "terrain_effect_id": 46,
                "leaders": {0: 17, 1: -201},
                "monsters": {
                    -201: monsters.owned_instance(
                        5525, 1, -201, map_id=1134, x=14, y=9, z=2
                    )
                },
                "world_marker_cells": ((14, 9),),
                "world_marker_origin": (14, 9, 2),
                "fight_started_at": 99.5,
            },
        )
        packet = markers.update(shared, now_ms=100_000, now_monotonic=100.0)
        self.assertEqual(packet[0], 13753)

        events = []

        def deliver(peer, opcode, body):
            events.append((peer, opcode, body))

        world = World(
            spawn=lambda character: f"player-actor:{character['id']}".encode(),
            remove=lambda character_id: b"remove",
            deliver=deliver,
        )
        owner_peer = object()
        world.join(
            "owner-generation",
            owner_peer,
            {
                "id": 17,
                "account_id": 1,
                "name": "fighter",
                "map_id": 1134,
                "instance_id": 0,
                "x": 14,
                "y": 9,
                "z": 2,
            },
        )

        class EmptySnapshots:
            @staticmethod
            def snapshots(*_args, **_kwargs):
                return ()

            @staticmethod
            def availability_snapshot(*_args, **_kwargs):
                return ()

        class ClaimedGroups:
            lock = threading.RLock()

            @staticmethod
            def available(_map_id, _instance_id):
                # The NPC group has status='fighting', so it is not returned
                # by the available-group query used during a world join.
                return []

        def send(peer, service, opcode, body):
            events.append((peer, opcode, body))

        join = _function(self.tree, "join_world")
        namespace = {
            "STORE": object(),
            "COMBAT_TEST": True,
            "send": send,
            "send_planting_context": lambda *_args, **_kwargs: None,
            "PLANTINGS": EmptySnapshots(),
            "WORLD": world,
            "COMBAT_GROUPS": ClaimedGroups(),
            "HARVESTS": EmptySnapshots(),
            "EXTERNAL_FIGHT_MARKERS": markers,
            "refresh_party": lambda *_args, **_kwargs: None,
        }
        exec(
            compile(ast.Module(body=[join], type_ignores=[]), str(SERVER), "exec"),
            namespace,
        )

        with patch.object(
            profession_store,
            "ensure_learned",
            return_value={"packets": ()},
        ):
            namespace["join_world"](
                "observer-generation",
                object(),
                {
                    "id": 99,
                    "account_id": 2,
                    "name": "observer",
                    "map_id": 1134,
                    "instance_id": 0,
                    "x": 15,
                    "y": 9,
                    "z": 2,
                },
            )

        observer_events = [event for event in events if event[0] is not owner_peer]
        marker_index = next(
            index
            for index, (_, opcode, _body) in enumerate(observer_events)
            if opcode == 13753
        )
        leader_ids = set(decode_external(observer_events[marker_index][2])["myr"])
        actor_ids_before_marker = {
            int(body.decode().split(":", 1)[1])
            for _peer, opcode, body in observer_events[:marker_index]
            if opcode == 12608 and body.startswith(b"player-actor:")
        }
        group_events = [
            body
            for _peer, opcode, body in observer_events[:marker_index]
            if opcode == 12608 and not body.startswith(b"player-actor:")
        ]
        self.assertEqual(len(group_events), 1)
        self.assertEqual(group_events[0][1], 1)
        self.assertEqual(struct.unpack_from(">q", group_events[0], 3)[0], -201)
        actor_ids_before_marker.add(-201)
        self.assertTrue(
            leader_ids <= actor_ids_before_marker,
            f"13753 precedes world actor snapshots for leaders "
            f"{sorted(leader_ids - actor_ids_before_marker)}",
        )


if __name__ == "__main__":
    unittest.main()
