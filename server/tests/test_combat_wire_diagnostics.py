"""Payload-free summaries for native 12613 combat-effect frames."""
import ast
from pathlib import Path
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat.combat_wire_diagnostics import effect_application_metadata
import wakfu_server.combat.combat_wire_diagnostics as wire_diagnostics


def _varint(value):
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _frame(
    effect_family, *, execute_flag=1, proto=None, runner_uid=123, target_uid=5672
):
    if proto is None:
        proto = (
            _varint(8)
            + _varint(runner_uid)
            + _varint(24)
            + _varint(386191)
            + _varint(56)
            + _varint(target_uid & ((1 << 64) - 1))
        )
    return (
        struct.pack(">ii", 285, 17)
        + struct.pack(">i", -1)
        + bytes((execute_flag,))
        + struct.pack(">ih", effect_family, len(proto))
        + proto
    )


class CombatWireDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        names = {
            "record_combat_wire_effect",
            "send",
            "send_batch",
        }
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        if {node.name for node in functions} != names:
            raise AssertionError("Missing combat wire send instrumentation")
        module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
        cls.sent = []
        cls.records = []
        cls.connection = SimpleNamespace(
            trace_id="wire-test-connection",
            sendall=cls.sent.append,
        )
        cls.scope = {
            "struct": struct,
            "NATIVE_PLANTING_BONUS": False,
            "COMBAT_WIRE_TRACE": True,
            "record": lambda **row: cls.records.append(row),
            "effect_application_metadata": effect_application_metadata,
        }
        exec(compile(module, str(source_path), "exec"), cls.scope)

    def setUp(self):
        self.sent.clear()
        self.records.clear()

    def test_extracts_expected_identity_for_effect_families(self):
        for family in (307, 308, 843):
            with self.subTest(family=family):
                result = effect_application_metadata(12613, _frame(family))
                self.assertEqual(
                    result,
                    {
                        "opcode": 12613,
                        "fight_id": 285,
                        "action_id": 17,
                        "effect_family": family,
                        "generic_effect_id": 386191,
                        "execute_flag": 1,
                        "runner_uid": 123,
                        "target_uid": 5672,
                        "parse_status": "ok",
                    },
                )

    def test_retained_application_reports_execute_zero(self):
        result = effect_application_metadata(12613, _frame(843, execute_flag=0))
        self.assertEqual(result["execute_flag"], 0)
        self.assertEqual(result["parse_status"], "ok")

    def test_negative_actor_target_is_restored_from_int64_wire_varint(self):
        result = effect_application_metadata(12613, _frame(308, target_uid=-7))
        self.assertEqual(result["target_uid"], -7)
        self.assertEqual(result["generic_effect_id"], 386191)

    def test_runner_uid_preserves_raw_positive_native_long_identity(self):
        runner_uid = (1 << 63) + 9
        result = effect_application_metadata(12613, _frame(307, runner_uid=runner_uid))
        self.assertEqual(result["runner_uid"], runner_uid)

    def test_malformed_frames_never_raise_or_return_wire_bytes(self):
        malformed = (
            b"",
            _frame(843)[:-1],
            _frame(843) + b"\x00",
            _frame(843, execute_flag=2),
            _frame(843, proto=b"\x80"),
        )
        for body in malformed:
            with self.subTest(length=len(body)):
                result = effect_application_metadata(12613, body)
                self.assertEqual(result["parse_status"], "malformed")
                self.assertFalse(
                    {"body", "payload", "payload_hex", "payload_base64"} & set(result)
                )

    def test_other_opcodes_are_ignored(self):
        self.assertIsNone(effect_application_metadata(12053, b"not-an-effect"))

    def test_send_logs_semantics_after_delivering_malformed_frame(self):
        body = b"bad"
        self.scope["send"](self.connection, "world", 12613, body)
        self.assertEqual(
            self.sent,
            [struct.pack(">IH", 6 + len(body), 12613) + body],
        )
        semantic = [
            row for row in self.records if row.get("event") == "combat_effect_wire"
        ]
        self.assertEqual(len(semantic), 1)
        self.assertEqual(semantic[0]["parse_status"], "malformed")
        self.assertNotIn("payload", semantic[0])
        self.assertNotIn("body", semantic[0])

    def test_unexpected_diagnostic_parser_exception_cannot_break_send(self):
        body = _frame(843)
        with patch.object(
            wire_diagnostics,
            "effect_application_metadata",
            side_effect=RuntimeError("diagnostic parser failure"),
        ):
            self.scope["send"](self.connection, "world", 12613, body)
        self.assertEqual(
            self.sent,
            [struct.pack(">IH", 6 + len(body), 12613) + body],
        )
        self.assertFalse(
            any(row.get("event") == "combat_effect_wire" for row in self.records)
        )

    def test_send_batch_logs_valid_and_malformed_12613_after_delivery(self):
        valid = _frame(308)
        malformed = b"truncated"
        packets = ((12613, valid), (12613, malformed), (12053, b"ignored"))
        self.scope["send_batch"](self.connection, "world", packets)
        expected = b"".join(
            struct.pack(">IH", 6 + len(body), opcode) + body for opcode, body in packets
        )
        self.assertEqual(self.sent, [expected])
        semantic = [
            row for row in self.records if row.get("event") == "combat_effect_wire"
        ]
        self.assertEqual(len(semantic), 2)
        self.assertEqual(semantic[0]["effect_family"], 308)
        self.assertEqual(semantic[0]["execute_flag"], 1)
        self.assertEqual(semantic[1]["parse_status"], "malformed")
        self.assertTrue(
            all("payload" not in row and "body" not in row for row in semantic)
        )

    def test_wire_semantic_records_are_default_off(self):
        self.scope["COMBAT_WIRE_TRACE"] = False
        body = _frame(843)
        self.scope["send"](self.connection, "world", 12613, body)
        self.assertEqual(len(self.sent), 1)
        self.assertFalse(
            any(row.get("event") == "combat_effect_wire" for row in self.records)
        )
        self.scope["COMBAT_WIRE_TRACE"] = True


if __name__ == "__main__":
    unittest.main()
