"""Keep dungeon run locks ahead of group settlement without ordinary-fight work."""
import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


SERVER = Path(__file__).resolve().parents[1]


def extracted_function(path, name, *, parent=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == name
        and (parent is None or any(node is child for child in ast.walk(parent)))
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name}, got {len(matches)}")
    return matches[0], tree


class DungeonSettlementLockOrderTests(unittest.TestCase):
    @staticmethod
    def helper():
        function, _tree = extracted_function(
            SERVER / "wakfu_server/maps/dungeon_progression.py",
            "lock_encounter_run",
        )
        scope = {}
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, "dungeon_progression.py", "exec"), scope)
        return scope["lock_encounter_run"]

    def test_ordinary_fight_without_dungeon_binding_is_a_noop(self):
        calls = []

        class Db:
            def execute(self, query, params):
                calls.append((query, params))
                return SimpleNamespace(fetchone=lambda: None)

        self.assertIsNone(self.helper()(Db(), 71))
        self.assertEqual(len(calls), 1)
        self.assertIn("dungeon_room_encounters", calls[0][0])

    def test_encounter_locks_existing_run_before_group_work(self):
        calls = []
        rows = iter(({"instance_id": 41}, {"instance_id": 41}))

        class Db:
            def execute(self, query, params):
                calls.append((query, params))
                return SimpleNamespace(fetchone=lambda: next(rows))

        self.assertEqual(self.helper()(Db(), 71), 41)
        self.assertEqual(len(calls), 2)
        self.assertIn("FOR UPDATE", calls[1][0])
        self.assertEqual(calls[0][1], (71,))
        self.assertEqual(calls[1][1], (41,))

    def test_encounter_without_its_room_run_fails_closed(self):
        rows = iter(({"instance_id": 41}, None))

        class Db:
            def execute(self, _query, _params):
                return SimpleNamespace(fetchone=lambda: next(rows))

        with self.assertRaisesRegex(ValueError, "no owned room progression"):
            self.helper()(Db(), 71)

    def test_real_settlement_callback_locks_run_before_group_and_respects_failed_group(
        self,
    ):
        path = SERVER / "local_game_server.py"
        session, tree = extracted_function(path, "session")
        callbacks = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef)
            and node.name == "shared_group_settlement"
        ]
        self.assertEqual(len(callbacks), 1)
        callback = callbacks[0]
        scope = {}
        module = ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[]))
        exec(compile(module, str(path), "exec"), scope)

        events = []
        progression = ModuleType("wakfu_server.dungeon_progression")
        progression.lock_encounter_run = lambda _db, fight_id: events.append(
            ("run-lock", fight_id)
        )
        group_lease = ((1086, 41, 61), "lease", 71, 1)

        def finish_group(_store, _groups, _lease, **kwargs):
            events.append(("group-finish", kwargs["character_id"], kwargs["defeated"]))
            return {"applied": False, "packets": []}

        scope.update(
            group_lease=group_lease,
            fight=SimpleNamespace(id=71, phase="finished", rift_wave_state=None),
            finish_developer_test_group=lambda *_args: None,
            COMBAT_GROUPS=object(),
            STORE=object(),
            DUNGEON_ROOM_RUNTIME_AVAILABLE=True,
            finish_world_group=finish_group,
            owner_character=16,
        )
        import wakfu_server

        previous = getattr(wakfu_server, "dungeon_progression", None)
        try:
            setattr(wakfu_server, "dungeon_progression", progression)
            with patch.dict(
                sys.modules, {"wakfu_server.dungeon_progression": progression}
            ):
                result = scope["shared_group_settlement"](object(), 1, 16, True)
        finally:
            if previous is None:
                delattr(wakfu_server, "dungeon_progression")
            else:
                setattr(wakfu_server, "dungeon_progression", previous)

        self.assertEqual(result, {"applied": False, "packets": []})
        self.assertEqual(events, [("run-lock", 71), ("group-finish", 16, True)])


if __name__ == "__main__":
    unittest.main()
