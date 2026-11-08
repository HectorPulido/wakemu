"""Native artifact contact followed by two individual owner departures.

This is an isolated native component, not a network or durable payout receipt.
"""
import json
import os
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_ASSIGNMENT_COMPONENT") == "1",
    "Installed native publication required",
)
class RiftArtifactWithdrawalTests(unittest.TestCase):
    def test_native_artifact_survives_two_departures_and_successor_turns(self):
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from test_rift_artifact_generation_component import (
            RiftArtifactGenerationComponentTests,
        )
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_pve_withdraw import plan
        from wakfu_server.combat_native_actor_lookup import native_actor_population
        from wakfu_server.rift_native_gameplay import (
            install_wave_state,
            register_artifact_group,
        )
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        fixture = NativeRiftCarrierComponentTests()
        fixture.compiled = npc_runtime_catalog()
        fixture.registry = characteristic_registry()
        component = fixture.fixture(3, native_geometry=True)
        fight, characters, rng = component.fight, component.characters, component.rng
        # The component builds synthetic owned snapshots; give each of its
        # three players a distinct account before native runtime admission.
        for identity, account in ((7, 3), (8, 4), (9, 5)):
            characters[identity]["account_id"] = account
            fight.actors[identity].owner_id = account
        native_policy = RiftArtifactGenerationComponentTests.native_policy()
        native_policy["compensation"] = fight.rift_wave_state["policy"][
            "native_gameplay"
        ]["compensation"]
        fight.rift_wave_state["policy"]["native_gameplay"] = native_policy
        decks = {identity: encode_deck() for identity in characters}
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        for identity in (7, 8, 9):
            fight, _ = prepare_server_initialization(
                characters[identity],
                fight.rift_monsters,
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=identity,
                fight_start=False,
                **common,
            )

        def factory(current, *, action_id):
            return server_runtime(
                characters[7],
                current.rift_monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                **common,
            )[0]

        def serialize(actor, current):
            serializer = (
                actual_actor_stats if actor.controlled else actual_monster_actor_stats
            )
            source = (
                characters[actor.id]
                if actor.controlled
                else current.rift_monsters[actor.id]
            )
            return serializer(
                source,
                actor,
                current.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                direction=actor.direction,
                fight=current,
            )

        dispatcher, _ = factory(fight, action_id=20)(
            fight, {"native_retained_container": {"present": False}}
        )
        native = fight.rift_wave_state["policy"]["native_gameplay"]
        template = native["artifacts"]["producer"]["template_effect_reference"]
        # Fight390 artifact1625 (area5680) owns the start listener317520;
        # UID6292 kept caster159 while targeting surviving owner160.
        cells = ((-8, -8, -1), (-8, -9, -1), (-7, -8, -1), (-7, -9, -1))
        created = []
        with fight.effect_resolution():
            from wakfu_server.rift_company_compensation import (
                company_actor_ids,
                install_company_compensation,
            )
            from wakfu_server.combat_start_events import deliver_fight_start

            install_company_compensation(dispatcher, actor_ids=company_actor_ids(fight))
            install_wave_state(dispatcher, actor_ids=(-200, -201), wave=1)
            deliver_fight_start(dispatcher, initialized_actor_ids=tuple(fight.actors))
            # Keep the actual initialization/start producers, then construct
            # the specific artifact under test once (no random duplicate group).
            for reference, cell in zip((1625, 1594, 1613, 1614), cells):
                previous = set(fight.native_effect_areas)
                self.assertTrue(
                    dispatcher.execute(
                        EffectInvocation(
                            template,
                            fight.actors[7].effective_level,
                            7,
                            None,
                            cell,
                            native_context_hex=transfer_value_context(
                                constructed_execution_context().payload(),
                                reference,
                            ).hex(),
                            native_retained_container={"present": False},
                        )
                    )
                )
                added = set(fight.native_effect_areas) - previous
                self.assertEqual(len(added), 1)
                created.append(added.pop())
            register_artifact_group(fight, wave=1, area_uids=created)

        runtime = RuntimeMessages(fight, runtime_stats_serializer=serialize)

        def area_provider(preview, **kwargs):
            return prepare_area_movement(
                characters[7],
                preview.rift_monsters,
                preview,
                decks[7],
                **common,
                **kwargs,
            )

        apply_client(
            runtime,
            3,
            struct.pack(">q", 7) + struct.pack(">iih", *cells[0]),
            lambda actor: serialize(actor, runtime.fight),
            runtime_stats_serializer=serialize,
            area_provider=area_provider,
        )
        fight = runtime.fight
        retained = {
            uid
            for uid, row in fight.native_owned_group_effects.items()
            if row["invocation"]["caster_id"] == 7
            and row["invocation"]["target_id"] in (8, 9)
            and row["invocation"]["reference"] == 317520
        }
        self.assertEqual(len(retained), 2)

        for identity, account in ((7, 3), (8, 4)):
            self.assertGreater(fight.actors[identity].hp, 0)
            runtime.expiration_runtime_factory = lambda *, action_id: factory(
                runtime.fight, action_id=action_id
            )
            runtime.turn_start_provider = (
                lambda current, **kwargs: prepare_server_turn_start(
                    characters[9],
                    current.rift_monsters,
                    current,
                    decks[9],
                    **common,
                    **kwargs,
                )
            )
            runtime.turn_end_provider = (
                lambda current, **kwargs: prepare_server_turn_end(
                    characters[9],
                    current.rift_monsters,
                    current,
                    decks[9],
                    **common,
                    **kwargs,
                )
            )
            # Native SU interleaves NPCs and owners. Voluntarily end those
            # actual turns and consume their ACKs rather than changing order.
            for _ in range(len(fight.actors)):
                if fight.current.id == identity:
                    break
                current = fight.current
                if current.controlled:
                    from wakfu_server.combat_timeline_snapshot import current_wire_turn

                    runtime.end_turn(
                        current.owner_id, current.id, current_wire_turn(fight)
                    )
                else:
                    from wakfu_server.combat_automatic_npc_turn import (
                        requires_automatic_npc_turn_end,
                    )

                    end = (
                        runtime.end_automatic_npc_turn
                        if requires_automatic_npc_turn_end(fight, current)
                        else runtime.end_server_turn
                    )
                    end(current.id, fight.turn_id)
                self.assertIsNotNone(runtime.awaiting_ack)
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                fight = runtime.fight
            self.assertEqual(fight.current.id, identity)
            original = snapshot(fight)
            current_before = None if fight.current is None else fight.current.id
            order_before = tuple(fight.order)
            withdrawal = plan(
                Session(account, identity, "component", 1134, 1), fight, runtime
            )
            self.assertEqual(snapshot(fight), original)
            fight, runtime = withdrawal.fight, withdrawal.runtime
            self.assertTrue(fight.actors[identity].pve_withdrawn)
            self.assertNotIn(
                identity, {actor.id for actor in native_actor_population(fight)}
            )
            self.assertTrue(
                withdrawal.turn_changed,
                (
                    identity,
                    current_before,
                    order_before,
                    fight.turn_index,
                    fight.turn_id,
                ),
            )
            self.assertTrue(
                any(opcode == 13482 for opcode, _ in withdrawal.public_packets)
            )
            persisted = json.loads(json.dumps(snapshot(fight)))
            fight.native_retained_departure_sources = persisted[
                "native_retained_departure_sources"
            ]
            self.assertTrue(
                any(
                    uid in fight.native_owned_group_effects
                    and fight.native_owned_group_effects[uid]["invocation"]["target_id"]
                    == 9
                    for uid in retained
                )
            )
        self.assertEqual(
            {actor.id for actor in native_actor_population(fight) if actor.controlled},
            {9},
        )


if __name__ == "__main__":
    unittest.main()
