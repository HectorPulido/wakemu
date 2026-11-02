"""Focused semantic checks for the private ordinary-phase read pass."""
from types import SimpleNamespace
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_combat_ordinary_events as ordinary_fixture
from wakfu_server import combat_ordinary_events
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections


class PhaseReadPassSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ordinary_fixture.OrdinaryHealingEventTests.setUpClass()

    def fixture(self):
        case = ordinary_fixture.OrdinaryHealingEventTests()
        case.setUp()
        case.retention = case.f.retention
        case.replay = case.f.replay
        initialize_global_pv_collections(case.fight, tuple(case.fight.actors))
        return case

    def test_custom_replay_and_adapter_gates_do_not_read_custom_properties(self):
        case = self.fixture()
        replay_reads = []

        class CustomReplay:
            @property
            def _read_pass(self):
                replay_reads.append("read_pass")
                raise AssertionError("custom replay getter must not be read")

        case.events.replay = CustomReplay()
        with combat_ordinary_events._phase_read_pass(case.events, case.inv):
            pass
        self.assertEqual(replay_reads, [])

        adapter_reads = []

        class CustomAdapter:
            @property
            def actor_authority(self):
                adapter_reads.append("actor_authority")
                raise AssertionError("custom adapter getter must not be read")

        case.events.replay = case.f.replay
        case.events.adapter = CustomAdapter()
        with combat_ordinary_events._phase_read_pass(case.events, case.inv):
            pass
        self.assertEqual(adapter_reads, [])
        self.assertIsNone(case.f.replay._read_pass)

    def test_nested_phase_pass_invalidates_inner_view_and_restores_outer_scope(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        helper = combat_ordinary_events._phase_read_pass
        source = case.f.source()
        with patch.object(case.retention, "view", wraps=case.retention.view) as view:
            with helper(case.events, case.inv):
                outer = case.replay._read_pass
                self.assertIs(outer["ordinary_phase_owner"], case.events)
                case.replay(source, authority=case.f.authority)
                self.assertIsNotNone(outer["view"])
                with helper(case.events, case.inv):
                    inner = case.replay._read_pass
                    self.assertIsNot(inner, outer)
                    self.assertIs(inner["ordinary_phase_owner"], case.events)
                    case.replay(source, authority=case.f.authority)
                self.assertIs(case.replay._read_pass, outer)
                self.assertIsNone(outer["view"])
                case.replay(source, authority=case.f.authority)
                self.assertIsNotNone(outer["view"])
            self.assertEqual(view.call_count, 3)
        self.assertIsNone(case.replay._read_pass)

    def test_nested_custom_adapter_fallback_cannot_borrow_owned_outer_view(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        helper = combat_ordinary_events._phase_read_pass
        source = case.f.source()
        with patch.object(case.retention, "view", wraps=case.retention.view) as view:
            with helper(case.events, case.inv):
                case.replay(source, authority=case.f.authority)
                outer = case.replay._read_pass
                self.assertIsNotNone(outer["view"])
                before = view.call_count
                authority = case.adapter.actor_authority
                case.events.adapter = SimpleNamespace(
                    actor_authority=authority, cast=case.adapter.cast
                )
                case.events.phase(case.effect, case.inv, uid=801, value=1, channel=3)
                self.assertGreater(view.call_count, before)
                self.assertIsNone(outer["view"])
                self.assertIs(case.replay._read_pass, outer)
        self.assertIsNone(case.replay._read_pass)

    def test_custom_fallback_exception_restores_outer_scope_but_clears_snapshot(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        source = case.f.source()
        with combat_ordinary_events._phase_read_pass(case.events, case.inv):
            case.replay(source, authority=case.f.authority)
            outer = case.replay._read_pass
            self.assertIsNotNone(outer["view"])
            case.events.adapter = SimpleNamespace(
                actor_authority=case.adapter.actor_authority, cast=case.adapter.cast
            )
            with patch.object(
                type(case.replay),
                "__call__",
                side_effect=RuntimeError("fallback failure"),
            ), self.assertRaisesRegex(RuntimeError, "fallback failure"):
                case.events.phase(case.effect, case.inv, uid=802, value=1, channel=3)
            self.assertIs(case.replay._read_pass, outer)
            self.assertIsNone(outer["view"])
        self.assertIsNone(case.replay._read_pass)

    def test_actual_phase_reuses_adjacent_empty_scans_then_clears_scope(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        with patch.object(case.retention, "view", wraps=case.retention.view) as view:
            case.events.phase(case.effect, case.inv, uid=800, value=1, channel=3)
        self.assertEqual(view.call_count, 1)
        self.assertIsNone(case.replay._read_pass)

    def test_q_q_callback_mutation_is_outside_any_retained_read_view(self):
        case = self.fixture()
        row = dict(uid=901, reference=111, cell=(2, 3, 0), native_removal_masks=[])
        manager = SimpleNamespace(
            id=901,
            position=row["cell"],
            native_is_area=True,
            native_running_effect_manager=False,
            native_entry_masks=frozenset(),
        )
        observed = []

        def running_source(*args, **kwargs):
            self.assertEqual(kwargs["qf_delivered"], True)
            self.assertIsNone(case.replay._read_pass)
            observed.append(True)
            outer = case.replay._read_pass
            with combat_ordinary_events._phase_read_pass(case.events, case.inv):
                nested = case.replay._read_pass
                self.assertIsNot(nested, outer)
                case.replay(
                    replace(case.f.source(), event_ids=()), authority=case.f.authority
                )
                nested["view"] = {"qf_mutation_probe": True}
            self.assertIs(case.replay._read_pass, outer)
            self.assertIsNone(outer)
            case.fight.native_effect_areas.pop(901, None)
            return ()

        case.retention.area_events = SimpleNamespace(running_source=running_source)
        invocation = EffectInvocation(
            case.inv.reference, 1, case.inv.caster_id, 901, (2, 3, 0)
        )
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            side_effect=lambda fight, identity: manager if identity == 901 else None,
        ), patch(
            "wakfu_server.combat_state_managers.retained_area_pv_row",
            side_effect=lambda fight, identity: row if identity == 901 else None,
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"111": {"exit_masks": []}},
        ):
            case.fight.native_effect_areas = {901: row}
            case.events.phase(case.effect, invocation, uid=800, value=1, channel=1)
        self.assertEqual(observed, [True])
        self.assertNotIn(901, case.fight.native_effect_areas)
        self.assertIsNone(case.replay._read_pass)

    def test_function_forwarder_suspends_owned_parent_and_restores_after_error(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        source = replace(case.f.source(), channel=31)
        helper = combat_ordinary_events._phase_read_pass
        opaque_reads = []

        class OpaqueEvents:
            @property
            def replay(self):
                opaque_reads.append("replay")
                raise AssertionError("fallback must not inspect replay")

            @property
            def __dict__(self):
                opaque_reads.append("dict")
                raise AssertionError("fallback must not inspect __dict__")

        with patch.object(case.retention, "view", wraps=case.retention.view) as view:
            with helper(case.events, case.inv):
                case.replay(source, authority=case.f.authority)
                parent = case.replay._read_pass
                self.assertIsNotNone(parent["view"])
                before = view.call_count

                # PaidSpellCostEvents stores this shape: an ordinary function
                # forwarding to the same replay, rather than a replay object.
                forwarder = lambda item, **kw: case.replay(
                    item, authority=case.f.authority
                )
                forwarding_events = SimpleNamespace(replay=forwarder)
                with helper(forwarding_events, case.inv):
                    forwarder(source)
                self.assertEqual(view.call_count, before + 1)
                self.assertIs(case.replay._read_pass, parent)
                self.assertIsNone(parent["view"])

                with helper(OpaqueEvents(), case.inv):
                    with self.assertRaisesRegex(RuntimeError, "fallback boom"):
                        raise RuntimeError("fallback boom")
                self.assertIs(case.replay._read_pass, parent)
                self.assertIsNone(parent["view"])
        self.assertEqual(opaque_reads, [])
        self.assertIsNone(case.replay._read_pass)
        self.assertEqual(combat_ordinary_events._PHASE_READ_SCOPES.get(), ())

    def test_nested_same_and_different_replay_scopes_restore_context_tokens(self):
        outer = self.fixture()
        inner = self.fixture()
        helper = combat_ordinary_events._phase_read_pass
        with helper(outer.events, outer.inv):
            outer_scope = combat_ordinary_events._PHASE_READ_SCOPES.get()
            self.assertEqual(len(outer_scope), 1)
            with helper(outer.events, outer.inv):
                self.assertEqual(
                    len(combat_ordinary_events._PHASE_READ_SCOPES.get()), 2
                )
            self.assertEqual(
                combat_ordinary_events._PHASE_READ_SCOPES.get(), outer_scope
            )
            with helper(inner.events, inner.inv):
                scopes = combat_ordinary_events._PHASE_READ_SCOPES.get()
                self.assertEqual(len(scopes), 2)
                self.assertIs(scopes[0][0], outer.replay)
                self.assertIs(scopes[1][0], inner.replay)
            self.assertEqual(
                combat_ordinary_events._PHASE_READ_SCOPES.get(), outer_scope
            )
        self.assertEqual(combat_ordinary_events._PHASE_READ_SCOPES.get(), ())
        self.assertIsNone(outer.replay._read_pass)
        self.assertIsNone(inner.replay._read_pass)

    def test_actual_phase_local_callback_subscription_is_seen_by_global_scan(self):
        case = self.fixture()
        source = case.f.source()
        definition = case.retention.metadata["effects"]["308265"]
        definition["event_global_subscription"] = True
        initial = case.fight.native_owned_group_effects[900]
        initial["native_subscription_masks"] = [None] * 7
        initial["native_subscription_masks"] = [list(source.event_ids)] * 7
        activations = []
        created = []
        original = case.f.dispatcher.execute_activation

        def activation(invocation, **kwargs):
            activations.append(invocation.target_id)
            if invocation.target_id == 7 and not created:
                case.f.dispatcher.execute(
                    EffectInvocation(308265, 1, -7, -7, (1, 0, 0))
                )
                added = max(case.fight.native_owned_group_effects)
                case.fight.native_owned_group_effects[added][
                    "native_subscription_masks"
                ] = [list(source.event_ids)] * 7
                created.append(added)
            return original(invocation, **kwargs)

        case.f.dispatcher.execute_activation = activation
        case.events.phase(case.effect, case.inv, uid=800, value=1, channel=3)
        self.assertTrue(created)
        # The caster's local scan runs before the final global iterator; the
        # newly registered -7 listener is therefore visible in that same phase.
        self.assertIn(-7, activations)
        # Its one-shot group is retired after the actual global activation.
        self.assertNotIn(created[0], case.fight.native_owned_group_effects)
        self.assertIsNone(case.replay._read_pass)

    def test_actual_phase_local_callback_removal_is_seen_by_global_scan(self):
        case = self.fixture()
        source = case.f.source()
        initial = case.fight.native_owned_group_effects[900]
        initial["native_subscription_masks"] = [list(source.event_ids)] * 7
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        activations = []
        original = case.f.dispatcher.execute_activation

        def activation(invocation, **kwargs):
            activations.append(invocation.target_id)
            if (
                invocation.target_id == 7
                and 900 in case.fight.native_owned_group_effects
            ):
                case.retention.removal(case.retention.view()).remove((900,))
                return False
            return original(invocation, **kwargs)

        case.f.dispatcher.execute_activation = activation
        case.events.phase(case.effect, case.inv, uid=800, value=1, channel=3)
        self.assertEqual(activations, [7])
        self.assertNotIn(900, case.fight.native_owned_group_effects)
        self.assertIsNone(case.replay._read_pass)


if __name__ == "__main__":
    unittest.main()
