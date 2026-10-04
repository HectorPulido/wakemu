import struct
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_orientation import apply, decode_request, response


class OrientationTests(unittest.TestCase):
    def runtime(self):
        cells = {(0, 0, 0), (1, 0, 0)}
        pc = Actor(-7, 0, (0, 0, 0), 60, 0, 0, 100, 1, 9, True)
        npc = Actor(2, 1, (1, 0, 0), 10, 3, 3, 0, 1)
        fight = Fight(3, [pc, npc], cells, {0: {pc.position}, 1: {npc.position}})
        fight.ready(9)
        return RuntimeMessages(fight), pc

    def test_native_response_and_cardinal_changes_cost_no_resources(self):
        runtime, actor = self.runtime()
        for direction in (1, 3, 5, 7):
            result = apply(runtime, 9, struct.pack(">qB", -7, direction))
            self.assertEqual([n for n, _ in result["packets"]], [13494, 13420])
            self.assertEqual(len(result["packets"][0][1]), 21)
            self.assertEqual(
                struct.unpack(">iiiqB", result["packets"][0][1]),
                (3, runtime.action_id, -1, -7, direction),
            )
            self.assertEqual((actor.direction, actor.ap, actor.mp), (direction, 0, 0))
        self.assertEqual(actor.position, (0, 0, 0))

    def test_invalid_owner_current_phase_and_ack_do_not_mutate(self):
        runtime, actor = self.runtime()
        body = struct.pack(">qB", -7, 1)
        for owner, request in ((8, body), (9, struct.pack(">qB", 2, 1))):
            with self.assertRaises(ValueError):
                apply(runtime, owner, request)
        runtime.awaiting_ack = 1
        with self.assertRaises(ValueError):
            apply(runtime, 9, body)
        runtime.awaiting_ack = None
        runtime.fight.phase = "placement"
        with self.assertRaises(ValueError):
            apply(runtime, 9, body)
        self.assertEqual(runtime.action_id, 0)
        self.assertFalse(hasattr(actor, "direction"))

    def test_malformed_direction_identity_and_exhaustion_fail_before_mutation(self):
        runtime, actor = self.runtime()
        for body in (
            b"",
            struct.pack(">qB", -7, 0),
            struct.pack(">qB", -7, 8),
            struct.pack(">qB", 0, 1),
        ):
            with self.assertRaises(ValueError):
                decode_request(body)
        runtime.action_id = (1 << 31) - 1
        with self.assertRaises(ValueError):
            apply(runtime, 9, struct.pack(">qB", -7, 1))
        self.assertFalse(hasattr(actor, "direction"))
