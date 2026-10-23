"""Actual native transformation roots, class/sex selection and strict HMI scope."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.consumable_visual_effects import select


class ConsumableVisualEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "protocol/native-consumable-actions.json"
        cls.rows = {
            row["item_ref"]: row
            for row in json.loads(path.read_text())["items"]
            if row["native_type"] == 738
        }

    def test_actual_state531_selects_native_breed_sex_and_unconditional_color(self):
        state = self.rows[10363]["plan"]["states"][0]
        # This criterion subset never reads characteristic aliases.
        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            for sex, expected in ((False, 25601), (True, 25775)):
                result = select(dict(breed=1, sex=sex), state)
                self.assertEqual([node["id"] for node in result], [expected, 71553])
            # The installed original state has no Ouginak model operation.
            self.assertEqual(
                [node["id"] for node in select(dict(breed=15, sex=0), state)], [71553]
            )

    def test_all36_actual_plans_have_visual_selection_for_all18_classes_both_sexes(
        self,
    ):
        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            for row in self.rows.values():
                for breed in (*range(1, 17), 18, 19):
                    for sex in (0, 1):
                        selected = [
                            node
                            for state in row["plan"]["states"]
                            for node in select(dict(breed=breed, sex=sex), state)
                        ]
                        self.assertTrue(selected, (row["item_ref"], breed, sex))

    def test_unqualified_gameplay_hmi_and_context_are_rejected(self):
        original = self.rows[10380]["plan"]["states"][0]
        for mutation in ("generic", "hmi", "context", "event", "root"):
            state = copy.deepcopy(original)
            node = state["metadata"]["native_effects"]["43974"]
            if mutation == "generic":
                node["generic"] = 122
            elif mutation == "hmi":
                node["native_metadata"]["native_hmi_actions"]["rze"][0][
                    "type"
                ] = "GAMEPLAY"
            elif mutation == "context":
                node["criteria"] = "HasState(949)"
            elif mutation == "event":
                node["native_metadata"]["target_masks"][6] = [1001]
            else:
                state["effect_ids"] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                select(dict(breed=1, sex=0), state)
