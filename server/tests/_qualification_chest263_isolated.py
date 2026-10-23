"""Run the reviewed staged reward contracts without touching the warm game heap."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class StagedChestProcess(unittest.TestCase):
    def runTest(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = "server:server/tests"
        result = subprocess.run(
            [sys.executable, ".runtime/chest-achievements-stage/run_staged_tests.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        path = Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/chest263-four-staged-child-process.log"
        )
        path.write_text(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout[-9000:])


def qualify():
    return unittest.TestSuite([StagedChestProcess()])
