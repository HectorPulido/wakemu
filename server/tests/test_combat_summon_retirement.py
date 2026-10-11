from copy import deepcopy
import unittest

from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_fighter,
)
from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_summon_creation import register_fresh_summon_obstacle


class SummonRetirementTests(unittest.TestCase):
    def fight(self, *, ko=0, registered=True, origin="ordinary"):
        owner = Actor(7, 0, (0, 0, 0), 100, 6, 6, 10, 10, owner_id=1, controlled=True)
        enemy = Actor(-7, 1, (3, 3, 0), 100, 0, 0, 1, 10)
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        fight = Fight(
            99, [owner, enemy], cells, {0: {owner.position}, 1: {enemy.position}}
        )
        for actor in fight.actors.values():
            actor.physical_radius = 0
            actor.native_fight_property_counts = {}
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        initialize_global_pv_collections(fight, (7, -7))
        registry = prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        install_fresh_actor_slots(fight, registry)
        fight.ready(1)

        summon = Actor(901, 0, (1, 1, 0), 40, 4, 3, 0, 10, owner_id=1, controlled=True)
        summon.physical_radius = 0
        summon.native_fight_property_counts = {}
        summon.native_controller_id = owner.id
        summon.native_master_id = owner.id
        summon.native_summoned_from_symbiot = False
        summon.native_summon_source = dict(
            ref=307,
            level=10,
            caster_id=owner.id,
            controller_id=owner.id,
            native_relation_source="big.new_bje.fdt_initial_registration",
            native_symbiot_source="eZl.new_eHD.pRO_false",
        )
        if origin == "captured":
            from wakfu_server.characters.captured_roster import (
                CapturedCreature,
                OwnedCapturedRoster,
            )

            slots = (CapturedCreature(0, 307, "beacon"),) + (None,) * 9
            available = (False,) * 10
            roster = OwnedCapturedRoster(owner.id, slots, available, selected_slot=0)
            fight.native_captured_rosters = {str(owner.id): roster.to_record()}
            fight.native_captured_roster_updates = {str(owner.id): roster.to_record()}
            summon.native_summoned_from_symbiot = True
            summon.native_summon_source.update(
                native_symbiot_source="eZr324.after_common_factory_and_fan.lE_true",
                native_captured_owner_id=owner.id,
                native_captured_slot=0,
            )
        if origin == "copied":
            summon.native_summon_source["ref"] = 2382
            summon.native_summon_source.update(
                native_character_copy_source="eZw1002.faB.eHI.bPl",
                native_symbiot_source="eZw1002.new_eHI.pRO_false",
                native_copy_source_actor_id=owner.id,
                native_copy_effect_reference=554,
                native_copy_runner_uid=700,
            )
            summon.native_copy_pa_source = dict(
                producer="eHI.pRU.ffh.a",
                actor_id=summon.id,
                source_actor_id=owner.id,
                profile=2382,
                effect_reference=554,
            )
            summon.effect_characteristic_raw_currents = {1: 40}
        summon.effect_stats = {1: 40, 14: ko}
        summon.effect_minima = {1: 0, 14: 0}
        summon.effect_maxima = {1: 100, 14: 100}
        summon.effect_base_minima = {1: 0, 14: 0}
        summon.effect_base_maxima = {1: 100, 14: 100}
        summon.effect_percentages = {1: 0, 14: 0}
        summon.effect_frozen = frozenset()
        register_fresh_summon_obstacle(fight, summon)
        fight.actors[summon.id] = summon
        register_global_fighter(fight, summon.id)
        fight.order.insert(1, summon.id)
        if registered:
            fight.native_summon_registrations = {
                summon.id: dict(
                    actor_id=summon.id,
                    caster_id=owner.id,
                    controller_id=owner.id,
                    authority=dict(
                        is_summon=True,
                        is_player=False,
                        breed_id=summon.native_summon_source["ref"],
                        native_real_level=10,
                        native_controller_id=owner.id,
                        native_summoned_from_symbiot=(origin == "captured"),
                    ),
                )
            }
        return fight, owner, enemy, summon

    def test_zero_hp_in_play_is_not_elected_for_death_retirement(self):
        from wakfu_server.combat_summon_retirement import settle_summon_retirements

        fight, _, _, summon = self.fight(ko=0)
        slot = summon.native_obstacle_id
        summon.hp = 0
        # This test isolates candidate election; QI/PA certification has its
        # own source-backed tests. No death transition was registered here.
        self.assertEqual(settle_summon_retirements(fight), ())
        self.assertEqual(summon.native_obstacle_id, slot)
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "IN_PLAY",
        )

    def test_zero_ko_settles_to_out_of_play_and_releases_only_qi_slot(self):
        fight, owner, _, summon = self.fight(ko=0)
        old_slot = summon.native_obstacle_id
        old_position = summon.position

        fight.apply_effect_damage(owner.id, summon.id, summon.hp)

        self.assertEqual(summon.hp, 0)
        self.assertEqual(fight.actors[summon.id], summon)
        self.assertEqual(
            fight.native_summon_registrations[summon.id]["actor_id"], summon.id
        )
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "OUT_OF_PLAY",
        )
        self.assertEqual(summon.native_obstacle_id, -1)
        self.assertIsNone(fight.native_qi_slots[old_slot])
        self.assertEqual(current_registry(fight).ordered_U(*old_position[:2]), ())
        self.assertEqual(
            fight.native_summon_retirements[summon.id]["qi_slot"], old_slot
        )
        self.assertNotIn(summon.id, fight.order)

        replacement = Actor(902, 0, old_position, 20, 1, 1, 0, 10)
        replacement.physical_radius = 0
        register_fresh_summon_obstacle(fight, replacement)
        self.assertEqual(replacement.native_obstacle_id, old_slot)

    def test_retired_fighter_stats_preserve_signed_qi_removal_byte(self):
        import struct
        from dataclasses import asdict
        from unittest.mock import patch
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority
        from wakfu_server.combat_summon_stats import registered_summon_stats

        for origin in ("ordinary", "captured", "copied"):
            with self.subTest(origin=origin):
                fight, owner, _, summon = self.fight(origin=origin)
                summon.native_controlled_by_ai = False
                source = summon.native_summon_source
                authority = NativeActorAuthority(
                    targeting={},
                    is_player=False,
                    deck_spell_ids=frozenset(),
                    excluded_deck_spell_ids=frozenset(),
                    is_carried=False,
                    breed_id=source["ref"],
                    summon_count=0,
                    summon_counts_by_breed={},
                    occupant_blocks=True,
                    is_summon=True,
                    native_real_level=source["level"],
                    native_controller_id=owner.id,
                    native_summoned_from_symbiot=(origin == "captured"),
                )
                fight.native_summon_registrations[summon.id]["authority"] = asdict(
                    authority
                )
                fight.apply_effect_damage(owner.id, summon.id, summon.hp)
                with patch(
                    "wakfu_server.combat_summon_stats.snapshot_characteristics",
                    return_value=b"\x00\x00",
                ):
                    payload = registered_summon_stats(summon, fight, 1134)
                    self.assertEqual(struct.unpack_from(">b", payload, 29)[0], -1)
                    # Retained records cannot authorize a stale status or event.
                    fight.native_summon_retirements[summon.id]["sequence"] += 1
                    with self.assertRaises(ValueError):
                        registered_summon_stats(summon, fight, 1134)

    def test_live_negative_qi_slot_is_not_retirement_authority(self):
        from unittest.mock import patch
        from wakfu_server.combat_summon_stats import registered_summon_stats

        fight, _, _, summon = self.fight()
        summon.native_obstacle_id = -1
        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics"
        ) as serialize:
            with self.assertRaises(ValueError):
                registered_summon_stats(summon, fight, 1134)
            serialize.assert_not_called()

    def test_nonzero_ko_keeps_off_play_corpse_and_qi_registration(self):
        fight, owner, _, summon = self.fight(ko=1)
        slot = summon.native_obstacle_id

        fight.apply_effect_damage(owner.id, summon.id, summon.hp)

        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "OFF_PLAY",
        )
        self.assertIsNotNone(fight.native_qi_slots[slot])
        self.assertNotIn(summon.id, fight.native_summon_retirements)
        self.assertEqual(current_registry(fight).ordered_U(1, 1), (slot,))

    def test_copied_summon_uses_its_source_attested_copy_identity(self):
        fight, owner, _, summon = self.fight(ko=0, origin="copied")

        fight.apply_effect_damage(owner.id, summon.id, summon.hp)

        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "OUT_OF_PLAY",
        )
        self.assertTrue(fight.native_summon_retirements[summon.id]["copied"])

    def test_captured_retirement_releases_exact_slot_without_changing_descriptor(self):
        fight, owner, _, summon = self.fight(ko=0, origin="captured")
        before = deepcopy(fight.native_captured_rosters[str(owner.id)])

        fight.apply_effect_damage(owner.id, summon.id, summon.hp)

        after = fight.native_captured_rosters[str(owner.id)]
        self.assertEqual(after["slots"], before["slots"])
        self.assertEqual(after["selected_slot"], before["selected_slot"])
        self.assertEqual(after["available"], [True, *before["available"][1:]])
        self.assertEqual(fight.native_summon_retirements[summon.id]["captured"], True)

    def test_unregistered_actor_and_non_summon_death_are_not_retired(self):
        fight, owner, enemy, summon = self.fight(registered=False)
        summon.hp = 0
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        set_global_fighter_status(fight, summon.id, "OFF_PLAY")
        # No registration source means the runtime never elects the actor.
        from wakfu_server.combat_summon_retirement import settle_summon_retirements

        self.assertEqual(settle_summon_retirements(fight), ())
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "OFF_PLAY",
        )

        ordinary = deepcopy(enemy)
        fight.native_summon_registrations = {}
        fight.apply_effect_damage(owner.id, ordinary.id, ordinary.hp)
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(enemy.id)],
            "OFF_PLAY",
        )

    def test_missing_ko_authority_rejects_without_partial_retirement(self):
        fight, owner, _, summon = self.fight(ko=0)
        slot = summon.native_obstacle_id
        del summon.effect_stats[14]

        with self.assertRaisesRegex(ValueError, "KO_TIME snapshot"):
            fight.apply_effect_damage(owner.id, summon.id, summon.hp)

        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "OFF_PLAY",
        )
        self.assertEqual(summon.hp, 0)
        self.assertIsNotNone(fight.native_qi_slots[slot])
        self.assertNotIn(summon.id, fight.native_summon_retirements)

    def test_retirement_rejects_a_nested_boundary_without_partial_qi_change(self):
        fight, _, _, summon = self.fight(ko=0)
        slot = summon.native_obstacle_id
        summon.hp = 0
        summon.effect_stats[1] = 0
        fight._event("damage", source_id=7, target_id=summon.id, amount=40, hp=0)
        fight._event("death", actor_id=summon.id)
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        set_global_fighter_status(fight, summon.id, "OFF_PLAY")
        fight._resolution_depth = 1
        from wakfu_server.combat_summon_retirement import settle_summon_retirements

        with self.assertRaisesRegex(ValueError, "nested effect chain"):
            settle_summon_retirements(fight)

        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(summon.id)],
            "OFF_PLAY",
        )
        self.assertIsNotNone(fight.native_qi_slots[slot])
        self.assertNotIn(summon.id, fight.native_summon_retirements)


if __name__ == "__main__":
    unittest.main()
