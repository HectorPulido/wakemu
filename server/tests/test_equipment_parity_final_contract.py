"""Native parity-conditioned equipment final-modifier source qualification."""
from collections import ChainMap
from copy import deepcopy
from types import SimpleNamespace
import unittest
from collections.abc import Mapping

from wakfu_server import equipment_stats
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_equipment_parity_final_contract import (
    parity_final_state_contract,
)
from wakfu_server.combat_owned_equipment import compiled_with_sources
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.wire import proto_field


def _character(reference, uid):
    return {
        "id": 7,
        "breed": 8,
        "level": 245,
        "active_build_index": 0,
        "inventory_items": [
            {"uid": uid, "reference": reference, "character_id": 7, "quantity": 1}
        ],
        "builds": {
            0: {
                "sheet": proto_field(24, 245).hex(),
                "equipment": proto_field(
                    10, proto_field(8, uid) + proto_field(16, 17)
                ).hex(),
            }
        },
    }


class EquipmentParityFinalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = tuple(
            plan(_character(reference, 500 + index), ordinary_only=True)[0]
            for index, reference in enumerate((29420, 29445))
        )
        cls.compiled = compiled_with_sources(compiled_runtime_catalog(), cls.sources)
        cls.registry = characteristic_registry()

    def test_both_native_sources_qualify_complete_parity_graph(self):
        for source in self.sources:
            with self.subTest(reference=source["reference"]):
                self.assertEqual(source["unplanned_passive_effect_ids"], ())
                self.assertIsNone(
                    parity_final_state_contract(source, self.compiled, self.registry)
                )

    def test_changed_root_parameters_fail_closed(self):
        source = self.sources[0]
        root_id = str(source["roots"][0])

        def thaw(value):
            if isinstance(value, Mapping):
                return {key: thaw(child) for key, child in value.items()}
            if isinstance(value, (tuple, list)):
                return [thaw(child) for child in value]
            return deepcopy(value)

        changed = thaw(self.compiled.effects[root_id])
        changed["parameters"][1] += 1
        compiled = SimpleNamespace(
            effects=ChainMap({root_id: changed}, self.compiled.effects),
            source_states=self.compiled.source_states,
        )
        self.assertIsNotNone(
            parity_final_state_contract(source, compiled, self.registry)
        )
