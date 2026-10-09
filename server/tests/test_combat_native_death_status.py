import unittest
from types import SimpleNamespace

from wakfu_server.combat_native_death_status import (
    initialize_fresh_bje_death_status,
    apply_native_fighter_state_transition,
    native_is_dead,
)


class NativeDeathStatusTests(unittest.TestCase):
    def test_detached_life_query_uses_actual_constructor_pv(self):
        from wakfu_server.combat.combat_summon_initialization import (
            detached_summon_scope,
            detached_actor_authority,
        )
        from wakfu_server.combat.combat_summon_creation import (
            native_fresh_summon_authority,
        )
        from wakfu_server.combat.combat_condition_life import registered_life_predicate
        from wakfu_server.combat.combat_state_ledger import StateLedger

        actor = SimpleNamespace(
            id=901,
            effective_level=20,
            team=-1,
            native_controlled_by_ai=False,
            native_world_properties=frozenset(),
            state_ledger=StateLedger(901),
        )
        initialize_fresh_bje_death_status(actor)
        fight = SimpleNamespace(actors={})
        authority = native_fresh_summon_authority(actor, 3798)
        with detached_summon_scope(fight, actor, authority):
            self.assertFalse(
                registered_life_predicate(
                    fight, detached_actor_authority, "IsDead", actor.id
                )
            )
            self.assertFalse(
                registered_life_predicate(
                    fight, detached_actor_authority, "IsInPlay", actor.id
                )
            )
            self.assertEqual(fight.actors, {})

    def test_native_writes_are_independent_of_hp_and_participation(self):
        actor = SimpleNamespace(hp=0, native_world_properties=frozenset())
        initialize_fresh_bje_death_status(actor)
        self.assertFalse(native_is_dead(actor))
        apply_native_fighter_state_transition(actor, 0)
        self.assertFalse(native_is_dead(actor))
        apply_native_fighter_state_transition(actor, 2)
        self.assertTrue(native_is_dead(actor))
        actor.hp = 60
        apply_native_fighter_state_transition(actor, 3)
        self.assertTrue(native_is_dead(actor))
        apply_native_fighter_state_transition(actor, 1)
        self.assertFalse(native_is_dead(actor))

    def test_world_dead_namespace_and_missing_components(self):
        actor = SimpleNamespace(native_world_properties=frozenset())
        self.assertIsNone(native_is_dead(actor))
        actor.native_world_properties = frozenset({19})
        self.assertTrue(native_is_dead(actor))
        actor.native_world_properties = frozenset()
        initialize_fresh_bje_death_status(actor)
        actor.native_fight_properties = frozenset({19})
        self.assertFalse(native_is_dead(actor))
        actor.native_world_properties = frozenset({19})
        self.assertTrue(native_is_dead(actor))
        apply_native_fighter_state_transition(actor, 2)
        self.assertFalse(actor.native_death_status["mwD"])
        actor.native_world_properties = frozenset()
        self.assertFalse(native_is_dead(actor))

    def test_gg_guard_does_not_invent_unknown_legacy_components(self):
        actor = SimpleNamespace()
        apply_native_fighter_state_transition(actor, 2)
        self.assertIsNone(native_is_dead(actor))
        self.assertIsNone(actor.native_death_status["mwD"])
        apply_native_fighter_state_transition(actor, 1)
        self.assertFalse(actor.native_death_status["mwD"])
        self.assertIsNone(native_is_dead(actor))

    def test_complete_registered_count_uses_current_native_status(self):
        from wakfu_server.combat.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat.combat_summon_count import registered_summon_counts

        owner = SimpleNamespace(id=7)
        summon = SimpleNamespace(
            id=901,
            native_world_properties=frozenset(),
            native_fight_properties=frozenset(),
            native_controller_id=7,
        )
        initialize_fresh_bje_death_status(summon)
        fight = SimpleNamespace(actors={7: owner, 901: summon})
        initialize_global_pv_collections(fight, (7, 901))
        records = {
            901: {
                "controller_id": 7,
                "authority": {
                    "targeting": {"is_eGj": True, "dTE": True},
                    "breed_id": 3798,
                },
            }
        }
        ordinary = lambda view, actor: SimpleNamespace(
            targeting={"is_eGj": True, "dTE": False}
        )
        self.assertEqual(
            registered_summon_counts(fight, 7, records, ordinary, fight), (1, {3798: 1})
        )
        self.assertEqual(
            registered_summon_counts(fight, 8, records, ordinary, fight), (0, {})
        )
        summon.native_controller_id = 8
        self.assertIsNone(registered_summon_counts(fight, 7, records, ordinary, fight))
        summon.native_controller_id = 7
        from wakfu_server.combat.combat_global_pv_collections import (
            set_global_fighter_status,
        )

        set_global_fighter_status(fight, 901, "OUT_OF_PLAY")
        self.assertEqual(
            registered_summon_counts(fight, 7, records, ordinary, fight), (0, {})
        )
        set_global_fighter_status(fight, 901, "OFF_PLAY")
        self.assertEqual(
            registered_summon_counts(fight, 7, records, ordinary, fight), (1, {3798: 1})
        )
        summon.native_fight_properties = frozenset({103})
        self.assertEqual(
            registered_summon_counts(fight, 7, records, ordinary, fight), (0, {})
        )
        summon.native_fight_properties = frozenset()
        apply_native_fighter_state_transition(summon, 2)
        self.assertEqual(
            registered_summon_counts(fight, 7, records, ordinary, fight), (0, {})
        )
