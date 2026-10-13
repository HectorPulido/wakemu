"""NPC prototype copy and unchanged connected-player authority boundary."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon_visual_copy import plan_summon_visual_copy
from wakfu_server.combat_character_copy_equipment import copied_equipment_source


class NpcVisualCopyTests(unittest.TestCase):
    def metadata(self):
        return NativeActorAuthority(
            {},
            False,
            frozenset(),
            frozenset(),
            False,
            2437,
            0,
            {},
            True,
            native_actor_type=1,
            native_npc_prototype_ref=2437,
            native_copied_equipment_operand=0,
        )

    def test_actual_fresh_bje_metadata_publishes_prototype_and_inherited_operand(self):
        from wakfu_server.combat_summon_creation import native_fresh_summon_authority

        actor = SimpleNamespace(
            id=-73, effective_level=98, native_controlled_by_ai=True
        )
        metadata = native_fresh_summon_authority(actor, 2437)
        self.assertEqual(metadata.native_npc_prototype_ref, 2437)
        self.assertEqual(metadata.native_copied_equipment_operand, 0)
        self.assertEqual(copied_equipment_source(metadata, actor.id)["dsK"], 0)
        self.assertIsNone(metadata.native_selected_cosmetics)

    def test_npc_uses_prototype_identity_without_connected_player_bytes(self):
        caster = SimpleNamespace(id=-73)
        with patch(
            "wakfu_server.monsters.reference",
            return_value={
                "ref": 2437,
                "sprite_id": 40,
            },
        ) as source:
            plan = plan_summon_visual_copy(lambda *_: self.metadata(), None, caster)
        source.assert_called_once_with(2437)
        self.assertEqual(plan["model"], 40)
        self.assertEqual(plan["prototype_visual"]["reference"], 2437)
        self.assertEqual(plan["prototype_categories"]["reference"], 2437)
        self.assertEqual(plan["equipment"]["dsK"], 0)
        self.assertNotIn("appearance_hex", plan)
        self.assertNotIn("categories", plan)

    def test_unknown_npc_prototype_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "prototype authority"):
            plan_summon_visual_copy(
                lambda *_: replace(self.metadata(), native_npc_prototype_ref=None),
                None,
                SimpleNamespace(id=-73),
            )

    def test_player_still_requires_connected_ehp_authority(self):
        with self.assertRaisesRegex(ValueError, "connected bjo"):
            plan_summon_visual_copy(
                lambda *_: replace(
                    self.metadata(), native_actor_type=0, is_player=True
                ),
                None,
                SimpleNamespace(id=73),
            )

    def test_npc_equipment_cannot_substitute_unproved_nonzero_operand(self):
        with self.assertRaisesRegex(ValueError, "inherited eGj.dsK"):
            copied_equipment_source(
                replace(self.metadata(), native_copied_equipment_operand=17),
                -73,
            )
