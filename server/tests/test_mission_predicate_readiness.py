import unittest
import json
from pathlib import Path

import inspect_mission_predicate_readiness as readiness


class MissionPredicateReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = readiness.source_support()

    def test_source_support_tracks_registry_dispatch_authority_and_npc_context(self):
        support = self.support
        self.assertIn("IsAchievementActive", support["registry"])
        self.assertIn("IsAchievementActive", support["dispatch"])
        self.assertIn("IsAchievementActive", support["authority"])
        self.assertIn("CanResetAchievement", support["contextual"])
        self.assertTrue(support["reset_callback"])

    def test_compound_expression_and_quoted_arguments_are_parsed(self):
        result = readiness.inspect_expression(
            'GetBooleanSystemConfiguration("a,b") && IsAchievementActive(1985)',
            "quest_earning",
            self.support,
        )
        self.assertEqual("ready", result["status"])
        self.assertEqual(
            {"GetBooleanSystemConfiguration", "IsAchievementActive"},
            {call["name"] for call in result["calls"]},
        )
        self.assertEqual(
            1,
            next(
                call["argument_count"]
                for call in result["calls"]
                if call["name"] == "GetBooleanSystemConfiguration"
            ),
        )

    def test_removed_shared_predicate_support_fails_closed(self):
        support = dict(self.support)
        for key in ("registry", "dispatch", "authority", "query_dispatch"):
            support[key] = set(support[key]) - {"IsAchievementActive"}
        result = readiness.inspect_expression(
            "IsAchievementActive(1985)", "quest_earning", support
        )
        self.assertEqual("requires_adapter", result["status"])
        self.assertEqual("requires_adapter", result["calls"][0]["status"])

    def test_npc_instance_adapter_is_not_claimed_for_earning_context(self):
        npc = readiness.inspect_expression(
            "GetInstanceId() == 3", "npc_dialogue", self.support
        )
        earning = readiness.inspect_expression(
            "GetInstanceId() == 3", "quest_earning", self.support
        )
        self.assertEqual("ready", npc["status"])
        self.assertEqual("npc_adapter", npc["calls"][0]["status"])
        self.assertEqual("requires_adapter", earning["status"])

    def test_reset_predicate_requires_explicit_recurring_context_and_callback(self):
        expression = "CanResetAchievement(1985)"
        unqualified = readiness.inspect_expression(
            expression, "npc_dialogue", self.support
        )
        qualified = readiness.inspect_expression(
            expression,
            "npc_dialogue",
            self.support,
            recurring_reset_ids={1985},
        )
        no_callback_support = dict(self.support, reset_callback=False)
        no_callback = readiness.inspect_expression(
            expression,
            "npc_dialogue",
            no_callback_support,
            recurring_reset_ids={1985},
        )
        self.assertEqual("requires_adapter", unqualified["status"])
        self.assertEqual("ready", qualified["status"])
        self.assertEqual("qualified_recurring_context", qualified["calls"][0]["status"])
        self.assertEqual("requires_adapter", no_callback["status"])

    def test_audit_scans_published_earning_and_reviewed_graph_only(self):
        native = {
            "definitions": [
                {
                    "d": 10,
                    "aqb": False,
                    "cjI": "IsAchievementActive(99)",
                    "cjJ": [{"d": 101, "ckc": "IsAchievementActive(98)", "cke": ""}],
                },
                {"d": 11, "aqb": True, "cjI": "Unknown(1)", "cjJ": []},
                {"d": 12, "aqb": False, "cjI": "Unrelated(1)", "cjJ": []},
            ]
        }
        publication = {
            "profiles": [
                {
                    "profile_id": "reviewed",
                    "document": {"bindings": [{"quest_id": 10, "objective_id": 101}]},
                }
            ]
        }
        conversations = [
            {
                "placements": [{"graph": [[700, 1, 701]]}],
                "recurring_deliveries": [],
            }
        ]
        dialogues = {
            "nodes": [
                {
                    "id": 700,
                    "criteria": "GetInstanceId() == 3",
                    "choices": [{"id": 1, "criteria": "IsAchievementActive(97)"}],
                },
                {"id": 701, "criteria": "", "choices": []},
                {"id": 999, "criteria": "Unrelated(1)", "choices": []},
            ]
        }
        report = readiness.audit(
            native, publication, conversations, dialogues, self.support
        )
        criteria = report["criteria"]
        self.assertEqual(
            {"cjI", "ckc", "cke"},
            {row["field"] for row in criteria if row.get("quest_id") == 10},
        )
        self.assertFalse(any(row.get("quest_id") in {11, 12} for row in criteria))
        self.assertEqual(
            {700, 701}, {row["node_id"] for row in criteria if "node_id" in row}
        )
        self.assertFalse(any(row.get("node_id") == 999 for row in criteria))
        self.assertFalse(
            any(
                row.get("node_id") == 700
                and row.get("field") == "node.criteria"
                and row["status"] != "ready"
                for row in criteria
            )
        )

    def test_audit_uses_generated_cji_for_native_mercenary_definition(self):
        root = Path(__file__).resolve().parents[1]
        index = json.loads(
            (root / "wakfu_server/achievements/native_mercenary_ranks.json").read_text()
        )
        rank = next(row for row in index["definitions"] if row["d"] == 2138)
        definition = {
            **rank,
            "cjW": True,
            "aqb": False,
            "native_class": "aJM",
            "cjJ": [{"d": 4231, "ckc": "", "cke": ""}],
        }
        effective = self.support["effective_criterion"](definition)
        self.assertTrue(effective.startswith("(GetLevel() >= 6 && "))
        for identity in (2143, 2144, 2145, 2146):
            self.assertIn(f"IsAchievementComplete({identity})", effective)

        publication = {
            "profiles": [
                {
                    "profile_id": "rank-gate",
                    "document": {
                        "bindings": [{"quest_id": 2138, "objective_id": 4231}]
                    },
                }
            ]
        }
        report = readiness.audit(
            {"definitions": [definition]}, publication, [], {"nodes": []}, self.support
        )
        earned = next(
            row
            for row in report["criteria"]
            if row.get("quest_id") == 2138 and row.get("field") == "effective_cjI"
        )
        self.assertEqual("ready", earned["status"])
        self.assertIn("GetLevel() >= 6", earned["expression"])
        self.assertEqual("", definition["cjI"])

        mutated = {**definition, "d": 999999}
        with self.assertRaises(ValueError):
            self.support["effective_criterion"](mutated)


if __name__ == "__main__":
    unittest.main()
