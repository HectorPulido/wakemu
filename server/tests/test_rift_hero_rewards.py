"""Six real company members share two sessions and receive durable owned loot."""
import struct
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import rift_entry_adapter, rift_runtime, rift_rewards
from wakfu_server.characters import heroes
from wakfu_server.rift_policy import select_wave


class RiftHeroRewardsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.companies = []
        for company in range(2):
            account = self.store.register(
                "rift-company-" + str(company), "hero-loot-password"
            )["id"]
            ids = [
                self.store.create_character(
                    account, "Riftcompany" + chr(97 + company) + chr(97 + i)
                )["id"]
                for i in range(3)
            ]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, ids[0])
            for hero in ids[1:]:
                heroes.add(self.store, account, generation, ids[0], hero)
            self.companies.append(dict(account=account, ids=ids, generation=generation))
        self.ids = [cid for c in self.companies for cid in c["ids"]]
        self.main = self.companies[0]
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=30,map_id=527,instance_id=0")
            db.execute("DELETE FROM player_parties")
            party = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (self.main["ids"][0],),
            ).fetchone()["id"]
            for company in self.companies:
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (company["ids"][0], party),
                )
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            portal = next(p for p in catalog["entrances"] if p["map_id"] == 527)
        entry = rift_entry_adapter.enter(
            self.store,
            self.main["account"],
            self.main["generation"],
            self.main["ids"][0],
            527,
            struct.pack(">qHH", portal["object_id"], 11, 0),
            source_allowed=lambda c, o: True,
            resolve_destination=lambda db, c, m: dict(
                map_id=c["map_id"], x=1, y=2, z=0
            ),
            seed="six-companies",
        )
        self.run = entry["run"]
        self.assertEqual(set(self.run["members"]), set(self.ids))
        with self.store.connection() as db:
            self.fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            for company in self.companies:
                for cid in company["ids"]:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                        (self.fight, cid, company["account"], company["generation"]),
                    )
            rift_runtime.start(
                db, self.run["instance_id"], self.main["ids"][0], self.fight
            )
            refs = select_wave(
                self.run["catalog"], self.run["policy"], self.run["seed"], 1
            )
            rift_runtime.bind_wave(
                db, self.run["instance_id"], 1, list(zip([-4, -3, -2, -1], refs))
            )
            rift_runtime.record_wave(
                db, self.run["instance_id"], 1, [-4, -3, -2, -1], turn=2
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (self.fight,)
            )

    def settle(self, db):
        return rift_runtime.settle(
            db,
            self.run["instance_id"],
            self.fight,
            outcome="won",
            turn=40,
            apply_rewards=lambda connection, run, result: rift_rewards.apply(
                connection,
                run,
                result,
                store=self.store,
                eligible_character_ids=self.ids,
                rng=lambda n: 0,
            ),
        )

    def test_six_main_and_hero_rewards_commit_once_under_two_real_sessions(self):
        with self.store.connection() as db:
            first = self.settle(db)
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM sessions").fetchone()["n"], 2
            )
            rows = db.execute(
                "SELECT character_id,sum(quantity) AS q FROM inventory_items WHERE reference=27083 GROUP BY character_id"
            ).fetchall()
            self.assertEqual(
                {r["character_id"]: r["q"] for r in rows}, {cid: 2 for cid in self.ids}
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM rift_item_reward_receipts"
                ).fetchone()["n"],
                6,
            )
        with self.reopen().connection() as db:
            with patch.object(
                rift_rewards, "plan", side_effect=AssertionError("reroll")
            ):
                self.assertEqual(self.settle(db), first)
            for cid in self.ids:
                self.assertEqual(
                    len(
                        rift_rewards.delivery(
                            db, self.store, self.run["instance_id"], cid
                        )["loots"]
                    ),
                    1,
                )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS q FROM inventory_items WHERE reference=27083"
                ).fetchone()["q"],
                12,
            )

    def test_removed_company_hero_rejects_and_rolls_back_entire_payout(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_hero_slots WHERE character_id=%s",
                (self.companies[1]["ids"][2],),
            )
        with self.assertRaisesRegex(ValueError, "frozen owned hero"):
            with self.store.connection() as db:
                self.settle(db)
        with self.store.connection() as db:
            for table in (
                "fight_drop_awards",
                "inventory_items",
                "rift_item_reward_receipts",
                "rift_settlement_receipts",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 0
                )
            self.assertEqual(
                rift_runtime._run(db, self.run["instance_id"])["status"], "running"
            )

    def test_stale_main_generation_rejects_hero_reward_without_partial_grant(self):
        self.store.begin_session(self.companies[1]["account"], ttl=10000)
        with self.assertRaises(ValueError):
            with self.store.connection() as db:
                self.settle(db)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM inventory_items").fetchone()["n"],
                0,
            )
