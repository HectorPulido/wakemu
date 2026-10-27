"""Declared Wakemu max-change policy on the existing generic eWU setters.

The recording lifecycle is a test observer, not an admission provider. Actual
native PA arithmetic, payloads, retained registration and preview rollback run
unchanged. This does not claim the missing original publishers were recovered.
"""

from copy import deepcopy
from types import SimpleNamespace
import unittest

import test_combat_parameter_maximum as fixture
from wakfu_server.combat_effect_dispatch import EffectInvocation, run_effect_transaction
from wakfu_server.combat_maximum_characteristic_events import (
    maximum_event_ids,
    notify,
)
from wakfu_server.combat_parameter_maximum import (
    NativeParameterMaximumHandler,
    remove_parameter_maximum,
)
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_stat_handler import StatExecutionContext


class _Lifecycle:
    def __init__(self, fight, packets, effect, reference):
        self.preview, self.events, self.fail_channel = fight, [], None
        self.intent_events, self.on_phase = [], None
        metadata = dict(
            effects={
                str(reference): dict(
                    effect_class=effect["effect_class"],
                    variant=0,
                    minimum_level=0,
                    maximum_level=32767,
                    parameters=effect["parameters"],
                    definition_type=0,
                    definition_dispellable=False,
                    owner_on_caster=False,
                    subscription=False,
                )
            },
            states={},
        )
        self.retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={
                "native_retained_container": dict(
                    present=True,
                    type=12,
                    id=10272,
                    level=20,
                    native_kind="item",
                    is_spell=False,
                )
            },
            state_catalog={"effects": {}, "states": {}},
            action_id=1,
            timing=None,
            metadata=metadata,
        )

    def register_applied(self, effect, invocation, uid):
        self.retention.register_applied_stat(effect, invocation, uid)

    def phase(self, effect, invocation, **fields):
        if fields["channel"] == self.fail_channel:
            raise ValueError("Declared reaction failure after maximum mutation")
        events = self.intent_events if fields["channel"] == 2 else self.events
        events.append(
            dict(
                fields,
                caster=invocation.caster_id,
                target=invocation.target_id,
                reference=invocation.reference,
                maximum=deepcopy(
                    self.preview.actors[invocation.target_id].effect_maxima
                ),
            )
        )
        if self.on_phase is not None:
            self.on_phase(effect, invocation, fields)


def _source(stat, family, amount):
    return dict(
        effect_class=family,
        parameters=[float(stat), 0.0, float(amount), 0.0],
        variant=0,
        minimum_level=0,
        maximum_level=32767,
        native_execution_mode=0,
        native_effect_flags=[],
        target_masks=[None] * 7,
    )


def _handler(fight, packets, effect, reference):
    handler = NativeParameterMaximumHandler(
        fight,
        packets,
        action_id=1,
        allocate_uid=lambda: 101,
        context=lambda *_: StatExecutionContext(True, True, None, True, None, None),
    )
    handler.event_lifecycle = _Lifecycle(fight, packets, effect, reference)
    return handler


def _fixture(stat, family, amount, *, maximum=10):
    base = fixture.ParameterMaximumTests()
    base.setUp()
    actor = base.actor
    for field, value in (
        ("effect_stats", 5),
        ("effect_maxima", maximum),
        ("effect_base_maxima", maximum),
        ("effect_minima", 0),
        ("effect_base_minima", 0),
        ("effect_percentages", 0),
    ):
        getattr(actor, field)[stat] = value
    effect = _source(stat, family, amount)
    invocation = EffectInvocation(
        345699 if family == 1201 else 345698, 1, 7, 7, (0, 0, 0)
    )
    handler = _handler(base.fight, base.packets, effect, invocation.reference)
    return base, effect, invocation, handler


