"""Paid optional resumption preserves original instance/policy/room receipts."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_reentry as resume
from wakfu_server.dungeon_instances import EntryRoute


def configuration(*, optional=False):
    policy = dict(
        id="reviewed-fixture",
        admission=dict(quest_id=2166, objective_id=4288),
        steps=[dict(id="boss-victory")],
    )
    if optional:
        policy["optional_companion"] = dict(
            path="reviewed-fixture.json", sha256="0" * 64
        )
    return dict(
        policy=policy,
        compiled_plan=dict(
            rooms=[dict(order=1, monsters=[dict(ref_id=3234, count=1)])]
        ),
        topology=dict(
            rooms=[dict(order=1, cells=[[0, 0, 0]])],
            exploration_geometry=dict(
                client_sha256="same-client", topology_sha256="same-map"
            ),
        ),
    )


class PaidStoryResumeTests(unittest.TestCase):
    def setUp(self):
        self.old, self.new = configuration(), configuration(optional=True)
        self.route = EntryRoute(
            key="fixture",
            template_id=1000887,
            definition_id=1000887,
            entry_map_id=747,
            entry_object_id=23621,
            destination_id=4029,
            start_map_id=887,
            criterion="",
            native_template_id=-1,
        )
        self.resolved = dict(
            route=self.route, native_destination=dict(cyW=1, item_reference=18747)
        )
        self.run = dict(
            instance_id=99,
            party_id=55,
            context_policy_version=1,
            live_party_revision=2,
            leader_id=None,
            dungeon_solo=True,
            template_id=1000887,
            definition_id=1000887,
            entry_map_id=747,
            entry_object_id=23621,
            entry_destination_id=4029,
            start_map_id=887,
        )
        self.current_party = None
        self.members = [dict(character_id=7, status="returned")]
        self.party_members = []
        self.entry = dict(
            payload=dict(
                schema="owned-quest-instance-v1",
                quest_id=2166,
                objective_id=4288,
                instance_id=99,
                route_key="fixture",
            )
        )
        self.witness, self.busy = dict(present=1), None
        self.eligible = True
        self.writes = []
        self.reads = []
        self.visit = None
        self.db = SimpleNamespace(execute=self.execute)
        self.store = SimpleNamespace(
            lock_character=lambda *_: None,
            character=lambda *_: dict(id=7, account_id=3, map_id=747, instance_id=0),
        )
        self.enter_context(patch.object(resume.player_parties, "_lock_members"))
        self.enter_context(
            patch.object(
                resume.storage,
                "load_locked",
                return_value=dict(completed=[2166, 2170], running=[]),
            )
        )
        self.enter_context(
            patch.object(
                resume.owned_story_controller,
                "policy",
                side_effect=lambda config: config.get("policy"),
            )
        )
        self.enter_context(
            patch.object(
                resume.owned_companion_rescue,
                "can_reenter",
                side_effect=lambda *_: self.eligible,
            )
        )
        self.enter_context(
            patch.object(
                resume.dungeon_runtime_config,
                "pinned_configuration",
                return_value=self.old,
            )
        )

    def enter_context(self, manager):
        manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)

    def execute(self, sql, args):
        if sql.startswith("SELECT"):
            self.reads.append((sql, args))
        if sql.startswith(("UPDATE", "INSERT")):
            self.writes.append((sql, args))
            return SimpleNamespace(rowcount=1)
        if sql.startswith("SELECT party_id"):
            row = self.current_party
        elif sql.startswith("SELECT i.*"):
            row = self.run
        elif sql.startswith("SELECT character_id,status"):
            return SimpleNamespace(fetchall=lambda: self.members)
        elif sql.startswith("SELECT character_id FROM player_party_members"):
            return SimpleNamespace(fetchall=lambda: self.party_members)
        elif sql.startswith("SELECT payload"):
            row = self.visit if args[1].endswith(":arrived") else self.entry
        elif sql.startswith("SELECT 1 FROM dungeon_transition_outbox"):
            row = self.witness
        elif sql.startswith("SELECT 1 FROM combat_fights"):
            row = self.busy
        else:
            raise AssertionError(sql)
        return SimpleNamespace(fetchone=lambda: row)

    def prepare(self):
        return resume.prepare(
            self.db, self.store, 3, "current-generation", 7, self.resolved, self.new
        )

    def test_real_paid_owner_can_restore_same_run_without_optional_already_running_or_repin(
        self,
    ):
        self.assertEqual(self.prepare(), 99)
        self.assertEqual(len(self.writes), 4)
        sql = " ".join(q for q, _ in self.writes)
        self.assertNotIn("context_policy_version=", sql)
        self.assertNotIn("dungeon_room_runs", sql)
        self.assertNotIn("achievement", sql)
        self.assertNotIn("inventory", sql)
        self.assertIn(
            (
                "UPDATE dungeon_instance_members SET session_generation=%s,party_revision=%s WHERE instance_id=%s AND character_id=%s",
                ("current-generation", 3, 99, 7),
            ),
            self.writes,
        )

    def _prepare_narrative_fixture(self, objective_id=4288):
        policy = dict(
            id="reviewed-fixture",
            map_id=887,
            maximum_members=1,
            admission=dict(quest_id=2166, objective_id=objective_id),
            steps=[
                dict(
                    id="arrived",
                    kind="world_ready",
                    reference=887,
                    requires=[],
                    effects=[],
                    evidence="The original paid route entered this narrative map.",
                )
            ],
        )
        self.old = dict(
            policy=deepcopy(policy),
            compiled_plan={"rooms": []},
            topology=dict(
                policy="owned-story-narrative-v1",
                rooms=[],
                exploration_geometry=dict(
                    client_sha256="same-client", topology_sha256="same-map"
                ),
            ),
        )
        self.new = deepcopy(self.old)
        resume.dungeon_runtime_config.pinned_configuration.return_value = self.old
        self.visit = dict(
            payload=dict(
                schema=resume.owned_story_controller.SCHEMA,
                profile_sha256=resume.owned_story_controller._digest(policy),
                owner=7,
                instance_id=99,
                step="arrived",
            )
        )

    def test_paid_narrative_resume_requires_actual_world_ready_receipt_without_room_run(
        self,
    ):
        self._prepare_narrative_fixture()
        self.assertEqual(self.prepare(), 99)
        sql = " ".join(query for query, _ in self.reads)
        self.assertNotIn("JOIN dungeon_room_runs r USING(instance_id)", sql)
        self.assertIn("NOT EXISTS (SELECT 1 FROM dungeon_room_runs", sql)
        self.assertIn(
            (
                "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (7, "owned-story:reviewed-fixture:99:arrived"),
            ),
            self.reads,
        )
        self.assertFalse(
            any(
                "inventory" in query.lower() or "achievement" in query.lower()
                for query, _ in self.writes
            )
        )

        self.writes.clear()
        self.visit = None
        self.assertIsNone(self.prepare())
        self.assertEqual(self.writes, [])

    def test_roomless_no_objective_reuses_real_visit_without_nonexistent_entry_receipt(
        self,
    ):
        self._prepare_narrative_fixture(objective_id=None)
        self.entry = None
        evidence = dict(
            map_id=887,
            instance_id=99,
            route_key="fixture",
            policy_version=1,
            entry_map_id=747,
            source_id=23621,
            destination_id=4029,
        )
        self.visit["payload"]["evidence"] = deepcopy(evidence)
        self.assertEqual(self.prepare(), 99)
        self.assertEqual(len(self.writes), 4)
        self.assertFalse(any("inventory" in sql.lower() for sql, _ in self.writes))
        self.writes.clear()
        for key in evidence:
            with self.subTest(changed_evidence=key):
                self.visit["payload"]["evidence"] = deepcopy(evidence)
                del self.visit["payload"]["evidence"][key]
                self.assertIsNone(self.prepare())
                self.assertEqual(self.writes, [])
        self.visit["payload"]["evidence"] = deepcopy(evidence)
        self.witness = None
        self.assertIsNone(self.prepare())
        self.assertEqual(self.writes, [])

    def test_missing_paid_witness_foreign_group_live_fight_or_changed_mechanics_never_mutate(
        self,
    ):
        for case in (
            "receipt",
            "transition",
            "group",
            "member",
            "fight",
            "mechanics",
            "eligibility",
        ):
            entry, witness, busy, current, members, eligible = deepcopy(
                (
                    self.entry,
                    self.witness,
                    self.busy,
                    self.current_party,
                    self.members,
                    self.eligible,
                )
            )
            original = deepcopy(self.new)
            if case == "receipt":
                self.entry = None
            elif case == "transition":
                self.witness = None
            elif case == "group":
                self.current_party = dict(party_id=999)
            elif case == "member":
                self.members.append(dict(character_id=8, status="returned"))
            elif case == "fight":
                self.busy = dict(present=1)
            elif case == "mechanics":
                self.new["topology"]["rooms"][0]["cells"].append([1, 0, 0])
            else:
                self.eligible = False
            with self.subTest(case=case):
                self.assertIsNone(self.prepare())
                self.assertEqual(self.writes, [])
            (
                self.entry,
                self.witness,
                self.busy,
                self.current_party,
                self.members,
                self.eligible,
            ) = (entry, witness, busy, current, members, eligible)
            self.new = original
