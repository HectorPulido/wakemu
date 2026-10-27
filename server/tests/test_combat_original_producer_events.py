"""Bounded static producer evidence; no runtime callback or catalog expansion."""

from copy import copy
from types import SimpleNamespace
import unittest

from wakfu_server.combat_original_producer_events import (
    original_output_index,
    available_original_events,
    available_paid_breeze_events,
)
from wakfu_server.combat_static_catalogs import ImmutableCatalog, DefinitionOverlay


class OriginalProducerEvidenceTests(unittest.TestCase):
    def test_static_overlay_routes_phases_and_negative_authority_controls(self):
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_equipment_operation_capability import (
            FactoryOperationRoute,
            FactoryOperationRoutes,
        )
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_summon_handler import NativeSummonHandler
        from wakfu_server.combat_stat_handler import NativeStatHandler
        from wakfu_server.combat_carry_handler import NativeCarryHandler
        from wakfu_server.combat_displacement import NativeDisplacementHandler

        def row(family, events):
            return dict(effect_class=family, target_masks=[None] * 6 + [events])

        raw = {
            "1": row(400, [2148]),
            "2": row(333, [2158]),
            "3": row(400, [2180, 2231]),
            "4": row(400, []),
        }
        base = ImmutableCatalog(raw)
        first = original_output_index(base)
        self.assertIs(original_output_index(base), first)
        self.assertEqual(base._views, {})
        self.assertEqual(first["1"], (400, frozenset((2148,))))
        overlay = DefinitionOverlay(
            base, ImmutableCatalog({"1": row(400, []), "5": row(400, [9999])})
        )
        nested = DefinitionOverlay(overlay, {"5": row(400, [2231])})
        index = original_output_index(nested)
        self.assertNotIn("1", index)
        self.assertEqual(index["5"][1], frozenset((2231,)))
        self.assertEqual(original_output_index(raw), {})
        self.assertEqual(base._cached_views(), {})
        with self.assertRaises(TypeError):
            index["changed"] = (400, frozenset((1,)))

        authority = OrdinaryActorAuthority.__new__(OrdinaryActorAuthority)
        adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = authority
        adapter.cast = SimpleNamespace(stat=lambda *args: None)
        runtime = NativeEffectRuntimeFactory.__new__(NativeEffectRuntimeFactory)
        runtime.contexts = SimpleNamespace(
            healing_events=adapter.healing_events, stat=adapter.cast.stat
        )
        runtime.summon_authority = runtime.displacement_authority = authority
        runtime.effects = nested
        runtime.characteristic_registry = {"400": {"runner": "eXE"}}
        handlers = {
            307: NativeSummonHandler,
            400: NativeStatHandler,
            333: NativeCarryHandler,
            422: NativeDisplacementHandler,
            300: NativeDisplacementHandler,
            301: NativeDisplacementHandler,
            340: NativeDisplacementHandler,
        }
        routes = FactoryOperationRoutes.create(
            runtime,
            {
                family: FactoryOperationRoute(family, None, handler, runtime)
                for family, handler in handlers.items()
            },
        )
        wanted = {2130, 2158, 2180, 2231, 184, 187, 188, 198}
        for phase in (1, 2, 3, 4):
            events = available_original_events(runtime, routes, phase=phase)
            self.assertTrue(wanted <= events)
            self.assertNotIn(2148, events)  # Explicit source override removed it.
        self.assertEqual(
            available_original_events(copy(runtime), routes, phase=3), frozenset()
        )
        self.assertEqual(
            available_original_events(runtime, routes, phase=5), frozenset()
        )
        runtime.contexts.stat = lambda *args: None
        self.assertEqual(
            available_original_events(runtime, routes, phase=3), frozenset()
        )
        runtime.contexts.stat = adapter.cast.stat
        runtime.displacement_authority = object()
        events = available_original_events(runtime, routes, phase=3)
        self.assertFalse(events & {2158, 184, 187, 188, 198})
        self.assertIn(2130, events)
        self.assertEqual(
            available_paid_breeze_events(runtime, routes, {}, phase=2), frozenset()
        )
