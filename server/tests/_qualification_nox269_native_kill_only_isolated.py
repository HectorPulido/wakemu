"""Qualify terminal-helper settlement without changing either retained scope."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class Isolated269(unittest.TestCase):
    def runTest(self):
        names = [
            "test_nox_terminal_helper_cleanup.NoxTerminalHelperCleanupTests.test_original_kill_dispatch_private_preview_and_terminal_journal_once"
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
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox269-only-native-kill-authentic-state-uid-and-global-pv-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-16000:])


def qualify():
    return unittest.TestSuite([Isolated269()])
