"""Regression coverage for the live native stele selection/readiness boundary."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Fight
import test_combat_spell_transaction as fixture_module


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class DungeonSteleDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(SERVER))

    def test_selection_opcode_rejects_fight_bag_and_spectator(self):
        branch = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12686 and loaded"
        )
        code = ast.unparse(branch)
        self.assertIn("fight is not None", code)
        self.assertIn("spectator_session is not None", code)
        self.assertIn("bag_session is not None", code)
        self.assertIn("dungeon_stele.activate(", code)
        self.assertLess(
            code.index("dungeon_stele.activate("), code.index("STORE.character(")
        )
        self.assertIn("dungeon_stele_selection_rejected", code)

    def test_native_stele_browse_and_close_are_interaction_guarded(self):
        branch = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test).startswith("target_action in (12, 13) and any(")
        )
        code = ast.unparse(branch)
        self.assertIn("dungeon_stele.definition(", code)
        self.assertIn("dungeon_stele.browse(", code)
        self.assertIn("dungeon_stele.close(", code)
        self.assertIn("fight is not None", code)
        self.assertIn("spectator_session is not None", code)
        self.assertIn("bag_session is not None", code)
        self.assertIn("dungeon_stele.cancel_packet(character['id'])", code)
        self.assertIn("continue", code)
        outer = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12870 and len(body) == 12"
        )
        self.assertIn("target_action in (12, 13)", ast.unparse(outer))

    def test_readiness_dispatch_installs_native_states_only_for_dungeon_encounters(
        self,
    ):
        function = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == "apply_readiness"
        )
        code = ast.unparse(function)
        self.assertIn("initialize_encounter_states", code)
        self.assertIn("is_dungeon_run(source.get('instance_id', 0))", code)
        self.assertIn("initialize_stele_states(", code)
        self.assertIn("server_runtime(", code)
        self.assertIn("player_characters=characters", code)
        self.assertIn("deck_blobs=decks", code)
        self.assertIn("encounter_initializer=", code)
        self.assertIn("COMBAT_SESSIONS.ready_transition(", code)

    def test_production_nested_stele_and_scaling_imports_execute(self):
        import importlib
        import sys

        stele = importlib.import_module("wakfu_server.maps.dungeon_stele")
        stele_states = importlib.import_module("wakfu_server.maps.dungeon_stele_states")
        scaling_entry = importlib.import_module(
            "wakfu_server.maps.dungeon_scaling_entry"
        )
        self.assertTrue(
            all(
                callable(getattr(stele, name))
                for name in ("activate", "browse", "close")
            )
        )
        self.assertTrue(callable(stele_states.initialize))

        class EmptyResult:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        class EmptyEncounterDb:
            def execute(self, query, params=()):
                if "settings" in query or "dungeon_encounter_difficulties" in query:
                    return EmptyResult(None)
                if "to_regclass" in query:
                    return EmptyResult({"relation": None})
                raise AssertionError(f"Unexpected production import query: {query}")

        fight = SimpleNamespace(id=7)
        db = EmptyEncounterDb()
        self.assertEqual(scaling_entry.initialize(db, fight, {}), (fight, None))
        self.assertEqual(
            stele_states.initialize(db, fight, {}, runtime_factory=None),
            (fight, None, []),
        )
        nested_scaling = importlib.import_module(
            "wakfu_server.maps.dungeon_combat_scaling"
        )
        self.assertIs(
            sys.modules["wakfu_server.maps.dungeon_combat_scaling"], nested_scaling
        )
        self.assertIsNot(
            nested_scaling,
            importlib.import_module("wakfu_server.dungeon_combat_scaling"),
        )

    def test_ready_transition_runs_encounter_initializer_on_active_preview_before_owner_start(
        self,
    ):
        with patch.object(Fight, "ready"):
            (
                character,
                monster,
                fight,
            ) = fixture_module.SpellTransactionTests().native_server_fixture(
                16, 60, native_qi=True
            )
        from wakfu_server.monsters import owned_instance

        monster = owned_instance(5525, 1, -7, map_id=1134, x=1, y=0, z=0)
        characters = {7: character}

        class SnapshotStore:
            def character(self, account_id, character_id):
                value = characters[character_id]
                if value["account_id"] != account_id:
                    raise ValueError("wrong owner")
                return deepcopy(value)

        adapter = CombatSessionAdapter(SnapshotStore())
        session = Session(
            character["account_id"], 7, "generation", character["map_id"], 0
        )
        sequence = []
        original = __import__(
            "wakfu_server.combat_server_spell",
            fromlist=["prepare_server_initialization"],
        ).prepare_server_initialization

        def encounter(preview, action_id, roster, decks):
            sequence.append(
                (
                    "encounter",
                    preview.phase,
                    preview.turn_id,
                    preview.native_start_event_delivered,
                    tuple(roster),
                    tuple(decks),
                )
            )
            preview.stele_test_receipt = {"action_id": action_id}
            return preview, ((13436, b"native-stele"),)

        def owner_start(source, monsters, preview, owner_id, deck, **kwargs):
            sequence.append(
                (
                    "owner",
                    preview.phase,
                    preview.turn_id,
                    getattr(preview, "stele_test_receipt", None),
                )
            )
            return original(source, monsters, preview, owner_id, deck, **kwargs)

        with patch(
            "wakfu_server.combat_server_spell.prepare_server_initialization",
            side_effect=owner_start,
        ):
            transition = adapter.ready_transition(
                session,
                fight,
                None,
                True,
                {monster["id"]: monster},
                fight_start=False,
                encounter_initializer=encounter,
            )
        self.assertEqual(transition.fight.phase, "active")
        self.assertEqual(sequence[0][:4], ("encounter", "active", 1, False))
        self.assertEqual(sequence[1], ("owner", "active", 1, {"action_id": 1}))
        self.assertIn((13436, b"native-stele"), transition.packets)
        self.assertEqual(fight.phase, "placement")
        self.assertFalse(hasattr(fight, "stele_test_receipt"))

    def test_encounter_initializer_failure_rolls_back_readiness_preview(self):
        with patch.object(Fight, "ready"):
            (
                character,
                monster,
                fight,
            ) = fixture_module.SpellTransactionTests().native_server_fixture(
                16, 60, native_qi=True
            )
        from wakfu_server.monsters import owned_instance

        monster = owned_instance(5525, 1, -7, map_id=1134, x=1, y=0, z=0)

        class SnapshotStore:
            def character(self, account_id, character_id):
                return deepcopy(character)

        adapter = CombatSessionAdapter(SnapshotStore())
        session = Session(
            character["account_id"], 7, "generation", character["map_id"], 0
        )
        before = (
            fight.phase,
            set(fight.ready_owners),
            tuple(fight.order),
            fight.turn_id,
        )

        def fail(preview, action_id, characters, decks):
            preview.stele_test_partial = True
            raise ValueError("native stele state unsupported")

        with self.assertRaisesRegex(ValueError, "native stele state unsupported"):
            adapter.ready_transition(
                session,
                fight,
                None,
                True,
                {monster["id"]: monster},
                fight_start=False,
                encounter_initializer=fail,
            )
        self.assertEqual(
            (fight.phase, set(fight.ready_owners), tuple(fight.order), fight.turn_id),
            before,
        )
        self.assertFalse(hasattr(fight, "stele_test_partial"))


if __name__ == "__main__":
    unittest.main()
