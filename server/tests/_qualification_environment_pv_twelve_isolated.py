"""Qualify constructor PV reservations without changing retained fights."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedEnvironmentPV(unittest.TestCase):
    def runTest(self):
        names = [
            "test_environment_glyph_pv_identity_allocation.EnvironmentGlyphPVIdentityAllocationTests",
            "test_monster_area_pv_identity_allocation.AreaPVIdentityAllocationTests",
            "test_combat_effect_uids.EffectUIDTests",
        ]
        child = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", *names],
            env=dict(os.environ, PYTHONPATH="server:server/tests"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/environment-pv-two-and-existing-ten-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-14000:])


def qualify():
    return unittest.TestSuite([IsolatedEnvironmentPV()])
