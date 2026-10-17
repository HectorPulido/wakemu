"""Native source ownership, unknown branches and recovered callback contracts."""
from collections import ChainMap
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import equipment_stats
from wakfu_server.wire import proto_field
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_equipment_snapshot_roles import snapshot_roles, _relic_aura
from wakfu_server.combat_owned_equipment import (
    compiled_with_sources,
    ordinary_turn_state_contract,
)
from wakfu_server.combat_owned_equipment_pin import (
    execution_contract_sha256,
    pinned_sources,
    _digest,
    _plain,
)
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import (
    characteristic_registry,
    ImmutableCatalog,
)


class EquipmentSnapshotRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.character = dict(
            id=7,
            breed=1,
            level=200,
            active_build_index=0,
            inventory_items=[
                dict(uid=500, character_id=7, reference=24110, quantity=1)
            ],
            builds={
                0: dict(
                    sheet=proto_field(24, 200).hex(),
                    equipment=proto_field(
                        10, proto_field(8, 500) + proto_field(16, 17)
                    ).hex(),
                )
            },
        )
        cls.sources = plan(cls.character, ordinary_only=True)
        cls.compiled = compiled_with_sources(compiled_runtime_catalog(), cls.sources)
        cls.registry = characteristic_registry()
        cls.native = native_copied_equipment_catalog()
        cls.aura = next(
            root
            for root in copied_equipment_plan(24110, cls.native)["roots"]
            if root["reference"] == 237743
        )

    def test_actual_native_roles_preserve_flat_stats_and_reject_wrong_source_identity(
        self,
    ):
        rows = equipment_stats.bonuses(self.character)["unsupported"]
        before = deepcopy(equipment_stats.bonuses(self.character))
        malformed = [
            dict(
                uid=501,
                reference=24110,
                effect_id=237738,
                generic=304,
                reason="unsupported-native-effect",
            ),
            dict(
                uid=500,
                reference=20720,
                effect_id=187534,
                generic=304,
                reason="unsupported-native-effect",
            ),
            dict(
                uid=500,
                reference=24110,
                effect_id=237738,
                generic=987,
                reason="unsupported-native-effect",
            ),
        ]
        roles = snapshot_roles(self.character, rows + malformed)
        self.assertEqual(roles[(500, 24110, 237738, 304)], "qualified-ready-state")
        self.assertEqual(
            roles[(500, 24110, 237743, 400)],
            "native-relic-aura-no-static-characteristic",
        )
        for row in malformed:
            self.assertNotIn(
                tuple(row[k] for k in ("uid", "reference", "effect_id", "generic")),
                roles,
            )
        self.assertEqual(equipment_stats.bonuses(self.character), before)
        self.assertEqual(before["stats"][1], 180)

    def test_non_aura_null_status_or_children_are_not_blanket_ignored(self):
        self.assertTrue(_relic_aura(self.aura))
        variants = []
        status = deepcopy(self.aura)
        status.update(parameters=[1.0, 0.0], parameter_count=1)
        variants.append(status)
        child = deepcopy(self.aura)
        child["children"] = [187531]
        variants.append(child)
        unqualified = deepcopy(self.aura)
        unqualified["metadata"]["native_effect_flags"] = [17]
        variants.append(unqualified)
        gameplay_hmi = deepcopy(self.aura)
        gameplay_hmi["metadata"]["native_hmi_actions"]["rze"][0][
            "type"
        ] = "STATE_APPLICATION"
        variants.append(gameplay_hmi)
        for root in variants:
            with self.subTest(root=root):
                self.assertFalse(_relic_aura(root))
                native = dict(self.native, definitions=dict(self.native["definitions"]))
                definition = dict(native["definitions"]["24110"])
                definition["ordered_effects"] = [
                    root if e["reference"] == 237743 else e
                    for e in definition["ordered_effects"]
                ]
                native["definitions"]["24110"] = definition
                with patch(
                    "wakfu_server.combat_equipment_snapshot_roles.native_copied_equipment_catalog",
                    return_value=native,
                ):
                    roles = snapshot_roles(
                        self.character,
                        equipment_stats.bonuses(self.character)["unsupported"],
                    )
                self.assertNotIn((500, 24110, 237743, 400), roles)
        self.assertTrue(_relic_aura(self.aura))

    def test_foreign_event_target_and_unknown_family_stay_unqualified(self):
        source = self.sources[0]
        self.assertIsNone(
            ordinary_turn_state_contract(source, self.compiled, self.registry)
        )
        variants = []
        foreign = dict(self.compiled.effects["187531"])
        foreign["target_masks"] = (None, None, None, None, (1002,), None, None)
        variants.append(("187531", foreign))
        target = dict(self.compiled.effects["187532"])
        target["native_target_selector"] = dict(
            target["native_target_selector"], mask=63
        )
        variants.append(("187532", target))
        unsupported = dict(self.compiled.effects["187532"], effect_class=803)
        variants.append(("187532", unsupported))
        malformed_ap = dict(
            self.compiled.effects["187530"], parameters=[], parameter_count=0
        )
        variants.append(("187530", malformed_ap))
        for reference, effect in variants:
            altered = SimpleNamespace(
                effects=ChainMap({reference: effect}, self.compiled.effects),
                source_states=self.compiled.source_states,
            )
            with self.subTest(reference=reference, effect_class=effect["effect_class"]):
                self.assertIsNotNone(
                    ordinary_turn_state_contract(source, altered, self.registry)
                )
        self.assertIsNone(
            ordinary_turn_state_contract(source, self.compiled, self.registry)
        )

    def test_recovered_pin_rejects_changed_nested_turn_callback(self):
        execution = execution_contract_sha256(
            self.sources, self.compiled, self.registry
        )
        payload = dict(
            version=1,
            actor_id=7,
            owner_id=3,
            sources=_plain(self.sources),
            deferred=[],
            execution_sha256=execution,
        )
        record = dict(payload, sha256=_digest(payload))
        checkpoint = SimpleNamespace(
            native_owned_equipment_sources={"7": ImmutableCatalog(record)}
        )
        self.assertEqual(
            len(pinned_sources(checkpoint, self.compiled, self.registry)), 1
        )
        child = dict(self.compiled.effects["187532"])
        parameters = list(child["parameters"])
        parameters[2] = 0.0
        child["parameters"] = parameters
        changed = SimpleNamespace(
            effects=ChainMap({"187532": child}, self.compiled.effects),
            source_states=self.compiled.source_states,
        )
        self.assertNotEqual(
            execution_contract_sha256(self.sources, changed, self.registry), execution
        )
        with self.assertRaisesRegex(ValueError, "execution contract mismatch"):
            pinned_sources(checkpoint, changed, self.registry)
        self.assertEqual(
            len(pinned_sources(checkpoint, self.compiled, self.registry)), 1
        )
