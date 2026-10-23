"""A declared compatible native variant executes its own original world action."""
import struct
import unittest

from wakfu_server import health_store
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.planting_cells import cells
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.objectives import environmental_monster_actions as actions
from wakfu_server.objectives import environmental_monster_destroy as destroy
from wakfu_server.objectives import environmental_destroy_publication as publication
from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from test_environmental_group_bulk_pipeline import seed_sql


class EnvironmentalNamedDestroyLifecycleTests(unittest.TestCase):
    def test_xelot_5710_original_action_1356_completes_owned_source_and_rewards_once(
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
        store, account, identity = (
            fixture.store,
            fixture.account,
            fixture.character["id"],
        )
        points = [
            (x, y, row["z"])
            for (x, y), rows in cells(1401).items()
            for row in rows
            if row["region_id"] == 94601
        ]
        self.assertTrue(points)
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET level=231,map_id=1401,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (*points[-1], identity),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[231], identity),
            )
        character = health_store.initialize(
            store, account, fixture.generation, identity
        )
        fixture.world.join(fixture.generation, object(), character)
        registry = PersistentGroups(store)
        key = "destroy-native-2258-1401-94601"
        location = dict(map_id=1401, instance_id=0, region_id=94601)
        with store.connection() as db:
            for fragment in seed_sql("environmental_named_destroy_profiles.sql").split(
                ";\n"
            ):
                statement = fragment.strip()
                if "E'" + key + "'" in statement and (
                    statement.startswith("INSERT INTO environmental_profile_")
                    or statement.startswith(
                        "INSERT INTO environmental_runtime_profiles"
                    )
                    or statement.startswith(
                        "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                    )
                ):
                    db.execute(statement + ";", prepare=False)
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (key,),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('fixture-native-xelot',1,1401,94601,'wakemu_round_robin','occupied_sequential_windows',0,"
                "'bounded exact named-type native action component',%s)",
                ("0" * 64,),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates VALUES('fixture-native-xelot',1,0,%s,1)",
                (key,),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true WHERE policy_key='fixture-native-xelot'"
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET enabled=true WHERE singleton"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            source = db.execute(
                "SELECT * FROM environmental_destroy_sources WHERE scenario_id=-2258 "
                "AND policy_version='wakemu.original-body-namedtype-compatible-variant-v1'"
            ).fetchone()
            self.assertEqual(
                (
                    source["template_reference"],
                    source["monster_reference"],
                    source["action_id"],
                ),
                (2545, 5710, 1356),
            )
            proof = source["public_proof"]
            self.assertEqual(
                proof["kind"], "ORIGINAL_BODY_NAMEDTYPE_COMPATIBLE_VARIANT"
            )
            self.assertEqual(proof["selected_species"]["ref"], 5710)
            self.assertIs(proof["original_template_membership_recovered"], False)
        rule = actions.native_destroy_action(5710, 1356)
        self.assertEqual(
            (
                rule["monster_reference"],
                rule["action_id"],
                rule["monster_action_type"],
                rule["duration_ms"],
            ),
            (5710, 1356, 3, 0),
        )
        self.assertEqual(rule["native"], source["action_descriptor"])
        # The body names a type. It does not invent a world action on the
        # ordinary prototype3535 merely because the selected variant shares it.
        with self.assertRaises(ValueError):
            actions.native_destroy_action(3535, 1356)

        def refresh():
            return service.refresh(
                store,
                account,
                fixture.generation,
                identity,
                location=location,
                now_ms=int(fixture.clock[0] * 1000),
                groups=registry,
            )

        event_id = refresh()["instances"][0]["instance_id"]
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            profile = storage._event_profile(db, event)
            self.assertEqual((profile["level_min"], profile["level_max"]), (231, 245))
            owned = db.execute(
                "SELECT * FROM environmental_owned_groups WHERE instance_id=%s ORDER BY group_ordinal",
                (event_id,),
            ).fetchall()
            self.assertEqual(len(owned), 100)
            members = [
                member
                for row in owned
                for member in db.execute(
                    "SELECT members FROM combat_groups WHERE map_id=1401 "
                    "AND instance_id=0 AND group_id=%s",
                    (row["group_id"],),
                ).fetchone()["members"]
            ]
            self.assertEqual({member["ref"] for member in members}, {5710})
            self.assertTrue(
                all(
                    member.get("environmental_world_action_only") is True
                    and type(member["hp"]) is int
                    and member["hp"] > 0
                    for member in members
                )
            )
        edges = {(tuple(a), tuple(b)) for a, b in map_geometry(1401)["edges"]}
        adjacent = {}
        for start, target in sorted(edges):
            adjacent.setdefault(target, start)

        def balances():
            with store.connection() as db:
                xp = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (identity,),
                ).fetchone()["xp"]
                items = db.execute(
                    """SELECT COALESCE(SUM(quantity),0) AS n FROM (
                    SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=31808
                    UNION ALL SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=31808
                    UNION ALL SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=31808) q""",
                    (identity, identity, account),
                ).fetchone()["n"]
                return xp, items

        before = balances()
        selected = members[:5]
        last_receipt = None
        for member in selected:
            target = tuple(member[field] for field in ("x", "y", "z"))
            self.assertIn(target, adjacent)
            # Fixture positioning uses actual native adjacent cells; action
            # authentication still reads the real owned/session/current actor.
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*adjacent[target], identity),
                )
            actual = store.character(account, identity)
            fixture.world.join(fixture.generation, object(), actual)
            fixture.clock[0] += 0.01
            with registry.lock, store.connection() as db:
                last_receipt = destroy.commit(
                    store,
                    db,
                    account,
                    fixture.generation,
                    actual,
                    struct.pack(">qq", member["id"], 1356),
                    groups=registry,
                    loaded=True,
                    reachable=lambda owner, npc: (
                        tuple(owner[k] for k in ("x", "y", "z")),
                        tuple(npc[k] for k in ("x", "y", "z")),
                    )
                    in edges,
                    now_ms=int(fixture.clock[0] * 1000),
                )
                self.assertEqual(
                    (last_receipt["monster_reference"], last_receipt["action_id"]),
                    (5710, 1356),
                )
                self.assertTrue(gameplay.committed_monster_destroy(db, last_receipt))
        self.assertEqual(balances(), before)  # Entitlement precedes actual payout.
        with registry.lock, store.connection() as db:
            participant = dict(
                db.execute(
                    "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                    (event_id, identity),
                ).fetchone()
            )
            self.assertIsNotNone(participant["completed_at_ms"])
            entitlement_id = db.execute(
                "SELECT entitlement_id FROM environmental_reward_entitlements WHERE instance_id=%s AND character_id=%s",
                (event_id, identity),
            ).fetchone()["entitlement_id"]
            self.assertEqual(
                destroy.counters(db, event, participant, "monster"), (5, 5)
            )
            deliveries = [
                d
                for d in publication.pending(
                    db, map_id=1401, instance_id=0, now_ms=int(fixture.clock[0] * 1000)
                )
                if d.instance_id == event_id
            ]
            self.assertEqual(len(deliveries), 5)
            self.assertEqual(
                {d.monster_id for d in deliveries}, {m["id"] for m in selected}
            )
            for delivery in deliveries:
                self.assertEqual(delivery.packets[0][0], 12421)
                self.assertEqual(
                    struct.unpack(">qqq", delivery.packets[0][1]),
                    (delivery.monster_id, identity, 1356),
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE event_key LIKE 'fight:%'"
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(
            publication.publish(
                store,
                fixture.world,
                registry,
                map_id=1401,
                instance_id=0,
                now_ms=int(fixture.clock[0] * 1000),
            ),
            5,
        )
        delivered = refresh()
        self.assertEqual(delivered["rewards"]["delivered"], [entitlement_id])
        self.assertEqual(balances(), (before[0] + 37787444, before[1] + 3))
        after = balances()
        self.assertEqual(refresh()["rewards"]["delivered"], [])
        self.assertEqual(balances(), after)
        # Completed-owner replay authenticates the old removal and grants
        # neither another objective fact nor another reward.
        with registry.lock, store.connection() as db:
            replay = destroy.commit(
                store,
                db,
                account,
                fixture.generation,
                store.character(account, identity, db),
                struct.pack(">qq", selected[-1]["id"], 1356),
                groups=registry,
                reachable=lambda *_: False,
                loaded=True,
                now_ms=int(fixture.clock[0] * 1000),
            )
            self.assertTrue(replay["replayed"])
            self.assertEqual(gameplay.committed_monster_destroy(db, replay), ())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_monster_destructions WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_destroy_progress_facts WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts WHERE entitlement_id=%s",
                    (entitlement_id,),
                ).fetchone()["n"],
                1,
            )
        self.assertEqual(balances(), after)
