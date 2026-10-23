"""Finite original-pool births and whole-victory secondary counters on SQL."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.achievements import service as achievements, storage as journal
from wakfu_server import heroes
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.combat_state import Actor
from wakfu_server.monsters import REFERENCES
from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives import environmental_group_population as population
from wakfu_server.objectives import environmental_group_publication as publication
from wakfu_server.objectives import environmental_group_progress as progress
from wakfu_server.objectives import environmental_native_variables as variables
from wakfu_server.objectives import environmental_random_rosters as random
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.progression import XP_BY_LEVEL


class EnvironmentalRandomGroupLifecycleTests(unittest.TestCase):
    def test_exact_original_draw_retry_repin_whole_fight_hero_counters_and_collaborative_birth_goal(
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
        store, account, main = fixture.store, fixture.account, fixture.character["id"]
        groups = PersistentGroups(store)
        hero = store.create_character(account, "Group Counter Hero")
        with store.connection() as db:
            db.execute("UPDATE characters SET level=81 WHERE id=%s", (hero["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[81], hero["id"]),
            )
        heroes.add(store, account, fixture.generation, main, hero["id"])
        self.assertTrue(store.heartbeat(account, fixture.generation, ttl=1800))
        race, collab = "group-native-1331-327-56601", "group-native-1329-327-56601"
        # The complete seed was qualified separately. Import its exact two
        # profile statements only; no repeated all790 bootstrap or fabricated
        # roster/cell data, and a declared two-candidate test schedule.
        raw = (
            Path(__file__).parents[1] / "seeds/environmental_group_profiles.sql"
        ).read_text()
        selected_statements = []
        for fragment in raw.split(";\n"):
            statement = fragment.strip()
            if any("E'" + key + "'" in statement for key in (race, collab)):
                if statement.startswith(
                    "INSERT INTO environmental_profile_"
                ) or statement.startswith("INSERT INTO environmental_runtime_profiles"):
                    selected_statements.append(statement + ";")
                elif statement.startswith(
                    "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                ):
                    selected_statements.append(statement + ";")
        self.assertGreater(len(selected_statements), 20)
        with store.connection() as db:
            for statement in selected_statements:
                db.execute(statement, prepare=False)
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('fixture-two-native-groups',1,327,56601,'wakemu_round_robin','occupied_sequential_windows',0,"
                "'explicit finite two-source component schedule',%s)",
                ("0" * 64,),
            )
            for ordinal, key in enumerate((race, collab)):
                db.execute(
                    "INSERT INTO environmental_regional_schedule_candidates VALUES "
                    "('fixture-two-native-groups',1,%s,%s,1)",
                    (ordinal, key),
                )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true WHERE policy_key='fixture-two-native-groups'"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (race,),
            )
            active = dict(
                db.execute(
                    "SELECT * FROM environmental_random_roster_active WHERE singleton"
                ).fetchone()
            )
            self.assertFalse(active["enabled"])
            db.execute(
                "UPDATE environmental_random_roster_active SET enabled=true WHERE singleton"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")

        def refresh():
            return service.refresh(
                store,
                account,
                fixture.generation,
                main,
                location=fixture.location,
                now_ms=int(fixture.clock[0] * 1000),
                groups=groups,
            )

        with patch.object(random, "_geometry", return_value=([], {})):
            initial = refresh()
        event_id = initial["instances"][0]["instance_id"]
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            self.assertEqual(event["profile_key"], race)
            header = dict(
                db.execute(
                    "SELECT * FROM environmental_random_roster_draws WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            slots = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_random_roster_slots "
                    "WHERE instance_id=%s ORDER BY group_ordinal,member_ordinal",
                    (event_id,),
                )
            ]
            self.assertEqual(
                (header["group_count"], header["min_members"], header["max_members"]),
                (2, 2, 5),
            )
            counts = Counter(r["group_ordinal"] for r in slots)
            self.assertEqual(set(counts), {0, 1})
            self.assertTrue(all(2 <= n <= 5 for n in counts.values()))
            self.assertTrue(
                {r["monster_reference"] for r in slots} <= {4424, 4425, 4426}
            )
            for row in slots:
                self.assertEqual(
                    row["native_level"],
                    REFERENCES[row["monster_reference"]]["min_level"],
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "INSERT INTO environmental_random_roster_versions SELECT "
                "'fixture-repin',policy_contract,min_members,max_members,max_zone_members,max_zone_groups,source_authority,source_sha256 "
                "FROM environmental_random_roster_versions WHERE policy_version=%s",
                (active["policy_version"],),
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET policy_version='fixture-repin',enabled=false WHERE singleton"
            )
        # All-or-none birth rollback cannot lose the already-earned draw.
        with self.assertRaisesRegex(
            RuntimeError, "rollback birth"
        ), store.connection() as db:
            self.assertEqual(
                len(population.populate(db, event, groups, now_ms=fixture.now_ms)), 2
            )
            raise RuntimeError("rollback birth")
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups"
                ).fetchone()["n"],
                0,
            )
            keys = population.populate(db, event, groups, now_ms=fixture.now_ms)
            self.assertEqual(len(keys), 2)
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM environmental_random_roster_draws WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()
                ),
                header,
            )
            self.assertEqual(
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM environmental_random_roster_slots "
                        "WHERE instance_id=%s ORDER BY group_ordinal,member_ordinal",
                        (event_id,),
                    )
                ],
                slots,
            )
            self.assertEqual(
                population.populate(db, event, groups, now_ms=fixture.now_ms), ()
            )
        with patch.object(
            fixture.world, "emit_location_batch", return_value=False
        ) as failed_send:
            self.assertEqual(
                publication.publish(
                    store,
                    fixture.world,
                    groups,
                    map_id=327,
                    instance_id=0,
                    now_ms=fixture.now_ms,
                ),
                0,
            )
            self.assertEqual(failed_send.call_count, 2)
            self.assertTrue(
                all(
                    call.kwargs.get("require_all") is True
                    for call in failed_send.call_args_list
                )
            )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_publications WHERE kind='spawn' AND published_at_ms IS NULL"
                ).fetchone()["n"],
                2,
            )
        self.assertEqual(
            publication.publish(
                store,
                fixture.world,
                groups,
                map_id=327,
                instance_id=0,
                now_ms=fixture.now_ms,
            ),
            2,
        )

        def winning_receipts(members, *, lease=None):
            with store.connection() as db:
                fight_id = (
                    lease[2]
                    if lease
                    else db.execute(
                        "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
                    ).fetchone()["id"]
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
                actors = {
                    r["id"]: SimpleNamespace(controlled=False, team=1, hp=0)
                    for r in members
                }
                for identity in (main, hero["id"]):
                    actual = store.character(account, identity, db)
                    actors[identity] = Actor(
                        identity,
                        0,
                        (actual["x"], actual["y"], actual["z"]),
                        actual["hp"],
                        6,
                        3,
                        0,
                        actual["effective_level"],
                        owner_id=account,
                        controlled=True,
                    )
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0) ON CONFLICT DO NOTHING",
                        (fight_id, identity, account),
                    )
                fight = SimpleNamespace(
                    id=fight_id,
                    phase="finished",
                    winner=0,
                    actors=actors,
                    native_summon_registrations={},
                )
                original = [dict(id=r["id"], ref=r["ref"]) for r in members]
                for index, identity in enumerate((main, hero["id"])):
                    actual = store.character(account, identity, db)
                    receipt = achievements._event(db, actual, fight, original)
                    journal.record_event(
                        db, identity, "fight:" + str(fight_id), receipt
                    )
                    # Recipient commits can have different timestamps for the
                    # same physical kill. Global entity identity excludes them.
                    stamp = datetime.fromtimestamp(
                        (fixture.now_ms + 10 + index) / 1000, timezone.utc
                    )
                    db.execute(
                        "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                        (stamp, identity, "fight:" + str(fight_id)),
                    )
            scene = dict(
                map_id=327,
                instance_id=0,
                region_id=56601,
                original_entities=deepcopy(members),
            )
            if lease is not None:
                scene["group_lease"] = lease
            return fight_id, scene

        with store.connection() as db:
            members = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                keys[0],
            ).fetchone()["members"]
        wild = [dict(members[0], id=-99990001)]
        wild_id, wild_scene = winning_receipts(wild)
        with store.connection() as db:
            wild_facts = []
            for identity in (main, hero["id"]):
                gameplay.settled_fight(
                    db,
                    account_id=account,
                    character_id=identity,
                    fight_id=wild_id,
                    source_scene=wild_scene,
                    deferred_facts=wild_facts,
                )
            self.assertEqual(gameplay.consume(db, wild_facts), ())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_progress_facts"
                ).fetchone()["n"],
                0,
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
        lease, members = groups.claim(keys[0], fixture.generation, fight_id)
        groups.finish(lease, defeated=True)
        fight_id, scene = winning_receipts(members, lease=lease)
        fixture.world.leave(main, fixture.generation)
        with store.connection() as db:
            self.assertEqual(
                gameplay.settled_fight(
                    db,
                    account_id=account,
                    character_id=main,
                    fight_id=fight_id,
                    source_scene=scene,
                ),
                (),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_progress_facts"
                ).fetchone()["n"],
                0,
            )
        fixture.world.join(fixture.generation, object(), store.character(account, main))
        with store.connection() as db:
            facts = []
            for identity in (main, hero["id"]):
                gameplay.settled_fight(
                    db,
                    account_id=account,
                    character_id=identity,
                    fight_id=fight_id,
                    source_scene=scene,
                    deferred_facts=facts,
                )
            self.assertTrue(gameplay.consume(db, facts))
            completed = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            self.assertEqual(completed["state"], "completed")
            profile = storage._event_profile(db, completed)
            total_members = len(slots)
            killed_members = len(members)
            for identity in (main, hero["id"]):
                participant = dict(
                    db.execute(
                        "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                        (event_id, identity),
                    ).fetchone()
                )
                self.assertEqual(
                    progress.counters(db, completed, participant, "monster"),
                    (killed_members, killed_members),
                )
                self.assertEqual(
                    progress.counters(db, completed, participant, "group"), (1, 1)
                )
                values = {
                    r["name"]: r["value"]
                    for r in variables.project(
                        db, completed, profile, participant, fixture.now_ms + 20
                    )
                }
                self.assertEqual(
                    (
                        values["nbMobPlayer"],
                        values["nbMobGlobal"],
                        values["nbGroupPlayer"],
                        values["nbGroupGlobal"],
                    ),
                    (killed_members, killed_members, 1, 1),
                )
                self.assertEqual(
                    (values["nbMobSpawned"], values["nbGroupSpawned"]),
                    (total_members, 2),
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_progress_facts WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()["n"],
                2 * (killed_members + 1),
            )
            self.assertEqual(gameplay.consume(db, facts), ())
            population.cleanup(
                db, map_id=327, instance_id=0, now_ms=fixture.now_ms + 20
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=false WHERE profile_key=%s",
                (race,),
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (collab,),
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET policy_version=%s,enabled=true WHERE singleton",
                (active["policy_version"],),
            )
        # Occupied regional schedules preserve the original window even when
        # both race places finish early; advance the fixture clock, not SQL.
        fixture.clock[0] = (completed["deadline_ms"] + 1) / 1000
        next_event = refresh()["instances"][0]["instance_id"]
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (next_event,),
                ).fetchone()
            )
            self.assertEqual(event["profile_key"], collab)
            profile = storage._event_profile(db, event)
            draw = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_random_roster_slots WHERE instance_id=%s "
                    "ORDER BY group_ordinal,member_ordinal",
                    (next_event,),
                )
            ]
            self.assertEqual(random.frozen_birth_count(db, event, "group"), 30)
            self.assertEqual(random.frozen_birth_count(db, event, "monster"), len(draw))
            objective = storage._objectives(db, profile)[0]
            self.assertEqual(objective["required_quantity"], len(draw))
            self.assertEqual(profile["minimum_contribution"], 5)
            self.assertGreater(len(draw), 30)
            counts = Counter(r["group_ordinal"] for r in draw)
            ordinal = next(k for k, count in counts.items() if count < 5)
            original = next(r for r in draw if r["group_ordinal"] == ordinal)
            with self.assertRaises(ValueError), db.transaction():
                db.execute(
                    "INSERT INTO environmental_random_roster_slots VALUES(%s,%s,%s,%s,%s)",
                    (
                        next_event,
                        ordinal,
                        counts[ordinal],
                        original["monster_reference"],
                        original["native_level"],
                    ),
                )
                storage._objectives(db, profile)
            self.assertEqual(
                storage._objectives(db, profile)[0]["required_quantity"], len(draw)
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups WHERE instance_id=%s",
                    (next_event,),
                ).fetchone()["n"],
                30,
            )
