"""One native QI read preserves eII fighter selection and eOV first-slot facts."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_combat_qi_fight import NativeQIFightLifecycleTests
from wakfu_server.combat_casting_context import resolve_criterion_cell_invocation
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    OrdinaryConditionCellQuery,
    ordinary_cell_obstacle,
)
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_conditions import UnknownCondition
from wakfu_server import combat_qi_fight


class CombinedCellQueryTests(unittest.TestCase):
    def fixture(self):
        fixture = NativeQIFightLifecycleTests()
        fight, actor, other = fixture.fixture(radii=(0, 0))
        fixture.initialize(fight)
        adapter = SimpleNamespace(
            _actor=lambda f, a: SimpleNamespace(targeting={"is_eGj": True})
        )
        return fight, actor, other, adapter

    def test_actual_qi_combined_matches_separate_reads_and_preserves_invocation(self):
        fight, actor, other, adapter = self.fixture()
        for cell in (actor.position, other.position, (1, 0, 0), (99, 99, 0), None):
            with self.subTest(cell=cell):
                invocation = EffectInvocation(
                    410765,
                    1,
                    actor.id,
                    None,
                    cell,
                    native_target_cell_argument=True,
                    native_trigger_context={"kept": True},
                )
                with patch.object(
                    combat_qi_fight,
                    "current_registry",
                    wraps=combat_qi_fight.current_registry,
                ) as calls:
                    old = resolve_criterion_cell_invocation(adapter, fight, invocation)
                    obstacle = ordinary_cell_obstacle(fight, {}, None, old)
                    separate_calls = calls.call_count
                with patch.object(
                    combat_qi_fight,
                    "current_registry",
                    wraps=combat_qi_fight.current_registry,
                ) as calls:
                    combined, actual = resolve_criterion_cell_invocation(
                        adapter, fight, invocation, return_obstacle=True
                    )
                    self.assertEqual(calls.call_count, 0 if cell is None else 1)
                self.assertEqual(combined, old)
                self.assertEqual(actual, obstacle)
                self.assertEqual(separate_calls, 0 if cell is None else 2)
                self.assertIs(
                    combined.native_trigger_context, invocation.native_trigger_context
                )
                self.assertIsNone(invocation.target_id)

    def test_first_slot_and_first_actual_fighter_are_distinct(self):
        for first in ("area", "nonfighter", "null"):
            with self.subTest(first=first):
                actor, nonfighter = SimpleNamespace(id=7), SimpleNamespace(id=8)
                first_row = (
                    None
                    if first == "null"
                    else {
                        "identity": ["area", 900] if first == "area" else ["actor", 8]
                    }
                )
                rows = [first_row, {"identity": ["actor", 7]}]
                registry = SimpleNamespace(slots=rows, ordered_U=lambda x, y: (0, 1))
                adapter = SimpleNamespace(
                    _actor=lambda f, a: SimpleNamespace(targeting={"is_eGj": a.id == 7})
                )
                fight = SimpleNamespace(actors={7: actor, 8: nonfighter})
                invocation = EffectInvocation(1, 1, 7, None, (0, 0, 0))
                with patch.object(
                    combat_qi_fight, "current_registry", return_value=registry
                ):
                    resolved, obstacle = resolve_criterion_cell_invocation(
                        adapter, fight, invocation, return_obstacle=True
                    )
                self.assertEqual(resolved.target_id, 7)
                self.assertEqual(obstacle, first != "null")

    def test_missing_topology_and_changed_actor_still_reject(self):
        for corrupt in ("topology", "position"):
            for combined in (False, True):
                with self.subTest(corrupt=corrupt, combined=combined):
                    fight, actor, _, adapter = self.fixture()
                    if corrupt == "topology":
                        fight.native_qi_byte_topology = None
                    else:
                        actor.position = (1, 1, 0)
                    with self.assertRaises(ValueError):
                        resolve_criterion_cell_invocation(
                            adapter,
                            fight,
                            EffectInvocation(1, 1, actor.id, None, (0, 0, 0)),
                            return_obstacle=combined,
                        )

    def test_unknown_native_fighter_kind_keeps_original_error(self):
        fight, actor, _, adapter = self.fixture()
        adapter._actor = lambda f, a: SimpleNamespace(targeting={"is_eGj": None})
        for combined in (False, True):
            with self.assertRaises(UnknownCondition):
                resolve_criterion_cell_invocation(
                    adapter,
                    fight,
                    EffectInvocation(1, 1, actor.id, None, actor.position),
                    return_obstacle=combined,
                )

    def test_capability_rejects_replaced_obstacle_and_custom_actor_authority(self):
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        native = OrdinaryActorAuthority.__new__(OrdinaryActorAuthority)
        cap = OrdinaryConditionCellQuery(ordinary_cell_obstacle)
        adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = native
        adapter.cast = SimpleNamespace(cell_obstacle=ordinary_cell_obstacle)
        self.assertTrue(cap.admitted(adapter))
        adapter.actor_authority = RegisteredSummonAuthority(native)
        self.assertTrue(cap.admitted(adapter))
        adapter.cast.cell_obstacle = lambda *a: False
        self.assertFalse(cap.admitted(adapter))
        adapter.cast.cell_obstacle = ordinary_cell_obstacle

        class Custom(OrdinaryActorAuthority):
            pass

        for provider in (
            Custom.__new__(Custom),
            RegisteredSummonAuthority(Custom.__new__(Custom)),
        ):
            adapter.actor_authority = provider
            self.assertFalse(cap.admitted(adapter))
        self.assertFalse(OrdinaryConditionCellQuery(lambda *a: False).admitted(adapter))

        class CustomAdapter(NativeServerRuntimeAdapter):
            pass

        custom_adapter = CustomAdapter.__new__(CustomAdapter)
        custom_adapter.actor_authority = native
        custom_adapter.cast = SimpleNamespace(cell_obstacle=ordinary_cell_obstacle)
        self.assertFalse(cap.admitted(custom_adapter))


class CombinedAdapterContextTests(unittest.TestCase):
    def test_public_adapter_unadmitted_context_keeps_original_fresh_reads(self):
        from test_combat_range_selection_projection import RangeSelectionProjectionTests
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_condition_selection_scope import (
            condition_actor_selection_scope,
        )
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        fixture = RangeSelectionProjectionTests()
        fixture.setUp()
        fight = fixture.fight
        terrain = dict(x=0, y=0, width=4, height=4, cell_masks=[256] * 16)
        slots = [None] * 127
        for i, actor in enumerate(fight.actors.values()):
            actor.native_obstacle_id = i
            slots[i] = dict(
                identity=["actor", actor.id],
                position=list(actor.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        registry = NativeQIRegistry(terrain, slots)
        registry.capture_fresh_cell_topology(list(range(len(fight.actors))))
        fight.native_qi_snapshot = terrain
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        invocation = EffectInvocation(
            410765, 1, 7, None, (2, 2, 0), native_target_cell_argument=True
        )
        cap = OrdinaryConditionCellQuery(ordinary_cell_obstacle)
        cast = replace(
            fixture.adapter.cast,
            cell_obstacle=ordinary_cell_obstacle,
            condition_cell_query=cap,
        )
        contexts, counts = [], []
        for pure in (False, True):
            adapter = NativeServerRuntimeAdapter(
                actor_authority=fixture.native, cast=cast
            )
            with condition_actor_selection_scope(enabled=pure), patch.object(
                combat_qi_fight,
                "current_registry",
                wraps=combat_qi_fight.current_registry,
            ) as calls:
                contexts.append(adapter.condition(fight, {}, None, invocation))
                counts.append(calls.call_count)
        self.assertEqual(contexts[0].actors, contexts[1].actors)
        self.assertEqual(contexts[0].target_cell, contexts[1].target_cell)
        # A paired read now requires the complete bulk source proof. Merely
        # entering a selection scope must not suppress the second QI guard.
        self.assertEqual(counts, [2, 2])
        observed = []
        custom = replace(
            cast, cell_obstacle=lambda *a: observed.append("custom") or True
        )
        adapter = NativeServerRuntimeAdapter(
            actor_authority=fixture.native, cast=custom
        )
        with condition_actor_selection_scope():
            context = adapter.condition(fight, {}, None, invocation)
        self.assertEqual(observed, ["custom"])
        self.assertTrue(context.target_cell.has_obstacle)

        class MutatingAdapter(NativeServerRuntimeAdapter):
            changed = False

            def _actor(self, fight, actor, **kwargs):
                result = super()._actor(fight, actor, **kwargs)
                if not self.changed:
                    self.changed = True
                    fight.actors[-7].position = (2, 3, 0)
                return result

        custom_adapter = MutatingAdapter(actor_authority=fixture.native, cast=cast)
        occupied = replace(invocation, cell=fight.actors[7].position)
        with condition_actor_selection_scope(), patch.object(
            combat_qi_fight, "current_registry", wraps=combat_qi_fight.current_registry
        ) as calls:
            with self.assertRaises(ValueError):
                custom_adapter.condition(fight, {}, None, occupied)
            self.assertEqual(calls.call_count, 2)
