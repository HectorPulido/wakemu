"""Complete native Qf view at L3, before the handler wrapper returns."""
import unittest
from types import SimpleNamespace
from copy import deepcopy
import test_combat_stat_handler as fixtures
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    run_effect_transaction,
)
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.fight_checkpoint_store import snapshot


class AppliedRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StatHandlerTests()
        self.fixture.setUp()
        self.fight = self.fixture.fight
        self.fight.native_effect_uid_next = 900
        # Synthetic test definition exercises ownership/ordering, not a claim
        # about a particular spell's clock or subscription.
        self.effect = dict(
            effect_class=120,
            parameters=[10, 0],
            parameter_count=1,
            minimum_level=1,
            maximum_level=200,
            variant=0,
            native_execution_mode=0,
            target_masks=[None] * 7,
            children=[],
            criteria="",
            probability_base=100,
            probability_per_level=0,
        )
        self.invocation = EffectInvocation(123, 1, 7, 7, (0, 0, 0))

    def runtime(self, preview, *, fail=False):
        packets, observed = [], []
        metadata = dict(
            states={},
            spells={},
            effects={
                "123": dict(
                    effect_class=120,
                    parameters=[10, 0],
                    minimum_level=1,
                    maximum_level=200,
                    variant=0,
                    definition_type=0,
                    definition_dispellable=False,
                    owner_on_caster=False,
                    subscription=False,
                )
            },
        )
        retention = NativeRetainedRuntime(
            preview,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=None,
            metadata=metadata,
        )
        handler = NativeStatHandler(
            preview,
            packets,
            self.fixture.registry,
            action_id=1,
            allocate_uid=preview.allocate_effect_uid,
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0.5,
        )

        def phase(effect, invocation, *, channel, uid, **kwargs):
            if channel in (3, 4):
                view = retention.view()
                observed.append((channel, uid, tuple(e.uid for e in view.entries)))
                self.assertIn(uid, preview.native_retained_records)
                if fail:
                    raise ValueError("Injected post-registration failure")

        handler.event_lifecycle = SimpleNamespace(
            phase=phase, register_applied=retention.register_applied_stat
        )
        retention.stat_handler = handler
        return retention, handler, packets, observed

    def test_post_producer_sees_exact_registration_before_wrapper_return(self):
        retention, handler, packets, observed = self.runtime(self.fight)
        inv = handler.prepare(self.effect, {}, self.invocation)
        self.assertTrue(retention.wrap(handler)(self.effect, {}, inv))
        uid = inv.native_running_uid
        self.assertEqual(observed, [(3, uid, (uid,)), (4, uid, (uid,))])
        self.assertEqual(self.fight.native_retained_order, [uid])
        with self.assertRaisesRegex(ValueError, "already registered"):
            retention.register_applied_stat(self.effect, inv, uid)
        # Registering this exact UID never licenses unrelated unknown rows.
        row = deepcopy(self.fight.owned_stat_effects[uid])
        row["uid"] = uid + 100
        self.fight.owned_stat_effects[uid + 100] = row
        with self.assertRaisesRegex(ValueError, "Unregistered native retained effects"):
            retention.view()

    def test_failed_post_producer_rolls_back_resource_and_complete_registry(self):
        before = snapshot(self.fight)

        def factory(preview):
            retention, handler, _, _ = self.runtime(preview, fail=True)
            dispatcher = EffectDispatcher(
                {"123": self.effect},
                {120: retention.wrap(handler)},
                resolve=lambda e, i: (i,),
                condition_context=lambda i: ConditionContext({}),
                probability_accepts=lambda *a: True,
                group_cells=lambda *a: (),
                actor_position=lambda identity: preview.actors[identity].position,
            )
            dispatcher.prepare_effect = handler.prepare
            return dispatcher

        with self.assertRaisesRegex(ValueError, "post-registration"):
            run_effect_transaction(self.fight, [self.invocation], factory)
        self.assertEqual(snapshot(self.fight), before)
