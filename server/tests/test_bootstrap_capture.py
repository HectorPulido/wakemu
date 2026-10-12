"""Bootstrap authority integrity and explicit offline source import validation."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from wakfu_server.storage import bootstrap_capture as capture


def frames():
    result = [
        {
            "direction": "in",
            "opcode": 630,
            "body_base64": "",
            "frame_index": index,
            "route": {"label": "Original é"},
        }
        for index in range(45)
    ]
    result[44].update(direction="out", opcode=23664)
    return result


class BootstrapCaptureTests(unittest.TestCase):
    def test_complete_order_is_part_of_digest_and_extra_fields_are_preserved(self):
        original = frames()
        digest, hashes = capture.describe(original)
        self.assertEqual(len(hashes), 45)
        reordered = frames()
        reordered[0], reordered[1] = reordered[1], reordered[0]
        self.assertNotEqual(capture.describe(reordered)[0], digest)
        self.assertEqual(original[0]["route"], {"label": "Original é"})

    def test_malformed_frames_and_missing_character_anchor_reject(self):
        for changed in (
            {"direction": "bad"},
            {"opcode": True},
            {"body_base64": "!"},
            {"route": {"invalid": float("nan")}},
        ):
            records = frames()
            records[0].update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                capture.describe(records)
        records = frames()
        records[44]["opcode"] = 1
        with self.assertRaises(ValueError):
            capture.describe(records)
        with self.assertRaises(ValueError):
            capture.describe(records[:44])

    def test_explicit_source_digest_and_duplicate_json_keys(self):
        path = Path(__file__).parents[1] / "tools/import_bootstrap_capture.py"
        spec = importlib.util.spec_from_file_location("bootstrap_import_tool", path)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            raw = b'{"direction":"in","opcode":1,"body_base64":""}\n'
            source.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(tool.parse_source(source, digest)[1][0]["opcode"], 1)
            with self.assertRaises(ValueError):
                tool.parse_source(source, "0" * 64)
            raw = b'{"opcode":1,"opcode":2}\n'
            source.write_bytes(raw)
            with self.assertRaises(ValueError):
                tool.parse_source(source, hashlib.sha256(raw).hexdigest())

    def test_runtime_loader_contains_no_file_read_or_fallback(self):
        import inspect

        source = inspect.getsource(capture.load)
        for forbidden in ("read_text", "read_bytes", "open(", "Path("):
            self.assertNotIn(forbidden, source)
        main = (Path(__file__).parents[1] / "local_game_server.py").read_text()
        self.assertNotIn("SOURCE.read_text()", main)
        self.assertLess(
            main.index("STORE = Store("), main.index("FRAMES = load_bootstrap_capture(")
        )
