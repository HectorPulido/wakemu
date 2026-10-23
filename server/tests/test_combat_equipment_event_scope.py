"""Pure scope matrix checks; no catalog, dispatcher or event publication."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch
from server.tests.postgres_case import PostgresCase

from wakfu_server import combat_equipment_event_scope as scope

tree = ast.parse(
    Path("server/wakfu_server/combat/combat_cost_payment_events.py").read_text()
)
node = next(
    n
    for n in tree.body
    if isinstance(n, ast.FunctionDef) and n.name == "payment_event_ids"
)
namespace = {}
exec(
    compile(
        ast.Module(body=[node], type_ignores=[]), "native-payment-producer", "exec"
    ),
    namespace,
)


class ScopeTests(unittest.TestCase):
    def run_scope(self, masks, *, retained=True, routes=None):
        lifecycle = ModuleType("wakfu_server.combat_equipment_retained_lifecycle")
        lifecycle.preflight = lambda factory, container: retained
        payment = ModuleType("wakfu_server.combat_cost_payment_events")
        payment.payment_event_ids = namespace["payment_event_ids"]
        with patch.dict(
            sys.modules, {lifecycle.__name__: lifecycle, payment.__name__: payment}
        ):
            return scope.assess(
                SimpleNamespace(contexts=SimpleNamespace(damage=lambda: None)),
                {"target_masks": masks},
                {"present": True},
                routes=routes,
            )

    def test_installed_start_cast_damage_and_paid_phases(self):
        for index, events in (
            (5, (1028, 1024, 1025)),
            (2, (1025, 2234)),
            (3, (2188, 2234, 2263)),
            (0, (2,)),
            (1, (2,)),
            (2, (2,)),
        ):
            masks = [None] * 7
            masks[index] = events
            self.assertIs(self.run_scope(masks), True)

    def test_scoped_outcome_absent_producer_and_wrong_phase_remain_unknown(self):
        for index, events in ((2, (1026,)), (5, (1016,)), (0, (2234,)), (6, (1001,))):
            masks = [None] * 7
            masks[index] = events
            self.assertIsNone(self.run_scope(masks))
        self.assertIsNone(self.run_scope([None] * 5 + [(1001, 1016), None]))

    def test_preflight_and_malformed_guards(self):
        self.assertIsNone(self.run_scope([None] * 5 + [(1028,), None], retained=False))
        self.assertIs(self.run_scope([None] * 5 + [(True,), None]), False)

    def test_committed_movement_is_external_only_and_requires_native_retention(self):
        # The established producer is Qf6/60/61 (mask5), never a Qe value.
        self.assertIs(self.run_scope([None] * 5 + [(1005,), None]), True)
        self.assertIsNone(self.run_scope([None] * 5 + [(1005,), None], retained=False))
        for index in range(5):
            masks = [None] * 7
            masks[index] = (1005,)
            self.assertIsNone(self.run_scope(masks))
        self.assertIsNone(self.run_scope([None] * 5 + [(1005, 1016), None]))

    def test_characteristic_prototypes_extend_only_actual_runner_phases(self):
        routes = object()
        with patch.object(
            scope, "characteristic_events", return_value=frozenset((67, 69))
        ) as metadata:
            for index in (0, 1, 2, 3):
                masks = [None] * 7
                masks[index] = (67, 69)
                self.assertIs(self.run_scope(masks, routes=routes), True)
                self.assertIs(metadata.call_args.args[1], routes)
            self.assertIsNone(self.run_scope([None] * 5 + [(67,), None], routes=routes))
            self.assertIsNone(
                self.run_scope(
                    [None, (68,), None, None, None, None, None], routes=routes
                )
            )

    def test_healing_and_displacement_keep_actual_qe_phases_without_external_guesses(
        self,
    ):
        with patch.object(
            scope, "healing_events", return_value=frozenset((0, 1, 17))
        ), patch.object(
            scope, "displacement_events", return_value=frozenset((0, 184, 193))
        ):
            for index in range(4):
                masks = [None] * 7
                masks[index] = (1, 17, 184, 193)
                self.assertIs(self.run_scope(masks), True)
            self.assertIsNone(self.run_scope([None] * 5 + [(1, 17, 184, 193), None]))

    def test_conditional_damage_and_preparation_require_their_real_phase(self):
        def produced(factory, routes, *, phase=1):
            return frozenset((0, 2)) | (
                frozenset((29, 2233)) if phase in (3, 4) else frozenset()
            )

        with patch.object(scope, "damage_events", side_effect=produced):
            for index in (2, 3):
                masks = [None] * 7
                masks[index] = (29, 2233)
                self.assertIs(self.run_scope(masks), True)
            for index in (0, 1, 5):
                masks = [None] * 7
                masks[index] = (29, 2233)
                self.assertIsNone(self.run_scope(masks))
            self.assertIs(
                self.run_scope([(500,), None, None, None, None, None, None]), True
            )
            self.assertIsNone(
                self.run_scope([None, None, (500,), None, None, None, None])
            )

    def test_element_damage_events_keep_qe_phases_and_source_metadata_distinct(self):
        with patch.object(
            scope, "damage_events", return_value=frozenset((0, 2, 5, 6, 7, 8))
        ):
            for index in range(4):
                masks = [None] * 7
                masks[index] = (5, 6, 7, 8)
                self.assertIs(self.run_scope(masks), True)
            self.assertIsNone(self.run_scope([None] * 5 + [(5,), None]))
            self.assertIsNone(
                self.run_scope([None, (1016,), None, None, None, None, None])
            )


class NativeFactoryEventScopePostgresTests(PostgresCase):
    def test_real_owned_factory_proves_new_scopes_without_running_callbacks(self):
        from copy import copy
        from dataclasses import replace
        from test_equipment_null_carrier_pipeline import (
            EquipmentNullCarrierPipelineTests,
        )
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_equipment_retained_lifecycle import preflight
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.fight_checkpoint_store import snapshot

        # Reuse the real persisted build/Ready fixture without inheriting its
        # TestCase methods or substituting a selected-entry list.
        (
            char,
            monster,
            deck,
            rng,
            runtime,
            _stats,
        ) = EquipmentNullCarrierPipelineTests._fixture(self)
        container = plan(char, ordinary_only=True)[0]["native_retained_container"]
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        routes, provider = factory.equipment_operation_capability()
        self.assertIs(type(routes.factory), NativeEffectRuntimeFactory)
        callback = routes.factory.contexts.healing_events
        self.assertIs(callback.__func__, NativeServerRuntimeAdapter.healing_events)
        self.assertIs(
            callback.__self__.actor_authority, routes.factory.summon_authority
        )
        self.assertTrue(preflight(factory, container))
        prototypes = scope.characteristic_events(factory, routes)
        self.assertTrue({67, 69}.issubset(prototypes))
        self.assertEqual(
            scope.characteristic_events(copy(factory), routes), frozenset()
        )
        self.assertTrue(
            {0, 2, 5, 6, 7, 8}.issubset(scope.damage_events(factory, routes))
        )
        self.assertEqual(scope.damage_events(copy(factory), routes), frozenset())
        self.assertTrue({0, 1, 17}.issubset(scope.healing_events(factory, routes)))
        self.assertEqual(scope.healing_events(copy(factory), routes), frozenset())
        self.assertFalse({29, 2233} & scope.damage_events(factory, routes, phase=1))
        self.assertTrue(
            {29, 2233}.issubset(scope.damage_events(factory, routes, phase=3))
        )
        self.assertTrue(
            {184, 187, 188, 193, 194, 197, 198}.issubset(
                scope.displacement_events(factory, routes)
            )
        )
        before, random_before = snapshot(runtime.fight), rng.getstate()

        def query(context_provider, index, events):
            masks = [None] * 7
            masks[index] = events
            return context_provider(
                kind="context",
                effect={"target_masks": masks},
                level=1,
                operation_id="effect.group",
                requires_context=("native_event_scope",),
                detail={"retained_container": container},
            )

        for index, events in (
            (5, (1028,)),
            (5, (1024, 1025)),
            (5, (1005,)),
            (5, (1016,)),
            (2, (1025,)),
            (3, (2188, 2234, 2263)),
            (1, (67, 69)),
            (1, (5, 6, 7, 8)),
        ):
            self.assertIs(query(provider, index, events), True)
        for index, events in ((2, (1026,)), (0, (2234,))):
            self.assertIsNone(query(provider, index, events))

        # Both a missing producer and a callable from an unrelated adapter
        # are insufficient. Merely being callable cannot qualify a new scope.
        for bad_callback in (None, lambda *_args, **_kwargs: None):
            changed = copy(factory)
            changed.contexts = replace(changed.contexts, healing_events=bad_callback)
            _routes, rejected = changed.equipment_operation_capability()
            self.assertFalse(preflight(changed, container))
            self.assertIsNone(query(rejected, 5, (1028,)))
            self.assertIsNone(query(rejected, 3, (2234,)))
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual(rng.getstate(), random_before)


if __name__ == "__main__":
    unittest.main()
