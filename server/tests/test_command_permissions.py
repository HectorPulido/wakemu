import json
import unittest
from postgres_case import PostgresCase
from wakfu_server.command_permissions import (
    authorize_command,
    is_admin,
    set_admin,
    PUBLIC_COMMANDS_SETTING,
)
from wakfu_server.test_console import execute


class CommandPermissionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("permissions", "password")["id"]
        self.character = self.store.create_character(self.account, "Permissions Test")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def test_registration_does_not_grant_admin_and_forbidden_grant_has_no_effect(self):
        self.assertFalse(is_admin(self.store, self.account))
        authorize_command(self.store, self.account, "!pos")
        with self.assertRaises(PermissionError):
            execute(
                self.store,
                None,
                self.account,
                self.generation,
                self.character,
                "!item 2021 1",
            )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            [],
        )

    def test_english_aliases_preserve_the_existing_authorization(self):
        authorize_command(self.store, self.account, "!help")
        authorize_command(self.store, self.account, "!position")
        for text in ("!level 50", "!teleport 527 -245 -89 0", "!monster 1 1 1"):
            with self.assertRaises(PermissionError):
                authorize_command(self.store, self.account, text)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (json.dumps(["!level"]), PUBLIC_COMMANDS_SETTING),
            )
        authorize_command(self.store, self.account, "!level 50")
        authorize_command(self.store, self.account, "!nivel 50")

    def test_admin_revocation_is_immediate_and_audited(self):
        set_admin(self.store, self.account, True, operator="test", reason="grant")
        authorize_command(self.store, self.account, "!item 2021 1")
        set_admin(self.store, self.account, False, operator="test", reason="revoke")
        with self.assertRaises(PermissionError):
            authorize_command(self.store, self.account, "!item 2021 1")
        with self.store.connection() as db:
            self.assertEqual(
                [
                    r["is_admin"]
                    for r in db.execute(
                        "SELECT is_admin FROM admin_role_audit ORDER BY id"
                    )
                ],
                [1, 0],
            )
        self.assertFalse(is_admin(self.reopen(), self.account))

    def test_database_allowlist_is_live_and_invalid_policy_fails_closed(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (json.dumps(["!item"]), PUBLIC_COMMANDS_SETTING),
            )
        authorize_command(self.store, self.account, "!item 2021 1")
        with self.assertRaises(PermissionError):
            authorize_command(self.store, self.account, "!pos")
        for value in ("{}", "[1]", '["!item 2021"]'):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE settings SET value=%s WHERE name=%s",
                    (value, PUBLIC_COMMANDS_SETTING),
                )
            with self.assertRaises(PermissionError):
                authorize_command(self.store, self.account, "!item 2021 1")

    def test_reopening_keeps_role_and_operator_is_required(self):
        set_admin(self.store, self.account, True, operator="test", reason="grant")
        self.assertTrue(is_admin(self.reopen(), self.account))
        with self.assertRaises(ValueError):
            set_admin(self.store, self.account, False, operator="", reason="")
        self.assertTrue(is_admin(self.store, self.account))

    def test_public_astrub_uses_fixed_native_destination_without_tp_rights(self):
        authorize_command(self.store, self.account, "!astrub")
        with self.assertRaises(PermissionError):
            authorize_command(self.store, self.account, "!tp 527 0 32 0")
        outcome = execute(
            self.store,
            None,
            self.account,
            self.generation,
            self.character,
            "!astrub",
        )
        self.assertEqual(outcome["action"], "tp")
        self.assertEqual(
            {
                key: outcome["character"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            },
            dict(map_id=527, instance_id=0, x=0, y=32, z=0),
        )
        for command in ("!astrub Other", "!astrub 1134 -10 -10 -1"):
            with self.assertRaises(ValueError):
                execute(
                    self.store,
                    None,
                    self.account,
                    self.generation,
                    outcome["character"],
                    command,
                )
