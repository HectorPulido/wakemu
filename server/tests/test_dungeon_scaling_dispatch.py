"""Fight-entry integration boundary for frozen dungeon scaling."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from wakfu_server import dungeon_scaling_entry


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def calls(node, name):
    return [
        current
        for current in ast.walk(node)
        if isinstance(current, ast.Call)
        and isinstance(current.func, ast.Name)
        and current.func.id == name
    ]


def attribute_calls(node, value):
    return [
        current
        for current in ast.walk(node)
        if isinstance(current, ast.Call)
        and isinstance(current.func, ast.Attribute)
        and isinstance(current.func.value, ast.Name)
        and current.func.value.id == value
    ]


class DungeonScalingEntryTests(unittest.TestCase):
    class Database:
        def __init__(self, encounter):
            self.encounter = encounter
            self.queries = []

        def execute(self, query, params):
            self.queries.append((query, params))
            return self

        def fetchone(self):
            return self.encounter

    def test_missing_catalog_without_encounter_preserves_original_fight(self):
        fight = Mock(id=12)
        db = self.Database(None)
        with patch(
            "wakfu_server.maps.dungeon_scaling_catalog.load", return_value=None
        ), patch("wakfu_server.maps.dungeon_combat_scaling.initialize") as initialize:
            result, receipt = dungeon_scaling_entry.initialize(db, fight, {})
        self.assertIs(result, fight)
        self.assertIsNone(receipt)
        initialize.assert_not_called()
        self.assertIn("dungeon_encounter_difficulties", db.queries[0][0])
        self.assertEqual(db.queries[0][1], (12,))

    def test_frozen_encounter_without_scaling_catalog_fails_closed(self):
        db = self.Database({"fight_id": 12})
        with patch(
            "wakfu_server.maps.dungeon_scaling_catalog.load", return_value=None
        ), self.assertRaisesRegex(ValueError, "no scaling catalog"):
            dungeon_scaling_entry.initialize(db, Mock(id=12), {})

    def test_native_runtime_factory_uses_canonical_npc_constructor_runtime(self):
        fight = Mock(id=12)
        preview = Mock(name="private-placement-preview")
        monsters = {88: {"id": 88, "ref": 1}}
        catalog = {"effects": {"native": True}}
        dispatcher = object()
        runtime_factory = Mock(return_value=(dispatcher, object()))
        receipt = {"initialized": True}

        def initialize(_db, _fight, _monsters, *, catalog, runtime_factory):
            self.assertEqual(catalog, {"effects": {"native": True}})
            return runtime_factory(preview, 88), receipt

        with patch(
            "wakfu_server.maps.dungeon_scaling_catalog.load", return_value=catalog
        ), patch(
            "wakfu_server.combat.combat_npc_initialization._runtime",
            return_value=(runtime_factory, object()),
        ) as native_runtime, patch(
            "wakfu_server.maps.dungeon_combat_scaling.initialize",
            side_effect=initialize,
        ) as scale:
            result, actual_receipt = dungeon_scaling_entry.initialize(
                self.Database(None), fight, monsters
            )

        self.assertIs(result, dispatcher)
        self.assertIs(actual_receipt, receipt)
        native_runtime.assert_called_once_with(monsters, 88)
        runtime_factory.assert_called_once_with(
            preview, {"native_retained_container": {"present": False}}
        )
        scale.assert_called_once()


class DungeonScalingFightEntryAstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = ast.parse(SERVER_SOURCE.read_text())
        cls.session = next(
            node
            for node in cls.module.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )

    def test_scaling_runs_after_snapshot_initialization_before_registration(self):
        placements = calls(self.session, "create_placement")
        snapshots = calls(self.session, "initialize_fight_snapshots")
        scaling = calls(self.session, "initialize_dungeon_scaling")
        claims = [
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "COMBAT_GROUPS"
            and node.func.attr == "claim"
        ]
        placements_messages = calls(self.session, "placement_messages")
        registrations = [
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "COMBAT_SESSIONS"
            and node.func.attr == "register"
        ]
        self.assertEqual(len(placements), 1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(len(scaling), 1)
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(placements_messages), 1)
        self.assertEqual(len(registrations), 1)
        ordered = [
            placements[0].lineno,
            snapshots[0].lineno,
            scaling[0].lineno,
            claims[0].lineno,
            placements_messages[0].lineno,
            registrations[0].lineno,
        ]
        self.assertEqual(ordered, sorted(ordered))

    def test_durable_binding_passes_current_selection_revision(self):
        binding = next(
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.FunctionDef) and node.name == "dungeon_binding"
        )
        bind = next(node for node in calls(binding, "bind_room_group"))
        keyword = next(
            item for item in bind.keywords if item.arg == "expected_selection_revision"
        )
        self.assertIsInstance(keyword.value, ast.IfExp)
        self.assertIsInstance(keyword.value.test, ast.Compare)
        self.assertIsInstance(keyword.value.body, ast.Constant)
        self.assertIsNone(keyword.value.body.value)
        self.assertIsInstance(keyword.value.orelse, ast.Subscript)
        self.assertEqual(keyword.value.orelse.value.id, "profile")
        self.assertEqual(
            ast.literal_eval(keyword.value.orelse.slice), "selection_revision"
        )

    def test_scaled_actors_rebuild_actual_stats_and_initial_effects_before_wire(self):
        branch = next(
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and calls(node, "should_rebuild_placement")
            and any(
                isinstance(current, ast.Call)
                and isinstance(current.func, ast.Name)
                and current.func.id == "getattr"
                and len(current.args) > 1
                and isinstance(current.args[1], ast.Constant)
                and current.args[1].value == "native_dungeon_scaling_receipt"
                for current in ast.walk(node.test)
            )
        )
        actual_stats = calls(branch, "actual_monster_actor_stats")
        initial_effects = calls(branch, "initial_npc_actor_effects")
        packets = calls(branch, "placement_messages")
        self.assertEqual(
            (len(actual_stats), len(initial_effects), len(packets)), (1, 1, 1)
        )
        self.assertLess(actual_stats[0].lineno, initial_effects[0].lineno)
        self.assertLess(initial_effects[0].lineno, packets[0].lineno)
        receipt_guards = [
            current
            for current in ast.walk(branch)
            if isinstance(current, ast.Call)
            and isinstance(current.func, ast.Name)
            and current.func.id == "getattr"
            and len(current.args) > 1
            and isinstance(current.args[1], ast.Constant)
            and current.args[1].value == "native_dungeon_scaling_receipt"
        ]
        self.assertGreaterEqual(len(receipt_guards), 2)


if __name__ == "__main__":
    unittest.main()
