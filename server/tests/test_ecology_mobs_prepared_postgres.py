"""Prepared monster plans are revalidated and committed by the world owner."""
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import ecology_mobs, monster_maturation, monster_reproduction
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class PreparedMonsterEcologyPostgresTests(PostgresCase):
    map_id = 1134
    instance_id = 0

    def setUp(self):
        super().setUp()
        self.groups = PersistentGroups(self.store)
        self.harvests = SimpleNamespace(lock=RLock(), targets={})
        self.published = []
        self.world = SimpleNamespace(
            snapshot=lambda: [
                dict(id=88, map_id=self.map_id, instance_id=0, x=30000, y=30000, z=0)
            ],
            emit_location=lambda *event: self.published.append(event),
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (
                    Jsonb(
                        dict(
                            interval_ms=1000,
                            base_probability=1.0,
                            stage_decay=1.0,
                            boss_probability=0.0,
                        )
                    ),
                ),
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (
                    Jsonb(
                        dict(
                            interval_ms=1000,
                            birth_probability=1.0,
                            birth_stage_decay=1.0,
                            new_group_probability=0.0,
                            max_members=8,
                            max_zone_members=128,
                            max_zone_groups=32,
                        )
                    ),
                ),
            )
        geometry = published_geometry(self.map_id)
        self.origin, self.destination = next(
            (origin, destination)
            for origin, destinations in geometry.outgoing.items()
            for destination in destinations
            if destination[:2] != origin[:2]
        )

    def _register(self, reference, group_id, actor_id):
        member = owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            actor_id,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=self.origin[0],
            y=self.origin[1],
            z=self.origin[2],
        )
        self.groups.register(self.map_id, self.instance_id, group_id, [member])
        return member

    def _snapshot(self, *, now_ms=1000):
        return dict(
            world_epoch="boot-prepared",
            now_ms=now_ms,
            players=[
                dict(id=88, map_id=self.map_id, instance_id=0, x=30000, y=30000, z=0)
            ],
            locations=[[self.map_id, self.instance_id]],
            excluded_ids=[],
            previous_locations=[],
            allow_wander=False,
        )

    def _due_timer(self, table, member, cycle=1):
        with self.store.connection() as db:
            db.execute(
                f"INSERT INTO {table}(map_id,instance_id,monster_id,reference,"
                "remaining_ms,due,cycle) VALUES(%s,%s,%s,%s,0,true,%s)",
                (self.map_id, self.instance_id, member["id"], member["ref"], cycle),
            )

    def _proposal(self, kind, member):
        proposals = ecology_mobs.prepare(self.store, self._snapshot(), limit=8)
        return next(
            p
            for p in proposals
            if p["kind"] == kind and p["ticket"]["monster_id"] == member["id"]
        )

    def _apply(self, proposal):
        return ecology_mobs.apply(
            self.store,
            self.groups,
            self.harvests,
            self.world,
            proposal,
            world_epoch="boot-prepared",
        )

    def _count(self, table, actor_id):
        with self.store.connection() as db:
            return db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s",
                (self.map_id, self.instance_id, actor_id),
            ).fetchone()["n"]

    def test_prepared_maturation_claim_rejects_then_success_receipts_once_without_constructor(
        self,
    ):
        member = self._register(2, 98101, -98101)
        self._due_timer("monster_maturation_timers", member)
        proposal = self._proposal("maturation", member)
        self.harvests.targets[member["id"]] = 88
        self.assertEqual(self._apply(proposal), {"status": "harvesting"})
        self.assertEqual(self._count("monster_maturation_receipts", member["id"]), 0)
        self.harvests.targets.clear()

        with patch(
            "wakfu_server.monsters.owned_instance",
            side_effect=AssertionError("prepared apply rebuilt native actor"),
        ):
            self.assertEqual(self._apply(proposal), {"status": "applied"})
            self.assertEqual(self._apply(proposal), {"status": "duplicate"})
        self.assertEqual(self._count("monster_maturation_receipts", member["id"]), 1)

    def test_prepared_reproduction_stale_group_has_no_receipt_and_success_retries_idempotently(
        self,
    ):
        member = self._register(4, 98201, -98201)
        self._due_timer("monster_reproduction_timers", member)
        proposal = self._proposal("reproduction", member)
        self.harvests.targets[member["id"]] = 88
        self.assertEqual(self._apply(proposal), {"status": "harvesting"})
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 0)
        self.harvests.targets.clear()

        with patch(
            "wakfu_server.monsters.owned_instance",
            side_effect=AssertionError("prepared apply rebuilt native actor"),
        ):
            self.assertEqual(self._apply(proposal), {"status": "applied"})
            self.assertEqual(self._apply(proposal), {"status": "duplicate"})
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 1)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT child_id,child_group_id,child FROM monster_reproduction_receipts "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, member["id"]),
            ).fetchone()
            self.assertIsNotNone(receipt["child_id"])
            self.assertEqual(receipt["child"]["x"], proposal["destination"][0])
            self.assertEqual(receipt["child"]["y"], proposal["destination"][1])

    def test_prepared_reproduction_stale_roster_is_rejected_before_receipt(self):
        member = self._register(4, 98301, -98301)
        self._due_timer("monster_reproduction_timers", member)
        proposal = self._proposal("reproduction", member)
        replacement = owned_instance(
            member["ref"],
            member["level"],
            member["id"],
            map_id=self.map_id,
            instance_id=0,
            x=self.destination[0],
            y=self.destination[1],
            z=self.destination[2],
            team=member["team"],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s,revision=revision+1 "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (Jsonb([replacement]), self.map_id, 0, 98301),
            )
        self.assertEqual(self._apply(proposal), {"status": "stale_group"})
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 0)


if __name__ == "__main__":
    unittest.main()
