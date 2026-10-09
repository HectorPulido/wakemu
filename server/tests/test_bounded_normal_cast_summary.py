import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "bounded_summary",
    Path(__file__).resolve().parents[1] / "tools/summarize_bounded_normal_casts.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BoundedSummaryTests(unittest.TestCase):
    def test_stream_keeps_only_bounded_owned_actions_and_exact_row_identity(self):
        rejected = dict(
            native_casting_diagnostic=dict(
                criterion="HasState(123)",
                trace=[dict(stage="criterion_cell", value=False)],
            ),
            authority_unresolved=False,
        )
        action = dict(
            reference=10,
            origin="normal_owned_deck",
            status="bounded_search_exhausted",
            target_selection=dict(
                rejected=[rejected],
                candidate_count=45,
                checked_count=32,
                search_complete=False,
            ),
        )
        report = dict(
            rows=[
                dict(
                    breed=1,
                    level=20,
                    runtime_access=dict(
                        actions=[
                            action,
                            dict(action, reference=11, status="prepared_transaction"),
                        ]
                    ),
                ),
                dict(
                    breed=2,
                    level=200,
                    runtime_access=dict(actions=[dict(action, reference=12)]),
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(report, indent=2) + "\n")
            result = module.summarize(path)
        self.assertEqual(result["bounded_pairs"], 2)
        self.assertEqual(
            [(p["breed"], p["level"], p["spell_reference"]) for p in result["pairs"]],
            [(1, 20, 10), (2, 200, 12)],
        )
        self.assertEqual(result["failed_stage_counts"], {"criterion_cell": 2})
        self.assertEqual(
            result["pairs"][0]["source_search_tags"], ["native_state_transition"]
        )
        self.assertFalse(result["full_functional_completion"])
