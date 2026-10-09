"""Native harness AP budget and ownership regressions."""
import sys
from pathlib import Path
import unittest
import queue
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import dungeon_combat_harness as driver


class AttackBudgetTests(unittest.TestCase):
    def test_rejection_probe_preserves_native_boundary_queue(self):
        from types import SimpleNamespace

        events = queue.Queue()
        events.put((12502, b"boundary"))
        events.put((674, b"rejection"))
        peer = SimpleNamespace(
            events=events, pending=[(13482, b"turn"), (12755, b"report")]
        )
        with patch.object(
            driver, "_command_text", return_value="Not current owned turn"
        ):
            with self.assertRaisesRegex(AssertionError, "Not current owned turn"):
                driver._wait_checkpoint(
                    None,
                    7,
                    lambda state: True,
                    timeout=1,
                    description="attack",
                    peer=peer,
                )
        self.assertEqual(events.qsize(), 2)
        self.assertEqual(len(peer.pending), 2)

    def run_budget(self, states):
        outcome = dict(
            attacked=True, moved=False, target_id=-1, hp_before=10, hp_after=5
        )
        with patch.object(driver, "checkpoint", side_effect=states), patch.object(
            driver,
            "checkpoint_turn_ready",
            side_effect=lambda state, actor: state.get("owner") == actor,
        ), patch.object(driver, "_attack_turn", return_value=outcome) as attack:
            result = driver.attack_owned_turn(
                None, {1: None}, 7, 1086, b"", 1, timeout=1
            )
        return result, attack.call_count

    def state(self, ap, owner=1):
        return dict(owner=owner, actors={"1": dict(ap=ap, controlled=True)})

    def test_six_ap_produces_two_legal_attacks(self):
        result, calls = self.run_budget([self.state(6), self.state(3), self.state(0)])
        self.assertEqual(calls, 2)
        self.assertEqual(len(result), 2)

    def test_no_ap_sends_no_attack(self):
        self.assertEqual(self.run_budget([self.state(0)]), ([], 0))

    def test_finished_stops_after_attack(self):
        self.assertEqual(self.run_budget([self.state(6), dict(phase="finished")])[1], 1)

    def test_changed_actor_stops_before_another_attack(self):
        self.assertEqual(self.run_budget([self.state(6), self.state(3, owner=2)])[1], 1)
