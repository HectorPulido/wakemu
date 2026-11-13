import struct
import unittest
from unittest.mock import patch

from wakfu_server.achievements import tutorial_presentation_once as once


def packet(event, scenario, *args):
    return (
        13411,
        struct.pack(">BiiB", 0, event, scenario, len(args))
        + b"".join(struct.pack(">q", arg) for arg in args),
    )


class TutorialPresentationOnceTests(unittest.TestCase):
    def test_unique_per_character_event_and_step_across_retries(self):
        seen = set()

        def record(_db, character, key, _payload):
            identity = (character, key)
            if identity in seen:
                return False
            seen.add(identity)
            return True

        inputs = [
            packet(22514, 2500),
            packet(22515, 2500, 100),
            packet(22529, 2500, 10),
            packet(22409, 2543),
        ]
        with patch.object(once.storage, "record_event", side_effect=record):
            self.assertEqual(once.filter_packets(None, 1, inputs), inputs)
            self.assertEqual(once.filter_packets(None, 1, inputs), [])
            # New fight id cannot repeat the same guide, but another character can see it.
            self.assertEqual(
                once.filter_packets(None, 1, [packet(22515, 2500, 101)]), []
            )
            self.assertEqual(
                once.filter_packets(None, 1, [packet(22529, 2500, 50)]),
                [packet(22529, 2500, 50)],
            )
            self.assertEqual(once.filter_packets(None, 2, inputs), inputs)

    def test_rejects_malformed_packet(self):
        with self.assertRaises(ValueError):
            once.filter_packets(None, 1, [(13411, b"short")])


if __name__ == "__main__":
    unittest.main()
