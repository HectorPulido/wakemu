"""Actual native camp hydration keeps paid transfers separate from exits."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_instances, dungeon_native_flow, generic_transports


class OwnedTransferBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1] / "wakfu_server/maps"
        cls.camp = json.loads(
            (
                root / "quest_encounter_profiles/astrub-grambo-camp.configuration.json"
            ).read_text()
        )
        cls.temple = json.loads(
            (
                root / "owned_story_profiles/astrub-temple-887.configuration.json"
            ).read_text()
        )
        cls.routes = dict(dungeon_instances._ROUTES)
        cls.routes.update(
            dungeon_instances._load_routes([cls.camp["route"], cls.temple["route"]])
        )

    def hydrate(self, *, completed=False, topology=None):
        with patch.object(dungeon_instances, "_ROUTES", self.routes):
            return dungeon_native_flow._progress_packets(
                topology or self.camp["topology"],
                map_id=747,
                instance_id=144115188075855919,
                unlocked_room=1,
                completed=completed,
                recipient_character_id=369,
            )

    def test_real_camp_bootstrap_renders_paid_portal_without_exterior_room_inference(
        self,
    ):
        source = generic_transports.source(747, 23621)
        cells = {
            tuple(point)
            for room in self.camp["topology"]["rooms"]
            for point in room["cells"]
        }
        self.assertNotIn(tuple(source[k] for k in ("x", "y", "z")), cells)
        for completed in (False, True):
            with self.subTest(completed=completed):
                rows = {
                    struct.unpack_from(">q", body)[0]: (opcode, body)
                    for opcode, body in self.hydrate(completed=completed)
                }
                self.assertTrue({21378, 21379, 21381, 23621} <= set(rows))
                opcode, body = rows[23621]
                self.assertEqual(opcode, 12344)
                payload = body[10:]
                state, visible, usable = struct.unpack_from(">hBB", payload, 7)
                self.assertEqual(
                    (state, visible, usable), (1, int(completed), int(completed))
                )
                # The ordinary physical exterior remains available in room1.
                self.assertEqual(
                    struct.unpack_from(">hBB", rows[21378][1][10:], 7), (1, 1, 1)
                )

    def test_wrong_target_or_duplicate_declaration_cannot_hide_invalid_exit_authority(
        self,
    ):
        for case in ("wrongtarget", "duplicate"):
            topology = deepcopy(self.camp["topology"])
            declared = topology["owned_quest_transfers"][0]
            if case == "wrongtarget":
                declared["target_route_key"] = "unrelated-owned-route"
            else:
                topology["owned_quest_transfers"].append(deepcopy(declared))
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.hydrate(topology=topology)
