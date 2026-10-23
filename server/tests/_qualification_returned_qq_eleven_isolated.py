"""Qualify returned-glyph removal authority without changing the retained fight."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedReturnedQq(unittest.TestCase):
    def runTest(self):
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "test_combat_encounter_area_seed_removal_selection.SeedRemovalSelectionTests",
                "test_combat_encounter_area_seed_source.EncounterAreaSeedSourceTests",
            ],
            env=dict(os.environ, PYTHONPATH="server:server/tests"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/returned-qq-six-and-seed-source-five-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-14000:])


def qualify():
    return unittest.TestSuite([IsolatedReturnedQq()])
