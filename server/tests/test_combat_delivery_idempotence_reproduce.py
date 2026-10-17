"""Closed correction evidence rejects altered inputs and false qualifications."""
from copy import deepcopy
import unittest

from tools import combat_delivery_idempotence_reproduce as replay


class DeliveryCorrectionEvidenceTests(unittest.TestCase):
    def prefix_facts(self):
        return dict(
            input_delivery_unchanged=True,
            input_ids=[2, 3, 4],
            error=None,
            fight_reference_preserved=True,
            actor_reference_preserved=True,
            first_same_object=True,
            repeat_same_object=True,
            prefix_bytes_preserved=True,
            prefix_correlations_preserved=True,
            first_ids=[2, 3, 4],
            second_ids=[2, 3, 4],
            first_counter=4,
            final_counter=4,
        )

    def sealed_case(self):
        before = dict(schema="typed-input", nodes=[dict(native_id=2)])
        result = dict(recorded="observation")
        return dict(
            scenario="prepared-prefix",
            before=before,
            before_sha256=replay._json_hash(before),
            observed_source_a=dict(
                result=result,
                result_sha256=replay._json_hash(result),
                facts=self.prefix_facts(),
                qualifies_source_c=True,
            ),
        )

    def test_changed_input_or_recorded_outcome_is_not_reproduction_evidence(self):
        original = self.sealed_case()
        replay.validate_closed_case(original)
        changed = deepcopy(original)
        changed["before"]["nodes"][0]["native_id"] = 5
        with self.assertRaisesRegex(ValueError, "input digest"):
            replay.validate_closed_case(changed)
        changed = deepcopy(original)
        changed["observed_source_a"]["result"]["recorded"] = "different"
        with self.assertRaisesRegex(ValueError, "observation digest"):
            replay.validate_closed_case(changed)

    def test_renumbered_prefix_or_lost_correlation_cannot_pass_idempotence_gate(self):
        original = self.prefix_facts()
        self.assertTrue(replay.qualifies_c("prepared-prefix", original))
        for field, value in (
            ("first_ids", [5, 6, 7]),
            ("final_counter", 7),
            ("prefix_correlations_preserved", False),
            ("repeat_same_object", False),
        ):
            with self.subTest(field=field):
                changed = deepcopy(original)
                changed[field] = value
                self.assertFalse(replay.qualifies_c("prepared-prefix", changed))
        case = self.sealed_case()
        case["observed_source_a"]["facts"]["first_ids"] = [5, 6, 7]
        with self.assertRaisesRegex(ValueError, "classification"):
            replay.validate_closed_case(case)

    def test_capsule_cannot_select_an_unknown_executable_recipe(self):
        case = self.sealed_case()
        case["scenario"] = "user_supplied_module.callable"
        with self.assertRaisesRegex(ValueError, "Unknown closed"):
            replay.validate_closed_case(case)


if __name__ == "__main__":
    unittest.main()
