"""Real Cra summons and owned arrows must enumerate beacon area occupants."""
import json
import os
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class CraBeaconReactionTests(unittest.TestCase):
    def test_three_beacons_and_three_owned_elements_react_then_stop_after_removal(self):
        from audit_cra_beacon_manual_sequence import run

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "beacons.json"
            run(output, 200, True)
            rows = json.loads(output.read_text())["rows"]
        self.assertEqual(len(rows), 9)
        self.assertEqual({row["profile"] for row in rows}, {3798, 3799, 3800})
        self.assertEqual({row["arrow"] for row in rows}, {4810, 4816, 4820})
        for row in rows:
            with self.subTest(profile=row["profile"], arrow=row["arrow"]):
                self.assertTrue(row.get("secondary_reaction_verified"), row)
                self.assertLess(row["secondary_enemy_hp_delta"], 0)
                self.assertEqual(row["post_cleanup_enemy_hp_delta"], 0)
                self.assertTrue(row["cleanup_verified"])
                self.assertTrue(row["old_cell_reusable"])
