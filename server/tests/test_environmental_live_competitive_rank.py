"""Live competitive UI uses the frozen final cohort without settling it early."""
from dataclasses import replace
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import heroes
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalLiveCompetitiveRankTests(unittest.TestCase):
    def test_live_rank_uses_final_qualified_cohort_and_owned_context_without_early_settlement(
        self,
    ):
        from test_environmental_durable_lifecycle import (
            EnvironmentalDurableLifecycleTests,
        )

        fixture = EnvironmentalDurableLifecycleTests(
            methodName="test_shared_progress_rewards_only_real_contributors"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        account, generation, main = (
            fixture.account,
            fixture.generation,
            fixture.character,
        )
        hero = store.create_character(account, "Live Rank Hero")
        heroes.add(store, account, generation, main["id"], hero["id"])
        other_account, other_generation, other = fixture.owner()
        now = fixture.now_ms
        with store.connection() as db:
            for mode, challenge in (
                ("competitive", -9101),
                ("race", -9102),
                ("collaborative", -9103),
            ):
                key = "live-rank-" + mode
                db.execute(
                    "INSERT INTO environmental_runtime_profiles "
                    "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,"
                    "level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision) "
                    "VALUES(%s,1,%s,'resource_collect',%s,527,17,60000,%s,1,245,5,'test-only live-rank component',%s,%s)",
                    (key, challenge, mode, now - 1000, "0" * 64, "1" * 64),
                )
                db.execute(
                    "INSERT INTO environmental_profile_objectives VALUES "
                    "(%s,1,'collect','resource_collect',1337,3,1,'quantity',5)",
                    (key,),
                )
                db.execute(
                    "INSERT INTO environmental_profile_rewards VALUES(%s,1,0,'xp',NULL,100,'test-only')",
                    (key,),
                )
                db.execute(
                    "INSERT INTO environmental_profile_publication VALUES(%s,1,%s,0,17,0,'remaining_ms','test-only')",
                    (key, challenge),
                )
                db.execute(
                    "INSERT INTO environmental_profile_variables VALUES(%s,1,0,'count','collect',NULL)",
                    (key,),
                )
                for state, ordinal in (
                    ("proposed", 0),
                    ("active", 1),
                    ("completed", 2),
                    ("expired", 2),
                    ("cancelled", 2),
                ):
                    db.execute(
                        "INSERT INTO environmental_profile_publication_states VALUES(%s,1,%s,%s)",
                        (key, state, ordinal),
                    )
                if mode != "collaborative":
                    db.execute(
                        "INSERT INTO environmental_profile_evaluation VALUES(%s,1,%s,%s,%s,%s)",
                        (
                            key,
                            "score_at_deadline"
                            if mode == "competitive"
                            else "first_completion",
                            1 if mode == "competitive" else 2,
                            "share_boundary"
                            if mode == "competitive"
                            else "commit_order",
                            "test-only frozen final eligibility",
                        ),
                    )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET sealed=true,enabled=%s WHERE profile_key=%s",
                    (mode == "competitive", key),
                )
        initial = fixture.admit()
        event_id = initial["instances"][0]["instance_id"]
        fixture.admit(other_account, other_generation, other)
        with store.connection() as db:
            self.assertEqual(
                {
                    r["character_id"]
                    for r in db.execute(
                        "SELECT character_id FROM environmental_participants WHERE instance_id=%s",
                        (event_id,),
                    )
                },
                {main["id"], hero["id"], other["id"]},
            )
        fixture.roster(event_id, range(9101, 9107))

        def contribute(entity, quantity, owner, character):
            fact = replace(
                fixture.fact(entity, account=owner, character=character),
                quantity=quantity,
            )
            self.assertTrue(fixture.consume(fact))

        def view(owner, character):
            with store.connection() as db:
                return storage.refresh(
                    db,
                    account_id=owner,
                    character_id=character["id"],
                    location=fixture.location,
                    now_ms=now + 10,
                )["instances"][0]

        def assert_no_early_settlement():
            with store.connection() as db:
                for table in (
                    "environmental_event_rankings",
                    "environmental_reward_entitlements",
                    "environmental_claim_receipts",
                ):
                    self.assertEqual(
                        db.execute("SELECT count(*) AS n FROM " + table).fetchone()[
                            "n"
                        ],
                        0,
                        table,
                    )
                self.assertEqual(
                    db.execute(
                        "SELECT state FROM environmental_event_instances WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()["state"],
                    "active",
                )

        batches = []
        world = SimpleNamespace(
            scope_presence=fixture.presence_world.scope_presence,
            send_batch_to=Mock(
                side_effect=lambda *args: batches.append(args[-1]) or True
            ),
        )
        cursor = SelectedEnvironmentalEvents()

        def publish(connection=cursor, selected=main, lease=None):
            return connection.refresh(
                store,
                world,
                account,
                lease or generation,
                selected["id"],
                location=fixture.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=now + 10,
            )

        self.assertTrue(publish())
        self.assertLess(
            [op for op, _ in batches[-1]].index(12549),
            [op for op, _ in batches[-1]].index(13828),
        )
        self.assertEqual(
            [body for op, body in batches[-1] if op == 13828], [struct.pack(">h", -1)]
        )
        contribute(9101, 4, account, main)
        contribute(9102, 4, account, hero)
        contribute(9103, 6, other_account, other)
        self.assertEqual(
            (view(account, main)["live_rank"], view(account, main)["challenge_value"]),
            (-1, 1),
        )
        self.assertEqual(
            (view(account, hero)["live_rank"], view(other_account, other)["live_rank"]),
            (-1, 1),
        )
        self.assertTrue(publish())
        self.assertEqual(
            [body for op, body in batches[-1] if op == 12361], [struct.pack(">i", 1)]
        )
        self.assertNotIn(13263, [op for op, _ in batches[-1]])
        contribute(9104, 2, account, main)
        contribute(9105, 2, account, hero)
        # The declared share-boundary policy gives equal scores the same rank.
        self.assertEqual(
            [
                (
                    view(owner, character)["live_rank"],
                    view(owner, character)["challenge_value"],
                )
                for owner, character in (
                    (account, main),
                    (account, hero),
                    (other_account, other),
                )
            ],
            [(1, 3)] * 3,
        )
        self.assertTrue(publish())
        self.assertEqual(
            [body for op, body in batches[-1] if op == 13828], [struct.pack(">h", 1)]
        )
        assert_no_early_settlement()
        # An unrelated competitor's action must refresh this selected rank,
        # even though this owner's progress/outbox has not changed.
        contribute(9106, 2, other_account, other)
        self.assertEqual(
            (view(account, main)["live_rank"], view(account, main)["challenge_value"]),
            (2, 3),
        )
        world.send_batch_to.side_effect = (
            lambda *args: batches.append(args[-1]) or False
        )
        self.assertFalse(publish())
        failed = batches[-1]
        self.assertEqual(
            [body for op, body in failed if op == 13828], [struct.pack(">h", 2)]
        )
        self.assertNotIn(12549, [op for op, _ in failed])
        world.send_batch_to.side_effect = lambda *args: batches.append(args[-1]) or True
        self.assertTrue(publish())
        self.assertEqual(batches[-1], failed)
        self.assertNotIn(13263, [op for op, _ in failed])
        assert_no_early_settlement()
        # Select the actual owned hero. The global rank packet has no event ID,
        # so it must follow that new owned context rather than target the main.
        heroes.switch_main(store, account, generation, main["id"], hero["id"])
        fixture.presence_world.leave(main["id"], generation)
        hero = store.character(account, hero["id"])
        fixture.presence_world.join(generation, object(), hero)
        selected_hero = SelectedEnvironmentalEvents()
        self.assertTrue(publish(selected_hero, hero))
        operations = [op for op, _ in batches[-1]]
        self.assertLess(operations.index(12549), operations.index(13828))
        self.assertEqual(
            [body for op, body in batches[-1] if op == 13828], [struct.pack(">h", 2)]
        )
        fixture.presence_world.leave(hero["id"], generation)
        new_generation = store.begin_session(account, previous_generation=generation)
        store.select_character(account, new_generation, hero["id"])
        fixture.presence_world.join(
            new_generation, object(), store.character(account, hero["id"])
        )
        self.assertTrue(publish(SelectedEnvironmentalEvents(), hero, new_generation))
        operations = [op for op, _ in batches[-1]]
        self.assertLess(operations.index(12549), operations.index(13828))
        self.assertEqual(
            [body for op, body in batches[-1] if op == 13828], [struct.pack(">h", 2)]
        )
        assert_no_early_settlement()
        # Other modes have actual qualified views but no competitive rank.
        for mode in ("race", "collaborative"):
            with store.connection() as db:
                key = "live-rank-" + mode
                event = db.execute(
                    "INSERT INTO environmental_event_instances "
                    "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state) "
                    "VALUES(%s,1,527,0,17,0,%s,%s,'active') RETURNING *",
                    (key, now - 1000, now + 59000),
                ).fetchone()
                profile = storage._event_profile(db, event)
                participant = db.execute(
                    "INSERT INTO environmental_participants(instance_id,character_id,account_id,joined_at_ms) "
                    "VALUES(%s,%s,%s,%s) RETURNING *",
                    (event["instance_id"], hero["id"], account, now),
                ).fetchone()
                actual = storage._view(db, event, profile, participant, now + 10)
                self.assertIsNone(actual["live_rank"])
            snapshot = dict(instances=[actual], deliveries=[])
            with patch.object(service, "refresh", return_value=snapshot):
                self.assertTrue(
                    publish(SelectedEnvironmentalEvents(), hero, new_generation)
                )
            self.assertNotIn(13828, [op for op, _ in batches[-1]])
        # Read one installed original source profile, without activating or
        # playing it, to distinguish native objective identities from values.
        native_key = "resource-native-2247-1401-94601"
        with store.connection() as db:
            for fragment in (
                (
                    Path(__file__).parents[1]
                    / "seeds/environmental_resource_competitions.sql"
                )
                .read_text()
                .split(";\n")
            ):
                statement = fragment.strip()
                if "E'" + native_key + "'" in statement and (
                    statement.startswith("INSERT INTO environmental_profile_")
                    or statement.startswith(
                        "INSERT INTO environmental_runtime_profiles"
                    )
                ):
                    db.execute(statement + ";", prepare=False)
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true WHERE profile_key=%s",
                (native_key,),
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            native_event = db.execute(
                "INSERT INTO environmental_event_instances "
                "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state) "
                "VALUES(%s,1,1401,0,94601,0,%s,%s,'active') RETURNING *",
                (native_key, now, now + 600000),
            ).fetchone()
            profile = storage._event_profile(db, native_event)
            participant = db.execute(
                "INSERT INTO environmental_participants(instance_id,character_id,account_id,joined_at_ms) "
                "VALUES(%s,%s,%s,%s) RETURNING *",
                (native_event["instance_id"], hero["id"], account, now),
            ).fetchone()
            native_view = storage._view(
                db, native_event, profile, participant, now + 10
            )
            objectives = [
                r["objective_id"]
                for r in db.execute(
                    "SELECT objective_id FROM environmental_native_objectives "
                    "WHERE source_key='installed-environmental-source-v1' AND scenario_id=-2247 AND client_visible ORDER BY objective_id"
                )
            ]
            self.assertTrue(objectives)
            self.assertEqual(native_view["active_objectives"], objectives)
        # Packet-model component only: the original profile is disabled and no
        # source mission admission, transport or reward is claimed here.
        model_store = SimpleNamespace(current_character_session=Mock(return_value=True))
        model_world = SimpleNamespace(
            scope_presence=Mock(return_value=1), send_batch_to=Mock(return_value=True)
        )
        with patch.object(
            service,
            "refresh",
            return_value=dict(instances=[native_view], deliveries=[]),
        ):
            self.assertTrue(
                SelectedEnvironmentalEvents().refresh(
                    model_store,
                    model_world,
                    account,
                    new_generation,
                    hero["id"],
                    location=dict(map_id=1401, instance_id=0, region_id=94601),
                    ready=True,
                    checkpoint=lambda: None,
                    now_ms=now + 10,
                )
            )
        native_packets = model_world.send_batch_to.call_args.args[2]
        operations = [op for op, _ in native_packets]
        self.assertLess(operations.index(12549), operations.index(13955))
        self.assertLess(operations.index(13955), operations.index(13828))
        initial_body = next(body for op, body in native_packets if op == 12549)
        self.assertEqual(
            list(struct.unpack(">" + "i" * len(objectives), initial_body[30:])),
            objectives,
        )
        body = next(body for op, body in native_packets if op == 13955)
        self.assertEqual(struct.unpack_from(">i", body)[0], -2247)
        count = struct.unpack_from(">b", body, 4)[0]
        offset = 5 + 4 * count
        self.assertEqual(
            list(struct.unpack_from(">" + "i" * count, body, 5)), objectives
        )
        self.assertEqual(body[offset], 0)
        variable_count = struct.unpack_from(">i", body, offset + 1)[0]
        offset += 5
        variables = [
            struct.unpack_from(">bq", body, offset + 9 * index)
            for index in range(variable_count)
        ]
        self.assertEqual(
            variables,
            [(r["variable_index"], r["value"]) for r in native_view["variables"]],
        )
        self.assertEqual(offset + 9 * variable_count, len(body))
        self.assertNotEqual([value for _, value in variables], objectives)
        # Final evaluation still owns durable ranks/rewards, once at deadline.
        with store.connection() as db:
            storage.refresh(
                db,
                account_id=other_account,
                character_id=other["id"],
                location=fixture.location,
                now_ms=now + 60000,
            )
            ranks = db.execute(
                "SELECT character_id,display_rank,score FROM environmental_event_rankings WHERE instance_id=%s ORDER BY position",
                (event_id,),
            ).fetchall()
            self.assertEqual(
                [(r["character_id"], r["display_rank"], r["score"]) for r in ranks],
                [(other["id"], 1, 8), (main["id"], 2, 6), (hero["id"], 2, 6)],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                1,
            )
