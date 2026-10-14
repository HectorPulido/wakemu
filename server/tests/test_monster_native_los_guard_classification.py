import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from select_functional_native_contexts import classify_guard


class NativeLosGuardClassificationTests(unittest.TestCase):
    def actual_case(self):
        return json.loads(
            (
                Path(__file__).parent / "fixtures/monster_native_los_guard4110.json"
            ).read_text()
        )["raw_case"]

    def test_actual_grinch_blocked_los_stays_guarded_and_not_effectful(self):
        case = self.actual_case()
        before = copy.deepcopy(case)
        result = classify_guard(case)
        self.assertEqual(result["mode"], "native_guarded_not_effectful")
        self.assertFalse(result["effectful_claim_unchanged"])
        self.assertTrue(result["dormancy_permanent_not_inferred"])
        self.assertEqual(case, before)
        self.assertIn("twG", [g["native_result"] for g in result["guards"]])

    def test_missing_contradictory_or_error_los_authority_is_rejected(self):
        for mutation in (
            "missing_detail",
            "detail_true",
            "los_true",
            "error",
            "error_type",
            "unsupported_stage",
            "unsupported_error",
            "missing_flag",
        ):
            with self.subTest(mutation=mutation):
                case = self.actual_case()
                native = case["cast_diagnostics"][0]["details"][
                    "native_casting_diagnostic"
                ]
                trace = native["trace"]
                detail = next(e for e in trace if e["stage"] == "native_los_detail")
                if mutation == "missing_detail":
                    trace.remove(detail)
                elif mutation == "detail_true":
                    detail["value"]["result"] = True
                elif mutation == "los_true":
                    next(e for e in trace if e["stage"] == "native_los")["value"] = True
                elif mutation == "error":
                    trace.append(
                        {"stage": "criterion_actor", "error": "UnknownCondition"}
                    )
                elif mutation == "error_type":
                    detail["value"]["error_type"] = "MissingAuthority"
                elif mutation == "unsupported_stage":
                    trace.append({"stage": "unsupported_criterion", "value": False})
                elif mutation == "unsupported_error":
                    case["errors"]["ValueError: Unsupported primitive"] = 1
                elif mutation == "missing_flag":
                    del native["selected_casting_flags"]["line_of_sight"]
                self.assertIsNone(classify_guard(case))
