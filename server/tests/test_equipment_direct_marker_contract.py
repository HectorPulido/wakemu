"""Direct ordinary null markers retain their original definitions and HMI."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.combat_copied_equipment_execution import equipment_effect_definitions
from wakfu_server.combat_equipment_direct_marker_contract import (
    direct_marker_effect,
    direct_marker_root,
    direct_marker_contract,
    direct_owned_effect,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.world_clock import daytime


class EquipmentDirectMarkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native = native_copied_equipment_catalog()
        cls.roots = []
        references = (
            8089,
            9605,
            9606,
            9607,
            9608,
            9704,
            9706,
            10378,
            11119,
            11120,
            11121,
            11363,
            11808,
            11809,
            11810,
            12107,
            12108,
            12109,
            20527,
            20715,
            30000,
            30926,
            33000,
        )
        for reference in references:
            plan = copied_equipment_plan(reference, native)
            for root in plan["roots"]:
                if direct_marker_root(root):
                    cls.roots.append((reference, plan, root))

    def test_twenty_three_complete_items_preserve_twenty_seven_root_shapes(self):
        self.assertEqual(23, len({row[0] for row in self.roots}))
        self.assertEqual(27, len(self.roots))
        kinds = {
            "zero": 0,
            "LIGHT_SOURCE": 0,
            "PARTICLE_SYSTEM": 0,
            "world_property": 0,
        }
        for reference, plan, root in self.roots:
            before = deepcopy(root)
            effects = equipment_effect_definitions({"roots": [root]})
            effect = effects[str(root["reference"])]
            source = dict(
                attachment_field=None,
                roots=(root["reference"],),
                native_retained_container=plan["native_retained_container"],
            )
            self.assertIsNone(
                direct_marker_contract(
                    source,
                    SimpleNamespace(effects=effects),
                    {"effects": {"400": {"runner": "eXE"}}},
                )
            )
            actions = [
                a for rows in effect["native_hmi_actions"].values() for a in rows
            ]
            kind = (
                "world_property"
                if effect["effect_class"] == 449
                else actions[0]["type"]
                if actions
                else "zero"
            )
            kinds[kind] += 1
            self.assertEqual(before, root)
            self.assertTrue(direct_owned_effect(effect))
        self.assertEqual(
            {"zero": 15, "LIGHT_SOURCE": 7, "PARTICLE_SYSTEM": 3, "world_property": 2},
            kinds,
        )

    def test_unknown_metadata_criteria_and_unbalanced_visual_lifecycle_reject(self):
        for _, _, root in self.roots:
            effect = equipment_effect_definitions({"roots": [root]})[
                str(root["reference"])
            ]
            for key, value in (
                ("native_active_effect", True),
                ("native_effect_flags", [17]),
                ("criteria", 'GetCharac("HP") > 0'),
                ("variant", 1),
                ("children", [999]),
                ("probability_base", 50),
            ):
                changed = dict(effect, **{key: value})
                self.assertFalse(direct_owned_effect(changed), key)
            if any(effect["native_hmi_actions"].values()):
                changed = deepcopy(effect)
                changed["native_hmi_actions"]["rzf"] = []
                self.assertFalse(direct_marker_effect(changed))
            else:
                self.assertFalse(direct_owned_effect(dict(effect, parameters=[1, 0])))

    def test_native_day_boundaries_and_missing_time_authority(self):
        for seconds, expected in (
            (1799, False),
            (1800, True),
            (5399, True),
            (5400, False),
            (8999, False),
            (9000, True),
        ):
            context = ConditionContext(
                actors={}, daytime_query=lambda: daytime(seconds * 1000)
            )
            self.assertEqual(expected, evaluate_condition("IsDay()", context))
            self.assertEqual(not expected, evaluate_condition("not IsDay()", context))
        for query in (None, lambda: 1):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "IsDay()", ConditionContext(actors={}, daytime_query=query)
                )

    def test_mixed_sources_are_complete_and_pin_world_property_authority(self):
        from wakfu_server.combat_equipment_passive_completeness import (
            unplanned_passive_effect_ids,
        )
        from wakfu_server.combat_owned_equipment import (
            compiled_with_sources,
            ordinary_turn_state_contract,
        )
        from wakfu_server.combat_owned_equipment_pin import execution_contract_sha256
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.equipment_stats import CATALOG
        from wakfu_server.combat_world_properties import registry as world_registry

        for reference in (30000, 33000):
            plan = next(plan for item, plan, _ in self.roots if item == reference)
            roots = [root for root in plan["roots"] if direct_marker_root(root)]
            source = dict(
                attachment_field=None,
                roots=tuple(root["reference"] for root in roots),
                effects=equipment_effect_definitions({"roots": roots}),
                native_retained_container=plan["native_retained_container"],
            )
            source["unplanned_passive_effect_ids"] = unplanned_passive_effect_ids(
                reference, plan, source["roots"], templates=CATALOG
            )
            self.assertEqual(3, len(roots))
            self.assertEqual((), source["unplanned_passive_effect_ids"])
            compiled = compiled_with_sources(compiled_runtime_catalog(), (source,))
            registry = characteristic_registry()
            self.assertIsNone(ordinary_turn_state_contract(source, compiled, registry))
            digest = execution_contract_sha256((source,), compiled, registry)
            changed = deepcopy(world_registry())
            changed["5"]["fixture_semantic_version"] = 2
            with patch(
                "wakfu_server.combat_world_properties.registry", return_value=changed
            ):
                self.assertNotEqual(
                    digest, execution_contract_sha256((source,), compiled, registry)
                )
            self.assertEqual(
                digest, execution_contract_sha256((source,), compiled, registry)
            )

    def test_authoritative_400_and_449_unapplication_preserve_proto_and_force_notification(
        self,
    ):
        from wakfu_server.combat_effects import _integer, _varint
        from wakfu_server.combat_effect_removal import (
            running_effect_removal,
            state_unapplication_payload,
            _identity_fields,
        )

        identity = b"".join(
            _integer(k, v)
            for k, v in ((1, 1234), (2, 1230), (3, 36528), (4, 0), (6, 22), (7, 22))
        )
        timing = _integer(2, -1) + _integer(3, 17) + _integer(5, 1)
        original = identity + b"\x5a" + _varint(len(timing)) + timing
        for family in (400, 449):
            body = running_effect_removal(
                7,
                9,
                effect_class=family,
                target_id=22,
                uid=1234,
                running_effect_payload=original,
            )
            self.assertEqual(state_unapplication_payload(original), body[18:-16])
            self.assertEqual(_identity_fields(original), _identity_fields(body[18:-16]))
            self.assertIn(timing, body[18:-16])
            quiet = running_effect_removal(
                7,
                9,
                effect_class=family,
                target_id=22,
                uid=1234,
                running_effect_payload=original,
                notify_unapplication=False,
            )
            self.assertEqual(original, quiet[18:-16])
