"""Offline sparse descriptors require explicit native summon-edge evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_monster_zero_resource_roles import classify


class ZeroResourceRoleTests(unittest.TestCase):
    def test_sparse_summon_is_preserved_and_other_sparse_role_stays_unknown(self):
        monsters = [
            dict(ref=i, raw_native=dict(ckP=hp, ckQ=ap, ckR=0), fight_properties=[28])
            for i, hp, ap in [(1, 1, 0), (2, 1, 0), (3, 100, 8)]
        ]
        document = dict(
            spells={"10": dict(levels=[[0, 0, [20]]])},
            effects={
                "20": dict(effect_class=330, children=[21]),
                "21": dict(effect_class=307, parameters=[1, 0, -2, 0]),
            },
        )
        rows = classify(
            monsters, [("native", document)], [dict(id=28, symbol="CANNOT_BE_SEDUCED")]
        )
        self.assertEqual(
            rows[0]["classification"], "summon_referenced_sparse_descriptor"
        )
        self.assertEqual(rows[0]["incoming_summon_edges"][0]["spell_id"], 10)
        self.assertEqual(rows[1]["classification"], "sparse_descriptor_role_unproven")
        self.assertEqual(rows[2]["classification"], "nonzero_descriptor_resources")
        self.assertTrue(
            all(not row["excluded"] and not row["resources_changed"] for row in rows)
        )

    def test_unreachable_effect_and_cyclic_graph_do_not_fabricate_parent_edges(self):
        monster = dict(ref=1, raw_native=dict(ckP=1, ckQ=0, ckR=0), fight_properties=[])
        document = dict(
            spells={"10": dict(levels=[[0, 0, [20]]])},
            effects={
                "20": dict(effect_class=330, children=[20]),
                "21": dict(effect_class=307, parameters=[1, 0]),
            },
        )
        row = classify([monster], [("native", document)], [])[0]
        self.assertEqual(row["incoming_summon_edges"], [])
        self.assertEqual(row["classification"], "sparse_descriptor_role_unproven")
