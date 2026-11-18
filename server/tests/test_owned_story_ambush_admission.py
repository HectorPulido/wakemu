"""One-use tickets retain only reviewed owned-room ambush starting poses."""

from copy import deepcopy
from contextlib import contextmanager
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_ambush_admission as admission
from wakfu_server import owned_story_auto_start


class OwnedStoryAmbushAdmissionTests(unittest.TestCase):
    def setUp(self):
        # Reuse the pinned School configuration, exact native formation and
        # readiness receipt exercised by the existing auto-start fixture.
        from test_owned_story_auto_start import Cursor, OwnedStoryAutoStartTests

        self.base = OwnedStoryAutoStartTests(
            "test_loaded_sole_owner_queues_only_the_durable_native_group"
        )
        self.base.setUp()
        self.session = self.base.session
        self.state = self.base.state
        self.store = self.base.store
        self.configuration = self.base.configuration
        self.selected = self.base.selected
        self.group = dict(self.base.group, key=(1030, 501, 701))
        self.cursor_type = Cursor
        self.state.selected_group = self.group
        self.state.body = b""
        self.state.connection = SimpleNamespace(
            owned_story_auto_frontier=("huppermage-platform-1030", 1)
        )

    def _queue(self):
        with patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=self.configuration,
        ):
            self.assertTrue(
                owned_story_auto_start.queue(
                    self.session, self.group, configuration=self.configuration
                )
            )
        self.state.body = self.state.pending_guardian_attack
        return self.state.owned_story_ambush_admission

    def _consume(self):
        original_execute = self.base.db.execute

        def execute(query, params=None):
            if (
                "SELECT r.group_id,r.asset_map_id,r.room_order,g.members,g.status"
                in query
            ):
                return self.cursor_type(dict(self.base.durable_group, room_order=1))
            return original_execute(query, params)

        with patch.object(self.base.db, "execute", side_effect=execute), patch(
            "wakfu_server.owned_story_controller.recognizes_instance",
            return_value=True,
        ), patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, self.configuration),
        ), patch(
            "wakfu_server.owned_story_controller._scope",
            return_value=(self.selected, {"platform-ready"}),
        ):
            return admission.consume(self.session)

    def test_ticket_requires_exact_owner_pose_group_readiness_and_is_one_use(self):
        ticket = self._queue()
        self.assertEqual(ticket["owner"], 81)
        self.assertEqual(ticket["generation"], "generation-1")
        self.group["members"] = tuple(dict(row) for row in self.base.group_members)
        self.assertTrue(self._consume())
        self.assertIsNone(self.state.owned_story_ambush_admission)
        self.assertIsNone(self.state.connection.owned_story_auto_frontier)
        with self.assertRaisesRegex(ValueError, "issued native group"):
            self._consume()

        # An actual change to one tuple member still fails the durable list
        # comparison, even though list/tuple container shapes are compatible.
        self.state.pending_guardian_attack = None
        self.state.owned_story_ambush_admission = None
        self.state.body = b""
        self.group["members"] = tuple(dict(row) for row in self.base.group_members)
        self._queue()
        changed = [dict(row) for row in self.base.group_members]
        changed[1]["id"] -= 1
        self.group["members"] = tuple(changed)
        with self.assertRaisesRegex(ValueError, "issued native group"):
            self._consume()

        # Reissue a legitimate ticket for each adversarial mutation. A mismatch
        # must fail before the combat approach exception is waived.
        self.group["members"] = tuple(dict(row) for row in self.base.group_members)
        mutations = (
            lambda value: value.update(account_id=20),
            lambda value: value.update(generation="stale-generation"),
            lambda value: value.update(owner=82),
            lambda value: value.update(profile_sha256="0" * 64),
            lambda value: value["pose"].update(x=127),
            lambda value: value.update(attack_body=b"forged"),
            lambda value: value.update(room_order=2),
            lambda value: value.update(group_id=702),
            lambda value: value.update(ready_steps=("missing-step",)),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.state.pending_guardian_attack = None
                self.state.owned_story_ambush_admission = None
                self.state.body = b""
                self._queue()
                changed = deepcopy(self.state.owned_story_ambush_admission)
                mutate(changed)
                self.state.owned_story_ambush_admission = changed
                with self.assertRaises(ValueError):
                    self._consume()
                self.assertIsNone(self.state.owned_story_ambush_admission)

    def test_issue_rejects_unowned_or_forged_server_queue_body(self):
        self._queue()
        ticket = self.state.owned_story_ambush_admission
        self.state.owned_story_ambush_admission = None
        self.state.pending_guardian_attack = b"different"
        with self.assertRaisesRegex(ValueError, "authenticated selected session"):
            admission.issue(
                self.state,
                self.selected,
                owned_story_auto_start.requirements(self.selected, 1),
                self.group,
                ticket["attack_body"],
            )

    def test_rejected_genuine_ticket_clears_cached_frontier_for_a_fresh_room_check(
        self,
    ):
        self._queue()
        self.state.connection.owned_story_auto_frontier = (
            "huppermage-platform-1030",
            1,
            (1,),
        )
        # Keep the authentic one-use ticket but move away from its issued pose.
        self.state.character["x"] = 127
        with self.assertRaisesRegex(ValueError, "issued native group"):
            self._consume()
        self.assertIsNone(self.state.owned_story_ambush_admission)
        self.assertIsNone(self.state.connection.owned_story_auto_frontier)

    def test_public_or_unmarked_attack_keeps_the_normal_approach_path(self):
        # Public attacks are never eligible for this owner-only waiver.
        self.state.character["instance_id"] = 0
        self.state.owned_story_ambush_admission = None
        self.state.pending_guardian_attack = None
        self.assertFalse(admission.consume(self.session))
        self.state.character["instance_id"] = 501
        with patch(
            "wakfu_server.owned_story_controller.recognizes_instance",
            return_value=False,
        ):
            self.assertFalse(admission.consume(self.session))

        from wakfu_server.application.session_combat_admission import (
            CombatAdmissionMixin,
        )
        from wakfu_server.application.dispatch_result import DispatchResult

        class Harness(CombatAdmissionMixin):
            def __init__(self, state, runtime):
                self.state, self.runtime = state, runtime
                self.approach_calls = 0

            def approach_actor(self, *_args, **_kwargs):
                self.approach_calls += 1
                return True

        @contextmanager
        def lock():
            yield

        state = SimpleNamespace(
            loaded=True,
            rift_start_run=None,
            encounter_world_action=None,
            body=struct.pack(">qiihB", -99001, 124, -15, 0, 0),
            fight=None,
            bag_session=None,
            ranch_session=None,
            spectator_session=None,
            combat_session=None,
            group_lease=None,
            durable_fight_id=None,
            character=dict(self.base.character, instance_id=0),
            account_id=19,
            generation="generation-1",
            pending_guardian_attack=None,
            selected_group=None,
            connection=SimpleNamespace(owned_story_auto_frontier=None),
        )
        runtime = SimpleNamespace(
            PLANTINGS=SimpleNamespace(cancel=lambda *_args: None),
            HARVESTS=SimpleNamespace(cancel=lambda *_args, **_kwargs: None),
            COMBAT_GROUPS=SimpleNamespace(lock=lock()),
            combat_group_for_target=lambda *_args: self.group,
            COMBAT_TEST=False,
            DUNGEON_ROOM_RUNTIME_AVAILABLE=False,
            record=lambda **_kwargs: None,
            STORE=self.store,
        )
        harness = Harness(state, runtime)
        with patch(
            "wakfu_server.combat_terrain.map_geometry", return_value=object()
        ), patch(
            "wakfu_server.combat_geometry.prepare_geometry", return_value=object()
        ), patch(
            "wakfu_server.actor_approach.combat_approach",
            return_value=(frozenset(), frozenset()),
        ), patch(
            "wakfu_server.owned_story_ambush_admission.consume", return_value=False
        ):
            result = harness.handle_encounter_start()
        self.assertEqual(result, DispatchResult.CONTINUE)
        self.assertEqual(harness.approach_calls, 1)

    def test_only_a_consumed_native_ticket_skips_the_ordinary_approach_branch(self):
        from wakfu_server.application.session_combat_admission import (
            CombatAdmissionMixin,
        )

        class AfterAdmission(BaseException):
            pass

        class Harness(CombatAdmissionMixin):
            def __init__(self, state, runtime):
                self.state, self.runtime = state, runtime
                self.approach_calls = 0

            def approach_actor(self, *_args, **_kwargs):
                self.approach_calls += 1
                return True

        @contextmanager
        def lock():
            yield

        state = SimpleNamespace(
            loaded=True,
            rift_start_run=None,
            encounter_world_action=None,
            body=b"",
            fight=None,
            bag_session=None,
            ranch_session=None,
            spectator_session=None,
            combat_session=None,
            group_lease=None,
            durable_fight_id=None,
            character=dict(self.base.character),
            account_id=19,
            generation="generation-1",
            pending_guardian_attack=None,
            selected_group=None,
            connection=SimpleNamespace(owned_story_auto_frontier=None),
        )
        runtime = SimpleNamespace(
            PLANTINGS=SimpleNamespace(cancel=lambda *_args: None),
            HARVESTS=SimpleNamespace(cancel=lambda *_args, **_kwargs: None),
            COMBAT_GROUPS=SimpleNamespace(lock=lock()),
            combat_group_for_target=lambda *_args: self.group,
            COMBAT_TEST=False,
            record=lambda **_kwargs: None,
            STORE=self.store,
        )
        harness = Harness(state, runtime)
        session = SimpleNamespace(state=state, runtime=runtime)
        with patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=self.configuration,
        ):
            self.assertTrue(
                owned_story_auto_start.queue(
                    session, self.group, configuration=self.configuration
                )
            )
        state.body = state.pending_guardian_attack

        original_execute = self.base.db.execute

        def execute(query, params=None):
            if (
                "SELECT r.group_id,r.asset_map_id,r.room_order,g.members,g.status"
                in query
            ):
                return self.cursor_type(dict(self.base.durable_group, room_order=1))
            return original_execute(query, params)

        with patch.object(self.base.db, "execute", side_effect=execute), patch(
            "wakfu_server.owned_story_controller.recognizes_instance",
            return_value=True,
        ), patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, self.configuration),
        ), patch(
            "wakfu_server.owned_story_controller._scope",
            return_value=(self.selected, {"platform-ready"}),
        ), patch(
            "wakfu_server.achievements.source_quest_encounters.candidate_monsters",
            side_effect=AfterAdmission,
        ):
            with self.assertRaises(AfterAdmission):
                harness.handle_encounter_start()
        self.assertIsNone(state.owned_story_ambush_admission)
        self.assertEqual(harness.approach_calls, 0)


if __name__ == "__main__":
    unittest.main()
