"""Qualify the disjoint running-effect and PV namespaces outside both held realms."""
import os, subprocess, sys, unittest
from pathlib import Path


class IsolatedUidNamespaces(unittest.TestCase):
    def runTest(self):
        prefix = (
            "test_monster_area_pv_identity_allocation.AreaPVIdentityAllocationTests."
        )
        names = [
            "test_combat_effect_uids.EffectUIDTests",
            *[
                prefix + name
                for name in (
                    "test_ordinary_running_effect_can_still_overlap_actor_identity",
                    "test_active_retired_and_dead_actor_pvs_are_reserved",
                    "test_owned_effect_collision_keeps_counter_and_rollback_authority",
                    "test_exhausted_skip_does_not_consume_counter",
                )
            ],
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
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/effect-uid-five-and-area-pv-four-isolated-child.log"
        ).write_text(child.stdout)
        self.assertEqual(child.returncode, 0, child.stdout[-12000:])


def qualify():
    return unittest.TestSuite([IsolatedUidNamespaces()])
