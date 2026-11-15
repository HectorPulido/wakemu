"""Certified native unassigned actors are pruned safely with durable retry."""

from threading import RLock
from types import SimpleNamespace

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import monster_population_cleanup as subject
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterPopulationCleanupTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.groups = PersistentGroups(self.store)
        self.harvests = SimpleNamespace(lock=RLock(), targets={})
        self.events = []
        self.world = SimpleNamespace(
            emit_location_batch=lambda *args, **kwargs: self.events.append(
                (args, kwargs)
            )
        )
        self.members = [
            self.member(-8101, -162, -125, -4),
            self.member(-8102, -163, -125, -4),
            self.member(-8103, 30000, 30000, 0),
        ]
        self.key = self.groups.register(527, 0, 8101, self.members)
        self.snapshot = dict(
            world_epoch="cleanup-test", planning_tick=1, players=[], excluded_ids=[]
        )

    def member(self, identity, x, y, z):
        return owned_instance(
            6,
            REFERENCES[6]["min_level"],
            identity,
            map_id=527,
            instance_id=0,
            x=x,
            y=y,
            z=z,
        )

    def proposal(self):
        # Explicit Rust-shaped result; planner selection/cadence/ownership
        # execute in Rust mob_idle::cleanup_contract against the native catalog.
        return dict(
            kind="cleanup_unassigned",
            world_epoch="cleanup-test",
            scope=[527, 0],
            group_id=8101,
            expected_members=self.members,
            actor_ids=[-8102],
        )

    def apply(self, proposal):
        return subject.apply(
            self.store,
            self.groups,
            self.harvests,
            self.world,
            proposal,
            world_epoch="cleanup-test",
        )

    def test_world_certifies_only_exact_unassigned_native_cells(self):
        self.assertTrue(subject.certified_unassigned(527, self.members[1]))
        self.assertFalse(subject.certified_unassigned(527, self.members[0]))
        self.assertFalse(subject.certified_unassigned(527, self.members[2]))

    def test_private_cleanup_scope_is_rejected_without_mutation(self):
        proposal = self.proposal()
        proposal["scope"] = [527, 17]
        with self.assertRaisesRegex(ValueError, "Invalid cleanup scope"):
            self.apply(proposal)
        self.assertEqual(self.events, [])

    def test_cleanup_commit_survives_delivery_failure_and_replay_preserves_survivors(
        self,
    ):
        proposal = self.proposal()
        with self.store.connection() as db:
            for member in self.members:
                for table in (
                    "monster_maturation_timers",
                    "monster_reproduction_timers",
                ):
                    db.execute(
                        f"INSERT INTO {table}(map_id,instance_id,monster_id,reference,remaining_ms) VALUES(527,0,%s,6,1000)",
                        (member["id"],),
                    )

        def failed(*args, **kwargs):
            raise OSError("delivery unavailable")

        self.world.emit_location_batch = failed
        with self.assertRaisesRegex(OSError, "delivery unavailable"):
            self.apply(proposal)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT members,ecology_admin_removed_ids,revision FROM combat_groups WHERE map_id=527 AND instance_id=0 AND group_id=8101"
            ).fetchone()
            self.assertEqual([m["id"] for m in row["members"]], [-8101, -8103])
            self.assertEqual(row["ecology_admin_removed_ids"], [-8102])
            revision = row["revision"]
            for table in ("monster_maturation_timers", "monster_reproduction_timers"):
                self.assertEqual(
                    [
                        r["monster_id"]
                        for r in db.execute(
                            f"SELECT monster_id FROM {table} ORDER BY monster_id"
                        )
                    ],
                    [-8103, -8101],
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                0,
            )
        self.world.emit_location_batch = lambda *args, **kwargs: self.events.append(
            (args, kwargs)
        )
        self.assertEqual(
            self.apply(proposal), dict(status="applied", removed=1, duplicate=True)
        )
        self.assertTrue(self.events[0][1]["require_all"])
        self.assertEqual([packet[0] for packet in self.events[0][0][2]], [12304, 12608])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM combat_groups WHERE map_id=527 AND instance_id=0 AND group_id=8101"
                ).fetchone()["revision"],
                revision,
            )

    def test_active_fight_and_harvest_prevent_mutation(self):
        proposal = self.proposal()
        self.harvests.targets[-8102] = 99
        self.assertEqual(self.apply(proposal), {"status": "harvesting"})
        self.harvests.targets.clear()
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        self.groups.claim(self.key, "cleanup-fight", fight_id)
        self.assertEqual(self.apply(proposal), {"status": "stale_group"})
        self.assertEqual(self.events, [])

    def test_harvesting_healthy_survivor_also_prevents_remove_and_respawn(self):
        proposal = self.proposal()
        self.harvests.targets[-8101] = 99
        self.assertEqual(self.apply(proposal), {"status": "harvesting"})
        self.assertEqual(self.events, [])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT ecology_admin_removed_ids FROM combat_groups WHERE map_id=527 AND instance_id=0 AND group_id=8101"
            ).fetchone()
        self.assertEqual(row["ecology_admin_removed_ids"], [])

    def test_unknown_native_or_healthy_actor_is_never_deletion_evidence(self):
        proposal = self.proposal()
        for identity in (-8101, -8103):
            proposal["actor_ids"] = [identity]
            self.assertEqual(self.apply(proposal), {"status": "stale_group"})
        self.assertEqual(self.events, [])

    def test_stale_epoch_or_roster_cannot_remove_current_actors(self):
        proposal = self.proposal()
        proposal["world_epoch"] = "old"
        self.assertEqual(self.apply(proposal), {"status": "stale_epoch"})
        proposal["world_epoch"] = "cleanup-test"
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s,revision=revision+1 WHERE map_id=527 AND instance_id=0 AND group_id=8101",
                (Jsonb(self.members + [self.member(-8104, -162, -124, -4)]),),
            )
        self.assertEqual(self.apply(proposal), {"status": "stale_group"})
        self.assertEqual(self.events, [])
