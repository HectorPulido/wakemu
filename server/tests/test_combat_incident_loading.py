"""Private incident loading bounds the bytes read, including growing files."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_incident_replay import (
    IncidentReplayError,
    NPC_SCHEMA,
    read_incident,
)


class IncidentLoadingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "incident.json"
        self.receipt = dict(schema=NPC_SCHEMA, before={}, after={})

    def test_exact_byte_limit_accepts_and_one_more_byte_rejects(self):
        raw = json.dumps(self.receipt).encode()
        self.path.write_bytes(raw)
        with patch("wakfu_server.combat_incident_replay.MAX_BYTES", len(raw)):
            self.assertEqual(read_incident(self.path), self.receipt)
            self.path.write_bytes(raw + b" ")
            with self.assertRaisesRegex(IncidentReplayError, "size bound"):
                read_incident(self.path)

    def test_read_is_bounded_without_trusting_a_prior_file_size(self):
        self.path.write_bytes(json.dumps(self.receipt).encode() + b" " * 256)
        with patch("wakfu_server.combat_incident_replay.MAX_BYTES", 32), patch.object(
            Path, "stat", return_value=SimpleNamespace(st_size=1)
        ):
            with self.assertRaisesRegex(IncidentReplayError, "size bound"):
                read_incident(self.path)

    def test_invalid_json_and_invalid_encoding_reject(self):
        for raw in (b"{", b"\xff"):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(IncidentReplayError, "bounded JSON"):
                    read_incident(self.path)

    def test_unknown_schema_and_missing_checkpoint_reject(self):
        for receipt in (
            [],
            dict(self.receipt, schema="unknown"),
            dict(self.receipt, before=None),
            dict(self.receipt, after=None),
        ):
            with self.subTest(receipt=receipt):
                self.path.write_text(json.dumps(receipt))
                with self.assertRaises(IncidentReplayError):
                    read_incident(self.path)
