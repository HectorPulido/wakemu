"""Bounded pure wire memoization never suppresses eager schema validation."""
import sys
import unittest
from unittest.mock import patch
from test_retained_gc_graph import fixture, wire, scalar
from wakfu_server import combat_retained_gc as gc


class GCWireCacheTests(unittest.TestCase):
    def test_plan_parity_warm_decode_and_opaque_custom_fallback(self):
        gc._cached_planner_wire_references.cache_clear()
        source = fixture()

        def plan():
            return gc.plan_retired_effects(source, {-100, -200}, pending_roots=())

        with patch.object(gc, "_planner_wire_references", gc._wire_references):
            baseline = plan()
        counts = []
        code = gc._wire_references.__code__

        def measured(callback):
            calls = []
            prior = sys.getprofile()

            def observe(frame, event, arg):
                if event == "call" and frame.f_code is code:
                    calls.append(True)

            sys.setprofile(observe)
            try:
                result = callback()
            finally:
                sys.setprofile(prior)
            return result, len(calls)

        for _ in range(2):
            result, calls = measured(plan)
            self.assertEqual(result, baseline)
            counts.append(calls)
        self.assertGreater(counts[0], 0)
        self.assertEqual(counts[1], 0)
        print("planner_wire_decodes", dict(cold=counts[0], warm=counts[1]))
        changed = wire(991, -100, -200)
        for family in (310, 949):
            result, calls = measured(
                lambda: gc._planner_wire_references(changed, family)
            )
            self.assertEqual(calls, 1)
            self.assertEqual(result, gc._wire_references(changed, family))
            self.assertTrue(all(type(values) is frozenset for values in result))
            with self.assertRaises(AttributeError):
                result[0].add(999)
        # An unreachable runner with an unknown field must still stop sweeping.
        source["native_owned_group_effects"]["31"]["payload"] += scalar(99, 30).hex()
        for _ in range(2):
            result = plan()
            with patch.object(gc, "_planner_wire_references", gc._wire_references):
                self.assertEqual(result, plan())
            self.assertTrue(result.opaque_sources)
            self.assertFalse(result.effect_uids)
        # Existing warm entries never hide newly supplied parsing callbacks.
        known = wire(10, 1, 1)
        gc._planner_wire_references(known, 310)
        original_fields = gc._fields
        field_calls = []

        def fields(*args, **kwargs):
            field_calls.append(True)
            return original_fields(*args, **kwargs)

        with patch.object(gc, "_fields", fields):
            self.assertEqual(
                gc._planner_wire_references(known, 310), gc._wire_references(known, 310)
            )
        self.assertGreaterEqual(len(field_calls), 2)
        original_parser = gc._wire_references
        parser_calls = []

        def parser(*args):
            parser_calls.append(args)
            return original_parser(*args)

        with patch.object(gc, "_wire_references", parser):
            gc._planner_wire_references(known, 310)
            gc._planner_wire_references(known, 310)
        self.assertEqual(len(parser_calls), 2)
        # 307 remains uncached, even for repeated invalid descriptors; this
        # negative fixture rejects before touching any external summon ABI.
        info = gc._cached_planner_wire_references.cache_info()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "summon recipient/caster"):
                gc._planner_wire_references(known, 307)
        self.assertEqual(gc._cached_planner_wire_references.cache_info(), info)
