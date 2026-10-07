from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from psycopg.types.json import Jsonb
from wakfu_server import monster_removal_ecology
from wakfu_server import monster_birth_ecology
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.planting_cells import cells


class MonsterRemovalEcologyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.map_id = 1134
        self.instance_id = 37
        self.region_id = 79001
        self.family_id = REFERENCES[5008]["family_id"]
        self.groups = PersistentGroups(self.store)
        self.account = self.store.register("removal-ecology", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Removal Owner")
        self._next_actor = 800000
        self._next_group = 90000

    def _locate(self, map_id, x, y, z):
        if map_id != self.map_id:
            raise ValueError("unknown map")
        return {"region_id": self.region_id}

    def _member(self, reference=5008, *, x, y=0, z=0, actor_id=None):
        if actor_id is None:
            self._next_actor += 1
            actor_id = -self._next_actor
        return owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            actor_id,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=x,
            y=y,
            z=z,
        )

    def _group(self, group_id, members):
        return self.groups.register(self.map_id, self.instance_id, group_id, members)

    def _lease(self, key, *, generation="removal-generation"):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        return self.groups.claim(key, generation, fight_id)[0]

    def _limit(self, family, minimum, maximum, *, region=None):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO ecology_family_limits(map_id,region_id,kind,family_id,minimum,maximum,source) "
                "VALUES(%s,%s,'monster',%s,%s,%s,'local') "
                "ON CONFLICT(map_id,region_id,kind,family_id) DO UPDATE "
                "SET minimum=excluded.minimum,maximum=excluded.maximum,source='local'",
                (
                    self.map_id,
                    self.region_id if region is None else region,
                    family,
                    minimum,
                    maximum,
                ),
            )

    def _state(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (self.character["id"],),
            ).fetchone()

    def _receipts(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM personal_ecology_receipts WHERE character_id=%s "
                "ORDER BY operation",
                (self.character["id"],),
            ).fetchall()

    def _single_family_setup(
        self, *, target_members=1, extra_members=0, minimum=1, maximum=1
    ):
        target = [self._member(x=index) for index in range(target_members)]
        self._next_group += 1
        key = self._group(self._next_group, target)
        if extra_members:
            extra = [self._member(x=100 + index) for index in range(extra_members)]
            self._next_group += 1
            self._group(self._next_group, extra)
        self._limit(self.family_id, minimum, maximum)
        return key

    def _status(self, key):
        return next(
            row["status"] for row in self.groups.snapshot(*key[:2]) if row["key"] == key
        )

    def _finish(self, lease, *, defeated=True, character_id=None, locate=None):
        return monster_removal_ecology.finish(
            self.store,
            self.groups,
            lease,
            character_id=self.character["id"] if character_id is None else character_id,
            defeated=defeated,
            locate=self._locate if locate is None else locate,
        )

    def test_overpopulation_removal_awards_balance_with_owner_absolute_packet_and_info(
        self,
    ):
        key = self._single_family_setup(
            target_members=1, extra_members=1, minimum=1, maximum=1
        )
        lease = self._lease(key)
        result = self._finish(lease)

        self.assertTrue(result["applied"])
        self.assertEqual(1, len(result["receipts"]))
        receipt = result["receipts"][0]
        self.assertEqual(
            (2, 1, 25),
            (
                receipt["evidence"]["before_population"],
                receipt["evidence"]["after_population"],
                receipt["requested_delta"],
            ),
        )
        self.assertEqual([13574, 349], [opcode for opcode, _ in result["packets"]])
        self.assertEqual(
            self.character["id"], int.from_bytes(result["packets"][0][1][:8], "big")
        )
        self.assertIn(
            "mejora el equilibrio",
            result["packets"][1][1].decode("utf-8", errors="ignore"),
        )
        self.assertEqual(
            {"ecology_value": 25, "ecology_revision": 1}, dict(self._state())
        )
        self.assertEqual("defeated", self._status(key))

    def test_removal_that_crosses_band_at_equal_distance_is_neutral(self):
        key = self._single_family_setup(
            target_members=2, extra_members=1, minimum=2, maximum=2
        )
        result = self._finish(self._lease(key))
        receipt = result["receipts"][0]
        self.assertEqual(
            (3, 1, 1, 1, 0),
            (
                receipt["evidence"]["before_population"],
                receipt["evidence"]["after_population"],
                receipt["evidence"]["distance_before"],
                receipt["evidence"]["distance_after"],
                receipt["requested_delta"],
            ),
        )
        self.assertEqual([13574, 349], [opcode for opcode, _ in result["packets"]])
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 1}, dict(self._state())
        )

    def test_subpopulation_removal_awards_stasis_and_overpopulation_moves_toward_band(
        self,
    ):
        below_key = self._single_family_setup(minimum=2, maximum=2)
        below = self._finish(self._lease(below_key))
        self.assertEqual(-25, below["receipts"][0]["requested_delta"])
        self.assertEqual(
            {"ecology_value": -25, "ecology_revision": 1}, dict(self._state())
        )

        # A separate schema-level character and group population keep the
        # second transition independent while checking the opposite sign.
        second = self.store.create_character(self.account, "Overpopulation Owner")
        self.character = second
        key = self._single_family_setup(
            target_members=1, extra_members=3, minimum=1, maximum=2
        )
        over = self._finish(self._lease(key))
        self.assertEqual(25, over["receipts"][0]["requested_delta"])
        self.assertEqual(
            {"ecology_value": 25, "ecology_revision": 1}, dict(self._state())
        )

    def test_nondefeated_outcome_releases_group_without_ecology_packets_or_receipts(
        self,
    ):
        key = self._single_family_setup(target_members=1, minimum=1, maximum=1)
        result = self._finish(self._lease(key), defeated=False)
        self.assertTrue(result["applied"])
        self.assertEqual([], result["packets"])
        self.assertEqual([], result["receipts"])
        self.assertEqual([], self._receipts())
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state())
        )
        self.assertEqual("available", self._status(key))

    def test_stale_duplicate_and_invalid_owner_never_duplicate_or_settle_group(self):
        key = self._single_family_setup(target_members=1, extra_members=1)
        lease = self._lease(key)
        with self.assertRaisesRegex(ValueError, "owner"):
            self._finish(lease, character_id=2**62)
        self.assertEqual("fighting", self._status(key))
        first = self._finish(lease)
        duplicate = self._finish(lease)
        self.assertTrue(first["applied"])
        self.assertFalse(duplicate["applied"])
        self.assertEqual([], duplicate["packets"])
        self.assertEqual([], duplicate["receipts"])
        self.assertEqual(1, len(self._receipts()))
        self.assertEqual(1, self._state()["ecology_revision"])

    def test_unresolved_member_surface_still_defeats_group_but_grants_no_ecology(self):
        key = self._single_family_setup(target_members=1, extra_members=1)
        lease = self._lease(key)

        def locate(map_id, x, y, z):
            if x == 100:
                raise ValueError("unknown member surface")
            return self._locate(map_id, x, y, z)

        result = self._finish(lease, locate=locate)
        self.assertTrue(result["applied"])
        self.assertEqual([], result["receipts"])
        self.assertEqual([349], [opcode for opcode, _ in result["packets"]])
        self.assertIn(
            "no se pudo determinar",
            result["packets"][0][1].decode("utf-8", errors="ignore").lower(),
        )
        self.assertEqual([], self._receipts())
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state())
        )

    def test_receipt_sql_failure_rolls_back_group_settlement_and_character(self):
        key = self._single_family_setup(target_members=1, extra_members=1)
        lease = self._lease(key)
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_removal_receipt() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'removal receipt rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_removal_receipt BEFORE INSERT ON personal_ecology_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_removal_receipt()"
            )
        with self.assertRaisesRegex(RaiseException, "removal receipt rejected"):
            self._finish(lease)
        self.assertEqual("fighting", self._status(key))
        self.assertEqual([], self._receipts())
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state())
        )
        with self.store.connection() as db:
            db.execute(
                "DROP TRIGGER reject_removal_receipt ON personal_ecology_receipts"
            )
        retry = self._finish(lease)
        self.assertTrue(retry["applied"])
        self.assertEqual(1, len(self._receipts()))

    def test_mixed_species_removal_creates_one_private_receipt_and_info_per_family(
        self,
    ):
        region = 79101
        refs = [4544, 2118]
        members = [self._member(ref, x=i) for i, ref in enumerate(refs)]
        key = self._group(90200, members)
        for family in {REFERENCES[ref]["family_id"] for ref in refs}:
            self._limit(family, 1, 1, region=region)
        lease = self._lease(key)
        result = self._finish(lease, locate=lambda *_: {"region_id": region})
        self.assertEqual(2, len(result["receipts"]))
        self.assertEqual(
            [-25, -25], sorted(r["requested_delta"] for r in result["receipts"])
        )
        self.assertEqual(
            [13574, 349, 13574, 349], [opcode for opcode, _ in result["packets"]]
        )
        self.assertEqual(2, self._state()["ecology_revision"])

    def test_two_concurrent_settlements_of_one_lease_apply_once(self):
        key = self._single_family_setup(target_members=1, extra_members=1)
        lease = self._lease(key)
        barrier = Barrier(2)

        def settle():
            barrier.wait(timeout=10)
            return self._finish(lease)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: settle(), range(2)))
        self.assertEqual(1, sum(result["applied"] for result in results))
        self.assertEqual(1, sum(bool(result["packets"]) for result in results))
        self.assertEqual(1, len(self._receipts()))
        self.assertEqual(1, self._state()["ecology_revision"])

    def test_birth_and_removal_serialize_population_and_each_award_once(self):
        points = list(
            dict.fromkeys(
                (x, y, row["z"])
                for (x, y), rows in cells(self.map_id).items()
                for row in rows
                if row["region_id"] == self.region_id
            )
        )
        target_member = self._member(x=points[0][0], y=points[0][1], z=points[0][2])
        extra_member = self._member(x=points[1][0], y=points[1][1], z=points[1][2])
        key = self._group(90300, [target_member])
        self._group(90301, [extra_member])
        self._limit(self.family_id, 2, 2)
        lease = self._lease(key)
        birth_owner = self.store.create_character(self.account, "Birth Race Owner")
        resource_uid = 990_101
        x, y, z = points[2]
        member = self._member(x=x, y=y, z=z)
        resource = {
            "resource_uid": resource_uid,
            "map_id": self.map_id,
            "instance_id": self.instance_id,
            "x": x,
            "y": y,
            "z": z,
            "resource_reference": 326,
            "stage": 1,
            "creation_time": 1_700_000_000_000,
        }
        birth_group = {
            "key": [self.map_id, self.instance_id, 90400],
            "members": [member],
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
                "VALUES('removal-birth-receipt',%s,1,%s,%s,true,1)",
                (birth_owner["id"], Jsonb({}), Jsonb(resource)),
            )
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) "
                "VALUES(%s,%s,%s)",
                (resource_uid, Jsonb(resource), Jsonb(birth_group)),
            )
        barrier = Barrier(2)

        def remove():
            barrier.wait(timeout=10)
            return self._finish(lease)

        def birth():
            barrier.wait(timeout=10)
            with self.groups.lock, self.store.connection() as db, db.transaction():
                return monster_birth_ecology.activate(db, self.groups, resource_uid)

        with ThreadPoolExecutor(max_workers=2) as pool:
            removal_future = pool.submit(remove)
            birth_future = pool.submit(birth)
            removed, born = removal_future.result(timeout=20), birth_future.result(
                timeout=20
            )
        self.assertTrue(removed["applied"])
        self.assertEqual("applied", born["reason"])
        deltas = [receipt["requested_delta"] for receipt in removed["receipts"]]
        with self.store.connection() as db:
            deltas.extend(
                row["requested_delta"]
                for row in db.execute(
                    "SELECT requested_delta FROM personal_ecology_receipts "
                    "WHERE character_id=%s AND operation LIKE 'monster-birth:%%'",
                    (birth_owner["id"],),
                )
            )
        self.assertEqual([-25, 25], sorted(deltas))
        self.assertEqual(
            {-25, 25},
            {
                self._state()["ecology_value"],
                self.store.character(self.account, birth_owner["id"])["ecology_value"],
            },
        )
        self.assertEqual("defeated", self._status(key))
        self.assertEqual(1, len(self._receipts()))


if __name__ == "__main__":
    unittest.main()
