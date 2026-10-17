"""Strict replay cannot silently accredit a different Python interpreter."""
import copy
import sys
import unittest
from unittest.mock import patch

from wakfu_server.combat_reproduction import (
    SCHEMA,
    digest,
    source_identity,
    _validate_case,
    execute_case,
)


class ReproductionEnvironmentTests(unittest.TestCase):
    def case(self, source):
        return dict(
            schema=SCHEMA,
            source=source,
            catalog={
                "revision": "fixture",
                "inventory_sha256": "0" * 64,
                "bundle_sha256": None,
            },
            clocks={},
            policies={},
            before=None,
            expected=None,
            boundary="isolated-runtime-action-not-live-session-recovery",
        )

    def test_interpreter_version_changes_identity_without_changing_source_files(self):
        identity = source_identity()
        self.assertEqual(identity["python"]["version"], list(sys.version_info[:3]))
        with patch("wakfu_server.combat_reproduction.sys.version_info", (3, 99, 0)):
            other = source_identity()
        self.assertEqual(identity["files"], other["files"])
        self.assertNotEqual(identity["sha256"], other["sha256"])
        _validate_case(self.case(identity))

    def test_legacy_source_is_readable_but_cannot_pass_strict_execution(self):
        identity = source_identity()
        legacy = {"files": identity["files"], "sha256": digest(identity["files"])}
        case = self.case(legacy)
        _validate_case(case)
        with patch(
            "wakfu_server.combat_reproduction.catalog_identity",
            side_effect=AssertionError("No catalog read"),
        ):
            with self.assertRaisesRegex(ValueError, "Combat sources differ"):
                execute_case(case)

    def test_tampered_or_malformed_interpreter_metadata_rejects(self):
        identity = source_identity()
        tampered = copy.deepcopy(identity)
        tampered["python"]["version"][1] += 1
        with self.assertRaisesRegex(ValueError, "source manifest"):
            _validate_case(self.case(tampered))
        malformed = copy.deepcopy(identity)
        malformed["python"]["version"][0] = True
        with self.assertRaisesRegex(ValueError, "interpreter identity"):
            _validate_case(self.case(malformed))


if __name__ == "__main__":
    unittest.main()
