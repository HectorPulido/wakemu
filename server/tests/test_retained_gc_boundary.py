"""Actual Fight boundary tests; no SimpleNamespace fast-path substitutes."""
import ast
from copy import deepcopy
from dataclasses import asdict
import gc
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch

from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_ordinary_qi_retirement import complete_ordinary_qi_death
from wakfu_server.combat_native_death_status import (
    initialize_fresh_bje_death_status,
    apply_native_fighter_state_transition,
    native_is_dead,
)


class RetainedGCBoundaryTests(unittest.TestCase):
    def setUp(self):
        boundary._CURSORS.clear()

    def fixture(self):
        fight, _, dead, _ = NativeQIDeathLifecycleTests().fight()
        # This fixture explicitly declares a complete empty PB world domain;
        # otherwise native dsA is unknown and type2 cannot attest mwD=True.
        dead.native_world_properties = frozenset()
        initialize_fresh_bje_death_status(dead)
        self.assertIs(native_is_dead(dead), False)
        fight.apply_effect_damage(7, dead.id, dead.hp)
        self.assertTrue(complete_ordinary_qi_death(fight, dead))
        apply_native_fighter_state_transition(dead, 2)
        self.assertIs(native_is_dead(dead), True)
        # The imported QI unit fixture installs its synthetic tackle provider.
        # This GC fixture has no movement provider; do not certify that custom
        # callback as native authority. Separate tests require its rejection.
        del fight.native_rail_movement_authority
        uid = 10001
        payload = group_payload(
            uid=uid,
            base_uid=uid,
            generic_effect=350552,
            caster_id=dead.id,
            target_id=None,
            cell=dead.position,
            container_type=None,
            container_id=None,
            timing_payload=b"",
        ).hex()
        entry = RetainedEffect(
            uid, None, 949, 350552, manager_id=dead.id, container_present=False
        )
        fight.native_retained_tracking = True
        fight.native_retained_order = [uid]
        fight.native_retained_records = {uid: asdict(entry)}
        fight.native_owned_group_effects[uid] = dict(
            target_id=None, effect_class=949, state_uid=None, payload=payload
        )
        previous = deepcopy(fight)
        runtime = RuntimeMessages(fight)
        return previous, fight, runtime, dead.id, uid

    def test_real_fight_is_canonical_and_full_path_collects_only_terminal_effect(self):
        previous, fight, runtime, dead, uid = self.fixture()
        self.assertTrue(boundary._canonical_graph(fight))
        events = deepcopy(fight.events)
        with patch.object(
            boundary, "_complete_view", wraps=boundary._complete_view
        ) as views:
            boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertEqual(views.call_count, 2)
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertNotIn(uid, fight.native_owned_group_effects)
        self.assertIn(dead, fight.actors)
        self.assertEqual(fight.events, events)
        self.assertIn(uid, previous.native_retained_records)

    def test_planner_projection_matches_full_snapshot_before_sweep(self):
        from wakfu_server.combat_retained_gc import plan_retired_effects
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_retained_collections import bound_collections
        from wakfu_server.combat_source_provenance_entries import (
            SourceProvenanceEntries,
        )
        from wakfu_server.combat_retained_source_provenance import POLICY

        _, fight, _, dead, uid = self.fixture()
        # Restore the authentic retained owner: the legacy death fixture swaps
        # these two fields for plain containers to cover its older callers.
        owner = fight.actors.owner
        row = fight.native_retained_records[uid]
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        owner.records.install_owned(uid, row)
        owner.order.append(uid)
        self.assertIs(bound_collections(vars(fight)), owner)

        # Keep the three planner-relevant history roots in their native
        # producer shapes, including the empty artifact-root subgraph.
        if not hasattr(fight, "native_global_pv_collections"):
            initialize_global_pv_collections(fight, tuple(fight.actors))
        if not hasattr(fight, "native_state_source_provenance"):
            fight.native_state_source_provenance = dict(
                policy=POLICY, entries=SourceProvenanceEntries()
            )
        if not hasattr(fight, "rift_wave_state"):
            fight.rift_wave_state = {"native_artifact_groups": {}}
        fight.planner_unknown_extension = {"future_label": "preserve-me"}
        self.assertTrue(boundary._canonical_graph(fight))

        full = snapshot(fight)

        class IgnoredHistory:
            def __deepcopy__(self, memo):
                raise AssertionError(
                    "filtered event history reached snapshot serializer"
                )

        # The full durable snapshot above captured the source of truth. A
        # poison event now proves this planner-only projection filters history
        # before the checkpoint serializer traverses it.
        fight.events.append(IgnoredHistory())
        projected, pending_roots = boundary._project_snapshot(fight, [])
        self.assertIn("events", full)
        self.assertNotIn("events", projected)
        self.assertEqual(
            full["planner_unknown_extension"], projected["planner_unknown_extension"]
        )
        for field in (
            "native_state_source_provenance",
            "native_global_pv_collections",
            "rift_wave_state",
        ):
            self.assertEqual(full[field], projected[field])

        full_plan = plan_retired_effects(full, {dead}, pending_roots=pending_roots)
        projected_plan = plan_retired_effects(
            projected, {dead}, pending_roots=pending_roots
        )
        self.assertEqual(full_plan, projected_plan)
        self.assertEqual(frozenset({dead}), projected_plan.actor_ids)
        self.assertEqual(frozenset({uid}), projected_plan.effect_uids)
        # Planning itself is read-only; the actual sweep has not run.
        self.assertIn(uid, fight.native_retained_records)
        self.assertIn(uid, fight.native_owned_group_effects)

    def test_pending_ack_preserves_dirty_until_later_quiescent_preview(self):
        previous, fight, runtime, _, uid = self.fixture()
        runtime.awaiting_ack = fight.turn_id
        with patch.object(
            boundary, "_complete_view", wraps=boundary._complete_view
        ) as views:
            boundary.prepare_retired_gc(previous, fight, runtime, ())
            self.assertEqual(views.call_count, 0)
        self.assertIn(uid, fight.native_retained_records)
        self.assertTrue(boundary._CURSORS[fight][1])
        candidate, resumed = deepcopy((fight, runtime))
        resumed.awaiting_ack = None
        boundary.prepare_retired_gc(fight, candidate, resumed, ())
        self.assertNotIn(uid, candidate.native_retained_records)

    def test_canonical_graph_accepts_actual_nested_running_state_timer(self):
        from wakfu_server.combat_state_ledger import RunningState, StateTimer

        _, fight, _, dead, _ = self.fixture()
        # Exercise typed serialization eligibility only. The complete-view
        # path separately requires its authentic owned payload/registration.
        fight.actors[dead].state_ledger._entries = (
            RunningState(
                10002,
                310,
                1,
                dead,
                dead,
                3,
                "caster",
                False,
                (350552,),
                0,
                True,
                StateTimer(dead, 4, "start"),
            ),
        )
        self.assertTrue(boundary._canonical_graph(fight))

    def test_custom_mapping_prevents_gc_without_invoking_its_getter(self):
        previous, fight, runtime, _, uid = self.fixture()
        calls = []

        class Opaque(dict):
            def items(self):
                calls.append(True)
                return super().items()

        fight.actors[7].extra_native_source = Opaque(caster_id=-7)
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertEqual(calls, [])
        self.assertIn(uid, fight.native_retained_records)

    def test_cycle_is_opaque_but_shared_plain_alias_is_canonical(self):
        _, fight, _, _, _ = self.fixture()
        shared = {"value": 1}
        fight.alias_probe = [shared, shared]
        self.assertTrue(boundary._canonical_graph(fight))
        shared["cycle"] = shared
        self.assertFalse(boundary._canonical_graph(fight))

    def test_partial_manager_collection_retries_after_last_source_root_disappears(self):
        previous, fight, runtime, dead, inert = self.fixture()

        def group(uid, manager, base):
            payload = group_payload(
                uid=uid,
                base_uid=base,
                generic_effect=350552,
                caster_id=manager,
                target_id=None,
                cell=fight.actors[manager].position,
                container_type=None,
                container_id=None,
                timing_payload=b"",
            ).hex()
            fight.native_owned_group_effects[uid] = dict(
                target_id=None, effect_class=949, state_uid=None, payload=payload
            )
            fight.native_retained_records[uid] = asdict(
                RetainedEffect(
                    uid, None, 949, 350552, manager_id=manager, container_present=False
                )
            )
            fight.native_retained_order.append(uid)

        group(10002, dead, 10002)
        group(10003, 7, 10002)  # Live retained child preserves its source UID.
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertNotIn(inert, fight.native_retained_records)
        self.assertIn(10002, fight.native_retained_records)
        self.assertTrue(boundary._CURSORS[fight][2])
        candidate, next_runtime = deepcopy((fight, runtime))
        for field in ("native_owned_group_effects", "native_retained_records"):
            getattr(candidate, field).pop(10003)
        candidate.native_retained_order.remove(10003)
        # Native deletion normally has its packet; scheduling must also retry
        # the preserved component on a later turn without that packet.
        candidate.turn_id += 1
        boundary.prepare_retired_gc(fight, candidate, next_runtime, ())
        self.assertNotIn(10002, candidate.native_retained_records)

    def test_invalid_full_view_raises_before_sweep_and_source_stays_intact(self):
        previous, fight, runtime, _, uid = self.fixture()
        fight.native_owned_group_effects[uid]["payload"] = "00"
        with self.assertRaises(ValueError):
            boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertIn(uid, fight.native_retained_records)
        self.assertNotEqual(previous.native_owned_group_effects[uid]["payload"], "00")
        self.assertNotIn(fight, boundary._CURSORS)

    def test_weak_cursor_has_no_owner_backreference(self):
        previous, fight, runtime, _, _ = self.fixture()
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        reference = weakref.ref(fight)
        del fight, runtime
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(len(boundary._CURSORS), 0)

    def test_generic_custom_callback_is_opaque(self):
        previous, fight, runtime, dead, uid = self.fixture()
        runtime.turn_start_provider = lambda preview, **kw: preview.actors[
            dead
        ].state_ledger.entries
        with patch.object(
            boundary, "_complete_view", wraps=boundary._complete_view
        ) as views:
            boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertEqual(views.call_count, 0)
        self.assertIn(uid, fight.native_retained_records)

    def test_permanent_carrier_only_does_not_schedule_every_turn(self):
        _, fight, _, dead, uid = self.fixture()
        fight.native_retained_records[uid]["effect_class"] = 310
        self.assertFalse(boundary._retryable_runners(fight, {dead}))
        fight.native_retained_records[uid]["effect_class"] = 949
        self.assertTrue(boundary._retryable_runners(fight, {dead}))
        self.assertFalse(boundary._retryable_runners(fight, {7}))

    def test_native_frozen_terrain_is_canonical_but_custom_subclass_is_not(self):
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet

        _, fight, _, _, _ = self.fixture()
        fight.walkable = ImmutableTerrainSet(fight.walkable)
        fight.edges = ImmutableTerrainSet((((0, 0, 0), (1, 0, 0)),))
        self.assertTrue(boundary._canonical_graph(fight))
        calls = []

        class CustomTerrain(ImmutableTerrainSet):
            def __iter__(self):
                calls.append(True)
                return super().__iter__()

        fight.walkable = CustomTerrain(((0, 0, 0),))
        self.assertFalse(boundary._canonical_graph(fight))
        self.assertEqual(calls, [])

    def test_native_qi_masks_are_canonical_but_custom_subclass_is_not(self):
        from wakfu_server.combat_qi_snapshot import ImmutableQIMasks

        _, fight, _, _, _ = self.fixture()
        fight.native_qi_snapshot["cell_masks"] = ImmutableQIMasks([0] * 16)
        self.assertTrue(boundary._canonical_graph(fight))
        calls = []

        class CustomMasks(ImmutableQIMasks):
            def __iter__(self):
                calls.append(True)
                return super().__iter__()

        fight.native_qi_snapshot["cell_masks"] = CustomMasks([0] * 16)
        self.assertFalse(boundary._canonical_graph(fight))
        self.assertEqual(calls, [])

    def test_native_catalog_validates_raw_source_fresh_without_lazy_reads(self):
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        _, fight, _, _, _ = self.fixture()
        source = {"rows": [{"reference": 123, "values": [1, 2]}]}
        catalog = ImmutableCatalog(source)
        fight.native_catalog_probe = catalog
        with patch.object(
            ImmutableCatalog,
            "_cached_views",
            side_effect=AssertionError("lazy view touched"),
        ):
            self.assertTrue(boundary._canonical_graph(fight))
            source["opaque"] = object()
            self.assertFalse(boundary._canonical_graph(fight))
            source.pop("opaque")
            source["cycle"] = catalog
            self.assertFalse(boundary._canonical_graph(fight))
            source.pop("cycle")
            self.assertTrue(boundary._canonical_graph(fight))
        catalog._views["unexpected"] = {}
        self.assertFalse(boundary._canonical_graph(fight))
        catalog._views.clear()

        class OpaqueSource(dict):
            def items(self):
                raise AssertionError("opaque source getter touched")

        catalog._source = OpaqueSource(source)
        self.assertFalse(boundary._canonical_graph(fight))

        class CustomCatalog(ImmutableCatalog):
            pass

        fight.native_catalog_probe = CustomCatalog(source)
        self.assertFalse(boundary._canonical_graph(fight))

    def test_canonical_assembler_issues_identity_proof_preserved_by_runtime_copy(self):
        from types import SimpleNamespace
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_retained_gc_authority import native_callbacks_known

        _, fight, _, _, _ = self.fixture()
        adapter = CombatSessionAdapter.__new__(CombatSessionAdapter)
        adapter.store = object()
        characters, decks = {7: {"id": 7, "account_id": 1}}, {7: b""}

        def ready_result(current, owner, ready, **providers):
            # This test isolates actual assembler issuance, not Ready gameplay:
            # keep its locally created callbacks, without running initialization.
            runtime = RuntimeMessages(
                current,
                **{
                    name: providers[name]
                    for name in (
                        "stats_serializer",
                        "runtime_stats_serializer",
                        "turn_start_provider",
                        "turn_end_provider",
                        "expiration_runtime_factory",
                    )
                }
            )
            self.assertFalse(native_callbacks_known(runtime))
            return current, runtime, ()

        with patch.object(
            CombatSessionAdapter, "player_sources", return_value=(characters, decks)
        ), patch("wakfu_server.combat_ready.prepare_ready", side_effect=ready_result):
            transition = adapter.ready_transition(
                SimpleNamespace(account_id=1, character_id=7), fight, None, True, {}
            )
        runtime = transition.runtime
        self.assertTrue(native_callbacks_known(runtime))
        clone = deepcopy(runtime)
        self.assertIs(clone._retained_gc_callbacks, runtime._retained_gc_callbacks)
        self.assertTrue(native_callbacks_known(clone))
        clone.turn_start_provider = lambda preview, **kw: preview.actors[
            -7
        ].state_ledger.entries
        self.assertFalse(native_callbacks_known(clone))
        self.assertTrue(native_callbacks_known(runtime))

    def test_four_shared_seams_are_before_adoption_and_after_turn_synchronization(self):
        source = Path(__file__).parent / "candidate" / "combat_shared.py"
        tree = ast.parse(source.read_text())
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "prepare_retired_gc"
        ]
        self.assertEqual(len(calls), 4)
        publication = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_prepare_publication"
        )
        text = ast.unparse(publication)
        self.assertLess(
            text.index("self._synchronize_defeated_current("),
            text.index("prepare_retired_gc("),
        )
        self.assertLess(
            text.index("prepare_retired_gc("), text.index("persist_prepared(")
        )


if __name__ == "__main__":
    unittest.main()
