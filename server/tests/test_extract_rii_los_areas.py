import base64
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / "tools" / "extract_rii_los_areas.py"
spec = importlib.util.spec_from_file_location("extract_rii_los_areas", PATH)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


def varint(value):
    if value < 0:
        value += 1 << 64
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def number(tag, value):
    return varint(tag << 3) + varint(value)


def nested(tag, value):
    return varint((tag << 3) | 2) + varint(len(value)) + value


class RiiLosExtractionTest(unittest.TestCase):
    def test_pairs_signed_area_uid_and_excludes_private_actor_fields(self):
        cell = number(1, 0) + number(2, -11) + number(3, 0)
        area = (
            number(3, 367419)
            + number(4, 1808)
            + nested(5, cell)
            + nested(8, number(21, -17))
        )
        frames = [
            {
                "frame_index": 5,
                "opcode": 12613,
                "remote": "private",
                "fields": {
                    "mzM": 315,
                    "hwM": {"base64": base64.b64encode(area).decode()},
                },
            },
            {"frame_index": 6, "opcode": 12678, "fields": {"hwf": 7968, "bgz": 999}},
            {"frame_index": 7, "opcode": 13726, "fields": {"mzt": -17}},
        ]
        result = extractor.extract(frames)
        self.assertEqual(
            [x["kind"] for x in result], ["area_created", "spell_cast", "area_retired"]
        )
        self.assertEqual(result[1]["active_cells"], [[0, -11, 0]])
        self.assertNotIn("private", str(result))
        self.assertNotIn("999", str(result))

    def test_rejects_truncated_payload(self):
        with self.assertRaises(ValueError):
            extractor._fields(b"\x2a\x05\x01")


if __name__ == "__main__":
    unittest.main()
