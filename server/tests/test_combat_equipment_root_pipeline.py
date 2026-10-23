"""General passive-root selection, snapshot ownership and pinning regressions."""
import importlib
import unittest

from wakfu_server.equipment_stats import CATALOG
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_equipment_root_roles import root_role
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.wire import proto_field


def native_cases():
    """Three real regressions; runtime classification has no reference list."""
    expected = (
        (18097, [109090], [112405]),
        (18604, [114942], [116422, 116421, 116420, 116423]),
        (30530, [340230], [340241]),
    )
    for reference, planned, omitted in expected:
        parent = copied_equipment_plan(reference, native_copied_equipment_catalog())
        identities = {row["id"]: row for row in CATALOG[reference]["effects"]}
        yield dict(
            reference=reference,
            planned=planned,
            omitted=omitted,
            roots=[
                dict(
                    reference=root["reference"],
                    effect_class=root["effect_class"],
                    native=root,
                    summary=identities[root["reference"]],
                )
                for root in parent["roots"]
            ],
        )


class RootPipelineTests(unittest.TestCase):
    def test_all_three_native_sources_keep_operator_siblings_and_static_ownership(self):
        cases = native_cases()
        for case in cases:
            reference = case["reference"]
            actor = dict(
                id=1,
                level=245,
                active_build_index=0,
                builds={0: dict(sheet=proto_field(24, 245).hex(), equipment="")},
                inventory_items=[dict(uid=100, reference=reference, quantity=1)],
            )
            sources = plan(
                actor, ordinary_only=True, _selected_entries=[dict(uid=100, slot=3)]
            )
            self.assertEqual(len(sources), 1)
            self.assertEqual(
                sources[0]["roots"], tuple(case["planned"] + case["omitted"])
            )
            self.assertEqual(sources[0]["unplanned_passive_effect_ids"], ())
            identities = {row["id"]: row for row in CATALOG[reference]["effects"]}
            parent = copied_equipment_plan(reference, native_copied_equipment_catalog())
            selected = set(sources[0]["roots"])
            for root in parent["roots"]:
                role = root_role(reference, root, identities[root["reference"]])
                self.assertEqual(
                    root["reference"] in selected, role == "runtime-operator"
                )
            self.assertEqual(sources[0]["native_retained_container"]["id"], reference)

    def test_snapshot_roles_bind_only_exact_planned_native_operator_identity(self):
        from unittest.mock import patch

        module = importlib.import_module("wakfu_server.combat_equipment_snapshot_roles")
        for case in native_cases():
            reference = case["reference"]
            actor = dict(
                id=1,
                level=245,
                active_build_index=0,
                builds={0: dict(sheet=proto_field(24, 245).hex(), equipment="")},
                inventory_items=[dict(uid=100, reference=reference, quantity=1)],
            )
            sources = plan(
                actor, ordinary_only=True, _selected_entries=[dict(uid=100, slot=3)]
            )
            omitted = set(case["omitted"])
            rows = [
                dict(
                    uid=100,
                    reference=reference,
                    effect_id=root["reference"],
                    generic=root["effect_class"],
                    reason="unsupported-native-effect",
                )
                for root in case["roots"]
                if root["reference"] in omitted
            ]
            rows.append(
                dict(
                    uid=999,
                    reference=reference,
                    effect_id=next(iter(omitted)),
                    generic=999,
                    reason="unsupported-native-effect",
                )
            )
            with patch.object(module, "plan", return_value=sources):
                roles = module.snapshot_roles(actor, rows)
            self.assertEqual({key[2] for key in roles}, omitted)
            self.assertTrue(all(key[0] == 100 for key in roles))

    def test_generic_admission_pins_direct_roots_and_legacy_unqualified_roots_still_reject(
        self,
    ):
        from copy import deepcopy
        from types import SimpleNamespace
        from wakfu_server.combat_owned_equipment_pin import (
            execution_contract_sha256,
            _execution_contract_payload,
        )

        for case in native_cases():
            if any(
                root["native"]["children"]
                for root in case["roots"]
                if root["reference"] in case["omitted"]
            ):
                continue  # This narrow proof isolates non-state root pinning.
            reference = case["reference"]
            actor = dict(
                id=1,
                level=245,
                active_build_index=0,
                builds={0: dict(sheet=proto_field(24, 245).hex(), equipment="")},
                inventory_items=[dict(uid=100, reference=reference, quantity=1)],
            )
            source = deepcopy(
                plan(
                    actor, ordinary_only=True, _selected_entries=[dict(uid=100, slot=3)]
                )[0]
            )
            source["roots"] = tuple(case["omitted"])
            compiled = SimpleNamespace(
                effects=source["effects"], source_states=dict(states={})
            )
            registry = dict(effects={})
            with self.assertRaisesRegex(
                ValueError, "Unqualified equipment state contract"
            ):
                execution_contract_sha256((source,), compiled, registry)
            source["_generic_operation_admission"] = True
            payload = _execution_contract_payload((source,), compiled, registry)
            self.assertEqual(
                set(payload["effects"]), {str(ref) for ref in case["omitted"]}
            )
            before = execution_contract_sha256((source,), compiled, registry)
            mutated = deepcopy(source)
            mutated["effects"][str(case["omitted"][0])]["criteria"] = "False"
            changed = SimpleNamespace(
                effects=mutated["effects"], source_states=dict(states={})
            )
            self.assertNotEqual(
                before, execution_contract_sha256((mutated,), changed, registry)
            )
            source["_generic_operation_admission"] = 1
            with self.assertRaisesRegex(
                ValueError, "Unqualified equipment state contract"
            ):
                execution_contract_sha256((source,), compiled, registry)

    def test_shared_classifier_excludes_snapshot_flats_and_profession_mutations(self):
        from wakfu_server.profession_equipment_modifiers import definitions
        from wakfu_server.equipment_stats import _flat

        catalog = native_copied_equipment_catalog()
        profession_checked = False
        for ref in definitions():
            reference = int(ref)
            if reference not in CATALOG:
                continue
            parent = copied_equipment_plan(reference, catalog)
            identities = {row["id"]: row for row in CATALOG[reference]["effects"]}
            for root in parent["roots"]:
                if (
                    root_role(reference, root, identities[root["reference"]])
                    == "snapshot-profession"
                ):
                    profession_checked = True
                    break
            if profession_checked:
                break
        self.assertTrue(profession_checked)
        flat_checked = False
        for case in native_cases():
            for root in case["roots"]:
                if _flat(root["summary"]) is not None:
                    self.assertEqual(
                        root_role(case["reference"], root["native"], root["summary"]),
                        "snapshot-characteristic",
                    )
                    flat_checked = True
        self.assertTrue(flat_checked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
