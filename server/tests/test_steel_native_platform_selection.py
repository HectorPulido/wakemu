"""Read-only original platform selection on actual Steel production startup."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))


class SteelPlatformSelectionDiagnostic(unittest.TestCase):
    def diagnose_original_triggered_platform_movement_on_real_startup(self):
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_effect_groups import decode_group_mode
        from wakfu_server.combat_definitions import effect_profile

        self.diagnose_original_platform_candidates_on_real_startup()
        fight, dispatcher, plan = self._component_context
        parent = dispatcher.effects["153135"]
        mode = decode_group_mode(effect_profile(parent, 1)["parameters"])
        self.assertTrue(mode.on_target and mode.transmit_target)
        actor = fight.actors[-200]
        before = dict(
            position=actor.position,
            ap=actor.ap,
            mp=actor.mp,
            wp=actor.effect_stats[4],
            states=[entry.reference for entry in actor.state_ledger.entries],
        )
        self.assertNotIn(3498, before["states"])
        cells, edges = fight.walkable, fight.edges
        original_execute = EffectDispatcher.execute
        observations = []

        def observe(selected, invocation, **kwargs):
            result = original_execute(selected, invocation, **kwargs)
            if invocation.reference in (
                153818,
                152665,
                152666,
                152668,
                152676,
                152677,
                152667,
                152669,
                152993,
            ):
                observations.append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        result=bool(result),
                    )
                )
            return result

        receipt = dict(
            status="pending_movement_component_only",
            earned_phase_qualified=False,
            before=before,
            original_parent=153135,
            parent_mode=vars(mode),
        )
        output = (
            ROOT
            / ".runtime/parallel-readiness-20261021/steel-original-platform-movement-component.json"
        )
        try:
            # This original unconditional426 producer runs the existing native
            # temporary-spell/cost route. No3498 subscription or phase is added.
            with patch.object(
                EffectDispatcher, "execute", observe
            ), fight.effect_resolution():
                outcome = dispatcher.execute(
                    EffectInvocation(
                        153818,
                        1,
                        -200,
                        -200,
                        actor.position,
                        native_context_hex=constructed_execution_context()
                        .payload()
                        .hex(),
                        native_explicit_target=mode.on_target and mode.transmit_target,
                        wakemu_fresh_child_selection=True,
                    )
                )
            actor = fight.actors[-200]
            receipt.update(
                outcome=bool(outcome),
                sources=observations,
                after=dict(
                    position=actor.position,
                    ap=actor.ap,
                    mp=actor.mp,
                    wp=actor.effect_stats[4],
                    states=[entry.reference for entry in actor.state_ledger.entries],
                ),
            )
            self.assertEqual(actor.position, (-1, -13, 0))
            self.assertEqual(
                (actor.ap, actor.mp, actor.effect_stats[4]),
                (before["ap"], before["mp"], before["wp"]),
            )
            self.assertNotIn(3498, receipt["after"]["states"])
            self.assertEqual(
                [
                    row["reference"]
                    for row in observations
                    if row["reference"] in (152667, 152669) and row["result"]
                ],
                [152667],
            )
            self.assertEqual((fight.walkable, fight.edges), (cells, edges))
            receipt["status"] = "original_triggered_platform_movement_observed_only"
        except Exception as error:
            receipt.update(
                error_type=type(error).__name__, error=str(error), sources=observations
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")

    def diagnose_original_platform_candidates_on_real_startup(self):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from test_ultimate_encounter_scene_recipes import (
            UltimateNativePaidProducerTests,
        )
        from wakfu_server.combat_crow_steel_scene_layout import (
            reconstructed_steel_scene,
        )
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_conditions import evaluate_condition
        from wakfu_server.combat_effect_area_queries import actor_on_specific_area
        from wakfu_server.fight_checkpoint_store import snapshot

        scene = reconstructed_steel_scene(
            json.loads(
                (ROOT / ".runtime/ultimate-scenes-20261021/map-959.json").read_text()
            )
        )
        tank, _ = native_tank_fixture(validator, feca=True)
        fixture, _ = encounter_fixture_factory(
            validator,
            scene,
            caster_cell=scene["source"],
            player_level=200,
            player_breed=1,
            player_deck=[6972],
            character_constructor=tank.__globals__["_healthy_owned_character"],
            production_bootstrap=True,
        )
        with original_bootstrap_publication():
            fight, character, monsters, deck = fixture(
                3582, 170, scene["anchor"], native_lifecycle=False
            )
        rng = Random(0)
        common = dict(player_characters={7: character}, deck_blobs={7: deck}, rng=rng)
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            deck,
            action_id=2,
            fight_start=True,
            **common
        )
        serializer = UltimateNativePaidProducerTests._serializer(character, monsters)
        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=serializer,
            turn_start_provider=lambda phase, **kwargs: prepare_server_turn_start(
                character,
                monsters,
                phase,
                deck,
                native_events=True,
                area_callbacks=True,
                **common,
                **kwargs
            ),
            turn_end_provider=lambda phase, **kwargs: prepare_server_turn_end(
                character, monsters, phase, deck, **common, **kwargs
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, **common
            )[0],
        )
        runtime.turn_started()
        fight = runtime.fight
        factory, adapter = server_runtime(
            character,
            monsters,
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            **common
        )
        plan = dict(
            spell_id=4869,
            evaluation_level=1,
            caster_id=-200,
            target_id=-200,
            target=fight.actors[-200].position,
        )
        dispatcher, _ = factory(fight, plan)
        receipt = dict(
            status="selection_diagnostic_only",
            earned_phase_qualified=False,
            boss_position=fight.actors[-200].position,
            boss_states=[
                entry.reference for entry in fight.actors[-200].state_ledger.entries
            ],
            platform_rows=[
                deepcopy(row)
                for row in fight.native_effect_areas.values()
                if row.get("reference") in (911, 912)
            ],
            on_platform={},
            branches=[],
        )
        output = (
            ROOT
            / ".runtime/parallel-readiness-20261021/steel-platform-selection-diagnostic.json"
        )
        before = snapshot(fight)
        try:
            border = next(
                row
                for row in fight.native_effect_areas.values()
                if row.get("reference") == 909
            )
            cliff_effect = dispatcher.effects["152447"]
            receipt["native_cliff_kill_predicate"] = {}
            for identity in (7, -200):
                selected = EffectInvocation(
                    152447, 0, border["uid"], identity, fight.actors[identity].position
                )
                receipt["native_cliff_kill_predicate"][
                    str(identity)
                ] = evaluate_condition(
                    cliff_effect["criteria"], dispatcher.condition_context(selected)
                )
            self.assertEqual(
                receipt["native_cliff_kill_predicate"], {"7": True, "-200": False}
            )
            for reference in (911, 912):
                receipt["on_platform"][str(reference)] = actor_on_specific_area(
                    fight, actor_id=-200, reference=reference, ownership="all"
                )
            for reference in (152665, 152666, 152668):
                effect = dispatcher.effects[str(reference)]
                invocation = EffectInvocation(
                    reference,
                    1,
                    -200,
                    -200,
                    fight.actors[-200].position,
                    wakemu_fresh_child_selection=reference != 152665,
                )
                candidates = tuple(dispatcher.resolve(effect, invocation))
                row = dict(
                    reference=reference,
                    criterion=effect.get("criteria"),
                    resolution_context=vars(
                        adapter.cast.resolution(fight, plan, effect, invocation)
                    ),
                    candidates=[],
                )
                for selected in candidates:
                    context = dispatcher.condition_context(selected)
                    row["candidates"].append(
                        dict(
                            target=selected.target_id,
                            cell=selected.cell,
                            criterion_result=evaluate_condition(
                                effect["criteria"], context
                            )
                            if effect["criteria"].strip()
                            else True,
                        )
                    )
                receipt["branches"].append(row)
            self.assertEqual(
                snapshot(fight),
                before,
                "Selection-only diagnostic mutated the actual fight",
            )
            self.assertEqual(
                {
                    row["reference"]: tuple(row["cell"])
                    for row in receipt["platform_rows"]
                },
                {911: (-17, 3, 0), 912: (-1, -13, 0)},
            )
            self.assertEqual(receipt["on_platform"], {"911": True, "912": False})
            selected = [
                (branch["reference"], candidate["target"])
                for branch in receipt["branches"]
                if branch["reference"] in (152666, 152668)
                for candidate in branch["candidates"]
                if candidate["criterion_result"]
            ]
            destination = next(
                row["uid"]
                for row in receipt["platform_rows"]
                if row["reference"] == 912
            )
            self.assertEqual(selected, [(152666, destination)])
            self._component_context = fight, dispatcher, plan
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
