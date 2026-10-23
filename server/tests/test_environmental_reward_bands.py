"""Original resource reward bands and explicitly declared Wakemu base grants."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
import struct
from types import SimpleNamespace

import psycopg

from postgres_case import PostgresCase
from wakfu_server.objectives import environmental_reward_bands as bands


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "installed-environmental-source-v1"


def original_competitions():
    source = json.loads(
        (
            ROOT
            / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
        ).read_text()
    )
    return [
        s
        for s in source["scenarios"]
        if s["subtype"] == 3
        and "ressourcerefid" in {k.lower() for k in s["configuration"]}
    ]


def native_rows(scenario):
    return [
        dict(
            reward_id=r["id"],
            primary_result_index=r["field_aHh"],
            primary_reward_list=r["flag"],
            native_text=r["text"],
        )
        for r in scenario["rewards"]
    ]


class EnvironmentalRewardBandTests(unittest.TestCase):
    def test_all_78_original_resource_competitions_keep_primary_indices_and_exact_rank_predicates(
        self,
    ):
        scenarios = original_competitions()
        self.assertEqual(len(scenarios), 78)
        self.assertEqual(len({s["id"] for s in scenarios}), 78)
        for scenario in scenarios:
            with self.subTest(scenario=scenario["id"]):
                original = native_rows(scenario)
                before = deepcopy(original)
                self.assertEqual(len(original), 3)
                self.assertEqual(
                    [r["primary_result_index"] for r in original], [0, 1, 2]
                )
                self.assertEqual(
                    [
                        bands.parse_native_reward_band(r["native_text"])
                        for r in original
                    ],
                    [(1, 1), (2, 2), None],
                )
                result = bands.compile_native_reward_bands(list(reversed(original)))
                self.assertEqual(
                    result,
                    [
                        dict(
                            reward_id=original[0]["reward_id"],
                            primary_reward_index=0,
                            rank_min=1,
                            rank_max=1,
                        ),
                        dict(
                            reward_id=original[1]["reward_id"],
                            primary_reward_index=1,
                            rank_min=2,
                            rank_max=2,
                        ),
                        dict(
                            reward_id=original[2]["reward_id"],
                            primary_reward_index=2,
                            rank_min=None,
                            rank_max=None,
                        ),
                    ],
                )
                self.assertEqual(original, before)

    def test_unknown_predicates_ambiguous_indices_and_overlapping_or_missing_fallback_fail_closed(
        self,
    ):
        predicate = 'ListContains(GetUser(), GetPlayerInRankRange(1, 1, "nbResourcePlayer", False))'
        self.assertEqual(bands.parse_native_reward_band(predicate), (1, 1))
        upper = predicate.replace("(1, 1,", "(1, 32767,")
        self.assertEqual(bands.parse_native_reward_band(upper), (1, 32767))
        invalid_text = [
            None,
            False,
            1,
            " ",
            predicate + " ",
            predicate.replace("False", "True"),
            predicate.replace("nbResourcePlayer", "nbResourceGlobal"),
            predicate.replace("nbResourcePlayer", "nbMobPlayer"),
            predicate.replace("(1, 1,", "(0, 1,"),
            predicate.replace("(1, 1,", "(2, 1,"),
            predicate.replace("(1, 1,", "(1, 32768,"),
            predicate.replace("(1, 1,", "(01, 1,"),
            predicate.replace("ListContains", "NotListContains"),
        ]
        for text in invalid_text:
            with self.subTest(predicate=text), self.assertRaises(ValueError):
                bands.parse_native_reward_band(text)
        original = native_rows(original_competitions()[0])
        cases = [[], original[:2], original[1:]]
        for index, change in (
            (0, dict(primary_result_index=False)),
            (1, dict(primary_result_index=0)),
            (0, dict(primary_reward_list=1)),
            (0, dict(primary_reward_list=False)),
            (1, dict(reward_id=original[0]["reward_id"])),
            (0, dict(reward_id=True)),
            (1, dict(native_text=predicate)),
            (0, dict(native_text="")),
        ):
            altered = deepcopy(original)
            altered[index].update(change)
            cases.append(altered)
        for index, rows in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                bands.compile_native_reward_bands(rows)


class EnvironmentalRewardBandPostgresTests(PostgresCase):
    def _profile(self, db, key, *, policy=True, seal=True):
        db.execute(
            "INSERT INTO environmental_runtime_profiles "
            "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,"
            "level_min,level_max,authority,source_sha256,catalog_revision) "
            "VALUES(%s,1,-2247,'resource_collect','competitive',1134,79001,600000,0,231,245,%s,%s,%s)",
            (key, "test-declared rank-band policy", "0" * 64, "1" * 64),
        )
        db.execute(
            "INSERT INTO environmental_profile_objectives VALUES "
            "(%s,1,'collect','resource_collect',849,NULL,2,'interaction',10)",
            (key,),
        )
        db.execute(
            "INSERT INTO environmental_profile_rewards VALUES "
            "(%s,1,0,'xp',NULL,1,'legacy-only reward fixture')",
            (key,),
        )
        db.execute(
            "INSERT INTO environmental_profile_publication VALUES "
            "(%s,1,-2247,0,0,600000,'constant','test-declared native display mapping')",
            (key,),
        )
        if policy:
            db.execute(
                "INSERT INTO environmental_profile_ranked_reward_policy VALUES "
                "(%s,1,%s,-2247,%s,'all_eligible',%s,%s,'winner_score',NULL,%s)",
                (
                    key,
                    SOURCE,
                    bands.CONTRACT,
                    "original resource predicates",
                    "Wakemu explicit original display base values; no boosters; not original server payouts",
                    "test-declared winner-score parameter",
                ),
            )
            for row in bands.compile_native_reward_bands(self.native):
                db.execute(
                    "INSERT INTO environmental_profile_ranked_reward_bands VALUES "
                    "(%s,1,%s,-2247,%s,%s,%s,%s)",
                    (
                        key,
                        SOURCE,
                        row["primary_reward_index"],
                        row["reward_id"],
                        row["rank_min"],
                        row["rank_max"],
                    ),
                )
        if seal:
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true WHERE profile_key=%s",
                (key,),
            )

    def test_original_top_two_fallback_components_and_shared_winner_display_keep_owned_recipient_identity(
        self,
    ):
        account = self.store.register("environmental-band-owner", "test-password")["id"]
        characters = [
            self.store.create_character(account, name)
            for name in ("Band Winner", "Band Second", "Band Fallback", "Band Excluded")
        ]
        with self.store.connection() as db:
            self.native = [
                dict(r)
                for r in db.execute(
                    "SELECT r.reward_id,d.primary_result_index,"
                    "d.primary_reward_list,r.native_text FROM environmental_native_rewards_raw r "
                    "JOIN environmental_native_reward_display d USING(source_key,scenario_id,reward_id) "
                    "WHERE r.source_key=%s AND r.scenario_id=-2247 AND d.primary_reward_list "
                    "ORDER BY d.primary_result_index",
                    (SOURCE,),
                ).fetchall()
            ]
            self.assertEqual(len(self.native), 3)
            self._profile(db, "ranked-native")
            self._profile(db, "legacy-native", policy=False)
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            event = dict(
                db.execute(
                    "INSERT INTO environmental_event_instances "
                    "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state,terminal_at_ms) "
                    "VALUES('ranked-native',1,1134,0,79001,0,1000,601000,'completed',601000) RETURNING *"
                ).fetchone()
            )
            legacy = dict(
                db.execute(
                    "INSERT INTO environmental_event_instances "
                    "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state,terminal_at_ms) "
                    "VALUES('legacy-native',1,1134,0,79001,0,1000,601000,'completed',601000) RETURNING *"
                ).fetchone()
            )
            profile = dict(
                db.execute(
                    "SELECT * FROM environmental_runtime_profiles WHERE profile_key='ranked-native'"
                ).fetchone()
            )
            # Durable evaluator results are explicit premises of this reader
            # component. It must never invent rewarded eligibility itself.
            participants = []
            for position, character in enumerate(characters, 1):
                participant = dict(
                    db.execute(
                        "INSERT INTO environmental_participants "
                        "(instance_id,character_id,account_id,joined_at_ms) VALUES(%s,%s,%s,1000) RETURNING *",
                        (event["instance_id"], character["id"], account),
                    ).fetchone()
                )
                participants.append(participant)
                db.execute(
                    "INSERT INTO environmental_event_rankings VALUES(%s,%s,%s,%s,%s,%s,601000)",
                    (
                        event["instance_id"],
                        character["id"],
                        position,
                        position,
                        1000 - position * 111,
                        position <= 3,
                    ),
                )
            expected_display = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_native_reward_display "
                    "WHERE source_key=%s AND scenario_id=-2247 AND primary_reward_list ORDER BY primary_result_index",
                    (SOURCE,),
                ).fetchall()
            ]
            before = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_event_rankings ORDER BY position"
                )
            ]
            mappings = []
            for index, participant in enumerate(participants[:3]):
                components = bands.reward_components(db, event, profile, participant)
                display = expected_display[index]
                expected = []
                for kind, reference, quantity in (
                    ("xp", None, display["base_xp"]),
                    ("item", display["item_reference"], display["item_quantity"]),
                    ("kamas", None, display["kamas"]),
                ):
                    if quantity:
                        expected.append((kind, reference, quantity))
                self.assertEqual(
                    [(r["kind"], r["reference"], r["quantity"]) for r in components],
                    expected,
                )
                self.assertEqual(
                    [r["ordinal"] for r in components], list(range(len(expected)))
                )
                self.assertTrue(
                    all(
                        "not original server payouts" in r["source_authority"]
                        for r in components
                    )
                )
                self.assertEqual(
                    bands.reward_components(db, event, profile, participant), components
                )
                mapping = bands.native_result_mapping(db, event, profile, participant)
                mappings.append(mapping)
                self.assertEqual(
                    (
                        mapping["primary_reward_index"],
                        mapping["primary_reward_count"],
                        mapping["display_rank"],
                    ),
                    (index, 3, index + 1),
                )
                self.assertEqual(
                    (mapping["character_id"], mapping["account_id"]),
                    (participant["character_id"], account),
                )
                self.assertEqual(
                    (mapping["name"], mapping["result_parameter"]), ("Band Winner", 889)
                )
            self.assertEqual({m["name"] for m in mappings}, {characters[0]["name"]})
            self.assertEqual(
                bands.reward_components(db, event, profile, participants[3]), []
            )
            self.assertIsNone(
                bands.native_result_mapping(db, event, profile, participants[3])
            )
            legacy_profile = dict(
                db.execute(
                    "SELECT * FROM environmental_runtime_profiles WHERE profile_key='legacy-native'"
                ).fetchone()
            )
            self.assertIsNone(
                bands.reward_components(db, legacy, legacy_profile, participants[0])
            )
            self.assertIsNone(
                bands.native_result_mapping(db, legacy, legacy_profile, participants[0])
            )
            for forged in (
                dict(participants[1], account_id=account + 100),
                dict(participants[1], instance_id=legacy["instance_id"]),
            ):
                with self.assertRaises(ValueError):
                    bands.reward_components(db, event, profile, forged)
            with self.assertRaises(ValueError):
                bands.reward_components(
                    db, event, dict(profile, sealed=False), participants[0]
                )
            self.assertEqual(
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM environmental_event_rankings ORDER BY position"
                    )
                ],
                before,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            with self.assertRaises(psycopg.Error), db.transaction():
                db.execute(
                    "UPDATE environmental_profile_ranked_reward_bands SET rank_max=2 WHERE profile_key='ranked-native' AND primary_reward_index=0"
                )
            with self.assertRaises(psycopg.Error), db.transaction():
                db.execute("SET CONSTRAINTS ALL DEFERRED")
                self._profile(db, "forged-native", seal=False)
                db.execute(
                    "UPDATE environmental_profile_ranked_reward_bands SET rank_max=2 WHERE profile_key='forged-native' AND primary_reward_index=0"
                )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET sealed=true WHERE profile_key='forged-native'"
                )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")


class EnvironmentalRewardBandIntegrationTests(unittest.TestCase):
    def test_actual_competition_entitles_three_bands_and_retries_native_result_without_double_grant(
        self,
    ):
        from test_environmental_durable_lifecycle import (
            EnvironmentalDurableLifecycleTests,
        )
        from wakfu_server.objectives import environmental_service as service
        from wakfu_server.objectives.environmental_world import (
            SelectedEnvironmentalEvents,
        )

        fixture = EnvironmentalDurableLifecycleTests(
            methodName="test_shared_progress_rewards_only_real_contributors"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        second = fixture.owner()
        third = fixture.owner()
        owners = [
            (fixture.account, fixture.generation, fixture.character),
            second,
            third,
        ]
        with store.connection() as db:
            self.native = [
                dict(r)
                for r in db.execute(
                    "SELECT r.reward_id,d.primary_result_index,"
                    "d.primary_reward_list,r.native_text FROM environmental_native_rewards_raw r "
                    "JOIN environmental_native_reward_display d USING(source_key,scenario_id,reward_id) "
                    "WHERE r.source_key=%s AND r.scenario_id=-2247 AND d.primary_reward_list "
                    "ORDER BY d.primary_result_index",
                    (SOURCE,),
                ).fetchall()
            ]
            EnvironmentalRewardBandPostgresTests._profile(
                self, db, "ranked-live", seal=False
            )
            # This component uses the existing authenticated gameplay fixture's
            # declared resource/action/scope. It qualifies settlement, not an
            # original scenario population or victory. Personal threshold10 is
            # the original reward threshold; no rank/rewarded rows are inserted.
            db.execute(
                "UPDATE environmental_runtime_profiles SET map_id=527,region_id=17,level_min=1,"
                "duration_ms=60000,anchor_ms=%s WHERE profile_key='ranked-live'",
                (fixture.now_ms - 1000,),
            )
            db.execute(
                "UPDATE environmental_profile_objectives SET target_reference=1337,action_id=3,"
                "resource_step=1,unit='quantity' WHERE profile_key='ranked-live'"
            )
            db.execute(
                "INSERT INTO environmental_profile_evaluation VALUES "
                "('ranked-live',1,'score_at_deadline',1,'character_id','test-declared evaluator')"
            )
            for state, ordinal in (
                ("proposed", 0),
                ("active", 1),
                ("completed", 2),
                ("expired", 3),
                ("cancelled", 3),
            ):
                db.execute(
                    "INSERT INTO environmental_profile_publication_states VALUES('ranked-live',1,%s,%s)",
                    (state, ordinal),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='ranked-live'"
            )
            before_xp = {
                r["character_id"]: r["xp"]
                for r in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    ([owner[2]["id"] for owner in owners],),
                )
            }
            expected = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_native_reward_display "
                    "WHERE source_key=%s AND scenario_id=-2247 AND primary_reward_list ORDER BY primary_result_index",
                    (SOURCE,),
                ).fetchall()
            ]
        admitted = fixture.admit()
        event_id = admitted["instances"][0]["instance_id"]
        for account, generation, character in owners[1:]:
            self.assertEqual(
                fixture.admit(account, generation, character)["instances"][0][
                    "instance_id"
                ],
                event_id,
            )
        fixture.roster(event_id, [8801, 8802, 8803])
        for index, (account, _, character) in enumerate(owners):
            fact = replace(
                fixture.fact(8801 + index, account=account, character=character),
                quantity=30 - index * 10,
            )
            self.assertTrue(fixture.consume(fact))
            self.assertEqual(fixture.consume(fact), ())
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
        now = fixture.now_ms + 60000
        batches = []
        world = SimpleNamespace(
            scope_presence=fixture.presence_world.scope_presence,
            send_batch_to=lambda *args: batches.append(args[-1]) or False,
        )
        connection = SelectedEnvironmentalEvents()
        self.assertFalse(
            connection.refresh(
                store,
                world,
                *owners[0][:2],
                owners[0][2]["id"],
                location=fixture.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=now
            )
        )

        def decoded_result(packets):
            bodies = [payload for opcode, payload in packets if opcode == 13263]
            self.assertEqual(len(bodies), 1)
            body = bodies[0]
            challenge, secondary, length = struct.unpack_from(">iib", body)
            name = body[9 : 9 + length].decode("utf-8")
            score, rank, index = struct.unpack_from(">ihi", body, 9 + length)
            self.assertEqual(len(body), 19 + length)
            return challenge, secondary, name, score, rank, index

        self.assertEqual(
            decoded_result(batches[-1]), (-2247, 0, owners[0][2]["name"], 30, 0, 0)
        )
        with store.connection() as db:
            ranked = db.execute(
                "SELECT character_id,score,display_rank,rewarded FROM "
                "environmental_event_rankings WHERE instance_id=%s ORDER BY position",
                (event_id,),
            ).fetchall()
            self.assertEqual(
                [
                    (r["character_id"], r["score"], r["display_rank"], r["rewarded"])
                    for r in ranked
                ],
                [
                    (owner[2]["id"], 30 - index * 10, index + 1, True)
                    for index, owner in enumerate(owners)
                ],
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["state"],
                "completed",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT acknowledged_at_ms FROM environmental_publication_outbox "
                    "WHERE instance_id=%s AND character_id=%s AND kind='completed'",
                    (event_id, owners[0][2]["id"]),
                ).fetchone()["acknowledged_at_ms"]
            )
            for index, owner in enumerate(owners):
                cached = db.execute(
                    "SELECT c.kind,c.reference,c.quantity FROM environmental_reward_components c "
                    "JOIN environmental_reward_entitlements e USING(entitlement_id) WHERE e.instance_id=%s "
                    "AND e.character_id=%s ORDER BY c.ordinal",
                    (event_id, owner[2]["id"]),
                ).fetchall()
                display = expected[index]
                expected_components = [("xp", None, display["base_xp"])]
                if display["item_quantity"]:
                    expected_components.append(
                        ("item", display["item_reference"], display["item_quantity"])
                    )
                if display["kamas"]:
                    expected_components.append(("kamas", None, display["kamas"]))
                self.assertEqual(
                    [(r["kind"], r["reference"], r["quantity"]) for r in cached],
                    expected_components,
                )
        # A fresh connection resumes the same unacknowledged completion/result,
        # while the previously committed XP/items remain granted exactly once.
        reopened = fixture.reopen()
        reopened.clock = store.clock
        world.send_batch_to = lambda *args: batches.append(args[-1]) or True
        resumed = SelectedEnvironmentalEvents()
        self.assertTrue(
            resumed.refresh(
                reopened,
                world,
                *owners[0][:2],
                owners[0][2]["id"],
                location=fixture.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=now + 1
            )
        )
        self.assertEqual(
            decoded_result(batches[-1]), (-2247, 0, owners[0][2]["name"], 30, 0, 0)
        )
        for index, (account, generation, character) in enumerate(owners[1:], 1):
            selected = SelectedEnvironmentalEvents()
            self.assertTrue(
                selected.refresh(
                    reopened,
                    world,
                    account,
                    generation,
                    character["id"],
                    location=fixture.location,
                    ready=True,
                    checkpoint=lambda: None,
                    now_ms=now + index + 1,
                )
            )
            self.assertEqual(
                decoded_result(batches[-1]),
                (-2247, 0, owners[0][2]["name"], 30, index, index),
            )
        for account, generation, character in owners:
            repeated = service.refresh(
                reopened,
                account,
                generation,
                character["id"],
                location=fixture.location,
                now_ms=now + 5,
            )
            self.assertEqual(repeated["rewards"]["delivered"], [])
            self.assertFalse(
                any(
                    opcode == 13263
                    for delivery in repeated["deliveries"]
                    for opcode, _ in delivery["packets"]
                )
            )
        with reopened.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox "
                    "WHERE kind='completed' AND acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
            for index, owner in enumerate(owners):
                actual = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (owner[2]["id"],),
                ).fetchone()["xp"]
                self.assertEqual(
                    actual - before_xp[owner[2]["id"]], expected[index]["base_xp"]
                )
