import unittest
from wakfu_server.combat_copy_characteristic import prepare_copy


class CopyCharacteristicTests(unittest.TestCase):
    def test_owned_application_and_removal_preserve_copied_values(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_copy_characteristic import (
            NativeCopyCharacteristicHandler,
            remove_copied_characteristic,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.wire import proto_fields

        source = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 20, 3, True)
        target = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        fight = Fight(
            8,
            [source, target],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(3)
        for actor, current in ((source, 2), (target, 1)):
            actor.effect_stats = {4: current}
            actor.effect_maxima = {4: 6}
            actor.effect_minima = {4: 0}
            actor.effect_base_maxima = {4: 6}
            actor.effect_base_minima = {4: 0}
            actor.effect_percentages = {4: 0}
            actor.effect_frozen = frozenset()
        packets = []
        handler = NativeCopyCharacteristicHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0.9,
        )
        handler(
            {"effect_class": 1001, "parameters": [4, 0, 50, 0]},
            None,
            EffectInvocation(1, 1, 7, -7, (1, 0, 0)),
        )
        self.assertEqual((target.effect_stats[4], target.effect_maxima[4]), (1, 3))
        payload = bytes.fromhex(fight.owned_stat_effects[101]["payload"])
        extra = dict(proto_fields(payload))[66]
        self.assertEqual(extra.hex(), "50036004")  # Actual ij.em(4).ek(3).
        # Qe.k owns the allocated clone UID; it executes a copy without Qf.p.
        from wakfu_server.combat_subscription_runners import deferred_payload
        from wakfu_server.combat_effect_removal import _identity_fields

        listener_payload = deferred_payload(
            family=1001,
            uid=77,
            base_uid=None,
            generic_effect=1,
            caster_id=7,
            target_id=-7,
            cell=(1, 0, 0),
            timing_payload=b"\x08\x00",
            container_type=None,
            container_id=None,
        )
        fight.native_owned_group_effects[77] = dict(
            effect_class=1001,
            invocation={"reference": 1},
            payload=listener_payload.hex(),
        )
        handler.allocate_uid = lambda: self.fail("Clone allocated a second UID")
        handler(
            {"effect_class": 1001, "parameters": [4, 0, 50, 0]},
            None,
            EffectInvocation(
                1, 1, 7, -7, (1, 0, 0), base_uid=77, native_running_uid=201
            ),
        )
        self.assertEqual(set(fight.owned_stat_effects), {101})
        self.assertEqual(set(fight.native_owned_group_effects), {77})
        self.assertEqual((target.effect_stats[4], target.effect_maxima[4]), (1, 3))
        self.assertEqual(packets[-1][0], 12613)
        import struct

        body = packets[-1][1]
        length = struct.unpack_from(">h", body, 17)[0]
        cloned_payload = body[19 : 19 + length]
        fields = _identity_fields(cloned_payload)
        self.assertEqual((fields[1], fields[2], fields[3], fields[4]), (201, 77, 1, 1))
        self.assertEqual(dict(proto_fields(cloned_payload))[66].hex(), "50036004")
        self.assertNotIn(9, fields)  # Preserve actual null PL.
        remove_copied_characteristic(handler, 101)
        self.assertEqual((target.effect_stats[4], target.effect_maxima[4]), (1, 3))
        self.assertEqual([opcode for opcode, _ in packets], [13497, 12613, 13560])
        self.assertFalse(fight.owned_stat_effects)

    def test_current_and_maximum_are_independent(self):
        result = prepare_copy(
            [4, 0], 20, caster_current=2, caster_maximum=6, rng=lambda: 0.9
        )
        self.assertEqual((result.stat_id, result.current, result.maximum), (4, 2, 6))

    def test_native_rounding_and_maximum_sentinel(self):
        # Draws occur maximum first, then current; only fractional values draw.
        draws = iter([0.9, 0.1])
        result = prepare_copy(
            [4, 0, 50, 0],
            1,
            caster_current=3,
            caster_maximum=5,
            rng=lambda: next(draws),
        )
        self.assertEqual((result.current, result.maximum), (2, 2))
        result = prepare_copy(
            [4, 0, 0, 0], 1, caster_current=3, caster_maximum=2147483647, rng=lambda: 0
        )
        self.assertEqual((result.current, result.maximum), (0, 2147483647))

    def test_native_overflow_and_unknown_snapshot(self):
        result = prepare_copy(
            [260, 0, 100, 0],
            1,
            caster_current=2147483647,
            caster_maximum=2147483647,
            rng=lambda: 0.9,
        )
        self.assertEqual(
            (result.stat_id, result.current, result.maximum), (4, -1, 2147483647)
        )
        with self.assertRaises(ValueError):
            prepare_copy(
                [4, 0], 1, caster_current=None, caster_maximum=6, rng=lambda: 0
            )
