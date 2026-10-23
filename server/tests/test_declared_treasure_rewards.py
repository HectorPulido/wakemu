"""One isolated compound contract for the two explicitly declared policies."""
from concurrent.futures import ThreadPoolExecutor
import struct
import time
from unittest.mock import patch

from postgres_case import PostgresCase


class DeclaredTreasureRewardTests(PostgresCase):
    def test_fifty_two_sources_character_cooldown_atomic_reservation_and_once_wallet(
        self,
    ):
        from wakfu_server import declared_treasure_rewards as service
        from wakfu_server import treasure_chests
        from wakfu_server.achievements import rewards

        clock = [int(time.time())]
        self.store.clock = lambda: clock[0]
        with self.store.connection() as db:
            locations = db.execute(
                "SELECT map_id,object_id FROM declared_treasure_locations ORDER BY map_id,object_id"
            ).fetchall()
            self.assertEqual(len(locations), 52)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_outcomes"
                ).fetchone()["n"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_locations WHERE NOT client_action_available"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_approaches"
                ).fetchone()["n"],
                154,
            )
            # Earlier qualified datasets are untouched.
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_locations"
                ).fetchone()["n"],
                17,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_reward_locations"
                ).fetchone()["n"],
                6,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM achievement_chest_bindings WHERE emote_id IS NOT NULL"
                ).fetchone()["n"],
                55,
            )
        rules = [
            service.definition(self.store, r["map_id"], r["object_id"])
            for r in locations
        ]
        gems = [r for r in rules if r["reward_kind"] == "uniform_fragment"]
        ordinary = [
            r
            for r in rules
            if r["reward_kind"] == "kamas"
            and r["source_disposition"] != "ORPHAN_MIMIK_NO_ORIGINAL_ACTION"
        ]
        orphans = [
            r
            for r in rules
            if r["source_disposition"] == "ORPHAN_MIMIK_NO_ORIGINAL_ACTION"
        ]
        self.assertEqual((len(gems), len(ordinary), len(orphans)), (24, 26, 2))
        self.assertEqual(sum(bool(r["client_action_available"]) for r in rules), 52)
        self.assertEqual({r["descriptor_id"] for r in orphans}, {179, 181})
        for rule in rules:
            service._source(
                rule["catalog_revision"],
                rule["map_id"],
                rule["object_id"],
                rule["native_family"],
                rule["payload_hex"],
                rule["state_payload_hex"],
                rule["geometry_sha256"],
                rule["x"],
                rule["y"],
                rule["z"],
            )
        account = self.store.register(
            "declared-treasure-contract", "local-test-password"
        )["id"]
        actor = self.store.create_character(account, "Treasure Native")
        other = self.store.create_character(account, "Treasure Other")
        generation = self.store.begin_session(account, ttl=200000)
        self.store.select_character(account, generation, actor["id"])
        current_actor = actor["id"]

        def approach(rule):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (rule["map_id"], *rule["approaches"][0], current_actor),
                )

        def current():
            return self.store.character(account, current_actor)

        def claim(rule, **kw):
            return service.claim(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], rule["wire_action"], 0),
                loaded=True,
                is_hero=False,
                **kw
            )

        def wallet():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
                ).fetchone()["kamas"]

        def fragment_count():
            return sum(
                r["quantity"]
                for r in current()["inventory_items"]
                if r["reference"] in range(26550, 26555)
            )

        def attempts(rule):
            with self.store.connection() as db:
                return [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM declared_treasure_attempts WHERE character_id=%s "
                        "AND map_id=%s AND object_id=%s ORDER BY prepared_at,token",
                        (current_actor, rule["map_id"], rule["object_id"]),
                    ).fetchall()
                ]

        first = gems[0]
        approach(first)
        with self.assertRaises(ValueError):
            claim(first, blocked=True)
        with self.assertRaises(ValueError):
            service.claim(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", first["object_id"], 0, 0),
                loaded=True,
                is_hero=False,
            )
        self.assertEqual(attempts(first), [])
        original = rewards._item

        def fail_after_grant(*args, **kwargs):
            original(*args, **kwargs)
            raise rewards.RewardCapacity(
                "Injected capacity failure after item mutation"
            )

        draws = []

        def choose(count):
            draws.append(count)
            return 3

        with patch.object(rewards, "_item", side_effect=fail_after_grant):
            with self.assertRaises(rewards.RewardCapacity):
                claim(first, choose=choose)
        reserved = attempts(first)
        self.assertEqual(
            (
                len(reserved),
                reserved[0]["selected_ordinal"],
                reserved[0]["completed_at"],
                fragment_count(),
            ),
            (1, 3, None, 0),
        )
        self.assertEqual(draws, [5])
        with patch.object(
            service.secrets,
            "randbelow",
            side_effect=AssertionError("Retry must not reroll"),
        ):
            settled = claim(first)
        self.assertEqual(
            (
                settled["receipt"]["item_reference"],
                settled["receipt"]["quantity"],
                fragment_count(),
            ),
            (26553, 1, 1),
        )
        self.assertTrue(claim(first)["replay"])
        self.assertEqual(len(attempts(first)), 1)
        # Every remaining Gem placement uses exactly one of the five original
        # fragment kinds; the injected draw validates indexing, not probability.
        observed = {26553}
        for index, rule in enumerate(gems[1:]):
            approach(rule)
            result = claim(rule, choose=lambda n, i=index: i % n)
            observed.add(result["receipt"]["item_reference"])
        self.assertEqual(observed, set(range(26550, 26555)))
        self.assertEqual(fragment_count(), 24)
        initial = wallet()
        for rule in ordinary:
            approach(rule)
            self.assertFalse(claim(rule)["replay"])
            self.assertTrue(claim(rule)["replay"])
        self.assertEqual(wallet() - initial, 2600)
        for rule in orphans:
            approach(rule)
            if not rule["client_action_available"]:
                with self.assertRaises(ValueError):
                    claim(rule)
            else:
                # 286 has its own original-reader/projection/claim contract.
                self.assertEqual(
                    rule["definition_override"]["original_definition"],
                    rule["descriptor_id"],
                )
            self.assertEqual(attempts(rule), [])
        # Once semantics are character-scoped, even though kamas share a wallet.
        self.store.select_character(account, generation, other["id"])
        current_actor = other["id"]
        approach(ordinary[0])
        self.assertFalse(claim(ordinary[0])["replay"])
        self.assertEqual(wallet() - initial, 2700)
        approach(first)
        self.assertFalse(claim(first, choose=lambda n: 0)["replay"])
        self.assertEqual(fragment_count(), 1)
        self.store.select_character(account, generation, actor["id"])
        current_actor = actor["id"]
        approach(first)
        # Reconnect/refresh reconstructs this character's own cooldown.
        states = treasure_chests.snapshots(
            self.store, account, first["map_id"], character_id=current_actor
        )
        packet = next(
            p for p in states if struct.unpack_from(">q", p[1])[0] == first["object_id"]
        )
        self.assertEqual(struct.unpack_from(">h", packet[1], 17)[0], 0)
        clock[0] += 86399
        self.assertTrue(claim(first)["replay"])
        clock[0] += 1
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(lambda _: claim(first, choose=lambda n: 4), range(2))
            )
        self.assertEqual(sorted(r["replay"] for r in results), [False, True])
        self.assertEqual((fragment_count(), len(attempts(first))), (25, 2))
        # A new authenticated connection cannot reset the rolling deadline.
        generation = self.store.begin_session(account, ttl=200000)
        self.store.select_character(account, generation, current_actor)
        self.assertTrue(claim(first)["replay"])
        approach(ordinary[0])
        self.assertTrue(claim(ordinary[0])["replay"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_attempts WHERE completed_at IS NULL"
                ).fetchone()["n"],
                0,
            )
        with self.assertRaises(Exception):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE declared_treasure_policies SET kamas=200 WHERE reward_kind='kamas'"
                )
