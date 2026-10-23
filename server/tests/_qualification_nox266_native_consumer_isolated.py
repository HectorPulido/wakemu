"""Qualify the post-start policy and production caller in an isolated process."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedNox266(unittest.TestCase):
    def runTest(self):
        names = [
            "test_nox_post_start_table_listener.NoxPostStartNativeConsumerTests.test_original_calendar_branch_creates_fatality_and_its_terminal_subscription"
        ]
        child = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", *names],
            env=dict(os.environ, PYTHONPATH="server:server/tests"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox266-original-calendar-native-consumer-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-14000:])


def qualify():
    return unittest.TestSuite([IsolatedNox266()])
