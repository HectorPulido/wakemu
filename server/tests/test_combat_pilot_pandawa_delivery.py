"""Owned native Pandawa carry/throw delivery on the current spatial boundary."""
import os
import unittest

from tools.combat_movement_differential import observe_movement
from wakfu_server.combat_protocol_reconstruction import decode_packet


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PilotPandawaDeliveryTests(unittest.TestCase):
    def test_actual_owned_carry_then_throw_packets_preserve_native_prerequisites(self):
        from test_combat_pandawa_runtime import PandawaRuntimeTests
        from test_combat_spatial_pilot_new_attack import (
            detached_native_world,
            native_world_observation,
        )

        helper = PandawaRuntimeTests()
        template = helper.fixture()
        stages = {}

        def state(fight):
            from wakfu_server.combat_carrying import carrying_relations

            for actor in fight.actors.values():
                # The canonical native relation authority validates fresh
                # absent fields as null and rejects unregistered/stale pairs.
                carrying_relations(fight, actor)
            return dict(
                positions={
                    actor.id: tuple(actor.position) for actor in fight.actors.values()
                },
                relations={
                    actor.id: dict(
                        carrier=getattr(actor, "native_carrier_id", None),
                        carried=getattr(actor, "native_carried_actor_id", None),
                    )
                    for actor in fight.actors.values()
                },
                resources={
                    actor.id: dict(
                        ap=actor.ap, mp=actor.mp, effect_stats=dict(actor.effect_stats)
                    )
                    for actor in fight.actors.values()
                },
            )

        def factory(context):
            world = detached_native_world(
                dict(
                    character=template[0],
                    monster=template[1],
                    fight=template[2],
                    deck=template[3],
                )
            )
            context.rng.setstate(template[4].getstate())
            return world

        def operation():
            def execute(world, inputs, context):
                fight = world["fight"]
                fixture = (
                    world["character"],
                    world["monster"],
                    fight,
                    world["deck"],
                    context.rng,
                )
                observed = []
                for spell, target, action_id in (
                    (6847, fight.actors[-7].position, 2),
                    (6848, None, 3),
                ):
                    before = state(fixture[2])
                    transaction = helper.cast(
                        fixture, spell, target=target, action_id=action_id
                    )
                    after = state(transaction.fight)
                    carry_packets = []
                    for opcode, payload in transaction.packets:
                        context.packet("pandawa-participant", opcode, payload)
                        if opcode == 12613:
                            decoded = decode_packet(opcode, payload)
                            if decoded["effect"]["family"] in (333, 334):
                                carry_packets.append(
                                    dict(opcode=opcode, payload_hex=payload.hex())
                                )
                    self.assertEqual(len(carry_packets), 1)
                    for event in transaction.events:
                        context.event(event)
                    observed.append(
                        dict(
                            spell=spell,
                            before=before,
                            after=after,
                            packets=carry_packets,
                        )
                    )
                    fixture = helper.adopt(fixture, transaction.fight)
                carried = observed[0]["after"]
                self.assertEqual(carried["relations"][7]["carried"], -7)
                self.assertEqual(carried["relations"][-7]["carrier"], 7)
                self.assertEqual(carried["positions"][7], carried["positions"][-7])
                self.assertIsNone(observed[1]["after"]["relations"][7]["carried"])
                self.assertIsNone(observed[1]["after"]["relations"][-7]["carrier"])
                self.assertNotEqual(
                    observed[1]["after"]["positions"][7],
                    observed[1]["after"]["positions"][-7],
                )
                stages["current"] = observed
                world["fight"] = fixture[2]
                return observed

            return execute

        def project(world):
            if (
                getattr(world["fight"], "native_rail_movement_authority", None)
                is not None
            ):
                return native_world_observation(world["fight"])
            result = dict(vars(world["fight"]))
            return result

        report = observe_movement(
            case_id="owned-pandawa-6847-6848-delivery",
            make_world=factory,
            operation=operation(),
            project_state=project,
        )
        self.assertTrue(report["action_succeeded"], report)
        self.carry_delivery_report = dict(
            schema="wakemu-current-pandawa-delivery-v2",
            observation=report,
            stages=stages,
        )


if __name__ == "__main__":
    unittest.main()
