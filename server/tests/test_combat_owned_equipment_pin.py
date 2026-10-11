"""Actual equipment plan pins definitions across factories and checkpoint JSON."""
from copy import deepcopy
import json
import unittest

import test_combat_owned_equipment as native_fixture
from wakfu_server.combat_owned_equipment_pin import (
    compiled_for_fight,
    pin_transaction,
    preparation_for_actor,
    pinned_sources,
    has_equipped_attachments,
)
from wakfu_server.combat_owned_equipment import initialize_transaction
from wakfu_server.combat_attachment_authority import CombatAttachmentAuthority
from wakfu_server.sublimation_eligibility import CLIENT_JAR_SHA256
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.wire import proto_field


class OwnedEquipmentPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = native_fixture.OwnedEquipmentInitializationTests
        fixture.setUpClass()
        cls.native = fixture(
            "test_actual_owned_dispatch_installs_parent_item_container_without_mutating_original"
        )
        cls.compiled, cls.registry, cls.fight = (
            fixture.compiled,
            fixture.registry,
            fixture.fight,
        )

    def equipped(self):
        character = deepcopy(self.native.character)
        state = b"".join(
            proto_field(10, proto_field(80, index) + proto_field(96, color))
            for index, color in enumerate([2, 3, 2])
        ) + proto_field(24, 27152)
        character["inventory_items"] = [
            dict(
                uid=500, reference=10272, character_id=7, quantity=1, shard_state=state
            )
        ]
        equipment = proto_field(10, proto_field(8, 500) + proto_field(16, 10))
        character["builds"] = {
            0: dict(equipment=equipment.hex(), sheet=proto_field(24, 0xFFFFFFFF).hex())
        }
        authority = CombatAttachmentAuthority(
            [
                dict(
                    reference=27152,
                    pattern_type="BASIC",
                    slot_colors=[2, 3, 2],
                    enabled=True,
                    client_jar_sha256=CLIENT_JAR_SHA256,
                )
            ],
            [],
        )
        return character, authority

    def pin(self):
        character, authority = self.equipped()
        return character, pin_transaction(
            self.fight, character, authority, self.compiled, self.registry, owner_id=3
        )

    def test_actual_plan_pin_is_immutable_detached_and_used_by_later_factory(self):
        original = snapshot(self.fight)
        character, (pinned, initial) = self.pin()
        self.assertEqual(snapshot(self.fight), original)
        self.assertEqual(
            [row["source_reference"] for row in initial["sources"]], [27152]
        )
        character["inventory_items"].clear()
        character["builds"].clear()
        recovered = preparation_for_actor(pinned, 7, self.compiled)
        self.assertEqual(
            [row["source_reference"] for row in recovered["sources"]], [27152]
        )
        with self.assertRaises(TypeError):
            pinned.native_owned_equipment_sources["7"]["sources"][0][
                "source_reference"
            ] = 28871
        first, _ = initialize_transaction(
            pinned, 7, recovered, self.native.factory(recovered["compiled"]), owner_id=3
        )
        # Later factories use fight-owned definitions even after mutable bags change.
        later = self.native.factory(compiled_for_fight(first, self.compiled))
        self.assertIn(str(initial["sources"][0]["roots"][0]), later.effects)
        self.assertEqual(
            first.actors[7].effect_stats[9], self.fight.actors[7].effect_stats[9] + 6
        )

    def test_plain_checkpoint_roundtrip_preserves_exact_pin_and_detects_mutation(self):
        _, (pinned, initial) = self.pin()
        restored = deepcopy(self.fight)
        restored.native_owned_equipment_sources = json.loads(
            json.dumps(snapshot(pinned)["native_owned_equipment_sources"])
        )
        recovery = preparation_for_actor(restored, 7, self.compiled)
        self.assertEqual(recovery["sources"][0]["source_reference"], 27152)
        root = str(initial["sources"][0]["roots"][0])
        self.assertIn(root, recovery["compiled"].effects)
        restored.native_owned_equipment_sources["7"]["sources"][0][
            "source_reference"
        ] = 28871
        with self.assertRaisesRegex(ValueError, "integrity"):
            compiled_for_fight(restored, self.compiled)

    def test_repeat_pin_and_foreign_owner_are_rejected_without_mutating_pin(self):
        character, (pinned, _) = self.pin()
        before = snapshot(pinned)
        _, authority = self.equipped()
        with self.assertRaisesRegex(ValueError, "already pinned"):
            pin_transaction(
                pinned, character, authority, self.compiled, self.registry, owner_id=3
            )
        with self.assertRaisesRegex(ValueError, "owned active"):
            pin_transaction(
                self.fight,
                character,
                authority,
                self.compiled,
                self.registry,
                owner_id=4,
            )
        self.assertEqual(snapshot(pinned), before)

    def test_disabled_authority_does_not_pin_or_activate_scroll(self):
        character, _ = self.equipped()
        pinned, initial = pin_transaction(
            self.fight,
            character,
            CombatAttachmentAuthority([], []),
            self.compiled,
            self.registry,
            owner_id=3,
        )
        self.assertEqual(initial["sources"], ())
        self.assertIs(compiled_for_fight(pinned, self.compiled), self.compiled)

    def test_changed_state_or_characteristic_contract_rejects_recovered_pin(self):
        from wakfu_server.combat_static_catalogs import CompiledEffects

        _, (pinned, _) = self.pin()
        states = dict(self.compiled.source_states)
        states["states"] = dict(states["states"])
        states["states"]["6026"] = dict(states["states"]["6026"], maximum_level=5)
        changed = CompiledEffects(self.compiled.source_effects, states)
        with self.assertRaisesRegex(ValueError, "execution contract"):
            compiled_for_fight(pinned, changed)
        registry = dict(self.registry)
        registry["effects"] = dict(registry["effects"])
        registry["effects"]["150"] = dict(registry["effects"]["150"], fixed_stat_id=87)
        with self.assertRaisesRegex(ValueError, "execution contract"):
            pinned_sources(pinned, self.compiled, registry)

    def test_two_actual_equipped_sources_add_levels_under_the_same_native_state(self):
        from wakfu_server.wire import proto_fields

        character, _ = self.equipped()
        state = b"".join(
            proto_field(tag, value)
            for tag, value in proto_fields(
                character["inventory_items"][0]["shard_state"]
            )
            if tag != 24
        )
        character["inventory_items"].append(
            dict(
                uid=501,
                reference=24309,
                character_id=7,
                quantity=1,
                shard_state=state + proto_field(24, 28871),
            )
        )
        character["builds"][0]["equipment"] += proto_field(
            10, proto_field(8, 501) + proto_field(16, 0)
        ).hex()
        authority = CombatAttachmentAuthority(
            [
                dict(
                    reference=reference,
                    pattern_type="BASIC",
                    slot_colors=[2, 3, 2],
                    enabled=True,
                    client_jar_sha256=CLIENT_JAR_SHA256,
                )
                for reference in (27152, 28871)
            ],
            [],
        )
        pinned, initial = pin_transaction(
            self.fight, character, authority, self.compiled, self.registry, owner_id=3
        )
        self.assertEqual(len(initial["sources"]), 2)
        result, _ = initialize_transaction(
            pinned, 7, initial, self.native.factory(initial["compiled"]), owner_id=3
        )
        self.assertEqual(
            result.actors[7].effect_stats[9], self.fight.actors[7].effect_stats[9] + 9
        )

    def test_authority_discovery_ignores_unequipped_bags_and_empty_builds(self):
        character, _ = self.equipped()
        self.assertTrue(has_equipped_attachments(character))
        character["builds"][0]["equipment"] = ""
        self.assertFalse(has_equipped_attachments(character))
        character["builds"].clear()
        self.assertFalse(has_equipped_attachments(character))
