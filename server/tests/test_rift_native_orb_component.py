"""Original boss death/orb component on a original native1318 terrain.

The native2100 constructor,6807 death subscriber,315/bcT glyphs and their
original roots run. This does not claim full boss AI/initial-spell Ready.
"""
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import unittest


class NativeRiftOrbComponentTests(unittest.TestCase):
    def test_native_boss_death_glyphs_player_contact_and_killer_clock(self):
        from tools.sublimation_bounded_census import BoundedDataset
        from wakfu_server import native_catalog
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.combat_timed_expiration import expire_timed_effects
        from wakfu_server.rift_native_gameplay import install_wave_state
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests

        manifest = os.environ.get("WAKFU_RIFT_ORB_MANIFEST")
        if not manifest:
            raise RuntimeError(
                "Explicit hash-pinned boss/carrier/orb manifest required"
            )
        dataset = BoundedDataset(manifest)
        dataset.install_catalog_backend()
        inventory = dataset.read(
            dataset.manifest["semantic"]["published_document_inventory"]
        )
        native_catalog._exists = lambda revision, name: (
            revision == dataset.manifest["revision"] and name in inventory
        )
        effects = {
            **dataset.closure["effects"],
            **dataset.read(dataset.manifest["semantic"]["extra_effects"])["effects"],
        }
        states = {
            **dataset.states["states"],
            **dataset.read(dataset.manifest["semantic"]["extra_states"])["states"],
        }
        recipe_path = Path(
            ".runtime/parallel-readiness-20261023/rift-phase2/native_orb_recipe.py"
        )
        expected = os.environ.get("WAKFU_RIFT_ORB_RECIPE_SHA256")
        if (
            not expected
            or hashlib.sha256(recipe_path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Native orb recipe must be hash-pinned")
        spec = importlib.util.spec_from_file_location("native_orb_recipe", recipe_path)
        recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recipe)
        policy = NativeRiftCarrierComponentTests.policy()
        catalog = dict(
            type="ULTIMATE_INFINITE_WAVE", map_id=1318, wave_id=1, species_refs=[2100]
        )
        roles = roles_for_catalog(catalog, policy, monster_references=(2100,))
        fixture = recipe.build_fixture(
            effects=effects,
            states=states,
            registry=dataset.closure["registry"],
            player_team=roles.player_team,
            npc_team=roles.npc_team,
            monster_reference=2100,
            monster_level=120,
            encounter_roles=roles,
        )
        fight, dispatcher = fixture.fight, fixture.dispatcher
        fight.rift_wave_state = dict(
            instance_id=1,
            wave=1,
            turn_budget=40,
            wave_actor_ids=[-200],
            catalog=catalog,
            policy=policy,
            seed="native-orb-component",
            world_group_id=fight.id,
        )
        fight.rift_monsters = fixture.monster_sources
        self.assertEqual(fixture.enemy.max_hp, 14300)
        self.assertEqual((fixture.player.team, fixture.enemy.team), (1, 0))
        install_wave_state(dispatcher, actor_ids=(-200,), wave=1)
        self.assertTrue(
            any(s.reference == 6807 for s in fixture.enemy.state_ledger.entries)
        )
        self.assertEqual(fight.native_effect_areas, {})
        self.assertTrue(
            dispatcher.execute(
                EffectInvocation(
                    402298,
                    1,
                    fixture.player.id,
                    fixture.enemy.id,
                    fixture.enemy.position,
                    native_context_hex=constructed_execution_context().payload().hex(),
                    native_retained_container={"present": False},
                )
            )
        )
        self.assertEqual(fixture.enemy.hp, 0)
        areas = tuple(fight.native_effect_areas.values())
        self.assertGreaterEqual(len(areas), 1)
        self.assertLessEqual(len(areas), 3)
        self.assertIn(1575, {row["reference"] for row in areas})
        self.assertLessEqual({row["reference"] for row in areas}, {1575, 1579, 1580})
        # Native extra armor/power roots each keep their original40% roll.
        expiry_fight = deepcopy(fight)
        runtime = dispatcher.native_area_events
        for row in areas:
            self.assertEqual(runtime._definition(row)["type"], "GLYPH")
            self.assertNotEqual(row.get("native_area_contract"), "faM")
        # Exact real QI relocation plus the shared movement callback. This
        # component tests native contact; paid pathfinding is qualified elsewhere.
        picked = next(row for row in areas if row["reference"] == 1575)
        before = fixture.player.position
        destination = tuple(picked["cell"])
        move_registered_actor(fight, fixture.player, destination)
        runtime.movement(fixture.player.id, from_cell=before, to_cell=destination)
        self.assertNotIn(picked["uid"], fight.native_effect_areas)
        self.assertFalse(getattr(fight, "native_artifact_activation_receipts", {}))
        fight = expiry_fight
        remaining = set(fight.native_effect_areas)
        self.assertTrue(remaining)
        timers = [
            row["timer"]
            for row in fight.native_owned_area_effects.values()
            if row.get("timer") is not None
        ]
        self.assertTrue(timers)
        self.assertEqual({timer["actor_id"] for timer in timers}, {fixture.player.id})
        timer = timers[0]
        # Original retained timer selects the killer's START, never a wall clock
        # or another fighter's boundary. No timer is fabricated by the fixture.
        self.assertEqual(timer["phase"], "start")
        expire_timed_effects(
            fight,
            actor_id=fixture.enemy.id,
            round_number=timer["expiration_round"],
            phase=timer["phase"],
            action_id=80,
            runtime_factory=fixture.expiration_factory,
        )
        self.assertEqual(set(fight.native_effect_areas), remaining)
        expire_timed_effects(
            fight,
            actor_id=fixture.player.id,
            round_number=timer["expiration_round"],
            phase=timer["phase"],
            action_id=81,
            runtime_factory=fixture.expiration_factory,
        )
        self.assertFalse(fight.native_effect_areas)
