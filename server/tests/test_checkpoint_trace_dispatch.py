"""Checkpoint stage instrumentation must accept an explicit fight identity."""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace


class CheckpointTraceTests(unittest.TestCase):
    def test_explicit_fight_id_reaches_record_once(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "checkpoint_trace"
        )
        emitted = []
        namespace = dict(
            record=lambda **event: emitted.append(event),
            fight=SimpleNamespace(id=53),
            captured_checkpoint_id=53,
        )
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        namespace["checkpoint_trace"]("pool_wait", fight_id=53, operation="save")
        namespace["checkpoint_trace"]("committed", elapsed_ms=12.5)
        self.assertEqual([row["stage"] for row in emitted], ["pool_wait", "committed"])
        self.assertTrue(all(row["fight_id"] == 53 for row in emitted))
        self.assertTrue(all(row["event"] == "persistence_stage" for row in emitted))
