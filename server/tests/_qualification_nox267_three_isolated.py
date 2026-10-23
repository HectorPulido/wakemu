"""Qualify recurring publication without altering either retained realm."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class Isolated267(unittest.TestCase):
    def runTest(self):
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "test_nox_recurring_post_start_listener.NoxRecurringPostStartTests",
            ],
            env=dict(os.environ, PYTHONPATH="server:server/tests"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox267-three-recurring-post-start-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-15000:])


def qualify():
    return unittest.TestSuite([Isolated267()])
