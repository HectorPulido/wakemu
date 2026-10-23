"""Actual retained legacy bootstrap remains unchanged without public metadata."""
import ast
import base64
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock

from protocol_codec import Reader
from wakfu_server import native_catalog, wire
from wakfu_server.storage.bootstrap_capture import DEFAULT_KEY, load


class LegacyBootstrapCompatibilityTests(unittest.TestCase):
    def test_legacy_registration_gate_auth_header_and_character_filter_keep_exact_bytes(
        self,
    ):
        self.assertEqual(
            (
                wire.TEMPLATE_ACCOUNT,
                wire.TEMPLATE_CHARACTER,
                wire.TEMPLATE_NAME,
                wire.SYNTHETIC_BOOTSTRAP,
            ),
            (83668792, 2409354, "Pekebu", False),
        )
        with native_catalog._database().connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            frames = load(db, DEFAULT_KEY)
        self.assertTrue(frames)
        self.assertNotIn("synthetic_template", frames[0])
        source = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        gates = [
            node
            for node in source.body
            if isinstance(node, ast.If)
            and "register_synthetic_bootstrap" in ast.unparse(node)
        ]
        self.assertEqual(len(gates), 1)
        registration = Mock()
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=gates, type_ignores=[])),
                "<actual-production-bootstrap-gate>",
                "exec",
            ),
            {
                "FRAMES": frames,
                "wire": type(
                    "WireRegistration",
                    (),
                    {"register_synthetic_bootstrap": registration},
                ),
            },
        )
        registration.assert_not_called()

        def fixture(opcode):
            return base64.b64decode(
                next(
                    row["body_base64"]
                    for row in frames
                    if row["direction"] == "in" and row["opcode"] == opcode
                )
            )

        auth = fixture(472)
        self.assertEqual(wire.adapt(472, auth, wire.TEMPLATE_ACCOUNT), auth)
        account = 1900000991
        self.assertEqual(
            wire.adapt(472, auth, account),
            auth.replace(struct.pack(">q", 83668792), struct.pack(">q", account)),
        )
        functions = [
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("character_list_local", "player_template")
        ]
        self.assertEqual(len(functions), 2)
        namespace = {
            "Reader": Reader,
            "struct": struct,
            "wire": wire,
            "fixture": fixture,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                "<actual-production-legacy-selectors>",
                "exec",
            ),
            namespace,
        )
        original = fixture(23548)
        reader = Reader(original)
        entities = [reader.take(reader.number("I")) for _ in range(reader.number("B"))]
        selected = [body for body in entities if b"Pekebu" in body]
        self.assertEqual(len(selected), 1)
        expected = (
            b"\x01"
            + struct.pack(">I", len(selected[0]))
            + selected[0]
            + original[reader.pos :]
        )
        self.assertEqual(namespace["character_list_local"](original), expected)
        entity = namespace["player_template"]()
        header = Reader(entity)
        header.take(18)
        self.assertEqual(header.text("H"), "Pekebu")
        self.assertEqual(
            wire.header(entity, 83668792, {"id": 2409354, "name": "Pekebu"}), entity
        )
