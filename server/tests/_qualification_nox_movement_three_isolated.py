"""Qualify scoped movement exclusions without modifying live code."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedMovement(unittest.TestCase):
    def runTest(self):
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "test_nox_calendar_movement_isolation.NoxCalendarMovementIsolationTests",
            ],
            env=dict(os.environ, PYTHONPATH="server:server/tests"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-calendar-movement-three-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-14000:])


def qualify():
    return unittest.TestSuite([IsolatedMovement()])
