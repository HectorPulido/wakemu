"""Exercise only the tracing wrapper offline, without TLS or a database."""
import ast
import json
from pathlib import Path
import time
import unittest


source = (
    Path(__file__).resolve().parents[1]
    / "tools/candidate_marker_join_withdraw_socket_smoke.py"
)
tree = ast.parse(source.read_text())
node = next(
    node
    for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name == "DiagnosticPeer"
)
namespace = {"json": json, "time": time}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
DiagnosticPeer = namespace["DiagnosticPeer"]


class FakePeer:
    def send(self, opcode, body=b""):
        return body

    def wait(self, opcode, timeout=45):
        if opcode == 9:
            raise AssertionError("timeout for 9; secret payload")
        if opcode == 8:
            raise ValueError("credential=secret")
        return b"secret payload", []

    def wait_any(self, opcodes, timeout=45):
        return (min(opcodes), b"secret payload"), []

    def close(self):
        return "closed"


class DiagnosticTests(unittest.TestCase):
    def trace(self):
        rows = []
        ticks = iter(range(100))
        return (
            DiagnosticPeer(
                FakePeer(),
                "starter",
                enabled=True,
                emit=rows.append,
                clock=lambda: next(ticks),
            ),
            rows,
        )

    def test_success_metadata_only_and_order(self):
        peer, rows = self.trace()
        self.assertEqual(peer.send(1, b"secret payload"), b"secret payload")
        peer.wait(2)
        peer.wait_any({4, 3})
        self.assertEqual(
            [row["operation"] for row in rows],
            ["send"] * 2 + ["wait"] * 2 + ["wait_any"] * 2,
        )
        self.assertEqual(rows[-1]["opcode"], [3, 4])
        self.assertTrue(
            all(
                row["duration"] == 1 and row["outcome"] == "success"
                for row in rows[1::2]
            )
        )
        self.assertNotIn("secret", json.dumps(rows))
        self.assertEqual(peer.close(), "closed")

    def test_failure_keeps_original_exception_without_private_text(self):
        peer, rows = self.trace()
        with self.assertRaisesRegex(AssertionError, "secret payload"):
            peer.wait(9)
        with self.assertRaisesRegex(ValueError, "credential=secret"):
            peer.wait(8)
        self.assertEqual([row["outcome"] for row in rows[1::2]], ["timeout", "error"])
        self.assertNotIn("secret", json.dumps(rows))
        self.assertNotIn("credential", json.dumps(rows))

    def test_disabled_is_silent(self):
        rows = []
        peer = DiagnosticPeer(FakePeer(), "watching", emit=rows.append)
        peer.send(1, b"secret")
        peer.wait(2)
        peer.wait_any({3})
        self.assertEqual(rows, [])
