"""Source-bound structural gates; source presence never grants gameplay credit."""
from copy import deepcopy
import unittest
import json
from types import SimpleNamespace
from wakfu_server.combat_equipment_null_carrier_contract import (
    permanent_null_carrier_contract,
)
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.combat_copied_equipment_execution import equipment_effect_definitions
from wakfu_server.combat_owned_equipment import compiled_with_sources
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry, CompiledEffects


class EquipmentNullCarrierContractTests(unittest.TestCase):
    @staticmethod
    def fixture(reference=14191):
        plan = copied_equipment_plan(reference, native_copied_equipment_catalog())
        source = dict(
            uid=1000,
            reference=reference,
            source_reference=reference,
            attachment_field=None,
            roots=tuple(root["reference"] for root in plan["roots"]),
            effects=equipment_effect_definitions(plan),
            native_retained_container=dict(plan["native_retained_container"]),
        )
        compiled = compiled_with_sources(compiled_runtime_catalog(), (source,))
        return source, compiled, characteristic_registry()

    def test_original_complete_sex_and_plain_costume_contracts_use_the_same_gate(self):
        for reference in (14191, 13716, 10424, 17713):
            with self.subTest(reference=reference):
                self.assertIsNone(
                    permanent_null_carrier_contract(*self.fixture(reference))
                )

    def test_missing_hmi_unmodeled_predicates_and_nonnull_children_stay_deferred(self):
        source, compiled, registry = self.fixture()
        for change in (
            "missing_hmi",
            "unknown_hmi",
            "protector",
            "scalar",
            "events",
            "timed",
            "foreign_selector",
            "area_selector_empty",
            "area_selector_circle",
        ):
            with self.subTest(change=change):
                effects = {
                    key: json.loads(json.dumps(compiled.effects[key]))
                    for key in (str(source["roots"][0]), "254678", "254679")
                }
                states = {
                    "states": {
                        "5384": json.loads(
                            json.dumps(compiled.source_states["states"]["5384"])
                        )
                    },
                    "effects": effects,
                }
                child = effects["254678"]
                if change == "missing_hmi":
                    child.pop("native_hmi_actions")
                elif change == "unknown_hmi":
                    for phase in ("rze", "rzf", "rzh"):
                        child["native_hmi_actions"][phase][0][
                            "type"
                        ] = "PARTICLE_SYSTEM"
                elif change == "protector":
                    child["criteria"] = 'IsSex("male") and IsProtectorInFight()'
                elif change == "scalar":
                    child["effect_class"] = 120
                elif change == "events":
                    child["target_masks"][5] = [1001]
                elif change == "timed":
                    states["states"]["5384"]["duration_base"] = 1
                elif change == "foreign_selector":
                    child["native_target_selector"]["mask"] = 8
                elif change == "area_selector_empty":
                    child["native_target_selector"]["mask"] = 1
                    child["area_native"], child["area_class"] = "empty", "anA"
                elif change == "area_selector_circle":
                    child["native_target_selector"]["mask"] = 1
                    child["area_native"], child["area_class"] = "circle-1", "anu"
                modified = SimpleNamespace(effects=effects, source_states=states)
                self.assertIsNotNone(
                    permanent_null_carrier_contract(source, modified, registry)
                )

    def test_attached_active_and_group_roots_are_not_a_null_carrier_shortcut(self):
        source, compiled, registry = self.fixture()
        attached = dict(source, attachment_field=24)
        self.assertIsNotNone(
            permanent_null_carrier_contract(attached, compiled, registry)
        )
        for field, value in (
            ("native_active_effect", True),
            ("variant", 1),
            ("effect_class", 999),
            ("children", [254678]),
        ):
            with self.subTest(field=field):
                changed = deepcopy(source)
                root = str(source["roots"][0])
                changed["effects"][root][field] = value
                effects = {
                    key: json.loads(json.dumps(compiled.effects[key]))
                    for key in (root, "254678", "254679")
                }
                effects[root] = changed["effects"][root]
                modified = SimpleNamespace(
                    effects=effects, source_states=compiled.source_states
                )
                self.assertIsNotNone(
                    permanent_null_carrier_contract(changed, modified, registry)
                )
