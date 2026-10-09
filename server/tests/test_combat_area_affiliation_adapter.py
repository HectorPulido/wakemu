"""faV.j captures fighter bcM and preserves constructor -1 for other PVs."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter


class AreaAffiliationAdapterTests(unittest.TestCase):
    def adapter(self, *, fighter=True):
        adapter = object.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = object()
        adapter._actor = lambda p, a: SimpleNamespace(targeting={"is_eGj": fighter})
        return adapter

    def test_actual_bcM_is_captured_independently_of_obstacle_and_team(self):
        actor = SimpleNamespace(
            native_fight_affiliation=3, native_obstacle_id=5, team=1
        )
        preview = SimpleNamespace(actors={7: actor})
        adapter = self.adapter()
        self.assertEqual(adapter.area_affiliation(preview, 7), 3)
        actor.native_fight_affiliation = -2
        self.assertEqual(adapter.area_affiliation(preview, 7), -2)

    def test_only_proven_ordinary_creation_can_use_live_team(self):
        preview = SimpleNamespace(actors={7: SimpleNamespace(team=1)})
        adapter = self.adapter()
        with self.assertRaises(ValueError):
            adapter.area_affiliation(preview, 7)
        with patch(
            "wakfu_server.combat_summon.ordinary_roster_authority", return_value=True
        ):
            self.assertEqual(adapter.area_affiliation(preview, 7), 1)

    def test_nonfighter_owner_preserves_constructor_minus_one(self):
        preview = SimpleNamespace(
            actors={7: SimpleNamespace(native_fight_affiliation=3)}
        )
        self.assertEqual(self.adapter(fighter=False).area_affiliation(preview, 7), -1)

    def test_unknown_or_invalid_authority_rejects(self):
        preview = SimpleNamespace(
            actors={7: SimpleNamespace(native_fight_affiliation=128)}
        )
        with self.assertRaises(ValueError):
            self.adapter().area_affiliation(preview, 7)
        with self.assertRaises(ValueError):
            self.adapter(fighter=None).area_affiliation(preview, 7)

    def test_registered_area_owner_is_nonfighter_unknown_identity_rejects(self):
        adapter = self.adapter()
        preview = SimpleNamespace(actors={})
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=object(),
        ):
            self.assertEqual(adapter.area_affiliation(preview, 9), -1)
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=None
        ):
            with self.assertRaises(ValueError):
                adapter.area_affiliation(preview, 9)
