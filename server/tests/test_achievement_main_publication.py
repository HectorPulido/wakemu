"""Achievement publication replaces only verified owned native section bytes."""
import ast
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
from wakfu_server import wire
from wakfu_server.achievements import wire as achievement_wire


class AchievementEntityPublicationTests(unittest.TestCase):
    def state(self):
        return dict(
            variables={"51": 1},
            objectives=[617],
            running=[239],
            completed=[238],
            tracking=[239],
            recent=[dict(id=238, date_ms=1000)],
            completion_dates={"238": 1000},
        )

    def test_owned_section_replaces_only_fixture_bound_achievement_slice(self):
        native = achievement_wire.section(self.state())
        for kind in (10, 11):
            body = bytes([kind]) + b"prefix" + b"oldachievements" + b"tail"
            layout = dict(
                template_sha256=hashlib.sha256(body).hexdigest(),
                sections=[dict(name="ACHIEVEMENTS", start=7, end=22)],
            )
            with patch.dict(wire.ENTITY_LAYOUTS, {kind: layout}):
                actual = wire.minimal_entity(
                    body, dict(level=6, achievement_section=native)
                )
            self.assertEqual(actual, body[:7] + native + body[22:])

    def test_foreign_fixture_or_nonbytes_state_never_publishes(self):
        body = b"\x0aprefixoldtail"
        layout = dict(
            template_sha256=hashlib.sha256(body).hexdigest(),
            sections=[dict(name="ACHIEVEMENTS", start=7, end=10)],
        )
        with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
            with self.assertRaisesRegex(ValueError, "fixture"):
                wire.minimal_entity(
                    body + b"x", dict(level=6, achievement_section=b"owned")
                )
            with self.assertRaisesRegex(ValueError, "achievement"):
                wire.minimal_entity(body, dict(level=6, achievement_section="notbytes"))

    def test_actual_finish_paths_use_postgroup_progression_callback(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        callback = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "settle_achievements"
        )
        self.assertIn("settle_participants", ast.unparse(callback))
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and any(
                k.arg == "progression_resolver"
                and ast.unparse(k.value) == "settle_achievements"
                for k in n.keywords
            )
        ]
        self.assertEqual(len(calls), 2)

    def test_actual_tracking_route_is_session_fenced_and_never_falls_through(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        route = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test)
            == "opcode == 13175 and loaded and (character is not None)"
        )
        request = next(
            n
            for n in ast.walk(route)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "tracking_request"
        )
        self.assertEqual(
            [ast.unparse(a) for a in request.args],
            ["STORE", "account_id", "generation", "character['id']", "body"],
        )
        self.assertIsInstance(route.body[-1], ast.Continue)
        self.assertTrue(
            any(isinstance(n, ast.Continue) for n in ast.walk(route.body[1]))
        )
