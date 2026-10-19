"""Fresh eZl lifecycle: Qe phases, runner value, actor reservation and commit."""
import unittest
from random import Random
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_summon import RegisteredSummonAuthority, SummonRegistration
from wakfu_server.combat_summon_handler import NativeSummonHandler
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_summon_codec import summon_descriptor_blob
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_effects import _integer
from wakfu_server.wire import proto_fields


class FreshSummonPhaseTests(unittest.TestCase):
    def make_fight(self):
        caster = Actor(
            7,
            0,
            (0, 0, 0),
            60,
            6,
            3,
            10,
            12,
            owner_id=3,
            controlled=True,
            direction=6,
        )
        opponent = Actor(-7, 1, (4, 0, 0), 60, 6, 3, 5, 12)
        fight = Fight(
            77,
            [caster, opponent],
            {(0, 0, 0), (1, 0, 0), (4, 0, 0)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(4, 0, 0)}},
        )
        # Enter the live phase through the Fight API so its native timeline
        # progress checkpoint is present when the summon joins the order.
        fight.ready(3)
        return fight

    def make_authority(self):
        parent = NativeActorAuthority(
            {"dpr_id": 7, "dpu_id": 7, "buX": False},
            True,
            frozenset({6266}),
            frozenset(),
            False,
            15,
            None,
            None,
            True,
            is_summon=False,
            summon_root_id=7,
            is_carrying=False,
            native_real_level=12,
            native_controller_id=7,
        )

        class OrdinaryAuthority:
            def __call__(self, fight, actor):
                if actor.id != 7 or fight.actors.get(actor.id) is not actor:
                    raise ValueError("Unexpected ordinary caster authority")
                return parent

        return RegisteredSummonAuthority(OrdinaryAuthority())

    def make_builder(self, authority):
        class Builder:
            properties = {"npc": {"999": {"fight_properties": []}}}

            def __init__(self):
                self.created = []

            def __call__(self, fight, specification, caster_id, actor_id, cell):
                actor = Actor(
                    actor_id,
                    specification.team,
                    cell,
                    1,
                    0,
                    0,
                    1,
                    specification.level,
                    owner_id=3,
                    controlled=True,
                    direction=specification.direction,
                )
                actor.native_obstacle_id = 2
                # Match build_npc_snapshot(...).install: fresh eGZ.pHH is
                # false before eZl.c's ordered post-factory lx(true) call.
                actor.native_controlled_by_ai = False
                actor.effect_stats = {1: 1, 2: 0, 3: 0}
                actor.effect_maxima = {1: 1, 2: 0, 3: 0}
                actor.effect_minima = {1: 0, 2: 0, 3: 0}
                actor.effect_frozen = frozenset()
                actor.physical_radius = 0
                actor.spell_ap_cost_modifiers = {}
                actor.spell_range_modifiers = {}
                actor.native_controller_id = caster_id
                actor.native_master_id = caster_id
                actor.native_carrier_id = None
                actor.native_carried_actor_id = None
                actor.native_summon_source = dict(
                    ref=specification.reference,
                    level=specification.level,
                    caster_id=caster_id,
                    controller_id=caster_id,
                    native_relation_source="big.new_bje.fdt_initial_registration",
                )
                metadata = NativeActorAuthority(
                    {
                        "dpr_id": caster_id,
                        "dpu_id": caster_id,
                        "buX": False,
                        "bcN": 2,
                    },
                    False,
                    frozenset(),
                    frozenset(),
                    False,
                    specification.reference,
                    None,
                    None,
                    True,
                    is_summon=True,
                    summon_root_id=caster_id,
                    is_carrying=False,
                    native_real_level=specification.level,
                    native_controller_id=caster_id,
                    native_ai_control_baseline=True,
                    native_controlled_by_ai=False,
                )
                actor.native_summon_source["controller_id"] = caster_id
                registration = SummonRegistration(
                    actor_id, caster_id, caster_id, metadata, frozenset(), frozenset()
                )
                self.created.append((actor, specification, registration))
                return actor, registration

        return Builder()

    def make_handler(self, *, cancel_after_l2=False):
        fight = self.make_fight()
        authority = self.make_authority()
        builder = self.make_builder(authority)
        allocated = []
        next_uid = iter((201, 202))

        def allocate_uid():
            uid = next(next_uid)
            allocated.append(uid)
            return uid

        live = {"executable": True}
        handler = NativeSummonHandler(
            fight,
            [],
            action_id=9,
            allocate_uid=allocate_uid,
            context=lambda effect, invocation: StatExecutionContext(
                live["executable"], True, None, False, b""
            ),
            actor_authority=authority,
            container_level=lambda invocation: (True, 6755),
            container=lambda invocation: ({"container_type": 3}, 6755),
            rng=Random(1).random,
        )
        handler.builder = builder
        observations = []

        class Lifecycle:
            def phase(self, effect, invocation, **kwargs):
                channel = kwargs["channel"]
                observations.append(
                    dict(
                        channel=channel,
                        uid=kwargs["uid"],
                        value=kwargs["value"],
                        event_ids=kwargs["_event_ids"],
                        actor_ids=tuple(sorted(fight.actors)),
                        allocated=tuple(allocated),
                        target_id=invocation.target_id,
                    )
                )
                if cancel_after_l2 and channel == 2:
                    live["executable"] = False

        handler.event_lifecycle = Lifecycle()
        effect = dict(
            effect_class=307,
            native_effect_flags=[],
            target_masks=[[], [], [], [], [], [], []],
        )
        context = _integer(9, 1) + _integer(6, 321)
        invocation = EffectInvocation(
            313167, 1, 7, None, (1, 0, 0), native_context_hex=context.hex()
        )
        values = {"parameters": [999, 20, 0, 3, 0, 0, 1]}
        return (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        )

    def _native_dependencies(self):
        return (
            patch(
                "wakfu_server.combat_summon_handler.native_actor_catalog",
                return_value={"npc_profiles": {"999": {}}},
            ),
            patch(
                "wakfu_server.monsters.reference",
                return_value={"min_level": 1},
            ),
        )

    def test_fresh_runner_phases_reserve_distinct_actor_and_preserve_descriptor(self):
        (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        ) = self.make_handler()
        patches = self._native_dependencies()
        with patches[0], patches[1]:
            prepared = handler.prepare(effect, values, invocation)
            self.assertEqual(allocated, [201, 202])
            self.assertTrue(handler(effect, values, prepared))

        self.assertEqual([row["channel"] for row in observations], [1, 2, 3, 4])
        self.assertEqual([row["uid"] for row in observations], [201, 201, 201, 201])
        self.assertEqual([row["value"] for row in observations], [0, 321, 321, 321])
        self.assertEqual(observations[0]["event_ids"], (0, 2130))
        self.assertEqual(observations[1]["event_ids"], (0, 2130))
        self.assertEqual(observations[0]["allocated"], (201,))
        self.assertEqual(observations[1]["allocated"], (201, 202))
        self.assertTrue(all(row["target_id"] is None for row in observations))
        self.assertEqual(observations[0]["actor_ids"], (-7, 7))
        self.assertEqual(observations[1]["actor_ids"], (-7, 7))
        self.assertIn(202, observations[2]["actor_ids"])
        self.assertIn(202, observations[3]["actor_ids"])
        self.assertEqual(tuple(sorted(fight.actors)), (-7, 7, 202))
        self.assertEqual(len(builder.created), 1)

        actor, specification, _ = builder.created[0]
        self.assertIs(actor.native_controlled_by_ai, True)
        opcode, packet = handler.packets[0]
        self.assertEqual(opcode, 12613)
        self.assertEqual(packet[12], 1)
        self.assertEqual(struct_class(packet), 307)
        body = packet[19:]
        identities = _identity_fields(body, integer_fields=(1, 2, 3, 4, 6))
        self.assertEqual(
            (identities[1], identities[3], identities[4]), (201, 313167, 321)
        )
        outer = dict(proto_fields(body))
        descriptor_wrapper = dict(proto_fields(outer[66]))
        descriptor = descriptor_wrapper[10]
        expected = summon_descriptor_blob(
            specification,
            actor_id=202,
            caster_id=7,
            obstacle_index=actor.native_obstacle_id,
            properties=(),
        )
        self.assertEqual(descriptor, expected)
        additional = dict(proto_fields(outer[98]))
        self.assertEqual(additional[32], 202)
        self.assertNotEqual(identities[1], 202)
        self.assertEqual(handler.prepared_runners, {})

    def test_creation_precedes_constructor_deliveries_for_new_entity(self):
        _, handler, builder, effect, values, invocation, _, _ = self.make_handler()
        prior_packet = (12588, b"prior owned action")
        constructor_packet = (13497, b"new actor initial state")
        handler.packets.append(prior_packet)
        original_create = type(builder).__call__

        def create_with_state(actual_builder, *args, **kwargs):
            result = original_create(actual_builder, *args, **kwargs)
            handler.packets.append(constructor_packet)
            return result

        dependencies = self._native_dependencies()
        with dependencies[0], dependencies[1], patch.object(
            type(builder), "__call__", new=create_with_state
        ):
            prepared = handler.prepare(effect, values, invocation)
            self.assertTrue(handler(effect, values, prepared))
        self.assertEqual(handler.packets[0], prior_packet)
        self.assertEqual(handler.packets[1][0], 12613)
        self.assertEqual(handler.packets[1][1][12], 1)
        self.assertEqual(handler.packets[2], constructor_packet)

    def test_post_l2_cancellation_keeps_uid_reserved_but_creates_no_actor(self):
        (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        ) = self.make_handler(cancel_after_l2=True)
        patches = self._native_dependencies()
        with patches[0], patches[1]:
            prepared = handler.prepare(effect, values, invocation)
            self.assertEqual(allocated, [201, 202])
            self.assertFalse(handler(effect, values, prepared))

        self.assertEqual([row["channel"] for row in observations], [1, 2])
        self.assertEqual([row["value"] for row in observations], [0, 321])
        self.assertTrue(all(row["actor_ids"] == (-7, 7) for row in observations))
        self.assertEqual(tuple(sorted(fight.actors)), (-7, 7))
        self.assertEqual(handler.packets, [])
        self.assertEqual(builder.created, [])
        self.assertEqual(handler.prepared_runners, {})


def struct_class(packet):
    import struct

    return struct.unpack_from(">i", packet, 13)[0]


if __name__ == "__main__":
    unittest.main()
