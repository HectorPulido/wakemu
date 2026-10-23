"""Real native chest action, atomic ordinary inventory and account replay."""
from concurrent.futures import ThreadPoolExecutor
import struct
import threading
from unittest.mock import patch

from postgres_case import PostgresCase


class TreasureChestTests(PostgresCase):
    def owner(self, suffix):
        account = self.store.register("treasure-" + suffix, "local-password")["id"]
        character = self.store.create_character(account, "Treasure " + suffix)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=5,y=57,z=0 WHERE id=%s",
                (character["id"],),
            )
        return account, generation, self.store.character(account, character["id"])

    def test_native_action_atomic_grant_account_scope_reconnect_and_rollback(self):
        from wakfu_server import treasure_chests as chests
        from wakfu_server import harvest_inventory
        from wakfu_server.inventory_items import grant as owned_grant

        body = struct.pack(">qHH", 25114, 22, 0)
        rule = chests.definition(self.store, 527, 25114)
        self.assertEqual(rule["position"], [5, 58, 0])
        self.assertEqual(rule["native_criterion"], "not IsHero()")
        self.assertEqual(rule["native_required_tools"], [])
        self.assertEqual(
            rule["reward_authority"], "wakemu-custom-content-not-original-loot"
        )
        self.assertEqual(rule["rewards"], [dict(reference=1752, quantity=5)])
        account, generation, character = self.owner("first")

        def claim(actor=character, payload=body, **extra):
            return chests.claim(
                self.store,
                account,
                generation,
                actor,
                payload,
                **dict(dict(loaded=True, is_hero=False), **extra)
            )

        for extra in (
            dict(loaded=False),
            dict(blocked=True),
            dict(is_hero=True),
            dict(is_hero=None),
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                claim(**extra)
        for actor in (
            dict(character, map_id=528),
            dict(character, instance_id=1),
            dict(character, x=4, y=58, z=4),
            dict(character, x=500),
        ):
            with self.subTest(actor=actor["map_id"]), self.assertRaises(ValueError):
                claim(actor=actor)
        for payload in (
            b"",
            struct.pack(">qHH", 25114, 0, 0),
            struct.pack(">qHH", 25114, 22, 1),
            struct.pack(">qHH", 25113, 22, 0),
        ):
            with self.subTest(payload=payload.hex()), self.assertRaises(ValueError):
                claim(payload=payload)
        with self.assertRaises(ValueError):
            chests.claim(
                self.store,
                account,
                "stale",
                character,
                body,
                loaded=True,
                is_hero=False,
            )

        gate = threading.Barrier(2)

        def simultaneous():
            gate.wait(timeout=10)
            return claim()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: simultaneous(), range(2)))
        self.assertEqual(sorted(row["replay"] for row in results), [False, True])
        granted = next(row for row in results if not row["replay"])
        self.assertEqual(len(granted["packets"]), 2)
        seed = next(
            item
            for item in granted["character"]["inventory_items"]
            if item["reference"] == 1752
        )
        self.assertEqual(seed["quantity"], 5)
        self.assertGreater(seed["uid"], 0)
        self.assertEqual(
            granted["receipt"]["rewards"],
            [dict(reference=1752, quantity=5, uid=seed["uid"])],
        )
        self.assertEqual(
            len(claim()["packets"]), 1
        )  # Only authoritative chest state, no duplicate inventory delta.
        reopened = self.reopen()
        closed = chests.snapshots(reopened, account, 527)
        self.assertEqual(struct.unpack_from(">h", closed[0][1], 17)[0], 0)
        self.assertEqual(
            sum(
                item["quantity"]
                for item in reopened.character(account, character["id"])[
                    "inventory_items"
                ]
                if item["reference"] == 1752
            ),
            5,
        )
        alternate = self.store.create_character(account, "Treasure Alternate")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=6,y=58,z=0 WHERE id=%s",
                (alternate["id"],),
            )
        alternate = self.store.character(account, alternate["id"])
        with self.assertRaisesRegex(ValueError, "Invalid inventory session"):
            chests.claim(
                self.store,
                account,
                generation,
                alternate,
                body,
                loaded=True,
                is_hero=False,
            )
        self.store.select_character(account, generation, alternate["id"])
        alternate_result = chests.claim(
            self.store, account, generation, alternate, body, loaded=True, is_hero=False
        )
        self.assertTrue(alternate_result["replay"])
        self.assertEqual(alternate_result["character"]["inventory_items"], [])

        other_account, other_generation, other = self.owner("other")
        self.assertEqual(
            struct.unpack_from(
                ">h", chests.snapshots(self.store, other_account, 527)[0][1], 17
            )[0],
            1,
        )
        independent = chests.claim(
            self.store,
            other_account,
            other_generation,
            other,
            body,
            loaded=True,
            is_hero=False,
        )
        self.assertFalse(independent["replay"])

        failed_account, failed_generation, failed = self.owner("rollback")
        original_grant = harvest_inventory.grant

        def fail_after_inventory_mutation(*args, **kwargs):
            original_grant(*args, **kwargs)
            raise ValueError("Injected failure after ordinary inventory mutation")

        with patch.object(
            harvest_inventory, "grant", side_effect=fail_after_inventory_mutation
        ):
            with self.assertRaisesRegex(ValueError, "Injected failure"):
                chests.claim(
                    self.store,
                    failed_account,
                    failed_generation,
                    failed,
                    body,
                    loaded=True,
                    is_hero=False,
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_treasure_claims WHERE account_id=%s",
                    (failed_account,),
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(
            self.store.character(failed_account, failed["id"])["inventory_items"], []
        )
        self.assertFalse(
            chests.claim(
                self.store,
                failed_account,
                failed_generation,
                failed,
                body,
                loaded=True,
                is_hero=False,
            )["replay"]
        )

        full_account, full_generation, full = self.owner("full")
        base = full["inventory_containers"][0]
        with self.store.connection() as db:
            for slot in range(base["capacity"]):
                owned_grant(
                    self.store,
                    full_account,
                    full_generation,
                    full["id"],
                    reference=2340,
                    quantity=1,
                    container=base["uid"],
                    slot=slot,
                    allowed_references={2340},
                    db=db,
                )
        with self.assertRaisesRegex(ValueError, "inventory full"):
            chests.claim(
                self.store,
                full_account,
                full_generation,
                full,
                body,
                loaded=True,
                is_hero=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_treasure_claims WHERE account_id=%s",
                    (full_account,),
                ).fetchone()["n"],
                0,
            )
        self.assertFalse(
            any(
                item["reference"] == 1752
                for item in self.store.character(full_account, full["id"])[
                    "inventory_items"
                ]
            )
        )
