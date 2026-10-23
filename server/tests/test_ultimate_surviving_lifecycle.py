"""Legal owned tank build witnesses for ultimate callback survival."""
from copy import deepcopy
from random import Random
import struct
import unittest
from unittest.mock import patch
from test_combat_npc_event_controller import admission


class UltimateSurvivingLifecycleTests(unittest.TestCase):
    def test_native_nogord_survives_owned_start_end_and_ack(self):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.monsters import native_abilities
        from wakfu_server.combat_effective_control import effective_server_controlled

        original_catalog = npc_spell_catalog()
        candidate_catalog = dict(original_catalog)
        candidate_policy = deepcopy(original_catalog["activation_policy"])
        if "3433" in candidate_policy["enabled_monsters"]:
            self.assertEqual(candidate_policy["enabled_monsters"]["3433"], admission())
        candidate_policy["enabled_monsters"]["3433"] = admission()
        candidate_catalog["activation_policy"] = candidate_policy
        observed = []
        original_replay = NativeEventReplay.__call__
        activations = []
        original_activation = EffectDispatcher.execute_activation

        def capture_activation(dispatcher, invocation, **kwargs):
            source = kwargs["source"]
            activations.append(
                (invocation.reference, source.manager_actor_id, source.event_ids)
            )
            return original_activation(dispatcher, invocation, **kwargs)

        def capture(dispatcher, event, **kwargs):
            outcome = original_replay(dispatcher, event, **kwargs)
            observed.append(
                dict(
                    manager=event.manager_actor_id,
                    event_ids=event.event_ids,
                    outcomes=list(outcome),
                )
            )
            return outcome

        with patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog",
            return_value=candidate_catalog,
        ), patch.object(NativeEventReplay, "__call__", capture), patch.object(
            EffectDispatcher, "execute_activation", capture_activation
        ):
            # Native static occlusion separates this scene from the lethal
            # visible opening; the actual actor heights must preserve it.
            enemy = (-8, -13, 0)
            fixture, facts = native_tank_fixture(validator)
            with original_bootstrap_publication():
                fight, character, monsters, deck = fixture(
                    3433, 200, enemy, native_lifecycle=True
                )
            npc = fight.actors[-200]
            from wakfu_server.combat_native_los_ray import cast_rays
            from wakfu_server.combat_group_cells import group_cells
            from wakfu_server.combat_area_geometry import native_area_contains
            from wakfu_server.combat_terrain import local_arena

            player = fight.actors[7]
            arena = local_arena(
                1134,
                0,
                enemy,
                npc.position,
                relocate_monsters=False,
                compact=True,
                variation_seed=1,
                minimum_dimensions=(9, 9),
            )
            self.assertIn(enemy, arena["validated_cells"])
            self.assertNotIn(enemy, arena["native_border_cells"])
            self.assertNotIn(npc.position, arena["native_border_cells"])
            rays = cast_rays(
                1134,
                npc.position,
                player.position,
                source_height=npc.native_los_height,
                target_height=player.native_los_height,
            )
            self.assertTrue(rays)
            self.assertFalse(
                any(visible for visible, _ in rays),
                (npc.native_los_height, player.native_los_height, rays),
            )
            root = candidate_catalog["effects"]["186070"]
            damage = candidate_catalog["effects"]["186071"]
            centers = group_cells(fight, root, npc.position, caster_id=npc.id)
            self.assertTrue(centers)
            self.assertFalse(
                any(
                    native_area_contains(
                        damage,
                        origin=center,
                        reference=npc.position,
                        point=player.position,
                        direction=npc.direction,
                        radius=player.physical_radius,
                    )
                    for center in centers
                )
            )
            self.assertEqual(native_abilities(3433, 200), [])
            self.assertEqual(character["level"], 200)
            receipt = fight.native_npc_initialization_receipts[-200]
            self.assertTrue(receipt["initialized"])
            self.assertEqual(
                receipt["raw_triples"], admission()["initial_state_triples"]
            )
            self.assertEqual(
                {row["state_id"] for row in receipt["resolved_states"]},
                {4509, 5619, 7998},
            )
            self.assertTrue(
                any(
                    row["manager"] == -200 and 1003 in row["event_ids"]
                    for row in observed
                )
            )
            self.assertTrue(
                {4503, 4502} <= {entry.reference for entry in npc.state_ledger.entries}
            )
            self.assertTrue(effective_server_controlled(fight, npc))
            self.assertEqual(fight.current.id, npc.id)
            rng = Random(0)

            def stats(actor, current):
                kw = dict(
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    fight=current,
                )
                if actor.controlled:
                    return actual_actor_stats(character, actor, current.id, **kw)
                return actual_monster_actor_stats(
                    monsters[actor.id], actor, current.id, **kw
                )

            runtime = RuntimeMessages(
                fight,
                runtime_stats_serializer=stats,
                turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                    character,
                    monsters,
                    p,
                    deck,
                    rng=rng,
                    native_events=True,
                    area_callbacks=True,
                    **kw
                ),
                turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                    character, monsters, p, deck, rng=rng, **kw
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            packets = list(runtime.turn_started())
            self.assertTrue(
                any(
                    row["manager"] == -200 and 1001 in row["event_ids"]
                    for row in observed
                )
            )
            self.assertTrue(
                any(
                    root == 186446 and manager == -200 and 1001 in ids
                    for root, manager, ids in activations
                )
            )
            self.assertGreater(
                fight.actors[7].hp, 0, dict(build=facts, events=fight.events[-20:])
            )
            self.assertEqual(fight.current.id, -200)
            packets.extend(runtime.end_server_turn(-200, fight.turn_id))
            self.assertIsNotNone(runtime.awaiting_ack)
            packets.extend(
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            )
            self.assertNotEqual(fight.current.id, -200)
            self.assertTrue(
                any(
                    row["manager"] == -200 and 1002 in row["event_ids"]
                    for row in observed
                )
            )
            self.assertFalse(any(event["kind"] == "npc_cast" for event in fight.events))
            self.assertTrue(packets)

    def test_native_magmog_fifth_counter_reaches_7515_through_owned_end(self):
        from ultimate_lifecycle_witness import run_witness

        result = run_witness()
        self.assertEqual(result["status"], "native_phase_callback_executed", result)
        self.assertTrue(result["paid_defense_casts"])
