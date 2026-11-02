"""Execute the actual private World publication block after a real PG choice.

No listening World is imported. The transport collector is the sole stub;
the owned-scene group serializer and native gate-packet producer are real.
"""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
from postgres_case import PostgresCase
from dungeon_physical_choice_fixture import PhysicalChoiceFixture


class PhysicalChoiceWorldPublicationTests(PhysicalChoiceFixture, PostgresCase):
    def test_actual_world_block_publishes_committed_gates_then_new_group_once(self):
        self.build_choice_fixture()
        choice = self.move_choice(0, "west")
        self.assertEqual(choice["branch_key"], "west")
        self.assertTrue(choice["scene_packets"])
        self.assertFalse(choice["group_receipt"]["replay"])
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        serializer = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "owned_scene_spawn_group"
        )
        blocks = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "physical_choice"
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value is None
        ]
        self.assertEqual(len(blocks), 1)
        packets = []
        namespace = dict(
            STORE=self.store,
            WORLD=SimpleNamespace(emit_location=lambda *args: packets.append(args)),
            character=choice["character"],
            physical_choice=choice,
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[copy.deepcopy(serializer)], type_ignores=[])
                ),
                str(source),
                "exec",
            ),
            namespace,
        )
        program = compile(
            ast.fix_missing_locations(
                ast.Module(body=[copy.deepcopy(blocks[0])], type_ignores=[])
            ),
            str(source),
            "exec",
        )
        exec(program, namespace)
        self.assertEqual(
            [p[2] for p in packets],
            [opcode for opcode, _ in choice["scene_packets"]] + [12608],
        )
        self.assertTrue(packets[-1][3])
        self.assertTrue(all(p[:2] == (301, self.instance_id) for p in packets))
        before = dict(choice["character"])
        namespace["physical_choice"] = None
        packets.clear()
        exec(program, namespace)
        self.assertEqual(packets, [])
        self.assertEqual(namespace["character"], before)
        replay = dict(choice, group_receipt=dict(choice["group_receipt"], replay=True))
        namespace["physical_choice"] = replay
        exec(program, namespace)
        self.assertNotIn(12608, [p[2] for p in packets])
