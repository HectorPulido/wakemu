"""Native scope unwinding matches historical nested-with entry execution."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_active_spell import active_spell_scope, active_spell_container
from wakfu_server.combat_cast_events import cast_event_scope
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_entry_executor import execute_entry_roots
from wakfu_server.combat_normal_execution_origin import (
    normal_execution_origin,
    normal_root_context,
)


class EntryScopeFailureTests(unittest.TestCase):
    def _execute(self, implementation, fail_at=None):
        trace = []
        failure = RuntimeError("entry failure: " + str(fail_at))
        old_container = dict(present=True, is_spell=True, spell_id=900, level=8)
        caster = SimpleNamespace(id=7, position=(0, 0, 0), physical_radius=0)
        target = SimpleNamespace(id=-7, position=(1, 0, 0), physical_radius=0)
        preview = SimpleNamespace(
            actors={7: caster, -7: target},
            native_active_spell_id=900,
            native_active_spell_container=old_container,
        )

        def record(point, *facts):
            trace.append((point, *facts, deepcopy(active_spell_container(preview))))
            if point == fail_at:
                raise failure

        @contextmanager
        def resolution():
            record("resolution.enter")
            try:
                yield
            finally:
                record("resolution.exit")

        preview.effect_resolution = resolution
        plan = dict(
            actor_id=7,
            spell_id=6266,
            evaluation_level=12,
            target_id=-7,
            target=(1, 0, 0),
        )
        origin = normal_execution_origin(plan)
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=preview),
            native_clone_authority=object(),
            replay_event=lambda *args, **kwargs: (),
            effects={
                str(ref): {
                    "area_class": "anD",
                    "native_target_selector": {"class": "fcE", "mask": 3},
                }
                for ref in (1, 2)
            },
        )

        def execute(invocation):
            record("root" + str(invocation.reference), invocation.native_context_hex)
            return True

        dispatcher.execute = execute

        def deliver(dispatcher, plan, event_id, context, *, removal=False):
            record("event" + str(event_id) + (".remove" if removal else ""))
            return ()

        def paid(*args):
            record("paid")

        def breeze(*args):
            record("breeze")

        outcome, error = None, None
        with patch("wakfu_server.combat_cast_events._deliver", deliver), patch(
            "wakfu_server.combat_attack_preparation.settle_attack_preparation",
            side_effect=lambda dispatcher: record("settle"),
        ), patch(
            "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs", paid
        ), patch(
            "wakfu_server.combat_breeze_payment_events.replay_paid_breeze_costs", breeze
        ), patch(
            "wakfu_server.combat_direct_target.native_direct_target_policies",
            return_value={},
        ):
            try:
                if implementation == "historical":
                    with active_spell_scope(
                        preview, 6266, level=12
                    ), preview.effect_resolution(), cast_event_scope(dispatcher, plan):
                        paid(dispatcher, plan)
                        breeze(dispatcher, plan)
                        outcome = tuple(
                            dispatcher.execute(
                                EffectInvocation(
                                    ref,
                                    12,
                                    7,
                                    -7,
                                    (1, 0, 0),
                                    native_explicit_target=False,
                                    native_context_hex=normal_root_context(
                                        origin,
                                        caster_id=7,
                                        spell_id=6266,
                                        level=12,
                                    ).hex(),
                                )
                            )
                            for ref in (1, 2)
                        )
                else:
                    outcome = execute_entry_roots(
                        preview,
                        plan,
                        caster,
                        dispatcher,
                        (1, 2),
                        route="player",
                        execution_origin=origin,
                    )
            except RuntimeError as raised:
                self.assertIs(raised, failure)
                error = str(raised)
                # A failed native scope never returns a successful transaction,
                # even if its local root tuple existed before cleanup failed.
                outcome = None
        self.assertEqual(preview.native_active_spell_id, 900)
        self.assertIs(preview.native_active_spell_container, old_container)
        from wakfu_server.combat_attack_preparation import _scope

        self.assertIsNone(_scope.get())
        return trace, outcome, error

    def test_native_success_scope_order_includes_after_events_before_restoration(self):
        expected = self._execute("historical")
        actual = self._execute("shared")
        self.assertEqual(actual, expected)
        self.assertEqual(
            [row[0] for row in actual[0]],
            [
                "resolution.enter",
                "event1024",
                "paid",
                "breeze",
                "root1",
                "root2",
                "settle",
                "event1025",
                "event1025.remove",
                "resolution.exit",
            ],
        )
        self.assertTrue(all(row[-1]["spell_id"] == 6266 for row in actual[0]))

    def test_failure_at_each_native_scope_stage_restores_and_preserves_exception(self):
        for point in (
            "resolution.enter",
            "event1024",
            "paid",
            "breeze",
            "root1",
            "root2",
            "settle",
            "event1025",
            "event1025.remove",
            "resolution.exit",
        ):
            with self.subTest(point=point):
                historical = self._execute("historical", point)
                shared = self._execute("shared", point)
                self.assertEqual(shared, historical)
                self.assertEqual(shared[2], "entry failure: " + point)
                if point in ("paid", "breeze", "root1", "root2"):
                    self.assertNotIn("event1025", [row[0] for row in shared[0]])


if __name__ == "__main__":
    unittest.main()
