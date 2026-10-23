"""Actual native parity definitions, complete passive roots and recovery guards."""
from collections import ChainMap
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server import equipment_stats
from wakfu_server.wire import proto_field
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_equipment_passive_completeness import (
    unplanned_passive_effect_ids,
)
from wakfu_server.equipment_stats import inactive_passive_root
from wakfu_server.combat_equipment_turn_scalar_contract import (
    turn_scalar_state_contract,
)
from wakfu_server.combat_owned_equipment import (
    compiled_with_sources,
    ordinary_turn_state_contract,
)
from wakfu_server.combat_owned_equipment_pin import (
    execution_contract_sha256,
    pinned_sources,
    _plain,
    _digest,
)
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import (
    characteristic_registry,
    ImmutableCatalog,
)


def character(reference=15001, *, uid=500, slot=12):
    return dict(
        id=7,
        breed=1,
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


class EquipmentParityBootContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = tuple(
            plan(character(reference, uid=500 + index), ordinary_only=True)[0]
            for index, reference in enumerate((15001, 15002, 15003, 15004))
        )
        cls.compiled = compiled_with_sources(compiled_runtime_catalog(), cls.sources)
        cls.registry = characteristic_registry()

    def changed(self, reference, effect):
        return SimpleNamespace(
            effects=ChainMap({str(reference): effect}, self.compiled.effects),
            source_states=self.compiled.source_states,
        )

    def test_all_four_actual_boot_sources_match_without_identity_allowlist(self):
        for source in self.sources:
            with self.subTest(reference=source["reference"]):
                self.assertEqual(source["unplanned_passive_effect_ids"], ())
                self.assertIsNone(
                    turn_scalar_state_contract(source, self.compiled, self.registry)
                )
                self.assertIsNone(
                    ordinary_turn_state_contract(source, self.compiled, self.registry)
                )

    def test_complete_literal_false_roots_are_exactly_accounted_for_as_noops(self):
        native = native_copied_equipment_catalog()
        accounted = 0
        references = set()
        for raw_reference in native["definitions"]:
            reference = int(raw_reference)
            parent = copied_equipment_plan(reference, native)
            roots = [
                root for root in parent["roots"] if root.get("criterion_raw") == "False"
            ]
            if not roots:
                continue
            references.add(reference)
            accounted += len(roots)
            template = equipment_stats.CATALOG[reference]
            identities = {row["id"]: row for row in template["effects"]}
            for root in roots:
                self.assertTrue(
                    equipment_stats.inactive_passive_root(
                        reference, identities[root["reference"]]
                    )
                )
            omitted = unplanned_passive_effect_ids(
                reference, parent, (), templates=equipment_stats.CATALOG
            )
            self.assertFalse({root["reference"] for root in roots} & set(omitted))
        self.assertEqual(accounted, 387)
        self.assertEqual(len(references), 311)

    def test_level_conditional_null_markers_remain_unqualified(self):
        native = native_copied_equipment_catalog()
        for reference, effect_id in ((8089, 32422),):
            with self.subTest(item_reference=reference, effect_id=effect_id):
                parent = copied_equipment_plan(reference, native)
                root = next(
                    row for row in parent["roots"] if row["reference"] == effect_id
                )
                identity = next(
                    row
                    for row in equipment_stats.CATALOG[reference]["effects"]
                    if row["id"] == effect_id
                )
                self.assertNotEqual(root["criterion_raw"], "False")
                self.assertFalse(
                    equipment_stats.inactive_passive_root(reference, identity)
                )
                self.assertFalse(equipment_stats.passive_null_marker(identity))
                omitted = unplanned_passive_effect_ids(
                    reference, parent, (), templates=equipment_stats.CATALOG
                )
                self.assertIn(effect_id, omitted)

    def test_foreign_events_target_predicate_and_clock_variants_stay_deferred(self):
        original = self.compiled.effects["80573"]
        changes = []
        row = dict(original, target_masks=(None, None, None, (2,), None, None, None))
        changes.append(row)
        row = dict(
            original,
            native_target_selector=dict(original["native_target_selector"], mask=2),
        )
        changes.append(row)
        changes.append(dict(original, criteria=original["criteria"] + " or True"))
        changes.append(
            dict(
                original,
                native_timing_definition=dict(
                    original["native_timing_definition"], ryE=2
                ),
            )
        )
        changes.append(
            dict(
                original,
                native_timing_definition=dict(
                    original["native_timing_definition"], clock_on_caster=True
                ),
            )
        )
        changes.append(dict(original, parameters=[1, 0, 1, 0]))
        for row in changes:
            with self.subTest(row=row):
                altered = self.changed(80573, row)
                self.assertIsNotNone(
                    turn_scalar_state_contract(self.sources[0], altered, self.registry)
                )
                self.assertIsNotNone(
                    ordinary_turn_state_contract(
                        self.sources[0], altered, self.registry
                    )
                )

    def test_wrong_owner_and_unavailable_inventory_uid_reject_before_planning(self):
        for altered in (dict(character(), inventory_items=[]), character()):
            if altered["inventory_items"]:
                altered["inventory_items"][0]["character_id"] = 8
            before = deepcopy(altered)
            with self.assertRaisesRegex(ValueError, "unavailable or unowned"):
                plan(altered, ordinary_only=True)
            self.assertEqual(altered, before)

    def test_full_passive_guard_retains_non304_groups_and_actual_template_authority(
        self,
    ):
        native = native_copied_equipment_catalog()
        ghaston_parent = copied_equipment_plan(30530, native)
        ghaston_roots = tuple(
            root["reference"]
            for root in ghaston_parent["roots"]
            if root["effect_class"] == 304
        )
        ghaston_omitted = unplanned_passive_effect_ids(
            30530, ghaston_parent, ghaston_roots, templates=equipment_stats.CATALOG
        )
        self.assertIn(340241, ghaston_omitted)
        # This source-only obligation does not grant the item's EQUIP criteria.
        ghaston = dict(
            reference=30530,
            roots=ghaston_roots,
            unplanned_passive_effect_ids=ghaston_omitted,
        )
        self.assertIsNotNone(
            ordinary_turn_state_contract(ghaston, self.compiled, self.registry)
        )
        parent = copied_equipment_plan(15001, native)
        summary = equipment_stats.CATALOG[15001]
        flat = next(
            row for row in summary["effects"] if equipment_stats._flat(row) is not None
        )
        changed = dict(
            summary,
            effects=[
                dict(row, effect_criteria=True) if row["id"] == flat["id"] else row
                for row in summary["effects"]
            ],
        )
        omitted = unplanned_passive_effect_ids(
            15001, parent, self.sources[0]["roots"], templates={15001: changed}
        )
        self.assertIn(flat["id"], omitted)
        for missing in (
            {
                key: value
                for key, value in self.sources[0].items()
                if key != "unplanned_passive_effect_ids"
            },
            dict(self.sources[0], unplanned_passive_effect_ids=None),
        ):
            self.assertIsNotNone(
                ordinary_turn_state_contract(missing, self.compiled, self.registry)
            )

    def test_all_native_literal_false_passive_roots_are_skipped_and_complete(self):
        native = native_copied_equipment_catalog()
        roots_by_reference = {}
        total = 0
        for raw_reference in native["definitions"]:
            reference = int(raw_reference)
            parent = copied_equipment_plan(reference, native)
            false_roots = [
                root for root in parent["roots"] if root.get("criterion_raw") == "False"
            ]
            if not false_roots:
                continue
            roots_by_reference[reference] = false_roots
            total += len(false_roots)

        self.assertEqual(total, 387)
        self.assertEqual(len(roots_by_reference), 311)
        for reference, roots in roots_by_reference.items():
            with self.subTest(reference=reference):
                template = equipment_stats.CATALOG[reference]
                identities = {row["id"]: row for row in template["effects"]}
                for root in roots:
                    identity = identities[root["reference"]]
                    self.assertTrue(inactive_passive_root(reference, identity))

                # The combat completeness gate sees these exact physical roots
                # and accepts the qualified no-op explanation without silently
                # claiming any unrelated passive as implemented.
                omitted = unplanned_passive_effect_ids(
                    reference,
                    copied_equipment_plan(reference, native),
                    (),
                    templates=equipment_stats.CATALOG,
                )
                self.assertFalse({root["reference"] for root in roots} & set(omitted))

    def test_false_positive_scalar_root_has_no_raw_projection_bonus(self):
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_stats import bonuses
        from wakfu_server.wire import proto_field

        native = native_copied_equipment_catalog()
        candidate = None
        for raw_reference in native["definitions"]:
            reference = int(raw_reference)
            template = equipment_stats.CATALOG.get(reference)
            slots = RULES.get(reference, {}).get("slots", ())
            if template is None or not slots:
                continue
            parent = copied_equipment_plan(reference, native)
            false_ids = {
                root["reference"]
                for root in parent["roots"]
                if root.get("criterion_raw") == "False"
            }
            effects = {row["id"]: row for row in template["effects"]}
            for effect_id in false_ids:
                effect = effects[effect_id]
                flat = equipment_stats._flat(effect)
                if flat is None or flat[1] <= 0:
                    continue
                # Pick a stat unique to the inactive root so another legitimate
                # effect on the same item cannot mask an accidental application.
                other_stats = set()
                for other in template["effects"]:
                    if other["id"] == effect_id:
                        continue
                    other_flat = equipment_stats._flat(other)
                    if other_flat is not None:
                        other_stats.add(other_flat[0])
                if flat[0] not in other_stats:
                    candidate = reference, slots[0], effect, flat
                    break
            if candidate:
                break
        self.assertIsNotNone(
            candidate, "native catalog should contain an inactive positive scalar"
        )
        reference, slot, effect, (stat, amount) = candidate
        uid = 987654321
        character = dict(
            id=1,
            breed=8,
            level=200,
            active_build_index=0,
            hp=1000,
            max_hp=1000,
            inventory_items=[
                dict(uid=uid, character_id=1, reference=reference, quantity=1)
            ],
            builds={
                0: dict(
                    sheet=proto_field(24, 200).hex(),
                    equipment=proto_field(
                        10, proto_field(8, uid) + proto_field(16, slot)
                    ).hex(),
                    aptitudes="",
                )
            },
        )
        self.assertTrue(inactive_passive_root(reference, effect))
        projected = equipment_stats.bonuses(character)["stats"]
        self.assertNotEqual(amount, 0)
        self.assertEqual(projected.get(stat, 0), 0)

        # The same row stops qualifying if any of the native execution facts
        # change; false-criterion text alone is not authority to skip it.
        for changed in (
            dict(effect, native_variant=1),
            dict(effect, native_active_effect=True),
            dict(effect, has_triggers=True),
            dict(effect, target_mask=1),
        ):
            self.assertFalse(inactive_passive_root(reference, changed))

    def test_recovered_pin_rejects_changed_actual_expiration_clock(self):
        source = self.sources[0]
        sources = (source,)
        fingerprint = execution_contract_sha256(sources, self.compiled, self.registry)
        payload = dict(
            version=1,
            actor_id=7,
            owner_id=3,
            sources=_plain(sources),
            deferred=[],
            execution_sha256=fingerprint,
        )
        record = dict(payload, sha256=_digest(payload))
        fight = SimpleNamespace(
            native_owned_equipment_sources={"7": ImmutableCatalog(record)}
        )
        self.assertEqual(len(pinned_sources(fight, self.compiled, self.registry)), 1)
        child = self.compiled.effects["80573"]
        changed = dict(
            child,
            native_timing_definition=dict(child["native_timing_definition"], ryE=2),
        )
        altered = self.changed(80573, changed)
        self.assertNotEqual(
            execution_contract_sha256(sources, altered, self.registry), fingerprint
        )
        with self.assertRaisesRegex(ValueError, "execution contract mismatch"):
            pinned_sources(fight, altered, self.registry)
        self.assertEqual(len(pinned_sources(fight, self.compiled, self.registry)), 1)
