"""Execute the actual nested World readiness initializer in isolation."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from wakfu_server.maps import boss_score, boss_score_runtime, dungeon_stele_states


class BossScoreDispatcherTests(unittest.TestCase):
    def initializer(self, dungeon=False):
        path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        functions = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "initialize_encounter_states"
        ]
        self.assertEqual(1, len(functions))
        module = ast.fix_missing_locations(
            ast.Module(body=[functions[0]], type_ignores=[])
        )
        self.db = object()
        self.store = SimpleNamespace(
            connection=Mock(side_effect=lambda: nullcontext(self.db))
        )
        namespace = dict(
            STORE=self.store,
            is_dungeon_run=lambda instance: dungeon,
            server_runtime=Mock(),
        )
        exec(compile(module, str(path), "exec"), namespace)
        return namespace["initialize_encounter_states"]

    def sources(self):
        preview = SimpleNamespace(
            id=9,
            actors={
                1: SimpleNamespace(team=0),
                2: SimpleNamespace(team=0),
                -7: SimpleNamespace(team=1),
            },
        )
        return (
            preview,
            {1: {"instance_id": 0}, 2: {"instance_id": 0}},
            {1: b"a", 2: b"b"},
            {-7: {"ref": 4378}},
        )

    def test_ordinary_readiness_prepares_full_owned_roster_before_install(self):
        initialize = self.initializer()
        preview, characters, decks, monsters = self.sources()
        with patch.object(
            boss_score, "prepare_snapshot", return_value={"profile": "frozen"}
        ) as prepare, patch.object(boss_score_runtime, "install") as install:
            self.assertEqual(
                (preview, ()), initialize(preview, 4, characters, decks, monsters)
            )
        self.assertEqual((1, 2), prepare.call_args.kwargs["player_ids"])
        self.assertEqual(
            {-7: {"ref": 4378, "team": 1}}, prepare.call_args.kwargs["monsters"]
        )
        install.assert_called_once_with(preview, {"profile": "frozen"})

    def test_rift_readiness_never_reads_or_installs_boss_policy(self):
        initialize = self.initializer()
        preview, characters, decks, monsters = self.sources()
        preview.rift_wave_state = {"turn_budget": 40}
        with patch.object(boss_score, "prepare_snapshot") as prepare, patch.object(
            boss_score_runtime, "install"
        ) as install:
            self.assertEqual(
                (preview, ()), initialize(preview, 4, characters, decks, monsters)
            )
        self.store.connection.assert_not_called()
        prepare.assert_not_called()
        install.assert_not_called()

    def test_dungeon_readiness_preserves_separate_stele_initializer(self):
        initialize = self.initializer(dungeon=True)
        preview, characters, decks, monsters = self.sources()
        with patch.object(
            boss_score, "prepare_snapshot", return_value=None
        ), patch.object(boss_score_runtime, "install"), patch.object(
            dungeon_stele_states,
            "initialize",
            return_value=(preview, {}, [(13339, b"native")]),
        ) as stele:
            self.assertEqual(
                (preview, ((13339, b"native"),)),
                initialize(preview, 4, characters, decks, monsters),
            )
        self.assertEqual(2, self.store.connection.call_count)
        self.assertIs(stele.call_args.args[0], self.db)
        self.assertTrue(callable(stele.call_args.kwargs["runtime_factory"]))
