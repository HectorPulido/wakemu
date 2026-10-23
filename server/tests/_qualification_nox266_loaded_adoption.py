"""Adopt qualified post-start publication before new encounter baselines."""
import ast
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest


class AdoptQualified266(unittest.TestCase):
    def runTest(self):
        for name, module in tuple(sys.modules.items()):
            if module is None:
                continue
            if name.startswith("test_nox"):
                self.assertFalse(getattr(module, "retained_components", ()), name)
            if name.startswith("test_rushu"):
                self.assertIsNone(
                    getattr(module, "RUSHU_ACTUAL_CHECKPOINT", None), name
                )
        listeners = importlib.import_module(
            "wakfu_server.combat_encounter_table_listeners"
        )
        server = importlib.import_module("wakfu_server.combat_server_spell")
        source = Path(server.__file__)
        expected = "09192430b87237a6d4817aa756b120d28944f684c258a2ffccf21971efee4ce8"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), expected)
        self.assertEqual(
            hashlib.sha256(Path(listeners.__file__).read_bytes()).hexdigest(),
            "8e876c490a12efd6fe85410587601c3fcd53d9a736c39d3ca56d604d6161c89b",
        )
        outer = server.prepare_server_turn_start
        chain = [outer]
        while hasattr(chain[-1], "__wrapped__"):
            chain.append(chain[-1].__wrapped__)
        target = chain[-1]
        node = next(
            n
            for n in ast.parse(source.read_text(), str(source)).body
            if isinstance(n, ast.FunctionDef) and n.name == "prepare_server_turn_start"
        )
        node.decorator_list = []
        namespace = {}
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
            server.__dict__,
            namespace,
        )
        replacement = namespace[node.name]
        importlib.reload(listeners)
        target.__code__ = replacement.__code__
        target.__defaults__ = replacement.__defaults__
        target.__kwdefaults__ = replacement.__kwdefaults__
        self.assertIs(server.prepare_server_turn_start, outer)
        self.assertIn("deliver_owned_post_start_listeners", target.__code__.co_names)
        policy = listeners.freeze_table_listener_policy(1435, (5664,))
        self.assertEqual(policy["callbacks"][0]["effect_reference"], 401544)
        facts = dict(
            no_live_encounters=True,
            fresh_baseline_required=True,
            production_restart=False,
            wrapper_identities_preserved=True,
            wrapper_depth=len(chain) - 1,
            callback=policy["callbacks"][0],
            server_source_sha256=expected,
            policy=policy,
        )
        Path(
            ".runtime/parallel-readiness-20261021/nox266-qualified-loaded-adoption-before-fresh-baselines.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptQualified266()])
