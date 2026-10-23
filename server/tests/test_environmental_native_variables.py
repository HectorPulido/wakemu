"""Complete original variable arrays projected from committed owned resources."""
import struct
import unittest
from dataclasses import replace

import psycopg

from wakfu_server import native_catalog, resource_collect
from wakfu_server.characters import heroes
from wakfu_server.objectives import environmental_native_variables as variables
from wakfu_server.objectives import environmental_resource_population as population
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.progression import XP_BY_LEVEL


class EnvironmentalNativeVariablesTests(unittest.TestCase):
    SOURCE = "installed-environmental-source-v1"

    def _profile(self, db, fixture, key, *, bindings=True, owned=False, seal=True):
        db.execute(
            "INSERT INTO environmental_runtime_profiles "
            "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,"
            "anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
            "VALUES(%s,1,-1320,'resource_collect','collaborative',327,56601,900000,%s,81,245,%s,%s,%s)",
            (
                key,
                fixture.now_ms - 1000,
                "test-declared durable counter projection",
                "0" * 64,
                native_catalog.release(),
            ),
        )
        db.execute(
            "INSERT INTO environmental_profile_objectives VALUES "
            "(%s,1,'collect','resource_collect',478,1190,2,'interaction',5)",
            (key,),
        )
        db.execute(
            "INSERT INTO environmental_profile_rewards VALUES "
            "(%s,1,0,'xp',NULL,100,'test-only')",
            (key,),
        )
        if owned:
            db.execute(
                "INSERT INTO environmental_profile_resource_population VALUES "
                "(%s,1,%s,'declared_native_cells','catalog_cvF','test-only placement')",
                (key, self.SOURCE),
            )
            for ordinal, point in enumerate(fixture.points[:200]):
                db.execute(
                    "INSERT INTO environmental_profile_resource_cells VALUES(%s,1,%s,%s,%s,%s)",
                    (key, ordinal, *point),
                )
        if bindings:
            self._bindings(db, key)
        if seal:
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                (key,),
            )

    def _bindings(self, db, key):
        db.execute(
            "INSERT INTO environmental_profile_native_variable_policy VALUES(%s,1,%s,-1320,%s,%s)",
            (
                key,
                self.SOURCE,
                variables.CONTRACT,
                "test-declared projection authority",
            ),
        )
        original = db.execute(
            "SELECT ordinal,native_name FROM environmental_native_variables "
            "WHERE source_key=%s AND scenario_id=-1320 ORDER BY ordinal",
            (self.SOURCE,),
        ).fetchall()
        config = {
            r["normalized_key"]: r
            for r in db.execute(
                "SELECT * FROM environmental_native_configuration WHERE source_key=%s AND scenario_id=-1320",
                (self.SOURCE,),
            ).fetchall()
        }
        for row in original:
            name = row["native_name"]
            objective = configuration = constant = entity = authority = None
            if name.lower() in config:
                kind = "configconstant"
                source = config[name.lower()]
                configuration, constant = source["native_key"], int(
                    source["native_value"]
                )
            elif name == "nbResourcePlayer":
                kind, objective = "personal_progress", "collect"
            elif name == "nbResourceGlobal":
                kind, objective = "global_progress", "collect"
            elif name == "nbResourceSpawned":
                kind, entity = "spawned", "resource"
            elif name == "nbResourceLeft":
                kind, entity = "remaining", "resource"
            elif name == "nbResourceMin":
                # Explicit Wakemu threshold policy; no original setter formula
                # is claimed from the client variable's name.
                kind = "declared_threshold"
                source = config["nbresourceforreward"]
                configuration, constant = source["native_key"], int(
                    source["native_value"]
                )
                authority = (
                    "Wakemu explicit threshold reconstruction from nbresourceforreward"
                )
            else:
                raise AssertionError(
                    f"Original variable requires explicit reviewed policy: {name}"
                )
            db.execute(
                "INSERT INTO environmental_profile_native_variable_bindings "
                "(profile_key,version,source_key,native_scenario_id,variable_index,native_name,"
                "binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) "
                "VALUES(%s,1,%s,-1320,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    key,
                    self.SOURCE,
                    row["ordinal"],
                    name,
                    kind,
                    objective,
                    configuration,
                    constant,
                    authority,
                    entity,
                ),
            )
        return original

    def test_original_full_array_two_owners_physical_union_and_owned_uid_lifecycle(
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
        hero = store.create_character(fixture.account, "Variable Hero")
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
        with store.connection() as db:
            self._profile(db, fixture, "native-vars", owned=True)
            self._profile(db, fixture, "legacy-vars", bindings=False)
        fixture.refresh()
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE profile_key='native-vars'"
                ).fetchone()
            )
            legacy = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE profile_key='legacy-vars'"
                ).fetchone()
            )
            profile = dict(storage._event_profile(db, event))
            participants = {
                r["character_id"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_participants WHERE instance_id=%s",
                    (event["instance_id"],),
                ).fetchall()
            }
            self.assertEqual(set(participants), {fixture.character["id"], hero["id"]})
            source = db.execute(
                "SELECT ordinal,native_name FROM environmental_native_variables "
                "WHERE source_key=%s AND scenario_id=-1320 ORDER BY ordinal",
                (self.SOURCE,),
            ).fetchall()
            self.assertEqual(
                [r["native_name"] for r in source],
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
            resources = [
                dict(r)
                for r in db.execute(
                    "SELECT p.* FROM planted_resources p "
                    "JOIN environmental_owned_resources o USING(resource_uid) WHERE o.instance_id=%s "
                    "ORDER BY resource_uid",
                    (event["instance_id"],),
                ).fetchall()
            ]
            uids = {r["resource_uid"] for r in resources}
            self.assertEqual(len(uids), 100)
            legacy_participant = db.execute(
                "SELECT * FROM environmental_participants "
                "WHERE instance_id=%s AND character_id=%s",
                (legacy["instance_id"], fixture.character["id"]),
            ).fetchone()
            self.assertIsNone(
                variables.project(
                    db,
                    legacy,
                    storage._event_profile(db, legacy),
                    legacy_participant,
                    fixture.now_ms,
                )
            )
            with self.assertRaises(ValueError):
                variables.project(
                    db, event, profile, legacy_participant, fixture.now_ms
                )

        def projections(db, *, personal, global_count, remaining):
            for identity, participant in participants.items():
                projected = variables.project(
                    db, event, profile, participant, int(fixture.clock[0] * 1000)
                )
                self.assertEqual(
                    [(r["variable_index"], r["name"]) for r in projected],
                    [(r["ordinal"], r["native_name"]) for r in source],
                )
                by_name = {r["name"]: r["value"] for r in projected}
                self.assertEqual(by_name["challengeLevelMax"], 245)
                self.assertEqual(by_name["challengeLevelMin"], 81)
                self.assertEqual(by_name["nbResourceForReward"], 5)
                self.assertEqual(by_name["nbResourceMin"], 5)
                self.assertEqual(by_name["nbResourcePlayer"], personal)
                self.assertEqual(by_name["nbResourceGlobal"], global_count)
                self.assertEqual(by_name["nbResourceSpawned"], 100)
                self.assertEqual(by_name["nbResourceLeft"], remaining)

        with store.connection() as db:
            projections(db, personal=0, global_count=0, remaining=100)
            # SQL authority rejects partial arrays and forged typed/configuration
            # bindings before they can become a sealed runtime profile.
            corruptions = (
                "DELETE FROM environmental_profile_native_variable_bindings WHERE profile_key=%s AND variable_index=0",
                "UPDATE environmental_profile_native_variable_bindings SET native_name='nbMobLeft' WHERE profile_key=%s AND native_name='nbResourceLeft'",
                "UPDATE environmental_profile_native_variable_bindings SET constant_value=999 WHERE profile_key=%s AND native_name='challengeLevelMin'",
                "UPDATE environmental_profile_native_variable_bindings SET binding_kind='global_progress' WHERE profile_key=%s AND native_name='nbResourcePlayer'",
                "UPDATE environmental_profile_native_variable_bindings SET source_authority=NULL WHERE profile_key=%s AND native_name='nbResourceMin'",
                "UPDATE environmental_profile_native_variable_bindings SET constant_value=6 WHERE profile_key=%s AND native_name='nbResourceMin'",
                "UPDATE environmental_profile_native_variable_bindings SET configuration_key='challengelevelmin',constant_value=81 WHERE profile_key=%s AND native_name='nbResourceMin'",
            )
            # Player must never read the physical-global counter, and declared
            # thresholds require their exact configuration and explicit policy.
            for index, statement in enumerate(corruptions):
                key = f"forged-variables-{index}"
                with self.subTest(forgery=index), self.assertRaises(
                    psycopg.Error
                ), db.transaction():
                    self._profile(db, fixture, key, seal=False)
                    db.execute(statement, (key,))
                    db.execute(
                        "UPDATE environmental_runtime_profiles SET sealed=true WHERE profile_key=%s",
                        (key,),
                    )
                    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with self.assertRaises(psycopg.Error), db.transaction():
                db.execute(
                    "UPDATE environmental_profile_native_variable_bindings SET constant_value=246 "
                    "WHERE profile_key='native-vars' AND native_name='challengeLevelMax'"
                )
        ticket = fixture.ticket(resources[0])
        fixture.clock[0] += 5
        result = resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))
        self.assertTrue(result["applied"])
        self.assertFalse(
            resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        with store.connection() as db:
            projections(db, personal=1, global_count=1, remaining=99)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_progress "
                    "WHERE instance_id=%s AND quantity=1",
                    (event["instance_id"],),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions "
                    "WHERE instance_id=%s",
                    (event["instance_id"],),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions "
                    "WHERE instance_id=%s",
                    (legacy["instance_id"],),
                ).fetchone()["n"],
                0,
            )
            retired = db.execute(
                "SELECT resource_uid FROM environmental_owned_resources "
                "WHERE instance_id=%s AND retired_at_ms IS NOT NULL",
                (event["instance_id"],),
            ).fetchall()
            self.assertEqual(
                [r["resource_uid"] for r in retired], [resources[0]["resource_uid"]]
            )
            self.assertFalse(
                population.retire(
                    db,
                    resources[0]["resource_uid"],
                    now_ms=int(fixture.clock[0] * 1000),
                    reason="interaction",
                )
            )
            storage.cancel(
                db,
                event["instance_id"],
                reason="test durable inventory cleanup",
                now_ms=int(fixture.clock[0] * 1000),
            )
            population.cleanup(
                db, map_id=327, instance_id=0, now_ms=int(fixture.clock[0] * 1000)
            )
            projections(db, personal=1, global_count=1, remaining=0)
            self.assertEqual(
                {
                    r["resource_uid"]
                    for r in db.execute(
                        "SELECT resource_uid FROM environmental_owned_resources WHERE instance_id=%s",
                        (event["instance_id"],),
                    ).fetchall()
                },
                uids,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planted_resources "
                    "WHERE resource_uid=ANY(%s)",
                    (list(uids),),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                population.populate(db, event, now_ms=int(fixture.clock[0] * 1000)), ()
            )

    def test_competitive_leader_is_max_personal_progress_with_distinct_shared_global_and_stock(
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
        owners = [
            (fixture.account, fixture.generation, fixture.character),
            fixture.owner(),
            fixture.owner(),
        ]
        with store.connection() as db:
            original = [
                dict(r)
                for r in db.execute(
                    "SELECT ordinal,native_name FROM environmental_native_variables "
                    "WHERE source_key=%s AND scenario_id=-2247 ORDER BY ordinal",
                    (self.SOURCE,),
                )
            ]
            config = {
                r["normalized_key"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_native_configuration "
                    "WHERE source_key=%s AND scenario_id=-2247",
                    (self.SOURCE,),
                )
            }
        self.assertEqual(
            [r["native_name"] for r in original],
            [
                "challengeLevelMax",
                "challengeLevelMin",
                "nbResourceForReward",
                "nbResourceGlobal",
                "nbResourceLeft",
                "nbResourceMax",
                "nbResourcePlayer",
                "nbResourceSpawned",
            ],
        )

        def create_profile(db, key, *, mode="competitive", corruption=None):
            # A controlled gameplay fixture, not an original native scenario
            # population: its action and admission scope remain declared.
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,"
                "level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES(%s,1,-2247,'resource_collect',%s,527,17,60000,%s,1,245,%s,%s,%s)",
                (
                    key,
                    mode,
                    fixture.now_ms - 1000,
                    "test-declared leader component fixture",
                    "0" * 64,
                    "1" * 64,
                ),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES "
                "(%s,1,'collect','resource_collect',1337,3,1,'quantity',10)",
                (key,),
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES "
                "(%s,1,0,'xp',NULL,1,'test-only')",
                (key,),
            )
            if mode == "competitive":
                db.execute(
                    "INSERT INTO environmental_profile_evaluation VALUES "
                    "(%s,1,'score_at_deadline',1,'character_id','test-declared evaluator')",
                    (key,),
                )
            db.execute(
                "INSERT INTO environmental_profile_native_variable_policy VALUES(%s,1,%s,-2247,%s,%s)",
                (
                    key,
                    self.SOURCE,
                    variables.CONTRACT,
                    "test-declared ordered native array",
                ),
            )
            for row in original:
                name = row["native_name"]
                objective = configuration = constant = entity = authority = None
                if name.lower() in config:
                    kind = "configconstant"
                    configuration = config[name.lower()]["native_key"]
                    constant = int(config[name.lower()]["native_value"])
                elif name in ("nbResourcePlayer", "nbResourceGlobal", "nbResourceMax"):
                    kind = {
                        "nbResourcePlayer": "personal_progress",
                        "nbResourceGlobal": "global_progress",
                        "nbResourceMax": "leader_progress",
                    }[name]
                    objective = "collect"
                    if kind == "leader_progress":
                        authority = "Wakemu explicit maximum personal objective contribution; not original setter"
                else:
                    kind, entity = (
                        "spawned" if name == "nbResourceSpawned" else "remaining"
                    ), "resource"
                db.execute(
                    "INSERT INTO environmental_profile_native_variable_bindings "
                    "(profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,"
                    "objective_key,configuration_key,constant_value,source_authority,entity_kind) "
                    "VALUES(%s,1,%s,-2247,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        key,
                        self.SOURCE,
                        row["ordinal"],
                        name,
                        kind,
                        objective,
                        configuration,
                        constant,
                        authority,
                        entity,
                    ),
                )
            if corruption:
                db.execute(corruption, (key,))
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                (key,),
            )

        with store.connection() as db:
            create_profile(db, "leader-native")
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for index, corruption in enumerate(
                (
                    "UPDATE environmental_profile_native_variable_bindings SET source_authority=NULL WHERE profile_key=%s AND binding_kind='leader_progress'",
                    "UPDATE environmental_profile_native_variable_bindings SET source_authority='' WHERE profile_key=%s AND binding_kind='leader_progress'",
                    "UPDATE environmental_profile_native_variable_bindings SET objective_key=NULL WHERE profile_key=%s AND binding_kind='leader_progress'",
                    "UPDATE environmental_profile_native_variable_bindings SET native_name='nbResourceGlobal' WHERE profile_key=%s AND binding_kind='leader_progress'",
                    "UPDATE environmental_profile_native_variable_bindings SET variable_index=127 WHERE profile_key=%s AND binding_kind='leader_progress'",
                )
            ):
                with self.subTest(corruption=index), self.assertRaises(
                    psycopg.Error
                ), db.transaction():
                    db.execute("SET CONSTRAINTS ALL DEFERRED")
                    create_profile(db, f"leader-forged-{index}", corruption=corruption)
                    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with self.assertRaises(psycopg.Error), db.transaction():
                db.execute("SET CONSTRAINTS ALL DEFERRED")
                create_profile(db, "leader-wrong-mode", mode="solo")
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        event_id = fixture.admit()["instances"][0]["instance_id"]
        for account, generation, character in owners[1:]:
            self.assertEqual(
                fixture.admit(account, generation, character)["instances"][0][
                    "instance_id"
                ],
                event_id,
            )
        fixture.roster(event_id, [9101, 9102, 9103])
        # All owners receive the same genuine physical-action receipt once;
        # the shared ledger counts it once. Two further physical actions give
        # personal30/20/10, physical40, and personal-sum60.
        for account, _, character in owners:
            fact = replace(
                fixture.fact(9101, account=account, character=character), quantity=10
            )
            self.assertTrue(fixture.consume(fact))
            self.assertEqual(fixture.consume(fact), ())
        self.assertTrue(fixture.consume(replace(fixture.fact(9102), quantity=20)))
        self.assertTrue(
            fixture.consume(
                replace(
                    fixture.fact(9103, account=owners[1][0], character=owners[1][2]),
                    quantity=10,
                )
            )
        )
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            profile = dict(storage._event_profile(db, event))
            participants = {
                r["character_id"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_participants WHERE instance_id=%s",
                    (event_id,),
                )
            }
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM environmental_progress WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                60,
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM environmental_shared_actions WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                40,
            )
            for index, (_, _, character) in enumerate(owners):
                participant = participants[character["id"]]
                projected = variables.project(
                    db, event, profile, participant, fixture.now_ms + 2
                )
                self.assertEqual(
                    [(r["variable_index"], r["name"]) for r in projected],
                    [(r["ordinal"], r["native_name"]) for r in original],
                )
                values = {r["name"]: r["value"] for r in projected}
                self.assertEqual(
                    (
                        values["nbResourceMax"],
                        values["nbResourcePlayer"],
                        values["nbResourceGlobal"],
                    ),
                    (30, 30 - index * 10, 40),
                )
                self.assertEqual(
                    (values["nbResourceSpawned"], values["nbResourceLeft"]), (0, 0)
                )
                self.assertEqual(
                    (
                        values["challengeLevelMin"],
                        values["challengeLevelMax"],
                        values["nbResourceForReward"],
                    ),
                    (231, 245, 10),
                )
                for wrong_mode in ("solo", "race", "collaborative"):
                    with self.subTest(mode=wrong_mode), self.assertRaises(ValueError):
                        variables.project(
                            db,
                            event,
                            dict(profile, mode=wrong_mode),
                            participant,
                            fixture.now_ms + 2,
                        )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_rankings"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
