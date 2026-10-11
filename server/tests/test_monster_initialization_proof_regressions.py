from dataclasses import dataclass
import sys
import unittest
from unittest.mock import patch

from validate_monster_spell_activation import (
    initialization_proven,
    nonretained_initial_states,
    placement_effects_proven,
)


@dataclass
class PlannedState:
    state_id: int
    level: int


class MonsterInitializationProofRegressionTests(unittest.TestCase):
    def native_modules(self, *, duration=0, realtime_duration=0, plan=None):
        state_plan = plan or [PlannedState(55, 5)]
        initial_states = type(sys)("wakfu_server.combat_summon_initial_states")
        initial_states.initial_state_plan = lambda triples, level: state_plan
        definitions = type(sys)("wakfu_server.combat_definitions")
        definitions.state_profile = lambda catalog, state_id, level: {
            "duration": duration,
            "realtime_duration": realtime_duration,
        }
        server_spell = type(sys)("wakfu_server.combat_server_spell")
        server_spell.states_catalog = lambda: {55: {}}
        return {
            "wakfu_server.combat_summon_initial_states": initial_states,
            "wakfu_server.combat_definitions": definitions,
            "wakfu_server.combat_server_spell": server_spell,
        }

    @staticmethod
    def placement(*, effect_count=2, carrier_count=1, size=20, verified=True):
        return {
            "verified": verified,
            "effect_count": effect_count,
            "state_carrier_count": carrier_count,
            "bytes": size,
            "sha256": "a" * 64,
        }

    def test_exact_native_zero_duration_nonretained_state_is_allowed(self):
        triples = [55, 0, 5]
        resolved = [dict(state_id=55, level=5)]
        receipt = {
            "initialized": True,
            "ref": 101,
            "descriptor_level": 5,
            "raw_triples": triples,
            "resolved_states": resolved,
            "applications": [dict(state_id=55, level=5, applied=True)],
            "nonretained_state_ids": [55],
            "placement_effects": self.placement(effect_count=1, carrier_count=0),
        }
        with patch.dict(sys.modules, self.native_modules()):
            self.assertEqual(nonretained_initial_states(triples, 5), [55])
            self.assertTrue(initialization_proven(101, 5, triples, receipt))

    def test_forged_nonretained_exemption_is_rejected(self):
        triples = [55, 2, 5]
        receipt = {
            "initialized": True,
            "ref": 101,
            "descriptor_level": 5,
            "raw_triples": triples,
            "resolved_states": [dict(state_id=55, level=5)],
            "applications": [dict(state_id=55, level=5, applied=True)],
            "nonretained_state_ids": [55],
            "placement_effects": self.placement(effect_count=1, carrier_count=0),
        }
        modules = self.native_modules(duration=3, realtime_duration=0)
        with patch.dict(sys.modules, modules):
            self.assertEqual(nonretained_initial_states(triples, 5), [])
            self.assertFalse(initialization_proven(101, 5, triples, receipt))

    def test_legacy_receipt_must_prove_every_raw_state_carrier(self):
        receipt = self.placement(effect_count=3, carrier_count=1)
        self.assertTrue(placement_effects_proven(receipt, 1))
        self.assertFalse(placement_effects_proven(receipt, 2))

    def test_malformed_placement_counts_are_rejected(self):
        for field, value in (
            ("effect_count", True),
            ("state_carrier_count", -1),
            ("effect_count", 0),
            ("state_carrier_count", 3),
        ):
            with self.subTest(field=field, value=value):
                receipt = self.placement(effect_count=2, carrier_count=2)
                receipt[field] = value
                self.assertFalse(placement_effects_proven(receipt, 1))


if __name__ == "__main__":
    unittest.main()
