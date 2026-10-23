"""One reader/projection PG contract; durable completion is an explicit premise."""
import struct

import psycopg

from postgres_case import PostgresCase
from wakfu_server.objectives import environmental_simple_results as simple
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives.environmental_result_delivery import plan_result_delivery


SOURCE = "installed-environmental-source-v1"


class EnvironmentalSimpleResultTests(PostgresCase):
    def test_actual_view_projects_solo_and_shared_earned_primary_without_granting_or_fallback(
        self,
    ):
        account = self.store.register("simple-result-owner", "test-password")["id"]
        actor = self.store.create_character(account, "Simple Result")
        with self.store.connection() as db:
            initial_xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (actor["id"],),
            ).fetchone()["xp"]
            cases = []
            for mode, scenario, parameter_mode in (
                ("solo", -2249, "personal_progress"),
                ("collaborative", -2246, "global_progress"),
            ):
                primary = db.execute(
                    "SELECT d.*,r.native_text FROM environmental_native_reward_display d "
                    "JOIN environmental_native_rewards_raw r USING(source_key,scenario_id,reward_id) "
                    "WHERE d.source_key=%s AND d.scenario_id=%s AND d.primary_reward_list",
                    (SOURCE, scenario),
                ).fetchall()
                self.assertEqual(len(primary), 1)
                reward = primary[0]
                self.assertEqual(
                    (reward["primary_result_index"], reward["native_text"]), (0, "")
                )
                key = "simple-" + mode
                db.execute(
                    "INSERT INTO environmental_runtime_profiles "
                    "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,"
                    "level_min,level_max,authority,source_sha256,catalog_revision) "
                    "VALUES(%s,1,%s,'resource_collect',%s,527,17,60000,0,1,245,%s,%s,%s)",
                    (
                        key,
                        scenario,
                        mode,
                        "component reader: original base grants, no boosters",
                        "0" * 64,
                        "1" * 64,
                    ),
                )
                db.execute(
                    "INSERT INTO environmental_profile_objectives VALUES "
                    "(%s,1,'collect','resource_collect',849,3,1,'interaction',1)",
                    (key,),
                )
                db.execute(
                    "INSERT INTO environmental_profile_publication VALUES "
                    "(%s,1,%s,0,0,0,'constant','component original display profile')",
                    (key, scenario),
                )
                for state, ordinal in (
                    ("proposed", 0),
                    ("active", 1),
                    ("completed", 2),
                    ("expired", 3),
                ):
                    db.execute(
                        "INSERT INTO environmental_profile_publication_states VALUES(%s,1,%s,%s)",
                        (key, state, ordinal),
                    )
                db.execute(
                    "INSERT INTO environmental_profile_simple_result_policy VALUES "
                    "(%s,1,%s,%s,%s,%s,0,%s,%s,%s,%s)",
                    (
                        key,
                        SOURCE,
                        scenario,
                        reward["reward_id"],
                        simple.CONTRACT,
                        parameter_mode,
                        "original one unconditional primary reward",
                        "Wakemu original display base XP/items; no boosters",
                        "Wakemu interpretation: actual "
                        + parameter_mode
                        + " as native winnerScore",
                    ),
                )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET sealed=true WHERE profile_key=%s",
                    (key,),
                )
                event = dict(
                    db.execute(
                        "INSERT INTO environmental_event_instances "
                        "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state) "
                        "VALUES(%s,1,527,0,17,0,1,60001,'active') RETURNING *",
                        (key,),
                    ).fetchone()
                )
                participant = dict(
                    db.execute(
                        "INSERT INTO environmental_participants "
                        "(instance_id,character_id,account_id,joined_at_ms,completed_at_ms) "
                        "VALUES(%s,%s,%s,1,10) RETURNING *",
                        (event["instance_id"], actor["id"], account),
                    ).fetchone()
                )
                entitlement = db.execute(
                    "INSERT INTO environmental_reward_entitlements "
                    "(instance_id,character_id,account_id,earned_at_ms) VALUES(%s,%s,%s,10) RETURNING entitlement_id",
                    (event["instance_id"], actor["id"], account),
                ).fetchone()["entitlement_id"]
                # These durable rows are the reader component's premise, not
                # evidence that a player paid/finished a real world mission.
                for ordinal, (kind, reference, quantity) in enumerate(
                    simple._components(reward)
                ):
                    db.execute(
                        "INSERT INTO environmental_reward_components VALUES(%s,%s,%s,%s,%s,%s)",
                        (
                            entitlement,
                            ordinal,
                            kind,
                            reference,
                            quantity,
                            "declared original base grant",
                        ),
                    )
                db.execute(
                    "INSERT INTO environmental_progress VALUES(%s,%s,%s,3)",
                    (event["instance_id"], actor["id"], "collect"),
                )
                db.execute(
                    "INSERT INTO environmental_shared_actions VALUES(%s,%s,%s,%s,%s,%s,7,9)",
                    (
                        event["instance_id"],
                        "collect",
                        "reader-premise",
                        "resource",
                        99,
                        "0" * 64,
                    ),
                )
                profile = dict(
                    db.execute(
                        "SELECT * FROM environmental_runtime_profiles WHERE profile_key=%s",
                        (key,),
                    ).fetchone()
                )
                cases.append((event, profile, participant, entitlement))
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for event, profile, participant, entitlement in cases:
                before = [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM environmental_reward_components "
                        "WHERE entitlement_id=%s ORDER BY ordinal",
                        (entitlement,),
                    )
                ]
                view = storage._view(db, event, profile, participant, 20)
                mapping = view["native_result"]
                self.assertIsNotNone(mapping)
                self.assertEqual(
                    mapping, simple.project(db, event, profile, participant, 20)
                )
                expected_score = 3 if profile["mode"] == "solo" else 7
                self.assertEqual(
                    (
                        mapping["result_parameter"],
                        mapping["primary_reward_count"],
                        mapping["primary_reward_index"],
                        mapping["name"],
                        mapping["display_rank"],
                    ),
                    (expected_score, 1, 0, None, 0),
                )
                delivery = dict(
                    delivery_key="simple:" + str(event["instance_id"]),
                    kind="completed",
                    instance_id=event["instance_id"],
                    revision=event["revision"],
                    account_id=account,
                    character_id=actor["id"],
                )
                plan = plan_result_delivery(
                    delivery, view, account_id=account, character_id=actor["id"]
                )
                self.assertEqual(
                    plan["packets"],
                    (
                        (
                            13263,
                            struct.pack(
                                ">iibihi",
                                profile["native_scenario_id"],
                                0,
                                0,
                                expected_score,
                                -1,
                                0,
                            ),
                        ),
                    ),
                )
                self.assertEqual(
                    simple.project(db, event, profile, participant, 20), mapping
                )
                self.assertEqual(
                    [
                        dict(r)
                        for r in db.execute(
                            "SELECT * FROM environmental_reward_components "
                            "WHERE entitlement_id=%s ORDER BY ordinal",
                            (entitlement,),
                        )
                    ],
                    before,
                )
                for forged in (
                    dict(participant, account_id=account + 100),
                    dict(participant, instance_id=event["instance_id"] + 100),
                    dict(participant, completed_at_ms=11),
                ):
                    with self.assertRaises(ValueError):
                        simple.project(db, event, profile, forged, 20)
                with self.assertRaises(ValueError):
                    simple.project(
                        db, event, dict(profile, sealed=False), participant, 20
                    )
                with self.assertRaises(ValueError):
                    simple.project(db, event, profile, participant, 9)
                with self.assertRaises(psycopg.Error), db.transaction():
                    db.execute(
                        "UPDATE environmental_profile_simple_result_policy SET parameter_authority=%s "
                        "WHERE profile_key=%s",
                        ("tampered", profile["profile_key"]),
                    )
                # Mismatched frozen component quantities cannot select a UI
                # reward merely because the profile points at index zero.
                with self.assertRaisesRegex(
                    ValueError, "differs from original"
                ), db.transaction():
                    db.execute(
                        "UPDATE environmental_reward_components SET quantity=quantity+1 "
                        "WHERE entitlement_id=%s AND ordinal=0",
                        (entitlement,),
                    )
                    simple.project(db, event, profile, participant, 20)
                self.assertEqual(
                    simple.project(db, event, profile, participant, 20), mapping
                )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (actor["id"],),
                ).fetchone()["xp"],
                initial_xp,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                2,
            )
            # Test the SQL guard before sealing a new policy. Its mode/source
            # must agree, rather than treating a ranked scenario as simple.
            with self.assertRaises(psycopg.Error), db.transaction():
                db.execute("SET CONSTRAINTS ALL DEFERRED")
                db.execute(
                    "INSERT INTO environmental_runtime_profiles "
                    "(profile_key,version,native_scenario_id,family,mode,map_id,duration_ms,anchor_ms,"
                    "level_min,level_max,authority,source_sha256,catalog_revision) "
                    "VALUES('forged-simple',1,-2247,'resource_collect','solo',527,60000,0,1,245,'test',%s,%s)",
                    ("0" * 64, "1" * 64),
                )
                reward = db.execute(
                    "SELECT reward_id FROM environmental_native_reward_display "
                    "WHERE source_key=%s AND scenario_id=-2247 AND primary_result_index=0",
                    (SOURCE,),
                ).fetchone()
                db.execute(
                    "INSERT INTO environmental_profile_simple_result_policy VALUES "
                    "('forged-simple',1,%s,-2247,%s,%s,0,'personal_progress','source','mapping','parameter')",
                    (SOURCE, reward["reward_id"], simple.CONTRACT),
                )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")
