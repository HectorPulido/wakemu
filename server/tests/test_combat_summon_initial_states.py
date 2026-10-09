import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_summon_initial_states import initial_state_plan
from wakfu_server import native_catalog


class SummonInitialStateTests(unittest.TestCase):
    @staticmethod
    def detached_pair(identity=901):
        from wakfu_server.combat.combat_state import Actor
        from wakfu_server.combat.combat_summon_creation import (
            native_fresh_summon_authority,
        )

        actor = Actor(identity, 0, (3, 4, 0), 40, 6, 3, 0, 20)
        actor.team = -1  # Actual pre-registration construction phase.
        actor.native_summon_action_book = {"profile": 3798, "actions": []}
        actor.native_fight_property_counts = {0: 1}
        return actor, native_fresh_summon_authority(actor, 3798)

    def test_builder_initializes_detached_before_profile_counters_and_control(self):
        from wakfu_server.combat.combat_summon_creation import NativeSummonBuilder

        parent = SimpleNamespace(summon_root_id=7, native_instance_id=1)

        class Authority:
            def __call__(self, fight, actor):
                return parent

            def world_properties(self, fight, actor):
                return frozenset({47})

        caster = SimpleNamespace(owner_id=3, controlled=True)
        fight = SimpleNamespace(actors={7: caster})
        specification = SimpleNamespace(
            reference=999, level=20, team=0, direction=6, self_controlled=False
        )
        values = {
            key: {"current": value, "maximum": value}
            for key, value in ((1, 60), (2, 6), (3, 3), (4, 6), (35, 10))
        }

        def initialize(preview, actor, plan):
            self.assertIs(preview, fight)
            self.assertNotIn(actor.id, preview.actors)
            self.assertEqual(actor.team, -1)
            self.assertEqual(actor.native_fight_property_counts, {})
            self.assertEqual(actor.native_world_properties, frozenset({5}))
            self.assertFalse(actor.native_summoned_from_symbiot)
            self.assertFalse(hasattr(actor, "native_controller_id"))
            self.assertIn(actor.native_obstacle_id, (None, -1))
            self.assertEqual(plan[0].level, 20)
            actor.native_fight_property_counts[41] = 2
            actor.native_fight_property_counts[21] = 1

        builder = NativeSummonBuilder(
            Authority(),
            characteristics={},
            properties={
                "npc": {"999": {"fight_properties": [41], "world_properties": [5]}}
            },
            initial_states={"999": {"initial_state_triples": [1304, -1, 1]}},
            initialize_states=initialize,
        )
        with patch(
            "wakfu_server.combat.combat_summon_creation.native_npc_creation_values",
            return_value=values,
        ), patch(
            "wakfu_server.combat.combat_summon_creation.build_npc_snapshot",
            return_value=SimpleNamespace(install=lambda actor: None),
        ), patch(
            "wakfu_server.combat.combat_summon_spellbook.fresh_action_book",
            return_value={"profile": 999, "actions": []},
        ), patch(
            "wakfu_server.combat.combat_summon_creation.register_fresh_summon_obstacle",
            side_effect=lambda preview, actor: setattr(actor, "native_obstacle_id", 1),
        ):
            actor, registration = builder(fight, specification, 7, 901, (1, 0, 0))
        self.assertEqual(actor.team, 0)
        self.assertEqual(actor.native_controller_id, 7)
        self.assertEqual(actor.native_fight_property_counts, {41: 3, 21: 1})
        self.assertTrue(registration.authority.targeting["UNTARGETTABLE_BY_OTHER"])
        self.assertFalse(registration.authority.native_summoned_from_symbiot)
        self.assertEqual(
            actor.native_summon_source["native_symbiot_source"], "eZl.new_eHD.pRO_false"
        )
        self.assertEqual(actor.native_world_properties, frozenset({5, 47}))

    def test_detached_constructor_uses_self_relations_and_off_play(self):
        from wakfu_server.combat.combat_summon_creation import (
            native_fresh_summon_authority,
        )

        actor = SimpleNamespace(
            id=901, effective_level=20, native_controlled_by_ai=False
        )
        authority = native_fresh_summon_authority(actor, 3798)
        self.assertEqual(authority.targeting["bcN"], -1)
        self.assertEqual(authority.targeting["dpu_id"], actor.id)
        self.assertEqual(authority.targeting["dpr_id"], actor.id)
        self.assertFalse(authority.targeting["baF"])
        self.assertTrue(authority.targeting["dTE"])
        self.assertFalse(authority.targeting["UNTARGETTABLE_BY_OTHER"])
        self.assertFalse(authority.native_in_play)
        self.assertEqual(authority.native_controller_id, actor.id)
        self.assertIsNone(authority.native_instance_id)
        self.assertFalse(authority.native_summoned_from_symbiot)

    def test_all_class_profiles_all_supported_descriptor_levels(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "protocol"
            / "native-class-summon-initial-states.json"
        )
        profiles = json.loads(native_catalog.read_text(path))["profiles"]
        self.assertEqual(len(profiles), 39)
        self.assertEqual(
            sum(bool(row["initial_state_triples"]) for row in profiles.values()), 6
        )
        for row in profiles.values():
            raw = row["initial_state_triples"]
            for level in range(246):
                plan = initial_state_plan(raw, level)
                self.assertEqual(len(plan), len(raw) // 3)
                for index, item in enumerate(plan):
                    self.assertEqual(item.state_id, raw[index * 3])
                    self.assertEqual(
                        item.level,
                        level if raw[index * 3 + 1] == -1 else raw[index * 3 + 1],
                    )
                    self.assertEqual(item.native_rBq, raw[index * 3 + 2] == 0)
                    self.assertTrue(item.native_rBr)

    def test_native_flag_zero_is_distinct_from_negative_and_positive(self):
        plan = initial_state_plan([1, -1, 0, 2, 10, -1, 3, 10, 1], 245)
        self.assertEqual([item.native_rBq for item in plan], [True, False, False])
        self.assertEqual([item.level for item in plan], [245, 10, 10])

    def test_rejects_incomplete_or_untyped_native_rows(self):
        for row in ([1, 2], [1, 2, True], [1, 32768, 0], None):
            with self.assertRaises(ValueError):
                initial_state_plan(row, 20)

    def test_initializer_failure_resets_scope_without_roster_or_qi_mutation(self):
        from wakfu_server.combat.combat_summon_initialization import (
            detached_actor,
            detached_actors,
            summon_initializer,
        )

        actor, _ = self.detached_pair()
        qi_slots = object()
        fight = SimpleNamespace(actors={7: object()}, native_qi_slots=qi_slots)
        roster_before = dict(fight.actors)

        def failing_runtime(preview, _context):
            self.assertIs(preview, fight)
            self.assertIs(detached_actor(fight, actor.id), actor)
            self.assertEqual(detached_actors(fight), (actor,))
            raise RuntimeError("initializer failed after detached lookup")

        initialize = summon_initializer(failing_runtime, [])
        with self.assertRaisesRegex(RuntimeError, "initializer failed"):
            initialize(fight, actor, ())

        self.assertIsNone(detached_actor(fight, actor.id))
        self.assertEqual(detached_actors(fight), ())
        self.assertEqual(fight.actors, roster_before)
        self.assertNotIn(actor.id, fight.actors)
        self.assertIs(fight.native_qi_slots, qi_slots)

    def test_nested_detached_scopes_restore_previous_fight_actor_and_authority(self):
        from wakfu_server.combat.combat_summon_initialization import (
            detached_actor,
            detached_actor_authority,
            detached_actors,
            detached_summon_scope,
        )

        actor_a, authority_a = self.detached_pair(901)
        actor_b, authority_b = self.detached_pair(902)
        actor_other_fight, authority_other_fight = self.detached_pair(901)
        fight_a = SimpleNamespace(actors={})
        fight_b = SimpleNamespace(actors={})

        with detached_summon_scope(fight_a, actor_a, authority_a):
            self.assertIs(detached_actor(fight_a, 901), actor_a)
            self.assertIs(detached_actor_authority(fight_a, actor_a), authority_a)
            with detached_summon_scope(fight_a, actor_b, authority_b):
                self.assertEqual(detached_actors(fight_a), (actor_a, actor_b))
                self.assertIs(detached_actor(fight_a, 901), actor_a)
                self.assertIs(detached_actor(fight_a, 902), actor_b)
                with detached_summon_scope(
                    fight_b, actor_other_fight, authority_other_fight
                ):
                    self.assertIs(detached_actor(fight_b, 901), actor_other_fight)
                    self.assertIs(detached_actor(fight_a, 901), actor_a)
            self.assertEqual(detached_actors(fight_a), (actor_a,))
            self.assertIs(detached_actor(fight_a, 902), None)

        self.assertEqual(detached_actors(fight_a), ())
        self.assertEqual(detached_actors(fight_b), ())
        self.assertIsNone(detached_actor(fight_a, 901))

    def test_detached_property_counts_use_actual_actor_and_reject_incomplete_pb(self):
        from wakfu_server.combat.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat.combat_summon_initialization import (
            detached_summon_scope,
        )

        actor, authority = self.detached_pair()
        fight = SimpleNamespace(actors={}, events=[])
        composed = RegisteredSummonAuthority(object())

        with detached_summon_scope(fight, actor, authority):
            counts = composed.property_counts(fight, actor)
            self.assertIs(counts, actor.native_fight_property_counts)
            counts[70] = 1
            self.assertEqual(actor.native_fight_property_counts[70], 1)

            del actor.native_fight_property_counts
            with self.assertRaisesRegex(ValueError, "Complete native PB"):
                composed.property_counts(fight, actor)

            actor.native_fight_property_counts = {0: True}
            with self.assertRaisesRegex(ValueError, "Complete native PB"):
                composed.property_counts(fight, actor)
