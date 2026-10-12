"""Real dispatcher cleanup obeys the invocation-only handler contract."""
import copy
import unittest
import test_combat_damage_handler as fixtures
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_conditions import ConditionContext


class DamageDispatchCleanupTests(unittest.TestCase):
    def fixture(self):
        case = fixtures.DamageHandlerTests()
        case.setUp()

        class Events:
            def phase(self, *args, **kwargs):
                pass

        case.handler.event_lifecycle = Events()
        listener = {"effect_class": 1, "invocation": {"reference": 339483}}
        case.fight.native_owned_group_effects = {88: listener}
        effect = dict(
            case.effect,
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            criteria="",
            children=[],
        )
        dispatcher = EffectDispatcher(
            {"339483": effect},
            {1: case.handler},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: case.fight.actors[identity].position,
            prepare_effect=case.handler.prepare,
        )
        return case, dispatcher, listener

    def assert_clean(self, case, listener):
        self.assertEqual(case.handler.prepared, {})
        self.assertEqual(case.handler.final_modifiers, {})
        self.assertEqual(case.handler.runner_modifiers, {})
        self.assertIs(case.fight.native_owned_group_effects[88], listener)
        self.assertEqual(
            listener, {"effect_class": 1, "invocation": {"reference": 339483}}
        )

    def test_real_dispatch_success_cleans_prepared_without_removing_listener(self):
        case, dispatcher, listener = self.fixture()
        self.assertTrue(dispatcher.execute(case.invocation))
        self.assertTrue(case.packets)
        self.assert_clean(case, listener)

    def test_real_dispatch_preparation_exception_cleans_modifiers_and_listener(self):
        case, dispatcher, listener = self.fixture()
        actor = case.fight.actors[-7]
        ledger = actor.state_ledger
        before = copy.deepcopy(
            {
                key: value
                for key, value in actor.__dict__.items()
                if key != "state_ledger"
            }
        )
        entries = tuple(ledger.entries)

        def fail(*args, **kwargs):
            raise RuntimeError("calculation failure witness")

        case.handler._calculate = fail
        with self.assertRaisesRegex(RuntimeError, "calculation failure witness"):
            dispatcher.execute(case.invocation)
        self.assertEqual(
            {
                key: value
                for key, value in actor.__dict__.items()
                if key != "state_ledger"
            },
            before,
        )
        self.assertIs(actor.state_ledger, ledger)
        self.assertEqual(tuple(ledger.entries), entries)
        self.assertEqual(case.packets, [])
        self.assert_clean(case, listener)

    def test_real_dispatch_exception_after_preparation_cleans_runner_scope(self):
        case, dispatcher, listener = self.fixture()
        before_hp = case.fight.actors[-7].hp

        def fail(*args):
            raise RuntimeError("probability boundary failure witness")

        dispatcher.probability_accepts = fail
        with self.assertRaisesRegex(
            RuntimeError, "probability boundary failure witness"
        ):
            dispatcher.execute(case.invocation)
        self.assertEqual(case.fight.actors[-7].hp, before_hp)
        self.assertEqual(case.packets, [])
        self.assert_clean(case, listener)
