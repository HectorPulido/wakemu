import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.combat_groups import Groups
from wakfu_server.test_console import execute, parse_target


class TargetParserTests(unittest.TestCase):
    def test_supported_commands_accept_quoted_or_prefixed_final_target(self):
        for command in (
            "!level 50",
            "!item 2021 1",
            "!monster 5525 1 2",
            "!teleport 527 1 2 3",
            "!kamas 100",
        ):
            base, target = parse_target(command)
            self.assertIsNone(target)
            self.assertEqual(
                parse_target(command + ' "Prueba Oficios"'), (base, "Prueba Oficios")
            )
            self.assertEqual(parse_target(command + " @Npers"), (base, "Npers"))

    def test_invalid_argument_counts_and_empty_targets_are_rejected(self):
        for command in (
            "!item 1",
            "!kamas 2 @",
            '!level 5 ""',
            "!tp 527 1 2 3 A B",
            "!level fish @Npers",
        ):
            with self.subTest(command=command), self.assertRaises(ValueError):
                parse_target(command)


class ConsoleTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("console", "password")["id"]
        from wakfu_server.command_permissions import set_admin

        set_admin(self.store, self.account, True, operator="test", reason="fixture")
        self.char = self.store.create_character(self.account, "Console Player")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.groups = Groups()

    def run_command(self, text):
        return execute(
            self.store, self.groups, self.account, self.generation, self.char, text
        )

    def test_kamas_absolute_wallet_packet_and_durable_addition(self):
        import struct

        before = self.store.character(self.account, self.char["id"])["kamas"]
        result = self.run_command("!kamas 1234")
        self.assertEqual(result["packets"], [(12753, struct.pack(">q", before + 1234))])
        self.assertEqual(
            self.reopen().character(self.account, self.char["id"])["kamas"],
            before + 1234,
        )
        for invalid in (0, -1, 1 << 63, (1 << 63) - 1):
            with self.assertRaises(ValueError):
                self.run_command(f"!kamas {invalid}")
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["kamas"], before + 1234
        )

    def test_administrator_can_credit_target_but_nonadmin_issuer_cannot(self):
        other = self.store.register("console-target", "password")["id"]
        target = self.store.create_character(other, "Target Player")
        generation = self.store.begin_session(other)
        self.store.select_character(other, generation, target["id"])
        result = execute(
            self.store,
            self.groups,
            other,
            generation,
            target,
            "!kamas 100",
            authorized_by=self.account,
        )
        self.assertEqual(result["character"]["kamas"], 100)
        with self.assertRaises(PermissionError):
            execute(
                self.store,
                self.groups,
                self.account,
                self.generation,
                self.char,
                "!kamas 100",
                authorized_by=other,
            )

    def test_item_native_delta_persistence_and_invalid_stack_no_change(self):
        result = self.run_command("!item 2021 1")
        self.assertEqual(result["packets"][0][0], 12471)
        restored = self.reopen().character(self.account, self.char["id"])
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
        restored = self.reopen().character(self.account, self.char["id"])
        self.assertEqual(
            tuple(restored[k] for k in ("map_id", "x", "y", "z")), (1385, 1, 2, 3)
        )

    def test_mob_native_spawn_registered_and_unique(self):
        p = tuple(self.char[k] for k in ("x", "y", "z"))
        a = (p[0] + 1, p[1], p[2])
        b = (p[0] + 2, p[1], p[2])
        from wakfu_server.combat_geometry import prepare_geometry

        geometry = prepare_geometry(
            {
                "map_id": self.char["map_id"],
                "cells": [p, a, b],
                "edges": [(p, a), (a, b)],
            }
        )
        with patch(
            "wakfu_server.test_console.published_geometry", return_value=geometry
        ):
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
        restored = self.reopen().character(self.account, self.char["id"])
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
        from wakfu_server.progression import level_xp

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=6 WHERE id=%s", (self.char["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(6), self.char["id"]),
            )
        granted = self.run_command("!item 2021 1")["item"]
        equipped = self.run_command(f"!equip {granted['uid']} 4")
        self.assertEqual(
            [p[0] for p in equipped["packets"]], [12284, 12393, 12103, 13046]
        )
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
        char = self.reopen().character(self.account, self.char["id"])
        self.assertEqual(
            validate_sheet(char, bytes.fromhex(char["builds"][0]["equipment"])), []
        )
        self.assertEqual(len(char["inventory_items"]), 1)

    def test_level_snapshot_failure_rolls_back_progression_and_health(self):
        before = self.store.character(self.account, self.char["id"])
        with patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            side_effect=ValueError("Injected snapshot failure"),
        ):
            with self.assertRaises(ValueError):
                self.run_command("!nivel 50")
        after = self.store.character(self.account, self.char["id"])
        for key in ("level", "xp", "hp", "max_hp", "builds"):
            self.assertEqual(after[key], before[key])

    def test_fixed_aptitude_level_survives_49_to_50(self):
        from wakfu_server import builds
        from wakfu_server.wire import proto_field

        self.run_command("!nivel 49")
        metadata = b"".join(
            proto_field(t, v)
            for t, v in [(8, 0), (18, b"Fixed"), (24, 49), (56, 1), (64, 1)]
        )
        self.store.save_build(
            self.account,
            self.generation,
            self.char["id"],
            0,
            dict(
                sheet=metadata,
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=proto_field(24, 49),
            ),
        )
        before = self.store.character(self.account, self.char["id"])
        result = self.run_command("!nivel 50")
        after = self.store.character(self.account, self.char["id"])
        self.assertEqual(after["level"], 50)
        self.assertEqual(result["character"]["effective_level"], 49)
        self.assertGreaterEqual(after["xp"], before["xp"])
        # The native build unlock boundary is 51. Crossing it must not
        # invalidate a lower fixed sheet or recompute its HP from level 51.
        result = self.run_command("!nivel 51")
        at_unlock = self.store.character(self.account, self.char["id"])
        self.assertEqual(at_unlock["level"], 51)
        self.assertEqual(result["character"]["effective_level"], 49)
        for key in ("hp", "max_hp", "builds"):
            self.assertEqual(at_unlock[key], before[key])
        with self.assertRaises(ValueError):
            self.run_command("!nivel 50")
        after_rejected_downgrade = self.store.character(self.account, self.char["id"])
        self.assertEqual(after_rejected_downgrade["level"], 51)
        self.assertEqual(after_rejected_downgrade["xp"], at_unlock["xp"])
        self.assertEqual(after_rejected_downgrade["builds"], at_unlock["builds"])
        self.assertEqual(
            self.reopen().character(self.account, self.char["id"])["builds"],
            at_unlock["builds"],
        )
