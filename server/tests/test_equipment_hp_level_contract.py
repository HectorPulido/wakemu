"""Actual nineteen native HP-derived equipment graphs, without admission guesses."""
from collections import ChainMap
from types import SimpleNamespace
import unittest
from wakfu_server.equipment import RULES
from wakfu_server.wire import proto_field
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_owned_equipment import compiled_with_sources
from wakfu_server.combat_equipment_hp_level_contract import hp_level_state_contract
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry


class EquipmentHpLevelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.references = (
            18098,
            18099,
            18221,
            18222,
            18459,
            18461,
            23209,
            23213,
            23214,
            23217,
            23218,
            23221,
            23228,
            23231,
            23232,
            23977,
            23978,
            27295,
            27296,
        )
        cls.sources = []
        for index, reference in enumerate(cls.references):
            rule = RULES[reference]
            if (
                not isinstance(rule["slots"], (tuple, list))
                or not rule["slots"]
                or any(type(slot) is not int for slot in rule["slots"])
                or type(rule["minimum_level"]) is not int
                or not 0 <= rule["minimum_level"] <= 200
            ):
                raise ValueError("Missing lawful native source fixture rule")
            uid = 100000 + index
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
                            10, proto_field(8, uid) + proto_field(16, rule["slots"][0])
                        ).hex(),
                    )
                },
            )
            sources = plan(character, ordinary_only=True)
            if (
                not isinstance(sources, (tuple, list))
                or len(sources) != 1
                or not isinstance(sources[0], dict)
                or sources[0]["reference"] != reference
                or sources[0]["uid"] != uid
            ):
                raise ValueError("Native plan did not return the exact owned source")
            cls.sources.extend(sources)
        cls.compiled = compiled_with_sources(compiled_runtime_catalog(), cls.sources)
        cls.registry = characteristic_registry()

    def source(self, reference=18099):
        return next(row for row in self.sources if row["reference"] == reference)

    def changed(self, reference, **changes):
        return SimpleNamespace(
            effects=ChainMap(
                {
                    str(reference): dict(
                        self.compiled.effects[str(reference)], **changes
                    )
                },
                self.compiled.effects,
            ),
            source_states=self.compiled.source_states,
        )

    def test_all_nineteen_actual_sources_cover_both_scalar_topologies(self):
        self.assertEqual(len(self.sources), 19)
        for source in self.sources:
            with self.subTest(reference=source["reference"]):
                self.assertIsNone(
                    hp_level_state_contract(source, self.compiled, self.registry)
                )

    def test_other_hp_modes_growth_actor_selector_or_extra_rounding_remain_deferred(
        self,
    ):
        original = self.compiled.effects["108957"]["parameters"]
        for index, value in ((20, 2), (19, 0.02), (14, 1), (12, 92)):
            raw = list(original)
            raw[index] = value
            self.assertIsNotNone(
                hp_level_state_contract(
                    self.source(), self.changed(108957, parameters=raw), self.registry
                )
            )
        self.assertIsNotNone(
            hp_level_state_contract(
                self.source(),
                self.changed(108957, parameters=[*original, 2, 0], parameter_count=12),
                self.registry,
            )
        )

    def test_ordered_decurse_and_reapplication_must_target_same_derived_state(self):
        for reference, changes in (
            (108957, dict(children=[108958, 108961])),
            (108961, dict(parameters=[2511, 0])),
            (108958, dict(parameters=[2504, 0, 1, 0, -1, 0])),
            (187549, dict(parameters=[2511, 0, 0, 1, -1, 0])),
        ):
            self.assertIsNotNone(
                hp_level_state_contract(
                    self.source(), self.changed(reference, **changes), self.registry
                )
            )

    def test_marker_level_intervals_subscription_clock_and_hmi_are_authoritative(self):
        for reference, changes in (
            (108983, dict(minimum_level=11)),
            (108984, dict(maximum_level=99)),
            (
                108957,
                dict(target_masks=[None, None, None, [1], None, [1001, 1002], None]),
            ),
            (187547, dict(target_masks=[None, None, None, None, None, [1002], None])),
            (
                108940,
                dict(
                    native_timing_definition=dict(
                        self.compiled.effects["108940"]["native_timing_definition"],
                        esr=False,
                    )
                ),
            ),
            (108946, dict(native_hmi_actions={"rzc": []})),
        ):
            self.assertIsNotNone(
                hp_level_state_contract(
                    self.source(), self.changed(reference, **changes), self.registry
                )
            )

    def test_secondary_state_policies_and_unknown_scalar_runner_reject(self):
        original = self.compiled.source_states
        definition = dict(original["states"]["2504"], additive=True)
        altered = SimpleNamespace(
            effects=self.compiled.effects,
            source_states=dict(
                original, states=ChainMap({"2504": definition}, original["states"])
            ),
        )
        self.assertIsNotNone(
            hp_level_state_contract(self.source(), altered, self.registry)
        )
        registry = dict(
            self.registry,
            effects=ChainMap(
                {"80": dict(self.registry["effects"]["80"], runner="eWR")},
                self.registry["effects"],
            ),
        )
        self.assertIsNotNone(
            hp_level_state_contract(self.source(), self.compiled, registry)
        )
