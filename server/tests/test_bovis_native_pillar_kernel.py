"""Representative real native catalog kernel; no AI, TLS or quest mutations."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_DATABASE_URL"), "requires read-only native catalog"
)
class BovisNativePillarKernelTests(unittest.TestCase):
    def fixture(self, target_reference, *, marker_selection=True):
        from wakfu_server import monsters
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_npc_initialization import _runtime

        path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/maps/owned_story_profiles/bovis-lair-1002-encounters.json"
        )
        scene = json.loads(path.read_text())["rooms"][0]["encounter_scene"]
        declaration = deepcopy(scene["native_initial_glyphs"][0])
        if not marker_selection:
            declaration.pop("marker_damage_selection", None)
        members, actors = {}, []
        for identity, team, position in ((-7, 1, (-5, -11, 0)), (-8, 0, (-3, -10, 0))):
            reference = 3774 if team == 1 else target_reference
            level = 38 if reference == 3845 else 16
            member = monsters.owned_instance(
                reference,
                level,
                identity,
                map_id=1002,
                instance_id=99,
                x=position[0],
                y=position[1],
                z=position[2],
                team=team,
            )
            members[identity] = member
            actors.append(
                Actor(
                    identity,
                    team,
                    position,
                    member["hp"],
                    member["ap"],
                    member["mp"],
                    member["initiative"],
                    level,
                    max_hp=member["max_hp"],
                    direction=0,
                )
            )
        from wakfu_server.combat_qi_surface_catalog import (
            native_qi_surfaces,
            native_qi_surface_provenance,
        )

        surfaces = native_qi_surfaces(1002)
        columns = {
            xy: values for _, chunk in surfaces.chunks for xy, values in chunk.items()
        }
        cells = {
            (x, y, columns[x, y][0].z) for x in range(-5, 0) for y in range(-12, -7)
        }
        fight = Fight(100, actors, cells, {1: {(-5, -11, 0)}, 0: {(-3, -10, 0)}})
        from wakfu_server.combat_wire import arena as native_arena

        arena = native_arena(
            1002,
            99,
            sorted(cells),
            {1: {(-5, -11, 0)}, 0: {(-3, -10, 0)}},
            surface_indices={xy: 0 for xy in ((x, y) for x, y, _ in cells)},
            native_surfaces=surfaces,
        )
        fight.native_qi_snapshot = {
            name: deepcopy(arena[name])
            for name in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = native_qi_surface_provenance(1002)
        prepare_environment_glyphs(
            fight,
            dict(
                native_encounter_scene_layout=dict(
                    party_placement_cells=[[-3, -10, 0]], boss_footprint=[[-5, -11, 0]]
                ),
                native_initial_glyphs=[declaration],
                native_initial_glyph_policy=scene["policy_id"],
                native_initial_glyph_authority=scene["authority"],
            ),
            1000,
        )
        initialize_global_pv_collections(fight, tuple(members))
        initialize_fight_snapshots(
            fight,
            characters={},
            monsters=members,
            wp_resources={i: (m["wp"], m["wp"]) for i, m in members.items()},
            running_effects={i: () for i in members},
            initial_effect_uid=1,
        )
        # This is a direct kernel boundary, without an ordinary AI turn or win command.
        fight.phase, fight.order = "active", list(members)
        from wakfu_server.combat_timeline_snapshot import (
            initialize as initialize_timeline,
        )

        initialize_timeline(fight, fight.order)
        fight.turn_id, fight.native_timeline_round = 1, 1
        factory, _ = _runtime(members, -7)
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        return fight, dispatcher, factory

    def test_authored_pillar_damage_explodes_and_retires_with_real_bovis_and_lethal_target(
        self,
    ):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_fake_fighter_resources import fake_fighter_hp_state
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_area_orientation import creation_area_pv
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        for target_reference in (3845, 3774):
            with self.subTest(target_reference=target_reference):
                fight, dispatcher, factory = self.fixture(target_reference)
                row = fight.native_effect_areas[999]
                self.assertEqual(row["direction"], -1)  # Native visual field.
                self.assertEqual(
                    creation_area_pv(fight, 999).direction, 7
                )  # Qq.bcy null owner.
                self.assertEqual(
                    fake_fighter_hp_state(row, native_effect_areas()["986"])["minimum"],
                    1,
                )
                self.assertEqual(len(row["state_ledger"].entries), 1)
                self.assertTrue(
                    any(
                        r["reference"] == 997
                        for r in fight.native_effect_areas.values()
                    )
                )
                target_before, hero_before = fight.actors[-8].hp, fight.actors[-7].hp
                for _ in range(10):
                    if 999 not in fight.native_effect_areas:
                        break
                    # Original3774 spell5239 damage leaf, unchanged source definition.
                    self.assertTrue(
                        dispatcher.execute(
                            EffectInvocation(
                                162135,
                                16,
                                -7,
                                999,
                                tuple(row["cell"]),
                                native_retained_container={"present": False},
                            )
                        )
                    )
                self.assertNotIn(999, fight.native_effect_areas)
                self.assertEqual(fight.native_effect_areas, {})
                self.assertEqual(fight.actors[-8].hp, max(0, target_before - 250))
                self.assertLess(fight.actors[-7].hp, hero_before)
                events = [e for e in fight.events if e.get("kind") == "damage"]
                self.assertEqual(
                    [e["hp"] for e in events if e["target_id"] == 999][-1], 1
                )
                self.assertTrue(
                    any(e["source_id"] == 999 and e["target_id"] == -8 for e in events)
                )
                if target_reference == 3774:
                    self.assertTrue(registered_ordinary_death(fight, fight.actors[-8]))
                factory(fight, {"native_retained_container": {"present": False}})
                self.assertEqual(fight.native_effect_areas, {})

    def test_marker_recipient_reconstruction_requires_explicit_authored_opt_in(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fight, dispatcher, _ = self.fixture(3845, marker_selection=False)
        for _ in range(10):
            if 999 not in fight.native_effect_areas:
                break
            dispatcher.execute(
                EffectInvocation(
                    162135,
                    16,
                    -7,
                    999,
                    (-4, -10, 2),
                    native_retained_container={"present": False},
                )
            )
        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(fight.actors[-8].hp, 800)
