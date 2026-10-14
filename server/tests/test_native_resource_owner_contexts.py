"""Alternate ownership scheduling cannot grant resources or clamp native PL."""
import unittest
from copy import deepcopy
from native_resource_owner_contexts import plan_alternate_resource_owners


class AlternateResourceOwnerTests(unittest.TestCase):
    def data(self):
        monsters = {
            r: dict(
                min_level=level, native_abilities=[dict(spell_id=9, level_parameter=-1)]
            )
            for r, level in ((1, 2), (2, 3), (3, 4))
        }
        profiles = {
            str(r): dict(
                base_level=m["min_level"],
                at_base_level={
                    str(s): dict(current=(wp if s == 4 else 8)) for s in (2, 3, 4)
                },
            )
            for r, m in monsters.items()
            for wp in [0 if r == 2 else 3]
        }
        return (
            [dict(reference=1, spell_id=9)],
            monsters,
            profiles,
            {"9": dict(costs=[[2, 0, 1]] * 4)},
            {},
        )

    def test_affordable_real_alternate_precedes_zero_wp_owner(self):
        data = self.data()
        before = deepcopy(data)
        result = plan_alternate_resource_owners(*data)
        self.assertEqual(result["spells"][0]["selected_context"]["reference"], 3)
        self.assertEqual(data, before)
        self.assertFalse(
            result["spells"][0]["selected_context"]["actual_available_proven"]
        )

    def test_class_only_route_does_not_become_npc_or_wild_context(self):
        data = self.data()
        data[-1][3] = {"producers": [{"source_kind": "class"}]}
        result = plan_alternate_resource_owners(*data)
        self.assertIsNone(result["spells"][0]["selected_context"])

    def test_dual_route_retains_genuine_npc_context(self):
        data = self.data()
        data[-1][3] = {
            "producers": [
                {"source_kind": "class"},
                {"source_kind": "npc", "creator_ref": 8},
            ]
        }
        row = plan_alternate_resource_owners(*data)["spells"][0]["selected_context"]
        self.assertEqual(row["genuine_npc_creator_routes"][0]["creator_ref"], 8)

    def test_unknown_pl_bounds_are_not_clamped(self):
        data = self.data()
        data[1][3]["native_abilities"][0]["level_parameter"] = 205
        result = plan_alternate_resource_owners(*data)
        self.assertIsNone(result["spells"][0]["selected_context"])
        self.assertEqual(result["unresolved_source_contexts"][0]["spell_level"], 205)

    def test_duplicate_failed_spell_contexts_schedule_once(self):
        data = self.data()
        data[0].extend(data[0] * 2)
        self.assertEqual(len(plan_alternate_resource_owners(*data)["spells"]), 1)

    def test_failed_owner_is_not_rescheduled_using_base_resource_hint(self):
        data = self.data()
        data[1].pop(2)
        data[1].pop(3)
        self.assertIsNone(
            plan_alternate_resource_owners(*data)["spells"][0]["selected_context"]
        )
