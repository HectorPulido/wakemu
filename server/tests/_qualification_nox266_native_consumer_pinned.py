"""Qualify the post-start policy and production caller in an isolated process."""
import hashlib
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
        source = Path("server/tests/test_nox_post_start_table_listener.py")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
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
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        Path(
            ".runtime/parallel-readiness-20261021/nox266-native-consumer-qualified-source-sha.txt"
        ).write_text(before + "\n")
        self.assertEqual(child.returncode, 0, child.stdout[-14000:])


def qualify():
    return unittest.TestSuite([IsolatedNox266()])
