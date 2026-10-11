"""eYC retains selected PV identity while each child reads its current position."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_state_managers import (
    selected_area_pv_scope,
    retained_area_pv_row,
)
import test_combat_effect_dispatch as definitions


class MultipleTargetPvScopeTests(unittest.TestCase):
    def fixture(self, first):
        row = dict(uid=91, reference=823, cell=(2, 3, 0))
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, position=(0, 0, 0))},
            native_effect_areas={91: row},
            native_retired_area_managers={},
        )
        invocation = EffectInvocation(90, 1, 7, None, (9, 9, 0))
        from dataclasses import replace

        seen = []

        def position(identity):
            if identity == 7:
                return fight.actors[7].position
            selected = retained_area_pv_row(fight, identity)
            if selected is None:
                raise ValueError("Unknown selected PV")
            return selected["cell"]

        def handler(effect, values, selected):
            self.assertTrue(selected.native_explicit_target)
            self.assertTrue(selected.wakemu_fresh_child_selection)
            seen.append((selected.reference, selected.cell))
            if selected.reference == 92:
                first(fight, row)
            return True

        retention = SimpleNamespace(
            is_subscription=lambda *a: False,
            begin_group=lambda *a: None,
            finish_group=lambda *a, **k: None,
            child_level_context=lambda *a, **k: (1, b""),
            probability_bypassed=lambda *a: False,
        )
        dispatcher = EffectDispatcher(
            {
                "90": definitions.effect(345, (1, 0, 0, 0), children=(92, 93)),
                "92": definitions.effect(400),
                "93": definitions.effect(400),
            },
            {400: handler},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: (),
            actor_position=position,
            group_retention=retention,
            multiple_group_candidates=lambda *a: (replace(invocation, target_id=91),),
            group_random=lambda: 0.5,
            pt_preflight=lambda *a: True,
            resolved_population_scope=lambda population: selected_area_pv_scope(
                fight, tuple(i.target_id for i in population)
            ),
        )
        return dispatcher, invocation, fight, row, seen

    def test_removed_selected_area_stays_available_only_during_children(self):
        dispatcher, invocation, fight, row, seen = self.fixture(
            lambda f, r: f.native_effect_areas.pop(91)
        )
        with patch("wakfu_server.combat_state_managers.registered_area_pv"):
            self.assertTrue(dispatcher.execute(invocation))
        self.assertEqual(seen, [(92, (2, 3, 0)), (93, (2, 3, 0))])
        self.assertIsNone(retained_area_pv_row(fight, 91))
        self.assertEqual(fight.native_effect_areas, {})

    def test_later_child_reads_updated_selected_pv_position(self):
        dispatcher, invocation, fight, row, seen = self.fixture(
            lambda f, r: r.update(cell=(4, 5, 0))
        )
        with patch("wakfu_server.combat_state_managers.registered_area_pv"):
            self.assertTrue(dispatcher.execute(invocation))
        self.assertEqual(seen, [(92, (2, 3, 0)), (93, (4, 5, 0))])

    def test_default_pt_stays_bound_and_opt_in_preserves_selected_leaf(self):
        from dataclasses import replace

        dispatcher, invocation, fight, row, seen = self.fixture(lambda *a: None)
        observed = []
        dispatcher.handlers[400] = lambda effect, values, selected: (
            observed.append(
                (
                    selected.target_id,
                    selected.native_explicit_target,
                    selected.wakemu_fresh_child_selection,
                )
            )
            or True
        )
        child = replace(
            invocation,
            reference=92,
            target_id=7,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        dispatcher.execute_pt(child)
        dispatcher.execute_pt(child, fresh_relationship_policy=True)
        self.assertEqual(observed, [(7, True, False), (7, True, True)])

    def test_exception_releases_held_pointer_and_unknown_target_rejects(self):
        def fail(fight, row):
            fight.native_effect_areas.pop(91)
            raise ValueError("Child failed")

        dispatcher, invocation, fight, row, seen = self.fixture(fail)
        with patch("wakfu_server.combat_state_managers.registered_area_pv"):
            with self.assertRaisesRegex(ValueError, "Child failed"):
                dispatcher.execute(invocation)
        self.assertIsNone(retained_area_pv_row(fight, 91))
        with self.assertRaisesRegex(ValueError, "Unknown selected native area PV"):
            with selected_area_pv_scope(fight, (999,)):
                self.fail("Unknown PV entered scope")
