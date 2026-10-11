"""Actual eligible native5347 metadata through shared captured construction."""
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_summon import (
    captured_summon_plan,
    NativeCapturedSummonPipeline,
    mark_captured_origin,
)
from wakfu_server.combat_summon import RegisteredSummonAuthority, fresh_summon_insertion
from wakfu_server.combat_summon_creation import NativeSummonBuilder
from wakfu_server.combat_summon_spellbook import fresh_action_book


class ActualCapturedNativeFixtureTests(unittest.TestCase):
    def test_source_eligible5347_shared_constructor_and_original_book(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/owned-captured-5347-native.json"
            ).read_text()
        )
        profile = fixture["native_profile_export"]["profiles"]["5347"]
        self.assertIn(40, profile["fight_properties"])
        self.assertNotIn(28, profile["fight_properties"])
        self.assertEqual(fixture["native_profile_export"]["native_book_checks"], 15)
        roster = OwnedCapturedRoster(
            42,
            (CapturedCreature(0, 5347, "owned Wonejo"),) + (None,) * 9,
            (True,) + (False,) * 9,
        )
        plan = captured_summon_plan(
            {"effect_class": 324},
            {"parameters": ()},
            roster,
            caster_id=42,
            caster_level=153,
            caster_direction=3,
            caster_team=0,
            allocate_uid=lambda: 901,
        )

        class Authority:
            def __call__(self, fight, actor):
                return SimpleNamespace(summon_root_id=42, native_instance_id=1)

            def world_properties(self, fight, actor):
                return frozenset()

        caster = SimpleNamespace(
            id=42,
            owner_id=3,
            controlled=True,
            native_obstacle_id=0,
            hp=40,
            position=(0, 0, 0),
        )
        preview = SimpleNamespace(
            actors={42: caster},
            phase="active",
            order=[42],
            turn_index=0,
            native_timeline_round=1,
            current=caster,
            walkable={(3, 4, 0)},
        )
        from wakfu_server.combat_timeline_snapshot import initialize

        initialize(preview, preview.order)
        registered = RegisteredSummonAuthority(Authority())
        order = []

        def descriptor(fight, actor, specification, caster):
            # Actual bPq minimum-HP source is1 and current native bound here1.
            self.assertEqual(profile["descriptor_initial_hp"], 1)
            self.assertLessEqual(1, actor.effect_maxima[1])
            actor.effect_stats[1] = actor.hp = 1
            actor.native_captured_name = roster.slots[0].name
            order.append("descriptor")

        builder = NativeSummonBuilder(
            Authority(),
            characteristics=fixture["actor_catalog"],
            properties={"npc": {"5347": profile}},
            initial_states={"5347": profile},
            ability_profiles={"5347": profile},
            descriptor_initializer=descriptor,
        )

        def create(fight, specification, actual_descriptor, **kwargs):
            self.assertEqual(actual_descriptor, profile)
            actor, registration = builder(
                fight,
                specification,
                kwargs["caster_id"],
                kwargs["actor_id"],
                kwargs["cell"],
                creation_properties=(),
            )
            self.assertEqual(registration.fight_properties, frozenset())
            self.assertFalse(actor.native_summoned_from_symbiot)
            timeline, index = fresh_summon_insertion(
                fight,
                specification,
                caster_id=kwargs["caster_id"],
                actor_id=kwargs["actor_id"],
            )
            registered.register(
                fight, actor, registration, new_order=timeline, new_turn_index=index
            )
            return actor

        committed = []

        def scale(actor, main, secondary):
            self.assertEqual((main, secondary), (1.0, 1.0))
            order.append("fan")

        def mark(actor, value):
            self.assertTrue(value)
            mark_captured_origin(preview, actor, plan)
            order.append("lE")

        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=lambda *args, **kwargs: profile,
            create=create,
            scale_characteristics=scale,
            mark_symbiot=mark,
            commit_roster=lambda fight, owned: committed.append(owned),
        )
        with patch(
            "wakfu_server.combat_summon_creation.register_fresh_summon_obstacle",
            side_effect=lambda fight, actor: setattr(actor, "native_obstacle_id", 1),
        ):
            actor = pipeline.execute(plan, roster, preview=preview, cell=(3, 4, 0))
        self.assertEqual(order, ["descriptor", "fan", "lE"])
        self.assertEqual(actor.effective_level, 153)
        self.assertEqual(actor.native_controller_id, 42)
        self.assertEqual(
            actor.native_summon_action_book,
            fresh_action_book(5347, 153, profiles={"5347": profile}),
        )
        self.assertEqual(
            [row["reference"] for row in actor.native_summon_action_book["actions"]],
            [7356, 7357, 7358],
        )
        self.assertTrue(actor.native_summoned_from_symbiot)
        self.assertTrue(
            preview.native_summon_registrations[901]["authority"][
                "native_summoned_from_symbiot"
            ]
        )
        self.assertEqual(preview.order, [42, 901])
        self.assertFalse(committed[0].available[0])
        self.assertEqual(committed[0].free_slots, 9)


if __name__ == "__main__":
    unittest.main()
