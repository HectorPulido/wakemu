import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from wakfu_server.store import Store
from wakfu_server.combat_groups import Groups
from wakfu_server.test_console import execute


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / "world.db")
        self.account = self.store.register("console", "password")["id"]
        self.char = self.store.create_character(self.account, "Console Player")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.groups = Groups()

    def run_command(self, text):
        return execute(
            self.store, self.groups, self.account, self.generation, self.char, text
        )

    def test_item_native_delta_persistence_and_invalid_stack_no_change(self):
        result = self.run_command("!item 2021 1")
        self.assertEqual(result["packets"][0][0], 12471)
        restored = Store(self.store.path).character(self.account, self.char["id"])
        self.assertEqual(restored["inventory_items"][0]["reference"], 2021)
        with self.assertRaises(ValueError):
            self.run_command("!item 2021 32768")
        self.assertEqual(
            len(self.store.character(self.account, self.char["id"])["inventory_items"]),
            1,
        )

    def test_tp_persists_and_invalid_surface_does_not_move(self):
        with patch(
            "wakfu_server.test_console.map_geometry",
            return_value={"cells": [(1, 2, 3)], "edges": []},
        ):
            self.run_command("!tp 1385 1 2 3")
            with self.assertRaises(ValueError):
                self.run_command("!tp 1385 1 2 4")
        restored = Store(self.store.path).character(self.account, self.char["id"])
        self.assertEqual(
            tuple(restored[k] for k in ("map_id", "x", "y", "z")), (1385, 1, 2, 3)
        )

    def test_mob_native_spawn_registered_and_unique(self):
        p = tuple(self.char[k] for k in ("x", "y", "z"))
        a = (p[0] + 1, p[1], p[2])
        b = (p[0] + 2, p[1], p[2])
        geometry = {"cells": [p, a, b], "edges": [(p, a), (a, b)]}
        with patch("wakfu_server.test_console.map_geometry", return_value=geometry):
            result = self.run_command("!mob 5525 1 2")
            with self.assertRaises(ValueError):
                self.run_command("!mob 5525 1 1")
        self.assertEqual(result["world_packets"][0][0], 12608)
        self.assertEqual(len(self.groups.available(self.char["map_id"], 0)), 1)
        self.assertEqual(len({m["id"] for m in result["members"]}), 2)

    def test_stale_generation_rejects_without_grant(self):
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.run_command("!item 2021 1")
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"], []
        )

    def test_level_command_persists_native_xp_and_rejects_lower_or_stale(self):
        from wakfu_server.progression import level_xp

        result = self.run_command("!nivel 6")
        restored = Store(self.store.path).character(self.account, self.char["id"])
        self.assertEqual((restored["level"], restored["xp"]), (6, level_xp(6)))
        self.assertEqual(result["packets"][0][0], 13046)
        with self.assertRaises(ValueError):
            self.run_command("!nivel 1")
        with self.assertRaises(ValueError):
            self.run_command("!nivel 201")
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.run_command("!nivel 7")
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["level"], 6
        )

    def test_equip_unequip_and_foreign_uid_do_not_remove_owned_items(self):
        from wakfu_server.equipment import validate_sheet

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=6 WHERE id=?", (self.char["id"],))
        granted = self.run_command("!item 2021 1")["item"]
        equipped = self.run_command(f"!equip {granted['uid']} 4")
        self.assertEqual([p[0] for p in equipped["packets"]], [12284, 13046])
        char = self.store.character(self.account, self.char["id"])
        self.assertEqual(
            validate_sheet(char, bytes.fromhex(char["builds"][0]["equipment"])),
            [{"uid": granted["uid"], "slot": 4}],
        )
        with self.assertRaises(ValueError):
            self.run_command("!equip 999999999 4")
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["builds"],
            char["builds"],
        )
        self.run_command("!unequip 4")
        char = Store(self.store.path).character(self.account, self.char["id"])
        self.assertEqual(
            validate_sheet(char, bytes.fromhex(char["builds"][0]["equipment"])), []
        )
        self.assertEqual(len(char["inventory_items"]), 1)
