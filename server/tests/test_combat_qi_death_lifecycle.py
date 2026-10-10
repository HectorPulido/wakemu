"""Owned OFF_PLAY preserves exact QI slots for subsequent combat actions."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_qi_fight import (
    current_registry,
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
    register_effect_area_obstacle,
)
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
    register_global_fighter,
)
from wakfu_server.combat_casting_context import NativeOwnedCastingContext


class NativeQIDeathLifecycleTests(unittest.TestCase):
    def fight(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 6, 10, 10, owner_id=1, controlled=True)
        first = Actor(-7, 1, (3, 3, 0), 30, 0, 0, 1, 10)
        second = Actor(-8, 1, (3, 1, 0), 30, 0, 0, 1, 10)
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        fight = Fight(
            99,
            [pc, first, second],
            cells,
            {0: {pc.position}, 1: {first.position, second.position}},
        )
        for actor in fight.actors.values():
            actor.physical_radius = 0
            # Fresh PB instances have a complete, empty property counter map.
            actor.native_fight_property_counts = {}
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        initialize_global_pv_collections(fight, (7, -7, -8))
        registry = prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0, -8: 0})
        install_fresh_actor_slots(fight, registry)
        fight.ready(1)
        # This isolated QI fixture declares a complete zero tackle/dodge
        # characteristic domain and typed life/property authority.
        from test_combat_tackle_movement import Authority

        class LifecycleAuthority(Authority):
            def __call__(self, current, actor):
                from dataclasses import replace
                from wakfu_server.combat_global_pv_collections import (
                    global_fighter_guards,
                )

                facts = super().__call__(current, actor)
                return replace(
                    facts,
                    targeting=dict(
                        facts.targeting, **global_fighter_guards(current, actor.id)
                    ),
                )

        fight.native_rail_movement_authority = LifecycleAuthority()
        for actor in fight.actors.values():
            actor.effect_stats = {1: actor.hp, 2: actor.ap, 3: actor.mp, 7: 0, 8: 0}
        return fight, pc, first, second

    def kill_first(self, fight, first):
        fight.apply_effect_damage(7, first.id, first.hp)
        self.assertEqual(fight.phase, "active")  # A second NPC remains alive.

    def test_native_hp_setter_zero_preserves_in_play_qi_membership(self):
        from wakfu_server.combat_hp_raw import (
            SOURCE,
            install_fresh_hp_operand,
            set_hp_raw_current,
        )
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        fight, _, first, _ = self.fight()
        first.effect_stats = {1: first.hp}
        first.effect_minima = {1: 0}
        first.effect_maxima = {1: first.max_hp}
        first.effect_frozen = frozenset()
        install_fresh_hp_operand(
            first, dict(producer=SOURCE, actor_id=first.id, raw_current=first.hp)
        )
        # Fresh ordinary sources may expose profile PB authority through their
        # provider rather than a mutated live counter cache. It is irrelevant
        # to the independently proved IN_PLAY PA setter membership.
        first.native_fight_property_counts = None
        before = deepcopy(fight.native_qi_slots)
        set_hp_raw_current(first, 0)
        self.assertEqual(first.hp, 0)
        self.assertEqual(
            global_fighter_guards(fight, first.id), dict(baF=True, baG=False, baK=False)
        )
        self.assertEqual(
            current_registry(fight).ordered_U(3, 3), (first.native_obstacle_id,)
        )
        self.assertEqual(fight.native_qi_slots, before)

    def test_actual_death_keeps_slot_byte_footprint_and_byte_set_order(self):
        fight, _, first, _ = self.fight()
        before = deepcopy(
            (
                fight.native_qi_slots,
                fight.native_qi_touched_cells,
                fight.native_qi_byte_topology,
            )
        )
        slot = first.native_obstacle_id
        self.kill_first(fight, first)
        registry = current_registry(fight)
        self.assertEqual(first.native_obstacle_id, slot)
        self.assertEqual(registry.ordered_U(3, 3), (slot,))
        self.assertTrue(registry.slots[slot]["movement_blocking"])
        self.assertEqual(
            (
                fight.native_qi_slots,
                fight.native_qi_touched_cells,
                fight.native_qi_byte_topology,
            ),
            before,
        )

    def test_casting_target_resolution_on_other_npc_remains_valid_after_kill(self):
        fight, _, first, second = self.fight()
        self.kill_first(fight, first)
        adapter = SimpleNamespace(
            _actor=lambda preview, actor: SimpleNamespace(targeting={"is_eGj": True})
        )
        invocation = SimpleNamespace(caster_id=7, cell=second.position)
        context = NativeOwnedCastingContext(adapter, fight, {}, invocation, None, {})
        context.resolve_target_fighter()
        self.assertIs(context.target, second)
        self.assertTrue(context.qi_in_bounds())
        self.assertTrue(context.qi_r())

    def test_move_and_new_area_preflight_remain_valid_after_kill(self):
        fight, pc, first, _ = self.fight()
        self.kill_first(fight, first)
        fight.move(1, pc.id, [(1, 0, 0)])
        self.assertEqual(pc.position, (1, 0, 0))
        self.assertEqual(
            current_registry(fight).ordered_U(1, 0), (pc.native_obstacle_id,)
        )
        self.assertIsNone(
            register_effect_area_obstacle(
                fight, None, {"obstacle": True, "movement_blocking": True}
            )
        )

    def test_actual_summon_obstacle_registration_after_kill_keeps_corpse_byte_reserved(
        self,
    ):
        from wakfu_server.combat_summon_creation import register_fresh_summon_obstacle

        fight, _, first, _ = self.fight()
        self.kill_first(fight, first)
        summon = Actor(901, 0, (1, 1, 0), 20, 6, 3, 0, 10, owner_id=1, controlled=True)
        summon.physical_radius = 0
        summon.native_obstacle_id = None
        register_fresh_summon_obstacle(fight, summon)
        self.assertEqual(summon.native_obstacle_id, 3)
        self.assertEqual(fight.native_qi_slots[1]["identity"], ["actor", first.id])
        fight.actors[
            summon.id
        ] = summon  # Actual source registration follows QI allocation.
        register_global_fighter(fight, summon.id)
        self.assertEqual(current_registry(fight).ordered_U(1, 1), (3,))

    def test_native_los_after_kill_preserves_proved_corpse_visibility(self):
        from wakfu_server.combat_casting_los import native_casting_ray

        fight, pc, first, second = self.fight()
        self.kill_first(fight, first)
        authority = SimpleNamespace(properties=lambda preview, actor: frozenset())
        kwargs = dict(
            source_height=0, target_height=0, ignored_slots=[pc.native_obstacle_id]
        )
        # Ray geometry is an isolated source fixture; QI and bcQ production
        # are the actual shared implementation, including the OFF_PLAY actor.
        with patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=[(True, [(1, 1)])],
        ):
            self.assertTrue(
                native_casting_ray(
                    fight, authority, 1134, pc.position, second.position, **kwargs
                )
            )
        with patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=[(True, [(3, 3)])],
        ):
            self.assertFalse(
                native_casting_ray(
                    fight, authority, 1134, pc.position, second.position, **kwargs
                )
            )

    def test_raw_hp0_does_not_prove_off_play(self):
        fight, _, first, _ = self.fight()
        first.hp = 0
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            current_registry(fight)

    def test_out_of_play_with_positive_hp_requires_actual_qi_removal(self):
        fight, _, first, _ = self.fight()
        set_global_fighter_status(fight, first.id, "OUT_OF_PLAY")
        self.assertGreater(first.hp, 0)
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            current_registry(fight)

    def test_fabricated_off_play_without_owned_death_does_not_prove_qi_lifecycle(self):
        fight, _, first, _ = self.fight()
        first.hp = 0
        set_global_fighter_status(fight, first.id, "OFF_PLAY")
        with self.assertRaisesRegex(ValueError, "owned corpse registration"):
            current_registry(fight)

    def test_dead_actor_movement_cannot_hide_unregistered_hp0_on_another_actor(self):
        fight, pc, first, _ = self.fight()
        first.hp = 0
        before = deepcopy(fight.native_qi_slots)
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            fight.move(1, pc.id, [(1, 0, 0)])
        self.assertEqual(fight.native_qi_slots, before)
        self.assertEqual(pc.position, (0, 0, 0))

    def test_registration_mismatch_identifies_actual_actor_without_repairing_qi(self):
        fight, _, first, _ = self.fight()
        before = deepcopy(fight.native_qi_slots)
        first.position = (2, 3, 0)  # Deliberately bypass the actual QK producer.
        with self.assertRaisesRegex(
            ValueError, r"actor=-7 boundary=physical_registration.*expected="
        ):
            current_registry(fight)
        self.assertEqual(fight.native_qi_slots, before)

    def test_actual_multi_step_registration_remains_current_at_each_area_boundary(self):
        from wakfu_server.combat_qi_fight import move_registered_actor

        fight, _, first, _ = self.fight()
        slot = first.native_obstacle_id
        for destination in ((2, 3, 0), (1, 3, 0), (1, 2, 0)):
            move_registered_actor(fight, first, destination)
            registry = current_registry(fight)
            self.assertEqual(registry.ordered_U(*destination[:2]), (slot,))
            self.assertEqual(tuple(registry.slots[slot]["position"]), destination[:2])
