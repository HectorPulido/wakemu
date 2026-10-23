"""One whole-corpus import and one complete original-sized resource event."""
import hashlib
import struct
import unittest
from pathlib import Path

from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalResourceBulkPipelineTests(unittest.TestCase):
    def test_all_174_profiles_seal_and_original_hundred_resource_event_settles_once(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )
        from wakfu_server import resource_collect

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        raw = (
            Path(__file__).resolve().parents[1]
            / "seeds/environmental_resource_profiles.sql"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "7d2eace560c5bc466bb73c6128ba026d6720e6e5e188e49e23c1761cc2cdbe2b",
        )
        # Keep generated transaction wrappers out of the caller-owned isolated
        # transaction, so an import failure rolls back the complete corpus.
        sql = raw.decode().replace("\nBEGIN;\n", "\n").replace("\nCOMMIT;\n", "\n")
        with store.connection() as db:
            db.execute(sql, prepare=False)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                174,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_policies"
                ).fetchone()["n"],
                87,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT native_scenario_id) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                150,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_native_variable_bindings"
                ).fetchone()["n"],
                1305,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_resource_cells"
                ).fetchone()["n"],
                57768,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles WHERE enabled OR sealed"
                ).fetchone()["n"],
                0,
            )
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            selected = dict(
                db.execute(
                    "SELECT * FROM environmental_runtime_profiles "
                    "WHERE native_scenario_id=-1320 AND map_id=327 AND region_id=56601"
                ).fetchone()
            )
            objective = db.execute(
                "SELECT * FROM environmental_profile_objectives WHERE profile_key=%s",
                (selected["profile_key"],),
            ).fetchone()
            self.assertEqual(
                (
                    selected["mode"],
                    selected["minimum_contribution"],
                    objective["required_quantity"],
                ),
                ("collaborative", 5, 100),
            )
            expected = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_profile_rewards "
                    "WHERE profile_key=%s ORDER BY ordinal",
                    (selected["profile_key"],),
                ).fetchall()
            ]
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (selected["profile_key"],),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=true WHERE map_id=327 AND region_id=56601"
            )
            before_xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (fixture.character["id"],),
            ).fetchone()["xp"]
        connection = SelectedEnvironmentalEvents()
        self.assertTrue(
            connection.refresh(
                store,
                fixture.world,
                fixture.account,
                fixture.generation,
                fixture.character["id"],
                location=fixture.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=fixture.now_ms,
            )
        )
        first = fixture.refresh()["instances"][0]
        self.assertEqual(len(first["variables"]), 8)
        self.assertEqual(
            first["native_publication"]["variable_names"],
            [
                "challengeLevelMax",
                "challengeLevelMin",
                "nbResourceForReward",
                "nbResourceGlobal",
                "nbResourceLeft",
                "nbResourceMin",
                "nbResourcePlayer",
                "nbResourceSpawned",
            ],
        )
        with store.connection() as db:
            resources = [
                dict(r)
                for r in db.execute(
                    "SELECT p.* FROM planted_resources p "
                    "JOIN environmental_owned_resources o USING(resource_uid) ORDER BY resource_uid"
                ).fetchall()
            ]
        self.assertEqual(len(resources), 100)
        # Virtual time spans the full native event; keep the genuine selected
        # session live as World's heartbeat does during ordinary play.
        store.heartbeat(fixture.account, fixture.generation, ttl=1800)
        for resource in resources:
            ticket = fixture.ticket(resource)
            fixture.clock[0] += 5
            self.assertTrue(
                resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                    "applied"
                ]
            )
        self.assertTrue(
            connection.refresh(
                store,
                fixture.world,
                fixture.account,
                fixture.generation,
                fixture.character["id"],
                location=fixture.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=int(fixture.clock[0] * 1000),
            )
        )
        final = fixture.refresh()["instances"][0]
        self.assertEqual(final["state"], "completed")
        values = dict(
            zip(
                final["native_publication"]["variable_names"],
                [r["value"] for r in final["variables"]],
            )
        )
        self.assertEqual(
            (
                values["nbResourceGlobal"],
                values["nbResourcePlayer"],
                values["nbResourceSpawned"],
                values["nbResourceLeft"],
            ),
            (100, 100, 100, 0),
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (fixture.character["id"],),
            ).fetchone()["xp"]
            self.assertEqual(
                xp - before_xp,
                sum(r["quantity"] for r in expected if r["kind"] == "xp"),
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions"
                ).fetchone()["n"],
                100,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts"
                ).fetchone()["n"],
                100,
            )
        fixture.refresh()
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (fixture.character["id"],),
                ).fetchone()["xp"],
                xp,
            )
