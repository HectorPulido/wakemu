import struct
import unittest
from wakfu_server.inventory_animation import eating
from wakfu_server.wire import proto_fields


class FoodAnimationTests(unittest.TestCase):
    def test_native_world_effect_uses_only_owned_actor_and_food_effect(self):
        opcode, body = eating(
            actor_id=7, action_id=81, effect_uid=9001, effect_id=183200
        )
        self.assertEqual(opcode, 12705)
        action, sequence, flag1, flag2, kind, size = struct.unpack_from(">iiBBih", body)
        self.assertEqual((action, sequence, flag1, flag2, kind), (81, -1, 0, 0, 550))
        self.assertEqual(
            dict(proto_fields(body[16 : 16 + size])),
            {8: 9001, 16: 0, 24: 183200, 32: 20019, 48: 7, 56: 7},
        )
        self.assertEqual(struct.unpack(">iiq", body[16 + size :]), (81, -1, 7))
        for bad in (dict(actor_id=-1), dict(effect_id=183201), dict(action_id=0)):
            with self.assertRaises(ValueError):
                eating(
                    **(
                        dict(
                            actor_id=7, action_id=81, effect_uid=9001, effect_id=183200
                        )
                        | bad
                    )
                )
