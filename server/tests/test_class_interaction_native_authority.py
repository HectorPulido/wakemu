"""Native cross-class event authorities, without invented ownership equivalence.

These are producer/consumer boundary tests. They do not claim a full paid party
rotation: real resource-loss application supplies the event and source value;
published listener metadata and the production criterion evaluator consume it.
"""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_events import subscription_selection
from wakfu_server.combat_ordinary_events import OrdinaryResourceLossEvents
from wakfu_server.combat_resource_loss_handler import NativeResourceLossHandler
from wakfu_server.combat_stat_handler import StatExecutionContext

import test_combat_resource_loss_handler as loss_fixture


def definition(reference, *, retained=False):
    path = (
        "native-retained-effect-metadata.json"
        if retained
        else "combat-state-definitions.json"
    )
    return native_catalog.record(DATA_ROOT / path, "effects", str(reference))


class ClassInteractionNativeAuthorityTests(unittest.TestCase):
    def test_capture_killer_identity_does_not_alias_its_controller_or_root(self):
        listener = definition(326382)
        self.assertEqual(listener["target_masks"][5], [1013])
        owner = ConditionActor(actor_id=7, breed_id=2)
        summon = ConditionActor(
            actor_id=901, is_summon=True, summon_root_id=7, breed_id=87
        )
        context = ConditionContext(
            actors={
                "caster": owner,
                "target": ConditionActor(actor_id=-7, breed_id=4),
                "triggeringcaster": summon,
            },
            triggering_effect_present=True,
            triggering_effect_caster_id=901,
            breed_in_symbiot_query=lambda *_: False,
        )
        # The real listener compares fighter UIDs. Shared account/control/root
        # identity is deliberately irrelevant to its original expression.
        for source_id, expected in ((7, True), (901, False), (8, False), (-1, False)):
            with self.subTest(source_id=source_id):
                self.assertEqual(
                    evaluate_condition(
                        listener["criteria"],
                        replace(context, triggering_effect_caster_id=source_id),
                    ),
                    expected,
                )
        self.assertFalse(
            evaluate_condition(
                listener["criteria"],
                replace(context, triggering_effect_present=False),
            )
        )

    def test_external_ap_mp_loss_uses_actual_amount_and_hostile_source_for_poison(self):
        listeners = [
            (reference, definition(reference), definition(reference, retained=True))
            for reference in (155696, 378033)
        ]
        for stat, family in ((2, 55), (3, 48)):
            for friendly, empty in ((False, False), (True, False), (False, True)):
                with self.subTest(stat=stat, friendly=friendly, empty=empty):
                    helper = loss_fixture.NativeResourceLossHandlerTests()
                    helper.setup_handler()
                    target = helper.fight.actors[-7]
                    if empty:
                        setattr(target, "ap" if stat == 2 else "mp", 0)
                        target.effect_stats[stat] = 0
                    initial = target.ap if stat == 2 else target.mp
                    observed = []
                    test = self

                    class Events:
                        def phase(self, effect, invocation, **data):
                            if data["channel"] != 3:
                                return
                            plan = data["plan"]
                            event_ids = OrdinaryResourceLossEvents.events(
                                SimpleNamespace(synthetic_authority=None),
                                effect,
                                3,
                                plan,
                                invocation,
                            )
                            test.assertEqual(
                                data["value"],
                                initial - (target.ap if stat == 2 else target.mp),
                            )
                            for reference, listener, metadata in listeners:
                                selected = subscription_selection(
                                    masks=listener["target_masks"],
                                    event_ids=event_ids,
                                    channel=31
                                    if metadata["event_global_subscription"]
                                    else 30
                                    if metadata["event_reverse_subscription"]
                                    else 3,
                                    global_subscription=metadata[
                                        "event_global_subscription"
                                    ],
                                    reversed_subscription=metadata[
                                        "event_reverse_subscription"
                                    ],
                                    flags=listener["native_effect_flags"],
                                    source_present=True,
                                )
                                context = ConditionContext(
                                    actors={
                                        "caster": ConditionActor(
                                            actor_id=8, fight_affiliation=0
                                        ),
                                        "target": ConditionActor(
                                            actor_id=-7,
                                            fight_affiliation=0 if friendly else 1,
                                        ),
                                        "triggeringcaster": ConditionActor(
                                            actor_id=invocation.caster_id,
                                            fight_affiliation=0,
                                        ),
                                    },
                                    triggering_effect_present=True,
                                    triggering_effect_caster_id=invocation.caster_id,
                                    triggering_effect_value=data["value"],
                                )
                                if selected == "activate" and evaluate_condition(
                                    listener["criteria"], context
                                ):
                                    observed.append(
                                        (reference, data["value"], invocation.caster_id)
                                    )

                    helper.handler.event_lifecycle = Events()
                    effect = dict(
                        effect_class=family,
                        parameters=[2.0, 0.0],
                        native_effect_flags=[],
                        target_masks=[None] * 7,
                    )
                    self.assertTrue(
                        helper.handler(
                            effect, {}, EffectInvocation(123, 1, 7, -7, (1, 0, 0))
                        )
                    )
                    if friendly or empty:
                        self.assertEqual(observed, [])
                    else:
                        self.assertEqual(observed, [(155696, 1, 7), (378033, 1, 7)])
                        self.assertNotEqual(observed[0][2], 8)  # Foreign poison owner.

    def test_toxins_clock_and_dormant_loss_branches_do_not_become_walk_triggers(self):
        for reference in (378095, 378097):
            listener = definition(reference)
            self.assertEqual(listener["target_masks"][5], [1001])
            for channel, events, expected in (
                (6, (1001,), "activate"),
                (3, (77, 79), None),
                (3, (65, 74), None),
            ):
                with self.subTest(reference=reference, channel=channel, events=events):
                    self.assertEqual(
                        subscription_selection(
                            masks=listener["target_masks"],
                            event_ids=events,
                            channel=channel,
                            global_subscription=False,
                            reversed_subscription=False,
                            flags=listener["native_effect_flags"],
                            source_present=True,
                        ),
                        expected,
                    )
        for reference in (380065, 380067):
            listener = definition(reference)
            context = ConditionContext(
                actors={
                    "target": ConditionActor(fight_affiliation=1),
                    "triggeringcaster": ConditionActor(fight_affiliation=0),
                },
                triggering_effect_present=True,
                triggering_effect_value=1,
            )
            self.assertFalse(evaluate_condition(listener["criteria"], context))
