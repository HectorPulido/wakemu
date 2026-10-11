"""Transactional guild authority integration tests.

These tests are deliberately opt-in. They inherit PostgresCase so an explicit
run uses its isolated schema and migration guard; ordinary/offline test runs
never open a database, even when WAKFU_POSTGRES_TEST_URL is present.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.characters import guild_character
from wakfu_server.characters.guild_service import GuildService


class GuildServicePostgresTests(PostgresCase):
    def setUp(self):
        if os.environ.get("WAKFU_RUN_GUILD_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_GUILD_POSTGRES_TESTS=1 for isolated guild DB tests"
            )
        super().setUp()
        self.service = GuildService(self.store)
        self.policy = {
            "enabled": True,
            "native_sync_enabled": True,
            "moderation_bonus_learning_factor": 0.0,
            "owner_id_semantics": "account",
            "creation_kamas": 10000,
            "creation_item": 16942,
            "max_members": 20,
            "max_ranks": 15,
            "name_pattern": r"[A-Za-z][A-Za-z0-9 ]{2,30}",
            "name_normalization": "NFKC_CASEFOLD",
            "allowed_blazons": [123],
            "leader_permissions": (1 << 63) - 1,
            "member_permissions": 0,
            "permissions": {
                "invite": 0,
                "rank_create": 1,
                "rank_edit": 2,
                "rank_remove": 3,
                "rank_move": 4,
                "member_rank": 5,
                "kick": 6,
                "description": 7,
                "message": 8,
            },
            "invitation_seconds": 3600,
            "description_max_bytes": 500,
            "message_max_bytes": 500,
            "weekly_points_limit": 7500,
            "earned_points_limit": 0,
            "last_earning_point_week": 0,
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )

    def _player(self, label):
        suffix = "".join(chr(97 + int(char, 16)) for char in uuid.uuid4().hex[:8])
        account = self.store.register("guild_" + suffix, "guild-test-password")["id"]
        name = label + " " + suffix
        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,1,false,0,0,%s,%s,100,100) RETURNING id",
                (account, name, name.casefold(), Jsonb([0, 0, 0]), Jsonb({})),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                "VALUES(%s,1,0,64,0)",
                (character_id,),
            )
            db.execute(
                "INSERT INTO character_progression(character_id,xp) VALUES(%s,%s)",
                (character_id, 10000 + character_id),
            )
        generation = self.store.begin_session(account)
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                (character_id, account),
            )
            db.execute(
                "UPDATE account_wallets SET kamas=50000 WHERE account_id=%s", (account,)
            )
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character_id,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            item_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,16942,2,%s,%s) RETURNING uid",
                (character_id, bag, slot),
            ).fetchone()["uid"]
        return {
            "account": account,
            "character": character_id,
            "name": name,
            "xp": 10000 + character_id,
            "generation": generation,
            "item": item_uid,
        }

    def _create(self, player, name):
        return self.service.create(
            player["account"],
            player["generation"],
            player["character"],
            name,
            123,
            "Leader",
            "Member",
            operation_key="create-" + name,
        )

    def _wallet(self, account):
        with self.store.connection() as db:
            return db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]

    def _item_quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return row["quantity"] if row else 0

    def test_creation_debits_and_consumes_once_with_durable_operation_receipt(self):
        owner = self._player("Guild Owner")
        before_wallet = self._wallet(owner["account"])
        before_item = self._item_quantity(owner["item"])

        first = self._create(owner, "Guild Atomic")
        replay = self._create(owner, "Guild Atomic")

        self.assertEqual(first, replay)
        with self.assertRaisesRegex(ValueError, "different request"):
            self.service.create(
                owner["account"],
                owner["generation"],
                owner["character"],
                "Guild Other",
                123,
                "Leader",
                "Member",
                operation_key="create-Guild Atomic",
            )
        self.assertEqual(
            before_wallet - self.policy["creation_kamas"],
            self._wallet(owner["account"]),
        )
        self.assertEqual(before_item - 1, self._item_quantity(owner["item"]))
        self.assertEqual(2, len(first["ranks"]))
        self.assertEqual(1, len(first["members"]))
        with self.reopen().connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM guild_operation_receipts WHERE character_id=%s",
                    (owner["character"],),
                ).fetchone()["n"],
            )

    def test_identity_change_consumes_once_and_rolls_back_on_snapshot_failure(self):
        owner = self._player("Guild Identity")
        self._create(owner, "Guild Original")
        self.policy["identity_changes"] = {
            "name": dict(enabled=True, authority="leader", item=25101, kamas=1000),
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (owner["character"],),
            ).fetchone()["uid"]
            item = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,25101,2,%s,1) RETURNING uid",
                (owner["character"], bag),
            ).fetchone()["uid"]
        before = self._wallet(owner["account"])
        args = (owner["account"], owner["generation"], owner["character"], "name")
        first = self.service.change_identity(
            *args, "Guild Renamed", operation_key="rename-one"
        )
        replay = self.service.change_identity(
            *args, "Guild Renamed", operation_key="rename-one"
        )
        self.assertEqual(first, replay)
        self.assertEqual(before - 1000, self._wallet(owner["account"]))
        self.assertEqual(1, self._item_quantity(item))
        with patch.object(
            self.service, "_snapshot", side_effect=RuntimeError("forced rollback")
        ):
            with self.assertRaises(RuntimeError):
                self.service.change_identity(
                    *args, "Guild Rolled Back", operation_key="rename-two"
                )
        self.assertEqual(before - 1000, self._wallet(owner["account"]))
        self.assertEqual(1, self._item_quantity(item))
        with self.store.connection() as db:
            self.assertEqual(
                "Guild Renamed",
                db.execute(
                    "SELECT name FROM guilds WHERE leader_id=%s",
                    (owner["character"],),
                ).fetchone()["name"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM guild_operation_receipts WHERE character_id=%s AND operation_key=%s",
                    (owner["character"], "rename-two"),
                ).fetchone()
            )

    def test_creation_rolls_back_wallet_item_and_guild_when_snapshot_fails(self):
        owner = self._player("Guild Rollback")
        wallet, quantity = self._wallet(owner["account"]), self._item_quantity(
            owner["item"]
        )
        with patch.object(
            self.service, "_snapshot", side_effect=RuntimeError("forced rollback")
        ):
            with self.assertRaisesRegex(RuntimeError, "forced rollback"):
                self._create(owner, "Guild Rollback")

        self.assertEqual(wallet, self._wallet(owner["account"]))
        self.assertEqual(quantity, self._item_quantity(owner["item"]))
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM guilds WHERE name=%s",
                    ("Guild Rollback",),
                ).fetchone()["n"],
            )

    def test_stale_generation_cannot_create_or_debit(self):
        owner = self._player("Guild Stale")
        wallet, quantity = self._wallet(owner["account"]), self._item_quantity(
            owner["item"]
        )
        self.store.end_session(owner["account"], owner["generation"])

        with self.assertRaises(ValueError):
            self._create(owner, "Guild Stale")

        self.assertEqual(wallet, self._wallet(owner["account"]))
        self.assertEqual(quantity, self._item_quantity(owner["item"]))

    def test_invitation_replay_and_capacity_do_not_duplicate_membership(self):
        owner, member, overflow = (self._player("Guild Member") for _ in range(3))
        self.policy["max_members"] = 2
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        guild = self._create(owner, "Guild Capacity")

        invite_id = self.service.invite(
            owner["account"],
            owner["generation"],
            owner["character"],
            member["character"],
        )
        self.service.invitation_answer(
            member["account"],
            member["generation"],
            member["character"],
            invite_id,
            True,
        )
        with self.assertRaises(ValueError):
            self.service.invitation_answer(
                member["account"],
                member["generation"],
                member["character"],
                invite_id,
                True,
            )

        overflow_invite = self.service.invite(
            owner["account"],
            owner["generation"],
            owner["character"],
            overflow["character"],
        )
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.service.invitation_answer(
                overflow["account"],
                overflow["generation"],
                overflow["character"],
                overflow_invite,
                True,
            )
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM guild_members WHERE guild_id=%s",
                    (guild["guild"]["id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                "pending",
                db.execute(
                    "SELECT status FROM guild_invitations WHERE id=%s",
                    (overflow_invite,),
                ).fetchone()["status"],
            )

    def test_native_invitation_is_rebound_after_target_session_replacement(self):
        owner, target = self._player("Guild Inviter"), self._player("Guild Target")
        self._create(owner, "Guild Rebind")
        target_name = target["name"]
        first = self.service.invite(
            owner["account"], owner["generation"], owner["character"], target_name
        )

        replacement_generation = self.store.begin_session(target["account"])
        self.store.select_character(
            target["account"], replacement_generation, target["character"]
        )
        second = self.service.invite(
            owner["account"], owner["generation"], owner["character"], target_name
        )

        self.assertNotEqual(first["target_generation"], second["target_generation"])
        with self.store.connection() as db:
            invitations = db.execute(
                "SELECT target_generation,status FROM guild_invitations WHERE target_id=%s ORDER BY id",
                (target["character"],),
            ).fetchall()
        self.assertEqual(
            ["cancelled", "pending"], [row["status"] for row in invitations]
        )
        self.assertEqual(replacement_generation, invitations[1]["target_generation"])

        accepted = self.service.respond_invitation(
            target["account"], replacement_generation, target["character"], True
        )
        self.assertEqual(2, len(accepted["members"]))

    def test_concurrent_accepts_cannot_overfill_the_last_member_slot(self):
        owner, first, second = (self._player("Guild Capacity") for _ in range(3))
        self.policy["max_members"] = 2
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        guild = self._create(owner, "Guild Last Place")
        invitations = [
            self.service.invite(
                owner["account"],
                owner["generation"],
                owner["character"],
                player["character"],
            )
            for player in (first, second)
        ]
        barrier = threading.Barrier(2)

        def accept(player, invitation):
            barrier.wait(timeout=5)
            try:
                self.service.invitation_answer(
                    player["account"],
                    player["generation"],
                    player["character"],
                    invitation,
                    True,
                )
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            accepted = list(workers.map(accept, (first, second), invitations))

        self.assertEqual([False, True], sorted(accepted))
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM guild_members WHERE guild_id=%s",
                    (guild["guild"]["id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM guild_invitations WHERE guild_id=%s AND status='accepted'",
                    (guild["guild"]["id"],),
                ).fetchone()["n"],
            )

    def test_character_load_projects_xp_identity_and_clears_after_expulsion(self):
        owner, member = self._player("Guild Loader"), self._player("Guild Reload")
        self._create(owner, "Guild Reload")
        invitation = self.service.invite(
            owner["account"],
            owner["generation"],
            owner["character"],
            member["character"],
        )
        self.service.invitation_answer(
            member["account"],
            member["generation"],
            member["character"],
            invitation,
            True,
        )

        def load(character_id):
            with self.store.connection() as db:
                character = dict(
                    db.execute(
                        "SELECT * FROM characters WHERE id=%s", (character_id,)
                    ).fetchone()
                )
                guild_character.load(db, self.store, character)
                return character

        loaded = load(member["character"])
        native_member = next(
            row
            for row in loaded["guild_native"]["members"]
            if row["id"] == member["character"]
        )
        self.assertEqual(member["xp"], native_member["xp"])
        self.assertEqual(member["account"], native_member["ownerId"])
        self.assertTrue(native_member["isConnected"])

        self.service.remove_member(
            owner["account"],
            owner["generation"],
            owner["character"],
            member["character"],
        )
        expelled = load(member["character"])
        self.assertIsNone(expelled["guild_native"])
        self.assertEqual(0.0, expelled["guild_moderation_factor"])

    def test_oversize_native_metadata_rolls_back_value_and_revision(self):
        owner = self._player("Guild Metadata")
        self.policy["message_max_bytes"] = 100000
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        guild = self._create(owner, "Guild Message Size")
        guild_id = guild["guild"]["id"]
        with self.assertRaises(ValueError):
            self.service.metadata_set(
                owner["account"],
                owner["generation"],
                owner["character"],
                "message",
                "x" * 70000,
            )
        with self.store.connection() as db:
            persisted = db.execute(
                "SELECT message,revision FROM guilds WHERE id=%s", (guild_id,)
            ).fetchone()
        self.assertEqual("", persisted["message"])
        self.assertEqual(guild["guild"]["revision"], persisted["revision"])

    def test_member_permission_denial_rank_capacity_and_cross_guild_rank(self):
        owner, member, other_owner = (self._player("Guild Rank") for _ in range(3))
        guild_a = self._create(owner, "Guild Ranks A")
        guild_b = self._create(other_owner, "Guild Ranks B")
        invitation = self.service.invite(
            owner["account"],
            owner["generation"],
            owner["character"],
            member["character"],
        )
        joined = self.service.invitation_answer(
            member["account"],
            member["generation"],
            member["character"],
            invitation,
            True,
        )
        foreign_rank = guild_b["ranks"][1]["id"]

        with self.assertRaisesRegex(ValueError, "permission denied"):
            self.service.invite(
                member["account"],
                member["generation"],
                member["character"],
                other_owner["character"],
            )
        with self.assertRaisesRegex(ValueError, "permission denied"):
            self.service.rank_create(
                member["account"],
                member["generation"],
                member["character"],
                "Escalate",
                (1 << 62),
            )
        with self.assertRaisesRegex(ValueError, "Unknown guild rank"):
            self.service.member_rank(
                owner["account"],
                owner["generation"],
                owner["character"],
                member["character"],
                foreign_rank,
            )

        self.policy["max_ranks"] = 2
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.service.rank_create(
                owner["account"], owner["generation"], owner["character"], "Extra", 0
            )

        self.assertEqual(2, len(joined["members"]))
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM guild_ranks WHERE guild_id=%s",
                    (guild_a["guild"]["id"],),
                ).fetchone()["n"],
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
