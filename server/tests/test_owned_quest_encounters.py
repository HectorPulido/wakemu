"""Reviewed quest arenas retain native transport, owner and real-victory fences."""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.achievements import owned_quest_encounters as quest
from wakfu_server import dungeon_instances, dungeon_native_flow, dungeon_object_states
from wakfu_server import generic_transports
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.combat_state import Fight, Actor
from wakfu_server.monsters import reference
from wakfu_server.quest_instance_configuration import compile_profile


class OwnedQuestEncounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/quest_encounter_profiles/astrub-warehouse.json"
            ).read_text()
        )
        cls.sources = {(s["map_id"], s["id"]): s for s in generic_transports._CATALOG}
        cls.configuration = compile_profile(
            profile,
            geometry=published_geometry(891),
            exploration=json.loads(
                (
                    Path(__file__).parents[1]
                    / "wakfu_server/maps/quest_encounter_profiles"
                    / profile["exploration_file"]
                ).read_text()
            ),
            sources=cls.sources,
            monster=reference(3233),
        )

    def setUp(self):
        self.selected = quest.policy(self.configuration)
        self.character = dict(id=7, account_id=2, map_id=891, instance_id=99)
        self.state = dict(
            variables={},
            objectives=[4079],
            running=[2016],
            completed=[],
            tracking=[2016],
            recent=[],
            completion_dates={},
        )
        self.originals = [dict(id=-(n + 1), ref=3233) for n in range(3)]
        cells = [(n, 0, 0) for n in range(4)]
        self.fight = Fight(
            123,
            [Actor(7, 0, cells[0], 100, 6, 3, 10, 35, owner_id=2, controlled=True)]
            + [
                Actor(row["id"], 1, cells[n + 1], 60, 4, 3, 30, 30)
                for n, row in enumerate(self.originals)
            ],
            cells,
            {0: cells[:1], 1: cells[1:]},
        )
        self.fight.phase, self.fight.winner = "finished", 0
        for row in self.originals:
            self.fight.actors[row["id"]].hp = 0
        self.fight.native_summon_registrations = {}
        self.assertFalse(hasattr(self.fight, "map_id"))
        self.encounter = dict(
            asset_map_id=891,
            status="victory",
            player_team=0,
            encounter_scope="main",
            result=dict(victory=True, completed=True),
            room_order=1,
            instance_id=99,
            context_route_key=self.configuration["route"]["key"],
            context_policy_version=1,
        )
        self.members = [dict(character_id=7)]
        self.spawned = dict(
            status="defeated", asset_map_id=891, members=copy.deepcopy(self.originals)
        )
        self.definition = dict(
            d=2016,
            native_class="aJM",
            aqb=False,
            cjI="",
            cjK=[],
            cjJ=[dict(d=i, ckc="", cke="", ckf=[], ckd=[]) for i in [4079, 4084, 4140]],
        )
        self.db = SimpleNamespace(execute=self.execute)
        self.store = SimpleNamespace(
            character=lambda *_: dict(self.character),
            now=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        self.planned = []
        self.enter_context(
            patch.object(
                quest.storage,
                "load_locked",
                side_effect=lambda *_: copy.deepcopy(self.state),
            )
        )
        self.enter_context(
            patch.object(quest.storage, "record_event", return_value=True)
        )
        self.enter_context(
            patch(
                "wakfu_server.dungeon_runtime_config.pinned_configuration",
                return_value=self.configuration,
            )
        )
        self.enter_context(
            patch.object(quest.mission_dependencies, "settle", side_effect=self.persist)
        )

    def enter_context(self, manager):
        self.addCleanup(manager.__exit__, None, None, None)
        return manager.__enter__()

    def persist(self, db, store, character, before, planned, *_, **__):
        self.planned.append(planned)
        self.state = copy.deepcopy(planned[0])
        return dict(packets=[(13312, b"changed")])

    def execute(self, sql, params=()):
        if "SELECT c.id,c.account_id FROM characters" in sql:
            result = dict(id=7, account_id=2)
        elif "AS policy" in sql:
            result = dict(policy=self.selected)
        elif "SELECT e.*" in sql:
            result = self.encounter
        elif "SELECT character_id FROM dungeon_instance_members" in sql:
            return SimpleNamespace(fetchall=lambda: copy.deepcopy(self.members))
        elif "SELECT 1 FROM combat_fight_participants" in sql:
            result = dict(ok=1)
        elif "SELECT g.members,g.status" in sql:
            result = self.spawned
        elif "SELECT data FROM native_quest_metadata_definitions" in sql:
            result = dict(data=dict(native=self.definition))
        else:
            raise AssertionError(sql)
        return SimpleNamespace(fetchone=lambda: copy.deepcopy(result))

    def test_native_map_routes_and_cellar_are_preserved_without_stat_override(self):
        c = self.configuration
        t = c["topology"]
        g = published_geometry(891)
        self.assertFalse(c["compiled_plan"]["official"])
        self.assertEqual(set(map(tuple, t["rooms"][0]["cells"])), g.cells)
        self.assertEqual(len(t["rooms"][0]["encounter_region"]["cells"]), 67)
        self.assertEqual(c["route"]["criterion"], "IsAchievementRunning(2016)")
        routes = dungeon_instances._load_routes([c["route"]])
        self.assertEqual(routes[c["route"]["key"]].native_template_id, -1)
        for identity in (23180, 23031, 23181):
            self.assertEqual(
                dungeon_native_flow.object_room(t, self.sources[(891, identity)]), 1
            )
        packets = dungeon_object_states.packets(
            t,
            map_id=891,
            instance_id=99,
            unlocked_room=1,
            sources=[s for s in self.sources.values() if s["map_id"] == 891],
        )
        self.assertEqual(len(packets), 3)
        roster = c["compiled_plan"]["rooms"][0]["monsters"][0]
        self.assertEqual(
            (
                roster["ref_id"],
                roster["count"],
                roster["native_min_level"],
                roster["native_max_level"],
            ),
            (3233, 3, 30, 30),
        )
        from wakfu_server.combat_geometry import prepare_geometry, reachable

        walking = prepare_geometry(t["exploration_geometry"])
        self.assertIn(
            (-15, -159, 12),
            reachable((-11, -159, 0), walking.cells, walking.outgoing),
        )
        self.assertNotIn(
            (-15, -159, 12), reachable((-11, -159, 0), g.cells, g.outgoing)
        )

    def test_activated_quest_route_preserves_existing_registry_and_rejects_collision(
        self,
    ):
        from wakfu_server.quest_instance_configuration import merge_runtime_routes

        ordinary = dict(dungeon_instances._ROUTES)
        merged = merge_runtime_routes(ordinary, [self.configuration])
        self.assertEqual({key: merged[key] for key in ordinary}, ordinary)
        self.assertIn(self.configuration["route"]["key"], merged)
        conflict = copy.deepcopy(self.configuration)
        conflict["route"]["key"] = "conflicting-owned-entrance"
        with self.assertRaisesRegex(ValueError, "another route"):
            merge_runtime_routes(merged, [conflict])

    def test_physical_visits_only_advance_an_actually_running_admitted_mission(self):
        baseline = copy.deepcopy(self.state)
        resolved = dict(
            route=SimpleNamespace(
                key=self.configuration["route"]["key"], context_route_key=None
            )
        )
        cases = (
            ("running", dict(running=[2016]), True),
            ("unassigned", dict(running=[]), False),
            (
                "completed",
                dict(running=[], completed=[2016], objectives=[4079, 4084]),
                False,
            ),
            ("completed_with_followup", dict(running=[2166], completed=[2016]), False),
            (
                "expired_active_period",
                dict(
                    running=[2016],
                    active=[2016],
                    active_periods={
                        "2016": dict(
                            anchor_ms=1000, period_seconds=60, accepted_at_ms=1000
                        )
                    },
                ),
                False,
            ),
            (
                "unknown_completed",
                dict(running=[], completed=[2016], active=[], active_unknown=[2016]),
                False,
            ),
        )
        with patch("wakfu_server.companions.controlled_count", return_value=0):
            for label, changes, advances in cases:
                with self.subTest(phase=label):
                    self.state = dict(copy.deepcopy(baseline), objectives=[])
                    self.state.update(changes)
                    before = copy.deepcopy(self.state)
                    self.planned.clear()
                    session = dict(
                        context_policy_version=1, members=(7,), instance_id=99
                    )
                    quest.initialize(self.db, session, resolved, store=self.store)
                    self.assertEqual(
                        session["owned_quest_encounter"].get("content_only", False),
                        not advances,
                    )
                    packets = quest.settle(
                        self.db, self.store, self.character, self.fight, self.originals
                    )
                    if advances:
                        self.assertTrue(packets)
                        self.assertEqual(self.state["objectives"], [4079, 4084])
                        self.assertEqual(len(self.planned), 2)
                        self.assertTrue(all(plan[1] == [] for plan in self.planned))
                    else:
                        self.assertEqual(packets, [])
                        self.assertEqual(self.state, before)
                        self.assertEqual(self.planned, [])
            # Assignment after a content visit never retroactively grants entry.
            self.state = dict(copy.deepcopy(baseline), objectives=[])
            self.planned.clear()
            self.assertEqual(
                quest.settle(
                    self.db, self.store, self.character, self.fight, self.originals
                ),
                [],
            )
            self.assertEqual(self.planned, [])
            with self.assertRaises(ValueError):
                quest.initialize(
                    self.db, dict(session, members=(7, 8)), resolved, store=self.store
                )
        with patch(
            "wakfu_server.companions.controlled_count", return_value=1
        ), self.assertRaises(ValueError):
            quest.initialize(self.db, session, resolved, store=self.store)

    def test_committed_owned_victory_advances_once_without_giving_book(self):
        self.assertTrue(
            quest.settle(
                self.db, self.store, self.character, self.fight, self.originals
            )
        )
        self.assertEqual(self.state["objectives"], [4079, 4084])
        self.assertEqual(self.state["running"], [2016])
        self.assertEqual(self.state["completed"], [])
        self.assertEqual(self.planned[0][1], [])
        self.assertEqual(
            quest.settle(
                self.db, self.store, self.character, self.fight, self.originals
            ),
            [],
        )

    def test_wrong_instance_defeat_unfinished_and_nonowner_never_advance(self):
        for changes in [
            dict(status="defeat"),
            dict(result=dict(victory=False, completed=False)),
            dict(player_team=1),
            dict(encounter_scope="optional"),
        ]:
            before = self.encounter
            self.encounter = dict(before, **changes)
            self.assertEqual(
                quest.settle(
                    self.db, self.store, self.character, self.fight, self.originals
                ),
                [],
            )
            self.encounter = before
        self.assertEqual(
            quest.settle(
                self.db,
                self.store,
                dict(self.character, instance_id=100),
                self.fight,
                self.originals,
            ),
            [],
        )
        self.members = [dict(character_id=8)]
        self.assertEqual(
            quest.settle(
                self.db, self.store, self.character, self.fight, self.originals
            ),
            [],
        )
        self.assertEqual(self.planned, [])

    def test_live_enemy_summon_or_foreign_original_identity_reject(self):
        for mutation in ["living", "summoned", "foreign"]:
            self.fight.actors[-1].hp = 1 if mutation == "living" else 0
            self.fight.native_summon_registrations = (
                {-1: {}} if mutation == "summoned" else {}
            )
            originals = copy.deepcopy(self.originals)
            if mutation == "foreign":
                originals[0]["id"] = -88
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                quest.settle(self.db, self.store, self.character, self.fight, originals)
        self.assertEqual(self.planned, [])

    def test_public_world_victory_does_not_query_private_encounter_tables(self):
        db = SimpleNamespace(
            execute=lambda *_: self.fail("Public fight queried quest-instance tables")
        )
        self.assertEqual(
            quest.settle(
                db,
                self.store,
                dict(self.character, instance_id=0),
                self.fight,
                self.originals,
            ),
            [],
        )

    def test_legacy_followup_metadata_still_rejects_malformed_declarations(self):
        from wakfu_server.quest_instance_configuration import reviewed_reentry_quests

        for malformed in ([], [True], [2166, 2166], [2165]):
            with self.subTest(value=malformed), self.assertRaises(ValueError):
                reviewed_reentry_quests(dict(quest_id=2165, reentry_quests=malformed))

    def test_completed_parent_reentry_never_replays_objectives_rewards_or_completion(
        self,
    ):
        configuration = copy.deepcopy(self.configuration)
        selected = dict(
            self.selected,
            quest_id=2165,
            reentry_quests=[2166, 2170],
            native_entry_criterion="",
        )
        configuration["route"]["criterion"] = ""
        configuration["topology"]["owned_quest_encounter"] = selected
        self.selected = selected
        self.state.update(completed=[2165], running=[2170], objectives=[])
        before = copy.deepcopy(self.state)
        session = dict(context_policy_version=1, members=(7,), instance_id=99)
        resolved = dict(
            route=SimpleNamespace(
                key=configuration["route"]["key"], context_route_key=None
            )
        )
        with patch("wakfu_server.companions.controlled_count", return_value=0), patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=configuration,
        ), patch.object(quest, "_advance") as advance:
            quest.initialize(self.db, session, resolved, store=self.store)
            advance.assert_not_called()
        self.assertEqual(
            session["owned_quest_encounter"],
            dict(owner=7, quest_id=2165, content_only=True),
        )
        self.assertEqual(self.state, before)
        self.assertEqual(self.planned, [])

    def test_missed_optional_reentry_does_not_require_circular_running_quest(self):
        from wakfu_server.quest_instance_configuration import reviewed_pending_reentry

        selected = dict(
            self.selected,
            quest_id=2165,
            pending_reentry=dict(
                all_completed=[2166, 2170], none_completed=[1721, 1726]
            ),
        )
        state = dict(completed=[2165, 2166, 2170], running=[])
        self.assertEqual(quest.admission_phase(selected, state), "content_only")
        for completed in (
            [2166, 2170],
            [2165, 2166],
            [2165, 2166, 2170, 1721],
            [2165, 2166, 2170, 1726],
        ):
            with self.subTest(completed=completed):
                self.assertEqual(
                    quest.admission_phase(
                        selected, dict(completed=completed, running=[])
                    ),
                    "content_only",
                )
        for pending in (
            dict(all_completed=[True], none_completed=[1726]),
            dict(all_completed=[2170], none_completed=[2170]),
            dict(all_completed=[], none_completed=[1726]),
        ):
            with self.subTest(pending=pending), self.assertRaises(ValueError):
                reviewed_pending_reentry(dict(pending_reentry=pending))
