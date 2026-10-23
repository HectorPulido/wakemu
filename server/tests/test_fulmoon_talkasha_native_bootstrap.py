"""Real Ready creates encounter actors; reconstructed layouts grant no states."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from random import Random
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))


class FulMoonTalKashaNativeBootstrapTests(unittest.TestCase):
    def _started(
        self, reference, level, map_id, provider, *, player_breed=1, player_deck=(6972,)
    ):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from wakfu_server.combat_server_spell import prepare_server_initialization

        geometry = json.loads(
            (
                ROOT
                / ".runtime/parallel-readiness-20261021/supreme-entry-staging"
                / f"map-{map_id}.json"
            ).read_text()
        )
        scene = provider(geometry)
        tank, player_facts = native_tank_fixture(validator, feca=player_breed == 1)
        fixture, preparation = encounter_fixture_factory(
            validator,
            scene,
            caster_cell=scene["source"],
            player_level=200,
            player_breed=player_breed,
            player_deck=list(player_deck),
            production_bootstrap=True,
            character_constructor=tank.__globals__["_healthy_owned_character"],
        )
        with original_bootstrap_publication():
            fight, character, monsters, deck = fixture(
                reference, level, scene["anchor"], native_lifecycle=False
            )
        initial_ids = set(fight.actors)
        initial_areas = deepcopy(getattr(fight, "native_effect_areas", {}))
        ready, packets = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            deck,
            action_id=2,
            rng=Random(0),
            fight_start=True,
            player_characters={7: character},
            deck_blobs={7: deck},
        )
        self.assertEqual(set(fight.actors), initial_ids)
        self.assertEqual(getattr(fight, "native_effect_areas", {}), initial_areas)
        self.assertTrue(ready.native_start_event_delivered)
        self.assertTrue(packets)
        registrations = getattr(ready, "native_summon_registrations", {})
        children = {
            identity: row["authority"]["breed_id"]
            for identity, row in registrations.items()
            if identity in ready.actors
        }
        receipt = dict(
            reference=reference,
            map_id=map_id,
            status="native_ready_observed",
            original_world_coordinates=False,
            source=scene["source"],
            player=scene["anchor"],
            preparation=preparation,
            player_facts=player_facts,
            manual_state_or_actor_grants=False,
            native_children=children,
            packets=len(packets),
            actor_positions={
                str(identity): actor.position
                for identity, actor in ready.actors.items()
            },
            areas=[
                dict(reference=row["reference"], cell=row["cell"])
                for row in ready.native_effect_areas.values()
            ],
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            ROOT
            / f".runtime/ultimate-scenes-20261021/native-ready-{reference}-{stamp}.json"
        )
        output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.encounter_context = character, monsters, deck
        return ready, scene, children

    def test_fulmoon_ready_creates_four_original_totems_and_native_glyph(self):
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
            fulmoon_ready_cells,
        )

        ready, scene, children = self._started(
            3870, 185, 1056, reconstructed_fulmoon_scene
        )
        self.assertCountEqual(children.values(), [3993, 3995, 3996, 3997])
        self.assertEqual(ready.actors[-200].team, 0)
        self.assertEqual(ready.actors[7].team, 1)
        borders = [
            row
            for row in ready.native_effect_areas.values()
            if row["reference"] == 1085
        ]
        self.assertEqual(len(borders), 1)
        self.assertEqual(borders[0]["native_area_contract"], "faP")
        self.assertEqual(borders[0]["owner_id"], None)
        self.assertEqual(
            set(map(tuple, borders[0]["native_cells_xy"])),
            {cell[:2] for cell in scene["native_border_cells"]},
        )
        self.assertFalse(
            set(scene["native_border_cells"])
            & (
                set(scene["party_placement_cells"])
                | set(scene["glyph_cells"])
                | set(scene["boss_footprint"])
            )
        )
        expected = fulmoon_ready_cells(scene["source"])
        actual = {
            reference: ready.actors[identity].position
            for identity, reference in children.items()
        }
        for group, reference in (
            (177762, 3993),
            (177778, 3995),
            (177780, 3996),
            (177782, 3997),
        ):
            self.assertEqual(actual[reference], expected[group])
        glyphs = [
            row
            for row in ready.native_effect_areas.values()
            if row["reference"] == 1086
        ]
        self.assertEqual(len(glyphs), 1)
        self.assertEqual(tuple(glyphs[0]["cell"]), expected[177776])
        self.assertFalse(set(scene["party_placement_cells"]) & set(expected.values()))

    def test_talkasha_native_ready_creates_four_elemental_pyramids_and_mirror(self):
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )

        ready, scene, children = self._started(
            5500, 155, 1400, reconstructed_talkasha_scene
        )
        self.assertCountEqual(children.values(), [5502, 5502, 5502, 5502, 5579])
        elements = set()
        for identity, reference in children.items():
            if reference == 5502:
                assigned = {
                    entry.reference
                    for entry in ready.actors[identity].state_ledger.entries
                    if entry.reference in (8232, 8233, 8234, 8235)
                }
                self.assertEqual(len(assigned), 1)
                elements.update(assigned)
        self.assertEqual(elements, {8232, 8233, 8234, 8235})
        self.assertEqual(len(scene["glyph_cells"]), 5)
