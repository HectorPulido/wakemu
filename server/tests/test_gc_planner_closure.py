"""Pure planner closure lifetime without altering snapshot admission shapes."""
import gc
import sys
import unittest
import weakref
from copy import deepcopy
from unittest.mock import patch
from test_retained_gc_graph import fixture
from wakfu_server import combat_retained_gc as planner


class PlannerClosureTests(unittest.TestCase):
    def test_normal_opaque_and_exception_release_captured_planning_graph(self):
        def check(mode):
            snapshot = fixture()
            if mode == "opaque":
                snapshot["native_delay_queue"] = {"source": "unknown"}
            before = deepcopy(snapshot)
            references = []
            code = planner.plan_retired_effects.__code__

            def observe(frame, event, _arg):
                if (
                    not references
                    and event == "call"
                    and frame.f_code.co_name == "walk"
                    and frame.f_back is not None
                    and frame.f_back.f_code is code
                ):
                    fields = frame.f_back.f_locals
                    references.extend(
                        weakref.ref(fields[name])
                        for name in ("walk", "link", "uncertain")
                    )

            def fail_after_walk(*args):
                raise RuntimeError("intentional post-walk failure")

            old_profile = sys.getprofile()
            sys.setprofile(observe)
            try:
                if mode == "exception":
                    with patch.object(
                        planner, "_orphaned_containers", new=fail_after_walk
                    ):
                        try:
                            planner.plan_retired_effects(
                                snapshot, {-100, -200}, pending_roots=[]
                            )
                        except RuntimeError:
                            pass
                        else:
                            self.fail("Expected post-walk failure")
                else:
                    result = planner.plan_retired_effects(
                        snapshot, {-100, -200}, pending_roots=[]
                    )
                    self.assertEqual(
                        result.effect_uids, {21, 22, 31} if mode == "normal" else set()
                    )
                    self.assertEqual(bool(result.opaque_sources), mode == "opaque")
            finally:
                sys.setprofile(old_profile)
            self.assertEqual(snapshot, before)
            self.assertEqual(len(references), 3)
            return references

        previous = gc.isenabled()
        gc.disable()
        try:
            for mode in ("normal", "opaque", "exception"):
                with self.subTest(mode=mode):
                    self.assertTrue(
                        all(reference() is None for reference in check(mode))
                    )
        finally:
            if previous:
                gc.enable()
