"""Source-bound box-goal settlement and scripted native-entry validation."""

from copy import deepcopy
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat.combat_scene_box_goals import (
    declaration,
    passive_admission,
    qualified_result,
    settle_cast,
)
from wakfu_server import owned_story_generic_entry


class SceneBoxGoalsTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = dict(
            full_room_scope=True,
            box_goals=dict(
                schema="owned-box-goals-v1",
                box_reference=3889,
                goal_area_reference=1020,
                goals=[[2, 0, 0], [3, 0, 0]],
                spell_ids=[9011],
                evidence="reviewed native box goal cells",
            ),
            native_initial_glyphs=[
                dict(reference=1020, cell=[2, 0, 0], level=0),
                dict(reference=1020, cell=[3, 0, 0], level=0),
            ],
        )

    def fight(self, *, positions=((2, 0, 0), (3, 0, 0)), caster=None):
        hero = caster or SimpleNamespace(
            id=7,
            controlled=True,
            owner_id=19,
            team=0,
            hp=100,
            is_summon=False,
            native_summon_source=None,
        )
        boxes = [
            SimpleNamespace(
                id=-11, controlled=False, team=1, hp=0, position=tuple(positions[0])
            ),
            SimpleNamespace(
                id=-12, controlled=False, team=1, hp=0, position=tuple(positions[1])
            ),
        ]
        record = dict(
            descriptor=deepcopy(self.descriptor),
            room_cells={(x, 0, 0) for x in range(6)},
            sha256="a" * 64,
            scope=dict(
                actor_bindings=[dict(actor_id=box.id, ref=3889) for box in boxes]
            ),
        )
        events = []
        sequence = 1
        for index, box in enumerate(boxes):
            events.extend(
                [
                    dict(
                        kind="state_removed",
                        sequence=sequence,
                        actor_id=box.id,
                        uid=100 + index,
                        reference=4062,
                        source="decurse321",
                    ),
                    dict(
                        kind="kill_hp_minimum_update",
                        sequence=sequence + 1,
                        effect_class=28,
                        generic_effect=173367,
                        native_container=dict(
                            present=True, type=1, is_state=True, state_id=4062
                        ),
                        uid=200 + index,
                        source_id=hero.id,
                        target_id=box.id,
                        hp_before=1,
                        hp=0,
                        minimum=0,
                    ),
                    dict(kind="death", sequence=sequence + 2, actor_id=box.id),
                ]
            )
            sequence += 3
        fight = SimpleNamespace(
            native_encounter_scene=record,
            actors={hero.id: hero, **{box.id: box for box in boxes}},
            phase="finished",
            winner=0,
            events=events,
            _in_play=lambda actor: actor.hp > 0,
        )
        fight._event = lambda kind, **fields: fight.events.append(
            dict(kind=kind, **fields)
        )
        return fight, hero, boxes

    def settle(self, fight, hero, *, spell=9011):
        roles = SimpleNamespace(player_team=0, npc_team=1)
        with patch(
            "wakfu_server.combat.combat_scene_box_goals._goal_areas",
            return_value=[9001, 9002],
        ), patch(
            "wakfu_server.combat.combat_encounter_scene_policy.frozen_scene",
            return_value=self.descriptor,
        ), patch(
            "wakfu_server.combat_encounter_roles.assigned_roles", return_value=roles
        ):
            return settle_cast(fight, caster_id=hero.id, spell_id=spell, action_id=44)

    def test_native_goal_deaths_are_observed_once_without_manufacturing_terminal_state(
        self,
    ):
        fight, hero, boxes = self.fight()
        before = (fight.phase, fight.winner, deepcopy(fight.events))
        self.assertTrue(self.settle(fight, hero))
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, 0)
        self.assertEqual(fight.native_box_goal_receipt["schema"], "owned-box-goals-v1")
        self.assertEqual(fight.native_box_goal_receipt["spell_id"], 9011)
        self.assertEqual(fight.native_box_goal_receipt["action_id"], 44)
        self.assertEqual(
            {
                row["generic_effect"]
                for row in fight.native_box_goal_receipt["native_goal_deaths"]
            },
            {173367},
        )
        self.assertEqual((fight.phase, fight.winner, fight.events), before)
        self.assertFalse(self.settle(fight, hero))
        self.assertEqual((fight.phase, fight.winner, fight.events), before)

    def test_wrong_spell_caster_box_roster_or_unreached_goals_cannot_win(self):
        wrong_spell, hero, _ = self.fight()
        self.assertFalse(self.settle(wrong_spell, hero, spell=9022))
        self.assertEqual(wrong_spell.phase, "finished")

        no_owner, hero, _ = self.fight(
            caster=SimpleNamespace(
                id=7,
                controlled=True,
                owner_id=None,
                team=0,
                hp=100,
                is_summon=False,
                native_summon_source=None,
            )
        )
        self.assertFalse(self.settle(no_owner, hero))

        dead_caster, hero, _ = self.fight(
            caster=SimpleNamespace(
                id=7,
                controlled=True,
                owner_id=19,
                team=0,
                hp=0,
                is_summon=False,
                native_summon_source=None,
            )
        )
        self.assertFalse(self.settle(dead_caster, hero))

        not_solved, hero, _ = self.fight(positions=((1, 0, 0), (3, 0, 0)))
        self.assertFalse(self.settle(not_solved, hero))
        self.assertEqual(not_solved.phase, "finished")

        missing_native_death, hero, _ = self.fight()
        missing_native_death.events = []
        with self.assertRaisesRegex(ValueError, "no owned corpse registration"):
            self.settle(missing_native_death, hero)

        wrong_causal_effect, hero, _ = self.fight()
        wrong_causal_effect.events[1]["generic_effect"] = 999999
        with self.assertRaisesRegex(ValueError, "native state-removal death"):
            self.settle(wrong_causal_effect, hero)

        missing_binding, hero, _ = self.fight()
        missing_binding.native_encounter_scene["scope"]["actor_bindings"].pop()
        with self.assertRaisesRegex(ValueError, "exact original box roster"):
            self.settle(missing_binding, hero)

        missing_actor, hero, _ = self.fight()
        del missing_actor.actors[-12]
        with self.assertRaisesRegex(ValueError, "lost an original box identity"):
            self.settle(missing_actor, hero)

    def test_declaration_rejects_goals_outside_frozen_room(self):
        self.assertIs(
            declaration(self.descriptor, [(2, 0, 0), (3, 0, 0)]),
            self.descriptor["box_goals"],
        )
        with self.assertRaisesRegex(ValueError, "leave their actual native board"):
            declaration(self.descriptor, [(2, 0, 0)])

    def test_passive_admission_uses_exact_native_constructor_and_goal_glyphs(self):
        from wakfu_server.combat.combat_scene_box_goals import _native_constructors

        source = _native_constructors()["3889"]
        descriptor = deepcopy(self.descriptor)
        descriptor["box_goals"]["box_reference"] = 3889
        descriptor["state_programs"] = [
            dict(
                target_references=[3889],
                state_id=4062,
                level=1,
                protected=False,
                source_sha256=source["state_source_sha256"],
            )
        ]
        configuration = dict(
            topology=dict(
                rooms=[
                    dict(
                        order=1,
                        cells=[(2, 0, 0), (3, 0, 0)],
                        encounter_scene=descriptor,
                    )
                ]
            )
        )
        native = dict(
            ref=3889,
            native_abilities=[],
            min_level=1,
            max_level=1,
            statistics={
                "HP": {"base": 1},
                "AP": {"base": 0},
                "MP": {"base": 0},
                "WP": {"base": 0},
            },
        )
        properties = {
            key: source[key] for key in ("fight_properties", "world_properties")
        }
        with patch(
            "wakfu_server.combat.combat_ordinary_authority.native_property_catalog",
            return_value={"npc": {"3889": properties}},
        ), patch(
            "wakfu_server.spell_audit.states_catalog",
            return_value={"states": {}, "effects": {}},
        ), patch(
            "wakfu_server.combat.combat_encounter_scene_states.native_state_source_digest",
            return_value=source["state_source_sha256"],
        ):
            self.assertTrue(passive_admission(configuration, 1, 3889, 1, native))
            self.assertFalse(passive_admission(configuration, 1, 3888, 1, native))
            changed_native = deepcopy(native)
            changed_native["statistics"]["HP"]["base"] = 2
            with self.assertRaisesRegex(ValueError, "constructor authority"):
                passive_admission(configuration, 1, 3889, 1, changed_native)
            missing_glyph = deepcopy(configuration)
            missing_glyph["topology"]["rooms"][0]["encounter_scene"][
                "native_initial_glyphs"
            ].pop()
            with self.assertRaisesRegex(ValueError, "original native goal glyphs"):
                passive_admission(missing_glyph, 1, 3889, 1, native)
            wrong_state = deepcopy(configuration)
            wrong_state["topology"]["rooms"][0]["encounter_scene"]["state_programs"][0][
                "source_sha256"
            ] = ("f" * 64)
            with self.assertRaisesRegex(ValueError, "constructor authority"):
                passive_admission(wrong_state, 1, 3889, 1, native)

    def test_result_requires_the_sealed_receipt_original_roster_and_native_death_causality(
        self,
    ):
        fight, hero, boxes = self.fight()
        self.assertTrue(self.settle(fight, hero))
        originals = [dict(id=box.id, ref=3889) for box in boxes]
        roles = SimpleNamespace(player_team=0, npc_team=1)
        with patch(
            "wakfu_server.combat.combat_scene_box_goals._goal_areas",
            return_value=[9001, 9002],
        ), patch(
            "wakfu_server.combat.combat_encounter_scene_policy.frozen_scene",
            return_value=self.descriptor,
        ), patch(
            "wakfu_server.combat_encounter_roles.assigned_roles", return_value=roles
        ):
            self.assertTrue(qualified_result(fight, originals))
            self.assertFalse(qualified_result(SimpleNamespace(), originals))

            missing_receipt, caster, _ = self.fight()
            missing_receipt.phase, missing_receipt.winner = "finished", 0
            with self.assertRaisesRegex(ValueError, "authenticated native scene"):
                qualified_result(missing_receipt, originals)

            wrong_roster, caster, _ = self.fight()
            self.settle(wrong_roster, caster)
            with self.assertRaisesRegex(ValueError, "authenticated native scene"):
                qualified_result(wrong_roster, originals[:1])

            bad_goal, caster, bad_boxes = self.fight()
            self.settle(bad_goal, caster)
            bad_goal.native_box_goal_receipt["boxes"][0]["cell"] = [1, 0, 0]
            with self.assertRaisesRegex(ValueError, "goal occupants"):
                qualified_result(
                    bad_goal, [dict(id=box.id, ref=3889) for box in bad_boxes]
                )

            live_box, caster, dead_boxes = self.fight()
            self.settle(live_box, caster)
            dead_boxes[0].hp = 1
            with self.assertRaisesRegex(ValueError, "goal occupants"):
                qualified_result(
                    live_box, [dict(id=box.id, ref=3889) for box in dead_boxes]
                )

            moved_box, caster, moved_boxes = self.fight()
            self.settle(moved_box, caster)
            moved_boxes[0].position = (1, 0, 0)
            with self.assertRaisesRegex(ValueError, "goal occupants"):
                qualified_result(
                    moved_box, [dict(id=box.id, ref=3889) for box in moved_boxes]
                )

            changed_death, caster, death_boxes = self.fight()
            self.settle(changed_death, caster)
            changed_death.events[1]["generic_effect"] = 999999
            with self.assertRaisesRegex(ValueError, "native state-removal death"):
                qualified_result(
                    changed_death, [dict(id=box.id, ref=3889) for box in death_boxes]
                )


