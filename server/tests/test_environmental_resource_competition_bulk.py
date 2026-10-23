"""One complete public seed import and an actual original-sized competition."""
import hashlib
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from wakfu_server import health_store, resource_collect
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.objectives import environmental_service
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalResourceCompetitionBulkTests(unittest.TestCase):
    def test_all_348_profiles_seal_and_native_occupations_settle_three_original_bands_once(
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
        owners = [(fixture.account, fixture.generation, fixture.character)]
        for suffix, name, point in (
            ("second", "Rank Second", fixture.points[-2]),
            ("third", "Rank Third", fixture.points[-3]),
        ):
            account = store.register("resource-competition-" + suffix, "test-password")[
                "id"
            ]
            character = store.create_character(account, name)
            generation = store.begin_session(account)
            store.select_character(account, generation, character["id"])
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=81,map_id=327,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (*point, character["id"]),
                )
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (XP_BY_LEVEL[81], character["id"]),
                )
            character = health_store.initialize(
                store, account, generation, character["id"]
            )
            fixture.world.join(
                generation, SimpleNamespace(shutdown=lambda *_: None), character
            )
            owners.append((account, generation, character))
        for account, generation, _ in owners:
            # Actual native occupations advance virtual time through the full
            # original event; use a genuine heartbeat, not a forged lease row.
            store.heartbeat(account, generation, ttl=1800)

        seeds = Path(__file__).resolve().parents[1] / "seeds"
        hashes = (
            (
                "environmental_resource_profiles.sql",
                "7d2eace560c5bc466bb73c6128ba026d6720e6e5e188e49e23c1761cc2cdbe2b",
            ),
            (
                "environmental_resource_races.sql",
                "5ccc89f749e7e98d12df6240dd2b2c7f865fadf925a7026adfe4062f23d3b2e5",
            ),
            (
                "environmental_resource_competitions.sql",
                "0c18f56a635fc9c44f091f1d3a0c4db6b3d793a9aebdb2c9dd0c97b631563e2e",
            ),
            (
                "environmental_resource_results.sql",
                "b1ab66b98fd64703a06e21ca2997f825c9368b18ab599abb2aa4f4bf40b3f666",
            ),
        )
        with store.connection() as db:
            for filename, expected_hash in hashes:
                raw = (seeds / filename).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_hash)
                sql = (
                    raw.decode()
                    .replace("\nBEGIN;\n", "\n")
                    .replace("\nCOMMIT;\n", "\n")
                )
                db.execute(sql, prepare=False)
            counts = {
                "environmental_runtime_profiles": 348,
                "environmental_profile_native_variable_bindings": 2610,
                "environmental_profile_resource_cells": 87058,
                "environmental_profile_simple_result_policy": 174,
                "environmental_profile_ranked_reward_policy": 174,
                "environmental_profile_ranked_reward_bands": 348,
            }
            for table, expected in counts.items():
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"],
                    expected,
                    table,
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT native_scenario_id) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                300,
            )
            self.assertEqual(
                [
                    (r["mode"], r["n"])
                    for r in db.execute(
                        "SELECT mode,count(*) AS n FROM environmental_runtime_profiles GROUP BY mode ORDER BY mode"
                    )
                ],
                [
                    ("collaborative", 87),
                    ("competitive", 87),
                    ("race", 87),
                    ("solo", 87),
                ],
            )
            for version, candidates in ((1, 174), (2, 261), (3, 348)):
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_regional_schedule_policies WHERE version=%s",
                        (version,),
                    ).fetchone()["n"],
                    87,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_regional_schedule_candidates WHERE version=%s",
                        (version,),
                    ).fetchone()["n"],
                    candidates,
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles WHERE enabled OR sealed"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_policies WHERE enabled OR sealed"
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
                    "WHERE native_scenario_id=-1321 AND map_id=327 AND region_id=56601"
                ).fetchone()
            )
            objective = db.execute(
                "SELECT * FROM environmental_profile_objectives WHERE profile_key=%s",
                (profile["profile_key"],),
            ).fetchone()
            self.assertEqual(
                (
                    profile["mode"],
                    profile["minimum_contribution"],
                    objective["required_quantity"],
                    objective["action_id"],
                    objective["resource_step"],
                ),
                ("competitive", 10, 10, 1190, 2),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_rewards WHERE profile_key=%s",
                    (profile["profile_key"],),
                ).fetchone()["n"],
                0,
            )
            expected_rewards = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM environmental_native_reward_display WHERE source_key=%s "
                    "AND scenario_id=-1321 AND primary_reward_list ORDER BY primary_result_index",
                    ("installed-environmental-source-v1",),
                )
            ]
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (profile["profile_key"],),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=true "
                "WHERE map_id=327 AND region_id=56601 AND version=3"
            )
            before_xp = {
                row["character_id"]: row["xp"]
                for row in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    ([owner[2]["id"] for owner in owners],),
                )
            }

        for account, generation, character in owners:
            admitted = environmental_service.refresh(
                store,
                account,
                generation,
                character["id"],
                location=fixture.location,
                now_ms=int(fixture.clock[0] * 1000),
            )
            self.assertEqual(admitted["instances"][0]["native_scenario_id"], -1321)
        event_id = admitted["instances"][0]["instance_id"]
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            resources = [
                dict(row)
                for row in db.execute(
                    "SELECT p.* FROM planted_resources p "
                    "JOIN environmental_owned_resources o USING(resource_uid) ORDER BY resource_uid"
                )
            ]
        self.assertEqual(len(resources), 100)
        from wakfu_server.wire import proto_field

        offset, last_ticket = 0, None
        for score, (account, generation, character) in zip((10, 20, 30), owners):
            for resource in resources[offset : offset + score]:
                unsigned = lambda value: value if value >= 0 else value + (1 << 64)
                body = (
                    proto_field(8, 1190)
                    + proto_field(16, unsigned(resource["x"]))
                    + proto_field(24, unsigned(resource["y"]))
                )
                prepared = resource_collect.prepare(
                    store,
                    account,
                    generation,
                    character["id"],
                    body,
                    reachable=lambda *_: True,
                )
                last_ticket = resource_collect.reserve(
                    store, account, generation, prepared
                )
                fixture.clock[0] += 5
                self.assertTrue(
                    resource_collect.complete(
                        store, last_ticket, struct.pack(">Bh", 2, 3)
                    )["applied"]
                )
            offset += score
        self.assertFalse(
            resource_collect.complete(store, last_ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        view = fixture.refresh()["instances"][0]
        variables = dict(
            zip(
                view["native_publication"]["variable_names"],
                [r["value"] for r in view["variables"]],
            )
        )
        self.assertEqual(
            (
                view["state"],
                variables["nbResourcePlayer"],
                variables["nbResourceGlobal"],
                variables["nbResourceMax"],
                variables["nbResourceLeft"],
                variables["nbResourceSpawned"],
            ),
            ("active", 10, 60, 30, 40, 100),
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts"
                ).fetchone()["n"],
                60,
            )
        fixture.clock[0] = (event["deadline_ms"] + 1) / 1000
        for rank, (account, generation, character) in zip((3, 2, 1), owners):
            connection = SelectedEnvironmentalEvents()
            start = len(fixture.batches)
            self.assertTrue(
                connection.refresh(
                    store,
                    fixture.world,
                    account,
                    generation,
                    character["id"],
                    location=fixture.location,
                    ready=True,
                    checkpoint=lambda: None,
                    now_ms=int(fixture.clock[0] * 1000),
                )
            )
            bodies = [
                payload
                for batch in fixture.batches[start:]
                for opcode, payload in batch
                if opcode == 13263
            ]
            self.assertEqual(len(bodies), 1)
            body = bodies[0]
            challenge, _, length = struct.unpack_from(">iib", body)
            winner = body[9 : 9 + length].decode("utf-8")
            score, wire_rank, reward_index = struct.unpack_from(
                ">ihi", body, 9 + length
            )
            self.assertEqual(
                (challenge, winner, score, wire_rank, reward_index),
                (-1321, owners[2][2]["name"], 30, rank - 1, rank - 1),
            )
            with store.connection() as db:
                xp = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["xp"]
                self.assertEqual(
                    xp - before_xp[character["id"]],
                    expected_rewards[rank - 1]["base_xp"],
                )
            replay = environmental_service.refresh(
                store,
                account,
                generation,
                character["id"],
                location=fixture.location,
                now_ms=int(fixture.clock[0] * 1000),
            )
            self.assertEqual(replay["rewards"]["delivered"], [])
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                3,
            )
            ranked = db.execute(
                "SELECT character_id,score,display_rank,rewarded FROM environmental_event_rankings "
                "WHERE instance_id=%s ORDER BY position",
                (event_id,),
            ).fetchall()
            self.assertEqual(
                [
                    (
                        row["character_id"],
                        row["score"],
                        row["display_rank"],
                        row["rewarded"],
                    )
                    for row in ranked
                ],
                [
                    (owner[2]["id"], score, rank, True)
                    for owner, score, rank in (
                        (owners[2], 30, 1),
                        (owners[1], 20, 2),
                        (owners[0], 10, 3),
                    )
                ],
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["state"],
                "completed",
            )
            # The enabled occupied schedule immediately starts its next real
            # window. The old100 members are retired, not reused or counted
            # toward that new event; no synthetic depletion shortcut is used.
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_resources "
                    "WHERE instance_id=%s AND retired_at_ms IS NOT NULL",
                    (event_id,),
                ).fetchone()["n"],
                100,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planted_resources p "
                    "JOIN environmental_owned_resources o USING(resource_uid) WHERE o.instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )
