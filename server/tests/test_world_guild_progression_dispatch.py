"""Keep guild publication retries independent from progression clock failures."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class GuildProgressionWorldDispatchTests(unittest.TestCase):
    def test_failed_tick_still_drains_publications_and_next_clock_retries(self):
        tree = ast.parse(SERVER.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "refresh_player_guilds"
        )
        # Inject the clock callable instead of importing the application module;
        # this exercises the actual loop body without starting World services.
        function.body = [
            node for node in function.body if not isinstance(node, ast.ImportFrom)
        ]

        timeline = []
        waits = iter((False, False, True))

        class Span:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def tick(_store, *, limit):
            timeline.append(("tick", limit))
            if timeline.count(("tick", limit)) == 1:
                raise RuntimeError("transient progression database failure")

        def drain(*, limit):
            timeline.append(("drain", limit))
            if timeline.count(("drain", limit)) == 1:
                raise RuntimeError("transient publication failure")

        records = []
        scope = {
            "tick": tick,
            "STOPPING": SimpleNamespace(wait=lambda seconds: next(waits)),
            "PROFILER": SimpleNamespace(span=lambda _name: Span()),
            "STORE": object(),
            "GUILDS": SimpleNamespace(drain_pending=drain),
            "record": lambda **fields: records.append(fields),
        }
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        scope["refresh_player_guilds"]()

        self.assertEqual(
            timeline,
            [("tick", 16), ("drain", 64), ("tick", 16), ("drain", 64)],
        )
        self.assertEqual(
            [row["event"] for row in records],
            [
                "guild_progression_tick_failed",
                "guild_publication_retry_failed",
            ],
        )
        self.assertEqual(
            [row["reason"] for row in records],
            [
                "transient progression database failure",
                "transient publication failure",
            ],
        )
