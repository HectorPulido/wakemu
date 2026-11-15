"""World commits frozen Rust population proposals under durable live fences.

Planner validation lives in Rust's legacy_population_contract tests. These tests
exercise the SQL authority that accepts or rejects a worker's prepared envelope.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Barrier
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_initial_population as population, native_catalog
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterInitialPopulationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.map_id, self.instance_id, self.region_id = 1134, 29, 79001
        self.groups = PersistentGroups(self.store)
        self.plan = dict(
            map_id=self.map_id,
            instance_id=self.instance_id,
            region_id=self.region_id,
            members=[
                dict(reference=5008, level=REFERENCES[5008]["min_level"], x=x, y=0, z=0)
                for x in (0, 1)
            ],
        )
        self.catalog_plans = [self.plan]
        original_load = native_catalog.load

        def load(path):
            if Path(path).name == "initial-monster-population.json":
                return dict(plans=self.catalog_plans)
            return original_load(path)

        self.catalog_patch = patch.object(native_catalog, "load", side_effect=load)
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)

    def _proposal(self, plan=None):
        # Serialize the exact worker/World contract using a fixture plan. This
        # snapshots durable fences only; it performs no geometry or planning.
        plan = self.plan if plan is None else plan
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='monster_initial_population'"
            ).fetchone()["value"]
            digest = population._scope_digest(
                population._scope_state(db, plan["map_id"], plan["instance_id"])
            )
        return dict(
            plan=deepcopy(plan),
            policy=policy,
            scope_digest=digest,
            catalog_revision=native_catalog.release(),
        )

    def _apply(self, proposal=None, groups=None):
        return population.apply_prepared(
            self.store,
            groups or self.groups,
            self._proposal() if proposal is None else proposal,
        )

    def _rows(self, table):
        with self.store.connection() as db:
            return db.execute(
                f"SELECT * FROM {table} ORDER BY map_id,instance_id"
            ).fetchall()

    def _sequence(self):
        with self.store.connection() as db:
            return dict(
                db.execute(
                    "SELECT last_value,is_called FROM lua_exact_npc_actor_ids"
                ).fetchone()
            )

    def _neighbor(self, group_id=99000):
        member = owned_instance(
            5008,
            REFERENCES[5008]["min_level"],
            -group_id,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=10,
            y=5,
            z=0,
        )
        key = self.groups.register(self.map_id, self.instance_id, group_id, [member])
        return key, member

    def test_marker_group_and_publication_are_durable_and_defeat_never_refills(self):
        proposal = self._proposal()
        self.assertEqual(self._apply(proposal), "applied")
        self.assertEqual(len(self._rows("monster_initial_population")), 1)
        self.assertEqual(len(self._rows("monster_initial_population_publication")), 1)
        members = self._rows("combat_groups")[0]["members"]
        self.assertEqual(len(members), 2)
        self.assertTrue(all(member["id"] < 0 for member in members))
        with self.store.connection() as db:
            db.execute("UPDATE combat_groups SET status='defeated'")
        before = self._sequence()
        self.assertEqual(
            self._apply(proposal, PersistentGroups(self.store, recover=True)), "stale"
        )
        self.assertEqual(self._sequence(), before)
        self.assertEqual(len(self._rows("combat_groups")), 1)
        self.assertEqual(self._rows("combat_groups")[0]["status"], "defeated")

    def test_parallel_startup_commits_one_group_and_one_marker(self):
        proposal, barrier = self._proposal(), Barrier(2)
        other = PersistentGroups(self.store)

        def apply(registry):
            barrier.wait(timeout=10)
            return self._apply(proposal, registry)

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(
                list(pool.map(apply, (self.groups, other))), ["applied", "stale"]
            )
        self.assertEqual(len(self._rows("combat_groups")), 1)
        self.assertEqual(len(self._rows("monster_initial_population")), 1)
        self.assertEqual(len(self._rows("monster_initial_population_publication")), 1)

    def test_group_marker_and_publication_roll_back_together(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_initial_population_marker() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'marker write rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_initial_population_marker BEFORE INSERT ON monster_initial_population FOR EACH ROW EXECUTE FUNCTION reject_initial_population_marker()"
            )
        with self.assertRaisesRegex(Exception, "marker write rejected"):
            self._apply()
        for table in (
            "combat_groups",
            "combat_group_members",
            "monster_initial_population",
            "monster_initial_population_publication",
        ):
            self.assertEqual(self._rows(table), [], table)

    def test_changed_live_groups_reject_stale_scope_before_identity_allocation(self):
        proposal, before = self._proposal(), self._sequence()
        self._neighbor()
        self.assertEqual(self._apply(proposal), "stale")
        self.assertEqual(self._sequence(), before)
        self.assertEqual(self._rows("monster_initial_population"), [])
        self.assertEqual(len(self._rows("combat_groups")), 1)

    def test_changed_planted_resource_rejects_stale_scope_before_identity_allocation(
        self,
    ):
        proposal, before = self._proposal(), self._sequence()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(1,%s,%s,0,0,0,60,0,0)",
                (self.map_id, self.instance_id),
            )
        self.assertEqual(self._apply(proposal), "stale")
        self.assertEqual(self._sequence(), before)
        self.assertEqual(self._rows("monster_initial_population"), [])
        self.assertEqual(self._rows("combat_groups"), [])

    def test_changed_or_disabled_policy_never_allocates_ids(self):
        proposal, before = self._proposal(), self._sequence()
        for field, value in (
            ("enabled", False),
            ("version", 2),
            ("members_per_zone", 1),
        ):
            policy = dict(proposal["policy"], **{field: value})
            with self.store.connection() as db:
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='monster_initial_population'",
                    (Jsonb(policy),),
                )
            with self.subTest(field=field):
                self.assertEqual(self._apply(proposal), "stale")
                self.assertEqual(self._sequence(), before)
        self.assertEqual(self._rows("monster_initial_population"), [])

    def test_unconfigured_or_malformed_proposal_never_allocates_ids(self):
        proposal, before = self._proposal(), self._sequence()
        bad = deepcopy(proposal)
        bad["plan"]["region_id"] += 1
        with self.assertRaisesRegex(ValueError, "not configured"):
            self._apply(bad)
        for policy in (
            None,
            dict(enabled=False, members_per_zone=2),
            dict(enabled=True, members_per_zone=True),
            dict(enabled=True, members_per_zone=1),
        ):
            with self.subTest(policy=policy), self.assertRaisesRegex(
                ValueError, "policy"
            ):
                self._apply(dict(proposal, policy=policy))
        self.assertEqual(self._sequence(), before)
        self.assertEqual(self._rows("combat_groups"), [])

    def test_changed_catalog_revision_rejects_before_database_or_identity(self):
        proposal = dict(self._proposal(), catalog_revision="retired-catalog")
        with patch.object(
            self.store,
            "connection",
            side_effect=AssertionError("stale catalog opened SQL"),
        ):
            self.assertEqual(self._apply(proposal), "stale")

    def test_marker_scope_is_region_and_instance_specific(self):
        plans = [
            self.plan,
            dict(self.plan, region_id=self.region_id + 1),
            dict(self.plan, instance_id=self.instance_id + 1),
        ]
        self.catalog_plans[:] = plans
        for plan in plans:
            self.assertEqual(self._apply(self._proposal(plan)), "applied")
        markers = self._rows("monster_initial_population")
        self.assertEqual(len(markers), 3)
        self.assertEqual(
            len({(r["map_id"], r["instance_id"], r["region_id"]) for r in markers}), 3
        )

    def test_map_capacity_includes_unique_pending_birth_and_defeat_releases_it(self):
        from wakfu_server import monster_population_capacity as capacity

        key, member = self._neighbor()
        reservation = dict(
            key=[self.map_id, self.instance_id, 99001],
            members=[dict(member, id=-99001)],
        )
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='monster_reproduction'"
            ).fetchone()["value"]
            policy["max_zone_members"] = 3
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (Jsonb(policy),),
            )
            for uid in (10, 11):
                db.execute(
                    "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,%s)",
                    (
                        uid,
                        Jsonb(dict(map_id=self.map_id, instance_id=self.instance_id)),
                        Jsonb(reservation),
                    ),
                )
            self.assertEqual(
                capacity.snapshot(db, self.map_id, self.instance_id)["members"], 2
            )
        proposal, before = self._proposal(), self._sequence()
        self.assertEqual(self._apply(proposal), "stale")
        self.assertEqual(self._sequence(), before)
        self.assertEqual(self._rows("monster_initial_population"), [])
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(key, "capacity-defeat", fight)
        self.assertTrue(self.groups.finish(lease, defeated=True))
        self.assertEqual(self._apply(self._proposal()), "applied")
        with self.store.connection() as db:
            self.assertEqual(
                capacity.snapshot(db, self.map_id, self.instance_id)["members"], 3
            )


if __name__ == "__main__":
    unittest.main()
