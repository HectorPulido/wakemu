"""Read-only PostgreSQL qualification for account quest item spell publication."""
from concurrent.futures import ThreadPoolExecutor
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.items import item_spell_publication


class AccountInventorySpellPublicationPostgresTests(PostgresCase):
    def test_publishes_only_eligible_loaded_company_members_without_writes_or_locks(
        self,
    ):
        account = self.store.register(
            "spell-publish-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        main = self.store.create_character(account, "Publication Main")
        active = self.store.create_character(account, "Publication Hero")
        inactive = self.store.create_character(account, "Unloaded Hero")
        foreign_account = self.store.register(
            "spell-publish-foreign-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        foreign = self.store.create_character(foreign_account, "Foreign Member")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=130 WHERE id=%s", (main["id"],))
            db.execute("UPDATE characters SET level=129 WHERE id=%s", (active["id"],))
            db.execute("UPDATE characters SET level=230 WHERE id=%s", (inactive["id"],))
            db.execute("UPDATE characters SET level=230 WHERE id=%s", (foreign["id"],))
            db.execute(
                "INSERT INTO account_hero_rosters(account_id,leader_id) VALUES(%s,%s) "
                "ON CONFLICT(account_id) DO UPDATE SET leader_id=EXCLUDED.leader_id",
                (account, main["id"]),
            )
            db.execute(
                "INSERT INTO account_hero_slots(account_id,slot,character_id) VALUES(%s,0,%s)",
                (account, active["id"]),
            )
            db.execute(
                "INSERT INTO account_quest_items(account_id,reference,quantity) VALUES(%s,26347,1)",
                (account,),
            )

        packets = item_spell_publication.account_inventory_packets(
            self.store, account, generation, main["id"]
        )
        # Main meets unlock 130; active hero at 129 does not. Inactive and
        # foreign level-230 characters are not part of the loaded company.
        self.assertEqual(1, len(packets))
        opcode, payload = packets[0]
        self.assertEqual(12503, opcode)
        self.assertEqual(main["id"], struct.unpack_from(">q", payload)[0])
        self.assertEqual(
            (5623, (main["id"] << 32) | 5623, 130),
            struct.unpack_from(">iqh", payload, 8),
        )

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=130 WHERE id=%s", (active["id"],))
        packets = item_spell_publication.account_inventory_packets(
            self.store, account, generation, main["id"]
        )
        self.assertEqual(
            [main["id"], active["id"]],
            [struct.unpack_from(">q", payload)[0] for _, payload in packets],
        )

        # Hold row locks on every row this path could mutate. A concurrent
        # publication must still finish; it is a pure snapshot read.
        with self.store.connection() as lock_db:
            lock_db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,)
            )
            lock_db.execute(
                "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE",
                (account,),
            )
            lock_db.execute(
                "SELECT id FROM characters WHERE account_id=%s FOR UPDATE", (account,)
            )
            lock_db.execute(
                "SELECT account_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
                (account,),
            )
            lock_db.execute(
                "SELECT account_id FROM account_hero_slots WHERE account_id=%s FOR UPDATE",
                (account,),
            )
            lock_db.execute(
                "SELECT account_id FROM account_quest_items WHERE account_id=%s FOR UPDATE",
                (account,),
            )
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    item_spell_publication.account_inventory_packets,
                    self.store,
                    account,
                    generation,
                    main["id"],
                )
                locked_read_packets = future.result(timeout=3)
            self.assertEqual(2, len(locked_read_packets))

        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=26347",
                    (account,),
                ).fetchone()["quantity"],
            )
            session = db.execute(
                "SELECT generation,character_id FROM sessions WHERE account_id=%s",
                (account,),
            ).fetchone()
            self.assertEqual(
                (generation, main["id"]),
                (session["generation"], session["character_id"]),
            )

        stale_generation = self.store.begin_session(account)
        self.store.select_character(account, stale_generation, main["id"])
        with self.assertRaises(ValueError):
            item_spell_publication.account_inventory_packets(
                self.store, account, generation, main["id"]
            )
        with self.assertRaises(ValueError):
            item_spell_publication.account_inventory_packets(
                self.store, foreign_account, generation, main["id"]
            )


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTests(
        loader.loadTestsFromTestCase(AccountInventorySpellPublicationPostgresTests)
    )
    return suite
