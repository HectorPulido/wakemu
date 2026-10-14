from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_native_trigger_witness import annotate_pending, source_callers


class NativeTriggerWitnessTests(unittest.TestCase):
    def fixture(self):
        document = json.loads(
            (
                Path(__file__).parent
                / "fixtures/monster_native_trigger_source_row.json"
            ).read_text()
        )
        row = document["rows"][0]
        spell = row["native_initialization"]["source_paths"][0]["spell_id"]
        return document, dict(reference=row["ref"], spell_id=spell)

    def test_real_native_callback_marks_pending_without_qualifying_or_hiding_rejection(
        self,
    ):
        document, context = self.fixture()
        original = dict(status="pending", errors={"native casting rejection": 1})
        result = annotate_pending(
            original, context, document, {"sha256": "source-receipt"}
        )
        self.assertEqual(result["status"], "pending")
        self.assertEqual(
            result["native_execution_domain_status"], "pending_native_trigger_witness"
        )
        self.assertEqual(result["errors"], original["errors"])
        self.assertFalse(
            result["native_trigger_source"]["actual_trigger_execution_proven"]
        )
        self.assertNotIn("native_execution_domain_status", original)

    def test_spell_grant649_is_not_a_native_cast_trigger(self):
        document, context = self.fixture()
        for row in document["rows"][0]["native_initialization"]["source_paths"]:
            row["family"] = 649
        self.assertEqual(source_callers(document, context), [])

    def test_other_owner_or_spell_cannot_inherit_trigger_source(self):
        document, context = self.fixture()
        context["reference"] = -1
        self.assertEqual(source_callers(document, context), [])

    def test_actual_validated_cast_is_not_relabelled_as_trigger_pending(self):
        document, context = self.fixture()
        case = dict(status="validated")
        self.assertIs(annotate_pending(case, context, document, {}), case)


if __name__ == "__main__":
    unittest.main()