class MaximumCharacteristicEventTests(unittest.TestCase):
    def test_l2_operation_intention_precedes_real_setter_and_remains_transactional(
        self,
    ):
        # Reuse the directly affected post-mutation/inverse controls in this
        # single qualification rather than repeat an unrelated combat suite.
        self.test_actual_setter_inverse_noop_identity_and_preview_rollback()

        for family, amount, intent, outcome in (
            (1201, 3, 2257, 2257),
            (1202, 3, 2258, 2258),
            (1201, -3, 2257, 2258),  # Native constructor direction is intentional.
        ):
            base, effect, invocation, handler = _fixture(86, family, amount)
            allocations = []
            handler.allocate_uid = lambda: allocations.append(101) or 101
            handler(effect, {}, invocation)
            lifecycle = handler.event_lifecycle
            self.assertEqual(allocations, [101])
            self.assertEqual(len(lifecycle.intent_events), 1)
            before = lifecycle.intent_events[0]
            self.assertEqual(
                (
                    before["channel"],
                    before["_event_ids"],
                    before["value"],
                    before["uid"],
                ),
                (2, (intent,), amount, 101),
            )
            self.assertEqual(
                (before["caster"], before["target"], before["maximum"][86]), (7, 7, 10)
            )
            self.assertEqual(
                [e["_event_ids"] for e in lifecycle.events], [(outcome,), (outcome,)]
            )
            remove_parameter_maximum(handler, 101)
            self.assertEqual(
                len(lifecycle.intent_events), 1
            )  # Inverse is not a new L2 application.

        # A real preapplication reaction changes the PA through the existing
        # generic setter; the original setter must read the new max afterwards.
        base, effect, invocation, handler = _fixture(86, 1201, 3)
        lifecycle = handler.event_lifecycle

        def clamp_reaction(_effect, _invocation, fields):
            if fields["channel"] != 2:
                return
            self.assertEqual(base.actor.effect_maxima[86], 10)
            self.assertEqual(base.packets, [])
            reaction = NativeParameterMaximumHandler(
                base.fight,
                base.packets,
                action_id=1,
                allocate_uid=lambda: 201,
                context=lambda *_: StatExecutionContext(
                    executable=True,
                    source_guards_verified=True,
                    trigger_value=None,
                    retained=False,
                    timing_payload=None,
                    timer=None,
                ),
            )
            reaction(
                _source(86, 1201, 990), {}, EffectInvocation(345699, 1, 7, 7, (0, 0, 0))
            )

        lifecycle.on_phase = clamp_reaction
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(base.actor.effect_maxima[86], 1000)
        self.assertEqual(len(lifecycle.intent_events), 1)
        self.assertEqual(
            lifecycle.events, []
        )  # Original intended change became a no-op.
        self.assertEqual([p[0] for p in base.packets], [13497, 13497])

        for maximum, amount in ((1000, 3), (10, 0)):
            base, effect, invocation, handler = _fixture(
                86, 1201, amount, maximum=maximum
            )
            handler(effect, {}, invocation)
            self.assertEqual(
                [e["_event_ids"] for e in handler.event_lifecycle.intent_events],
                [(2257,)],
            )
            self.assertEqual(handler.event_lifecycle.events, [])

        # A guard changed by an L2 reaction cancels the original application;
        # its intent is real but no PA mutation, application packet or row exists.
        base, effect, invocation, handler = _fixture(86, 1202, 3)

        def cancel_reaction(_effect, _invocation, fields):
            if fields["channel"] == 2:
                handler.context = lambda *_: StatExecutionContext(
                    False, True, None, True, None, None
                )

        handler.event_lifecycle.on_phase = cancel_reaction
        self.assertFalse(handler(effect, {}, invocation))
        self.assertEqual(base.actor.effect_maxima[86], 10)
        self.assertEqual(base.fight.owned_stat_effects, {})
        self.assertEqual(base.packets, [])
        self.assertEqual(
            [e["_event_ids"] for e in handler.event_lifecycle.intent_events], [(2258,)]
        )
        self.assertEqual(handler.event_lifecycle.events, [])

        # A failed reaction rolls back even its own already staged PA mutation.
        base, effect, invocation, handler = _fixture(86, 1201, 3)
        before = deepcopy(base.fight)
        staged = []

        def factory(preview):
            packets = []
            current = _handler(preview, packets, effect, invocation.reference)

            def failed_reaction(_effect, _invocation, fields):
                if fields["channel"] != 2:
                    return
                reaction = NativeParameterMaximumHandler(
                    preview,
                    packets,
                    action_id=1,
                    allocate_uid=lambda: 201,
                    context=lambda *_: StatExecutionContext(
                        executable=True,
                        source_guards_verified=True,
                        trigger_value=None,
                        retained=False,
                        timing_payload=None,
                        timer=None,
                    ),
                )
                reaction(
                    _source(86, 1202, 2),
                    {},
                    EffectInvocation(345698, 1, 7, 7, (0, 0, 0)),
                )
                raise ValueError("L2 reaction rejects the transaction")

            current.event_lifecycle.on_phase = failed_reaction
            staged.append(packets)
            return SimpleNamespace(execute=lambda i: current(effect, {}, i))

        with self.assertRaisesRegex(ValueError, "L2 reaction rejects"):
            run_effect_transaction(base.fight, [invocation], factory)
        self.assertEqual(
            base.fight.actors[7].effect_maxima, before.actors[7].effect_maxima
        )
        self.assertEqual(base.fight.owned_stat_effects, before.owned_stat_effects)
        self.assertEqual(base.packets, [])
        self.assertEqual([p[0] for p in staged[0]], [13497])

    def test_actual_setter_inverse_noop_identity_and_preview_rollback(self):
        for stat, family, applied, removed in (
            (11, 1201, (), (208,)),
            (11, 1202, (208,), ()),
            (86, 1201, (2257,), (2258,)),
            (86, 1202, (2258,), (2257,)),
        ):
            with self.subTest(stat=stat, family=family):
                base, effect, invocation, handler = _fixture(stat, family, 3)
                self.assertTrue(handler(effect, {}, invocation))
                lifecycle = handler.event_lifecycle
                self.assertEqual(
                    [tuple(e["_event_ids"]) for e in lifecycle.events],
                    [applied] * 2 if applied else [],
                )
                for event in lifecycle.events:
                    self.assertEqual(
                        (
                            event["caster"],
                            event["target"],
                            event["uid"],
                            event["value"],
                        ),
                        (7, 7, 101, 3),
                    )
                    self.assertEqual(
                        event["maximum"][stat], 13 if family == 1201 else 7
                    )
                self.assertEqual([p[0] for p in base.packets], [13497])
                before = len(lifecycle.events)
                remove_parameter_maximum(handler, 101)
                self.assertEqual(base.actor.effect_maxima[stat], 10)
                self.assertEqual(
                    [tuple(e["_event_ids"]) for e in lifecycle.events[before:]],
                    [removed] * 2 if removed else [],
                )
                self.assertEqual([p[0] for p in base.packets], [13497, 13560])
                for event in lifecycle.events[before:]:
                    self.assertEqual(
                        event["value"], 3
                    )  # Original Qe, not a fabricated inverse amount.

        # Native eWU cap: requested +10 does not change a Willpower max of1000.
        # Its own inverse uses effective max as input and really changes it to990.
        base, effect, invocation, handler = _fixture(86, 1201, 10, maximum=1000)
        handler(effect, {}, invocation)
        self.assertEqual(handler.event_lifecycle.events, [])
        self.assertEqual(base.actor.effect_maxima[86], 1000)
        remove_parameter_maximum(handler, 101)
        self.assertEqual(base.actor.effect_maxima[86], 990)
        self.assertEqual(
            [e["_event_ids"] for e in handler.event_lifecycle.events],
            [(2258,), (2258,)],
        )

        # The native subtract-underflow stores zero; preserve it and its inverse.
        base, effect, invocation, handler = _fixture(86, 1202, 50)
        handler(effect, {}, invocation)
        self.assertEqual(base.fight.owned_stat_effects[101]["actual"], 0)
        self.assertEqual([e["value"] for e in handler.event_lifecycle.events], [0, 0])
        before = len(handler.event_lifecycle.events)
        remove_parameter_maximum(handler, 101)
        self.assertEqual(base.actor.effect_maxima[86], 0)
        self.assertEqual(len(handler.event_lifecycle.events), before)

        base, effect, invocation, handler = _fixture(86, 1201, 0)
        handler(effect, {}, invocation)
        base.actor.effect_stats[86] = 2  # Only current changes; max remains10.
        self.assertFalse(
            notify(
                handler.event_lifecycle,
                base.fight,
                base.actor,
                86,
                10,
                effect=effect,
                invocation=invocation,
                uid=101,
                value=0,
            )
        )
        self.assertEqual(handler.event_lifecycle.events, [])
        with self.assertRaisesRegex(ValueError, "actual registered setter PA"):
            notify(
                handler.event_lifecycle,
                base.fight,
                deepcopy(base.actor),
                86,
                9,
                effect=effect,
                invocation=invocation,
                uid=101,
                value=0,
            )
        actual_max = base.actor.effect_maxima.pop(86)
        with self.assertRaisesRegex(ValueError, "actual registered setter PA"):
            notify(
                handler.event_lifecycle,
                base.fight,
                base.actor,
                86,
                9,
                effect=effect,
                invocation=invocation,
                uid=101,
                value=0,
            )
        base.actor.effect_maxima[86] = actual_max
        self.assertEqual(handler.event_lifecycle.events, [])
        saved = deepcopy(base.fight.owned_stat_effects[101])
        base.fight.owned_stat_effects[101]["maximum_event_source"]["invocation"][
            "caster_id"
        ] = -7
        with self.assertRaisesRegex(ValueError, "original Qe"):
            remove_parameter_maximum(handler, 101)
        self.assertEqual(base.actor.effect_maxima[86], 10)
        self.assertEqual([p[0] for p in base.packets], [13497])
        base.fight.owned_stat_effects[101] = saved

        # Use the real preview boundary: a reaction fails after PA/outbox mutate.
        original = deepcopy(base.fight)
        staged = []
        rollback_effect = _source(86, 1202, 3)

        def factory(preview):
            packets = []
            current = _handler(preview, packets, rollback_effect, 345698)
            current.allocate_uid = lambda: 102
            current.event_lifecycle.fail_channel = 4
            staged.append(packets)
            return SimpleNamespace(execute=lambda i: current(rollback_effect, {}, i))

        with self.assertRaisesRegex(ValueError, "reaction failure"):
            run_effect_transaction(
                base.fight, [EffectInvocation(345698, 1, 7, 7, (0, 0, 0))], factory
            )
        self.assertEqual(
            base.fight.actors[7].effect_maxima, original.actors[7].effect_maxima
        )
        self.assertEqual(base.fight.owned_stat_effects, original.owned_stat_effects)
        self.assertEqual([p[0] for p in base.packets], [13497])
        self.assertEqual(
            [p[0] for p in staged[0]], [13497]
        )  # Staged, never emitted/committed.
        for invalid in ((86, True, 0), (86, 0, 1 << 31), (86, None, 0)):
            with self.assertRaises(ValueError):
                maximum_event_ids(*invalid)
