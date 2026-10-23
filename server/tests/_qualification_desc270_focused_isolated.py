"""Qualify descending native health ordering in an isolated draft-policy schema."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedDescending270(unittest.TestCase):
    def runTest(self):
        names = [
            "test_native_descending_health_ordering.DescendingHealthOrderingTests",
            "test_native_health_ordering_authority_postgres.NativeHealthOrderingAuthorityPostgresTests",
            "test_combat_target_health_ordering.HealthOrderingTests",
            "test_monster_group_health_ordering_flag.GroupHealthOrderingFlagTests",
        ]
        env = dict(
            os.environ,
            PYTHONPATH="server:server/tests",
            WAKFU_HEALTH_ORDERING_MIGRATION=str(
                Path(
                    ".runtime/rushu-phase-review-20261021/flag25-native/270_native_descending_health_ordering_authority.sql"
                ).resolve()
            ),
        )
        child = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", *names],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/desc270-new-six-and-existing-health-order-guards-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-16000:])


def qualify():
    return unittest.TestSuite([IsolatedDescending270()])
