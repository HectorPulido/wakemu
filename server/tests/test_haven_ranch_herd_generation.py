"""Whole-catalog native creature construction and seeded-slot checks."""
import random
import struct
import unittest


class RanchHerdGenerationTests(unittest.TestCase):
    def test_all_native_actions_keep_weighted_slots_and_original_constructor_defaults(
        self,
    ):
        from wakfu_server import haven_ranch_herd, haven_ranch_herd_wire

        actions, definitions = haven_ranch_herd.catalog()
        self.assertEqual(len(actions), 36)
        self.assertEqual(len(definitions), 125)
        expected_keys = {
            "definition",
            "uid",
            "birth_ms",
            "attributes",
            "name",
            "scale",
            "native_tJT",
            "native_eqf",
            "native_tJU",
            "x",
            "y",
            "z",
            "native_tJR",
            "native_tJV",
        }
        for action_id, action in sorted(actions.items()):
            candidates = action["candidate_refs"]
            self.assertTrue(candidates)
            self.assertTrue(all(reference in definitions for reference in candidates))
            # Preserve the original ordered list and duplicate slots. Sampling
            # each native index is the behavior that gives repeated refs their
            # original weight; converting candidates to a set would fail here.
            slots = set()
            seed_value = 0
            while len(slots) < len(candidates):
                seed = f"{seed_value:032x}"
                record, slot = haven_ranch_herd.generate(
                    action_id,
                    700000 + action_id,
                    1700000000000 + action_id,
                    seed,
                )
                expected_slot = random.Random(seed_value).randrange(len(candidates))
                self.assertEqual(slot, expected_slot)
                self.assertEqual(record["definition"], candidates[expected_slot])
                self.assertEqual(set(record), expected_keys)
                self.assertEqual(
                    record,
                    {
                        "definition": candidates[expected_slot],
                        "uid": 700000 + action_id,
                        "birth_ms": 1700000000000 + action_id,
                        "attributes": {},
                        "name": "",
                        "scale": 1.0,
                        "native_tJT": True,
                        "native_eqf": -1,
                        "native_tJU": -1,
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "native_tJR": 0,
                        "native_tJV": True,
                    },
                )
                encoded = haven_ranch_herd_wire.encode_creature(record)
                expected = (
                    struct.pack(
                        ">iqqh",
                        candidates[expected_slot],
                        700000 + action_id,
                        1700000000000 + action_id,
                        0,
                    )
                    + b"\x00"
                    + struct.pack(">fBiqiihqB", 1.0, 1, -1, -1, 0, 0, 0, 0, 1)
                )
                self.assertEqual(encoded, expected)
                slots.add(slot)
                seed_value += 1
