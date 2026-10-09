import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_area_damage_guard import area_damage_has_no_resources
from wakfu_server.combat_damage_handler import NativeDamageHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_trap_area import install_trap_characteristics
from wakfu_server.combat_state_ledger import StateLedger


class PartialAreaDamageTests(unittest.TestCase):
    def fixture(self, contract="fbc"):
        definition = dict(
            type="TRAP",
            native_class="bcY",
            native_type_id=3,
            native_container_type=3,
            raw_bdh=[1, 0],
            native_area_properties=[3, 9, 12],
            entry_masks=[10008],
        )
        row = dict(
            uid=901,
            reference=778,
            native_area_contract=contract,
            cell=(1, 0, 0),
            native_running_effect_manager=True,
            state_ledger=StateLedger(901),
        )
        if contract == "fbc":
            install_trap_characteristics(row, definition)
        if contract == "faY":
            definition["type"] = "GLYPH"
        actor = SimpleNamespace(id=7, position=(0, 0, 0))
        fight = SimpleNamespace(
            actors={7: actor},
            native_effect_areas={901: row},
            phase="active",
            current=actor,
        )
        return fight, row, definition

    def test_actual_trap_subset_has_no_hp_or_armor_and_stays_unchanged(self):
        fight, row, definition = self.fixture()
        before = dict(row["native_trap_characteristics"])
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"778": definition},
        ):
            self.assertTrue(area_damage_has_no_resources(fight, 901))
        self.assertEqual(row["native_trap_characteristics"], before)
        self.assertEqual(len(before), 10)
        self.assertNotIn("hp", row)

    def test_unknown_pv_does_not_supply_a_noop_proof(self):
        fight, row, definition = self.fixture("unknown")
        self.assertFalse(area_damage_has_no_resources(fight, 902))
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"778": definition},
        ):
            with self.assertRaises(ValueError):
                area_damage_has_no_resources(fight, 901)

    def test_plain_fav_has_no_invented_resources(self):
        fight, row, definition = self.fixture("faY")
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"778": definition},
        ):
            self.assertTrue(area_damage_has_no_resources(fight, 901))
        self.assertNotIn("effect_stats", row)

    def test_runner_delivers_four_phases_without_calculation_packet_or_resource_write(
        self,
    ):
        fight, row, definition = self.fixture()
        packets, phases = [], []
        handler = NativeDamageHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 99,
            context=lambda *args: self.fail(
                "No arithmetic context on native C early return"
            ),
            rng=lambda count: 1,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *args, **kw: phases.append(kw)
        )
        effect = {"effect_class": 3}
        invocation = EffectInvocation(17, 1, 7, 901, (1, 0, 0))
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"778": definition},
        ):
            prepared = handler.prepare(effect, None, invocation)
            self.assertTrue(handler(effect, None, prepared))
        self.assertEqual([item["channel"] for item in phases], [1, 2, 3, 4])
        self.assertEqual([item["value"] for item in phases], [0, 0, 0, 0])
        self.assertEqual(packets, [])
        self.assertNotIn("hp", row)
