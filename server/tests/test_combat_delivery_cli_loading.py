"""Private sidecar loading is bounded before typed schema verification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.combat_reproduce import _read_delivery_sidecars


class DeliveryCLILoadingTests(unittest.TestCase):
    def test_order_is_preserved_without_treating_file_order_as_dispatch_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (
                Path(directory) / "first.json",
                Path(directory) / "second.json",
            )
            first.write_text('{"incident_id":"one"}')
            second.write_text('{"incident_id":"two"}')
            self.assertEqual(
                _read_delivery_sidecars([second, first]),
                [{"incident_id": "two"}, {"incident_id": "one"}],
            )

    def test_sidecar_size_bound_applies_even_to_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.json"
            path.write_bytes(b"{}" + b" " * 20)
            with patch("wakfu_server.combat_reproduction_state.MAX_BYTES", 16):
                with self.assertRaisesRegex(ValueError, "size bound"):
                    _read_delivery_sidecars([path])

    def test_count_bound_precedes_opening_files(self):
        with self.assertRaisesRegex(ValueError, "count"):
            _read_delivery_sidecars([Path("missing-private-file.json")] * 129)

    def test_malformed_json_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.json"
            path.write_text("{malformed")
            with self.assertRaises(ValueError):
                _read_delivery_sidecars([path])


if __name__ == "__main__":
    unittest.main()
