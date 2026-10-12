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
        # Existing fixtures isolate receipt/locking behavior on synthetic surfaces.
        habitat = patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=True,
        )
        habitat.start()
        self.addCleanup(habitat.stop)
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

    def test_prepared_maturation_claim_rejects_then_validates_transition_once(
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
            "wakfu_server.monsters.owned_instance", wraps=owned_instance
        ) as rebuild:
            self.assertEqual(self._apply(proposal), {"status": "applied"})
            self.assertEqual(self._apply(proposal), {"status": "duplicate"})
        # Rebuild only when the worker proposed a real transition, and never
        # for the duplicate replay.
        self.assertEqual(rebuild.call_count, int(proposal["grown"] is not None))
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
            "wakfu_server.monsters.owned_instance", wraps=owned_instance
        ) as rebuild:
            self.assertEqual(self._apply(proposal), {"status": "applied"})
            self.assertEqual(self._apply(proposal), {"status": "duplicate"})
        # The world owner reconstructs the proposed child once to verify its
        # native fields; a replay returns the durable receipt without rebuilding.
        self.assertEqual(rebuild.call_count, 1)
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

    def test_prepared_reproduction_respects_live_zone_member_cap(self):
        member = self._register(4, 98401, -98401)
        self._due_timer("monster_reproduction_timers", member)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{max_zone_members}','1'::jsonb) "
                "WHERE name='monster_reproduction'"
            )
        with patch("wakfu_server.ecology_mobs._sample", return_value=0.0):
            proposal = self._proposal("reproduction", member)
        self.assertIsNotNone(proposal["child"])
        self.assertEqual(self._apply(proposal), {"status": "stale_group"})
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 0)
        with self.store.connection() as db:
            roster = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (self.map_id, self.instance_id, 98401),
            ).fetchone()["members"]
        self.assertEqual([member], roster)

    def test_prepared_reproduction_at_group_cap_appends_inside_existing_group(self):
        member = self._register(4, 98501, -98501)
        self._due_timer("monster_reproduction_timers", member)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{max_zone_groups}','1'::jsonb) "
                "WHERE name='monster_reproduction'"
            )
        with patch("wakfu_server.ecology_mobs._sample", return_value=0.0):
            proposal = self._proposal("reproduction", member)
        self.assertIsNotNone(proposal["child"])
        self.assertEqual(self._apply(proposal), {"status": "applied"})
        with self.store.connection() as db:
            groups = db.execute(
                "SELECT count(*) AS n FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
                (self.map_id, self.instance_id),
            ).fetchone()["n"]
            roster = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (self.map_id, self.instance_id, 98501),
            ).fetchone()["members"]
        self.assertEqual(1, groups)
        self.assertEqual(2, len(roster))

    def test_prepared_reproduction_at_member_cap_starts_a_separate_group(self):
        member = self._register(4, 98601, -98601)
        self._due_timer("monster_reproduction_timers", member)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set("
                "jsonb_set(value,'{max_members}','1'::jsonb),"
                "'{new_group_probability}','0.5'::jsonb) "
                "WHERE name='monster_reproduction'"
            )
        with patch("wakfu_server.ecology_mobs._sample", return_value=0.0):
            proposal = self._proposal("reproduction", member)
        self.assertIsNotNone(proposal["child"])
        self.assertEqual(self._apply(proposal), {"status": "applied"})
        with self.store.connection() as db:
            groups = db.execute(
                "SELECT group_id,members FROM combat_groups "
                "WHERE map_id=%s AND instance_id=%s AND status!='defeated' ORDER BY group_id",
                (self.map_id, self.instance_id),
            ).fetchall()
        self.assertEqual(2, len(groups))
        by_id = {row["group_id"]: row["members"] for row in groups}
        self.assertEqual([member], by_id[98601])
        newborn_groups = [
            members for group_id, members in by_id.items() if group_id != 98601
        ]
        self.assertEqual(1, len(newborn_groups[0]))

    def test_worker_omits_birth_when_all_adjacent_cells_are_outside_native_territory(
        self,
    ):
        member = self._register(4, 98701, -98701)
        self._due_timer("monster_reproduction_timers", member)
        with patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=False,
        ) as allowed:
            proposals = ecology_mobs.prepare(self.store, self._snapshot(), limit=8)
        self.assertTrue(allowed.called)
        self.assertFalse(any(p["kind"] == "reproduction" for p in proposals))
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 0)

    def test_commit_rejects_prepared_birth_into_now_invalid_native_territory(self):
        member = self._register(4, 98801, -98801)
        self._due_timer("monster_reproduction_timers", member)
        with patch("wakfu_server.ecology_mobs._sample", return_value=0.0):
            proposal = self._proposal("reproduction", member)
        self.assertIsNotNone(proposal["child"])
        with patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=False,
        ) as allowed:
            result = self._apply(proposal)
        self.assertTrue(allowed.called)
        self.assertEqual(result, {"status": "stale_group"})
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 0)
        self.assertEqual(self._count("monster_reproduction_outbox", member["id"]), 0)
        self.assertEqual(self.published, [])

    def test_commit_rejects_forged_nonadjacent_prepared_birth(self):
        member = self._register(4, 98901, -98901)
        self._due_timer("monster_reproduction_timers", member)
        with patch("wakfu_server.ecology_mobs._sample", return_value=0.0):
            proposal = self._proposal("reproduction", member)
        destination = (300000, 300000, 0)
        proposal["destination"] = list(destination)
        proposal["child"] = owned_instance(
            proposal["child"]["ref"],
            proposal["child"]["level"],
            proposal["child"]["id"],
            map_id=self.map_id,
            instance_id=0,
            x=destination[0],
            y=destination[1],
            z=destination[2],
            team=member["team"],
        )
        self.assertEqual(self._apply(proposal), {"status": "stale_group"})
        self.assertEqual(self._count("monster_reproduction_receipts", member["id"]), 0)
        self.assertEqual(self.published, [])

    def test_worker_wander_never_proposes_entering_invalid_native_territory(self):
        self._register(2, 99001, -99001)
        snapshot = self._snapshot()
        snapshot["allow_wander"] = True
        snapshot["players"][0].update(
            x=self.origin[0], y=self.origin[1], z=self.origin[2]
        )
        with patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=False,
        ) as allowed, patch(
            "wakfu_server.ecology_mobs.random.random", return_value=0.0
        ):
            proposals = ecology_mobs.prepare(self.store, snapshot, limit=8)
        self.assertTrue(allowed.called)
        self.assertFalse(any(proposal["kind"] == "wander" for proposal in proposals))
        self.assertEqual(self.published, [])

    def test_wander_gets_reserved_slot_when_cleanup_fills_background_budget(self):
        self._register(2, 99002, -99002)
        snapshot = self._snapshot()
        snapshot["allow_wander"] = True
        snapshot["domain_planning_tick"] = 0
        snapshot["players"][0].update(
            x=self.origin[0] + 10, y=self.origin[1] + 10, z=self.origin[2]
        )
        cleanup_rows = [
            dict(kind="cleanup_unassigned", world_epoch="boot-prepared")
            for _ in range(7)
        ]
        with patch(
            "wakfu_server.monster_population_cleanup.prepare",
            return_value=cleanup_rows,
        ) as cleanup, patch(
            "wakfu_server.ecology_mobs.random.random", return_value=0.0
        ), patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=True,
        ):
            proposals = ecology_mobs.prepare(self.store, snapshot, limit=8)
        cleanup.assert_called_once()
        self.assertEqual(cleanup.call_args.kwargs["limit"], 7)
        bulk = [proposal for proposal in proposals if proposal["kind"] == "wander_bulk"]
        self.assertEqual(len(bulk), 1)
        self.assertLessEqual(
            len(bulk[0]["moves"]), ecology_mobs.MAX_WANDER_BATCH_GROUPS
        )
        self.assertLessEqual(
            sum(len(move["packets"]) for move in bulk[0]["moves"]),
            ecology_mobs.MAX_WANDER_BATCH_MOVED_MEMBERS,
        )


if __name__ == "__main__":
    unittest.main()
