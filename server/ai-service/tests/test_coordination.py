"""Regressions for checkpoint-backed team coordination scoring."""
import copy
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.planning import planner
from test_tactical import actor, snapshot, add_state, transition, cast


def checkpoint(data, *, focus=None, reserved=(), revision=None):
    data["teamContext"] = {
        "fightInstanceId": data["fightInstanceId"],
        "stateRevision": data["stateRevision"] if revision is None else revision,
        "team": 1,
        "focusId": focus,
        "reservedCells": [list(cell) for cell in reserved],
    }
    return data


class CoordinationTests(unittest.TestCase):
    def test_reservation_score_is_a_delta_from_root_position(self):
        data = snapshot()
        current = (0, 0, 0)
        checkpoint(data, reserved=[current])

        stays = planner.decide(data)
        self.assertEqual(stays["decision"]["actions"], [{"type": "end_turn"}])
        self.assertEqual(stays["decision"]["score_components"]["coordination"], 0)

        moved = copy.deepcopy(data["actors"])
        moved[0]["position"] = [1, 0, 0]
        data["states"][0]["transitions"] = [
            transition(
                "leave-reservation", {"type": "move", "path": [[1, 0, 0]]}, "outside"
            )
        ]
        add_state(data, "outside", moved)
        leaves = planner.decide(data)
        self.assertEqual(
            leaves["decision"]["actions"], [{"type": "move", "path": [[1, 0, 0]]}]
        )
        self.assertEqual(leaves["decision"]["score_components"]["coordination"], 5)

        enters_data = snapshot()
        enters_data["actors"][0]["position"] = [1, 0, 0]
        enters_data["states"][0]["actors"][0]["position"] = [1, 0, 0]
        checkpoint(enters_data, reserved=[current])
        enters_data["states"][0]["transitions"] = [
            transition(
                "enter-reservation", {"type": "move", "path": [[0, 0, 0]]}, "inside"
            )
        ]
        enters = copy.deepcopy(enters_data["actors"])
        enters[0]["position"] = [0, 0, 0]
        add_state(enters_data, "inside", enters, positionValue=10)
        enters_data["policy"] = {"weights": {"position": 1}}
        entering = planner.decide(enters_data)
        self.assertEqual(
            entering["decision"]["actions"], [{"type": "move", "path": [[0, 0, 0]]}]
        )
        self.assertEqual(entering["decision"]["score_components"]["coordination"], -5)

    def test_stale_revision_and_dead_or_friendly_focus_are_rejected(self):
        stale = snapshot()
        checkpoint(stale, revision=stale["stateRevision"] - 1)
        with self.assertRaisesRegex(ValueError, "Stale or foreign team checkpoint"):
            planner.decide(stale)

        dead = snapshot()
        dead["actors"][1]["hp"] = 0
        dead["states"][0]["actors"] = copy.deepcopy(dead["actors"])
        checkpoint(dead, focus=1)
        with self.assertRaisesRegex(ValueError, "Invalid team focus"):
            planner.decide(dead)

        friendly = snapshot()
        checkpoint(friendly, focus=-2)
        with self.assertRaisesRegex(ValueError, "Invalid team focus"):
            planner.decide(friendly)

    def test_focus_bonus_uses_effective_damage(self):
        data = snapshot()
        checkpoint(data, focus=1)
        damaged = copy.deepcopy(data["actors"])
        damaged[1]["hp"] -= 10
        data["states"][0]["transitions"] = [transition("hit-focus", cast(1), "damaged")]
        add_state(data, "damaged", damaged)

        result = planner.decide(data)

        self.assertEqual(result["decision"]["score_components"]["damage"], 10)
        self.assertEqual(result["decision"]["score_components"]["coordination"], 0.5)

    def test_two_encounter_checkpoints_are_isolated_under_concurrency(self):
        reserved = snapshot()
        open_cell = snapshot()
        reserved.update(requestId="fight-A-request", fightInstanceId="fight-A")
        open_cell.update(requestId="fight-B-request", fightInstanceId="fight-B")
        move = {"type": "move", "path": [[1, 0, 0]]}
        after = copy.deepcopy(reserved["actors"])
        after[0]["position"] = [1, 0, 0]
        reserved["states"][0]["transitions"] = [transition("move", move, "moved")]
        add_state(reserved, "moved", after, positionValue=2)
        open_cell["states"] = copy.deepcopy(reserved["states"])
        checkpoint(reserved, reserved=[(1, 0, 0)])
        checkpoint(open_cell)

        with ThreadPoolExecutor(max_workers=2) as pool:
            response_a, response_b = list(
                pool.map(planner.decide, (reserved, open_cell))
            )

        self.assertEqual(response_a["fightInstanceId"], "fight-A")
        self.assertEqual(response_b["fightInstanceId"], "fight-B")
        self.assertEqual(response_a["decision"]["actions"], [{"type": "end_turn"}])
        self.assertEqual(response_b["decision"]["actions"], [move])

    def test_repeated_healing_scores_net_hp_once(self):
        data = snapshot()
        ally = actor(-3, 1, (1, 0, 2), hp=20)
        data["actors"].append(ally)
        data["states"][0]["actors"].append(copy.deepcopy(ally))
        first = copy.deepcopy(data["actors"])
        first[2]["hp"] = 25
        second = copy.deepcopy(first)  # Second heal is fully overheal.
        enemy_hurt = copy.deepcopy(second)
        enemy_hurt[1]["hp"] -= 4
        heal = cast(-3, (1, 0, 2), spell_id=200)
        followup = cast(-3, (1, 0, 2), spell_id=201)
        data["states"][0]["transitions"] = [transition("heal-once", heal, "healed")]
        add_state(
            data,
            "healed",
            first,
            [transition("heal-again-and-hit", followup, "followup")],
        )
        add_state(data, "followup", enemy_hurt)

        result = planner.decide(data)

        self.assertEqual(result["decision"]["actions"], [heal, followup])
        self.assertEqual(result["decision"]["score_components"]["healing"], 5)
        self.assertEqual(result["decision"]["score_components"]["damage"], 4)

    def test_search_can_move_then_heal_when_combined_forecast_scores_more(self):
        data = snapshot()
        data["actors"][1]["position"] = [2, 0, 2]
        data["states"][0]["actors"][1]["position"] = [2, 0, 2]
        ally = actor(-3, 1, (2, 0, 0), hp=20)
        data["actors"].append(ally)
        data["states"][0]["actors"].append(copy.deepcopy(ally))
        moved = copy.deepcopy(data["actors"])
        moved[0]["position"] = [1, 0, 0]
        healed_direct = copy.deepcopy(data["actors"])
        healed_direct[2]["hp"] = 25
        moved_healed = copy.deepcopy(moved)
        moved_healed[2]["hp"] = 25
        move = {"type": "move", "path": [[1, 0, 0]]}
        direct_heal = cast(-3, (2, 0, 0), spell_id=200)
        after_move_heal = cast(-3, (2, 0, 0), spell_id=200)
        data["states"][0]["transitions"] = [
            transition("move-first", move, "nearby"),
            transition("heal-direct", direct_heal, "direct-heal"),
        ]
        add_state(
            data,
            "nearby",
            moved,
            [transition("heal-after-move", after_move_heal, "moved-healed")],
            positionValue=10,
        )
        add_state(data, "direct-heal", healed_direct)
        add_state(data, "moved-healed", moved_healed, positionValue=10)
        data["policy"] = {"weights": {"position": 2, "resources": 0}}

        result = planner.decide(data)

        self.assertEqual(result["decision"]["actions"], [move, after_move_heal])
        self.assertEqual(result["decision"]["score_components"]["healing"], 5)
        self.assertEqual(result["decision"]["score_components"]["position"], 20)


if __name__ == "__main__":
    unittest.main()
