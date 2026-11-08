"""Isolated candidate semantics; imported through production wakfu_server paths."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_structural_qf_scope as scope
from wakfu_server import combat_retained_runtime as retained
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeCloneAuthority
import test_combat_event_replay as fixture


class StructuralIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NativeEventReplayTests.setUpClass()

    def setUp(self):
        self.case = fixture.NativeEventReplayTests()
        self.case.setUp()
        self.case.dispatcher.native_retention = self.case.retention
        self.case.dispatcher.native_clone_authority = self.case.authority
        self.frame = scope.Frame(self.case.dispatcher)
        scope.COUNTS.clear()

    def register_fresh_globals(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        # This is the newly constructed two-participant fixture, never a
        # restored roster. Supply its missing native registration producer.
        initialize_global_pv_collections(self.case.fight, tuple(self.case.fight.actors))

    @contextmanager
    def admitted_fixture(self):
        # Unit-level admission supplies the same complete ENTRY as the actual
        # source-qualified wave scope. Real factory qualification is exercised
        # separately by the unmodified full-producer admission component.
        scope._full_check(self.case.retention, self.case.fight)
        token = scope._FRAMES.set((self.frame,))
        try:
            yield
        finally:
            scope._FRAMES.reset(token)

    def test_selected_rows_match_full_view_and_conversion_is_selected_only(self):
        self.register_fresh_globals()
        expected = self.case.retention.view().manager_entries(7)
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            with patch.object(
                retained, "_retained_record", wraps=retained._retained_record
            ) as convert:
                result = population.for_manager(7)
            self.assertEqual(type(result).__name__, "NativeRetainedEventView")
            self.assertEqual(scope.COUNTS["selected_views"], 1)
            self.assertEqual(result.entries, expected)
            self.assertEqual(convert.call_count, len(expected))
            self.assertEqual(population.for_manager(-7).entries, ())
        self.assertEqual(
            scope.COUNTS["uid_index_rows"], len(self.case.fight.native_retained_records)
        )
        self.assertEqual(scope.COUNTS["event_populations"], 1)

    def test_new_population_observes_append_and_canonical_group_removal(self):
        with self.admitted_fixture():
            first = self.case.retention.event_population().for_manager(7).entries
            self.case.dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))
            later = self.case.retention.event_population().for_manager(7).entries
            self.assertGreater(len(later), len(first))
            self.case.retention.remove_group(later[-1].uid)
            current = self.case.retention.event_population().for_manager(7).entries
            self.assertEqual(current, self.case.retention.view().manager_entries(7))
            self.assertEqual(current, first)

    def test_selected_payload_is_read_again_without_cached_validation(self):
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            population.for_manager(7)
            uid = next(iter(self.case.fight.native_owned_group_effects))
            self.case.fight.native_owned_group_effects[uid]["payload"] = "zz"
            with self.assertRaises(ValueError):
                population.for_manager(7)
            with self.assertRaises(ValueError):
                self.case.retention.view()

    def test_opaque_authority_revokes_before_malformed_offmanager_read(self):
        with self.admitted_fixture():
            self.case.retention.event_population()
            opaque = NativeCloneAuthority(lambda *args: True, lambda *args: None)
            scope.qualify_replay(self.case.dispatcher, self.case.retention, opaque)
            self.assertFalse(self.frame.enabled)
            uid = next(iter(self.case.fight.native_retained_records))
            self.case.fight.native_retained_records[uid]["generic_effect"] = True
            with self.assertRaisesRegex(ValueError, "generic definition"):
                self.case.retention.event_population()

    def test_guard_none_falls_back_before_index_or_synchronization(self):
        with self.admitted_fixture():
            sentinel = object()
            with patch.object(
                self.case.retention, "_pure_view_manager_pass", return_value=None
            ), patch.object(
                self.case.retention, "view", return_value=sentinel
            ) as view, patch.object(
                self.case.retention,
                "synchronize",
                side_effect=AssertionError("extra sync"),
            ), patch(
                "wakfu_server.combat_structural_uid_index.UidIndex",
                side_effect=AssertionError("extra index"),
            ):
                self.assertIs(self.case.retention.event_population(), sentinel)
            view.assert_called_once_with()

    def test_callback_installed_custom_map_keeps_legacy_access_order(self):
        self.register_fresh_globals()
        accesses = []

        class CustomMap(dict):
            def items(self):
                accesses.append("items")
                return super().items()

            def values(self):
                accesses.append("values")
                return super().values()

            def __iter__(self):
                accesses.append("iter")
                return super().__iter__()

        with self.admitted_fixture():
            with scope.callback_projection_boundary(self.case.retention):
                self.case.fight.native_owned_group_effects = CustomMap(
                    self.case.fight.native_owned_group_effects
                )
            accesses.clear()
            expected = self.case.retention.view().entries
            legacy = tuple(accesses)
            accesses.clear()
            actual = self.case.retention.event_population()
            self.assertEqual(type(actual).__name__, "NativeRetainedEffectView")
            self.assertEqual(actual.entries, expected)
            self.assertEqual(tuple(accesses), legacy)
            self.assertEqual(scope.COUNTS["selected_views"], 0)

    def test_full_entry_rejects_malformed_registry_before_projection(self):
        uid = next(iter(self.case.fight.native_retained_records))
        self.case.fight.native_retained_records[uid]["generic_effect"] = True
        with self.assertRaisesRegex(ValueError, "generic definition"):
            scope._full_check(self.case.retention, self.case.fight)
        self.assertEqual(scope.COUNTS["selected_views"], 0)

    def test_callback_nested_read_and_exception_have_no_projected_authority(self):
        with self.admitted_fixture():
            with self.assertRaisesRegex(RuntimeError, "callback failed"):
                with scope.callback_projection_boundary(self.case.retention):
                    self.assertIsNone(scope.event_frame(self.case.retention))
                    self.assertEqual(
                        type(self.case.retention.event_population()).__name__,
                        "NativeRetainedEffectView",
                    )
                    raise RuntimeError("callback failed")
            self.assertIs(scope.event_frame(self.case.retention), self.frame)

    def test_clone_cannot_reuse_original_fight_scope(self):
        self.register_fresh_globals()
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            original_fields = set(vars(self.case.fight))
            cloned = deepcopy(self.case.fight)
            self.assertEqual(set(vars(cloned)), original_fields)
            self.case.retention.fight = cloned
            self.assertIsNone(scope.event_frame(self.case.retention))
            result = population.for_manager(7)
            self.assertIs(result.fight, cloned)
            self.assertEqual(set(vars(cloned)), original_fields)
            for field in (
                "structural_uid_index",
                "_structural_uid_index",
                "_structural_qf_frame",
            ):
                self.assertNotIn(field, vars(cloned))


class RootCarrierWitnessTests(unittest.TestCase):
    setUpClass = classmethod(StructuralIndexTests.setUpClass.__func__)
    register_fresh_globals = StructuralIndexTests.register_fresh_globals
    admitted_fixture = StructuralIndexTests.admitted_fixture

    def setUp(self):
        StructuralIndexTests.setUp(self)
        self.register_fresh_globals()
        from dataclasses import asdict
        from wakfu_server.combat_state_ledger import RunningState
        from wakfu_server.combat_retained_effects import RetainedEffect
        from wakfu_server.combat_effects import _integer

        self.parent_uid = 800
        self.parent = RunningState(
            800, 61, 1, -7, -7, 1, "target", False, (), 0, True, None
        )
        self.case.fight.actors[-7].state_ledger._entries = (self.parent,)
        self.case.fight.state_wire_payloads[800] = _integer(3, 123).hex()
        self.case.fight.native_retained_records[800] = asdict(
            RetainedEffect(800, -7, 310, 123, manager_id=-7)
        )
        self.case.fight.native_retained_order.append(800)
        self.child_uid = next(iter(self.case.fight.native_owned_group_effects))
        self.case.fight.native_owned_group_effects[self.child_uid]["state_uid"] = 800
        self.case.fight.native_retained_records[self.child_uid]["owner_uid"] = 800

    def test_root_parent_is_fresh_witness_never_delivered_entry(self):
        expected = self.case.retention.view().manager_entries(7)
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            result = population.for_manager(7)
            self.assertEqual(type(result).__name__, "NativeRetainedEventView")
            self.assertEqual(result.entries, expected)
            self.assertNotIn(800, result.by_uid)
            self.assertEqual(scope.COUNTS["root_carrier_witnesses"], 1)
            self.assertEqual(scope.COUNTS["cross_manager_fallbacks"], 0)

    def test_parent_wire_mutation_is_not_hidden_by_previous_witness(self):
        from wakfu_server.combat_effects import _integer

        with self.admitted_fixture():
            population = self.case.retention.event_population()
            population.for_manager(7)
            self.case.fight.state_wire_payloads[800] = _integer(3, 124).hex()
            for read in (lambda: population.for_manager(7), self.case.retention.view):
                with self.assertRaisesRegex(ValueError, "metadata disagrees"):
                    read()

    def test_parent_scalar_type_mutation_is_not_cached(self):
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            population.for_manager(7)
            self.case.fight.native_retained_records[800]["generic_effect"] = True
            with self.assertRaisesRegex(ValueError, "generic definition"):
                population.for_manager(7)

    def test_nonroot_chain_keeps_full_fallback(self):
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            self.case.fight.native_retained_records[800]["owner_uid"] = self.child_uid
            with patch.object(
                self.case.retention, "view", return_value="full"
            ) as fallback:
                self.assertEqual(population.for_manager(7), "full")
                fallback.assert_called_once_with()

    def test_changed_parent_ledger_requires_full_fallback(self):
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            self.case.fight.actors[-7].state_ledger._entries = ()
            with patch.object(
                self.case.retention, "view", return_value="full"
            ) as fallback:
                self.assertEqual(population.for_manager(7), "full")
                fallback.assert_called_once_with()

    def test_callback_cannot_reuse_parent_proof(self):
        with self.admitted_fixture():
            population = self.case.retention.event_population()
            population.for_manager(7)
            with scope.callback_projection_boundary(self.case.retention):
                with patch.object(
                    self.case.retention, "view", return_value="full"
                ) as fallback:
                    self.assertEqual(population.for_manager(7), "full")
                    fallback.assert_called_once_with()
