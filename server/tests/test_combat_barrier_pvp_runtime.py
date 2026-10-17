"""Actual controlled-player damage against a native Barrier aptitude target."""
import os
import random
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class BarrierPvpRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server import combat_retained_runtime

        cls.active_retained_metadata = (
            combat_retained_runtime.native_retained_metadata()
        )

    def test_real_controlled_spell_hits_barrier_twice_and_target_clock_expires(self):
        from wakfu_server import aptitudes
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
        )
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server import combat_retained_runtime
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck
        from tests.test_aptitude_catalog_coverage import aptitude_sheet
        from wakfu_server.wire import proto_field

        origin, target_position = (-8, -7, -1), (-7, -7, -1)
        arena = local_arena(1134, 78, origin, target_position)
        characters = {
            7: effective_character(
                dict(
                    id=7,
                    account_id=3,
                    map_id=1134,
                    breed=8,
                    level=200,
                    hp=maximum(8, 200),
                    builds={},
                    inventory_items=[],
                )
            ),
            8: effective_character(
                dict(
                    id=8,
                    account_id=4,
                    map_id=1134,
                    breed=8,
                    level=200,
                    hp=maximum(8, 200),
                    builds={
                        0: {
                            "sheet": proto_field(24, 0xFFFFFFFF).hex(),
                            "aptitudes": aptitude_sheet([(17, 1)]).hex(),
                        }
                    },
                    inventory_items=[],
                )
            ),
        }
        actors = [
            Actor(
                7,
                0,
                origin,
                characters[7]["hp"],
                6,
                3,
                20,
                200,
                3,
                True,
                max_hp=characters[7]["max_hp"],
            ),
            Actor(
                8,
                1,
                target_position,
                characters[8]["hp"],
                6,
                3,
                10,
                200,
                4,
                True,
                max_hp=characters[8]["max_hp"],
            ),
        ]
        fight = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {origin}, 1: {target_position}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources={7: (6, 6), 8: (6, 6)},
            running_effects={7: (), 8: ()},
            initial_effect_uid=1,
        )
        self.assertEqual(
            current_registry(fight).slots[actors[0].native_obstacle_id]["identity"],
            ["actor", 7],
        )
        fight.ready(3)
        fight.ready(4)
        attacker_deck = encode_deck([4775])
        target_deck = encode_deck()
        decks = {7: attacker_deck, 8: target_deck}
        with patch.object(
            combat_retained_runtime,
            "native_retained_metadata",
            return_value=self.active_retained_metadata,
        ):
            for action_id, (identity, owner) in enumerate(((7, 3), (8, 4)), 1):
                fight, _ = prepare_server_initialization(
                    characters[identity],
                    {},
                    fight,
                    owner,
                    decks[identity],
                    action_id=action_id,
                    rng=random.Random(0),
                    fight_start=(identity == 8),
                    player_characters=characters,
                    deck_blobs=decks,
                )
            self.assertTrue(fight.native_start_event_delivered)
            self.assertIn(17, aptitudes.BONUS_CATEGORY)
            aptitude_rows = [
                (uid, row)
                for uid, row in fight.native_retained_records.items()
                if row.get("container_type") == 36 and row.get("manager_id") == 8
            ]
            self.assertTrue(
                aptitude_rows,
                msg={
                    "states": [
                        (
                            actor_id,
                            [state.reference for state in actor.state_ledger.entries],
                        )
                        for actor_id, actor in fight.actors.items()
                    ],
                    "aptitude_records": {
                        uid: record
                        for uid, record in fight.native_retained_records.items()
                        if record.get("container_type") == 36
                    },
                },
            )
            barrier_listener_rows = [
                (uid, row)
                for uid, row in aptitude_rows
                if row.get("generic_effect") == 136452
            ]
            self.assertTrue(
                barrier_listener_rows,
                msg={
                    "aptitude_rows": aptitude_rows,
                    "groups": fight.native_owned_group_effects,
                },
            )
            barrier_uid = barrier_listener_rows[0][0]
            barrier_group = fight.native_owned_group_effects[barrier_uid]
            barrier_timer = barrier_group.get("timer")
            self.assertEqual(barrier_timer["actor_id"], 8)
            barrier_before = fight.actors[8].hp
            from wakfu_server.combat_aptitude_initialization import effect_catalog
            from wakfu_server.combat_damage_handler import NativeDamageHandler

            native_aptitudes = effect_catalog()["effects"]
            level_group = native_aptitudes["136452"]
            reduction_effect = native_aptitudes["164892"]
            self.assertEqual(level_group["effect_class"], 999)
            self.assertEqual(level_group["children"], [164892])
            self.assertEqual(level_group["parameters"][14:16], [50.0, 0.0])
            self.assertEqual(reduction_effect["effect_class"], 430)
            self.assertEqual(
                reduction_effect["parameters"], [1.0, 0.0, 0.0, -1.0, 0.0, 0.0]
            )
            native_reduction = fight.actors[8].effective_level * 50 // 100
            self.assertEqual(barrier_group["execution_count"], 1)
            calculated = []
            original_calculate = NativeDamageHandler._calculate
            # Only damage-formula inputs: AP/MP and accumulated class resource67
            # may change between casts without changing this classic damage.
            damage_stats = (
                16,
                17,
                20,
                21,
                27,
                28,
                48,
                49,
                52,
                95,
                101,
                102,
                103,
                104,
                105,
                106,
                107,
            )

            def observe_calculation(handler, effect, invocation, **kwargs):
                result = original_calculate(handler, effect, invocation, **kwargs)
                if invocation.caster_id == 7 and invocation.target_id == 8:
                    source = handler.fight.actors[7]
                    target = handler.fight.actors[8]
                    context, interpreted, amount = result
                    calculated.append(
                        dict(
                            action_id=action_id,
                            reference=invocation.reference,
                            level=invocation.level,
                            parameters=tuple(effect["parameters"]),
                            context=context,
                            flags=tuple(effect["native_effect_flags"]),
                            source=tuple(
                                source.effect_stats.get(k, 0) for k in damage_stats
                            ),
                            target=tuple(
                                target.effect_stats.get(k, 0) for k in damage_stats
                            ),
                            positions=(source.position, target.position),
                            source_health=(source.hp, source.max_hp),
                            additional_final=kwargs.get("additional_final", 0),
                            amount=amount,
                        )
                    )
                return result

            casts = []
            for action_id in (3, 4):
                target = fight.actors[8]
                with patch.object(
                    NativeDamageHandler, "_calculate", observe_calculation
                ):
                    tx = prepare_server_spell(
                        struct.pack(">qqiih", 7, (7 << 32) | 4775, *target.position),
                        characters[7],
                        {},
                        fight,
                        3,
                        attacker_deck,
                        action_id=action_id,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                casts.append(tx)
                fight = tx.fight
            after_barrier_hit = casts[0].fight.actors[8].hp
            after_unshielded_hit = casts[1].fight.actors[8].hp
            # Native Qe prepares damage before testing its criterion; skipped
            # sibling398197 can be calculated without producing a committed hit.
            # Compare the selected149450 within each actual cast, without making
            # the number of internal calculation passes a gameplay contract.
            by_cast = {}
            for cast_action in (3, 4):
                selected = [
                    {key: value for key, value in row.items() if key != "action_id"}
                    for row in calculated
                    if row["action_id"] == cast_action and row["reference"] == 149450
                ]
                self.assertTrue(selected, calculated)
                self.assertTrue(all(row == selected[0] for row in selected), calculated)
                by_cast[cast_action] = selected[0]
            first_calculation, second_calculation = by_cast[3], by_cast[4]
            self.assertEqual(first_calculation, second_calculation, calculated)
            self.assertEqual(first_calculation["reference"], 149450)
            self.assertEqual(first_calculation["parameters"], (3.0, 0.33))
            self.assertFalse(first_calculation["context"].critical)
            self.assertEqual(first_calculation["additional_final"], 0)
            raw_damage = second_calculation["amount"]
            self.assertGreater(raw_damage, native_reduction)
            protected_damage = max(0, raw_damage - native_reduction)
            self.assertEqual(barrier_before - after_barrier_hit, protected_damage)
            self.assertEqual(after_barrier_hit - after_unshielded_hit, raw_damage)
            first_remaining_barrier_rows = [
                row
                for row in casts[0].fight.native_retained_records.values()
                if row.get("generic_effect") == 136452 and row.get("manager_id") == 8
            ]
            self.assertFalse(first_remaining_barrier_rows)
            hit_events = [
                [
                    event["amount"]
                    for event in tx.fight.events
                    if event.get("kind") == "damage" and event.get("target_id") == 8
                ]
                for tx in casts
            ]
            self.assertEqual(hit_events[0], [protected_damage])
            self.assertEqual(hit_events[1], [protected_damage, raw_damage])
            fight = casts[1].fight
            fight, _ = prepare_server_turn_end(
                characters[7],
                {},
                fight,
                attacker_deck,
                actor_id=7,
                action_id=5,
                player_characters=characters,
                deck_blobs=decks,
            )
            fight.end_turn(3, 7, fight.actors[7].turn_count)
            self.assertEqual(fight.current.id, 8)
            from wakfu_server.combat_timed_expiration import prepare_timed_expiration

            fight, _ = prepare_timed_expiration(
                fight,
                actor_id=8,
                round_number=fight.native_timeline_round,
                phase="start",
                action_id=6,
            )
            fight, _ = prepare_server_turn_start(
                characters[8],
                {},
                fight,
                target_deck,
                actor_id=8,
                action_id=7,
                player_characters=characters,
                deck_blobs=decks,
            )
            renewed = [
                row
                for row in fight.native_retained_records.values()
                if row.get("generic_effect") == 136452
                and row.get("manager_id") == 8
                and row.get("container_type") == 36
            ]
            self.assertEqual(len(renewed), 1)
            self.assertEqual(
                fight.native_class_initializations[8]["aptitude_periodic_turn"],
                fight.turn_id,
            )
            from wakfu_server.combat_server_spell import server_runtime
            from wakfu_server.combat_periodic_aptitude import renew_periodic_aptitudes

            factory, _ = server_runtime(
                characters[8],
                {},
                target_deck,
                action_id=8,
                critical=False,
                player_characters=characters,
                deck_blobs=decks,
            )
            dispatcher, _ = factory(
                fight, {"native_retained_container": {"present": False}}
            )
            with fight.effect_resolution():
                self.assertEqual(renew_periodic_aptitudes(dispatcher, actor_id=8), ())
            self.assertEqual(
                sum(
                    row.get("generic_effect") == 136452
                    and row.get("manager_id") == 8
                    and row.get("container_type") == 36
                    for row in fight.native_retained_records.values()
                ),
                1,
            )
