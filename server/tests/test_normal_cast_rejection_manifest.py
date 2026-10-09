import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "summarize_normal_cast_rejections.py"
)
SPEC = importlib.util.spec_from_file_location("normal_cast_rejections", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _action(*, status="effect_transaction_rejected", target=(-2, -3, 7)):
    return {
        "origin": "normal_owned_deck",
        "reference": 4593,
        "status": status,
        "attempts": [
            {
                "status": "rejected",
                "failed_stage": "effect_transaction",
                "branch": "independent_actual_turn_baseline",
                "target": list(target),
                "first_root_failure": {
                    "kind": "authority_or_lifecycle_guard",
                    "reason": "Invalid state source, target or fight phase",
                    "first_failed_effect": {
                        "effect_reference": 410777,
                        "effect_class": 304,
                        "level": 20,
                        "target_id": -7,
                        "state_uid": 252,
                    },
                },
            }
        ],
    }


def _report(*, actions=None, expected=1):
    return {
        "finished": True,
        # Large unused members should be skipped, not retained in memory.
        "source_before": {"padding": "x" * 100},
        "numeric_summary": {
            "normal": {
                "expected_spell_level_pairs": 1,
                "preparation_partition": {"effect_transaction_rejected": expected},
            }
        },
        "rows": [
            {
                "breed": 4,
                "level": 20,
                "runtime_access": {"actions": actions or [_action()]},
            }
        ],
    }


class NormalCastRejectionManifestTests(unittest.TestCase):
    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_streams_rows_and_keeps_transaction_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            self.write_json(
                path,
                _report(
                    actions=[
                        _action(),
                        _action(status="bounded_search_exhausted"),
                        {
                            "origin": "normal_owned_deck",
                            "reference": 9000,
                            "status": "eligibility_authority_unresolved",
                            "attempts": [],
                        },
                    ]
                ),
            )
            result = MODULE.summarize(path)
        self.assertEqual(result["transaction_rejected_pairs"], 1)
        pair = result["pairs"][0]
        self.assertEqual(
            (pair["breed"], pair["level"], pair["spell_reference"]), (4, 20, 4593)
        )
        self.assertEqual(pair["first_failed_family"], 304)
        self.assertEqual(
            pair["attempts"][0]["branch"], "independent_actual_turn_baseline"
        )
        self.assertFalse(result["negative_prerequisite_outcomes_included"])

    def test_identical_duplicate_pair_is_deduplicated(self):
        report = _report()
        report["rows"].append(report["rows"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            self.write_json(path, report)
            result = MODULE.summarize(path)
        self.assertEqual(result["transaction_rejected_pairs"], 1)

    def test_conflicting_duplicate_pair_is_rejected(self):
        report = _report()
        duplicate = json.loads(json.dumps(report["rows"][0]))
        duplicate["runtime_access"]["actions"][0]["attempts"][0]["target"] = [3, 4, 7]
        report["rows"].append(duplicate)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            self.write_json(path, report)
            with self.assertRaisesRegex(ValueError, "Conflicting duplicate"):
                MODULE.summarize(path)

    def test_truncated_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text('{"finished":true,"rows":[{"breed":4', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid or truncated JSON"):
                MODULE.summarize(path)

    def test_malformed_row_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(
                '{"finished":true,"numeric_summary":{"normal":{}},"rows":[{"breed":4,}]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Invalid or truncated JSON"):
                MODULE.summarize(path)

    def test_duplicate_top_level_metadata_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text('{"finished":true,"finished":true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate top-level JSON key"):
                MODULE.summarize(path)

    def test_bad_numeric_summary_metadata_is_rejected(self):
        report = _report()
        report["numeric_summary"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            self.write_json(path, report)
            with self.assertRaisesRegex(ValueError, "numeric_summary.normal"):
                MODULE.summarize(path)

    def test_invalid_unselected_array_is_still_rejected_streamingly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(
                '{"unused":[1,,2],"finished":true,"numeric_summary":{"normal":'
                '{"preparation_partition":{"effect_transaction_rejected":0}}},"rows":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Invalid JSON scalar"):
                MODULE.summarize(path)

    def test_stream_reader_handles_chunk_boundaries_inside_escapes(self):
        reader = MODULE._JsonStream(
            io.StringIO('{"k":"a\\u0041b","n":[1,2]}'), chunk_size=2
        )
        reader.take("{")
        self.assertEqual(reader.decode_value(), "k")
        reader.take(":")
        reader.skip_value()
        reader.take(",")
        self.assertEqual(reader.decode_value(), "n")
        reader.take(":")
        reader.skip_value()
        reader.take("}")


if __name__ == "__main__":
    unittest.main()
