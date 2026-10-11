import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SNIFFER = Path(__file__).resolve().parents[2] / "sniffer"
sys.path.insert(0, str(SNIFFER))
import export_native_npc_coverage as exporter


class NativeNpcCoverageTests(unittest.TestCase):
    def test_every_speaker_and_inferred_markers_remain_separate(self):
        native = dict(
            speakers=[dict(ref=i, actions=[]) for i in (1, 2, 3)],
            translations={"es": {}},
        )
        captured = dict(
            source="original",
            source_sha256="a" * 64,
            actors=[dict(reference_id=1, actor_id=-7)],
            observed_interactions=[],
        )
        with patch.object(exporter, "qualify", return_value={"accepted": []}):
            result = exporter.coverage(
                native, [captured, captured], [dict(candidate_references=[2], x=9, y=8)]
            )
        self.assertEqual(result["speaker_count"], 3)
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(
            [row["status"] for row in result["speakers"]],
            [
                "native_position_without_initial_dialogue",
                "quest_marker_candidate_only",
                "catalog_only",
            ],
        )
        self.assertEqual(result["speakers"][1]["original_positions"], [])

    def test_local_server_capture_cannot_authorize_original_placements(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.jsonl"
            path.write_text(
                json.dumps(dict(opcode=12608, remote="localhost/127.0.0.1:5556")) + "\n"
            )
            with self.assertRaises(ValueError):
                exporter.original_capture(path)
