import json
import unittest
from types import SimpleNamespace
from wakfu_server.combat_carrying import NativeCarryPair
from wakfu_server.fight_checkpoint_store import snapshot


class CarryCheckpointTests(unittest.TestCase):
    def test_owned_carry_pair_preserves_all_checkpoint_fields(self):
        pair = NativeCarryPair(7, -7, (-8, -7, -1), 3, 1, 205)
        fight = SimpleNamespace(actors={}, native_carry_pairs={7: pair})
        encoded = snapshot(fight)
        self.assertEqual(
            json.loads(json.dumps(encoded)),
            {
                "actors": {},
                "native_carry_pairs": {
                    "7": dict(
                        carrier_id=7,
                        carried_id=-7,
                        position=[-8, -7, -1],
                        carried_direction=3,
                        carrier_direction=1,
                        source_uid=205,
                        source_reference=None,
                    )
                },
            },
        )
        self.assertIs(fight.native_carry_pairs[7], pair)

    def test_unknown_runtime_object_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonserializable"):
            snapshot(SimpleNamespace(actors={}, callback=object()))
