"""Native guild chest session, exact ACLs and atomic account/shared custody."""
import struct
from datetime import timedelta
from unittest.mock import patch
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_guild_service_postgres as guild_fixture
from wakfu_server.guild_service import GuildService
from wakfu_server.guild_native_validators import encode_blazon
from wakfu_server.guild_primary_policy import management_policy
from wakfu_server.guild_storage_policy import storage_policy, catalog
from wakfu_server import guild_progression, guild_economy
from wakfu_server.guild_chest_dispatch import GuildChestSession
from wakfu_server import guild_chest


class GuildStorageNativePostgresTests(PostgresCase):
    _player = guild_fixture.GuildServicePostgresTests._player
    _create = guild_fixture.GuildServicePostgresTests._create

    def setUp(self):
        super().setUp()
        self.service = GuildService(self.store)
        self.blazon = encode_blazon(
            emblem_id=1, background_id=2, background_color=3, emblem_color=4
        )
        self.policy = guild_progression.progression_policy(
            storage_policy(management_policy(enabled=True), enabled=True), enabled=True
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        self.owner = self._player("Storage Owner")
        self.member = self._player("Storage Member")
        self.guild_id = self._create(self.owner, "Native Storage Guild")["guild"]["id"]
        invitation = self.service.invite_character(
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.member["character"],
        )
        self.service.invitation_answer(
            self.member["account"],
            self.member["generation"],
            self.member["character"],
            invitation,
            True,
        )
        self.point = next(row for row in catalog()["chests"] if row["map_id"] == 527)
        self.objects = [
            dict(
                id=self.point["object_id"],
                map_id=527,
                type="GuildStorageBox",
                **dict(zip(("x", "y", "z"), self.point["object_position"]))
            )
        ]
        self.body = struct.pack(">qHH", self.point["object_id"], 12, 0)
        self.characters = {}
        with self.store.connection() as db:
            for player in (self.owner, self.member):
                pos = self.point["use_cells"][0]
                db.execute(
                    "UPDATE characters SET map_id=527,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (*pos, player["character"]),
                )
                self.characters[player["character"]] = dict(
                    id=player["character"],
                    map_id=527,
                    instance_id=0,
                    **dict(zip(("x", "y", "z"), pos))
                )
            self.bags = {
                p["character"]: db.execute(
                    "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                    (p["character"],),
                ).fetchone()["uid"]
                for p in (self.owner, self.member)
            }
            self.uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,2504,9,%s,2) RETURNING uid",
                (self.owner["character"], self.bags[self.owner["character"]]),
            ).fetchone()["uid"]
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,false,2504)",
                (self.uid,),
            )

    def learn_base(self):
        now = self.store.now()
        with self.store.connection() as db:
            db.execute(
                "UPDATE guilds SET level=4,current_points=3000 WHERE id=%s",
                (self.guild_id,),
            )
            db.execute(
                "UPDATE sessions SET expires_at=CURRENT_TIMESTAMP+interval '2 days' WHERE account_id IN (%s,%s)",
                (self.owner["account"], self.member["account"]),
            )
        with patch.object(self.store, "now", return_value=now):
            pending = guild_economy.bonus_operation(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                self.guild_id,
                11,
                activate=False,
                operation_key="storage-native-learn-11",
            )
        self.assertEqual(pending["points"], 0)
        self.assertEqual(
            pending["bonus"]["learned_at_ms"] - pending["bonus"]["purchased_at_ms"],
            16 * 60 * 60 * 1000,
        )
        with patch.object(
            self.store, "now", return_value=now + timedelta(hours=16, seconds=1)
        ):
            self.assertIn(
                self.guild_id,
                {identity for identity, _ in guild_progression.tick(self.store)},
            )

    def test_all_native_compartments_locked_until_real_base_bonus_learning(self):
        locked = self.session(self.owner)
        self.assertEqual([row["enabled"] for row in locked.chests], [False] * 4)
        with self.assertRaises(ValueError):
            self.handle(locked, self.owner, self.item_body(0, self.owner))
        self.learn_base()
        opened = self.session(self.owner)
        self.assertEqual(
            [row["enabled"] for row in opened.chests], [True, False, False, False]
        )
        result, _ = self.handle(opened, self.owner, self.item_body(0, self.owner))
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT unlocked_compartments FROM guilds WHERE id=%s",
                    (self.guild_id,),
                ).fetchone()["unlocked_compartments"],
                [0],
            )

    def session(self, player):
        return GuildChestSession(
            self.store,
            player["account"],
            player["generation"],
            self.characters[player["character"]],
            self.body,
            self.objects,
        )

    def handle(self, session, player, body):
        return session.handle(
            12531, body, self.characters[player["character"]], self.objects
        )

    def item_body(self, operation, player, *, slot=0):
        body = struct.pack(">ibqih", 0, operation, self.uid, 2504, 9)
        if operation == 1:
            body += struct.pack(">q", self.bags[player["character"]])
        return body + struct.pack(">b", slot)

    def rank_mask(self, mask):
        owner = (
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
        )
        if not hasattr(self, "custodian_rank"):
            result = self.service.rank_create(*owner, "Custodian", mask)
            self.custodian_rank = next(
                row["id"] for row in result["ranks"] if row["name"] == "Custodian"
            )
            self.service.member_rank(
                *owner, self.member["character"], self.custodian_rank
            )
        else:
            self.service.rank_edit(*owner, self.custodian_rank, "Custodian", mask)

    def test_native_session_member_deposit_scoped_withdraw_replay_and_reconnect(self):
        self.learn_base()
        owner, member = self.session(self.owner), self.session(self.member)
        self.assertEqual(
            [row["enabled"] for row in owner.chests], [True, False, False, False]
        )
        deposited, packets = self.handle(
            owner, self.owner, self.item_body(0, self.owner)
        )
        self.assertTrue(deposited["applied"])
        replay, _ = self.handle(owner, self.owner, self.item_body(0, self.owner))
        self.assertFalse(replay["applied"])
        member.refresh()
        with self.assertRaisesRegex(ValueError, "permission denied"):
            self.handle(member, self.member, self.item_body(1, self.member, slot=3))
        # A rejected native request closes the World chest session. Recreate
        # the session before the next request so its planned source snapshot is
        # not reused after the successful move below.
        member = self.session(self.member)
        # A zero-right member may rearrange shared items without taking custody.
        moved, _ = self.handle(
            member, self.member, struct.pack(">ibqb", 0, 2, self.uid, 1)
        )
        self.assertTrue(moved["applied"])
        self.rank_mask(1 << 11)
        member.refresh()
        taken, _ = self.handle(
            member, self.member, self.item_body(1, self.member, slot=3)
        )
        self.assertTrue(taken["applied"])
        again, _ = self.handle(
            member, self.member, self.item_body(1, self.member, slot=3)
        )
        self.assertFalse(again["applied"])
        reopened = self.reopen()
        with reopened.connection() as db:
            item = db.execute(
                "SELECT character_id,quantity FROM inventory_items WHERE uid=%s",
                (self.uid,),
            ).fetchone()
            self.assertEqual(
                (item["character_id"], item["quantity"]), (self.member["character"], 9)
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE uid=%s",
                    (self.uid,),
                ).fetchone()["n"],
                1,
            )
            binding = db.execute(
                "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
                (self.uid,),
            ).fetchone()
            self.assertEqual(
                (binding["bound"], binding["template_reference"]), (False, 2504)
            )
        self.assertFalse(self.session(self.member).chests[0]["items"])

    def test_treasury_acl_atomic_failure_locked_compartment_and_stale_owner(self):
        self.learn_base()
        member = self.session(self.member)
        deposit = struct.pack(">q", 300)

        def treasury(body):
            return member.handle(
                13994, body, self.characters[self.member["character"]], self.objects
            )

        result, _ = treasury(deposit)
        self.assertEqual(result["treasury_kamas"], 300)
        self.assertFalse(treasury(deposit)[0]["applied"])
        with self.assertRaisesRegex(ValueError, "permission denied"):
            treasury(struct.pack(">q", -100))
        # Global native treasury13994 needs bit8; it is not the per-item
        # compartment operation and must not invent an extra bit5/11 gate.
        self.rank_mask(1 << 8)
        result, _ = treasury(struct.pack(">q", -100))
        self.assertEqual(result["treasury_kamas"], 200)
        before = result["character"]["kamas"]
        with patch(
            "wakfu_server.guild_economy._save", side_effect=RuntimeError("rollback")
        ):
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                treasury(struct.pack(">q", 77))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.member["account"],),
                ).fetchone()["kamas"],
                before,
            )
        with self.assertRaisesRegex(ValueError, "locked"):
            guild_chest.load(
                self.store,
                self.member["account"],
                self.member["generation"],
                self.member["character"],
                1,
            )
        self.store.begin_session(self.member["account"])
        with self.assertRaises(ValueError):
            treasury(struct.pack(">q", 10))

    def test_concurrent_exchange_bound_source_and_failed_custody_preserve_source(self):
        self.learn_base()
        from datetime import timedelta

        owner = self.session(self.owner)
        with self.store.connection() as db:
            exchange = db.execute(
                "INSERT INTO player_exchanges(inviter_id,invitee_id,inviter_account,invitee_account,"
                "inviter_generation,invitee_generation,state,created_at,expires_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,'active',%s,%s) RETURNING id",
                (
                    self.owner["character"],
                    self.member["character"],
                    self.owner["account"],
                    self.member["account"],
                    self.owner["generation"],
                    self.member["generation"],
                    self.store.now(),
                    self.store.now() + timedelta(minutes=1),
                ),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_exchange_members(character_id,exchange_id) VALUES(%s,%s)",
                (self.owner["character"], exchange),
            )
        with self.assertRaisesRegex(ValueError, "intercambio"):
            self.handle(owner, self.owner, self.item_body(0, self.owner))
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_exchanges SET state='canceled' WHERE id=%s", (exchange,)
            )
            db.execute(
                "DELETE FROM player_exchange_members WHERE exchange_id=%s", (exchange,)
            )
            db.execute(
                "UPDATE inventory_item_bindings SET bound=true WHERE uid=%s",
                (self.uid,),
            )
        with self.assertRaisesRegex(ValueError, "Bound|nonexchangeable"):
            self.handle(owner, self.owner, self.item_body(0, self.owner))
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_bindings SET bound=false WHERE uid=%s",
                (self.uid,),
            )
        with patch(
            "wakfu_server.guild_chest._save",
            side_effect=RuntimeError("custody failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "custody failure"):
                self.handle(owner, self.owner, self.item_body(0, self.owner))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT i.quantity,b.bound FROM inventory_items i JOIN inventory_item_bindings b USING(uid) WHERE i.uid=%s",
                (self.uid,),
            ).fetchone()
            self.assertEqual((row["quantity"], row["bound"]), (9, False))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM guild_chest_receipts WHERE character_id=%s",
                    (self.owner["character"],),
                ).fetchone()["n"],
                0,
            )
        self.assertFalse(self.session(self.owner).chests[0]["items"])
