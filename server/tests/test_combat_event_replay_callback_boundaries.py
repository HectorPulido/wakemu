"""Callback mutations must not reuse stale retained-event snapshots."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_combat_event_replay_read_pass import EventReplayReadPassTests
from test_combat_ordinary_phase_read_pass import PhaseReadPassSemanticTests
from wakfu_server import combat_event_replay
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime


class EventReplayCallbackBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        EventReplayReadPassTests.setUpClass()
        PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        return EventReplayReadPassTests().fixture()

    def test_no_read_pass_control_observes_real_registered_listener(self):
        case = self.fixture()
        source = replace(case.source(), channel=31)
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        row = case.fight.native_owned_group_effects[900]
        row["native_subscription_masks"] = [None] * 7
        row["native_subscription_masks"][3] = list(source.event_ids)
        callbacks = []
        created = []

        def activation(invocation, **kwargs):
            callbacks.append(invocation.target_id)
            if invocation.target_id == 7 and not created:
                case.replay(
                    replace(source, event_ids=(), manager_actor_id=-7),
                    authority=case.authority,
                )
                case.dispatcher.execute(EffectInvocation(308265, 1, -7, -7, (1, 0, 0)))
                added = max(case.fight.native_owned_group_effects)
                case.fight.native_owned_group_effects[added][
                    "native_subscription_masks"
                ] = [None] * 7
                case.fight.native_owned_group_effects[added][
                    "native_subscription_masks"
                ][3] = list(source.event_ids)
                created.append(added)
            return False

        case.dispatcher.execute_activation = activation
        event = replace(source, manager_actor_id=-7)
        case.replay(event, authority=case.authority)
        case.replay(source, authority=case.authority)
        case.replay(event, authority=case.authority)
        self.assertTrue(created)
        self.assertIn(created[0], case.fight.native_owned_group_effects)
        self.assertIn(-7, callbacks)

    def test_read_pass_observes_listener_registered_after_nested_empty_replay(self):
        case = self.fixture()
        source = replace(case.source(), channel=31)
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        row = case.fight.native_owned_group_effects[900]
        row["native_subscription_masks"] = [None] * 7
        row["native_subscription_masks"][3] = list(source.event_ids)
        callbacks = []
        created = []

        def activation(invocation, **kwargs):
            self.assertIsNone(case.replay._read_pass)
            callbacks.append(invocation.target_id)
            if invocation.target_id == 7 and not created:
                case.replay(
                    replace(source, event_ids=(), manager_actor_id=-7),
                    authority=case.authority,
                )
                case.dispatcher.execute(EffectInvocation(308265, 1, -7, -7, (1, 0, 0)))
                added = max(case.fight.native_owned_group_effects)
                case.fight.native_owned_group_effects[added][
                    "native_subscription_masks"
                ] = [None] * 7
                case.fight.native_owned_group_effects[added][
                    "native_subscription_masks"
                ][3] = list(source.event_ids)
                created.append(added)
            return False

        case.dispatcher.execute_activation = activation
        with case.replay.read_pass():
            case.replay(replace(source, manager_actor_id=-7), authority=case.authority)
            case.replay(source, authority=case.authority)
            case.replay(replace(source, manager_actor_id=-7), authority=case.authority)
            self.assertTrue(created)
            self.assertIn(-7, callbacks)
        self.assertIsNone(case.replay._read_pass)

    def test_callback_exception_restores_parent_scope_cleared(self):
        case = self.fixture()
        source = replace(case.source(), channel=31)
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        row = case.fight.native_owned_group_effects[900]
        row["native_subscription_masks"] = [None] * 7
        row["native_subscription_masks"][3] = list(source.event_ids)
        callbacks = []

        def fail_activation(invocation, **kwargs):
            callbacks.append((invocation.base_uid, invocation.target_id))
            self.assertIsNone(case.replay._read_pass)
            case.replay(
                replace(source, event_ids=(), manager_actor_id=-7),
                authority=case.authority,
            )
            raise RuntimeError("activation callback failure")

        case.dispatcher.execute_activation = fail_activation
        with case.replay.read_pass():
            parent = case.replay._read_pass
            case.replay(replace(source, manager_actor_id=-7), authority=case.authority)
            with self.assertRaisesRegex(RuntimeError, "activation callback failure"):
                case.replay(source, authority=case.authority)
            self.assertIs(case.replay._read_pass, parent)
            self.assertIsNone(parent["view"])
        self.assertTrue(callbacks)
        self.assertEqual(callbacks[0][0], 900)
        self.assertIsNone(case.replay._read_pass)

    def test_callback_removal_is_visible_to_later_replay(self):
        case = self.fixture()
        source = replace(case.source(), channel=31)
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        row = case.fight.native_owned_group_effects[900]
        row["native_subscription_masks"] = [None] * 7
        row["native_subscription_masks"][3] = list(source.event_ids)
        callbacks = []

        def remove_inside_activation(invocation, **kwargs):
            callbacks.append((invocation.base_uid, invocation.target_id))
            case.replay(
                replace(source, event_ids=(), manager_actor_id=-7),
                authority=case.authority,
            )
            case.retention.remove_group(900)
            return False

        case.dispatcher.execute_activation = remove_inside_activation
        with case.replay.read_pass():
            case.replay(replace(source, manager_actor_id=-7), authority=case.authority)
            case.replay(source, authority=case.authority)
            self.assertNotIn(900, case.fight.native_owned_group_effects)
            case.replay(source, authority=case.authority)
        self.assertTrue(callbacks)
        self.assertEqual(callbacks[0][0], 900)
        self.assertIsNone(case.replay._read_pass)

    def test_same_fight_replay_suspends_parent_but_unrelated_fight_pass_survives(self):
        first = self.fixture()
        other = self.fixture()
        second_retention = NativeRetainedRuntime(
            first.fight,
            [],
            plan=first.retention.plan,
            state_catalog=first.retention.states,
            action_id=first.retention.action_id,
            timing=first.retention.timing,
            metadata=first.retention.metadata,
        )
        second = combat_event_replay.NativeEventReplay(
            first.dispatcher, second_retention
        )
        with first.replay.read_pass(), other.replay.read_pass():
            first_scope = first.replay._read_pass
            other_scope = other.replay._read_pass
            first_view = first.replay._current_view()
            other_view = other.replay._current_view()
            with second._callback_read_boundary(None):
                self.assertIsNone(first.replay._read_pass)
                self.assertIsNone(first_scope["view"])
                self.assertIs(other.replay._read_pass, other_scope)
                self.assertIs(other_scope["view"], other_view)
                with first.replay.read_pass():
                    self.assertIsNot(first.replay._read_pass, first_scope)
                    first.replay._current_view()
                self.assertIsNone(first.replay._read_pass)
            self.assertIs(first.replay._read_pass, first_scope)
            self.assertIsNone(first_scope["view"])
            self.assertIs(other.replay._read_pass, other_scope)
            self.assertIs(other_scope["view"], other_view)
        self.assertIsNone(first.replay._read_pass)
        self.assertIsNone(other.replay._read_pass)

    def test_copied_context_cannot_revive_closed_read_pass(self):
        from contextvars import copy_context

        first = self.fixture()
        same_fight_retention = NativeRetainedRuntime(
            first.fight,
            [],
            plan=first.retention.plan,
            state_catalog=first.retention.states,
            action_id=first.retention.action_id,
            timing=first.retention.timing,
            metadata=first.retention.metadata,
        )
        callback_replay = combat_event_replay.NativeEventReplay(
            first.dispatcher, same_fight_retention
        )
        with first.replay.read_pass():
            scope = first.replay._read_pass
            first.replay._current_view()
            copied = copy_context()
        self.assertIsNone(first.replay._read_pass)

        def after_exit():
            with callback_replay._callback_read_boundary(None):
                self.assertIsNone(first.replay._read_pass)

        copied.run(after_exit)
        self.assertIsNone(first.replay._read_pass)
        self.assertIsNone(scope["view"])

    def test_q_q_running_source_registration_matches_uncached_control(self):
        def exercise(cached):
            case = PhaseReadPassSemanticTests().fixture()
            fixture = case.f
            if not cached:
                case.events.replay = lambda source, **kwargs: fixture.replay(
                    source, **kwargs
                )
            groups = case.fight.native_owned_group_effects
            for row in groups.values():
                row["native_subscription_masks"] = [None] * 7
            fixture.retention.metadata["effects"]["308265"][
                "event_global_subscription"
            ] = True
            audit = []
            fixture.dispatcher.execute_activation = (
                lambda invocation, **kwargs: audit.append(invocation.target_id) or False
            )
            area_row = dict(
                uid=901, reference=111, cell=(2, 3, 0), native_removal_masks=[]
            )
            manager = SimpleNamespace(
                id=901,
                position=area_row["cell"],
                native_is_area=True,
                native_running_effect_manager=False,
                native_entry_masks=frozenset(),
            )

            def running_source(*args, **kwargs):
                empty = replace(
                    fixture.source(),
                    manager_actor_id=-7,
                    event_ids=(),
                    channel=31,
                )
                fixture.replay(empty, authority=fixture.authority)
                fixture.dispatcher.execute(
                    EffectInvocation(308265, 1, -7, -7, (1, 0, 0))
                )
                identity = max(groups)
                groups[identity]["native_subscription_masks"] = [None] * 7
                groups[identity]["native_subscription_masks"][3] = [1]
                fixture.replay(
                    replace(
                        fixture.source(),
                        manager_actor_id=-7,
                        event_ids=(1,),
                        channel=31,
                    ),
                    authority=fixture.authority,
                )
                case.fight.native_effect_areas.pop(901, None)
                return ()

            case.retention.area_events = SimpleNamespace(running_source=running_source)
            invocation = EffectInvocation(
                case.inv.reference, 1, case.inv.caster_id, 901, (2, 3, 0)
            )
            with (
                patch(
                    "wakfu_server.combat_state_managers.registered_area_pv",
                    side_effect=lambda fight, identity: manager
                    if identity == 901
                    else None,
                ),
                patch(
                    "wakfu_server.combat_state_managers.retained_area_pv_row",
                    side_effect=lambda fight, identity: area_row
                    if identity == 901
                    else None,
                ),
                patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value={"111": {"exit_masks": []}},
                ),
            ):
                case.fight.native_effect_areas = {901: area_row}
                case.events.phase(case.effect, invocation, uid=800, value=1, channel=1)
            return audit

        uncached = exercise(False)
        cached = exercise(True)
        self.assertIn(-7, uncached)
        self.assertEqual(cached, uncached)


if __name__ == "__main__":
    unittest.main()
