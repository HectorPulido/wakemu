"""Default native account entitlement, ownership and private-scene admission."""
from pathlib import Path
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.haven_ranch_authority import (
    require_owned_entitlement,
    portal_target,
    validate_return,
)
from wakfu_server.inventory_items import grant
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession
from wakfu_server.characters.exploration_secrets import account_quantity


class RanchEntitlementPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ranchentitlement", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Ranch owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.character = self.store.character(self.account, self.character["id"])
        self.actor = dict(
            self.character, map_id=9, instance_id=self.account, x=-8, y=5, z=4
        )

    def check(self):
        require_owned_entitlement(self.store, self.account, self.generation, self.actor)

    def give(self, account, generation, character):
        container = character["inventory_containers"][0]["uid"]
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=32864,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={32864},
        )

    def remove_default(self, account):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_quest_items WHERE account_id=%s AND reference=32864",
                (account,),
            )

    def test_default_owned_item_allows_private_source_and_is_published_without_consumption(
        self,
    ):
        self.check()
        bag = HavenBagSession(self.character)
        actor = bag.move(bag.inside, dict(x=-8, y=5, z=4))
        source = dict(id=36028, type="RanchEntrance", map_id=9, x=-9, y=5, z=4)
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[source],
        ):
            target = portal_target(
                actor,
                bag,
                struct.pack(">qHH", 36028, 35, 0),
                validate_lease=lambda: self.store.current_character_session(
                    self.account, self.generation, actor["id"]
                ),
                validate_entitlement=lambda: require_owned_entitlement(
                    self.store, self.account, self.generation, actor
                ),
                geometry=dict(map_id=9, cells=[(-8, 5, 4)]),
            )
        self.assertEqual(target, dict(biome_id=1, map_id=1440, x=28, y=6, z=4))
        saved = self.store.character(self.account, self.character["id"])
        self.assertEqual(saved["map_id"], self.character["map_id"])
        self.assertEqual(account_quantity(saved, (32864,)), 1)
        with self.store.connection() as db:
            owned = db.execute(
                "SELECT quantity FROM account_quest_items "
                "WHERE account_id=%s AND reference=32864",
                (self.account,),
            ).fetchone()
        self.assertEqual(owned["quantity"], 1)
        self.assertEqual(self.actor["map_id"], 9)
        from wakfu_server.characters.exploration_secrets import account_packet

        with self.store.connection() as db:
            opcode, body = account_packet(db, self.account)
        self.assertEqual(opcode, 13873)
        version, section, length = struct.unpack(">III", body[:12])
        self.assertEqual((version, section, length), (1, 4, len(body) - 12))
        # Native flY ACCOUNT_QUEST protobuf: reference32864, quantity1.
        self.assertIn(b"\x0a\x06\x08\xe0\x80\x02\x10\x01", body[12:])

    def test_migration_backfills_existing_accounts_preserves_quantity_and_grants_new_accounts(
        self,
    ):
        other = self.store.register("existingranchowner", "test-password")["id"]
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations/328_default_emerald_biome.sql"
        ).read_text()
        with self.store.connection() as db:
            db.execute("DROP TRIGGER account_default_emerald_biome ON accounts")
            db.execute("DROP FUNCTION grant_default_emerald_biome()")
            db.execute(
                "DELETE FROM account_quest_items WHERE account_id=%s AND reference=32864",
                (self.account,),
            )
            db.execute(
                "UPDATE account_quest_items SET quantity=3 WHERE account_id=%s AND reference=32864",
                (other,),
            )
            db.execute(migration)
            quantities = {
                row["account_id"]: row["quantity"]
                for row in db.execute(
                    "SELECT account_id,quantity FROM account_quest_items WHERE reference=32864"
                )
            }
        self.assertEqual(quantities[self.account], 1)
        self.assertEqual(quantities[other], 3)
        new = self.store.register("newranchowner", "test-password")["id"]
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=32864",
                    (new,),
                ).fetchone()["quantity"],
                1,
            )
        self.check()

    def test_other_account_item_and_removed_stale_item_do_not_authorize(self):
        self.remove_default(self.account)
        other = self.store.register("otherranchowner", "test-password")["id"]
        character = self.store.create_character(other, "Other owner")
        generation = self.store.begin_session(other)
        self.store.select_character(other, generation, character["id"])
        self.give(other, generation, self.store.character(other, character["id"]))
        with self.assertRaises(ValueError):
            self.check()
        self.give(self.account, self.generation, self.character)
        self.actor["account_quest_items"] = self.store.character(
            self.account, self.character["id"]
        )["account_quest_items"]
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_quest_items WHERE account_id=%s AND reference=32864",
                (self.account,),
            )
        with self.assertRaises(ValueError):
            self.check()

    def test_trusted_role_revocation_denies_new_admission_but_allows_exit(self):
        self.remove_default(self.account)
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (self.account,))
        self.check()
        self.actor["account_is_admin"] = True
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=FALSE WHERE id=%s", (self.account,)
            )
        with self.assertRaises(ValueError):
            self.check()
        bag = HavenBagSession(self.character)
        actor = bag.move(bag.inside, dict(x=-8, y=5, z=4))
        child = RanchSession(
            bag,
            actor,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease=1,
            now_ms=1000,
        )
        validate_return(
            child.inside,
            child,
            b"\x00",
            validate_lease=lambda: self.store.current_character_session(
                self.account, self.generation, self.character["id"]
            ),
        )
        self.assertEqual(child.leave(child.inside)["map_id"], 9)

    def test_changed_selected_actor_revokes_old_ranch_admission(self):
        self.give(self.account, self.generation, self.character)
        other = self.store.create_character(self.account, "Other selected")
        self.store.select_character(self.account, self.generation, other["id"])
        with self.assertRaises(ValueError):
            self.check()
