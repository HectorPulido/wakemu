"""Original independent ground-Crow birth and initial-caster retirement.

This short component does not earn the phase: the separate paid counterplay
receipt supplies that premise. It isolates the unchanged native307/28 coupling.
"""
import json
from pathlib import Path
from random import Random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))


class CrowNativePhaseLifetimeTests(unittest.TestCase):
    def test_original_independent_birth_survives_original_caster_retirement(self):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from wakfu_server.combat_crow_steel_scene_layout import reconstructed_crow_scene
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context

        scene = reconstructed_crow_scene(
            json.loads(
                (ROOT / ".runtime/ultimate-scenes-20261021/map-363.json").read_text()
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
            production_bootstrap=True,
            character_constructor=tank.__globals__["_healthy_owned_character"],
        )
        with original_bootstrap_publication():
            fight, character, monsters, deck = fixture(
                1988, 110, scene["anchor"], native_lifecycle=False
            )
        common = dict(
            player_characters={7: character}, deck_blobs={7: deck}, rng=Random(0)
        )
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
        marker = next(
            row
            for row in fight.native_effect_areas.values()
            if row["reference"] == 1724
        )
        cell = tuple(marker["cell"])
        factory, _ = server_runtime(
            character, monsters, deck, action_id=3, critical=False, **common
        )
        dispatcher, _ = factory(
            fight,
            dict(
                spell_id=7504,
                evaluation_level=1,
                caster_id=-200,
                target_id=None,
                target=cell,
            ),
        )
        self.assertEqual(dispatcher.effects["332928"]["effect_class"], 307)
        self.assertEqual(dispatcher.effects["332963"]["effect_class"], 28)
        receipt = dict(
            status="pending_native_lifetime_component_only",
            earned_phase_qualified=False,
            marker=marker,
            birth_caster=-200,
        )
        output = (
            ROOT
            / ".runtime/parallel-readiness-20261021/crow-original-phase-lifetime-component.json"
        )
        before_ids = set(fight.actors)
        try:
            with fight.effect_resolution():
                self.assertTrue(
                    dispatcher.execute(
                        EffectInvocation(
                            332928,
                            1,
                            -200,
                            None,
                            cell,
                            native_context_hex=constructed_execution_context()
                            .payload()
                            .hex(),
                        )
                    )
                )
            born = [
                actor
                for identity, actor in fight.actors.items()
                if identity not in before_ids
                and (getattr(actor, "native_summon_source", None) or {}).get("ref")
                == 1989
            ]
            self.assertEqual(len(born), 1)
            actor = born[0]
            receipt["birth"] = dict(
                id=actor.id,
                hp=actor.hp,
                team=actor.team,
                source=actor.native_summon_source,
                registration=fight.native_summon_registrations[actor.id],
                controller=actor.native_controller_id,
                master=actor.native_master_id,
            )
            self.assertGreater(actor.hp, 0)
            self.assertEqual(actor.team, fight.actors[-200].team)
            self.assertEqual(
                (actor.native_controller_id, actor.native_master_id),
                (actor.id, actor.id),
            )
            # Native1720 callback removes its original floor runner before
            # eXc assigns the resulting minimum. Preserve that sibling order.
            with fight.effect_resolution():
                self.assertTrue(
                    dispatcher.execute(
                        EffectInvocation(
                            332962,
                            1,
                            -200,
                            -200,
                            fight.actors[-200].position,
                            native_context_hex=constructed_execution_context()
                            .payload()
                            .hex(),
                        )
                    )
                )
                self.assertTrue(
                    dispatcher.execute(
                        EffectInvocation(
                            332963,
                            1,
                            -200,
                            -200,
                            fight.actors[-200].position,
                            native_context_hex=constructed_execution_context()
                            .payload()
                            .hex(),
                        )
                    )
                )
            receipt["after"] = dict(
                hp=actor.hp,
                boss_hp=fight.actors[-200].hp,
                phase=fight.phase,
                events=[
                    row
                    for row in fight.events
                    if row.get("kind") in ("death", "owner_death_hp_minimum_update")
                ],
            )
            self.assertEqual(fight.actors[-200].hp, 0)
            self.assertGreater(
                actor.hp,
                0,
                "Independent phase actor died with its original birth caster",
            )
            self.assertEqual(fight.phase, "active")
            receipt[
                "status"
            ] = "original_independent_phase_survives_original_retirement"
        except Exception as error:
            receipt.update(error_type=type(error).__name__, error=str(error))
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
