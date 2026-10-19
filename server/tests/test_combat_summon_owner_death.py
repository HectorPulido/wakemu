"""Non-attack descendant lifetime settlement and actual Tofona1152 creation."""
from copy import deepcopy
from random import Random
import struct
import unittest
from unittest.mock import patch

import test_combat_summon_retirement as retirement_fixture
from wakfu_server.combat_state import Actor
from wakfu_server.combat_summon_owner_death import settle
from wakfu_server.combat_ordinary_death import registered_ordinary_death
from wakfu_server.combat_global_pv_collections import (
    register_global_fighter,
    set_global_fighter_status,
)
from wakfu_server.combat_summon_creation import register_fresh_summon_obstacle
from wakfu_server.combat_native_action_ids import (
    native_delivery_boundary,
    MAX_NATIVE_ACTION_ID,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages


class SummonOwnerDeathTests(unittest.TestCase):
    def fixture(self, *, captured=False):
        fight, owner, enemy, child = retirement_fixture.SummonRetirementTests().fight(
            origin="captured" if captured else "ordinary"
        )
        # Explicit fixture PB authority, independent of a raw HP observation.
        child.native_world_properties = frozenset()
        ally = Actor(8, 0, (0, 1, 0), 50, 6, 3, 0, 10, owner_id=2, controlled=True)
        ally.physical_radius = 0
        ally.native_fight_property_counts = {}
        register_fresh_summon_obstacle(fight, ally)
        fight.actors[ally.id] = ally
        register_global_fighter(fight, ally.id)
        fight.order.append(ally.id)
        return fight, owner, enemy, child, ally

    def clone_child(self, fight, original, identity, caster, position):
        child = deepcopy(original)
        child.id, child.position, child.native_obstacle_id = identity, position, -1
        child.owner_id, child.controlled = caster.owner_id, caster.controlled
        child.native_controller_id = child.native_master_id = caster.id
        child.native_summon_source.update(caster_id=caster.id, controller_id=caster.id)
        child.native_summon_source["native_symbiot_source"] = "eZl.new_eHD.pRO_false"
        row = deepcopy(fight.native_summon_registrations[original.id])
        row.update(actor_id=identity, caster_id=caster.id, controller_id=caster.id)
        row["authority"]["native_controller_id"] = caster.id
        register_fresh_summon_obstacle(fight, child)
        fight.actors[identity] = child
        register_global_fighter(fight, identity)
        fight.native_summon_registrations[identity] = row
        fight.order.append(identity)
        return child

    def native_tofona(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            5, 20, native_qi=True, target_ref=5, target_level=10, variation_seed=0
        )
        if fight.current.id == 7:
            fight.end_turn(character["account_id"], 7, fight.current.turn_count)
        self.assertEqual(fight.current.id, -7)
        origin = fight.current.position
        occupied = {actor.position for actor in fight.actors.values()}
        cells = [
            cell
            for cell in sorted(fight.walkable)
            if cell not in occupied
            and 3 <= abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 6
        ]
        errors = []
        for cell in cells[:128]:
            try:
                tx = prepare_npc_spell(
                    fight,
                    dict(type="cast", spellId=1152, level=10, target=list(cell)),
                    character,
                    {-7: monster},
                    encode_deck([], []),
                    action_id=2,
                    rng=Random(0),
                )
            except ValueError as error:
                errors.append(str(error))
                continue
            fresh = set(tx.fight.actors) - set(fight.actors)
            self.assertEqual(len(fresh), 1)
            child = tx.fight.actors[fresh.pop()]
            self.assertEqual(child.native_summon_source["ref"], 6)
            self.assertEqual(child.native_summon_source["caster_id"], -7)
            return tx.fight, child.id
        self.fail(f"Actual native Tofona1152 had no legal birth: {errors[:4]}")

    def test_actual_tofona1152_baby_dies_with_mother_before_victory(self):
        from wakfu_server.combat_qi_fight import current_registry

        fight, identity = self.native_tofona()
        slot = fight.actors[identity].native_obstacle_id
        fight.apply_effect_damage(7, -7, fight.actors[-7].hp)
        child = fight.actors[identity]
        self.assertEqual(child.hp, 0)
        self.assertTrue(registered_ordinary_death(fight, child))
        self.assertEqual(child.native_obstacle_id, -1)
        self.assertIsNone(current_registry(fight).slots[slot])
        self.assertNotIn(identity, fight.order)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        self.assertEqual(
            len(
                [
                    e
                    for e in fight.events
                    if e["kind"] == "death" and e["actor_id"] == identity
                ]
            ),
            1,
        )
        self.assertFalse(
            any(
                e["kind"] == "damage" and e.get("target_id") == identity
                for e in fight.events
            )
        )

    def test_captured_owner_ko_releases_slot_and_resurrection_does_not_restore_child(
        self,
    ):
        from wakfu_server.combat_resurrection import (
            prepare_resurrection,
            complete_resurrection,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext

        fight, owner, enemy, child, _ = self.fixture(captured=True)
        credits = []
        fight.apply_effect_damage(
            enemy.id, owner.id, owner.hp, native_death_delivery=credits.append
        )
        self.assertEqual(credits, [owner.id])
        self.assertEqual((owner.hp, child.hp), (0, 0))
        self.assertEqual(fight.phase, "active")
        self.assertTrue(fight.native_captured_rosters[str(owner.id)]["available"][0])
        prepared = prepare_resurrection(
            fight,
            owner,
            dict(effect_class=196, native_effect_flags=[]),
            execution_context=StatExecutionContext(True, True, None, False, None),
        )
        owner.hp = 10  # Trusted HP-restoration half of the authorized196 boundary.
        self.assertTrue(
            complete_resurrection(fight, owner, prepared, action_id=5, packets=[])
        )
        self.assertEqual(child.hp, 0)
        self.assertTrue(registered_ordinary_death(fight, child))
        self.assertEqual(child.native_obstacle_id, -1)
        before = deepcopy(fight.events)
        self.assertEqual(settle(fight), ())
        self.assertEqual(fight.events, before)

    def test_nested_closure_preserves_foreign_summon_hero_and_independent_area(self):
        fight, owner, enemy, child, ally = self.fixture()
        grandchild = self.clone_child(fight, child, 902, child, (1, 2, 0))
        foreign = self.clone_child(fight, child, 903, ally, (2, 2, 0))
        # Isolate the relationship producer: unrelated area data is not an
        # actor lifetime producer and must not be interpreted as a descendant.
        area = {99: {"caster_id": owner.id, "sentinel": "independent-area"}}
        fight.native_effect_areas = deepcopy(area)
        fight._resolution_depth += 1
        try:
            fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
        finally:
            fight._resolution_depth -= 1
        self.assertEqual(settle(fight), (child.id, grandchild.id))
        self.assertEqual((child.hp, grandchild.hp), (0, 0))
        self.assertGreater(foreign.hp, 0)
        self.assertGreater(ally.hp, 0)
        self.assertEqual(fight.native_effect_areas, area)
        self.assertTrue(registered_ordinary_death(fight, grandchild))
        before = deepcopy(fight.events)
        self.assertEqual(settle(fight), ())
        self.assertEqual(fight.events, before)

    def test_raw_hp_zero_without_owned_death_or_off_play_does_not_cascade(self):
        fight, owner, _, child, _ = self.fixture()
        owner.hp = 0
        self.assertEqual(settle(fight), ())
        self.assertGreater(child.hp, 0)
        set_global_fighter_status(fight, owner.id, "OFF_PLAY")
        self.assertEqual(settle(fight), ())
        self.assertGreater(child.hp, 0)

    def test_no_live_descendant_work_does_not_scan_retained_event_history(self):
        class UnscannableHistory(list):
            def __iter__(self):
                raise AssertionError("No-op settlement scanned historical events")

        fight, owner, _, child, _ = self.fixture()
        fight.events = UnscannableHistory(fight.events)
        # A living owner cannot start a cascade, regardless of history size.
        self.assertEqual(settle(fight), ())
        owner.hp = 0
        child.hp = 0
        # Retained dead child registrations also need no new death work.
        self.assertEqual(settle(fight), ())
        fight.native_summon_registrations[child.id] = []
        with self.assertRaisesRegex(
            ValueError, "Malformed owner-death summon registration"
        ):
            settle(fight)

    def test_missing_child_is_not_hidden_by_cheap_work_filter(self):
        fight, owner, enemy, child, _ = self.fixture()
        fight._resolution_depth += 1
        try:
            fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
        finally:
            fight._resolution_depth -= 1
        del fight.actors[child.id]
        before = deepcopy(fight.events)
        with self.assertRaises(ValueError):
            settle(fight)
        self.assertEqual(fight.events, before)

    def test_authenticated_departure_does_not_reuse_a_historical_owner_death(self):
        from wakfu_server.combat_pve_departure import retire_pve_actor

        fight, owner, enemy, child, _ = self.fixture()
        fight._resolution_depth += 1
        try:
            fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
        finally:
            fight._resolution_depth -= 1
        retire_pve_actor(fight, owner, root_actor_id=owner.id, owner_id=owner.owner_id)
        owner.pve_withdrawn = True
        # Withdrawal owns a separate descendant teardown. This isolated
        # lifetime producer must not look up the removed native fdy owner.
        self.assertEqual(settle(fight), ())
        self.assertGreater(child.hp, 0)

    def test_synchronous_owner_resurrection_precedes_outer_cascade(self):
        from wakfu_server.combat_resurrection import (
            prepare_resurrection,
            complete_resurrection,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext

        fight, owner, enemy, child, _ = self.fixture()
        with fight.effect_resolution():
            fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
            prepared = prepare_resurrection(
                fight,
                owner,
                dict(effect_class=196, native_effect_flags=[]),
                execution_context=StatExecutionContext(True, True, None, False, None),
            )
            owner.hp = 10
            complete_resurrection(fight, owner, prepared, action_id=5, packets=[])
        self.assertGreater(child.hp, 0)
        self.assertFalse(
            any(e["kind"] == "owner_death_hp_minimum_update" for e in fight.events)
        )

    def test_native_protection_and_unqualified_lifetime_contracts_are_preserved(self):
        for mode in (
            "no_death",
            "ko_time",
            "frozen",
            "positive_minimum",
            "unknown_world",
        ):
            with self.subTest(mode=mode):
                fight, owner, enemy, child, _ = self.fixture()
                if mode == "no_death":
                    child.native_world_properties = frozenset({12})
                elif mode == "ko_time":
                    child.effect_stats[14] = 1
                elif mode == "frozen":
                    child.effect_frozen = frozenset({1})
                elif mode == "positive_minimum":
                    child.effect_minima[1] = 1
                else:
                    del child.native_world_properties
                fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
                self.assertGreater(child.hp, 0)
                self.assertFalse(
                    any(
                        e["kind"] == "owner_death_hp_minimum_update"
                        for e in fight.events
                    )
                )

    def test_forged_relationship_receipt_is_rejected(self):
        fight, owner, enemy, child, _ = self.fixture()
        fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
        update = next(
            e for e in fight.events if e["kind"] == "owner_death_hp_minimum_update"
        )
        update["parent_death_sequence"] += 100
        with self.assertRaisesRegex(ValueError, "relationship transition"):
            registered_ordinary_death(fight, child)

    def test_native_allocation_failure_rolls_back_parent_child_slot_and_pending_ack(
        self,
    ):
        fight, owner, enemy, child, _ = self.fixture(captured=True)
        runtime = RuntimeMessages(fight)
        runtime.native_action_id = MAX_NATIVE_ACTION_ID - 1
        before = deepcopy(fight.events)

        @native_delivery_boundary
        def lethal(candidate):
            candidate.fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
            return []

        with self.assertRaises(ValueError):
            lethal(runtime)
        self.assertEqual(
            (fight.actors[owner.id].hp, fight.actors[child.id].hp), (100, 40)
        )
        self.assertEqual(fight.events, before)
        self.assertFalse(fight.native_captured_rosters[str(owner.id)]["available"][0])
        self.assertEqual(runtime.native_action_id, MAX_NATIVE_ACTION_ID - 1)
        self.assertIsNone(runtime.awaiting_ack)
        self.assertFalse(getattr(runtime, "_reported_deaths", set()))

    def test_actual_npc_end_fallback_publishes_one_child_death_without_oracle(self):
        from wakfu_server.combat_death import newly_registered_death_messages

        fight, identity = self.native_tofona()
        before = fight.sequence

        def poison(candidate, *, actor_id, action_id):
            candidate = deepcopy(candidate)
            candidate.apply_effect_damage(7, actor_id, candidate.actors[actor_id].hp)
            return candidate, []

        runtime = RuntimeMessages(fight, turn_end_provider=poison)
        packets = runtime.end_server_turn(-7, fight.turn_id)
        child_states = [
            struct.unpack_from(">qB", payload, 12)
            for opcode, payload in packets
            if opcode == 12727 and struct.unpack_from(">q", payload, 12)[0] == identity
        ]
        self.assertEqual(child_states, [(identity, 0), (identity, 2)])
        ids = [row["native_action_id"] for row in packets.native_actions]
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(
            newly_registered_death_messages(runtime, after_sequence=before), []
        )
        self.assertEqual(fight.actors[identity].hp, 0)
