"""Selected native area pointers survive only within their ordered group."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state_managers import (
    selected_area_pv_scope,
    retained_area_pv_row,
)


class SelectedAreaPvScopeTests(unittest.TestCase):
    def fixture(self):
        row = dict(uid=91, reference=1835, owner_id=7, native_area_contract="faY")
        return (
            SimpleNamespace(
                actors={},
                native_effect_areas={91: row},
                native_retired_area_managers={},
            ),
            row,
        )

    def scope(self, fight, identities):
        return selected_area_pv_scope(fight, identities)

    def test_sibling_retains_actual_pointer_without_spatial_membership(self):
        fight, row = self.fixture()
        with patch("wakfu_server.combat_state_managers.registered_area_pv") as validate:
            with self.scope(fight, (91,)):
                del fight.native_effect_areas[91]
                self.assertIs(retained_area_pv_row(fight, 91), row)
                self.assertEqual(fight.native_effect_areas, {})
            validate.assert_called_once_with(fight, 91)
        self.assertIsNone(retained_area_pv_row(fight, 91))
        self.assertEqual(fight.native_retired_area_managers, {})

    def test_selected_owned_area_predicate_survives_but_cell_scan_does_not(self):
        from wakfu_server.combat_effect_area_queries import own_specific_area

        fight, row = self.fixture()
        fight.actors[7] = SimpleNamespace(id=7)
        with patch("wakfu_server.combat_state_managers.registered_area_pv"):
            with self.scope(fight, (91,)):
                del fight.native_effect_areas[91]
                from wakfu_server.combat_area_predicates import is_specific_area

                self.assertTrue(
                    is_specific_area(
                        fight, reference=1835, target_kind="area", target_id=91
                    )
                )
                self.assertFalse(
                    is_specific_area(
                        fight, reference=1835, target_kind="cell", cell=(2, 3, 0)
                    )
                )
                self.assertTrue(
                    own_specific_area(
                        fight,
                        reference=1835,
                        selector="target",
                        caster_id=7,
                        target_id=91,
                        cell=(2, 3, 0),
                    )
                )
                self.assertFalse(
                    own_specific_area(
                        fight,
                        reference=1835,
                        selector="target",
                        caster_id=7,
                        target_id=None,
                        cell=(2, 3, 0),
                    )
                )
            self.assertFalse(
                own_specific_area(
                    fight,
                    reference=1835,
                    selector="target",
                    caster_id=7,
                    target_id=91,
                    cell=(2, 3, 0),
                )
            )

    def test_resolved_population_holds_later_false_recipient_after_removal(self):
        from dataclasses import replace
        import test_combat_effect_dispatch as dispatch_tests
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_effect_area_queries import own_specific_area

        for fail in (False, True):
            with self.subTest(child_exception=fail):
                fight, row = self.fixture()
                fight.actors[7] = SimpleNamespace(id=7)
                second = dict(
                    uid=92, reference=1855, owner_id=7, native_area_contract="faY"
                )
                fight.native_effect_areas[92] = second
                resolved, visited = [], []

                def resolve(definition, invocation):
                    resolved.append(invocation.reference)
                    return tuple(replace(invocation, target_id=uid) for uid in (91, 92))

                def condition(invocation):
                    # The second identity must remain known, but its native
                    # area1835 predicate is false after the first runner.
                    self.assertIsNotNone(
                        retained_area_pv_row(fight, invocation.target_id)
                    )
                    visited.append(invocation.target_id)
                    matched = own_specific_area(
                        fight,
                        reference=1835,
                        selector="target",
                        caster_id=7,
                        target_id=invocation.target_id,
                        cell=(2, 3, 0),
                    )
                    return ConditionContext(
                        {}, own_specific_area_query=lambda *args: matched
                    )

                def handler(*args):
                    fight.native_effect_areas.clear()
                    if fail:
                        raise RuntimeError("child failure")
                    return True

                dispatcher = EffectDispatcher(
                    {
                        "90": dispatch_tests.effect(
                            400, criteria="IsOwnSpecificArea(1835)"
                        )
                    },
                    {400: handler},
                    resolve=resolve,
                    condition_context=condition,
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: (),
                    actor_position=lambda uid: (2, 3, 0),
                    resolved_population_scope=lambda population: self.scope(
                        fight, tuple(item.target_id for item in population)
                    ),
                )
                with patch("wakfu_server.combat_state_managers.registered_area_pv"):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "child failure"):
                            dispatcher.execute(
                                EffectInvocation(90, 20, 7, None, (2, 3, 0))
                            )
                    else:
                        self.assertTrue(
                            dispatcher.execute(
                                EffectInvocation(90, 20, 7, None, (2, 3, 0))
                            )
                        )
                        self.assertEqual(visited, [91, 92])
                self.assertEqual(resolved, [90])
                self.assertEqual(fight.native_effect_areas, {})
                self.assertIsNone(retained_area_pv_row(fight, 91))
                self.assertIsNone(retained_area_pv_row(fight, 92))

    def test_scope_cleans_up_on_child_exception(self):
        fight, row = self.fixture()
        with patch("wakfu_server.combat_state_managers.registered_area_pv"):
            with self.assertRaisesRegex(RuntimeError, "child failure"):
                with self.scope(fight, (91,)):
                    del fight.native_effect_areas[91]
                    raise RuntimeError("child failure")
        self.assertIsNone(retained_area_pv_row(fight, 91))

    def test_unknown_or_mismatched_identity_is_not_fabricated(self):
        fight, row = self.fixture()
        with self.assertRaisesRegex(ValueError, "Unknown selected"):
            with self.scope(fight, (92,)):
                self.fail("Unknown identity accepted")
        row["uid"] = 92
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            with self.scope(fight, (91,)):
                self.fail("Mismatched identity accepted")
