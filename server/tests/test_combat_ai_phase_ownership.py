"""Scoped advisory phase policy; actual native AI execution is qualified separately."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_ai_callback_spells as callbacks


class ScriptedPhaseOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            policy="reviewed-test-phase",
            map_id=363,
            layout_policy="reviewed-test-layout",
            layout_authority="reviewed-test-authority",
            actor_reference=1988,
            initial_state=7325,
            spell_reference=7508,
            source_effect_path=[332478, 332536, 332566, 332725],
            native_revision="a" * 64,
            source_closure_sha256="b" * 64,
            authority="authorized_wakemu_native_content_reconstruction",
        )
        self.actor = SimpleNamespace(id=-200, controlled=False, effective_level=110)
        self.fight = SimpleNamespace(
            current=self.actor,
            native_encounter_scene_layout=dict(
                policy=self.row["layout_policy"],
                authority=self.row["layout_authority"],
                map_id=363,
                original_world_coordinates=False,
            ),
            native_npc_initialization_receipts={
                -200: dict(
                    ref=1988,
                    descriptor_level=110,
                    initialized=True,
                    raw_triples=[7325, 1, 1],
                )
            },
        )
        self.monsters = {-200: dict(id=-200, ref=1988)}
        self.owned = {7503: 100, 7508: 100}
        self.enterContext(
            patch.object(callbacks, "_layout_declarations", return_value=(self.row,))
        )
        self.qualified = self.enterContext(
            patch.object(callbacks, "_qualified", return_value={7508})
        )
        self.enterContext(
            patch(
                "wakfu_server.combat_npc_attack.npc_spell_catalog",
                return_value={
                    "activation_policy": {
                        "enabled_monsters": {
                            "1988": {
                                "initial_state_triples": [7325, 1, 1],
                            }
                        }
                    },
                },
            )
        )
        self.enterContext(
            patch("wakfu_server.native_catalog.release", return_value="a" * 64)
        )
        self.enterContext(
            patch(
                "wakfu_server.combat_encounter_scene_policy.frozen_scene",
                return_value=None,
            )
        )

    def test_advice_excludes_scripted_phase_and_preserves_original_book_and_source_path(
        self,
    ):
        before = deepcopy(self.owned)
        self.assertEqual(
            callbacks.deliberate_spells(self.fight, self.owned, self.monsters),
            {7503: 100},
        )
        self.assertEqual(self.owned, before)
        import json

        record = json.loads(self.qualified.call_args.args[0])
        self.assertEqual(
            record["paths"],
            [
                [
                    ["state", 7325],
                    ["effect", 332478],
                    ["effect", 332536],
                    ["effect", 332566],
                    ["effect", 332725],
                    ["spell", 7508],
                ]
            ],
        )

    def test_different_map_and_original_ground_or_neo_forms_do_not_inherit_policy(self):
        for reference, map_id in ((1988, 959), (1989, 363), (5798, 363), (5825, 363)):
            with self.subTest(reference=reference, map_id=map_id):
                self.monsters[-200]["ref"] = reference
                self.fight.native_encounter_scene_layout["map_id"] = map_id
                self.assertEqual(
                    callbacks.deliberate_spells(self.fight, self.owned, self.monsters),
                    self.owned,
                )
        self.qualified.assert_not_called()

    def test_same_reference_summon_does_not_inherit_original_constructor_policy(self):
        self.actor.native_summon_source = dict(ref=1988)
        self.assertEqual(
            callbacks.deliberate_spells(self.fight, self.owned, self.monsters),
            self.owned,
        )
        self.qualified.assert_not_called()

    def test_missing_or_changed_constructor_receipt_is_not_treated_as_verified(self):
        original = deepcopy(self.fight.native_npc_initialization_receipts[-200])
        for change in (
            None,
            dict(initialized=False),
            dict(raw_triples=[7325, 2, 1]),
            dict(ref=1989),
            dict(descriptor_level=111),
        ):
            with self.subTest(change=change):
                self.fight.native_npc_initialization_receipts = (
                    {} if change is None else {-200: dict(original, **change)}
                )
                with self.assertRaisesRegex(
                    ValueError, "actual original scene constructor"
                ):
                    callbacks.deliberate_spells(self.fight, self.owned, self.monsters)
        self.qualified.assert_not_called()

    def test_phase_declaration_cannot_fabricate_an_owned_ability(self):
        with self.assertRaisesRegex(ValueError, "missing from actual owned book"):
            callbacks.deliberate_spells(self.fight, {7503: 100}, self.monsters)


if __name__ == "__main__":
    unittest.main()
