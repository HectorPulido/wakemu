"""Actual planting commits, profile-bound membership, rollback and crop custody."""
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.world import World
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_runtime as rules
from wakfu_server.objectives import environmental_bindings as bindings
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives.environmental_gameplay import GameplayFact
from test_flora_ecology_integration import FloraEcologyIntegrationTests


class EnvironmentalPlantingPolicyTests(unittest.TestCase):
    def test_initial_plant_stage_and_empty_presence_are_not_harvest_semantics(self):
        fact = GameplayFact(
            "resource_planted",
            "planting:real",
            1,
            1,
            1134,
            17,
            "resource",
            10,
            60,
            100,
            region_id=79001,
            action_id=8,
            after_step=2,
        )
        membership = dict(entity_kind="resource", entity_id=10, reference=60)
        objective = dict(family="resource_plant", required_quantity=1, resource_step=2)
        self.assertEqual(
            rules.objective_increment(objective, fact, membership=membership), 1
        )
        self.assertEqual(
            rules.objective_increment(
                dict(objective, resource_step=1), fact, membership=membership
            ),
            0,
        )
        db = Mock()
        with patch.object(presence, "_world", None):
            self.assertEqual(bindings.committed_planting(db, fact), ())
        db.execute.assert_not_called()


class EnvironmentalPlantingBindingTests(unittest.TestCase):
    def setUp(self):
        self.flora = FloraEcologyIntegrationTests(
            methodName="test_plant_improving_population_balance_then_worsening_population_stasis"
        )
        self.flora.setUp()
        self.addCleanup(self.flora.doCleanups)
        f = self.flora
        self.store = f.store
        self.world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        self.world.join(f.generation, object(), f.character)
        live = patch.object(presence, "_world", self.world)
        live.start()
        self.addCleanup(live.stop)
        self.now_ms = int(f.clock[0] * 1000)
        self.location = dict(
            map_id=f.map_id, instance_id=f.instance_id, region_id=f.region_id
        )

    def profile(self, key, *, target=60, action=None, binding=True, required=2):
        from wakfu_server.planting import SEEDS

        f = self.flora
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES(%s,1,'resource_plant','collaborative',%s,%s,60000,%s,1,245,'test-only',%s,%s)",
                (key, f.map_id, f.region_id, self.now_ms - 1000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES(%s,1,'plant','resource_plant',%s,%s,2,'interaction',%s)",
                (
                    key,
                    target,
                    SEEDS[4275]["action_id"] if action is None else action,
                    required,
                ),
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES(%s,1,0,'xp',NULL,100,'test-only')",
                (key,),
            )
            if binding:
                db.execute(
                    "INSERT INTO environmental_profile_bindings VALUES(%s,1,'committed_planting','test-only')",
                    (key,),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                (key,),
            )

    def refresh(self):
        f = self.flora
        return service.refresh(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            location=self.location,
            now_ms=self.now_ms,
        )

    def test_real_planting_binds_only_declared_matches_and_never_owns_player_crops(
        self,
    ):
        f = self.flora
        self.profile("plant-real")
        self.profile("wrong-target", target=999999)
        self.profile("wrong-action", action=999999)
        self.profile("unbound", binding=False)
        self.assertEqual(len(self.refresh()["instances"]), 4)
        first = f._prepare_plant(f.region_cells[0])
        one = f._plant(first, "environmental-plant-one")
        self.assertEqual(len(one["environmental_updates"]), 1)
        replay = f._plant(first, "environmental-plant-one")
        self.assertTrue(replay["duplicate"])
        self.assertEqual(replay.get("environmental_updates", ()), ())
        two = f._plant(f._prepare_plant(f.region_cells[1]), "environmental-plant-two")
        self.assertEqual(len(two["environmental_updates"]), 1)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT m.*,e.profile_key FROM environmental_event_memberships m JOIN environmental_event_instances e USING(instance_id)"
            ).fetchall()
            self.assertEqual({r["profile_key"] for r in rows}, {"plant-real"})
            self.assertEqual(
                {r["entity_id"] for r in rows},
                {one["resource"]["resource_uid"], two["resource"]["resource_uid"]},
            )
            self.assertTrue(all(not row["spawn_owned"] for row in rows))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                [
                    r["action"]
                    for r in db.execute(
                        "SELECT * FROM environmental_cleanup_outbox"
                    ).fetchall()
                ],
                ["release_membership", "release_membership"],
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                2,
            )
        self.assertEqual(len(self.refresh()["rewards"]["delivered"]), 1)
        self.assertEqual(self.refresh()["rewards"]["delivered"], [])
        with self.store.connection() as db:
            self.assertTrue(
                all(
                    row["completed_at_ms"] is not None
                    for row in db.execute(
                        "SELECT * FROM environmental_cleanup_outbox"
                    ).fetchall()
                )
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                2,
            )
        with self.assertRaisesRegex(Exception, "immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE environmental_profile_bindings SET source_authority='changed'"
                )

    def test_failed_plant_and_environmental_failure_preserve_the_native_transaction(
        self,
    ):
        f = self.flora
        self.profile("plant-atomic", required=1)
        self.refresh()
        failed = f._plant(
            f._prepare_plant(f.region_cells[0]), "failed-native-plant", success=False
        )
        self.assertFalse(failed["success"])
        self.assertEqual(failed["environmental_updates"], ())
        with self.store.connection() as db:
            before_seed = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s",
                (f.seed_item["uid"],),
            ).fetchone()["quantity"]
            before_ecology = db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (f.character["id"],),
            ).fetchone()
            before_xp = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                (f.account,),
            ).fetchone()["xp"]
            db.execute(
                "CREATE FUNCTION reject_env_plant() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'environmental fixture rollback'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_env_plant BEFORE INSERT ON environmental_fact_receipts FOR EACH ROW EXECUTE FUNCTION reject_env_plant()"
            )
        prepared = f._prepare_plant(f.region_cells[1])
        with self.assertRaisesRegex(Exception, "environmental fixture rollback"):
            f._plant(prepared, "environmental-atomic-plant")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (f.seed_item["uid"],),
                ).fetchone()["quantity"],
                before_seed,
            )
            self.assertEqual(
                db.execute(
                    "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                    (f.character["id"],),
                ).fetchone(),
                before_ecology,
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (f.account,),
                ).fetchone()["xp"],
                before_xp,
            )
            for table in (
                "environmental_event_memberships",
                "environmental_fact_receipts",
                "environmental_reward_entitlements",
                "planted_resources",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"],
                    0,
                    table,
                )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM planting_receipts WHERE operation_id='environmental-atomic-plant'"
                ).fetchone()
            )
            db.execute("DROP TRIGGER reject_env_plant ON environmental_fact_receipts")
        result = f._plant(prepared, "environmental-atomic-plant")
        self.assertEqual(len(result["environmental_updates"]), 1)
        self.assertEqual(len(self.refresh()["rewards"]["delivered"]), 1)


class EnvironmentalCleanupPolicyTests(unittest.TestCase):
    def test_release_never_opens_sql_for_a_vacant_scope(self):
        from wakfu_server.objectives.environmental_cleanup import release_memberships

        db = Mock()
        with patch.object(presence, "_world", None):
            self.assertEqual(
                release_memberships(db, map_id=1134, instance_id=17, now_ms=100), ()
            )
        db.execute.assert_not_called()
