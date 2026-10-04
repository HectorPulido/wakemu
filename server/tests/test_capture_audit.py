import base64
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "capture_audit", Path(__file__).resolve().parents[2] / "sniffer/audit-capture.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CaptureAuditTests(unittest.TestCase):
    def test_distinguishes_verified_opaque_and_malformed_without_payloads(self):
        frames = [
            dict(
                direction="in",
                opcode=opcode,
                body_base64=base64.b64encode(body).decode(),
            )
            for opcode, body in [
                (22025, b"\x00"),
                (22025, b""),
                (999999, b"private data"),
            ]
        ]
        result = module.audit(
            frames,
            {("in", 22025): ("creation_result",)},
            {"messages": [{"direction": "in", "opcode": 22025, "class": "cEc"}]},
        )
        self.assertEqual(result[0]["decoded"], 1)
        self.assertEqual(result[0]["decode_errors"], 1)
        self.assertEqual(result[0]["classes"], ["cEc"])
        self.assertEqual(result[1]["opaque"], 1)
        self.assertEqual(result[1]["action"], "unresolved")
        self.assertNotIn("private data", repr(result))
