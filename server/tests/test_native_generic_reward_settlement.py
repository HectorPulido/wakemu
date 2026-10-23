"""One transactional contract for all six original GenericActivable rewards."""
from concurrent.futures import ThreadPoolExecutor
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class NativeGenericRewardSettlementTests(PostgresCase):
    def test_six_sources_native_inventories_cost_rollback_and_repeatable_guards(self):
        from wakfu_server import native_generic_rewards as service
        from wakfu_server.achievements import rewards
        from wakfu_server.items import quest_inventory, account_quest_inventory
        from wakfu_server.dungeon_entry_payment import consume

        with self.store.connection() as db:
            sources = db.execute(
                "SELECT map_id,object_id FROM native_generic_reward_locations "
                "ORDER BY map_id,object_id"
            ).fetchall()
            self.assertEqual(len(sources), 6)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_reward_programs WHERE sealed"
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_reward_effects"
                ).fetchone()["n"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_reward_approaches"
                ).fetchone()["n"],
                22,
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','false') "
                "WHERE name='exploration_secret_access_policy'"
            )
        rules = [
            service.definition(self.store, r["map_id"], r["object_id"]) for r in sources
        ]
        for rule in rules:
            service._source(rule)
        account = self.store.register("generic-reward-contract", "local-test-password")[
            "id"
        ]
        actor = self.store.create_character(account, "Native Reward")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])

        def current():
            return self.store.character(account, actor["id"])

        def approach(rule):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (rule["map_id"], *rule["approaches"][0], actor["id"]),
                )

        def claim(rule, **kwargs):
            return service.claim(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], 0, 0),
                loaded=True,
                **kwargs
            )

        def amount(reference):
            with self.store.connection() as db:
                if reference in account_quest_inventory.REFERENCES:
                    rows = account_quest_inventory.load(db, account)
                elif reference in quest_inventory.REFERENCES:
                    rows = quest_inventory.load(db, actor["id"])
                else:
                    rows = current()["inventory_items"]
                return sum(r["quantity"] for r in rows if r["reference"] == reference)

        def receipt_count():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT count(*) n FROM native_generic_reward_attempts"
                ).fetchone()["n"]

        # Each original ballot object is distinct; replay never repeats its grant.
        for rule in (r for r in rules if r["descriptor_id"] == 1403):
            approach(rule)
            with self.assertRaises(ValueError):
                claim(rule, blocked=True)
            first = claim(rule)
            self.assertEqual(first["granted"][0]["reference"], 11423)
            self.assertTrue(claim(rule)["replay"])
        self.assertEqual(amount(11423), 3)

        paid = next(r for r in rules if r["descriptor_id"] == 183)
        approach(paid)
        before = receipt_count()
        with self.assertRaises(ValueError):
            claim(paid)
        self.assertEqual((receipt_count(), amount(17545)), (before, 0))
        with self.store.connection() as db:
            quest_inventory.grant(db, actor["id"], 17578, 1)
        original = rewards._item

        def fail_after_grant(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("Injected generic settlement failure")

        with patch.object(rewards, "_item", side_effect=fail_after_grant):
            with self.assertRaisesRegex(ValueError, "Injected generic"):
                claim(paid)
        self.assertEqual(
            (amount(17578), amount(17545), receipt_count()), (1, 0, before)
        )
        settled = claim(paid)
        self.assertEqual((amount(17578), amount(17545)), (0, 1))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT consumed FROM native_generic_reward_attempts WHERE token=%s",
                (settled["attempt"],),
            ).fetchone()
        self.assertEqual(row["consumed"][0]["reference"], 17578)
        self.assertEqual(row["consumed"][0]["consumed"], 1)
        # A once marker is checked before charging; replay needs no second key.
        self.assertTrue(claim(paid)["replay"])
        self.assertEqual(amount(17545), 1)

        bow = next(r for r in rules if r["descriptor_id"] == 181)
        approach(bow)
        first = claim(bow)
        self.assertEqual(amount(17496), 1)
        self.assertTrue(any(op == 13879 for op, _ in first["packets"]))
        held = claim(bow)
        self.assertTrue(held["replay"])
        self.assertEqual([op for op, _ in held["visual_packets"]], [13270])
        self.assertEqual(
            struct.unpack_from(">i", held["visual_packets"][0][1], 8)[0], 393
        )
        with self.store.connection() as db:
            consume(db, (actor["id"],), 17496, 1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(bow), range(2)))
        self.assertEqual(sorted(r["replay"] for r in results), [False, True])
        self.assertEqual(amount(17496), 1)
        second = next(r for r in results if not r["replay"])
        self.assertNotEqual(first["notification_key"], second["notification_key"])

        artifact = next(r for r in rules if r["descriptor_id"] == 1163)
        approach(artifact)
        acquired = claim(artifact)
        self.assertEqual(amount(21599), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM inventory_items WHERE character_id=%s "
                    "AND reference IN(17496,21599)",
                    (actor["id"],),
                ).fetchone()["n"],
                0,
            )
            account_quest_inventory.consume(db, account, 21599, 1)
        reacquired = claim(artifact)
        self.assertEqual(amount(21599), 1)
        self.assertNotEqual(
            acquired["notification_key"], reacquired["notification_key"]
        )
        # Reconnection preserves ownership/quantity; it does not turn this into once-account.
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        self.assertTrue(claim(artifact)["replay"])
        with self.store.connection() as db:
            account_quest_inventory.consume(db, account, 21599, 1)
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','true') "
                "WHERE name='exploration_secret_access_policy'"
            )
        self.assertTrue(claim(artifact)["replay"])
        self.assertEqual(
            amount(21599), 0
        )  # Effective projected ownership also satisfies native eKE.
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_reward_claims"
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_reward_claims WHERE policy_id IN "
                    "('native.generic.reward.181.v1','native.generic.reward.1163.v1')"
                ).fetchone()["n"],
                0,
            )
