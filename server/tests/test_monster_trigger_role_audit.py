"""Structural trigger evidence is distinct from runtime activation proof."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_monster_trigger_roles import trigger_role


class TriggerRoleAuditTests(unittest.TestCase):
    def monster(self):
        return dict(
            ref=5661,
            min_level=248,
            max_level=253,
            fight_properties=[1],
            native_abilities=[dict(spell_id=8299)],
            initial_state_triples=[8649, 1, 1],
        )

    def test_native_subscriber_lineage_links_owned_spell_without_activation(self):
        effects = {
            "1": dict(
                effect_class=330, target_masks=[None] * 5 + [[1001], None], children=[2]
            ),
            "2": dict(
                effect_class=426,
                parameters=[8299.0, 0.0],
                criteria="GetFightCurrentTableTurn() > 1",
            ),
        }
        row = trigger_role(self.monster(), {"8649": dict(effect_ids=[1])}, effects)
        link = row["owned_trigger_links"][0]
        self.assertEqual(link["spell_id"], 8299)
        self.assertEqual(link["inherited_subscriptions"][0]["event_bits"], [1001])
        self.assertEqual(link["criteria"], "GetFightCurrentTableTurn() > 1")
        self.assertFalse(row["runtime_validated"])
        self.assertFalse(row["excluded"])
        self.assertFalse(row["resources_changed"])

    def test_emitted_mask_is_not_a_subscription(self):
        effects = {
            "1": dict(effect_class=330, target_masks=[None] * 6 + [[1001]], children=[])
        }
        row = trigger_role(self.monster(), {"8649": dict(effect_ids=[1])}, effects)
        self.assertEqual(row["subscriber_evidence"], [])
        self.assertEqual(row["classification"], "skip_turn_role_unproven")

    def test_missing_graph_is_reported_not_guessed(self):
        row = trigger_role(self.monster(), {"8649": dict(effect_ids=[42])}, {})
        self.assertEqual(row["missing_effects"], ["42"])
        self.assertEqual(row["owned_trigger_links"], [])
        self.assertEqual(trigger_role(self.monster(), {}, {})["missing_states"], [8649])

    def test_nonowned_trigger_is_not_an_owned_spell_link(self):
        row = trigger_role(
            self.monster(),
            {"8649": dict(effect_ids=[1])},
            {"1": dict(effect_class=426, parameters=[9000.0, 0.0])},
        )
        self.assertEqual(row["owned_trigger_links"], [])

    def test_nonconstant_or_nonfinite_spell_slot_is_not_admitted(self):
        for parameters in (
            [8299.0, 1.0],
            [float("nan"), 0.0],
            [float("inf"), 0.0],
            [8299.0, float("nan")],
            [8299.0],
            [-8299.0, 0.0],
            [True, 0.0],
        ):
            with self.subTest(parameters=parameters):
                row = trigger_role(
                    self.monster(),
                    {"8649": dict(effect_ids=[1])},
                    {
                        "1": dict(
                            effect_class=426,
                            parameters=parameters,
                            target_masks=[None] * 5 + [[1001], None],
                        ),
                    },
                )
                self.assertEqual(row["owned_trigger_links"], [])
                self.assertEqual(row["unsubscribed_owned_trigger_links"], [])

    def test_unsubscribed_owned_trigger_is_reported_separately(self):
        row = trigger_role(
            self.monster(),
            {"8649": dict(effect_ids=[1])},
            {
                "1": dict(effect_class=426, parameters=[8299.0, 0.0]),
            },
        )
        self.assertEqual(row["owned_trigger_links"], [])
        self.assertEqual(row["unsubscribed_owned_trigger_links"][0]["spell_id"], 8299)
        self.assertEqual(row["classification"], "skip_turn_role_unproven")
