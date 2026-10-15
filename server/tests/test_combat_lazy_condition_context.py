"""Blank criteria must not build unused native actor/retained projections."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from dataclasses import replace

from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from test_combat_effect_dispatch import effect


class LazyConditionContextTests(unittest.TestCase):
    def fixture(self, criteria, *, probability=True):
        seen = []
        context = Mock(return_value=ConditionContext({}))
        handler = Mock(
            spec=lambda *args: None,
            side_effect=lambda definition, values, invocation: seen.append(invocation)
            or True,
        )
        roll = Mock(return_value=probability)
        dispatcher = EffectDispatcher(
            {"90": effect(400, criteria=criteria)},
            {400: handler},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=context,
            probability_accepts=roll,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (identity, 1, 2),
        )
        return dispatcher, context, handler, roll, seen

    def test_blank_and_whitespace_preserve_effect_result_without_context(self):
        invocation = EffectInvocation(90, 20, 7, 8, (0, 0, 0))
        expected = None
        for criteria in ("", " \t\n", "1 == 1"):
            dispatcher, context, handler, roll, seen = self.fixture(criteria)
            result = dispatcher.execute(invocation)
            outcome = result, seen, handler.call_args.args[1], roll.call_args.args
            if expected is None:
                expected = outcome
            else:
                self.assertEqual(outcome, expected)
            self.assertEqual(context.call_count, int(bool(criteria.strip())))

    def test_nonblank_still_builds_context_and_rejects_before_probability(self):
        dispatcher, context, handler, roll, _ = self.fixture("1 > 2")
        self.assertFalse(dispatcher.execute(EffectInvocation(90, 20, 7, 8, (0, 0, 0))))
        context.assert_called_once()
        handler.assert_not_called()
        roll.assert_not_called()

    def test_blank_still_honors_probability(self):
        dispatcher, context, handler, roll, _ = self.fixture("", probability=False)
        self.assertFalse(dispatcher.execute(EffectInvocation(90, 20, 7, 8, (0, 0, 0))))
        context.assert_not_called()
        handler.assert_not_called()
        roll.assert_called_once()

    def test_blank_candidate_groups_preserve_children_without_context(self):
        root = EffectInvocation(90, 1, 1, 2, (9, 9, 0))
        cells = ((1, 0, 0), (0, 1, 0))
        candidates = tuple(
            replace(root, target_id=i + 3, cell=cell) for i, cell in enumerate(cells)
        )
        for kind, parameters in ((345, (2, 1, 1, 0)), (349, (2, 0, 1, 0, 0, 0, 0))):
            with self.subTest(kind=kind):
                seen = []
                context = Mock(side_effect=AssertionError("Blank candidate context"))
                retention = SimpleNamespace(
                    is_subscription=lambda *args: False,
                    begin_group=lambda *args: "pending",
                    finish_group=lambda *args, **kwargs: None,
                    child_level_context=lambda *args, **kwargs: (1, b""),
                    probability_bypassed=lambda *args: False,
                )
                dispatcher = EffectDispatcher(
                    {"90": effect(kind, parameters, children=(91,)), "91": effect(400)},
                    {
                        400: lambda definition, values, invocation: seen.append(
                            invocation
                        )
                        or True
                    },
                    resolve=lambda definition, invocation: (invocation,),
                    condition_context=context,
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: cells,
                    actor_position=lambda identity: {3: cells[0], 4: cells[1]}.get(
                        identity, (0, 0, 0)
                    ),
                    group_retention=retention,
                    multiple_group_candidates=lambda *args: candidates,
                    group_random=lambda: 0,
                    pt_preflight=lambda *args: True,
                )
                with patch(
                    "wakfu_server.combat_cell_group.native_cell_criterion_presence",
                    return_value=True,
                ):
                    self.assertTrue(dispatcher.execute(root))
                self.assertEqual([row.reference for row in seen], [91, 91])
                expected_cells = [cells[1], cells[0]] if kind == 345 else list(cells)
                self.assertEqual([row.cell for row in seen], expected_cells)
                context.assert_not_called()

    def test_blank_activation_preserves_execution_guard_and_skips_unused_context(self):
        dispatcher, context, handler, _, _ = self.fixture("")
        invocation = EffectInvocation(90, 20, 7, 8, (0, 0, 0))
        activation_context = Mock(side_effect=AssertionError("Unused context"))
        self.assertFalse(
            dispatcher.execute_activation(
                invocation,
                source=object(),
                condition_context=activation_context,
                executable=False,
                allocate_uid=lambda: 101,
            )
        )
        handler.assert_not_called()
        self.assertTrue(
            dispatcher.execute_activation(
                invocation,
                source=object(),
                condition_context=activation_context,
                executable=True,
                allocate_uid=lambda: 101,
            )
        )
        context.assert_not_called()
        activation_context.assert_not_called()
        handler.assert_called_once()


if __name__ == "__main__":
    unittest.main()
