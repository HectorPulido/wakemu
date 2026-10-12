"""Transactional harvesting of native dead monster actors."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import ast
from contextlib import contextmanager
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

from postgres_case import PostgresCase
from wakfu_server import monster_corpses
from wakfu_server.monster_collect import Harvests, action
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.profession_store import ensure_learned
from wakfu_server.wire import proto_field


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _extract_harvest_target():
    module = ast.parse(SERVER.read_text(encoding="utf8"))
    nodes = [
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef)
        and item.name in {"combat_group_for_target", "harvest_target"}
    ]
    isolated = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {}
    exec(compile(isolated, str(SERVER), "exec"), namespace)
    return namespace["harvest_target"]


class CorpseHarvestDispatchTests(unittest.TestCase):
    def setUp(self):
        self.resolve = _extract_harvest_target()
        self.character = {"id": 7, "map_id": 1134, "instance_id": 17}

    def test_live_roster_is_authoritative_before_corpse_fallback(self):
        member = {"id": -41, "map_id": 1134, "instance_id": 17, "hp": 5}
        registry = Mock()
        registry.available.return_value = [{"key": (1134, 17, 9), "members": [member]}]
        store = Mock()
        with patch.dict(
            self.resolve.__globals__, {"COMBAT_GROUPS": registry, "STORE": store}
        ):
            self.assertEqual(
                {**member, "instance_id": 17}, self.resolve(self.character, -41)
            )
        store.connection.assert_not_called()

    def test_missing_live_actor_uses_only_matching_unconsumed_unexpired_corpse(self):
        registry = Mock()
        registry.available.return_value = []

        class Store:
            def __init__(self):
                self.query = None

            @contextmanager
            def connection(self):
                owner = self

                class Database:
                    def execute(self, sql, params):
                        owner.query = (sql, params)
                        return Mock(
                            fetchone=Mock(
                                return_value={
                                    "monster": {"id": -7001, "ref": 1, "hp": 0}
                                }
                            )
                        )

                db = Database()
                yield db

        store = Store()
        with patch.dict(
            self.resolve.__globals__, {"COMBAT_GROUPS": registry, "STORE": store}
        ):
            corpse = self.resolve(self.character, -7001)
        self.assertEqual({"id": -7001, "ref": 1, "hp": 0, "corpse": True}, corpse)
        self.assertEqual((-7001, 1134, 17), store.query[1])
        self.assertIn("consumed_at IS NULL", store.query[0])
        self.assertIn("expires_at>CURRENT_TIMESTAMP", store.query[0])

    def test_unknown_or_foreign_scope_target_is_rejected(self):
        registry = Mock()
        registry.available.return_value = []

        class Store:
            def __init__(self):
                self.query = None

            @contextmanager
            def connection(self):
                owner = self

                class Database:
                    def execute(self, sql, params):
                        owner.query = (sql, params)
                        return Mock(fetchone=Mock(return_value=None))

                yield Database()

        store = Store()
        with patch.dict(
            self.resolve.__globals__, {"COMBAT_GROUPS": registry, "STORE": store}
        ):
            with self.assertRaisesRegex(
                ValueError, "unavailable|expired|already harvested"
            ):
                self.resolve(self.character, -9999)
            self.assertEqual((-9999, 1134, 17), store.query[1])
            with self.assertRaisesRegex(
                ValueError, "unavailable|expired|already harvested"
            ):
                self.resolve({**self.character, "instance_id": 18}, -7001)
            self.assertEqual((-7001, 1134, 18), store.query[1])


class MonsterCorpseHarvestTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = [1000.0]
        self.store.clock = lambda: self.now[0]
        self.account = self.store.register("corpse-harvest-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Corpse Harvester")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.harvest = Harvests(self.store)
        self.monster_ref = 1
        self.action_id = 3722
        self.rule = action(self.monster_ref, self.action_id)
        self.assertEqual(
            (2731, 74, 3000, 'IsDead("target")'),
            (
                self.rule["item_ref"],
                self.rule["profession_id"],
                self.rule["duration_ms"],
                self.rule["condition"],
            ),
        )
        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [74]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=17,x=54,y=36,z=17 WHERE id=%s",
                (self.character["id"],),
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            self.member = owned_instance(
                self.monster_ref,
                REFERENCES[self.monster_ref]["min_level"],
                -920001,
                map_id=1134,
                instance_id=17,
                x=54,
                y=36,
                z=17,
            )
            fight = SimpleNamespace(
                id=fight_id,
                phase="finished",
                actors={self.member["id"]: SimpleNamespace(hp=0, controlled=False)},
            )
            self.assertEqual(1, monster_corpses.retain(db, fight, (self.member,)))
            row = db.execute(
                "SELECT actor_id FROM monster_corpses WHERE fight_id=%s", (fight_id,)
            ).fetchone()
            self.corpse_id = row["actor_id"]
        self.corpse = dict(self.member, id=self.corpse_id, hp=0, corpse=True)

    def request(self, target=None):
        return proto_field(8, self.action_id) + proto_field(
            16, (self.corpse_id if target is None else target) % (2**64)
        )

    def begin(self, harvest=None, *, account=None, generation=None, character=None):
        return (harvest or self.harvest).begin(
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character is None else character["id"],
            self.request(),
            self.corpse,
            profession_level=0,
            reachable=True,
        )

    def complete(self, harvest=None, *, account=None, generation=None, character=None):
        return (harvest or self.harvest).complete(
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character is None else character["id"],
            b"\x02\x00\x06",
            monster=self.corpse,
            profession_level=0,
        )

    def prepare_completion(self, harvest=None, **kwargs):
        self.begin(harvest, **kwargs)
        self.now[0] += self.rule["duration_ms"] / 1000

    def test_harvest_consumes_corpse_and_commits_inventory_receipt_and_profession_xp(
        self,
    ):
        self.prepare_completion()
        ticket = self.harvest.pending[self.character["id"]]
        result = self.complete()

        self.assertTrue(result["applied"])
        self.assertEqual(
            (2731, 1), (result["item"]["reference"], result["item"]["quantity"])
        )
        self.assertIn((12916, struct.pack(">iq", 74, 50)), result["packets"])
        self.assertEqual(12304, result["availability"][2][0])
        with self.store.connection() as db:
            corpse = db.execute(
                "SELECT consumed_at,harvest_token,harvested_by FROM monster_corpses WHERE actor_id=%s",
                (self.corpse_id,),
            ).fetchone()
            item_count = db.execute(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=2731 AND quantity=1",
                (self.character["id"],),
            ).fetchone()["n"]
            receipt = db.execute(
                "SELECT token,action_id,item_uid FROM monster_harvest_receipts WHERE token=%s",
                (ticket["token"],),
            ).fetchone()
            xp = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=74",
                (self.account,),
            ).fetchone()["xp"]
            xp_receipt = db.execute(
                "SELECT applied_xp FROM profession_xp_receipts WHERE operation=%s",
                ("monster-harvest:" + ticket["token"],),
            ).fetchone()["applied_xp"]
        self.assertIsNotNone(corpse["consumed_at"])
        self.assertEqual(
            (ticket["token"], self.character["id"]),
            (corpse["harvest_token"], corpse["harvested_by"]),
        )
        self.assertEqual(1, item_count)
        self.assertEqual(
            (ticket["token"], self.action_id, result["item"]["uid"]),
            (receipt["token"], receipt["action_id"], receipt["item_uid"]),
        )
        self.assertEqual((50, 50), (xp, xp_receipt))
        replay = self.complete()
        self.assertFalse(replay["applied"])
        self.assertEqual([], replay["packets"])
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=2731",
                    (self.character["id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts WHERE account_id=%s AND operation=%s",
                    (self.account, "monster-harvest:" + ticket["token"]),
                ).fetchone()["n"],
            )
        with self.assertRaisesRegex(
            ValueError, "unavailable|expired|already harvested"
        ):
            self.begin()

    def test_unrestricted_native_seed_action_consumes_once_and_blocks_hand_afterward(
        self,
    ):
        self.action_id = 3724
        self.rule = action(self.monster_ref, self.action_id)
        self.assertEqual((7361, ""), (self.rule["item_ref"], self.rule["condition"]))
        self.prepare_completion()
        result = self.complete()
        self.assertTrue(result["applied"])
        self.assertEqual(
            (7361, 1), (result["item"]["reference"], result["item"]["quantity"])
        )
        self.assertEqual(12304, result["availability"][2][0])
        self.assertFalse(self.complete()["applied"])
        self.action_id = 3722
        self.rule = action(self.monster_ref, self.action_id)
        with self.assertRaisesRegex(
            ValueError, "unavailable|expired|already harvested"
        ):
            self.begin()
        with self.store.connection() as db:
            rewards = db.execute(
                "SELECT reference,sum(quantity) AS quantity FROM inventory_items "
                "WHERE character_id=%s AND reference IN (7361,2731) GROUP BY reference",
                (self.character["id"],),
            ).fetchall()
            receipts = db.execute(
                "SELECT action_id FROM monster_harvest_receipts WHERE monster_id=%s",
                (self.corpse_id,),
            ).fetchall()
        self.assertEqual([{"reference": 7361, "quantity": 1}], rewards)
        self.assertEqual([{"action_id": 3724}], receipts)

    def test_expiry_after_start_aborts_without_consumption_or_rewards(self):
        self.begin()
        token = self.harvest.pending[self.character["id"]]["token"]
        self.now[0] += self.rule["duration_ms"] / 1000
        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_corpses SET created_at=created_at-INTERVAL '2 hours', "
                "expires_at=expires_at-INTERVAL '2 hours' WHERE actor_id=%s",
                (self.corpse_id,),
            )

        with self.assertRaisesRegex(
            ValueError, "unavailable|expired|already harvested"
        ):
            self.complete()
        with self.store.connection() as db:
            corpse = db.execute(
                "SELECT consumed_at,harvest_token FROM monster_corpses WHERE actor_id=%s",
                (self.corpse_id,),
            ).fetchone()
            self.assertEqual(
                (None, None), (corpse["consumed_at"], corpse["harvest_token"])
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=2731",
                    (self.character["id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM monster_harvest_receipts WHERE token=%s",
                    (token,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts WHERE operation=%s",
                    ("monster-harvest:" + token,),
                ).fetchone()["n"],
            )

    def test_expired_corpse_is_rejected_before_occupation_starts(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_corpses SET created_at=created_at-INTERVAL '2 hours', "
                "expires_at=expires_at-INTERVAL '2 hours' WHERE actor_id=%s",
                (self.corpse_id,),
            )
        with self.assertRaisesRegex(
            ValueError, "unavailable|expired|already harvested"
        ):
            self.begin()
        self.assertNotIn(self.character["id"], self.harvest.pending)

    def test_two_workers_can_start_but_only_one_can_consume_the_corpse(self):
        second_account = self.store.register("corpse-harvest-second", "local-password")[
            "id"
        ]
        second_character = self.store.create_character(
            second_account, "Second Harvester"
        )
        second_generation = self.store.begin_session(second_account)
        self.store.select_character(
            second_account, second_generation, second_character["id"]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=17,x=54,y=36,z=17 WHERE id=%s",
                (second_character["id"],),
            )
        ensure_learned(
            self.store, second_account, second_generation, second_character["id"], [74]
        )
        worker_a, worker_b = Harvests(self.store), Harvests(self.store)
        self.begin(worker_a)
        self.begin(
            worker_b,
            account=second_account,
            generation=second_generation,
            character=second_character,
        )
        self.now[0] += self.rule["duration_ms"] / 1000
        barrier = Barrier(2)

        def finish(worker, account, generation, character):
            barrier.wait()
            try:
                result = self.complete(
                    worker, account=account, generation=generation, character=character
                )
                return result["applied"]
            except ValueError as exc:
                if "unavailable" not in str(exc) and "harvested" not in str(exc):
                    raise
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    finish, worker_a, self.account, self.generation, self.character
                ),
                pool.submit(
                    finish,
                    worker_b,
                    second_account,
                    second_generation,
                    second_character,
                ),
            ]
            outcomes = [future.result(timeout=20) for future in futures]
        self.assertEqual([False, True], sorted(outcomes))
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM monster_harvest_receipts WHERE monster_id=%s AND action_id=%s",
                    (self.corpse_id, self.action_id),
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE reference=2731 AND character_id IN (%s,%s)",
                    (self.character["id"], second_character["id"]),
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM monster_corpses WHERE actor_id=%s AND consumed_at IS NOT NULL",
                    (self.corpse_id,),
                ).fetchone()["n"],
            )

    def test_inventory_failure_rolls_back_corpse_claim_and_action_receipts(self):
        with self.store.connection() as db:
            base = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s ORDER BY uid LIMIT 1",
                (self.character["id"],),
            ).fetchone()
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE uid=%s",
                (base["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(9000000001,%s,1,1,%s,0)",
                (self.character["id"], base["uid"]),
            )
        self.prepare_completion()
        token = self.harvest.pending[self.character["id"]]["token"]
        with self.assertRaisesRegex(ValueError, "Base inventory full"):
            self.complete()
        with self.store.connection() as db:
            row = db.execute(
                "SELECT consumed_at,harvest_token FROM monster_corpses WHERE actor_id=%s",
                (self.corpse_id,),
            ).fetchone()
            self.assertEqual((None, None), (row["consumed_at"], row["harvest_token"]))
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM monster_harvest_receipts WHERE token=%s",
                    (token,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts WHERE operation=%s",
                    ("monster-harvest:" + token,),
                ).fetchone()["n"],
            )

    def test_owned_ranch_corpse_harvest_preserves_exterior_and_rejects_foreign_scope(
        self,
    ):
        from wakfu_server.haven_bag import HavenBagSession
        from wakfu_server.haven_ranch import RanchSession

        saved = self.store.character(self.account, self.character["id"])
        exterior = tuple(saved[key] for key in ("map_id", "instance_id", "x", "y", "z"))
        bag = HavenBagSession(saved)
        session = RanchSession(
            bag,
            bag.inside,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease=self.generation,
            now_ms=1000000,
        )
        inside = dict(session.inside)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            member = owned_instance(
                self.monster_ref,
                REFERENCES[self.monster_ref]["min_level"],
                -920002,
                map_id=1440,
                instance_id=inside["instance_id"],
                x=28,
                y=6,
                z=4,
            )
            fight = SimpleNamespace(
                id=fight_id,
                phase="finished",
                actors={member["id"]: SimpleNamespace(hp=0, controlled=False)},
            )
            self.assertEqual(monster_corpses.retain(db, fight, (member,)), 1)
            corpse_id = db.execute(
                "SELECT actor_id FROM monster_corpses WHERE fight_id=%s", (fight_id,)
            ).fetchone()["actor_id"]
        corpse = dict(member, id=corpse_id, hp=0, corpse=True)
        request = proto_field(8, self.action_id) + proto_field(
            16, corpse_id % (2**64)
        )
        projected = []

        def project(fresh):
            session.validate_lease(self.generation)
            active = session.refresh(inside, fresh)
            projected.append(active)
            return active

        foreign_account = self.store.register(
            "foreign-ranch-harvester", "local-password"
        )["id"]
        foreign = self.store.create_character(foreign_account, "Foreign Ranch")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(foreign_account, foreign_generation, foreign["id"])
        foreign_bag = HavenBagSession(foreign)
        foreign_session = RanchSession(
            foreign_bag,
            foreign_bag.inside,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease=foreign_generation,
            now_ms=1000000,
        )
        with self.assertRaises(ValueError):
            Harvests(self.store).begin(
                foreign_account,
                foreign_generation,
                foreign["id"],
                request,
                corpse,
                profession_level=0,
                reachable=True,
                location_context=lambda fresh: foreign_session.refresh(
                    foreign_session.inside, fresh
                ),
            )
        self.harvest.begin(
            self.account,
            self.generation,
            saved["id"],
            request,
            corpse,
            profession_level=0,
            reachable=True,
            location_context=project,
        )
        self.now[0] += self.rule["duration_ms"] / 1000
        result = self.harvest.complete(
            self.account,
            self.generation,
            saved["id"],
            b"\x02\x00\x06",
            monster=corpse,
            profession_level=0,
            location_context=project,
        )
        self.assertTrue(result["applied"])
        self.assertEqual(len(projected), 2)
        self.assertEqual(projected[-1]["map_id"], 1440)
        self.assertEqual(projected[-1]["instance_id"], inside["instance_id"])
        self.assertFalse(
            self.harvest.complete(
                self.account,
                self.generation,
                saved["id"],
                b"\x02\x00\x06",
                monster=corpse,
                profession_level=0,
                location_context=project,
            )["applied"]
        )
        with self.store.connection() as db:
            durable = self.store.character(self.account, saved["id"], db)
            self.assertEqual(
                tuple(durable[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                exterior,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_harvest_receipts WHERE monster_id=%s",
                    (corpse_id,),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM inventory_items WHERE character_id=%s AND reference=2731",
                    (saved["id"],),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=2731",
                    (foreign["id"],),
                ).fetchone()["n"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
