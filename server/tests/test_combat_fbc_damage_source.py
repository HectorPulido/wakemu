"""Focused contract tests for retaining the exact native damage source PV."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_damage_source import native_damage_source


class TrapDamageSourceTests(unittest.TestCase):
    def setUp(self):
        # The values below are from the real 3856/5552 probe. The full native
        # constructor and PC population are verified by registered_area_pv in
        # the production path and by the read-only native probe.
        self.trap_pcs = {18: -296, 20: -296}
        self.source = SimpleNamespace(
            id=-300,
            native_is_area=True,
            native_characteristics=self.trap_pcs,
        )
        self.owner = SimpleNamespace(id=7, effect_stats={18: 900, 20: 900})
        self.fight = SimpleNamespace(actors={7: self.owner})
        self.row = {"native_area_contract": "fbc"}

    def resolve(self, contract=None, source=None):
        if contract is not None:
            self.row["native_area_contract"] = contract
        area_source = self.source if source is None else source
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=area_source,
        ), patch(
            "wakfu_server.combat_state_managers.retained_area_pv_row",
            return_value=self.row,
        ):
            return native_damage_source(self.fight, -300)

    def test_fbc_preserves_its_own_characteristics_without_owner_alias(self):
        resolved = self.resolve("fbc")
        self.assertIs(resolved, self.source)
        self.assertIs(resolved.native_characteristics, self.trap_pcs)
        self.assertIsNot(resolved.native_characteristics, self.owner.effect_stats)
        self.assertNotIn(-300, self.fight.actors)

    def test_fap_and_fay_keep_their_no_characteristics_contract(self):
        plain = SimpleNamespace(
            id=-300, native_is_area=True, native_characteristics=None
        )
        for contract in ("faP", "faY"):
            with self.subTest(contract=contract):
                self.assertIs(self.resolve(contract, plain), plain)

    def test_corrupt_fbc_source_and_other_area_contracts_fail_closed(self):
        missing_trap_pcs = SimpleNamespace(
            id=-300, native_is_area=True, native_characteristics=None
        )
        with self.assertRaisesRegex(ValueError, "Changed native faV source"):
            self.resolve("fbc", missing_trap_pcs)
        for contract in ("fbd", "faW", "unknown"):
            with self.subTest(contract=contract):
                with self.assertRaisesRegex(
                    ValueError, "Unsupported native damage source"
                ):
                    self.resolve(contract)

    def test_invalid_fap_fay_characteristics_are_not_preserved_as_trap_stats(self):
        for contract in ("faP", "faY"):
            with self.subTest(contract=contract):
                with self.assertRaisesRegex(ValueError, "Changed native faV source"):
                    self.resolve(contract, self.source)


if __name__ == "__main__":
    unittest.main()
