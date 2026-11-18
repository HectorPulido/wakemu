"""Bovis physical stages preserve actual combat and separate native outcomes."""
from copy import deepcopy
from contextlib import nullcontext
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server import owned_story_controller as controller, owned_story_mechanics
from wakfu_server import combat_mission_allies
from wakfu_server.achievements import combat_missions

ROOT = Path(__file__).parents[1] / "wakfu_server"
PROFILE = ROOT / "maps/owned_story_profiles/bovis-lair-1002.json"


class BovisLairStoryTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(PROFILE.read_text())

    def test_native_scenes_and_actual_door_zone_are_pinned(self):
        selected = controller.policy(
            dict(topology=dict(owned_story_controller=self.profile))
        )
        native = owned_story_mechanics.sources(selected)
        self.assertEqual(
            native["scenes"]["16267"],
            dict(argument_count=4, duration_ms=51500, callback=16267),
        )
        self.assertEqual(native["scenes"]["16296"]["callback"], 16296)
        self.assertEqual(native["scenes"]["16161"]["callback"], 2)
        self.assertEqual(native["interaction_approaches"]["25581"], [[5, -14, 0]])
        zone = next(row for row in native["objects"] if row["id"] == 25602)
        self.assertEqual(zone["type"], "ZoneTrigger")

    def test_first_door_and_mimi_scene_never_grant_rescue_or_boss_credit(self):
        steps = {row["id"]: row for row in self.profile["steps"]}
        for identity in [
            "bovis-lair-explored",
            "bovis-door-opened",
            "bovis-first-intro-finished",
            "bovis-mimi-confrontation",
            "bovis-mimi-intro-finished",
        ]:
            self.assertFalse(
                any(
                    effect.get("quest_id") in (2711, 2720)
                    for effect in steps[identity]["effects"]
                )
            )
        self.assertIsNone(
            controller.plan(self.profile, set(), kind="scenario_complete", reference=2)
        )
        self.assertIsNone(
            controller.plan(
                self.profile,
                {"bovis-lair-explored"},
                kind="zone_trigger",
                reference=25602,
            )
        )
        self.assertIsNone(
            controller.plan(
                self.profile,
                set(steps) - {"bovis-mimi-rescued"},
                kind="scenario_complete",
                reference=16159,
            )
        )

    def test_rescue_and_final_capture_require_their_real_separate_victories(self):
        steps = {row["id"]: row for row in self.profile["steps"]}
        rescue = steps["bovis-mimi-rescue-outcome"]
        capture = steps["bovis-capture-outcome"]
        self.assertEqual(rescue["requires"], ["bovis-mimi-rescued"])
        self.assertEqual(steps["bovis-mimi-rescued"]["kind"], "room_victory")
        self.assertEqual(steps["bovis-mimi-rescued"]["reference"], 3)
        self.assertEqual(capture["requires"], ["bovis-boss-defeated"])
        self.assertEqual(steps["bovis-boss-defeated"]["kind"], "room_victory")
        self.assertEqual(steps["bovis-boss-defeated"]["reference"], 4)
        self.assertEqual(
            capture["effects"],
            [dict(kind="quest_objective", quest_id=2720, objective_id=5358)],
        )
        self.assertFalse(
            any(
                effect["kind"] == "reviewed_item_grant"
                for row in self.profile["steps"]
                for effect in row["effects"]
            )
        )

    def test_mimi_admission_is_exactly_scoped_to_original_team_and_bovis(self):
        character = dict(id=7, account_id=2, map_id=1002, instance_id=99)
        for room, refs in [(3, (3840, 3841)), (4, (3845,))]:
            members = [
                dict(id=-100 - index, ref=ref, x=index, y=0, z=0)
                for index, ref in enumerate(refs)
            ]
            admission = combat_mission_allies.admit(
                character, members, policy=combat_mission_allies.BOVIS_POLICY, room=room
            )
            policy = combat_mission_allies.validate(admission, character, members)
            self.assertEqual(policy["helpers"], (("mimi", 3854, 25, "player", "self"),))
            changed = deepcopy(members)
            changed[0]["ref"] = 735
            with self.assertRaises(ValueError):
                combat_mission_allies.validate(admission, character, changed)
        with self.assertRaises(ValueError):
            combat_mission_allies.admit(
                dict(character, instance_id=0),
                members,
                policy=combat_mission_allies.BOVIS_POLICY,
                room=4,
            )

    def test_level_23_victory_is_an_explicit_existing_combat_archetype(self):
        publication = json.loads(
            (
                ROOT / "achievements/combat_mission_profiles/bovis-level-victory.json"
            ).read_text()
        )
        raw = json.loads(
            (
                Path(__file__).with_name("fixtures") / "native_bovis_story.json"
            ).read_text()
        )
        native = next(row for row in raw if row["d"] == 2710)
        (rule,) = combat_missions.validate(publication, {2710: native})
        self.assertEqual(
            (rule["kind"], rule["minimum_level"], rule["acceptance"]),
            ("victory", 23, "explicit"),
        )
        from wakfu_server.achievements.combat_mission_activation import _level_matches

        self.assertFalse(_level_matches(rule, {"level": 22}))
        self.assertTrue(_level_matches(rule, {"level": 23}))
        self.assertEqual(rule["objective_id"], 5359)

    def test_explicit_altitudes_keep_original_pillar_floor_without_inventing_cells(
        self,
    ):
        from wakfu_server import monsters
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.owned_story_encounters import compile_rooms

        directory = PROFILE.parent
        document = json.loads(
            (directory / "bovis-lair-1002-encounters.json").read_text()
        )
        exploration = json.loads(
            (directory / "bovis-lair-1002.exploration.json").read_text()
        )
        geometry = published_geometry(1002)
        _, topology = compile_rooms(
            document,
            geometry=geometry,
            exploration=exploration,
            monster=monsters.reference,
        )
        cells = {tuple(point) for room in topology for point in room["cells"]}
        native = owned_story_mechanics.sources(self.profile)
        pillars = {
            (int(row["x"]), int(row["y"]), int(row["z"]))
            for row in native["objects"]
            if 25524 <= row["id"] <= 25542
        }
        self.assertEqual(len(pillars), 19)
        self.assertTrue(pillars <= cells)
        self.assertTrue(cells <= set(geometry.cells))
        malformed = deepcopy(document)
        malformed["rooms"][0]["altitudes"] = [0, True]
        with self.assertRaisesRegex(ValueError, "altitude layers"):
            compile_rooms(
                malformed,
                geometry=geometry,
                exploration=exploration,
                monster=monsters.reference,
            )

    def test_native_team_assignment_follows_real_mimi_helper_assembly(self):
        from wakfu_server import monsters
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server.combat_encounter_scene_helpers import (
            prepare_scene_roster,
            validated_manifest,
        )

        rows = json.loads((PROFILE.parent / "bovis-lair-1002.roles.json").read_text())[
            "roles"
        ]
        by_scope = {
            (row["map_id"], tuple(row["monster_references"])): row["policy"]
            for row in rows
        }
        by_policy = {
            row["policy"]: roles.EncounterRoles(
                **dict(
                    {k: v for k, v in row.items() if k != "schema"},
                    monster_references=tuple(row["monster_references"]),
                )
            )
            for row in rows
        }
        character = dict(
            id=7,
            account_id=2,
            level=23,
            breed=19,
            map_id=1002,
            instance_id=99,
            x=31,
            y=-15,
            z=0,
        )
        originals = tuple(
            monsters.owned_instance(
                ref,
                26,
                -100 - index,
                map_id=1002,
                instance_id=99,
                x=34 + index,
                y=-13,
                z=0,
            )
            for index, ref in enumerate((3840, 3841))
        )
        admission = combat_mission_allies.admit(
            character, originals, policy=combat_mission_allies.BOVIS_POLICY, room=3
        )
        with patch.object(
            roles,
            "_active_policy",
            side_effect=lambda map_id, refs: by_scope.get((map_id, refs)),
        ), patch.object(roles, "_version", side_effect=by_policy.__getitem__), patch(
            "wakfu_server.combat_encounter_scene_helpers._cells",
            return_value=[(36, -8, 0)],
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=900
        ):
            roster, manifest = prepare_scene_roster(
                SimpleNamespace(connection=lambda: nullcontext(None)),
                character,
                originals,
                mission_allies=admission,
            )
            self.assertEqual(roster[-1]["ref"], 3854)
            self.assertFalse(
                validated_manifest(manifest)["helpers"][0]["reward_eligible"]
            )
            assigned = roles.role_assignment(1002, [row["ref"] for row in roster])
            self.assertEqual((assigned.player_team, assigned.npc_team), (1, 0))
            self.assertEqual(assigned.monster_references, (3840, 3841, 3854))

    def test_physical_reentry_offer_keeps_exact_native_route_without_progress_grants(
        self,
    ):
        from wakfu_server import generic_transports, owned_physical_offers

        config = json.loads(
            (PROFILE.parent / "bovis-lair-1002.configuration.json").read_text()
        )
        source = generic_transports.source(1134, 25510)
        offer = owned_physical_offers._declaration(config, source)
        self.assertIsNotNone(offer)
        self.assertEqual((offer["source_id"], offer["destination_id"]), (25510, 2260))
        self.assertEqual(offer["label"], "Enter Bovis's Lair")
        changed = deepcopy(config)
        changed["version"] += 1
        self.assertIsNone(owned_physical_offers._declaration(changed, source))
        self.assertIsNone(
            owned_physical_offers._declaration(config, dict(source, id=25511))
        )

    def test_room_one_native_pillars_flow_from_sealed_scene_into_glyph_constructors(
        self,
    ):
        from wakfu_server.combat_encounter_scene_policy import (
            prepare_scene,
            arena_scene,
        )
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            prepare_declared_glyphs,
        )
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_geometry import published_geometry

        encounter_path = PROFILE.parent / "bovis-lair-1002-encounters.json"
        room = json.loads(encounter_path.read_text())["rooms"][0]
        descriptor = room["encounter_scene"]
        geometry = published_geometry(1002)
        room_cells = tuple(geometry.cells)
        scope = dict(
            map_id=1002,
            instance_id=99,
            group_id=288,
            room_order=1,
            policy_version=1,
            route_key="bovis-room-1",
            evidence_hashes={},
        )
        record = prepare_scene(descriptor, scope=scope, room_cells=room_cells)
        glyph_xy = {
            tuple(row["cell"][:2]) for row in descriptor["native_initial_glyphs"]
        }
        positions, used_xy = [], set(glyph_xy)
        for cell in sorted(room_cells):
            xy = tuple(cell[:2])
            if cell[2] == 0 and xy not in used_xy:
                positions.append(tuple(cell))
                used_xy.add(xy)
            if len(positions) == 5:
                break
        self.assertEqual(len(positions), 5)
        character = dict(
            id=7,
            account_id=2,
            map_id=1002,
            instance_id=99,
            x=positions[0][0],
            y=positions[0][1],
            z=positions[0][2],
        )
        members = [
            dict(
                id=-7 - index,
                ref=ref,
                x=positions[index + 1][0],
                y=positions[index + 1][1],
                z=positions[index + 1][2],
            )
            for index, ref in enumerate((3774, 3774, 3234, 3234))
        ]
        selected = dict(
            map_id=1002,
            instance_id=99,
            validated_cells=list(room_cells),
            native_border_cells=(),
        )
        attached = arena_scene(record, selected, character, members)
        self.assertEqual(len(attached["native_initial_glyphs"]), 4)
        self.assertEqual(
            attached["native_initial_glyph_policy"], descriptor["policy_id"]
        )
        self.assertEqual(
            attached["native_initial_glyph_authority"], descriptor["authority"]
        )
        self.assertEqual(
            attached["native_initial_glyph_source_url"], descriptor["source_uri"]
        )

        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        catalog = native_actor_catalog()
        radius = catalog["default_actor_radius"]
        actors = [Actor(7, 0, positions[0], 100, 6, 3, 10, 20)]
        actors[0].controlled = True
        actors[0].physical_radius = radius
        for member, level in zip(members, (16, 16, 12, 12)):
            profile = catalog["npc_profiles"][str(member["ref"])]
            actor = Actor(
                member["id"],
                1,
                tuple(member[k] for k in ("x", "y", "z")),
                100,
                6,
                3,
                10,
                level,
            )
            actor.controlled = False
            actor.physical_radius = profile["physical_radius"]
            actors.append(actor)
        fight = Fight(
            100,
            actors,
            set(room_cells),
            {
                0: {positions[0]},
                1: {tuple(member[k] for k in ("x", "y", "z")) for member in members},
            },
        )
        role_record = SimpleNamespace(
            map_id=1002,
            player_team=0,
            npc_team=1,
            monster_references=(3234, 3234, 3774, 3774),
        )
        with patch(
            "wakfu_server.combat_encounter_roles.assigned_roles",
            return_value=role_record,
        ):
            constructors = prepare_declared_glyphs(
                fight, attached, 1000, native_effect_areas()
            )
        self.assertEqual(
            [row["reference"] for row in constructors],
            [row["reference"] for row in descriptor["native_initial_glyphs"]],
        )
        self.assertTrue(
            all(row["policy"] == descriptor["policy_id"] for row in constructors)
        )
        self.assertTrue(
            all(row["authority"] == descriptor["authority"] for row in constructors)
        )
        self.assertTrue(
            all(row["source_url"] == descriptor["source_uri"] for row in constructors)
        )

        self.assertIs(arena_scene(None, selected, character, members), selected)
        explicit = dict(selected, native_initial_glyph_policy="")
        explicit_attached = arena_scene(record, explicit, character, members)
        self.assertEqual(explicit_attached["native_initial_glyph_policy"], "")
        with self.assertRaises(ValueError):
            prepare_declared_glyphs(
                fight, explicit_attached, 1000, native_effect_areas()
            )
        changed = deepcopy(record)
        changed["descriptor"]["authority"] += " altered"
        with self.assertRaisesRegex(ValueError, "source changed"):
            arena_scene(changed, selected, character, members)


if __name__ == "__main__":
    unittest.main()
