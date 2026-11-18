"""One current member per native pad; past emote receipts never accumulate."""
from copy import deepcopy
import struct
import unittest

from wakfu_server import simultaneous_party_pads as pads


class SimultaneousPartyPadTests(unittest.TestCase):
    def test_four_native_actions_must_be_current_distinct_and_same_scope(self):
        profile = pads.source()
        now = 100.0
        members = []
        for index, pad in enumerate(profile["pads"]):
            actor = 1000 + index
            packet = (
                12088,
                struct.pack(">BhqIiB", 1, 20, actor, 5, pad["emote_id"], 0),
            )
            members.append(
                dict(
                    id=actor,
                    account_id=2000 + index,
                    map_id=448,
                    instance_id=3000,
                    x=pad["position"][0],
                    y=pad["position"][1],
                    z=pad["position"][2],
                    _emote_packet=packet,
                    _emote_until=now + 4.2,
                    _pad_generation=str(index),
                )
            )
        self.assertEqual(len(pads.occupied(profile, members, now=now)), 4)
        # Three active actions, a disconnected member and sequential use by one
        # actor cannot fill four positions at the same instant.
        self.assertEqual(pads.occupied(profile, members[:3], now=now), ())
        for field, value in (
            ("x", 500),
            ("_emote_until", now),
            ("map_id", 1295),
            ("_emote_packet", (12088, b"malformed")),
        ):
            current = deepcopy(members)
            current[-1][field] = value
            with self.subTest(field=field):
                self.assertEqual(pads.occupied(profile, current, now=now), ())
        current = deepcopy(members)
        for member in current:
            member["id"] = 1000
        self.assertEqual(pads.occupied(profile, current, now=now), ())
        self.assertEqual(pads.occupied(profile, members, now=now + 4.2), ())
        # Native destruction has four state-count arguments; malformed arity
        # cannot become a client-authorized callback or an invented outcome.
        with self.assertRaises(ValueError):
            pads.native_packet(profile, 11212, [1, 1, 1])
