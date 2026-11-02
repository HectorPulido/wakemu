"""Source-backed encounter actions cannot turn arbitrary INTERACT into a fight."""
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

BASE = Path(__file__).resolve().parent
from wakfu_server import combat_encounter_world_action_start as subject


class EncounterWorldActionTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(
            (BASE / "fixtures/native_encounter_world_action_start.json").read_text()
        )
        self.character = dict(
            id=7, account_id=3, map_id=443, instance_id=10000, x=-28, y=-2, z=0
        )
        instance = dict(
            instance_id=10000,
            party_id=500,
            status="active",
            context_route_key=fixture["config"]["route"]["key"],
            context_policy_version=5,
        )
        progress = dict(
            instance_id=10000,
            party_id=500,
            status="active",
            current_room=1,
            catalog_hash=fixture["config"]["compiled_plan"]["document_sha256"],
            rooms=fixture["rooms"],
        )
        self.group = dict(
            key=(443, 10000, 900), members=fixture["members"], status="available"
        )
        self.args = dict(
            instance=instance,
            progress=progress,
            membership=dict(
                instance_id=10000, party_id=500, character_id=7, status="active"
            ),
            spawn=dict(instance_id=10000, room_order=1, asset_map_id=443, group_id=900),
            group=self.group,
            config=fixture["config"],
        )
        self.args["native_source"] = lambda ref: fixture["native"][str(ref)]
        self.request = struct.pack(">qq", self.group["members"][0]["id"], 254)

    def admit(self):
        return subject.admit_records(self.character, self.request, **self.args)

    def test_original_action_admits_same_actual_seven_native_members(self):
        before = deepcopy(self.args)
        result = self.admit()
        self.assertEqual(result["target_id"], self.group["members"][0]["id"])
        self.assertEqual(result["group_key"], self.group["key"])
        self.assertEqual(
            result["native_response"],
            (12421, struct.pack(">qqq", result["target_id"], 7, 254)),
        )
        self.assertEqual(self.args, before)
        self.assertEqual(
            [m["hp"] for m in self.group["members"]], [4, 4, 4, 4, 5, 5, 10]
        )

    def test_stale_instance_progress_membership_and_group_are_rejected(self):
        for section, key, value in [
            ("instance", "status", "closed"),
            ("progress", "status", "completed"),
            ("membership", "status", "returned"),
            ("membership", "character_id", 78),
            ("spawn", "room_order", 2),
            ("spawn", "group_id", 999),
            ("group", "status", "fighting"),
        ]:
            with self.subTest(section=section, key=key):
                old = self.args[section][key]
                self.args[section][key] = value
                with self.assertRaises(ValueError):
                    self.admit()
                self.args[section][key] = old

    def test_foreign_target_and_malformed_payload_are_rejected(self):
        for body in (
            b"",
            b"\0" * 15,
            struct.pack(">qq", 76, 254),
            struct.pack(">qq", -999, 254),
            struct.pack(">qq", self.group["members"][0]["id"], 660),
        ):
            with self.subTest(body=body):
                self.request = body
                with self.assertRaises(ValueError):
                    self.admit()

    def test_changed_native_roster_and_action_source_are_rejected(self):
        self.group["members"][0]["ref"] = 2048
        with self.assertRaises(ValueError):
            self.admit()
        self.setUp()
        original = self.args["native_source"]
        for key, value in [
            ("aGJ", 4),
            ("clT", "IsAchievementComplete(1)"),
            ("clx", 999),
            ("csJ", True),
        ]:

            def changed(ref):
                row = deepcopy(original(ref))
                row["world_actions"][0][key] = value
                return row

            self.args["native_source"] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.admit()

    def test_ordinary_interact_route_is_left_for_existing_consumers(self):
        self.args["instance"]["context_route_key"] = "ordinary-quest-scene"
        self.assertIsNone(self.admit())

    def test_missing_configuration_fails_closed(self):
        for config in ({}, None, {"route": {}}):
            self.args["config"] = config
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.admit()

    def test_no_sql_or_catalog_work_while_group_lock_is_held(self):
        tree = ast.parse((BASE.parent / "local_game_server.py").read_text())
        function = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "prepare_native_encounter_world_action"
        )
        locks = [
            n
            for n in ast.walk(function)
            if isinstance(n, ast.With)
            and any(
                "COMBAT_GROUPS.lock" in ast.unparse(i.context_expr) for i in n.items
            )
        ]
        self.assertEqual(len(locks), 1)
        source = "\n".join(ast.unparse(n) for n in locks[0].body)
        self.assertNotIn("prepare(STORE", source)
        self.assertIn("deepcopy(", source)

    def test_plan_and_source_scope_are_sealed(self):
        self.args["config"]["compiled_plan"]["rooms"][0]["monsters"][0]["count"] = 3
        with self.assertRaises(ValueError):
            self.admit()
        self.setUp()
        self.args["progress"]["catalog_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            self.admit()

    def test_current_public_13222_branch_reuses_existing_combat_producer(self):
        tree = ast.parse((BASE.parent / "local_game_server.py").read_text())
        branches = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and any(
                isinstance(x, ast.NamedExpr)
                and isinstance(x.target, ast.Name)
                and x.target.id == "encounter_world_action"
                for x in ast.walk(n.test)
            )
        ]
        self.assertEqual(len(branches), 1)
        body = "\n".join(ast.unparse(n) for n in branches[0].body)
        for name in (
            "combat_group_for_target",
            "create_placement",
            "COMBAT_GROUPS.claim",
            "COMBAT_SESSIONS.register",
            "native_encounter_world_action_started",
        ):
            self.assertIn(name, body)
        self.assertNotIn("world_property_counts", body)


if __name__ == "__main__":
    unittest.main()
