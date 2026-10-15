"""Inactive sheet edits must not mutate an admitted combat actor."""
import hashlib
import pickle
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import wire
from wakfu_server.combat_actor_snapshot import build_player_snapshot
from wakfu_server.combat_state import Actor


class InactiveBuildCombatTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("inactivebuilder", "test-password")["id"]
        self.character = self.store.create_character(
            self.account, "Inactivebuilder", breed=8
        )
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.store.save_build(
            self.account, self.generation, self.character["id"], 0, self.blobs(0)
        )
        self.store.save_build(
            self.account, self.generation, self.character["id"], 1, self.blobs(1)
        )
        with self.store.connection() as db:
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight_id, self.character["id"], self.account),
            )

    def blobs(self, index, name=b"Saved sheet"):
        return dict(
            sheet=b"".join(
                wire.proto_field(tag, value)
                for tag, value in [(8, index), (18, name), (24, 1), (56, 0)]
            ),
            equipment=b"",
            deck=b"",
            aptitudes=b"",
        )

    def durable_state(self):
        with self.store.connection() as db:
            return [
                db.execute(
                    "SELECT * FROM characters WHERE id=%s", (self.character["id"],)
                ).fetchone(),
                db.execute(
                    "SELECT * FROM character_regeneration WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchall(),
                db.execute(
                    "SELECT * FROM character_mount_state WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchall(),
                db.execute(
                    "SELECT * FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone(),
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (self.character["id"],),
                ).fetchall(),
            ]

    def test_inactive_save_and_delete_preserve_snapshot_resources_and_reconnect(self):
        current = self.store.character(self.account, self.character["id"])
        actor = Actor(
            current["id"],
            0,
            (0, 0, 0),
            current["hp"],
            6,
            3,
            0,
            1,
            owner_id=self.account,
            controlled=True,
            max_hp=current["max_hp"],
        )
        snapshot = build_player_snapshot(
            current, actor, wp_current=6, wp_maximum=6, running_effects=()
        )
        snapshot.install(actor)
        frozen = hashlib.sha256(pickle.dumps(snapshot)).hexdigest()
        # The ledger uses identity equality; compare the complete serialized
        # actor state rather than a separately allocated ledger instance.
        actor_before = pickle.dumps(actor)
        state = self.durable_state()
        # These authorities must not run for an inactive sheet, even if their
        # current implementation happens to produce identical numeric values.
        with patch(
            "wakfu_server.health_policy.reconfigure",
            side_effect=AssertionError("live health rewrite"),
        ), patch(
            "wakfu_server.mount_state.reconcile_equipment",
            side_effect=AssertionError("live mount rewrite"),
        ):
            saved = self.store.save_build(
                self.account,
                self.generation,
                current["id"],
                1,
                self.blobs(1, b"Edited during fight"),
            )
            self.assertEqual(
                self.reopen().character(self.account, current["id"])["builds"][1],
                saved["builds"][1],
            )
            self.assertEqual(self.durable_state(), state)
            deleted = self.store.delete_build(
                self.account, self.generation, current["id"], 1, in_fight=True
            )
        self.assertNotIn(1, deleted["builds"])
        self.assertNotIn(
            1, self.reopen().character(self.account, current["id"])["builds"]
        )
        self.assertEqual(self.durable_state(), state)
        self.assertEqual(pickle.dumps(actor), actor_before)
        self.assertEqual(hashlib.sha256(pickle.dumps(snapshot)).hexdigest(), frozen)
        self.assertEqual(deleted["builds"][0], current["builds"][0])

    def test_active_save_rejected_by_durable_fight_and_rolls_back(self):
        before = self.store.character(self.account, self.character["id"])
        with self.assertRaisesRegex(ValueError, "Active build cannot be saved"):
            self.store.save_build(
                self.account,
                self.generation,
                before["id"],
                0,
                self.blobs(0, b"Must not save"),
            )
        self.assertEqual(
            self.store.character(self.account, before["id"])["builds"], before["builds"]
        )

    def test_active_nondefault_delete_rejected_even_with_stale_session_flag(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_build_selection SET active_index=1 WHERE character_id=%s",
                (self.character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "Active build cannot be deleted"):
            self.store.delete_build(
                self.account, self.generation, self.character["id"], 1, in_fight=False
            )
        self.assertIn(
            1, self.reopen().character(self.account, self.character["id"])["builds"]
        )
