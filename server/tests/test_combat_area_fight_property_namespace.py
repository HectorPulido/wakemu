"""Complete registered faV fbo authority never aliases native ffe IDs."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_state_managers import registered_area_pv
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)


class AreaFightPropertyNamespaceTests(unittest.TestCase):
    def fixture(self):
        definition = dict(
            type="HOUR", native_area_properties=list(range(15)), entry_masks=[]
        )
        row = dict(
            uid=91,
            reference=1551,
            cell=(2, 3, 0),
            native_area_contract="faZ",
            native_running_effect_manager=True,
            state_ledger=StateLedger(91),
        )
        fight = SimpleNamespace(actors={}, native_effect_areas={91: row})
        return fight, row, definition

    def resolve(self, fight, definition):
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1551": definition},
        ), patch("wakfu_server.combat_effect_area_geometry.refresh_area_geometry"):
            return registered_area_pv(fight, 91)

    def test_all_fbo_properties_do_not_grant_same_numeric_fight_properties(self):
        fight, row, definition = self.fixture()
        area = self.resolve(fight, definition)
        self.assertEqual(area.native_fight_properties, frozenset())
        context = ConditionContext(
            actors={
                "target": ConditionActor(
                    actor_id=91, fight_properties=area.native_fight_properties
                )
            }
        )
        for identity in range(123):
            self.assertFalse(
                evaluate_condition(f'HasFightProperty("target", {identity})', context)
            )

    def test_unknown_or_malformed_property_producer_never_becomes_empty_authority(self):
        for mutation in (
            dict(
                native_current_area_properties=[11],
                native_area_property_source="forged",
            ),
            dict(
                native_current_area_properties=[15],
                native_area_property_source="faV.rzt.eWs",
            ),
            dict(native_area_contract="unknown"),
        ):
            fight, row, definition = self.fixture()
            row.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.resolve(fight, definition)
