"""Available-only actor rekeying retains durable rows and historical identities."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from wakfu_server.npc_actor_identity_repair import (
    repair_available_group,
    aliased_members,
)
from postgres_case import PostgresCase


class Rows:
    def __init__(self, rows=(), rowcount=0):
        self.rows, self.rowcount = list(rows), rowcount

    def __iter__(self):
        return iter(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class RepairDB:
    def __init__(self):
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.members = [
            dict(id=-((1 << 57) + 5), ref=4, level=8, hp=46),
            dict(id=-7, ref=5525, level=1, hp=12),
        ]
        self.claims = {member["id"] for member in self.members}
        self.status, self.pending = "available", False
        self.aliases, self.sql = {}, []

    def execute(self, sql, params=()):
        self.sql.append(sql)
        if sql.startswith("SELECT members,status"):
            return Rows([dict(members=deepcopy(self.members), status=self.status)])
        if sql.startswith("SELECT 1 FROM monster_"):
            return Rows([{"present": 1}] if self.pending else [])
        if sql.startswith("SELECT monster_id"):
            return Rows([dict(monster_id=value) for value in self.claims])
        if sql.startswith("SELECT old_actor_id"):
            return Rows(
                [
                    dict(old_actor_id=old, new_actor_id=new)
                    for old, new in self.aliases.items()
                ]
            )
        if sql.startswith("INSERT INTO npc_actor_identity_aliases"):
            self.aliases[params[-2]] = params[-1]
        if sql.startswith("UPDATE combat_group_members"):
            new, old = params[0], params[-1]
            if old not in self.claims:
                return Rows(rowcount=0)
            self.claims.remove(old)
            self.claims.add(new)
            return Rows(rowcount=1)
        if sql.startswith("UPDATE combat_groups"):
            self.members = deepcopy(params[0].obj)
            return Rows(rowcount=1)
        return Rows()


class LegacyNPCRepairTests(unittest.TestCase):
    @patch(
        "wakfu_server.npc_actor_identity_repair.allocate_block", return_value=1 << 50
    )
    def test_repair_and_retry_preserve_member_fields_group_and_history(self, allocate):
        db = RepairDB()
        original = deepcopy(db.members)
        result = repair_available_group(db, (527, 0, 99))
        self.assertEqual(result["status"], "remapped")
        self.assertEqual(result["key"], (527, 0, 99))
        self.assertEqual(db.members, [dict(original[0], id=-(1 << 50)), original[1]])
        self.assertEqual(db.claims, {-(1 << 50), -7})
        self.assertEqual(db.aliases, {original[0]["id"]: -(1 << 50)})
        self.assertEqual(
            repair_available_group(db, (527, 0, 99))["status"], "already_exact"
        )
        allocate.assert_called_once()
        self.assertFalse(any(sql.startswith("DELETE") for sql in db.sql))
        self.assertFalse(any("UPDATE monster_" in sql for sql in db.sql))

    @patch("wakfu_server.npc_actor_identity_repair.allocate_block")
    def test_live_or_pending_groups_never_allocate_or_mutate(self, allocate):
        for status, pending, expected in (
            ("fighting", False, "skipped_unavailable"),
            ("defeated", False, "skipped_unavailable"),
            ("available", True, "skipped_pending_ecology_publication"),
        ):
            db = RepairDB()
            db.status, db.pending = status, pending
            before = deepcopy(db.members)
            with self.subTest(status=status, pending=pending):
                self.assertEqual(
                    repair_available_group(db, (527, 0, 99))["status"], expected
                )
                self.assertEqual(db.members, before)
        allocate.assert_not_called()

    @patch("wakfu_server.npc_actor_identity_repair.allocate_block")
    def test_mismatched_claim_or_missing_transaction_rejects(self, allocate):
        db = RepairDB()
        db.claims.clear()
        with self.assertRaisesRegex(ValueError, "claims differ"):
            repair_available_group(db, (527, 0, 99))
        db.info.transaction_status = TransactionStatus.IDLE
        with self.assertRaisesRegex(ValueError, "active transaction"):
            repair_available_group(db, (527, 0, 99))
        allocate.assert_not_called()

    def test_alias_projection_does_not_rewrite_historical_receipt(self):
        historical = [dict(id=-((1 << 57) + 5), ref=4, level=8)]
        before = deepcopy(historical)
        projected = aliased_members(historical, {historical[0]["id"]: -(1 << 50)})
        self.assertEqual(historical, before)
        self.assertEqual(projected[0]["id"], -(1 << 50))


class LegacyNPCRepairPostgresTests(PostgresCase):
    """Real FK/receipt checks run only in PostgresCase's isolated schema."""

    def create_group(self, db, group_id, status, actor_id):
        members = [dict(id=actor_id, ref=4, level=8, hp=46, x=3, y=8, z=0)]
        fight_id = None
        generation = None
        if status == "fighting":
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            generation = "live-generation"
        db.execute(
            "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,generation,fight_id) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (527, 0, group_id, Jsonb(members), status, generation, fight_id),
        )
        db.execute(
            "INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) "
            "VALUES(%s,%s,%s,%s)",
            (527, 0, group_id, actor_id),
        )
        return members

    def insert_history_and_timers(self, db, group_id, actor_id):
        db.execute(
            "INSERT INTO monster_maturation_timers "
            "(map_id,instance_id,monster_id,reference,remaining_ms,last_active_ms,"
            "observer_generation,due,cycle) VALUES(527,0,%s,4,321,654,'mature',true,7)",
            (actor_id,),
        )
        db.execute(
            "INSERT INTO monster_reproduction_timers "
            "(map_id,instance_id,monster_id,reference,remaining_ms,last_active_ms,"
            "observer_generation,due,cycle) VALUES(527,0,%s,4,987,123,'repro',true,9)",
            (actor_id,),
        )
        db.execute(
            "INSERT INTO monster_maturation_receipts "
            "(map_id,instance_id,monster_id,cycle,group_id,from_reference,"
            "to_reference,draw,policy) VALUES(527,0,%s,7,%s,4,5,0.25,'{}')",
            (actor_id, group_id),
        )
        db.execute(
            "INSERT INTO monster_reproduction_receipts "
            "(map_id,instance_id,monster_id,cycle,parent_group_id,parent_reference,"
            "child_id,child_group_id,child,draw,probability,policy) "
            "VALUES(527,0,%s,9,%s,4,NULL,NULL,NULL,0.5,0.25,'{}')",
            (actor_id, group_id),
        )

    def test_079_080_cascade_only_live_timer_keys_and_preserve_receipts(self):
        old_id = -((1 << 58) + 17)
        with self.store.connection() as db:
            versions = {
                row["version"]: row["checksum"]
                for row in db.execute(
                    "SELECT version,checksum FROM schema_migrations "
                    "WHERE version IN (79,80)"
                )
            }
            self.assertEqual(set(versions), {79, 80})
            self.assertEqual(
                versions[79],
                "ddfc1e4479c066574ef636222f16d380e8073ded71326da835fd8320585b007f",
            )
            self.assertEqual(
                versions[80],
                "342ecf89392fbe28db0da0d39e51d408ff73ce9ba7317c576a04fbdba4e0d43b",
            )

            self.create_group(db, 99001, "available", old_id)
            self.insert_history_and_timers(db, 99001, old_id)
            before_reproduction = db.execute(
                "SELECT * FROM monster_reproduction_receipts WHERE map_id=527 "
                "AND instance_id=0 AND monster_id=%s AND cycle=9",
                (old_id,),
            ).fetchone()

            result = repair_available_group(db, (527, 0, 99001))
            self.assertEqual(result["status"], "remapped")
            new_id = result["aliases"][old_id]
            self.assertTrue(-(1 << 53) <= new_id < 0)
            self.assertEqual(int(float(new_id)), new_id)

            group = db.execute(
                "SELECT group_id,members,revision FROM combat_groups WHERE "
                "map_id=527 AND instance_id=0 AND group_id=99001"
            ).fetchone()
            self.assertEqual((group["group_id"], group["revision"]), (99001, 1))
            self.assertEqual(
                group["members"],
                [dict(id=new_id, ref=4, level=8, hp=46, x=3, y=8, z=0)],
            )
            self.assertEqual(
                db.execute(
                    "SELECT monster_id,remaining_ms,last_active_ms,observer_generation,due,cycle "
                    "FROM monster_maturation_timers WHERE map_id=527 AND instance_id=0"
                ).fetchone(),
                dict(
                    monster_id=new_id,
                    remaining_ms=321,
                    last_active_ms=654,
                    observer_generation="mature",
                    due=True,
                    cycle=7,
                ),
            )
            self.assertEqual(
                db.execute(
                    "SELECT monster_id,remaining_ms,last_active_ms,observer_generation,due,cycle "
                    "FROM monster_reproduction_timers WHERE map_id=527 AND instance_id=0"
                ).fetchone(),
                dict(
                    monster_id=new_id,
                    remaining_ms=987,
                    last_active_ms=123,
                    observer_generation="repro",
                    due=True,
                    cycle=9,
                ),
            )
            self.assertEqual(
                db.execute(
                    "SELECT monster_id,cycle FROM monster_maturation_receipts "
                    "WHERE map_id=527 AND instance_id=0"
                ).fetchone(),
                dict(monster_id=old_id, cycle=7),
            )
            self.assertEqual(
                db.execute(
                    "SELECT monster_id,cycle,parent_group_id FROM monster_reproduction_receipts "
                    "WHERE map_id=527 AND instance_id=0"
                ).fetchone(),
                dict(monster_id=old_id, cycle=9, parent_group_id=99001),
            )
            self.assertEqual(before_reproduction["monster_id"], old_id)
            self.assertEqual(
                repair_available_group(db, (527, 0, 99001))["status"], "already_exact"
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM npc_actor_identity_aliases "
                    "WHERE map_id=527 AND instance_id=0 AND group_id=99001"
                ).fetchone()["n"],
                1,
            )

    def test_live_group_and_pending_ecology_publication_are_untouched(self):
        fighting_id = -((1 << 58) + 101)
        pending_id = -((1 << 58) + 202)
        with self.store.connection() as db:
            self.create_group(db, 99002, "fighting", fighting_id)
            self.create_group(db, 99003, "available", pending_id)
            self.insert_history_and_timers(db, 99003, pending_id)
            db.execute(
                "INSERT INTO monster_maturation_outbox "
                "(map_id,instance_id,monster_id,cycle,group_id,revision,published) "
                "VALUES(527,0,%s,7,99003,4,false)",
                (pending_id,),
            )

            self.assertEqual(
                repair_available_group(db, (527, 0, 99002))["status"],
                "skipped_unavailable",
            )
            self.assertEqual(
                repair_available_group(db, (527, 0, 99003))["status"],
                "skipped_pending_ecology_publication",
            )
            self.assertEqual(
                db.execute(
                    "SELECT monster_id FROM combat_group_members WHERE group_id IN (99002,99003) "
                    "ORDER BY group_id"
                ).fetchall(),
                [{"monster_id": fighting_id}, {"monster_id": pending_id}],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM npc_actor_identity_aliases "
                    "WHERE group_id IN (99002,99003)"
                ).fetchone()["n"],
                0,
            )
