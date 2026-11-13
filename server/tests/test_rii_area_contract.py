"""Only the authenticated owner can advance a complete multi-sack cast."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_area_contract as area


class AreaContractTests(unittest.TestCase):
    def fight(self):
        return SimpleNamespace(
            phase="active",
            actors={
                1: SimpleNamespace(team=0),
                **{target: SimpleNamespace(team=1) for target in (-1, -2, -3, -4)},
            },
            rii_area_lesson_contract={
                "owner": 1,
                "targets": [-1, -2, -3, -4],
                "hits": 0,
                "actions": [],
            },
            allocate_effect_uid=lambda: 1,
        )

    def test_initialization_is_bound_to_exact_opposing_sacks(self):
        fight = self.fight()
        with patch(
            "wakfu_server.rii_lesson_grants.install", return_value=[11, 12, 13]
        ) as grant:
            self.assertTrue(area.initialize(fight, [], action_id=2))
            self.assertEqual(grant.call_args.kwargs["lesson"], "area")
            self.assertEqual(fight.rii_area_lesson_contract["grant_uids"], [11, 12, 13])
            with self.assertRaises(ValueError):
                area.initialize(fight, [], action_id=2)

    def test_one_incomplete_cast_never_combines_with_next(self):
        fight = self.fight()
        fight.rii_area_lesson_contract["initialized"] = True
        kwargs = dict(source_id=1, effect_reference=367103)
        self.assertFalse(
            area.complete_cast(fight, action_id=1, hit_ids=[-1, -2], **kwargs)
        )
        self.assertFalse(
            area.complete_cast(fight, action_id=2, hit_ids=[-3, -4], **kwargs)
        )
        self.assertEqual(fight.rii_area_lesson_contract["hits"], 0)
        self.assertTrue(
            area.complete_cast(fight, action_id=3, hit_ids=[-4, -3, -2, -1], **kwargs)
        )
        self.assertFalse(
            area.complete_cast(fight, action_id=3, hit_ids=[-1, -2, -3, -4], **kwargs)
        )


if __name__ == "__main__":
    unittest.main()
