"""Focused PT accounting regression through the production import namespace."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation


def effect(kind, parameters=(), *, children=()):
    return {
        "effect_class": kind,
        "parameters": [v for p in parameters for v in (p, 0)],
        "parameter_count": len(parameters),
        "probability_base": 100,
        "probability_per_level": 0,
        "minimum_level": 1,
        "maximum_level": 200,
        "criteria": "",
        "children": list(children),
    }


class Retention:
    def __init__(self, subscriptions=()):
        self.subscriptions = set(subscriptions)
        self.finished = []

    def is_subscription(self, definition, invocation):
        return invocation.reference in self.subscriptions

    def begin_group(self, definition, values, invocation):
        return (definition["effect_class"], invocation.reference)

    def finish_group(self, pending):
        self.finished.append(pending)

    def child_level_context(
        self, definition, values, invocation, *, default_level, event_activation=False
    ):
        return default_level, bytes.fromhex("08001000")

    def probability_bypassed(self, invocation):
        return False


class OrderedPtLimitTests(unittest.TestCase):
    def make_dispatcher(
        self, *, parent_parameters, children, handlers, subscriptions=(91,)
    ):
        effects = {"90": effect(330, parent_parameters, children=children)}
        effects.update(
            {str(ref): effect(304 if ref in subscriptions else 400) for ref in children}
        )
        retention = Retention(subscriptions)
        dispatcher = EffectDispatcher(
            effects,
            {400: handlers},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: SimpleNamespace(),
            probability_accepts=lambda probability, invocation: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (identity, 0, 0),
            group_retention=retention,
            pt_preflight=lambda definition, invocation: True,
        )
        return dispatcher, retention

    def test_registration_does_not_consume_success_limit_but_noop_execution_does(self):
        seen = []

        def handler(definition, values, invocation):
            seen.append(invocation.reference)
            return False  # zero material delta; PT.bas still executed

        dispatcher, retention = self.make_dispatcher(
            parent_parameters=(1, 1, 1, 0, 1, 0),
            children=(91, 92, 93),
            handlers=handler,
        )
        dispatcher.execute(EffectInvocation(90, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(seen, [92])
        self.assertEqual(len(retention.finished), 2)  # parent and subscription

    def test_pt_result_separates_execution_count_from_application_and_legacy_limits(
        self,
    ):
        calls = []

        def handler(definition, values, invocation):
            calls.append(invocation.reference)
            return False

        dispatcher, _ = self.make_dispatcher(
            parent_parameters=(0, 0, 1, 0, 1, 0),
            children=(92,),
            handlers=handler,
            subscriptions=(),
        )
        result = dispatcher.execute_pt(EffectInvocation(92, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(
            (result.present, result.accepted_count, result.applied), (True, 1, False)
        )
        self.assertEqual(calls, [92])

        calls.clear()
        legacy, _ = self.make_dispatcher(
            parent_parameters=(1, 0, 1, 0, 1, 0),
            children=(91, 92),
            handlers=handler,
        )
        legacy.execute(EffectInvocation(90, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(calls, [])  # call limit still counts registration

        calls.clear()
        unlimited, _ = self.make_dispatcher(
            parent_parameters=(0, 1, 1, 0, 1, 0),
            children=(91, 92, 93),
            handlers=lambda definition, values, invocation: calls.append(
                invocation.reference
            )
            is None,
        )
        unlimited.execute(EffectInvocation(90, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(calls, [92, 93])

    def test_child_rebind_metadata_and_base_uid_survive_group_dispatch(self):
        selected = []

        def handler(definition, values, invocation):
            selected.append(invocation)
            return False

        dispatcher, _ = self.make_dispatcher(
            parent_parameters=(0, 0, 1, 0, 1, 1),
            children=(92,),
            handlers=handler,
            subscriptions=(),
        )
        dispatcher.execute(EffectInvocation(90, 1, 7, -7, (1, 0, 0), base_uid=55))
        self.assertEqual(len(selected), 1)
        child = selected[0]
        self.assertEqual(
            (child.caster_id, child.target_id, child.base_uid), (-7, -7, 55)
        )
        self.assertTrue(child.wakemu_fresh_child_selection)
        self.assertTrue(child.wakemu_rebound_child_selection)


if __name__ == "__main__":
    unittest.main(verbosity=2)
