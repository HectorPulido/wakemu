"""The ordinary eOV predicate projects only the selected current QI slot."""
import sys
import unittest
from unittest.mock import patch
from test_combat_pointer_qi_projection import PointerQIProjectionTests
from wakfu_server import combat_qi_fight
from wakfu_server.combat_pointer_qi_registry import PointerRegistryCompatibility
from types import SimpleNamespace
from wakfu_server.combat_ordinary_authority import ordinary_cell_obstacle


class ConditionCellObstacleTests(unittest.TestCase):
    def test_canonical_selected_obstacle_matches_legacy_without_full_slots(self):
        registry = PointerQIProjectionTests().synthetic_registry()
        registry.qi.ordered_members = lambda x, y: registry.qi.cells[(x, y)].order()
        fight = registry.qi.fight

        def old(invocation):
            if invocation.cell is None:
                return None
            current = combat_qi_fight.current_registry(fight)
            order = current.ordered_U(*invocation.cell[:2])
            return bool(order and current.slots[order[0]] is not None)

        def observe(callback, invocations):
            reads = []
            code = PointerRegistryCompatibility.slots.fget.__code__
            prior = sys.getprofile()

            def profile(frame, event, arg):
                if event == "call" and frame.f_code is code:
                    reads.append(True)

            sys.setprofile(profile)
            try:
                values = [callback(invocation) for invocation in invocations]
            finally:
                sys.setprofile(prior)
            return values, len(reads)

        def compare():
            invocations = [
                SimpleNamespace(cell=cell)
                for cell in ((0, 0, 0), (1, 0, 0), (12, 0, 0), None)
            ]
            baseline, old_reads = observe(old, invocations)
            actual, new_reads = observe(
                lambda invocation: ordinary_cell_obstacle(fight, {}, None, invocation),
                invocations,
            )
            self.assertEqual(actual, baseline)
            self.assertGreater(old_reads, 0)
            self.assertEqual(new_reads, 0)
            legacy = SimpleNamespace(slots=registry.slots, ordered_U=registry.ordered_U)
            with patch.object(combat_qi_fight, "current_registry", return_value=legacy):
                legacy_actual = [
                    ordinary_cell_obstacle(fight, {}, None, invocation)
                    for invocation in invocations
                ]
                self.assertEqual(
                    legacy_actual, [old(invocation) for invocation in invocations]
                )
                self.assertEqual(legacy_actual, actual)
            return actual, old_reads, new_reads

        with patch.object(combat_qi_fight, "current_registry", return_value=registry):
            before, old_reads, new_reads = compare()
            self.assertEqual(before, [True, True, False, None])
            # The selected current QK becomes null while its historical byte
            # remains in the cell order; no later occupant may replace it.
            registry.qi.slots[1] = None
            registry.qi.cells[(1, 0)].values = (1, 0)
            after, _, _ = compare()
            self.assertEqual(after, [True, False, False, None])
        print(
            "ordinary_obstacle_full_slot_reads",
            dict(baseline=old_reads, candidate=new_reads),
        )
