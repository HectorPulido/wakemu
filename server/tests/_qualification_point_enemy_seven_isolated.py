"""Qualify the fixed chosen-PV resolver in a small process, preserving both live realms."""
import os, subprocess, sys, unittest
from pathlib import Path


class IsolatedPointEnemy(unittest.TestCase):
    def runTest(self):
        names = [
            "test_combat_point_enemy_chosen_recipient.PointEnemyChosenRecipientTests",
            "test_combat_effect_resolver.NativeResolverTests.test_fresh_owned_area_selector_reselects_qq_but_replay_keeps_pv",
            "test_combat_effect_resolver.NativeResolverTests.test_fresh_original_controller_child_reselects_controller_not_trigger_enemy",
            "test_combat_effect_resolver.NativeResolverTests.test_transmitted_rebound_point_recipient_keeps_identity",
        ]
        env = dict(os.environ, PYTHONPATH="server:server/tests")
        child = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", *names],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/point-enemy-four-original-contracts-and-three-guards-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-12000:])


def qualify():
    return unittest.TestSuite([IsolatedPointEnemy()])
