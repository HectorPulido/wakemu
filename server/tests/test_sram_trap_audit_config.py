import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from sram_trap_audit_config import (
    CANDIDATE_LIMIT,
    MAXIMUM_ELIGIBLE,
    validate_configuration,
)


class SramTrapAuditPreflightTests(unittest.TestCase):
    def test_default_harness_parameters_fit_production_selector_bounds(self):
        self.assertEqual(MAXIMUM_ELIGIBLE, 16)
        self.assertEqual(CANDIDATE_LIMIT, 256)
        validate_configuration(level=200, spell=5182)
        validate_configuration(level=1, spell=5183)
        validate_configuration(level=200, spell=5182, mover="enemy")

    def test_invalid_harness_arguments_reject_without_ready(self):
        for overrides in (
            {"maximum_eligible": 32},
            {"limit": 4097},
            {"level": 0},
            {"level": 201},
            {"spell": 315},
            {"maximum_eligible": True},
            {"mover": "synthetic"},
        ):
            with self.subTest(overrides=overrides):
                values = dict(level=200, spell=5182)
                values.update(overrides)
                with self.assertRaises(ValueError):
                    validate_configuration(**values)
