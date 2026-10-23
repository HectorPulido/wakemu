"""Typed dropped-Qq operands preserve the real player's callback ownership."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server import combat_encounter_area_callback_programs as policies
from wakfu_server import combat_encounter_area_callback_source as sources
from wakfu_server.combat_effect_dispatch import EffectInvocation


class EncounterAreaCallbackSourceTests(unittest.TestCase):
    def fixture(self):
        from wakfu_server.combat_state_ledger import StateLedger, RunningState
        from wakfu_server.combat_effect_area_targets import (
            NativeAreaTarget,
            area_target_context,
        )
        from wakfu_server.combat_effect_resolver import (
            NativeEffectResolver,
            EffectResolutionContext,
        )

        effects = json.loads(
            (
                Path(__file__).with_name("fixtures")
                / "rushu_native_pickup_removal_1650.json"
            ).read_text()
        )
        marker = StateLedger(132)
        marker._entries = (
            RunningState(301, 7001, 4, 3, 132, -1, "target", False, (), 0, True, None),
        )
        row = dict(
            uid=132,
            reference=1650,
            effect_reference=318822,
            level=1,
            owner_id=3,
            executing=True,
            cell=(0, 0, 0),
            native_area_contract="faY",
            native_running_effect_manager=True,
            state_ledger=marker,
        )
        player = SimpleNamespace(
            id=3,
            team=1,
            position=(0, 0, 0),
            hp=100,
            physical_radius=0,
            state_ledger=StateLedger(3),
        )
        boss = SimpleNamespace(
            id=-200,
            team=0,
            position=(1, 0, 0),
            hp=100,
            physical_radius=1,
            state_ledger=StateLedger(-200),
        )
        fight = SimpleNamespace(
            native_encounter_area_seed_policy=None,
            native_encounter_area_callback_programs={"policy": "unit-frozen-drop"},
            native_effect_areas={132: row},
            actors={3: player, -200: boss},
        )
        program = dict(
            area_reference=1650,
            state_reference=7001,
            steps=[
                dict(role="constructor", effect_family=315, effect_reference=318822)
            ],
        )
        definition = dict(
            type="GLYPH",
            native_area_properties=[12],
            entry_masks=[],
            effect_ids=[318813, 318814],
        )
        area = NativeAreaTarget(132, (0, 0, 0), 1, 3, native_targeting_bcR=True)
        actors = (player, boss, area)
        contexts = {
            actor.id: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for actor in (player, boss)
        }
        contexts[132] = area_target_context(area)
        resolver = NativeEffectResolver(
            actors=lambda e, i: actors,
            caster=lambda e, i: next(
                actor for actor in actors if actor.id == i.caster_id
            ),
            native_context=lambda e, i: contexts,
            context=lambda e, i: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
        )
        invocation = EffectInvocation(
            318816,
            1,
            3,
            -200,
            (0, 0, 0),
            native_retained_container=dict(
                present=True, type=3, id=132, level=1, native_kind="effect_area"
            ),
        )
        return fight, row, program, definition, effects, resolver, invocation

    def test_real_qf_grade_is_sp_operand_and_native_self_removal_keeps_player_caster(
        self,
    ):
        from wakfu_server.combat_state_level_group import runtime_child_level
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.combat_effect_groups import (
            decode_group_mode,
            execute_ordered_group,
        )
        from wakfu_server.combat_encounter_area_seed_source import (
            resolve_seed_program_selection,
        )

        fight, row, program, definition, effects, resolver, invocation = self.fixture()
        effect = effects["318816"]
        values = effect_profile(effect, invocation.level)
        with patch.object(
            policies, "encounter_area_callback_programs", return_value=(program,)
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1650": definition},
        ):
            self.assertEqual(runtime_child_level(effect, values, invocation, fight), 4)
            self.assertEqual((invocation.caster_id, invocation.target_id), (3, -200))
            wrapper = replace(
                invocation, reference=324631, wakemu_fresh_child_selection=True
            )
            selected = resolve_seed_program_selection(
                resolver,
                fight,
                effects["324631"],
                wrapper,
                effects=effects,
                definitions={"1650": definition},
            )
            self.assertEqual([(i.caster_id, i.target_id) for i in selected], [(3, 132)])
            children = []
            execute_ordered_group(
                decode_group_mode([]),
                [318818],
                caster_id=selected[0].caster_id,
                target_id=selected[0].target_id,
                target_cell=row["cell"],
                execute_child=lambda child: children.append(child) or True,
            )
            self.assertEqual([(i.caster_id, i.target_id) for i in children], [(3, 132)])
            self.assertEqual(row["state_ledger"].entries[0].level, 4)
            self.assertNotIn(132, fight.actors)

    def test_wrong_constructor_owner_pl_carrier_or_rebind_cannot_opt_in(self):
        from wakfu_server.combat_definitions import effect_profile

        for mutation in (
            "manifest",
            "constructor",
            "owner",
            "container",
            "state",
            "rebind",
            "target_getter",
        ):
            (
                fight,
                row,
                program,
                definition,
                effects,
                resolver,
                invocation,
            ) = self.fixture()
            effect = effects["318816"]
            values = effect_profile(effect, invocation.level)
            if mutation == "manifest":
                fight.native_encounter_area_callback_programs = None
            if mutation == "constructor":
                row["effect_reference"] = 324354
            if mutation == "owner":
                row["owner_id"] = 4
            if mutation == "container":
                invocation = replace(invocation, native_retained_container=None)
            if mutation == "state":
                invocation = replace(invocation, state_uid=55)
            if mutation == "rebind":
                values["parameters"][5] = 257
            if mutation == "target_getter":
                values["parameters"][7] = 0
            with self.subTest(mutation=mutation), patch.object(
                policies, "encounter_area_callback_programs", return_value=(program,)
            ), patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={"1650": definition},
            ):
                self.assertIsNone(
                    sources.callback_program_level_source(
                        fight, effect, values, invocation
                    )
                )
