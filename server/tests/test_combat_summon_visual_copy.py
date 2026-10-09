import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_character_copy_codec import CopiedAppearance
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon_visual_copy import (
    plan_summon_visual_copy,
    install_summon_visual_copy,
)


class NativeSummonVisualCopyTests(unittest.TestCase):
    def test_registered_bje_keeps_wrapped_metadata_and_ordinary_character_source(self):
        from wakfu_server.combat_character_copy_codec import connected_copy_appearance

        fight, actor, caster, metadata, appearance = self.fixture()
        character = dict(id=caster.id, breed=4, appearance=dict(sex=0, clothIndex=0))

        class Ordinary:
            characters = {caster.id: character}

            def __call__(self, preview, value):
                raise ValueError("Ordinary authority roster changed")

        class Registered:
            ordinary = Ordinary()

            def __call__(self, preview, value):
                self.seen = tuple(preview.actors)
                return metadata(preview, value)

        authority = Registered()
        with patch(
            "wakfu_server.wire.appearance_section", return_value=b"\x00\x00\x01"
        ):
            result = connected_copy_appearance(
                authority, fight, caster, model_query=lambda *_: 123
            )
        self.assertEqual(result.source_id, caster.id)
        self.assertEqual(result.model, 123)
        self.assertEqual(authority.seen, (7, 91))

    def fixture(self, equipment=0):
        caster = SimpleNamespace(id=7, effect_stats={20: 13})
        actor = SimpleNamespace(
            id=91,
            native_controller_id=7,
            native_fight_property_counts={101: 1},
            effect_stats={20: 0},
        )
        fight = SimpleNamespace(
            actors={7: caster, 91: actor},
            native_summon_registrations={91: {"controller_id": 7}},
        )
        base = dict(
            targeting={},
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
        )
        source = NativeActorAuthority(
            **base,
            is_player=True,
            breed_id=4,
            native_actor_type=0,
            native_is_ehp=True,
            native_selected_cosmetics={7: equipment}
        )
        target = NativeActorAuthority(
            **base,
            is_player=False,
            breed_id=3251,
            native_actor_type=1,
            is_summon=True,
            native_controller_id=7
        )
        authority = lambda preview, value: source if value is caster else target
        appearance = CopiedAppearance(7, 123, bytes(range(9)), ((2, 44),))
        return fight, actor, caster, authority, appearance

    def test_namespace_cannot_substitute_for_canonical_authority(self):
        fight, actor, caster, authority, appearance = self.fixture()
        fake = SimpleNamespace(native_actor_type=0, native_is_ehp=True)
        with self.assertRaisesRegex(ValueError, "connected bjo"):
            plan_summon_visual_copy(lambda *_: fake, fight, caster)

    def test_native3251_additional_zero_PJ_call_follows_visual_constructor_call(self):
        fight, actor, caster, authority, appearance = self.fixture()
        from wakfu_server.combat_character_copy_equipment import copied_equipment_source

        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=appearance,
        ):
            actor.native_pending_summon_visual_copy = plan_summon_visual_copy(
                authority, fight, caster
            )
            actor.native_pending_summon_equipment_replication = copied_equipment_source(
                authority(fight, caster), caster.id
            )
            self.assertTrue(install_summon_visual_copy(fight, actor, caster, authority))
        self.assertEqual(
            [row["callsite"] for row in actor.native_summon_equipment_calls],
            ["bje.ac.bPi.PJ", "eZl.c.reference3251.PJ"],
        )
        self.assertEqual(
            [row["dsK"] for row in actor.native_summon_equipment_calls], [0, 0]
        )
        self.assertEqual(actor.effect_stats, {20: 0})
        self.assertFalse(hasattr(actor, "native_pending_summon_equipment_replication"))

    def test_install_after_registration_preserves_bje_stats_and_plain_checkpoint(self):
        fight, actor, caster, authority, appearance = self.fixture()
        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=appearance,
        ):
            actor.native_pending_summon_visual_copy = plan_summon_visual_copy(
                authority, fight, caster
            )
            self.assertTrue(install_summon_visual_copy(fight, actor, caster, authority))
        self.assertEqual(actor.effect_stats, {20: 0})
        self.assertEqual(caster.effect_stats, {20: 13})
        self.assertEqual(actor.native_summon_visual_copy["model"], 123)
        self.assertEqual(actor.native_summon_visual_copy["categories"], [[2, 44]])
        self.assertEqual(actor.native_character_copy_equipment_source["dsK"], 0)
        self.assertFalse(hasattr(actor, "native_pending_summon_visual_copy"))
        json.dumps(actor.native_summon_visual_copy, allow_nan=False)

    def test_missing_registration_cannot_install_visual_early(self):
        fight, actor, caster, authority, appearance = self.fixture()
        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=appearance,
        ):
            actor.native_pending_summon_visual_copy = plan_summon_visual_copy(
                authority, fight, caster
            )
            fight.native_summon_registrations.clear()
            with self.assertRaises(ValueError):
                install_summon_visual_copy(fight, actor, caster, authority)
        self.assertFalse(hasattr(actor, "native_summon_visual_copy"))

    def test_positive_equipment_requires_actual_effect_producer(self):
        fight, actor, caster, authority, appearance = self.fixture(equipment=4)
        from wakfu_server.combat_copied_equipment_plan import SOURCE

        catalog = dict(
            producer=SOURCE,
            complete=True,
            definition_count=1,
            definitions={
                "4": dict(
                    reference=4,
                    container_type=12,
                    fresh_container_level=20,
                    ordered_effects=[
                        dict(
                            ordinal=0,
                            reference=91,
                            effect_class=1066,
                            parameters=[1, 0],
                            metadata={},
                        )
                    ],
                )
            },
        )
        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=appearance,
        ), patch(
            "wakfu_server.combat_character_copy_equipment.native_copied_equipment_catalog",
            return_value=catalog,
        ):
            with self.assertRaisesRegex(ValueError, "equipment effect closure"):
                plan_summon_visual_copy(authority, fight, caster)

    def test_positive_complete_missing_or_empty_definition_is_native_noop(self):
        from wakfu_server.combat_copied_equipment_plan import SOURCE
        from wakfu_server.combat_character_copy_equipment import copied_equipment_source

        catalog = dict(
            producer=SOURCE,
            complete=True,
            definition_count=1,
            definitions={
                "4": dict(
                    reference=4,
                    container_type=12,
                    fresh_container_level=20,
                    ordered_effects=[],
                )
            },
        )
        for operand, status in (
            (4, "explicit_self_effects"),
            (5, "missing_definition_return"),
        ):
            fight, actor, caster, authority, appearance = self.fixture(
                equipment=operand
            )
            with patch(
                "wakfu_server.combat_character_copy_equipment.native_copied_equipment_catalog",
                return_value=catalog,
            ):
                source = copied_equipment_source(authority(fight, caster), caster.id)
            self.assertEqual(source["dsK"], operand)
            self.assertEqual(source["native_plan"]["status"], status)
            self.assertEqual(source["native_plan"]["roots"], [])

    def test_changed_source_does_not_install_stale_visual_plan(self):
        fight, actor, caster, authority, appearance = self.fixture()
        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=appearance,
        ):
            actor.native_pending_summon_visual_copy = plan_summon_visual_copy(
                authority, fight, caster
            )
        changed = CopiedAppearance(7, 124, appearance.appearance, appearance.categories)
        with patch(
            "wakfu_server.combat_character_copy_codec.connected_copy_appearance",
            return_value=changed,
        ):
            with self.assertRaisesRegex(ValueError, "Changed native bPi"):
                install_summon_visual_copy(fight, actor, caster, authority)
        self.assertFalse(hasattr(actor, "native_summon_visual_copy"))
