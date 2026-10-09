"""Shared constructor hooks preserve307 while separating captured324 inputs."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_summon_creation import NativeSummonBuilder


class CapturedBuilderHookTests(unittest.TestCase):
    def build(self, creation_properties=None):
        order = []

        class Authority:
            def __call__(self, fight, actor):
                return SimpleNamespace(summon_root_id=7, native_instance_id=1)

            def world_properties(self, fight, actor):
                return frozenset({47})

        preview = SimpleNamespace(
            actors={7: SimpleNamespace(owner_id=3, controlled=True)}
        )
        spec = SimpleNamespace(
            reference=999, level=20, team=0, direction=6, self_controlled=False
        )
        values = {
            key: {"current": value, "maximum": value}
            for key, value in ((1, 60), (2, 6), (3, 3), (4, 6), (35, 10))
        }
        profiles = {"999": {"abilities": []}}

        def initialize(fight, actor, plan):
            self.assertFalse(hasattr(actor, "native_controller_id"))
            self.assertEqual(actor.native_fight_property_counts, {})
            actor.native_fight_property_counts[41] = 2
            order.append("initial")

        def descriptor(fight, actor, specification, caster):
            self.assertEqual(actor.native_fight_property_counts, {41: 2})
            self.assertEqual(actor.native_world_properties, frozenset({5}))
            self.assertFalse(hasattr(actor, "native_controller_id"))
            self.assertFalse(actor.native_summoned_from_symbiot)
            order.append("descriptor")

        builder = NativeSummonBuilder(
            Authority(),
            characteristics={},
            properties={
                "npc": {"999": {"fight_properties": [41], "world_properties": [5]}}
            },
            initial_states={"999": {"initial_state_triples": [1304, -1, 1]}},
            initialize_states=initialize,
            ability_profiles=profiles,
            descriptor_initializer=descriptor,
        )
        with patch(
            "wakfu_server.combat_summon_creation.native_npc_creation_values",
            return_value=values,
        ), patch(
            "wakfu_server.combat_summon_creation.build_npc_snapshot",
            return_value=SimpleNamespace(install=lambda actor: None),
        ), patch(
            "wakfu_server.combat_summon_spellbook.fresh_action_book",
            return_value={"profile": 999, "actions": []},
        ) as book, patch(
            "wakfu_server.combat_summon_creation.register_fresh_summon_obstacle",
            side_effect=lambda fight, actor: setattr(actor, "native_obstacle_id", 1),
        ):
            actor, registration = builder(
                preview,
                spec,
                7,
                901,
                (1, 0, 0),
                creation_properties=creation_properties,
            )
        self.assertEqual(book.call_args.kwargs["profiles"], profiles)
        self.assertEqual(order, ["initial", "descriptor"])
        self.assertEqual(actor.native_world_properties, frozenset({5, 47}))
        return actor, registration

    def test_default307_profile_counter_increment_preserved(self):
        actor, registration = self.build()
        self.assertEqual(actor.native_fight_property_counts, {41: 3})
        self.assertEqual(registration.fight_properties, frozenset({41}))

    def test_captured_null_eHN_skips_extra_increment_not_initial_state(self):
        actor, registration = self.build(())
        self.assertEqual(actor.native_fight_property_counts, {41: 2})
        self.assertEqual(registration.fight_properties, frozenset())


if __name__ == "__main__":
    unittest.main()
