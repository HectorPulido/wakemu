"""Owned scene reconstruction clears the native riding latch, never peer actors."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import mount_publication
from wakfu_server.world import World


class MountSceneReplayTests(unittest.TestCase):
    def test_reload_ready_replay_peer_visibility_and_dismount_preserve_owned_state(
        self,
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        state_function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "world_state_packets"
        )
        constructor = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "WORLD"
                for target in node.targets
            )
        )
        own_projection = next(
            keyword.value
            for keyword in constructor.keywords
            if keyword.arg == "own_state_packets"
        )
        namespace = dict(
            mount_snapshot=mount_publication.snapshot,
            STORE=object(),
            consumable_state_packets=lambda character: (),
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[state_function], type_ignores=[])
                ),
                str(source),
                "exec",
            ),
            namespace,
        )
        own_state = eval(
            compile(ast.Expression(own_projection), str(source), "eval"), namespace
        )
        packets = []
        world = World(
            lambda character: struct.pack(">q", character["id"]),
            lambda identity: struct.pack(">q", identity),
            lambda peer, opcode, body: packets.append((peer, opcode, body)),
            state_packets=namespace["world_state_packets"],
            own_state_packets=own_state,
        )
        character = dict(
            id=40,
            account_id=2,
            map_id=527,
            instance_id=0,
            mount_state=dict(mounted=True, revision=1),
        )
        before = deepcopy(character)
        observer = dict(
            id=41,
            account_id=3,
            map_id=527,
            instance_id=0,
            mount_state=dict(mounted=False, revision=0),
        )
        patches = [
            patch("wakfu_server.mount_inventory.equipped", return_value={"uid": 123}),
            patch("wakfu_server.personal_ecology.snapshot", return_value=()),
            patch("wakfu_server.emotes.retained", return_value=()),
            patch("wakfu_server.world_resurrection.snapshot", return_value=()),
            patch("wakfu_server.territory_bonus_wire.snapshot", return_value=()),
        ]
        from contextlib import ExitStack

        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            world.join("own", "owner", character)
            self.assertEqual(
                [(opcode, body) for peer, opcode, body in packets],
                [(13928, struct.pack(">q", 40)), (12634, struct.pack(">qi", 40, 0))],
            )
            packets.clear()
            world.join("other", "observer", observer)
            # A new observer gets the mounted actor and ordinary mount replay;
            # it must never receive the owner's reset carrier for that actor.
            observed = [
                (opcode, body) for peer, opcode, body in packets if peer == "observer"
            ]
            self.assertEqual([opcode for opcode, body in observed], [12608, 12634])
            packets.clear()
            for _ in range(2):
                self.assertTrue(world.resynchronize("own", "owner", character))
            self.assertTrue(all(peer == "owner" for peer, opcode, body in packets))
            self.assertEqual(
                [opcode for peer, opcode, body in packets], [12608, 13928, 12634] * 2
            )
            self.assertEqual(character, before)
            packets.clear()
            unmounted = dict(character, mount_state=dict(mounted=False, revision=2))
            world.update("own", unmounted, 13928, struct.pack(">q", 40))
            self.assertEqual([opcode for peer, opcode, body in packets], [13928, 13928])
            packets.clear()
            self.assertTrue(world.resynchronize("own", "owner", unmounted))
            self.assertEqual([opcode for peer, opcode, body in packets], [12608])
            # Fresh selection/reconnect uses the same directed replay projection.
            world.leave(40, "own")
            packets.clear()
            world.join("replacement", "new-owner", character)
            self.assertEqual(
                [opcode for peer, opcode, body in packets if peer == "new-owner"],
                [12608, 13928, 12634],
            )
        self.assertEqual(character, before)


if __name__ == "__main__":
    unittest.main()
