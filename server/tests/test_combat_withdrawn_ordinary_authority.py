"""Withdrawn PvE owners remain history, never active effect targets."""
import random
import struct
import unittest
from copy import deepcopy

from wakfu_server.combat_melee import execute_unarmed
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_state import Actor
from wakfu_server.spells import encode_deck
import test_combat_spell_transaction as spell_fixtures
from wakfu_server.combat_actor_snapshot import build_player_snapshot


def shared_fixture(*, native_qi=False, initialize_start=False):
    fixture = spell_fixtures.SpellTransactionTests()
    first, monster, fight = fixture.native_server_fixture(15, 1, native_qi=native_qi)
    first_cell = (-8, -7, -1) if native_qi else (-1, 0, 0)
    second_cell = (-7, -7, -1) if native_qi else (0, 0, 0)
    monster_cell = (-6, -7, -1) if native_qi else (1, 0, 0)
    first.update(account_id=3, x=first_cell[0], y=first_cell[1], z=first_cell[2])
    withdrawn = fight.actors[7]
    withdrawn.position = first_cell
    if not native_qi:
        withdrawn.pve_withdrawn = True
        withdrawn.hp = 0

    second = deepcopy(first)
    second.update(
        id=8,
        account_id=4,
        x=second_cell[0],
        y=second_cell[1],
        z=second_cell[2],
        builds={},
    )
    second_deck = encode_deck([6266], [])
    resources = dict(ap=6, mp=3, wp=6, initiative=20)
    actor = Actor(
        8,
        0,
        second_cell,
        second["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        1,
        4,
        True,
        max_hp=second["max_hp"],
        direction=0,
    )
    build_player_snapshot(
        second,
        actor,
        wp_current=resources["wp"],
        wp_maximum=resources["wp"],
        running_effects=(),
    ).install(actor)
    actor.native_resource_numeric_observers = {4: ()}
    if native_qi:
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        template = fight
        participants = [withdrawn, template.actors[-7], actor]
        if initialize_start:
            # Construct genuinely fresh participants before the production
            # placement snapshot initializer; template snapshots are immutable.
            participants = [
                Actor(
                    item.id,
                    item.team,
                    item.position,
                    item.hp,
                    item.ap,
                    item.mp,
                    item.initiative,
                    item.effective_level,
                    item.owner_id,
                    item.controlled,
                    max_hp=item.max_hp,
                    direction=item.direction,
                )
                for item in participants
            ]
        fight = Fight(
            template.id,
            participants,
            template.walkable,
            {0: {first_cell, second_cell}, 1: {monster_cell}},
            template.edges,
        )
        fight.native_qi_snapshot = deepcopy(template.native_qi_snapshot)
        fight.native_qi_surface_provenance = deepcopy(
            template.native_qi_surface_provenance
        )
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        if initialize_start:
            from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots

            # Use the placement producer's complete snapshot/QI/UID boundary
            # before class initialization creates its first retained effects.
            initialize_fight_snapshots(
                fight,
                characters={7: first, 8: second},
                monsters={-7: monster},
                wp_resources={identity: (6, 6) for identity in fight.actors},
                running_effects={identity: () for identity in fight.actors},
                initial_effect_uid=1,
            )
        else:
            install_fresh_actor_slots(
                fight,
                prepare_fresh_actor_slots(
                    fight,
                    physical_radii={
                        identity: item.physical_radius
                        for identity, item in fight.actors.items()
                    },
                ),
            )
        fight.ready(3)
        fight.ready(4)
        if initialize_start:
            from wakfu_server.combat_server_spell import prepare_server_initialization

            source_monster = dict(
                monster,
                x=monster_cell[0],
                y=monster_cell[1],
                z=monster_cell[2],
                direction=3,
                wp=6,
                max_wp=6,
                level=1,
            )
            characters = {7: first, 8: second}
            decks = {7: encode_deck([6266], []), 8: second_deck}
            fight, _ = prepare_server_initialization(
                first,
                {-7: source_monster},
                fight,
                3,
                decks[7],
                action_id=1,
                player_characters=characters,
                deck_blobs=decks,
                rng=random.Random(11),
            )
            fight, _ = prepare_server_initialization(
                second,
                {-7: source_monster},
                fight,
                4,
                decks[8],
                action_id=2,
                fight_start=True,
                player_characters=characters,
                deck_blobs=decks,
                rng=random.Random(12),
            )
        from wakfu_server.combat_pve_withdraw import plan
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_shared import Session

        fight = plan(
            Session(3, 7, "owner", 527, 0), fight, RuntimeMessages(fight)
        ).fight
    else:
        fight.actors[8] = actor
        fight.actors[-7].position = monster_cell
        fight.placement[0].update({first_cell, second_cell})
        fight.placement[1].add(monster_cell)
    monster.update(
        x=monster_cell[0],
        y=monster_cell[1],
        z=monster_cell[2],
        direction=3,
        wp=6,
        max_wp=6,
        level=1,
    )
    fight.order = [8, -7]
    fight.turn_index = 0
    fight.turn_id = 1
    fight._check_positions()
    if not initialize_start:
        fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    return first, second, monster, fight, second_deck


class WithdrawnOrdinaryAuthorityTests(unittest.TestCase):
    def test_owned_reconnect_omits_only_certified_withdrawal_and_keeps_history(self):
        from types import SimpleNamespace

        from wakfu_server.combat_pve_departure import retired_pve_actor_ids
        from wakfu_server.combat_actor import actor_effects
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_wire import arena, decode_bootstrap

        _first, _second, _monster, fight, _deck = shared_fixture(native_qi=True)
        withdrawn = fight.actors[7]
        self.assertTrue(withdrawn.pve_withdrawn)
        self.assertEqual(retired_pve_actor_ids(fight), {7})

        shared = SimpleNamespace(
            fight=fight,
            map_id=1134,
            runtime=RuntimeMessages(fight),
            join_context={
                "arena": arena(1134, 0, fight.walkable, fight.placement),
                "terrain_effect_id": 378,
                "terrain_instance_id": -300,
                "leaders": {0: 8, 1: -7},
            },
            ack=SimpleNamespace(turn=None, received=set()),
        )
        packets = owned_snapshot(
            fight,
            shared,
            SimpleNamespace(account_id=4),
            actor_payload=lambda *_args: (b"stats", actor_effects()),
        )

        bootstrap = decode_bootstrap(
            next(body for opcode, body in packets if opcode == 12847)
        )
        participant_ids = {row["actor_id"] for row in bootstrap["participants"]}
        self.assertEqual(participant_ids, {8, -7})
        self.assertNotIn(7, participant_ids)
        self.assertIn(7, fight.actors)  # Historical actor remains in the encounter.
        self.assertEqual(retired_pve_actor_ids(fight), {7})
        for opcode, payload in packets:
            if opcode in {13912, 12873}:
                self.assertNotEqual(struct.unpack_from(">q", payload, 4)[0], 7)

    def test_withdrawal_synchronizes_historical_actor_hp_snapshot(self):
        from wakfu_server.combat_pve_withdraw import plan
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        first, _second, _monster, fight, _deck = shared_fixture()
        fight.phase = "placement"
        fight.order = []
        fight.ready_owners.clear()
        withdrawn = fight.actors[7]
        withdrawn.pve_withdrawn = False
        withdrawn.owner_id = 3
        withdrawn.hp = withdrawn.effect_stats[1]
        fight.actors[8].owner_id = 4
        runtime = RuntimeMessages(fight)

        result = plan(Session(3, 7, "owner", 527, 0), fight, runtime)
        actor = result.fight.actors[7]

        self.assertEqual(actor.hp, 0)
        self.assertEqual(actor.effect_stats[1], 0)
        self.assertTrue(actor.pve_withdrawn)
        self.assertTrue(snapshot_characteristics(actor))

    def test_remaining_owner_can_cast_and_withdrawn_owner_is_not_a_target(self):
        first, second, monster, fight, deck = shared_fixture(native_qi=True)
        body = struct.pack(">qqiih", 8, (8 << 32) | 6266, *fight.actors[-7].position)
        transaction = prepare_server_spell(
            body,
            second,
            {-7: monster},
            fight,
            4,
            deck,
            action_id=1,
            line_of_sight=lambda *_args: True,
            critical=False,
            player_characters={8: second},
            deck_blobs={8: deck},
            rng=random.Random(1),
        )
        self.assertEqual(transaction.plan["actor_id"], 8)
        self.assertLess(transaction.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertEqual(transaction.fight.actors[7].hp, 0)
        self.assertTrue(transaction.fight.actors[7].pve_withdrawn)

        # A later legal cast centered on the withdrawn character's old cell
        # cannot restore it as a target or emit a hit against that actor.
        _first, second_fresh, monster_fresh, fight_fresh, deck_fresh = shared_fixture(
            native_qi=True
        )
        no_target = struct.pack(
            ">qqiih", 8, (8 << 32) | 6266, *fight_fresh.actors[7].position
        )
        retired_cast = prepare_server_spell(
            no_target,
            second_fresh,
            {-7: monster_fresh},
            fight_fresh,
            4,
            deck_fresh,
            action_id=2,
            line_of_sight=lambda *_args: True,
            critical=False,
            player_characters={8: second_fresh},
            deck_blobs={8: deck_fresh},
            rng=random.Random(2),
        )
        self.assertEqual(retired_cast.fight.actors[7].hp, 0)
        self.assertTrue(retired_cast.fight.actors[7].pve_withdrawn)
        self.assertFalse(
            any(event.get("target_id") == 7 for event in retired_cast.events)
        )

    def test_remaining_owner_can_use_native_unarmed_attack(self):
        _, second, monster, fight, deck = shared_fixture(native_qi=True)
        monster_cell = monster["x"], monster["y"], monster["z"]
        withdrawn_cell = fight.actors[7].position
        body = struct.pack(">qqbiih", 8, -1, 15, *monster_cell)
        with self.assertRaisesRegex(ValueError, "Melee requires"):
            # The withdrawn actor's cell cannot become a target; control below proves the same
            # setup can attack it. A withdrawn actor itself is never a melee
            # target because it has zero HP and is excluded from the roster.
            execute_unarmed(
                struct.pack(">qqbiih", 8, -1, 15, *withdrawn_cell),
                second,
                [monster],
                fight,
                4,
                unarmed=True,
                wp_current=6,
                wp_maximum=6,
                action_id=1,
                effect_uid=1,
                critical_chance=0,
                caster_running_effects=[],
                target_running_effects=[],
                caster_bonuses={},
                target_bonuses={},
                mitigate=lambda value, *_args: value,
                rng=random.Random(3),
                prepare_only=True,
                player_characters={8: second},
                deck_blobs={8: deck},
            )

        transaction = execute_unarmed(
            body,
            second,
            [monster],
            fight,
            4,
            unarmed=True,
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            caster_running_effects=[],
            target_running_effects=[],
            caster_bonuses={},
            target_bonuses={},
            mitigate=lambda value, *_args: value,
            rng=random.Random(3),
            prepare_only=True,
            player_characters={8: second},
            deck_blobs={8: deck},
        )
        self.assertLess(transaction.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertEqual(transaction.fight.actors[7].hp, 0)
        self.assertTrue(transaction.fight.actors[7].pve_withdrawn)

    def test_unregistered_summon_still_fails_closed(self):
        from wakfu_server.combat_server_spell import server_runtime

        _, second, monster, fight, deck = shared_fixture()
        summon = Actor(99, 0, (0, 1, 0), 20, 3, 3, 1, 1, 4, False)
        fight.actors[99] = summon
        fight.placement[0].add((0, 1, 0))
        fight.walkable.add((0, 1, 0))
        fight._check_positions()
        factory, adapter = server_runtime(
            second,
            {-7: monster},
            deck,
            action_id=1,
            critical=False,
            player_characters={8: second},
            deck_blobs={8: deck},
            rng=random.Random(4),
        )
        dispatcher, _packets = factory(fight, {"spell_id": 6266, "evaluation_level": 1})
        with self.assertRaisesRegex(ValueError, "roster changed"):
            adapter.targets(fight, {}, {}, None)
        self.assertIsNotNone(dispatcher)

    def test_withdrawn_registered_summon_has_no_active_authority(self):
        from wakfu_server.combat_summon import RegisteredSummonAuthority

        _, _second, _monster, fight, _deck = shared_fixture()
        summon = Actor(99, 0, (0, 1, 0), 20, 3, 3, 1, 1, 4, False)
        summon.pve_withdrawn = True
        fight.actors[99] = summon
        fight.native_summon_registrations = {99: {"actor_id": 99, "authority": {}}}
        authority = RegisteredSummonAuthority(lambda *_args: None)
        with self.assertRaisesRegex(ValueError, "Withdrawn PvE actor"):
            authority(fight, summon)

    @staticmethod
    def population_authority(first, second, monster, deck, *, retain_withdrawn):
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority

        characters = {8: second}
        if retain_withdrawn:
            characters[7] = first
        return OrdinaryActorAuthority(
            characters=characters,
            monsters={-7: monster},
            decks={identity: [6266] for identity in characters},
            excluded_decks={identity: [] for identity in characters},
            deck_blobs={identity: deck for identity in characters},
        )

    def test_full_and_certified_pruned_sources_preserve_active_authority_and_history(
        self,
    ):
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_pve_departure import retired_pve_actor_ids

        for retain_withdrawn in (True, False):
            with self.subTest(retain_withdrawn=retain_withdrawn):
                first, second, monster, fight, deck = shared_fixture(native_qi=True)
                authority = self.population_authority(
                    first, second, monster, deck, retain_withdrawn=retain_withdrawn
                )
                before = deepcopy(source_snapshot(fight))
                source_ids = set(authority.characters) | set(authority.monsters)
                self.assertTrue(authority(fight, fight.actors[8]).is_player)
                self.assertFalse(authority(fight, fight.actors[-7]).is_player)
                self.assertEqual(source_snapshot(fight), before)
                self.assertEqual(
                    set(authority.characters) | set(authority.monsters), source_ids
                )
                self.assertEqual(set(fight.actors), {7, 8, -7})
                self.assertEqual(retired_pve_actor_ids(fight), {7})
                self.assertEqual(fight.actors[7].hp, 0)
                with self.assertRaisesRegex(ValueError, "Withdrawn PvE actor"):
                    authority(fight, fight.actors[7])
                self.assertEqual(source_snapshot(fight), before)

    def test_remaining_player_and_npc_end_turn_with_full_and_pruned_owned_sources(self):
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import prepare_server_turn_end
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        for retain_withdrawn in (True, False):
            for current in (8, -7):
                with self.subTest(retain_withdrawn=retain_withdrawn, current=current):
                    first, second, monster, fight, deck = shared_fixture(
                        native_qi=True, initialize_start=True
                    )
                    self.assertTrue(fight.native_start_event_delivered)
                    self.assertEqual(set(fight.native_class_initializations), {7, 8})
                    fight.turn_index = fight.order.index(current)
                    historical = deepcopy(source_snapshot(fight)["actors"]["7"])
                    population = set(fight.actors)
                    characters = {8: second}
                    if retain_withdrawn:
                        characters[7] = first
                    decks = {identity: deck for identity in characters}
                    provider_calls = []

                    def turn_end(preview, *, actor_id, action_id):
                        before = deepcopy(source_snapshot(preview))
                        prepared, packets = prepare_server_turn_end(
                            second,
                            {-7: monster},
                            preview,
                            deck,
                            actor_id=actor_id,
                            action_id=action_id,
                            player_characters=characters,
                            deck_blobs=decks,
                            rng=random.Random(13),
                        )
                        self.assertEqual(source_snapshot(preview), before)
                        self.assertIsNot(prepared, preview)
                        provider_calls.append(actor_id)
                        return prepared, packets

                    runtime = RuntimeMessages(
                        fight, turn_end_provider=turn_end, clock=lambda: 0.0
                    )
                    previous_turn = fight.turn_id
                    if current == 8:
                        packets = runtime.end_turn(4, current, current_wire_turn(fight))
                    else:
                        packets = runtime.end_server_turn(current, previous_turn)
                    self.assertEqual(provider_calls, [current])
                    self.assertEqual(
                        [opcode for opcode, _ in packets][-2:], [12502, 13420]
                    )
                    end = next(
                        payload for opcode, payload in packets if opcode == 12502
                    )
                    self.assertEqual(
                        struct.unpack_from(">qii", end, 12), (current, -1, 0)
                    )
                    self.assertEqual(fight.current.id, -7 if current == 8 else 8)
                    self.assertGreater(fight.turn_id, previous_turn)
                    self.assertEqual(runtime.awaiting_ack, previous_turn)
                    self.assertEqual(set(fight.actors), population)
                    self.assertEqual(source_snapshot(fight)["actors"]["7"], historical)
                    self.assertNotIn(7, fight.order)
                    self.assertTrue(runtime.pending)
                    self.assertTrue(
                        runtime.acknowledge_turn(struct.pack(">i", previous_turn))
                    )
                    self.assertIsNone(runtime.awaiting_ack)
                    self.assertEqual(runtime.pending, [])

    def test_foreign_withdrawn_flag_and_unregistered_actor_cannot_bypass_population(
        self,
    ):
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        for withdrawn in (False, True):
            with self.subTest(withdrawn=withdrawn):
                first, second, monster, fight, deck = shared_fixture(native_qi=True)
                authority = self.population_authority(
                    first, second, monster, deck, retain_withdrawn=False
                )
                foreign = Actor(99, 0, (0, 1, 0), 20, 3, 3, 1, 1, 4, False)
                foreign.pve_withdrawn = withdrawn
                if withdrawn:
                    foreign.hp = 0
                fight.actors[99] = foreign
                before = deepcopy(source_snapshot(fight))
                with self.assertRaisesRegex(ValueError, "roster changed"):
                    authority(fight, fight.actors[8])
                self.assertEqual(source_snapshot(fight), before)
                self.assertIn(99, fight.actors)

    def test_uncertified_pruned_withdrawn_source_is_not_silently_accepted(self):
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        first, second, monster, fight, deck = shared_fixture()
        authority = self.population_authority(
            first, second, monster, deck, retain_withdrawn=False
        )
        before = deepcopy(source_snapshot(fight))
        self.assertTrue(fight.actors[7].pve_withdrawn)
        self.assertFalse(getattr(fight, "native_pve_departures", {}))
        with self.assertRaisesRegex(ValueError, "roster changed"):
            authority(fight, fight.actors[8])
        self.assertEqual(source_snapshot(fight), before)

    def test_stale_owned_departure_and_missing_actor_source_fail_without_mutation(self):
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        for malformed in ("stale_departure", "missing_actor"):
            with self.subTest(malformed=malformed):
                first, second, monster, fight, deck = shared_fixture(native_qi=True)
                authority = self.population_authority(
                    first,
                    second,
                    monster,
                    deck,
                    retain_withdrawn=malformed == "missing_actor",
                )
                if malformed == "stale_departure":
                    fight.native_pve_departures[7]["source"] = "foreign"
                    reason = "departure authority"
                else:
                    del fight.actors[7]
                    reason = "roster changed"
                before = deepcopy(source_snapshot(fight))
                with self.assertRaisesRegex(ValueError, reason):
                    authority(fight, fight.actors[8])
                self.assertEqual(source_snapshot(fight), before)

    def test_known_ordinary_ko_and_native_offplay_keep_existing_life_semantics(self):
        import test_combat_ordinary_authority as native_life

        # Reuse the original creation/death-provenance fixture and its real
        # owned death transition, not a fabricated withdrawal for an HP0 actor.
        fixture = native_life.OrdinaryAuthorityTests(
            methodName="test_selector_life_uses_owned_creation_and_departure_registration"
        )
        fixture.setUpClass()
        fixture.setUp()
        try:
            fixture.test_selector_life_uses_owned_creation_and_departure_registration()
            self.assertEqual(fixture.preview.actors[-7].hp, 0)
            self.assertFalse(
                getattr(fixture.preview.actors[-7], "pve_withdrawn", False)
            )
            self.assertIn(-7, fixture.authority.monsters)
        finally:
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
