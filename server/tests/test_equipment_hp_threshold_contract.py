"""Actual source definitions; qualification is distinct from paid gameplay."""
from collections import ChainMap
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_equipment_hp_threshold_contract import (
    hp_threshold_state_contract,
)
from wakfu_server.combat_owned_equipment import compiled_with_sources
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.wire import proto_field
from wakfu_server.equipment import RULES


class EquipmentHpThresholdContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.references = (
            18088,
            18089,
            18094,
            18095,
            18220,
            18460,
            18462,
            23210,
            23219,
            23220,
            23222,
            23224,
            23991,
            23992,
            24062,
            27301,
            27302,
        )
        cls.sources = []
        # Source planning validates each actual native equipment rule, including
        # its own allowed slot, minimum level and unmodified EQUIP criterion.
        for index, reference in enumerate(cls.references):
            uid = 500 + index
            rule = RULES[reference]
            slots = rule["slots"]
            if (
                not isinstance(slots, (tuple, list))
                or not slots
                or any(type(slot) is not int for slot in slots)
                or type(rule["minimum_level"]) is not int
                or not 0 <= rule["minimum_level"] <= 200
            ):
                raise ValueError("Missing lawful native equipment fixture rule")
            slot = slots[0]
            # This structural source fixture has no fight or resource snapshot.
            # Native ownership/level/EQUIP validation remains inside plan().
            character = dict(
                id=7,
                breed=7,
                level=200,
                active_build_index=0,
                inventory_items=[
                    dict(uid=uid, reference=reference, character_id=7, quantity=1)
                ],
                builds={
                    0: dict(
                        sheet=proto_field(24, 200).hex(),
                        equipment=proto_field(
                            10, proto_field(8, uid) + proto_field(16, slot)
                        ).hex(),
                    )
                },
            )
            sources = plan(character, ordinary_only=True)
            if (
                not isinstance(sources, (tuple, list))
                or len(sources) != 1
                or any(not isinstance(row, dict) for row in sources)
                or sources[0]["reference"] != reference
                or sources[0]["uid"] != uid
            ):
                raise ValueError(
                    "Native equipment plan did not return the owned source"
                )
            cls.sources.extend(sources)
        cls.compiled = compiled_with_sources(compiled_runtime_catalog(), cls.sources)
        cls.registry = characteristic_registry()

    def changed(self, reference, **changes):
        row = dict(self.compiled.effects[str(reference)], **changes)
        return SimpleNamespace(
            effects=ChainMap({str(reference): row}, self.compiled.effects),
            source_states=self.compiled.source_states,
        )

    def test_all_seventeen_actual_sources_match_five_source_topologies(self):
        self.assertEqual(len(self.sources), 17)
        for source in self.sources:
            with self.subTest(reference=source["reference"]):
                before = deepcopy(source)
                self.assertIsNone(
                    hp_threshold_state_contract(source, self.compiled, self.registry)
                )
                self.assertEqual(source, before)

    def test_generic_id_is_not_action_family_uid_or_another_leaf(self):
        source = next(row for row in self.sources if row["reference"] == 18089)
        for raw in ([120, 0], [400, 0], [109569, 0], [109059, 0, 1, 0]):
            with self.subTest(raw=raw):
                self.assertIsNotNone(
                    hp_threshold_state_contract(
                        source, self.changed(109060, parameters=raw), self.registry
                    )
                )

    def test_wrong_threshold_noncomplementary_criteria_and_order_reject(self):
        source = next(row for row in self.sources if row["reference"] == 18089)
        for expression in (
            'not HasEffectWithSpecificId("target", 109059) and GetTotalHpInPercent("target") >= 89',
            'not HasEffectWithSpecificId("caster", 109059) and GetTotalHpInPercent("target") >= 90',
            'not HasEffectWithSpecificId("target", 109059) and GetTotalHpInPercent("target") >= 90 or True',
        ):
            self.assertIsNotNone(
                hp_threshold_state_contract(
                    source, self.changed(109082, criteria=expression), self.registry
                )
            )
        self.assertIsNotNone(
            hp_threshold_state_contract(
                source,
                self.changed(
                    109060,
                    criteria='HasEffectWithSpecificId("target", 109059) and GetTotalHpInPercent("target") <= 90',
                ),
                self.registry,
            )
        )
        self.assertIsNotNone(
            hp_threshold_state_contract(
                source,
                self.changed(
                    109058,
                    children=list(
                        reversed(self.compiled.effects["109058"]["children"])
                    ),
                ),
                self.registry,
            )
        )

    def test_foreign_selector_subscription_clock_and_marker_reject(self):
        source = next(row for row in self.sources if row["reference"] == 18089)
        alterations = [
            self.changed(109059, native_target_selector={"mask": 2, "class": "fcE"}),
            self.changed(
                109058, target_masks=[None, None, None, [1, 2], None, [1001], None]
            ),
            self.changed(
                109059,
                native_timing_definition=dict(
                    self.compiled.effects["109059"]["native_timing_definition"], ryE=1
                ),
            ),
            self.changed(109021, parameters=[1, 1]),
            self.changed(109059, effect_class=999999),
            self.changed(109059, native_localization_enabled=True),
            self.changed(109059, area_class="anA"),
            self.changed(233549, native_active_effect=True),
            self.changed(109059, probability_base=True),
            self.changed(109059, native_target_selector={"mask": True, "class": "fcE"}),
            self.changed(109059, native_hmi_actions={"rzc": [{"id": 1}]}),
        ]
        for altered in alterations:
            self.assertIsNotNone(
                hp_threshold_state_contract(source, altered, self.registry)
            )
        self.assertIsNotNone(
            hp_threshold_state_contract(
                dict(source, attachment_field="innate_effect_sources"),
                self.compiled,
                self.registry,
            )
        )

    def test_invalid_source_level_and_state_level_branch_reject(self):
        source = next(row for row in self.sources if row["reference"] == 18089)
        for rank in (True, -1, 32768):
            self.assertIsNotNone(
                hp_threshold_state_contract(
                    dict(
                        source,
                        native_retained_container=dict(
                            source["native_retained_container"], level=rank
                        ),
                    ),
                    self.compiled,
                    self.registry,
                )
            )
        self.assertIsNotNone(
            hp_threshold_state_contract(
                source, self.changed(109058, minimum_level=1), self.registry
            )
        )
