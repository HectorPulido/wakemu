"""Native SELF query selects the real Qq without changing caster ownership."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_resolver import (
    NativeEffectResolver,
    EffectResolutionContext,
)
from wakfu_server import combat_encounter_seed_programs as manifests
from wakfu_server import combat_state_managers as managers

from wakfu_server import combat_encounter_area_seed_source as module


class SeedRemovalSelectionTests(unittest.TestCase):
    def fixture(self):
        effects = json.loads(
            (
                Path(__file__).with_name("fixtures")
                / "rushu_native_pickup_removal_1650.json"
            ).read_text()
        )
        program = dict(
            area_reference=1650,
            creator_reference=324354,
            program_reference=324353,
            state_reference=7001,
            state_effect_reference=324355,
            level=1,
        )
        seed = dict(
            area_reference=1650,
            effect_reference=324354,
            program_reference=324353,
            state_reference=7001,
            state_effect_reference=324355,
            cell=[0, 0, 0],
        )
        row = dict(
            uid=132,
            reference=1650,
            effect_reference=324354,
            level=1,
            owner_id=-200,
            executing=True,
            cell=(0, 0, 0),
        )
        fight = SimpleNamespace(
            native_encounter_area_seed_policy={"boss_reference": 5306},
            native_effect_areas={132: row},
            native_encounter_area_setups={
                "setup": dict(
                    schema="wakemu-native-area-setup-v1",
                    created_area_uids=[132],
                    plan=dict(creator_id=-200, seeds=[seed]),
                )
            },
        )
        owner = SimpleNamespace(
            id=-200, team=0, position=(0, 0, 0), hp=10, physical_radius=0
        )
        area = SimpleNamespace(
            id=132,
            team=0,
            position=(0, 0, 0),
            hp=10,
            physical_radius=0,
            state_ledger=SimpleNamespace(
                entries=(SimpleNamespace(reference=7001, level=1),)
            ),
        )
        actors = [owner, area]
        contexts = {
            actor.id: dict(
                bEe=True,
                is_amO=True,
                is_eGj=actor is owner,
                is_Qq=actor is area,
                is_eHH=actor is owner,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
                bcR=True,
            )
            for actor in actors
        }
        resolver = NativeEffectResolver(
            actors=lambda e, i: actors,
            caster=lambda e, i: next(a for a in actors if a.id == i.caster_id),
            native_context=lambda e, i: contexts,
            context=lambda e, i: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
        )
        invocation = EffectInvocation(
            324631,
            1,
            -200,
            2,
            (0, 0, 0),
            wakemu_fresh_child_selection=True,
            native_retained_container=dict(
                present=True, type=3, id=132, level=1, native_kind="effect_area"
            ),
        )
        return fight, row, program, area, resolver, effects, invocation

    def resolve(self, fixture):
        fight, row, program, area, resolver, effects, invocation = fixture
        with patch.object(
            manifests, "encounter_seed_programs", return_value=(program,)
        ), patch.object(managers, "registered_area_pv", return_value=area):
            return module.resolve_seed_program_selection(
                resolver,
                fight,
                effects["324631"],
                invocation,
                effects=effects,
                definitions={"1650": {"effect_ids": [318813, 318814]}},
            )

    def test_native_self_selects_real_qq_and_preserves_owner(self):
        fixture = self.fixture()
        original = fixture[4](fixture[5]["324631"], fixture[6])
        self.assertEqual(original, ())
        self.assertEqual(
            [(i.caster_id, i.target_id) for i in self.resolve(fixture)], [(-200, 132)]
        )
        self.assertEqual(fixture[6].caster_id, -200)
        from wakfu_server.combat_effect_groups import (
            decode_group_mode,
            execute_ordered_group,
        )
        from wakfu_server.combat_direct_target import native_direct_target_policies

        selected = self.resolve(fixture)[0]
        children = []
        execute_ordered_group(
            decode_group_mode([]),
            [318818],
            caster_id=selected.caster_id,
            target_id=selected.target_id,
            target_cell=fixture[3].position,
            execute_child=lambda child: children.append(child) or True,
        )
        child = children[0]
        leaf_invocation = replace(
            selected,
            reference=child.child_id,
            caster_id=child.caster_id,
            target_id=child.target_id,
            cell=child.cell,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        fixture[4].direct_target_policies = native_direct_target_policies()
        leaf_selected = fixture[4](fixture[5]["318818"], leaf_invocation)
        self.assertEqual(
            [(i.caster_id, i.target_id) for i in leaf_selected], [(-200, 132)]
        )
        for node in fixture[5].values():
            node["children"] = tuple(node.get("children", ()))
            node["parameters"] = tuple(node.get("parameters", ()))
        self.assertEqual(
            [(i.caster_id, i.target_id) for i in self.resolve(fixture)], [(-200, 132)]
        )

    def test_missing_manifest_or_committed_uid_preserves_original_self(self):
        fixture = self.fixture()
        fixture[0].native_encounter_area_seed_policy = None
        self.assertEqual(self.resolve(fixture), ())
        fixture = self.fixture()
        fixture[0].native_encounter_area_setups["setup"]["created_area_uids"] = [999]
        self.assertEqual(self.resolve(fixture), ())

    def test_unrelated_wrapper_retained_state_wrong_creator_and_inactive_callback_do_not_opt_in(
        self,
    ):
        for kind in ("state", "creator", "executing", "unrelated", "rebind"):
            fixture = list(self.fixture())
            if kind == "state":
                fixture[6] = replace(fixture[6], state_uid=444)
            if kind == "creator":
                fixture[1]["effect_reference"] = 123
            if kind == "executing":
                fixture[1]["executing"] = False
            if kind == "unrelated":
                fixture[5]["318816"]["children"] = []
            if kind == "rebind":
                fixture[5]["318816"]["parameters"][10] = 257
            self.assertEqual(self.resolve(fixture), (), kind)

    def returned_fixture(self):
        from wakfu_server.combat_state_ledger import StateLedger, RunningState

        fixture = self.fixture()
        fight, row, program, area, resolver, effects, invocation = fixture
        # Initial publication is retained, but the actual315 created a new Qq.
        fight.native_encounter_area_setups["setup"]["created_area_uids"] = [999]
        row.update(
            effect_class=315,
            effect_uid=4882,
            native_area_contract="faY",
            native_qq_bhi=False,
            native_qq_guard_source="Qq.constructor",
            native_running_effect_manager=True,
        )
        ledger = StateLedger(row["uid"])
        ledger._entries = (
            RunningState(
                4884, 7001, 5, -200, row["uid"], -1, "target", False, (), 0, True, None
            ),
        )
        row["state_ledger"] = ledger
        area.state_ledger = ledger
        fight.actors = {
            -200: SimpleNamespace(id=-200, state_ledger=StateLedger(-200)),
            2: SimpleNamespace(id=2, state_ledger=StateLedger(2)),
        }
        return fixture

    def test_returned_native_qq_uses_real_manager_without_initial_uid_membership(self):
        fixture = self.returned_fixture()
        fight, row, program, area, resolver, effects, invocation = fixture
        definition = dict(
            type="GLYPH",
            native_area_properties=[12],
            entry_masks=[],
            effect_ids=[318813, 318814],
        )
        with patch.object(
            manifests, "encounter_seed_programs", return_value=(program,)
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1650": definition},
        ):
            selected = module.resolve_seed_program_selection(
                resolver,
                fight,
                effects["324631"],
                invocation,
                effects=effects,
                definitions={"1650": definition},
            )
        self.assertEqual(
            [(item.caster_id, item.target_id) for item in selected], [(-200, 132)]
        )
        self.assertEqual(row["state_ledger"].entries[0].level, 5)
        self.assertNotIn(row["uid"], fight.actors)
        self.assertNotIn(
            row["uid"], fight.native_encounter_area_setups["setup"]["created_area_uids"]
        )
        self.assertEqual((invocation.caster_id, invocation.target_id), (-200, 2))

    def test_returned_area_requires_constructor_and_frozen_program_provenance(self):
        mutations = (
            "family",
            "contract",
            "guard",
            "completed",
            "manager",
            "runner",
            "level",
            "receipt_program",
            "receipt_owner",
            "owner",
            "creator",
        )
        for mutation in mutations:
            fixture = self.returned_fixture()
            fight, row, program, area, resolver, effects, invocation = fixture
            if mutation == "family":
                row["effect_class"] = 339
            if mutation == "contract":
                row["native_area_contract"] = "faW"
            if mutation == "guard":
                row["native_qq_guard_source"] = "unknown"
            if mutation == "completed":
                row["native_qq_bhi"] = True
            if mutation == "manager":
                row["native_running_effect_manager"] = False
            if mutation == "runner":
                row["effect_uid"] = None
            if mutation == "level":
                row["level"] = invocation.native_retained_container["level"] = 2
            if mutation == "receipt_program":
                fight.native_encounter_area_setups["setup"]["plan"]["seeds"][0][
                    "program_reference"
                ] += 1
            if mutation == "receipt_owner":
                fight.native_encounter_area_setups["setup"]["plan"]["creator_id"] = 3
            if mutation == "owner":
                row["owner_id"] = 3
            if mutation == "creator":
                row["effect_reference"] += 1
            with self.subTest(mutation=mutation):
                self.assertEqual(self.resolve(fixture), ())

    def test_owned_state_application_is_not_a_selection_operand(self):
        fixture = self.fixture()
        for reference in ("318817",):
            effect = fixture[5][reference]
            self.assertIsNone(
                module.seed_program_removal_selection_source(
                    fixture[0],
                    effect,
                    replace(fixture[6], reference=int(reference)),
                    effects=fixture[5],
                    definitions={},
                )
            )


if __name__ == "__main__":
    unittest.main()
