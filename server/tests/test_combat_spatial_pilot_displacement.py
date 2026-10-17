"""Actual native displacement/carry contracts on the current spatial boundary."""
from copy import deepcopy
import unittest

import test_combat_displacement as fixtures
from tools.combat_movement_differential import observe_movement
from wakfu_server.combat_displacement import NativeDisplacementHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation


class SpatialPilotDisplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def observe_runner(self, reference, cell):
        template = fixtures.NativeDisplacementTests()
        template.setUp()

        def make_world(context):
            return deepcopy(template.preview)

        def operation():
            def execute(fight, inputs, context):
                class PacketJournal(list):
                    def append(self, packet):
                        opcode, payload = packet
                        context.packet("fixture-participant", opcode, payload)
                        super().append(packet)

                original_positions = {
                    key: actor.position for key, actor in fight.actors.items()
                }
                original_resources = {
                    key: (actor.hp, actor.ap, actor.mp)
                    for key, actor in fight.actors.items()
                }
                packets = PacketJournal()
                handler = NativeDisplacementHandler(
                    fight,
                    packets,
                    action_id=1,
                    allocate_uid=fight.allocate_effect_uid,
                    authority=deepcopy(template.authority),
                    selected_surface=template.selected_surface,
                    draw_direction=lambda: context.rng.randint(1, 4),
                )
                events = []

                class AreaObserver:
                    def movement(self, actor_id, *, from_cell, to_cell):
                        events.append((actor_id, from_cell, to_cell))
                        context.event(("area-transition", actor_id, from_cell, to_cell))

                handler.area_events = AreaObserver()
                result = handler(
                    deepcopy(template.effects[str(reference)]),
                    None,
                    EffectInvocation(reference, 1, 7, -7, cell),
                )
                for event in fight.events:
                    context.event(event)
                self.assertTrue(events)
                expected_target = {
                    358000: (5, 0, 0),
                    326690: (2, 0, 0),
                    351394: (3, 3, 0),
                    349546: original_positions[7],
                }[reference]
                self.assertEqual(fight.actors[-7].position, expected_target)
                self.assertEqual(
                    fight.actors[7].position,
                    original_positions[-7]
                    if reference == 349546
                    else original_positions[7],
                )
                self.assertEqual(
                    {
                        key: (actor.hp, actor.ap, actor.mp)
                        for key, actor in fight.actors.items()
                    },
                    original_resources,
                )
                from wakfu_server.combat_qi_fight import current_registry

                current_registry(fight)
                # Observe the parent packet at callback entry, rather than
                # reconstructing cross-channel order from separate arrays.
                self.assertEqual(context.observations[0]["kind"], "packet")
                return result

            return execute

        def project(fight):
            state = dict(vars(fight))
            return state

        report = observe_movement(
            case_id=f"native-displacement-{reference}",
            make_world=make_world,
            operation=operation(),
            project_state=project,
        )
        self.assertTrue(report["action_succeeded"], report)
        self.assertTrue(report["current"]["packets"])
        self.assertFalse(report["live_delivery"])
        if not hasattr(self, "displacement_reports"):
            self.displacement_reports = []
        self.displacement_reports.append(report)
        return report

    def test_native_push_preserves_full_state_events_and_packets(self):
        self.observe_runner(358000, (4, 0, 0))

    def test_native_pull_preserves_full_state_events_and_packets(self):
        self.observe_runner(326690, (0, 0, 0))

    def test_native_target_teleport_preserves_full_state_events_and_packets(self):
        self.observe_runner(351394, (3, 3, 0))

    def test_native_swap_preserves_full_state_events_and_packets(self):
        self.observe_runner(349546, (4, 0, 0))


class SpatialPilotCarrierDisplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def observe_existing_carrier_case(self, method_name):
        template = fixtures.NativeDisplacementTests(method_name)
        template.setUp()

        def operation():
            def execute(fight, inputs, context):
                case = fixtures.NativeDisplacementTests(method_name)
                # Retain the original assertion body and read-only native
                # definitions, replacing every owned mutable execution object.
                case.__dict__.update(template.__dict__)
                case.preview = fight
                case.authority = deepcopy(template.authority)

                class Packets(list):
                    def append(self, packet):
                        context.packet("fixture-participant", *packet)
                        super().append(packet)

                case.packets = Packets()
                effect_inputs = []

                class RecordingHandler(NativeDisplacementHandler):
                    def __call__(self, effect, values, invocation):
                        effect_inputs.append(
                            {
                                "effect_class": effect["effect_class"],
                                "reference": invocation.reference,
                                "actors": {
                                    identity: {
                                        "position": tuple(actor.position),
                                        "carrier_id": getattr(
                                            actor, "native_carrier_id", None
                                        ),
                                        "carried_id": getattr(
                                            actor, "native_carried_actor_id", None
                                        ),
                                    }
                                    for identity, actor in fight.actors.items()
                                },
                            }
                        )
                        return super().__call__(effect, values, invocation)

                case.handler = RecordingHandler(
                    fight,
                    case.packets,
                    action_id=1,
                    allocate_uid=fight.allocate_effect_uid,
                    authority=case.authority,
                    selected_surface=template.selected_surface,
                )
                getattr(case, method_name)()
                for event in fight.events:
                    context.event(event)
                return {"completed": True, "native_effect_inputs": effect_inputs}

            return execute

        def projection(fight):
            state = dict(vars(fight))
            return state

        report = observe_movement(
            case_id=method_name,
            make_world=lambda context: deepcopy(template.preview),
            operation=operation(),
            project_state=projection,
        )
        self.assertTrue(report["action_succeeded"], report)
        if not hasattr(self, "displacement_reports"):
            self.displacement_reports = []
        self.displacement_reports.append(report)

    def test_forced_carrier_rollback_preserves_native_flag37_and_partner(self):
        self.observe_existing_carrier_case(
            "test_flag37_forced_carrier_preserves_registered_partner"
        )

    def test_swapping_carrier_preserves_partner_and_reserved_slot(self):
        self.observe_existing_carrier_case(
            "test_swap_carrier_moves_registered_partner_without_releasing_it"
        )

    def test_teleporting_carrier_preserves_partner_and_qi(self):
        self.observe_existing_carrier_case(
            "test_teleport_carrier_keeps_registered_partner_and_qi_identity"
        )


if __name__ == "__main__":
    unittest.main()
