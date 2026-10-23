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
            roots=tuple(
                root["reference"]
                for root in plan["roots"]
                if root["effect_class"] == 304
                and root["variant"] == 0
                and root["metadata"]["native_active_effect"] is False
            ),
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

    def test_original_flag17_costume_sources_use_the_existing_null_motor(self):
        for reference in (
            12176,
            12177,
            12179,
            12180,
            12202,
            12287,
            12646,
            12647,
            13236,
            13238,
            13239,
            13240,
            13241,
            13242,
            13243,
            13244,
            13245,
            13246,
            13247,
            13248,
            13249,
            13250,
            13251,
            13252,
            13253,
            13254,
            13715,
            13720,
            13721,
            18100,
            18101,
            18102,
            18604,
            19393,
            19571,
            19573,
        ):
            with self.subTest(reference=reference):
                self.assertIsNone(
                    permanent_null_carrier_contract(*self.fixture(reference))
                )

    def test_remaining_original_permanent_cosmetic_forms_keep_their_metadata(self):
        for reference in (
            12277,
            15057,
            15060,
            15061,
            15067,
            15105,
            15140,
            17436,
            17437,
            17438,
            18036,
            18047,
            20693,
            22129,
            17870,
            30485,
        ):
            with self.subTest(reference=reference):
                source, compiled, registry = self.fixture(reference)
                before = json.dumps(source, sort_keys=True)
                self.assertIsNone(
                    permanent_null_carrier_contract(source, compiled, registry)
                )
                self.assertEqual(json.dumps(source, sort_keys=True), before)

    def test_permanent_variants_reject_unproved_clocks_phases_and_level_children(self):
        from collections import ChainMap

        for label in (
            "positive-state",
            "growing-state",
            "malformed-skip",
            "positive-realtime",
            "growing-realtime",
            "crossed-mode",
            "double-hmi",
            "missing-remove-hmi",
            "new-criterion",
            "root-circle",
            "higher-level-unknown-child",
        ):
            with self.subTest(label=label):
                reference = 15140 if label == "higher-level-unknown-child" else 15067
                if label in ("double-hmi", "missing-remove-hmi"):
                    reference = 12277
                source, compiled, registry = self.fixture(reference)
                root_id = str(source["roots"][0])
                root = json.loads(json.dumps(compiled.effects[root_id]))
                state_id = str(int(root["parameters"][0]))
                state = json.loads(
                    json.dumps(compiled.source_states["states"][state_id])
                )
                child_id = str(state["effect_ids"][0])
                child = json.loads(json.dumps(compiled.effects[child_id]))
                effects = {root_id: root, child_id: child}
                if label == "positive-state":
                    state["duration_base"] = 1
                elif label == "growing-state":
                    state["duration_per_level"] = 1
                elif label == "malformed-skip":
                    state["skip_turn_timer"] = 1
                elif label == "positive-realtime":
                    child["native_timing_definition"]["rzv"] = 1
                elif label == "growing-realtime":
                    child["native_timing_definition"]["rzw"] = 1
                elif label == "crossed-mode":
                    child["native_execution_mode"] = 2
                elif label == "double-hmi":
                    child["native_hmi_actions"]["rze"] = deepcopy(
                        child["native_hmi_actions"]["rzc"]
                    )
                elif label == "missing-remove-hmi":
                    child["native_hmi_actions"]["rzf"] = []
                elif label == "new-criterion":
                    child["criteria"] = "IsProtectorInFight()"
                elif label == "root-circle":
                    root["area_native"], root["area_class"] = "circle-1", "anu"
                else:
                    # The source applies level1, but the whole native level
                    # domain must still be qualified instead of ignoring5.
                    child["minimum_level"] = 5
                    child["effect_class"] = 120
                changed = SimpleNamespace(
                    effects=ChainMap(effects, compiled.effects),
                    source_states={
                        **compiled.source_states,
                        "states": ChainMap(
                            {state_id: state}, compiled.source_states["states"]
                        ),
                        "effects": ChainMap(effects, compiled.source_states["effects"]),
                    },
                )
                self.assertIsNotNone(
                    permanent_null_carrier_contract(source, changed, registry)
                )

    def test_execution_pin_normalizes_only_optional_timing_observations(self):
        from collections import ChainMap
        from wakfu_server.combat_owned_equipment_pin import execution_contract_sha256

        source, compiled, registry = self.fixture(18047)
        before = execution_contract_sha256((source,), compiled, registry)
        child_id = "108647"
        original = json.loads(json.dumps(compiled.effects[child_id]))
        child = deepcopy(original)
        child.pop("native_timing_checks", None)
        without_observations = SimpleNamespace(
            effects=ChainMap({child_id: child}, compiled.effects),
            source_states=compiled.source_states,
        )
        self.assertEqual(
            execution_contract_sha256((source,), without_observations, registry), before
        )
        self.assertEqual(json.loads(json.dumps(compiled.effects[child_id])), original)
        for label in ("clock", "flags", "criterion", "unknown-metadata"):
            with self.subTest(label=label):
                mutated = deepcopy(child)
                if label == "clock":
                    mutated["native_timing_definition"]["ryE"] = 1
                elif label == "flags":
                    mutated["native_effect_flags"] = [17]
                elif label == "criterion":
                    mutated["criteria"] = "False"
                else:
                    mutated["unreviewed_metadata"] = 1
                changed = SimpleNamespace(
                    effects=ChainMap({child_id: mutated}, compiled.effects),
                    source_states=compiled.source_states,
                )
                self.assertNotEqual(
                    execution_contract_sha256((source,), changed, registry), before
                )

    def test_legacy_and_canonical_pins_keep_semantic_and_integrity_guards(self):
        from collections import ChainMap
        from wakfu_server.combat_owned_equipment_pin import (
            _digest,
            _legacy_execution_contract_sha256,
            _plain,
            execution_contract_sha256,
            pinned_sources,
        )

        source, compiled, registry = self.fixture(18047)
        snapshots = (
            execution_contract_sha256((source,), compiled, registry),
            _legacy_execution_contract_sha256((source,), compiled, registry),
        )
        self.assertNotEqual(*snapshots)
        for expected in snapshots:
            payload = dict(
                version=1,
                actor_id=1,
                owner_id=1,
                sources=_plain((source,)),
                deferred=[],
                execution_sha256=expected,
            )
            record = dict(payload, sha256=_digest(payload))
            fight = SimpleNamespace(native_owned_equipment_sources={"1": record})
            self.assertEqual(len(pinned_sources(fight, compiled, registry)), 1)
            for label in ("clock", "flags", "criterion", "hmi"):
                with self.subTest(legacy=expected == snapshots[1], mutation=label):
                    child = json.loads(json.dumps(compiled.effects["108647"]))
                    if label == "clock":
                        child["native_timing_definition"]["ryE"] = 1
                    elif label == "flags":
                        child["native_effect_flags"] = [17]
                    elif label == "criterion":
                        child["criteria"] = "False"
                    else:
                        child["native_hmi_actions"]["rzf"] = []
                    changed = SimpleNamespace(
                        effects=ChainMap({"108647": child}, compiled.effects),
                        source_states=compiled.source_states,
                    )
                    with self.assertRaisesRegex(
                        ValueError, "execution contract mismatch"
                    ):
                        pinned_sources(fight, changed, registry)
            damaged = dict(record, owner_id=2)
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                pinned_sources(
                    SimpleNamespace(native_owned_equipment_sources={"1": damaged}),
                    compiled,
                    registry,
                )

    def test_cosmetic_flag17_does_not_admit_unknown_flags_or_unproved_hmi_metadata(
        self,
    ):
        source, compiled, registry = self.fixture(12176)
        root = str(source["roots"][0])
        state_id = int(compiled.effects[root]["parameters"][0])
        child_id = str(compiled.source_states["states"][str(state_id)]["effect_ids"][0])
        for label in (
            "combined-flags",
            "unknown-flag",
            "light",
            "scale",
            "hide",
            "subscription",
            "positive-clock",
        ):
            with self.subTest(label=label):
                child = json.loads(json.dumps(compiled.effects[child_id]))
                if label == "combined-flags":
                    child["native_effect_flags"] = [15, 17]
                elif label == "unknown-flag":
                    child["native_effect_flags"] = [17, 99]
                elif label in ("light", "scale", "hide"):
                    kind = {
                        "light": "LIGHT_SOURCE",
                        "scale": "SCALE_MODIFICATION",
                        "hide": "HIDE_ALL_EQUIPMENTS",
                    }[label]
                    for phase in ("rze", "rzf", "rzh"):
                        child["native_hmi_actions"][phase][0]["type"] = kind
                        if label != "light":
                            # Audited scale/hide are presentation-only with
                            # these flags false, not arbitrary target-only HMI.
                            child["native_hmi_actions"][phase][0]["aYc"] = True
                elif label == "subscription":
                    child["target_masks"][5] = [1005]
                else:
                    child["native_timing_definition"]["ryE"] = 1
                from collections import ChainMap

                changed = SimpleNamespace(
                    effects=ChainMap({child_id: child}, compiled.effects),
                    source_states=compiled.source_states,
                )
                self.assertIsNotNone(
                    permanent_null_carrier_contract(source, changed, registry)
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
