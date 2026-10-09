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


def shared_fixture(*, native_qi=False):
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
        fight = Fight(
            template.id,
            [withdrawn, template.actors[-7], actor],
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
    fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    return first, second, monster, fight, second_deck


class WithdrawnOrdinaryAuthorityTests(unittest.TestCase):
    def test_owned_reconnect_omits_only_certified_withdrawal_and_keeps_history(self):
        from types import SimpleNamespace

        from wakfu_server.combat_pve_departure import retired_pve_actor_ids
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
            actor_payload=lambda *_args: (b"stats", b"effects"),
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


if __name__ == "__main__":
    unittest.main()
