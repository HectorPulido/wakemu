"""Real eWO resource reductions preserve native phase events and UID custody."""
from copy import deepcopy
from dataclasses import replace
import unittest

import test_combat_maximum_resource as resource_fixture
import test_combat_maximum_reduction_area as area_fixture
from test_combat_equipment_operation_capability import _effect
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_maximum_resource import NativeMaximumReductionHandler
from wakfu_server.combat_stat_handler import NativeStatHandler


class MaximumReductionEventPipelineTests(unittest.TestCase):
    def test_native_resource_phases_mutation_muted_area_chance_and_cleanup(self):
        def dispatch(handler, definition, invocation, fight):
            return EffectDispatcher(
                {str(invocation.reference): definition},
                {definition["effect_class"]: handler},
                resolve=lambda _definition, selected: (selected,),
                condition_context=lambda _invocation: ConditionContext({}),
                probability_accepts=lambda *_: True,
                group_cells=lambda *_: (),
                actor_position=lambda identity: fight.actors[identity].position,
                prepare_effect=handler.prepare,
            ).execute(invocation)

        # These are original eWO PC2/3/4 identifiers, not item-specific events.
        for family, stat, maximum_loss, current_loss in (
            (56, 2, 78, 77),
            (57, 3, 80, 79),
            (192, 4, 70, 68),
        ):
            for mode in (
                "ordinary",
                "zero",
                "no-current-change",
                "mutable",
                "mutable-trigger",
                "cancel",
                "chance",
                "phase-error",
            ):
                with self.subTest(family=family, mode=mode):
                    fixture = resource_fixture.MaximumResourceTests()
                    fixture.setUp()
                    fixture.actor.wp = fixture.actor.effect_stats[4]
                    live = [True]
                    phases, registered, rolls = [], [], []
                    listener = {"reference": 999, "uid": 88}
                    fixture.fight.native_owned_group_effects = {88: listener}
                    handler = NativeMaximumReductionHandler(
                        fixture.fight,
                        fixture.packets,
                        action_id=2,
                        allocate_uid=fixture.handler.allocate_uid,
                        context=lambda *args: replace(
                            fixture.handler.context(*args),
                            executable=live[0],
                            trigger_value=2 if mode == "mutable-trigger" else None,
                        ),
                        probability=lambda chance, invocation: rolls.append(chance)
                        or False,
                        rng=lambda: 0.0,
                    )
                    amount = 0 if mode == "zero" else 1
                    definition = _effect(family, (float(amount), 0.0))
                    if mode == "chance":
                        definition["parameters"] = [1.0, 0.0, 50.0, 0.0]
                        definition["parameter_count"] = 2
                    if mode == "no-current-change":
                        fixture.actor.effect_stats[stat] = 1
                        setattr(fixture.actor, {2: "ap", 3: "mp", 4: "wp"}[stat], 1)
                        definition["parameters"] = [
                            1.0,
                            0.0,
                            -1.0,
                            0.0,
                            1.0,
                            0.0,
                            0.0,
                            0.0,
                        ]
                        definition["parameter_count"] = 4
                    before = (
                        fixture.actor.effect_stats[stat],
                        fixture.actor.effect_maxima[stat],
                    )

                    class Events:
                        def phase(self, effect, invocation, **data):
                            phases.append(
                                (
                                    data["channel"],
                                    data["value"],
                                    tuple(data["_event_ids"]),
                                )
                            )
                            if data["channel"] == 2 and mode == "mutable":
                                data["runner_modifier"].mutate(1, 2, True)
                            if data["channel"] == 2 and mode == "mutable-trigger":
                                data["runner_modifier"].mutate(1, -1, True)
                            if data["channel"] == 2 and mode == "cancel":
                                live[0] = False
                            if mode == "phase-error":
                                raise RuntimeError("declared listener failure")

                        def register_applied(self, effect, invocation, uid):
                            registered.append(uid)

                    handler.event_lifecycle = Events()
                    if mode == "phase-error":
                        with self.assertRaisesRegex(
                            RuntimeError, "declared listener failure"
                        ):
                            dispatch(
                                handler, definition, fixture.invocation, fixture.fight
                            )
                    else:
                        applied = dispatch(
                            handler, definition, fixture.invocation, fixture.fight
                        )
                        self.assertEqual(applied, mode not in ("cancel", "chance"))
                    self.assertEqual(phases[0], (1, 0, (0, maximum_loss)))
                    self.assertFalse(handler.prepared_maxima)
                    self.assertFalse(handler.runner_amounts)
                    self.assertIs(
                        fixture.fight.native_owned_group_effects[88], listener
                    )
                    if mode in ("cancel", "chance", "phase-error"):
                        self.assertEqual(
                            (
                                fixture.actor.effect_stats[stat],
                                fixture.actor.effect_maxima[stat],
                            ),
                            before,
                        )
                        self.assertEqual(
                            (
                                fixture.packets,
                                fixture.fight.owned_stat_effects,
                                registered,
                            ),
                            ([], {}, []),
                        )
                        if mode == "chance":
                            self.assertEqual(rolls, [50])
                            self.assertEqual([phase[0] for phase in phases], [1])
                        continue
                    self.assertEqual([phase[0] for phase in phases], [1, 2, 3, 4])
                    self.assertEqual(phases[1][2], (0, maximum_loss))
                    expected = (
                        (0,)
                        if mode == "zero"
                        else (
                            (0, maximum_loss)
                            if mode == "no-current-change"
                            else tuple(sorted((0, maximum_loss, current_loss)))
                        )
                    )
                    self.assertEqual(
                        [phase[2] for phase in phases[2:]], [expected, expected]
                    )
                    actual = 2 if mode in ("mutable", "mutable-trigger") else amount
                    self.assertEqual(registered, [101])
                    self.assertEqual(
                        fixture.fight.owned_stat_effects[101]["actual"], actual
                    )
                    self.assertEqual(
                        fixture.actor.effect_maxima[stat], before[1] - actual
                    )
                    self.assertEqual(
                        fixture.actor.effect_stats[stat],
                        before[0]
                        if mode == "no-current-change"
                        else before[0] - actual,
                    )
                    NativeStatHandler(
                        fixture.fight,
                        fixture.packets,
                        {"effects": {}},
                        action_id=2,
                        allocate_uid=None,
                        context=None,
                    ).remove(101)
                    self.assertNotIn(101, fixture.fight.owned_stat_effects)
                    self.assertEqual(
                        [opcode for opcode, _ in fixture.packets], [12613, 13560]
                    )

            # Real faW constructor has HP only: absent AP/MP/WP remains muted,
            # while constructor lifecycle events and retained UID still exist.
            (
                fight,
                handler,
                _,
                packets,
            ) = area_fixture.MaximumReductionAreaTests().create()
            events = []

            class AreaEvents:
                def phase(self, effect, invocation, **data):
                    events.append((data["channel"], tuple(data["_event_ids"])))

                def register_applied(self, *args):
                    pass

            handler.rng = lambda: 0.0
            handler.event_lifecycle = AreaEvents()
            row = fight.native_effect_areas[901]
            before = area_fixture.MaximumReductionAreaTests().snapshot(row)
            invocation = EffectInvocation(319412, 200, 7, 901, (2, 3, 0))
            self.assertTrue(
                dispatch(handler, _effect(family, (6.0, 0.0)), invocation, fight)
            )
            self.assertEqual(
                events, [(phase, (0, maximum_loss)) for phase in (1, 2, 3, 4)]
            )
            self.assertEqual(packets, [])
            self.assertEqual(
                area_fixture.MaximumReductionAreaTests().snapshot(row), before
            )
            uid = next(iter(fight.owned_stat_effects))
            NativeStatHandler(
                fight,
                packets,
                {"effects": {}},
                action_id=2,
                allocate_uid=None,
                context=None,
            ).remove(uid)
            self.assertEqual([opcode for opcode, _ in packets], [13560])
            self.assertFalse(handler.prepared_maxima)
            self.assertFalse(handler.runner_amounts)
