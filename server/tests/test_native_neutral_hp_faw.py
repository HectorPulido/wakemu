"""Pinned scene faW construction reuses native HP/Qf/QI without a fighter."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_encounter_glyph_bootstrap as bootstrap
from wakfu_server import combat_environment_glyphs as environment
from wakfu_server.combat_neutral_faw_hp import SCHEMA, prototype_digest
from wakfu_server.combat_fake_fighter_resources import fake_fighter_hp_state
from wakfu_server.combat_fake_fighter_resources import fake_fighter_hp_resources
from wakfu_server import owned_story_victory_qualification


DEFINITIONS = json.loads(
    (Path(__file__).parent / "fixtures/native_bovis_pillar_prototypes.json").read_text()
)


def declaration(reference=986):
    return dict(
        reference=reference,
        cell=[1, 1, 0],
        level=0,
        neutral_faw_constructor=dict(
            schema=SCHEMA,
            prototype_sha256=prototype_digest(DEFINITIONS[str(reference)]),
        ),
    )


class NeutralHPFawTests(unittest.TestCase):
    def test_actual_beer_barrel_constructor_death_and_story_kill_are_source_qualified(
        self,
    ):
        records = json.loads(
            (
                Path(__file__).parents[1].parent
                / ".runtime/quest-archetypes/wild-beer-native-records.json"
            ).read_text()
        )
        areas = {
            int(row["record_key"]): row["payload"]
            for row in records
            if row["collection"] == "areas"
        }
        effects = {
            int(row["record_key"]): row["payload"]
            for row in records
            if row["collection"] == "effects"
        }
        self.assertEqual(set(areas), {630, 633})
        self.assertEqual(set(effects), {107101, 107102, 107114, 107415})
        constructors = []
        for reference in (630, 633):
            definition = areas[reference]
            request = dict(
                schema="native-neutral-removal-hp-faw-v1",
                prototype_sha256=prototype_digest(definition),
            )
            bootstrap.validate_environment_prototype(
                definition, level=0, neutral_faw_constructor=request
            )
            self.assertEqual(definition["entry_masks"], [10011])
            self.assertEqual(
                fake_fighter_hp_resources(definition, 0)["characteristics"][1][
                    "maximum"
                ],
                100,
            )
            changed = deepcopy(definition)
            changed["raw_bdh"][1] = 99.0
            with self.assertRaises(ValueError):
                bootstrap.validate_environment_prototype(
                    changed, level=0, neutral_faw_constructor=request
                )
            constructors.append(
                dict(
                    uid=reference, reference=reference, neutral_faw_constructor=request
                )
            )

        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime

        # The removal callback accepts only the actual self-targeted, completed
        # constructor; an ordinary removal or a foreign target supplies no cause.
        simple_fight = SimpleNamespace(
            native_environment_glyph_constructors=constructors
        )
        callback = object.__new__(NativeAreaEventRuntime)
        callback.fight = simple_fight
        source = constructors[0]
        barrel = dict(uid=source["uid"], native_qq_bhi=True)
        self.assertTrue(
            callback._reviewed_hp_removal_center(
                barrel, SimpleNamespace(id=source["uid"])
            )
        )
        self.assertFalse(
            callback._reviewed_hp_removal_center(barrel, SimpleNamespace(id=999))
        )
        barrel["native_qq_bhi"] = False
        self.assertFalse(
            callback._reviewed_hp_removal_center(
                barrel, SimpleNamespace(id=source["uid"])
            )
        )

        story = dict(steps=[dict(id="barrel-room", kind="room_victory", reference=1)])
        story["victory_qualification"] = [
            dict(
                room_order=1,
                original_monster_reference=2803,
                native_effect_reference=107114,
                native_area_reference=630,
                evidence="native barrel kill",
            )
        ]
        fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(hp=100, team=0),
                8: SimpleNamespace(hp=0, team=1),
            },
            phase="finished",
            winner=0,
            native_environment_glyph_constructors=constructors,
            events=[
                dict(
                    kind="kill_hp_minimum_update",
                    effect_class=28,
                    generic_effect=107114,
                    source_id=630,
                    target_id=8,
                    hp_before=1,
                    hp=0,
                ),
                dict(kind="death", actor_id=8),
            ],
        )
        roster = [dict(id=8, ref=2803)]
        self.assertTrue(
            owned_story_victory_qualification.qualified(story, fight, 7, roster, 1)
        )
        fight.events[0]["source_id"] = 999
        self.assertFalse(
            owned_story_victory_qualification.qualified(story, fight, 7, roster, 1)
        )

    def test_all_three_original_pillar_constructors_require_the_exact_explicit_pin(
        self,
    ):
        for reference in (986, 987, 988):
            definition = DEFINITIONS[str(reference)]
            request = declaration(reference)["neutral_faw_constructor"]
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError):
                    bootstrap.validate_fake_fighter_prototype(definition, level=0)
                actual = bootstrap.validate_fake_fighter_prototype(
                    definition, level=0, neutral_faw_constructor=request
                )
                self.assertEqual(actual["characteristic_ids"], (1,))
                self.assertTrue(actual["running_effect_manager"])
                self.assertTrue(actual["movement_blocking"])
                changed = deepcopy(definition)
                changed["raw_bdh"][1] = 101.0
                with self.assertRaisesRegex(ValueError, "prototype pin"):
                    bootstrap.validate_fake_fighter_prototype(
                        changed, level=0, neutral_faw_constructor=request
                    )
        for changed in (
            {"schema": SCHEMA},
            dict(schema=SCHEMA, prototype_sha256="0" * 64),
        ):
            with self.assertRaises(ValueError):
                bootstrap.validate_fake_fighter_prototype(
                    DEFINITIONS["986"], level=0, neutral_faw_constructor=changed
                )

    def test_reviewed_pin_cannot_enable_owner_copy_or_other_native_constructor_kinds(
        self,
    ):
        for index, value in ((0, 4.0), (9, 20.0), (5, 0.0), (1, 0.0)):
            definition = deepcopy(DEFINITIONS["986"])
            definition["raw_bdh"][index] = value
            with self.subTest(parameter=index):
                with self.assertRaises(ValueError):
                    bootstrap.validate_fake_fighter_prototype(
                        definition,
                        level=0,
                        neutral_faw_constructor=dict(
                            schema=SCHEMA, prototype_sha256=prototype_digest(definition)
                        ),
                    )
        with self.assertRaises(ValueError):
            bootstrap.validate_fake_fighter_prototype(
                DEFINITIONS["986"],
                level=1,
                neutral_faw_constructor=declaration()["neutral_faw_constructor"],
            )

    def test_actual_bootstrap_has_native_hp_qf_qi_and_does_not_respawn_removed_area(
        self,
    ):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 1, 53)
        actor.physical_radius = 0
        other = Actor(8, 1, (3, 3, 0), 100, 6, 3, 1, 53)
        other.physical_radius = 0
        fight = Fight(
            77,
            [actor, other],
            {(x, y, 0) for x in range(4) for y in range(4)},
            {0: {(0, 0, 0)}, 1: {(3, 3, 0)}},
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[256] * 16
        )
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 0, 8: 0})
        )
        arena = dict(
            native_initial_glyphs=[declaration()],
            native_initial_glyph_policy="wakemu.test.reviewed-neutral-hp.v1",
            native_initial_glyph_authority="reviewed-original-pillar-constructor",
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=DEFINITIONS,
        ), patch("wakfu_server.combat_global_pv_collections.register_global_area"):
            environment.prepare_environment_glyphs(fight, arena, 1000)
            self.assertEqual(
                bootstrap.declared_environment_blockers(
                    arena["native_initial_glyphs"], definitions=DEFINITIONS
                ),
                frozenset({(1, 1, 0)}),
            )
            environment.ensure_environment_glyphs(fight)
            row = fight.native_effect_areas[999]
            self.assertIsNone(row["owner_id"])
            self.assertEqual(row["native_fight_affiliation"], -1)
            self.assertEqual(
                fake_fighter_hp_state(row, DEFINITIONS["986"])["current"], 100
            )
            self.assertEqual(row["state_ledger"].actor_id, 999)
            self.assertGreaterEqual(row["native_obstacle_id"], 0)
            self.assertEqual(row["native_obstacle_source"], "QI.f(QK)")
            environment.verify_environment_glyph(fight, row)
            self.assertEqual(fight.actors[7].hp, 100)
            self.assertEqual(set(fight.actors), {7, 8})
            before = environment.environment_sections(fight)
            self.assertEqual(len(before), 1)
            restored = deepcopy(fight)
            environment.verify_environment_glyph(
                restored, restored.native_effect_areas[999]
            )
            self.assertEqual(environment.environment_sections(restored), before)
            del fight.native_effect_areas[999]
            environment.ensure_environment_glyphs(fight)
            self.assertEqual(fight.native_effect_areas, {})
            self.assertEqual(environment.environment_sections(fight), [])


if __name__ == "__main__":
    unittest.main()
