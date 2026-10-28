"""Natural owned Jamjam creation and paid death across three native owners."""
import os
import random
import struct
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as transaction_fixtures
from wakfu_server.combat_actor import (
    actor_effects,
    actual_actor_stats,
    actual_monster_actor_stats,
)
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_heroes import player_actor
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_state import Fight
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.combat_summon_stats import registered_summon_stats
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_timeline_snapshot import current_wire_turn
import test_combat_shared_timeline_recovery as timeline_fixture
from wakfu_server.equipment_stats import effective_character
from wakfu_server.health import maximum
from wakfu_server.spells import encode_deck


@patch.dict(
    os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"}
)
class JamjamPaidDeathMultiplayerTests(unittest.TestCase):
    def test_natural_invocation_paid_lethal_damage_three_owner_death_and_next_turn(
        self,
    ):
        self._run_native_scenario("paid")

    def test_natural_current_jamjam_nova_self_death_publishes_successor(self):
        self._run_native_scenario("nova")

    def _run_native_scenario(self, mode):
        def trace(message):
            if os.environ.get("WAKFU_JAMJAM_TEST_TRACE") == "1":
                print(message, flush=True)

        trace("fixture")
        (
            character,
            monster,
            template,
        ) = transaction_fixtures.SpellTransactionTests().native_server_fixture(
            2,
            30,
            full_health=True,
            native_qi=True,
            target_ref=4,
            target_level=8,
            target_distance=4,
            variation_seed=17,
        )
        character.update(sex=0, instance_id=0, x=-8, y=-7, z=-1)
        characters = {7: character}
        monsters = {-7: dict(monster, level=8)}
        decks = {7: encode_deck([7307, 7317, 7323] if mode == "nova" else [7307, 7317])}
        positions = ((-9, -6, -1), (-8, -8, -1))
        summon_cell = (-8, -6, -1)
        for cell in (*positions, summon_cell):
            self.assertIn(cell, template.walkable)
        # Reuse only the template's fresh native actors and frozen geometry;
        # class initialization and native Ready run below through the Registry.
        # The older reusable template already called Fight.ready; its actors
        # must start at zero turns in this new, still-unreadied encounter.
        for actor in template.actors.values():
            actor.turn_count = 0
        fight = Fight(
            78014,
            list(template.actors.values()),
            template.walkable,
            {
                0: {template.actors[7].position, *positions},
                1: {template.actors[-7].position},
            },
            template.edges,
        )
        fight.native_qi_snapshot = template.native_qi_snapshot
        fight.native_qi_surface_provenance = template.native_qi_surface_provenance
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight,
                physical_radii={a.id: a.physical_radius for a in fight.actors.values()},
            ),
        )
        fight.native_effect_uid_next = 1
        fight.native_obstacle_cells = frozenset()
        sessions = [
            Session(account, identity, "jamjam-native-" + str(account), 1134, 0)
            for account, identity in ((3, 7), (4, 8), (5, 9))
        ]
        registry = Registry(lambda session: session in sessions)

        def stats(actor, current):
            if actor.id in getattr(current, "native_summon_registrations", {}):
                return registered_summon_stats(actor, current, 1134)
            encoder = (
                actual_actor_stats if actor.controlled else actual_monster_actor_stats
            )
            source = characters[actor.id] if actor.controlled else monsters[actor.id]
            return encoder(
                source,
                actor,
                current.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )

        def payload(current, actor, owner):
            return stats(actor, current), actor_effects()

        arena = local_arena(
            1134,
            7,
            template.actors[7].position,
            template.actors[-7].position,
            relocate_monsters=False,
            variation_seed=17,
        )
        arena = dict(arena, placement_cells=fight.placement)
        shared = registry.register(
            fight,
            sessions[0],
            join_context=dict(
                arena=arena,
                terrain_effect_id=46,
                terrain_instance_id=-300,
                leaders={0: 7, 1: -7},
                duration_ms=60000,
                actor_payload=payload,
                frozen_company_members=(7, 8, 9),
            ),
        )
        for session, breed, cell in zip(sessions[1:], (4, 3), positions):
            level = 200 if breed == 4 else 30
            source = effective_character(
                dict(
                    id=session.character_id,
                    account_id=session.account_id,
                    breed=breed,
                    level=level,
                    hp=maximum(breed, level),
                    max_hp=maximum(breed, level),
                    map_id=1134,
                    instance_id=0,
                    x=cell[0],
                    y=cell[1],
                    z=cell[2],
                    sex=0,
                    builds={},
                    inventory_items=[],
                )
            )
            characters[source["id"]] = source
            decks[source["id"]] = encode_deck([4589] if breed == 4 else [])
            registry.join(
                session,
                struct.pack(">qB", 7, 0),
                player_actor(source, 0),
                actor_payload=payload,
                bootstrap_packets=CombatSessionAdapter.placement_bootstrap,
            )
            self.assertEqual(shared.fight.actors[source["id"]].position, cell)
        provider = OwnedExpirationFactory(
            characters=characters,
            monsters=monsters,
            decks=decks,
            actor_id=7,
            area_callbacks=True,
        )

        def initialize(preview, action_id):
            packets = []
            for index, source in enumerate(characters.values()):
                preview, own = prepare_server_initialization(
                    source,
                    monsters,
                    preview,
                    source["account_id"],
                    decks[source["id"]],
                    action_id=action_id,
                    rng=random.Random(17),
                    fight_start=index == 2,
                    player_characters=characters,
                    deck_blobs=decks,
                )
                packets.extend(own)
            return preview, packets

        for session in sessions:

            def ready(preview, runtime):
                prepared, runtime, packets = prepare_ready(
                    preview,
                    session.account_id,
                    True,
                    initialize=initialize,
                    stats_serializer=lambda actor: stats(actor, preview),
                    effects_serializer=actor_effects,
                    runtime_stats_serializer=stats,
                    turn_start_provider=provider.turn_start,
                    turn_end_provider=provider.turn_end,
                    expiration_runtime_factory=provider,
                )
                return Transition(prepared, runtime, packets)

            registry.execute(
                fight.id, session, session.character_id, ready, require_turn=False
            )
        self.assertEqual(shared.fight.phase, "active")
        self.assertEqual(len(shared.participants), 3)
        trace("native Ready completed")

        def drain():
            return {
                s.account_id: tuple(
                    p for batch in registry.drain(fight.id, s) for p in batch.packets
                )
                for s in sessions
            }

        def acknowledge():
            counter = shared.runtime.awaiting_ack
            if counter is None:
                return None

            def release(preview, runtime, body):
                return Transition(preview, runtime, runtime.acknowledge_turn(body))

            results = [
                registry.acknowledge(fight.id, s, struct.pack(">i", counter), release)
                for s in sessions
            ]
            self.assertEqual(results, [False, False, True])
            self.assertIsNone(shared.runtime.awaiting_ack)
            return results

        def end_turn():
            actor = shared.fight.current
            trace("end turn " + str(actor.id))

            def operation(preview, runtime):
                packets = (
                    runtime.end_turn(
                        actor.owner_id, actor.id, current_wire_turn(preview)
                    )
                    if actor.controlled
                    else runtime.end_server_turn(actor.id, preview.turn_id)
                )
                return Transition(runtime.fight, runtime, packets)

            if actor.controlled:
                owner = next(s for s in sessions if s.account_id == actor.owner_id)
                registry.execute(fight.id, owner, actor.id, operation)
            else:
                registry.execute_server(
                    fight.id, actor.id, operation, expected_sequence=shared.sequence
                )
            return acknowledge()

        def turn(identity):
            for _ in range(20):
                if shared.fight.current.id == identity:
                    return
                end_turn()
            self.fail("Native timeline did not reach actor " + str(identity))

        def cast(identity, reference, target, *, auto_ack=True, check_ap=True):
            trace("cast " + str(reference) + " by " + str(identity))
            actor = shared.fight.actors[identity]
            controller = (
                identity if identity in characters else actor.native_controller_id
            )
            source = characters[controller]
            before_ap = actor.ap
            owner = next(s for s in sessions if s.account_id == source["account_id"])

            def operation(preview, runtime):
                def los(origin, destination, current):
                    return authoritative_visible(
                        1134,
                        origin,
                        destination,
                        current,
                        blocking_footprints={
                            a.id: footprint(a.position, a.physical_radius)
                            for a in current.actors.values()
                            if a.hp > 0
                        },
                    )

                tx = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        identity,
                        reference
                        if reference >= 7348
                        else (identity << 32) | reference,
                        *target
                    ),
                    source,
                    monsters,
                    preview,
                    owner.account_id,
                    decks[controller],
                    action_id=runtime.action_id + 1,
                    line_of_sight=los,
                    critical=False,
                    rng=random.Random(17),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                packets = commit_spell_transaction(runtime, tx, stats_serializer=stats)
                return Transition(runtime.fight, runtime, packets)

            registry.execute(fight.id, owner, identity, operation)
            if check_ap:
                self.assertLess(shared.fight.actors[identity].ap, before_ap)
            if auto_ack:
                acknowledge()
                return drain()
            return None

        turn(7)
        before_ids = set(shared.fight.actors)
        cast(7, 7350, summon_cell)
        born = set(shared.fight.actors) - before_ids
        self.assertEqual(len(born), 1)
        jamjam = born.pop()
        actor = shared.fight.actors[jamjam]
        self.assertEqual(actor.native_summon_source["ref"], 1620)
        self.assertEqual(actor.native_controller_id, 7)
        self.assertEqual(actor.owner_id, 3)
        self.assertEqual(actor.position, summon_cell)
        natural_hp = actor.hp
        trace("natural Jamjam HP " + str(natural_hp))
        self.assertGreater(natural_hp, 1)
        self.assertEqual(actor.hp, actor.max_hp)
        self.assertTrue(actor_action_book(actor)["actions"])
        slot = actor.native_obstacle_id
        if mode == "nova":
            # Prefund the owner through a real Osamodas spell, then let the
            # newly summoned actor receive its natural server-controlled turn.
            turn(7)
            owner_wp_before_prefund = shared.fight.actors[7].effect_stats[4]
            owner_wp_maximum = shared.fight.actors[7].effect_maxima[4]
            cast(7, 7323, shared.fight.actors[7].position, check_ap=False)
            self.assertLess(shared.fight.actors[7].effect_stats[4], owner_wp_maximum)
            self.assertGreaterEqual(owner_wp_before_prefund, 0)
            predecessor_id = shared.fight.current.id
            self.assertEqual(predecessor_id, 7)
            turn(jamjam)
            self.assertEqual(shared.fight.current.id, jamjam)
            self.assertEqual(shared.fight.current.native_controller_id, 7)
            # Drop the predecessor turn's completed packets so the next drain
            # isolates Nova's own death and ACK-gated successor publication.
            drain()
            owner_wp = shared.fight.actors[7].effect_stats[4]
            owner_hp = shared.fight.actors[7].hp
            owner_ap = shared.fight.actors[7].ap
            owner_mp = shared.fight.actors[7].mp
            preserved = {
                identity: (
                    shared.fight.actors[identity].hp,
                    shared.fight.actors[identity].ap,
                    shared.fight.actors[identity].mp,
                    tuple(sorted(shared.fight.actors[identity].effect_stats.items())),
                )
                for identity in (8, 9, -7)
            }
            cast(
                jamjam,
                7355,
                shared.fight.actors[7].position,
                auto_ack=False,
                check_ap=False,
            )
            packets = drain()
            self.assertIn(jamjam, retired_summon_ids(shared.fight))
            self.assertEqual(shared.fight.actors[jamjam].native_obstacle_id, -1)
            self.assertNotIn(jamjam, shared.fight.order)
            self.assertIsNone(current_registry(shared.fight).slots[slot])
            self.assertEqual(shared.fight.actors[7].hp, owner_hp)
            self.assertEqual(
                shared.fight.actors[7].effect_stats[4],
                min(owner_wp + 3, shared.fight.actors[7].effect_maxima[4]),
            )
            # Native spell diagnostics identify all 7355 resource costs as
            # zero; the only resource change is Nova's real owner WP effect.
            self.assertEqual(shared.fight.actors[7].mp, owner_mp)
            for identity, state in preserved.items():
                actor = shared.fight.actors[identity]
                self.assertEqual(
                    (
                        actor.hp,
                        actor.ap,
                        actor.mp,
                        tuple(sorted(actor.effect_stats.items())),
                    ),
                    state,
                )
            self.assertEqual(shared.fight.actors[7].ap, owner_ap)
            self.assertEqual(shared.fight.phase, "active")
            self.assertNotEqual(shared.fight.current.id, jamjam)
            for account, frames in packets.items():
                opcodes = [opcode for opcode, _ in frames]
                death_states = [
                    struct.unpack_from(">qB", body, len(body) - 9)[1]
                    for opcode, body in frames
                    if opcode == 12727
                    and struct.unpack_from(">qB", body, len(body) - 9)[0] == jamjam
                ]
                self.assertEqual(death_states, [2], (account, death_states))
                self.assertIn(12502, opcodes)
            # The state-2 death and final 12502 reach all owners first.
            # The first two real ACKs cannot publish the successor; only the
            # final owner ACK releases 12053/13337/13482.
            for account, frames in packets.items():
                opcodes = [opcode for opcode, _ in frames]
                self.assertIn(12502, opcodes, (account, opcodes))
                self.assertFalse(
                    any(op in opcodes for op in (12053, 13337, 13482)),
                    (account, opcodes),
                )
                death_index = next(
                    i
                    for i, (opcode, body) in enumerate(frames)
                    if opcode == 12727
                    and struct.unpack_from(">qB", body, len(body) - 9)[0] == jamjam
                )
                end_index = next(
                    i for i, (opcode, _) in enumerate(frames) if opcode == 12502
                )
                self.assertLess(death_index, end_index, (account, opcodes))
            counter = shared.runtime.awaiting_ack
            self.assertIsNotNone(counter)
            partial_ack_results = []
            successor_frames = {session.account_id: [] for session in sessions}
            for index, session in enumerate(sessions):

                def release(preview, runtime, body):
                    return Transition(preview, runtime, runtime.acknowledge_turn(body))

                result = registry.acknowledge(
                    fight.id, session, struct.pack(">i", counter), release
                )
                partial_ack_results.append(result)
                newly_queued = drain()
                for account, frames in newly_queued.items():
                    successor_frames[account].extend(frames)
                if index < len(sessions) - 1:
                    self.assertFalse(
                        any(
                            op in [opcode for opcode, _ in frames]
                            for frames in newly_queued.values()
                            for op in (12053, 13337, 13482)
                        ),
                        newly_queued,
                    )
            self.assertEqual(partial_ack_results, [False, False, True])
            self.assertIsNone(shared.runtime.awaiting_ack)
            for account, frames in successor_frames.items():
                opcodes = [opcode for opcode, _ in frames]
                self.assertEqual(opcodes.count(12053), 1, (account, opcodes))
                self.assertEqual(opcodes.count(13337), 1, (account, opcodes))
                self.assertEqual(opcodes.count(13482), 1, (account, opcodes))
                timeline_packet = next(
                    body for opcode, body in frames if opcode == 12053
                )
                decoded = timeline_fixture.decoded_timeline(timeline_packet)
                self.assertEqual(decoded["phase"], 2, (account, decoded))
                self.assertEqual(decoded["current"], shared.fight.current.id)
                self.assertLess(opcodes.index(12053), opcodes.index(13337))
                self.assertLess(opcodes.index(13337), opcodes.index(13482))
            successor = shared.fight.current.id
            self.assertNotEqual(successor, jamjam)
            turn(8)
            owner_eight_hp = shared.fight.actors[8].hp
            action_packets = cast(8, 4589, shared.fight.actors[8].position)
            self.assertEqual(shared.fight.actors[8].hp, owner_eight_hp)
            self.assertTrue(action_packets)
            end_turn()
            self.assertNotEqual(shared.fight.current.id, 8)
            self.proof = dict(
                mode="nova",
                jamjam=jamjam,
                successor=shared.fight.current.id,
                owner_wp_before=owner_wp,
                owner_wp_after=shared.fight.actors[7].effect_stats[4],
                owners=sorted(packets),
            )
            return
        # A lawful controlled turn proves a real summoned timeline entry.
        turn(jamjam)
        self.assertEqual(shared.fight.current.native_controller_id, 7)
        end_turn()
        paid_hits = 0
        death_packets = None
        while shared.fight.actors[jamjam].hp > 0 and paid_hits < 20:
            turn(8)
            previous_hp = shared.fight.actors[jamjam].hp
            caster_hp = shared.fight.actors[8].hp
            death_packets = cast(8, 4589, shared.fight.actors[8].position)
            paid_hits += 1
            self.assertLess(shared.fight.actors[jamjam].hp, previous_hp)
            self.assertEqual(shared.fight.actors[8].hp, caster_hp)
            if shared.fight.actors[jamjam].hp > 0:
                end_turn()
        self.assertEqual(shared.fight.actors[jamjam].hp, 0)
        self.assertIn(jamjam, retired_summon_ids(shared.fight))
        self.assertEqual(shared.fight.actors[jamjam].native_obstacle_id, -1)
        self.assertNotIn(jamjam, shared.fight.order)
        self.assertFalse(
            any(
                row is not None and tuple(row["identity"]) == ("actor", jamjam)
                for row in current_registry(shared.fight).serialized_slots()
            )
        )
        self.assertIsNone(current_registry(shared.fight).slots[slot])
        for account, packets in death_packets.items():
            states = [
                struct.unpack_from(">qB", body, len(body) - 9)[1]
                for opcode, body in packets
                if opcode == 12727
                and struct.unpack_from(">qB", body, len(body) - 9)[0] == jamjam
            ]
            # Registered summons retire directly with final fighter-state2;
            # the ordinary NPC's preliminary state0 does not belong here.
            self.assertEqual(states, [2], (account, states))
        self.assertGreater(shared.fight.actors[-7].hp, 0)
        self.assertEqual(shared.fight.phase, "active")
        self.assertEqual(end_turn(), [False, False, True])
        self.assertNotEqual(shared.fight.current.id, jamjam)
        turn(7)
        self.assertGreater(natural_hp, 1)
        self.assertGreater(paid_hits, 0)
        self.proof = dict(
            natural_hp=natural_hp,
            paid_hits=paid_hits,
            death_accounts=sorted(death_packets),
            next_actor=shared.fight.current.id,
        )
        trace(str(self.proof))
