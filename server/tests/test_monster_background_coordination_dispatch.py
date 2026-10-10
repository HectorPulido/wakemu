"""Exercise the real background dispatch fences without running service loops."""
import ast
from contextlib import contextmanager, ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class _Lock:
    def __init__(self, name, events, state):
        self.name = name
        self.events = events
        self.state = state

    def __enter__(self):
        self.events.append(("acquire", self.name))
        self.state[0] += 1
        return self

    def __exit__(self, *_):
        self.state[0] -= 1
        self.events.append(("release", self.name))


class _Profiler:
    def __init__(self, events):
        self.events = events

    @contextmanager
    def span(self, name):
        self.events.append(("span_start", name))
        try:
            yield
        finally:
            self.events.append(("span_end", name))


class MonsterBackgroundCoordinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SERVER.read_text(encoding="utf8"))

    def _dispatch_and_coordination(self, dispatcher_name):
        dispatcher = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == dispatcher_name
        )
        tick_calls = [
            node
            for node in ast.walk(dispatcher)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "tick"
        ]
        self.assertEqual(len(tick_calls), 1)
        self.assertTrue(
            any(
                keyword.arg == "coordination"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "coordination"
                for keyword in tick_calls[0].keywords
            )
        )
        coordination = next(
            node
            for node in ast.walk(dispatcher)
            if isinstance(node, ast.FunctionDef) and node.name == "coordination"
        )
        events, state = [], [0]
        scope = {
            "contextmanager": contextmanager,
            "ExitStack": ExitStack,
            "PROFILER": _Profiler(events),
            "COMBAT_GROUPS": SimpleNamespace(lock=_Lock("groups", events, state)),
            "HARVESTS": SimpleNamespace(
                lock=_Lock("harvests", events, state), targets={-10: 1}
            ),
            "WORLD": SimpleNamespace(snapshot=lambda: [{"id": 7}]),
        }
        module = ast.fix_missing_locations(
            ast.Module(body=[coordination], type_ignores=[])
        )
        exec(compile(module, str(SERVER), "exec"), scope)
        return scope["coordination"], events, state

    def test_reproduction_dispatch_releases_both_fences_between_operations(self):
        coordination, events, state = self._dispatch_and_coordination(
            "reproduce_monsters"
        )
        for stage, label in (
            ("observe", "observe"),
            ("attempt", "attempt"),
            ("publish", "publish"),
        ):
            with self.subTest(stage=stage):
                before = len(events)
                with coordination(stage, 1, 0) as (players, excluded):
                    self.assertEqual(state[0], 2)
                    self.assertEqual(players, [{"id": 7}])
                    self.assertEqual(excluded, {-10})
                self.assertEqual(state[0], 0)
                chunk = events[before:]
                self.assertEqual(
                    [entry for entry in chunk if entry[0] == "acquire"],
                    [("acquire", "groups"), ("acquire", "harvests")],
                )
                self.assertEqual(
                    [entry for entry in chunk if entry[0] == "release"],
                    [("release", "harvests"), ("release", "groups")],
                )
                self.assertIn(
                    ("span_start", f"background.reproduction_guard_wait.{label}"), chunk
                )
                self.assertIn(
                    ("span_start", f"background.reproduction_guard_held.{label}"), chunk
                )

    def test_maturation_dispatch_releases_both_fences_between_operations(self):
        coordination, events, state = self._dispatch_and_coordination("mature_monsters")
        for stage, label in (
            ("observe", "observe"),
            ("attempt", "attempt"),
            ("publish", "publish"),
        ):
            with self.subTest(stage=stage):
                before = len(events)
                with coordination(stage, 1, 0) as (players, excluded):
                    self.assertEqual(state[0], 2)
                    self.assertEqual(players, [{"id": 7}])
                    self.assertEqual(excluded, {-10})
                self.assertEqual(state[0], 0)
                chunk = events[before:]
                self.assertEqual(
                    [entry for entry in chunk if entry[0] == "acquire"],
                    [("acquire", "groups"), ("acquire", "harvests")],
                )
                self.assertEqual(
                    [entry for entry in chunk if entry[0] == "release"],
                    [("release", "harvests"), ("release", "groups")],
                )
                self.assertIn(
                    ("span_start", f"background.maturation_guard_wait.{label}"), chunk
                )
                self.assertIn(
                    ("span_start", f"background.maturation_guard_held.{label}"), chunk
                )


if __name__ == "__main__":
    unittest.main()
