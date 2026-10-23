"""Qualify recipient reconstruction and affected hooks outside the retained realm."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class Isolated268(unittest.TestCase):
    def runTest(self):
        names = [
            "test_nox_faille_original_boss_recipient.NoxFailleOriginalBossRecipientTests",
            "test_ordinary_encounter_policy_admission.OrdinaryEncounterPolicyAdmissionTests.test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry",
            "test_combat_point_enemy_chosen_recipient.PointEnemyChosenRecipientTests",
            "test_combat_effect_resolver.NativeResolverTests.test_fresh_owned_area_selector_reselects_qq_but_replay_keeps_pv",
            "test_combat_effect_resolver.NativeResolverTests.test_fresh_original_controller_child_reselects_controller_not_trigger_enemy",
            "test_combat_effect_resolver.NativeResolverTests.test_transmitted_rebound_point_recipient_keeps_identity",
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
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox268-three-pg-ordinary-one-point-seven-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-16000:])


def qualify():
    return unittest.TestSuite([Isolated268()])
