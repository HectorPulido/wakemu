"""One bulk import qualifies declared character slots over original resource stock."""
import hashlib
import struct
import unittest
from pathlib import Path

from wakfu_server.characters import heroes
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server import resource_collect


class EnvironmentalResourceRaceBulkTests(unittest.TestCase):
    def test_all_87_race_profiles_seal_and_company_occupies_three_character_slots_once(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        additions = [
            store.create_character(fixture.account, name)
            for name in ("Race Companion One", "Race Companion Two")
        ]
        for hero in additions:
            with store.connection() as db:
                db.execute("UPDATE characters SET level=81 WHERE id=%s", (hero["id"],))
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (XP_BY_LEVEL[81], hero["id"]),
                )
            heroes.add(
                store,
                fixture.account,
                fixture.generation,
                fixture.character["id"],
                hero["id"],
            )
        members = [fixture.character["id"], *[r["id"] for r in additions]]
        seeds = Path(__file__).resolve().parents[1] / "seeds"
        race = (seeds / "environmental_resource_races.sql").read_bytes()
        self.assertEqual(
            hashlib.sha256(race).hexdigest(),
            "5ccc89f749e7e98d12df6240dd2b2c7f865fadf925a7026adfe4062f23d3b2e5",
        )
        with store.connection() as db:
            for raw in (
                (seeds / "environmental_resource_profiles.sql").read_bytes(),
                race,
            ):
                db.execute(
                    raw.decode()
                    .replace("\nBEGIN;\n", "\n")
                    .replace("\nCOMMIT;\n", "\n"),
                    prepare=False,
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                261,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT native_scenario_id) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                225,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles WHERE mode='race'"
                ).fetchone()["n"],
                87,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_candidates WHERE version=2"
                ).fetchone()["n"],
                261,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles WHERE enabled"
                ).fetchone()["n"],
                0,
            )
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            profile = dict(
                db.execute(
                    "SELECT * FROM environmental_runtime_profiles "
                    "WHERE native_scenario_id=-1322 AND map_id=327 AND region_id=56601"
                ).fetchone()
            )
            evaluation = db.execute(
                "SELECT * FROM environmental_profile_evaluation WHERE profile_key=%s",
                (profile["profile_key"],),
            ).fetchone()
            self.assertEqual(
                (evaluation["evaluator"], evaluation["winner_count"]),
                ("first_completion", 3),
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (profile["profile_key"],),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=true WHERE map_id=327 AND region_id=56601 AND version=2"
            )
        first = fixture.refresh()
        event = first["instances"][0]["instance_id"]
        with store.connection() as db:
            resources = [
                dict(r)
                for r in db.execute(
                    "SELECT p.* FROM planted_resources p "
                    "JOIN environmental_owned_resources o USING(resource_uid)"
                ).fetchall()
            ]
            self.assertEqual(len(resources), 3)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_participants WHERE instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                3,
            )
        ticket = fixture.ticket(resources[0])
        fixture.clock[0] += 5
        self.assertTrue(
            resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        delivered = fixture.refresh()
        self.assertEqual(len(delivered["rewards"]["delivered"]), 1)
        self.assertEqual(
            [
                len(delivered["hero_rewards"][identity]["delivered"])
                for identity in members[1:]
            ],
            [1, 1],
        )
        with store.connection() as db:
            ranked = db.execute(
                "SELECT character_id,position FROM environmental_event_rankings WHERE instance_id=%s ORDER BY position",
                (event,),
            ).fetchall()
            self.assertEqual(
                [(r["character_id"], r["position"]) for r in ranked],
                list(zip(members, (1, 2, 3))),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions WHERE instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_resources WHERE retired_at_ms IS NOT NULL"
                ).fetchone()["n"],
                3,
            )
        self.assertFalse(
            resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        repeated = fixture.refresh()
        self.assertEqual(repeated["rewards"]["delivered"], [])
        self.assertTrue(
            all(not r["delivered"] for r in repeated["hero_rewards"].values())
        )
