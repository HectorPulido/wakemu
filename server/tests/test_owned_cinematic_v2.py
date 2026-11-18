"""Native v2 continuation gates and zero-argument return lifecycle."""

import json
from pathlib import Path
import unittest

from wakfu_server import owned_cinematic_continuations as cinematic


ROOT = (
    Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_continuations"
)


class OwnedCinematicV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / "zinit-ullu-986.v2.json").read_text())

    def test_v2_requires_running2689_and_real5308_without5309(self):
        doc = self.document
        for state, expected in (
            ({"running": [2689], "completed": [], "objectives": [5308]}, True),
            ({"running": [2689], "completed": [], "objectives": [5308, 5309]}, False),
            ({"running": [], "completed": [], "objectives": [5308]}, False),
            ({"running": [2689], "completed": [2689], "objectives": [5308]}, False),
            ({"running": [2689], "completed": [], "objectives": []}, False),
        ):
            with self.subTest(state=state):
                self.assertEqual(cinematic.eligible(doc, state), expected)

    def test_v2_scene_packet_has_no_invented_player_argument_and_uses_native_exit(self):
        doc = self.document
        opcode, body = cinematic.packet(doc, doc["presentation"]["event"], 77)
        self.assertEqual(opcode, 13411)
        self.assertEqual(
            body,
            b"\x00" + (16087).to_bytes(4, "big") + (2029).to_bytes(4, "big") + b"\x00",
        )
        self.assertEqual(
            [(entry["source_id"], entry["destination_id"]) for entry in doc["entries"]],
            [(25395, 2234), (25430, 2234)],
        )
        self.assertEqual(
            (
                doc["native_arrival"]["map_id"],
                doc["stage"]["map_id"],
                doc["return_anchor"]["source_id"],
                doc["return_anchor"]["destination_id"],
            ),
            (986, 986, 27538, 2599),
        )


if __name__ == "__main__":
    unittest.main()