class ScriptedNativeGenericEntryTests(unittest.TestCase):
    def entry(self):
        source = dict(
            map_id=946,
            id=25104,
            type="GenericActivableInteractiveElement",
            x=10,
            y=2,
            z=0,
            chunk="0_0",
            auto=False,
            payload_hex=(bytes(33) + struct.pack(">i", 3) + b"946").hex(),
            native_parameters="946",
        )
        effect = dict(
            action_reference=2170,
            effect_type=1,
            criterion="IsAchievementRunning(2536)",
            parameters=[],
        )
        group = dict(
            cod=0,
            coe=0,
            cof=False,
            cnd=0,
            cog=0,
            actions=[
                dict(
                    wire_action=0,
                    raw_cob=1.0,
                    effects=[effect],
                )
            ],
        )
        entry = dict(
            kind="native_generic_choice",
            source=source,
            program=dict(descriptor_id=946, groups=[group]),
            wire_action=0,
            effect_reference=2170,
            approaches=[[10, 3, 0]],
            evidence="reviewed script entry on native source",
            scripted_trial=dict(
                schema="owned-native-script-entry-v1",
                map_id=946,
                arrival=[0, 0, 0],
                direction=3,
                evidence="reviewed private scene join",
            ),
        )
        return entry

    def test_scripted_entry_accepts_only_pinned_native_type_one_zero_argument_join(
        self,
    ):
        entry = self.entry()
        world = SimpleNamespace(objects=lambda _map_id: [entry["source"]])
        with patch.dict(
            sys.modules, {"wakfu_server.world_static": world}
        ), patch.object(
            owned_story_generic_entry,
            "validate_approaches",
            return_value=frozenset({(10, 3, 0)}),
        ):
            (
                source,
                group,
                action,
                effect,
                target,
                direction,
            ) = owned_story_generic_entry.validate_entry(entry, cells=[[0, 0, 0]])
        self.assertEqual(
            (source["id"], group["cnd"], action["wire_action"], effect["effect_type"]),
            (25104, 0, 0, 1),
        )
        self.assertEqual(target, dict(map_id=946, x=0, y=0, z=0))
        self.assertEqual(direction, 3)

        ordinary = self.entry()
        ordinary.pop("scripted_trial")
        ordinary["program"]["groups"][0]["actions"][0]["effects"][0].update(
            effect_type=3, parameters=["{0,0,0}", "946", "1"]
        )
        world = SimpleNamespace(objects=lambda _map_id: [ordinary["source"]])
        with patch.dict(
            sys.modules, {"wakfu_server.world_static": world}
        ), patch.object(
            owned_story_generic_entry,
            "validate_approaches",
            return_value=frozenset({(10, 3, 0)}),
        ), patch(
            "wakfu_server.exploration_artifact_actions._teleport",
            return_value=(
                dict(map_id=946, x=0, y=0, z=0),
                3,
                0,
            ),
        ):
            (
                _source,
                _group,
                _action,
                effect,
                target,
                _direction,
            ) = owned_story_generic_entry.validate_entry(ordinary, cells=[[0, 0, 0]])
        self.assertEqual(effect["effect_type"], 3)
        self.assertEqual(target["map_id"], 946)

    def test_scripted_join_rejects_forged_source_program_and_off_terrain_arrival(self):
        for mutation in ("source", "program", "terrain", "parameters"):
            entry = self.entry()
            if mutation == "source":
                entry["source"]["id"] += 1
            elif mutation == "program":
                entry["program"]["groups"][0]["actions"][0]["effects"][0][
                    "effect_type"
                ] = 3
            elif mutation == "terrain":
                entry["scripted_trial"]["arrival"] = [1, 0, 0]
            else:
                entry["program"]["groups"][0]["actions"][0]["effects"][0][
                    "parameters"
                ] = ["fake"]
            with self.subTest(mutation=mutation):
                world = SimpleNamespace(
                    objects=lambda _map_id: [self.entry()["source"]]
                )
                with patch.dict(
                    sys.modules, {"wakfu_server.world_static": world}
                ), patch.object(
                    owned_story_generic_entry,
                    "validate_approaches",
                    return_value=frozenset({(10, 3, 0)}),
                ):
                    with self.assertRaises(ValueError):
                        owned_story_generic_entry.validate_entry(
                            entry, cells=[[0, 0, 0]]
                        )


if __name__ == "__main__":
    unittest.main()
