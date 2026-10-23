"""Source-exact location truth and immutable new-window admission boundaries."""
import json
import unittest
from unittest.mock import Mock, patch

from psycopg import DatabaseError
from wakfu_server import ecology_population, territory_bonuses
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.objectives import environmental_group_population as population
from wakfu_server.objectives import environmental_random_rosters as rosters
from wakfu_server.objectives import environmental_location_criteria as criteria
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_schedule as schedule
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.world import World
from test_environmental_group_bulk_pipeline import seed_sql


class EnvironmentalLocationCriteriaTests(unittest.TestCase):
    def test_real_wish_states_typed_neo_and_new_window_rotation_keep_admitted_event_pinned(
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
        store, world = fixture.store, fixture.world
        call = dict(
            criterion="GetSatisfactionLevel() >= 3",
            map_id=327,
            world_instance_id=0,
            region_id=56601,
        )
        good = dict(
            complete=True,
            regions={56601: dict(monster={406: 266, 772: 400}, plant={1: 133})},
        )
        partial = dict(
            complete=True,
            regions={56601: dict(monster={406: 265, 772: 400}, plant={1: 133})},
        )
        none = dict(
            complete=True,
            regions={56601: dict(monster={406: 10, 772: 500}, plant={1: 0})},
        )
        # Source aMD wishes, native statuses and inclusive boundaries are real;
        # only the population read is replaced by bounded complete snapshots.
        evaluated = territory_bonuses.evaluate_population(
            56601, good["regions"][56601]["monster"], {1: 133}
        )
        self.assertEqual(
            (evaluated["satisfied_wishes"], evaluated["total_wishes"]), (3, 3)
        )
        fixture.world.leave(fixture.character["id"], fixture.generation)
        vacant_db = Mock()
        self.assertFalse(criteria.eligible(vacant_db, **call))
        vacant_db.execute.assert_not_called()
        fixture.world.join(fixture.generation, object(), fixture.character)
        with store.connection() as db:
            for snapshot, expected in (
                (good, True),
                (partial, False),
                (none, False),
                (dict(good, complete=False), False),
            ):
                with self.subTest(snapshot=snapshot), patch.object(
                    ecology_population, "snapshot", return_value=snapshot
                ):
                    self.assertIs(criteria.eligible(db, **call), expected)
            with patch.object(ecology_population, "snapshot") as population_read:
                self.assertFalse(criteria.eligible(db, **dict(call, region_id=62501)))
                self.assertFalse(criteria.eligible(db, **dict(call, region_id=59701)))
                population_read.assert_not_called()
            no_wishes_world = World(lambda _: b"", lambda _: b"", lambda *_: True)
            no_wishes_world.join(
                fixture.generation, object(), dict(fixture.character, map_id=472)
            )
            with patch.object(presence, "_world", no_wishes_world), patch.object(
                ecology_population,
                "snapshot",
                return_value=dict(
                    complete=True, regions={59701: dict(monster={}, plant={})}
                ),
            ):
                self.assertFalse(
                    criteria.eligible(db, **dict(call, map_id=472, region_id=59701))
                )

            def leave_during_snapshot(*args, **kwargs):
                world.leave(fixture.character["id"], fixture.generation)
                return good

            with patch.object(
                ecology_population, "snapshot", side_effect=leave_during_snapshot
            ):
                self.assertFalse(criteria.eligible(db, **call))
            world.join(fixture.generation, object(), fixture.character)
            for enabled in (False, True):
                db.execute(
                    "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s::jsonb) "
                    "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                    (json.dumps(dict(version=1, is_neo_server=enabled)),),
                )
                self.assertIs(
                    criteria.eligible(db, **dict(call, criterion="IsNeoServer()")),
                    enabled,
                )
            db.execute(
                "UPDATE settings SET value=%s::jsonb WHERE name='dungeon_server_mode'",
                (json.dumps(dict(version=1, is_neo_server="false")),),
            )
            with self.assertRaises(ValueError):
                criteria.eligible(db, **dict(call, criterion="IsNeoServer()"))
            for unsupported in (
                "GetSatisfactionLevel() >= 2",
                "IsNeoServer() || true",
                "GetSatisfactionLevel() >= 3.0",
            ):
                with self.subTest(unsupported=unsupported), self.assertRaises(
                    ValueError
                ):
                    criteria.eligible(db, **dict(call, criterion=unsupported))

        herd, blank = "group-native-1333-327-56601", "group-native-1331-327-56601"

        def statements(filename, key):
            for fragment in seed_sql(filename).split(";\n"):
                text = fragment.strip()
                if "E'" + key + "'" not in text:
                    continue
                if (
                    text.startswith("INSERT INTO environmental_profile_")
                    or text.startswith("INSERT INTO environmental_runtime_profiles")
                    or text.startswith(
                        "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                    )
                ):
                    yield text + ";"

        with store.connection() as db:
            # A source-bound HERD cannot be admitted through a legacy path by
            # silently omitting its required guard. Test the real SQL seal.
            with self.assertRaises(DatabaseError), db.transaction():
                for statement in statements(
                    "environmental_group_criteria_profiles.sql", herd
                ):
                    if statement.startswith(
                        "INSERT INTO environmental_profile_location_policy"
                    ):
                        continue
                    db.execute(
                        statement.replace(
                            "E'" + herd + "'", "E'fixture-missing-location-guard'"
                        ),
                        prepare=False,
                    )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM environmental_runtime_profiles "
                    "WHERE profile_key='fixture-missing-location-guard'"
                ).fetchone()
            )
            # Exercise the unscheduled creation seam separately; changing the
            # anchor is an explicit component-fixture window, not a claim about
            # native challenge scheduling. Roll this whole section back before
            # installing the independent regional schedule below.
            with self.assertRaisesRegex(
                RuntimeError, "legacy section verified"
            ), db.transaction():
                for statement in statements(
                    "environmental_group_criteria_profiles.sql", herd
                ):
                    if not statement.startswith(
                        "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                    ):
                        db.execute(statement, prepare=False)
                db.execute(
                    "UPDATE environmental_runtime_profiles SET anchor_ms=%s,sealed=true,enabled=true "
                    "WHERE profile_key=%s",
                    (fixture.now_ms - 1000, herd),
                )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")

                def legacy_refresh(now_ms):
                    return storage.refresh(
                        db,
                        account_id=fixture.account,
                        character_id=fixture.character["id"],
                        location=fixture.location,
                        now_ms=now_ms,
                    )

                with patch.object(ecology_population, "snapshot", return_value=partial):
                    self.assertEqual(legacy_refresh(fixture.now_ms)["instances"], [])
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_event_instances"
                    ).fetchone()["n"],
                    0,
                )
                with patch.object(ecology_population, "snapshot", return_value=good):
                    created = legacy_refresh(fixture.now_ms)["instances"][0]
                self.assertEqual(created["profile_key"], herd)
                with patch.object(ecology_population, "snapshot", return_value=partial):
                    resumed = legacy_refresh(fixture.now_ms + 1)["instances"][0]
                self.assertEqual(resumed["instance_id"], created["instance_id"])
                raise RuntimeError("legacy section verified")
            for filename, key in (
                ("environmental_group_criteria_profiles.sql", herd),
                ("environmental_group_profiles.sql", blank),
            ):
                for statement in statements(filename, key):
                    db.execute(statement, prepare=False)
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=ANY(%s)",
                ([herd, blank],),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('fixture-native-location',1,327,56601,'wakemu_round_robin','occupied_sequential_windows',0,"
                "'declared two-source admission component',%s)",
                ("0" * 64,),
            )
            for ordinal, key in enumerate((herd, blank)):
                db.execute(
                    "INSERT INTO environmental_regional_schedule_candidates VALUES('fixture-native-location',1,%s,%s,1)",
                    (ordinal, key),
                )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true "
                "WHERE policy_key='fixture-native-location'"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with patch.object(ecology_population, "snapshot", return_value=partial):
                first = schedule.select_event(
                    db, location=fixture.location, now_ms=fixture.now_ms
                )
            self.assertEqual(first["profile_key"], blank)
            # Changed truth cannot evict an existing active window.
            with patch.object(ecology_population, "snapshot", return_value=good):
                pinned = schedule.select_event(
                    db, location=fixture.location, now_ms=fixture.now_ms + 1
                )
            self.assertEqual(pinned["instance_id"], first["instance_id"])
            storage.cancel(
                db,
                first["instance_id"],
                reason="bounded fixture window finished",
                now_ms=first["deadline_ms"],
            )
            with patch.object(ecology_population, "snapshot", return_value=good):
                admitted = schedule.select_event(
                    db, location=fixture.location, now_ms=first["deadline_ms"]
                )
            self.assertEqual(admitted["profile_key"], herd)
            with patch.object(ecology_population, "snapshot", return_value=partial):
                still_admitted = schedule.select_event(
                    db, location=fixture.location, now_ms=first["deadline_ms"] + 1
                )
            self.assertEqual(still_admitted["instance_id"], admitted["instance_id"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )
            # HERD type7 follows the same admitted scope but its objective is
            # GROUP births, not the sum of the 2..5 members in each group.
            # Its sole special native species must survive ordinary-world
            # filtering and retain native level93, not player/challenge level81.
            db.execute(
                "UPDATE environmental_random_roster_active SET enabled=true WHERE singleton"
            )
            registry = PersistentGroups(store)
            captured_bindings = []
            original_binding = rosters.binding

            def observe_binding(*args, **kwargs):
                value = original_binding(*args, **kwargs)
                captured_bindings.append(None if value is None else dict(value))
                return value

            with patch.object(
                rosters, "binding", side_effect=observe_binding
            ), patch.object(rosters, "plan", wraps=rosters.plan) as observed_plan:
                born = population.populate(
                    db, admitted, registry, now_ms=admitted["started_at_ms"]
                )
            diagnostic = {}
            if len(born) != 10:
                from wakfu_server import native_catalog
                from wakfu_server.combat_actor_snapshot import native_actor_catalog
                from wakfu_server.monster_population_capacity import (
                    physical_groups,
                    pending_growth_groups,
                    physical_cells,
                )

                positions, adjacency = rosters._geometry(
                    native_catalog.release(), 327, 56601
                )
                physical = physical_groups(db, 327, 0)
                pending = pending_growth_groups(
                    db, 327, 0, existing_group_ids={r["group_id"] for r in physical}
                )
                row = db.execute(
                    "SELECT * FROM environmental_random_roster_draws WHERE instance_id=%s",
                    (admitted["instance_id"],),
                ).fetchone()
                diagnostic = dict(
                    binding_calls=captured_bindings,
                    plan_calls=observed_plan.call_count,
                    plan_policy=(
                        dict(observed_plan.call_args.args[3])
                        if observed_plan.call_args
                        else None
                    ),
                    event=dict(
                        db.execute(
                            "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                            (admitted["instance_id"],),
                        ).fetchone()
                    ),
                    profile=dict(storage._event_profile(db, admitted)),
                    draw_header=None if row is None else dict(row),
                    slot_count=db.execute(
                        "SELECT count(*) AS n FROM environmental_random_roster_slots WHERE instance_id=%s",
                        (admitted["instance_id"],),
                    ).fetchone()["n"],
                    geometry_cells=len(positions),
                    connected_cells=sum(bool(adjacency[p]) for p in positions),
                    species_2133_physical_radius=native_actor_catalog()["npc_profiles"][
                        "2133"
                    ]["physical_radius"],
                    physical_groups=len(physical),
                    physical_members=sum(len(r["members"]) for r in physical),
                    physical_cells=len(physical_cells(db, 327, 0)),
                    pending_groups=len(pending),
                    pending_members=sum(len(r["members"]) for r in pending),
                    taken_count=(
                        len(observed_plan.call_args.kwargs["taken"])
                        if observed_plan.call_args
                        else None
                    ),
                )
            self.assertEqual(
                len(born), 10, json.dumps(diagnostic, default=str, sort_keys=True)
            )
            profile = storage._event_profile(db, admitted)
            self.assertEqual(
                (profile["family"], profile["mode"], profile["level_min"]),
                ("group_defeat", "collaborative", 81),
            )
            source = db.execute(
                "SELECT p.group_count,p.native_type,s.monster_reference,n.native_min_level "
                "FROM environmental_random_roster_policies p "
                "JOIN environmental_random_roster_species s USING(source_key,scenario_id,policy_version) "
                "JOIN environmental_random_native_species n USING(monster_reference) "
                "WHERE p.scenario_id=-1333"
            ).fetchall()
            self.assertEqual(
                [
                    (
                        r["group_count"],
                        r["native_type"],
                        r["monster_reference"],
                        r["native_min_level"],
                    )
                    for r in source
                ],
                [(10, 7, 2133, 93)],
            )
            members = db.execute(
                "SELECT monster_reference,native_level FROM environmental_owned_group_members "
                "WHERE instance_id=%s",
                (admitted["instance_id"],),
            ).fetchall()
            self.assertGreaterEqual(len(members), 20)
            self.assertLessEqual(len(members), 50)
            self.assertEqual(
                {(r["monster_reference"], r["native_level"]) for r in members},
                {(2133, 93)},
            )
            self.assertEqual(rosters.frozen_birth_count(db, admitted, "group"), 10)
            self.assertEqual(
                rosters.frozen_birth_count(db, admitted, "monster"), len(members)
            )
            self.assertEqual(
                storage._objectives(db, profile)[0]["required_quantity"], 10
            )
            self.assertNotEqual(
                storage._objectives(db, profile)[0]["required_quantity"], len(members)
            )
