import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


class IdleHealthRegenerationTests(unittest.TestCase):
    def test_valid_session_health_does_not_shadow_regeneration_packet_module(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        session = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "session"
        )
        idle = next(
            n
            for n in session.body
            if isinstance(n, ast.FunctionDef) and n.name == "idle"
        )
        health_assignment = next(
            n
            for n in ast.walk(idle)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "session_health"
        )
        regen = next(
            n
            for n in ast.walk(idle)
            if isinstance(n, ast.If) and "last_health_tick" in ast.unparse(n.test)
        )
        calls = []
        character = {
            "id": 6,
            "hp": 807,
            "max_hp": 836,
            "hp_damage": 29,
            "health_dead": False,
        }
        namespace = {
            "STORE": SimpleNamespace(session_health=lambda *a, **k: {"valid": True}),
            "account_id": 1,
            "generation": "current",
            "renew": False,
            "loaded": True,
            "fight": None,
            "combat_session": None,
            "character": character,
            "last_health_tick": 0,
            "time": SimpleNamespace(monotonic=lambda: 2),
            "health_store": SimpleNamespace(
                tick=lambda *a: {
                    "hp": 808,
                    "max_hp": 836,
                    "hp_damage": 28,
                    "health_dead": False,
                    "regeneration_coefficient": 28,
                }
            ),
            "health": SimpleNamespace(packet=lambda *a: calls.append(a) or b"hp"),
            "WORLD": SimpleNamespace(update=lambda *a: None),
            "record": lambda **k: None,
        }
        isolated = ast.Module(body=[health_assignment, regen], type_ignores=[])
        exec(
            compile(ast.fix_missing_locations(isolated), str(source), "exec"), namespace
        )
        self.assertEqual(
            (character["hp"], character["hp_damage"], character["health_dead"]),
            (808, 28, False),
        )
        self.assertEqual(calls, [(6, 808, 28)])

        # Hidden wounds can decrease while the visible living minimum stays 1.
        calls.clear()
        character.update(hp=1, hp_damage=900)
        namespace["last_health_tick"] = 0
        namespace["health_store"] = SimpleNamespace(
            tick=lambda *a: {
                "hp": 1,
                "max_hp": 836,
                "hp_damage": 899,
                "health_dead": False,
                "regeneration_coefficient": 28,
            }
        )
        exec(
            compile(ast.fix_missing_locations(isolated), str(source), "exec"), namespace
        )
        self.assertEqual((character["hp"], character["hp_damage"]), (1, 899))
        self.assertEqual(calls, [])
