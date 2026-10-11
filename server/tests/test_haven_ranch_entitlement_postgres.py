"""Isolated PostgreSQL ownership, revocation and private-scene entitlement."""
from postgres_case import PostgresCase
from wakfu_server.haven_ranch_authority import (
    require_owned_entitlement,
    validate_return,
)
from wakfu_server.inventory_items import grant
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession


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

    def test_real_owned_item_allows_private_source_and_is_not_consumed(self):
        with self.assertRaises(ValueError):
            self.check()
        self.give(self.account, self.generation, self.character)
        self.check()
        saved = self.store.character(self.account, self.character["id"])
        self.assertEqual(saved["map_id"], self.character["map_id"])
        self.assertEqual(
            sum(
                i["quantity"]
                for i in saved["inventory_items"]
                if i["reference"] == 32864
            ),
            1,
        )
        self.assertEqual(self.actor["map_id"], 9)

    def test_other_account_item_and_removed_stale_item_do_not_authorize(self):
        other = self.store.register("otherranchowner", "test-password")["id"]
        character = self.store.create_character(other, "Other owner")
        generation = self.store.begin_session(other)
        self.store.select_character(other, generation, character["id"])
        self.give(other, generation, self.store.character(other, character["id"]))
        with self.assertRaises(ValueError):
            self.check()
        self.give(self.account, self.generation, self.character)
        self.actor["inventory_items"] = self.store.character(
            self.account, self.character["id"]
        )["inventory_items"]
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s",
                (self.character["id"],),
            )
        with self.assertRaises(ValueError):
            self.check()

    def test_trusted_role_revocation_denies_new_admission_but_allows_exit(self):
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
