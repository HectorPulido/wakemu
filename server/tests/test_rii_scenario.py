import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import incarnam_tutorial
from wakfu_server.maps import rii_scenario


class RiiScenarioTests(unittest.TestCase):
    def test_observed_event_layout(self):
        self.assertEqual(
            rii_scenario.packet(rii_scenario.INTRO),
            (13411, struct.pack(">BiiB", 0, 22360, 2536, 0)),
        )
        with self.assertRaises(ValueError):
            rii_scenario.packet(999)
        for event in (22530, 22538, 22539):
            self.assertEqual(
                rii_scenario.packet(event),
                (13411, struct.pack(">BiiB", 0, event, 2536, 0)),
            )

    def test_callback_requires_owner_and_scene_then_emits_completion_and_guide_once(
        self,
    ):
        connection = SimpleNamespace(pending_rii_intro=7)
        character = {"id": 7, "map_id": 1385, "instance_id": 0}
        from wakfu_server.characters import incarnam_completion

        with patch.object(
            incarnam_completion,
            "complete_after_rii_intro",
            return_value=[(1, b"mission")],
        ) as complete:
            for bad_character, in_combat in (
                (dict(character, id=8), False),
                (dict(character, map_id=1387), False),
                (character, True),
            ):
                with self.assertRaises(ValueError):
                    rii_scenario.finish_intro(
                        connection, None, 1, 2, bad_character, in_combat=in_combat
                    )
            complete.assert_not_called()
            packets = rii_scenario.finish_intro(
                connection, None, 1, 2, character, in_combat=False
            )
            self.assertEqual(
                packets,
                [(1, b"mission"), rii_scenario.packet(rii_scenario.INTRO_GUIDE)],
            )
            with self.assertRaises(ValueError):
                rii_scenario.finish_intro(
                    connection, None, 1, 2, character, in_combat=False
                )
            complete.assert_called_once()

    def test_login_replays_only_unfinished_intro(self):
        character = {"id": 7, "map_id": 1385, "instance_id": 0}
        state = {"running": [5139], "objectives": []}
        self.assertEqual(
            rii_scenario.login_packets(character, state),
            [
                rii_scenario.packet(rii_scenario.ENTRY),
                rii_scenario.packet(rii_scenario.INTRO),
            ],
        )
        state["objectives"] = [10568]
        self.assertEqual(
            rii_scenario.login_packets(character, state),
            [
                rii_scenario.packet(rii_scenario.ENTRY),
                incarnam_tutorial.interface_recovery_packet(),
            ],
        )
        self.assertEqual(
            rii_scenario.login_packets(dict(character, map_id=1387), state), []
        )

    def test_skipped_intro_restores_interface_only_on_public_rii_login(self):
        state = {"running": [], "objectives": []}
        character = {"id": 7, "map_id": 1385, "instance_id": 0}
        self.assertEqual(
            rii_scenario.login_packets(character, state),
            [
                rii_scenario.packet(rii_scenario.ENTRY),
                incarnam_tutorial.interface_recovery_packet(),
            ],
        )
        for other in (
            dict(character, map_id=1361),
            dict(character, instance_id=7),
        ):
            self.assertEqual(rii_scenario.login_packets(other, state), [])


if __name__ == "__main__":
    unittest.main()
