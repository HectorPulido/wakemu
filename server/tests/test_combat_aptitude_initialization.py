"""Real native aptitude registration, conditional selection and atomic previews."""
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_combat_spell_transaction as fixture_module
from test_aptitude_catalog_coverage import aptitude_sheet
from wakfu_server.combat_aptitude_initialization import plan, effect_catalog
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class AptitudeInitializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.character,
            cls.monster,
            cls.fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            1, 60, native_qi=True
        )

    def character_with(self, bonus, points=1):
        character = deepcopy(self.character)
        character["builds"] = {
            0: {"aptitudes": aptitude_sheet([(bonus, points)]).hex()}
        }
        return character

    def initialize(self, character, fight=None):
        return prepare_server_initialization(
            character,
            {self.monster["id"]: self.monster},
            self.fight if fight is None else fight,
            3,
            encode_deck(),
            action_id=1,
        )

    def test_all_conditional_roots_register_actual_aptitude_containers_atomically(self):
        before = snapshot(self.fight)
        for bonus in (17, 27, 36):
            with self.subTest(bonus=bonus):
                character = self.character_with(bonus)
                preview, packets = self.initialize(character)
                self.assertTrue(packets)
                records = [
                    row
                    for row in preview.native_retained_records.values()
                    if row["container_type"] == 36
                ]
                self.assertTrue(records, bonus)
                self.assertEqual(
                    {row["container_id"] for row in records}, {(bonus << 16) + 1}
                )
                self.assertTrue(
                    all(row["container_is_spell"] is False for row in records)
                )
                checkpoint = snapshot(preview)
                self.assertIn(
                    "aptitudes", checkpoint["native_class_initializations"]["7"]
                )
                self.assertEqual(snapshot(self.fight), before)
                with self.assertRaises(ValueError):
                    self.initialize(character, preview)
                self.assertEqual(snapshot(preview), checkpoint)

    def test_conditional_roots_are_deferred_without_evaluating_criteria_at_registration(
        self,
    ):
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        original = NativeServerRuntimeAdapter.condition
        roots = {row[2] for row in plan(self.character_with(17))}
        seen = []

        def capture(adapter, preview, source, effect, invocation, **kwargs):
            if invocation.reference in roots:
                seen.append(invocation.reference)
            return original(adapter, preview, source, effect, invocation, **kwargs)

        with patch.object(NativeServerRuntimeAdapter, "condition", capture):
            preview, _ = self.initialize(self.character_with(17))
        # Native Qe.d stores the root; its criterion waits for Qa.aZN events.
        self.assertFalse(seen)
        records = [
            row
            for row in preview.native_retained_records.values()
            if row["container_type"] == 36
        ]
        self.assertTrue(records)
        self.assertTrue(preview.native_class_initializations)

    def test_missing_child_authority_fails_before_any_aptitude_effect_is_installed(
        self,
    ):
        character = self.character_with(27)
        before = snapshot(self.fight)
        broken = deepcopy(effect_catalog())
        del broken["effects"]["136597"]
        with patch(
            "wakfu_server.combat_aptitude_initialization.effect_catalog",
            return_value=broken,
        ):
            with self.assertRaisesRegex(ValueError, "effect closure"):
                self.initialize(character)
        self.assertEqual(snapshot(self.fight), before)

    def test_native_identity_and_points_use_eQr_not_character_level(self):
        for bonus, points in ((17, 10), (27, 1), (36, 10)):
            rows = plan(self.character_with(bonus, points))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][:2], (bonus, points))
            self.assertEqual(rows[0][3], (bonus << 16) + points)

    def test_real_fight_start_replays_conditional_roots_with_original_aptitude_points(
        self,
    ):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        character = deepcopy(self.character)
        character["builds"] = {
            0: {"aptitudes": aptitude_sheet([(17, 2), (36, 2)]).hex()}
        }
        activated = []
        executed = []
        original = EffectDispatcher.execute_activation
        original_execute = EffectDispatcher.execute

        def capture(dispatcher, invocation, **kwargs):
            if invocation.reference in (165201, 303745, 164894):
                activated.append(
                    (invocation.reference, invocation.native_retained_container)
                )
            return original(dispatcher, invocation, **kwargs)

        def capture_execute(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference == 164894:
                executed.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        result,
                    )
                )
            return result

        before = snapshot(self.fight)
        with (
            patch.object(EffectDispatcher, "execute_activation", capture),
            patch.object(EffectDispatcher, "execute", capture_execute),
        ):
            preview, packets = prepare_server_initialization(
                character,
                {self.monster["id"]: self.monster},
                self.fight,
                3,
                encode_deck(),
                action_id=1,
                fight_start=True,
            )
        self.assertTrue(preview.native_start_event_delivered)
        self.assertTrue(packets)
        self.assertEqual(
            {reference for reference, _ in activated},
            {165201, 303745},
        )
        self.assertTrue(executed, msg={"executed": executed})
        for reference, container in activated:
            if reference == 164894:
                continue
            bonus = 17 if reference == 165201 else 36
            self.assertEqual(container["type"], 36)
            self.assertEqual(container["id"], (bonus << 16) + 2)
            self.assertEqual(container["level"], 2)
            self.assertFalse(container["is_spell"])
        # Native aptitude 36's actual 164894 branch applies 4% of the
        # initialized max-HP value per allocated point as armor at fight start.
        armor_before = self.fight.actors[7].effect_stats[97]
        armor_after = preview.actors[7].effect_stats[97]
        self.assertEqual(
            armor_after - armor_before,
            int(preview.actors[7].max_hp * 0.04 * 2),
        )
        self.assertEqual(snapshot(self.fight), before)
