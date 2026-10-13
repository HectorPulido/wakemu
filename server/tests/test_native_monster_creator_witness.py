"""Native creator discovery preserves real ownership and descriptor domains."""
import unittest
from native_monster_creator_witness import npc_creator_plans


class NativeMonsterCreatorPlanTests(unittest.TestCase):
    def source(self):
        return (
            {
                "rows": [
                    {
                        "ref": 3251,
                        "producers": [
                            {
                                "source_kind": "class",
                                "creator_ref": None,
                                "creator_spell": 4603,
                            },
                            {
                                "source_kind": "npc",
                                "creator_ref": 2437,
                                "creator_spell": 4603,
                                "family307_effect": 120894,
                                "source_path": ["spell:4603", "effect:120894"],
                            },
                        ],
                    }
                ]
            },
            {
                2437: {
                    "ref": 2437,
                    "min_level": 98,
                    "max_level": 115,
                    "native_abilities": [{"spell_id": 4603, "level_parameter": 9}],
                }
            },
        )

    def test_real_npc_high_creator_and_spell_override_preserved(self):
        index, native = self.source()
        plan = npc_creator_plans(index, native, 3251)[0]
        self.assertEqual(plan["creator_level"], 98)
        self.assertEqual(plan["spell_level_parameter"], 9)
        self.assertIsNone(plan["summon_level_override"])
        self.assertEqual(plan["source_kind"], "npc")

    def test_class_only_is_not_a_monster_producer(self):
        index, native = self.source()
        index["rows"][0]["producers"].pop()
        self.assertEqual(npc_creator_plans(index, native, 3251), [])

    def test_unowned_creator_spell_rejected(self):
        index, native = self.source()
        native[2437]["native_abilities"] = []
        with self.assertRaises(ValueError):
            npc_creator_plans(index, native, 3251)

    def test_duplicate_source_edges_do_not_multiply_attempts(self):
        index, native = self.source()
        index["rows"][0]["producers"] *= 5
        self.assertEqual(len(npc_creator_plans(index, native, 3251)), 1)
