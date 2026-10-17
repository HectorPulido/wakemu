"""Native Ouginak Wauwau summon, owned action book and retirement lifecycle."""
import os
import struct
import unittest
from random import Random
from unittest.mock import patch

from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
)
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.combat_summon_spellbook import actor_spellbook
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.equipment_stats import effective_character, combat_resources
from wakfu_server.health import maximum
from wakfu_server.spells import encode_deck


@patch.dict(
    os.environ,
    {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"},
)
class WauwauLifecycleTests(unittest.TestCase):
    def fixture(self, *, owner_level=90):
        origin = (-4, -18, 0)
        enemy_position = (-2, -18, 0)
        characters = {}
        decks = {}
        actors = []
        wp_resources = {}
        for identity, account, team, level, position, active in (
            (7, 3, 0, owner_level, origin, []),
            (8, 4, 1, 200, enemy_position, [6261, 6266]),
        ):
            character = effective_character(
                dict(
                    id=identity,
                    account_id=account,
                    breed=15,
                    level=level,
                    hp=maximum(15, level),
                    max_hp=maximum(15, level),
                    map_id=1134,
                    builds={},
                    inventory_items=[],
                )
            )
            resources = combat_resources(character)
            characters[identity] = character
            decks[identity] = encode_deck(active)
            actors.append(
                Actor(
                    identity,
                    team,
                    position,
                    character["hp"],
                    resources["ap"],
                    resources["mp"],
                    resources["initiative"],
                    level,
                    account,
                    True,
                    max_hp=character["max_hp"],
                )
            )
            wp_resources[identity] = (resources["wp"], resources["wp"])
        characters[7]["name"] = "Ouginak Wauwau owner"
        characters[8]["name"] = "Ouginak opponent"
        actors[0].direction = 0
        actors[1].direction = 3
        fight = Fight(
            78,
            actors,
            {
                (x, y, 0)
                for x in range(origin[0] - 6, origin[0] + 10)
                for y in range(origin[1] - 6, origin[1] + 7)
            },
            {0: {origin}, 1: {enemy_position}},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_qi_snapshot = dict(
            x=origin[0] - 6,
            y=origin[1] - 6,
            width=16,
            height=13,
            cell_masks=[128] * (16 * 13),
        )
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources=wp_resources,
            running_effects={identity: () for identity in characters},
            initial_effect_uid=1,
        )
        fight.ready(3)
        fight.ready(4)
        fight.native_obstacle_cells = frozenset()
        return characters, decks, fight

    def finish_current(self, characters, decks, fight, action_id):
        actor_id = fight.current.id
        preview, packets = prepare_server_turn_end(
            characters[7],
            {},
            fight,
            decks[7],
            actor_id=actor_id,
            action_id=action_id,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        actor = preview.actors[actor_id]
        if actor.controlled:
            preview.end_turn(actor.owner_id, actor_id, actor.turn_count)
        else:
            preview.end_server_turn(actor_id, preview.turn_id)
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        RuntimeMessages(preview).turn_started()
        return preview, packets

    def cast(self, characters, decks, fight, actor_id, uid, target, action_id):
        character = characters[7 if actor_id != 8 else 8]
        deck = decks[7 if actor_id != 8 else 8]
        owner_id = character["account_id"]
        line_of_sight = lambda source, destination, preview: authoritative_visible(
            character["map_id"],
            source,
            destination,
            preview,
            blocking_footprints={
                actor.id: footprint(actor.position, actor.physical_radius)
                for actor in preview.actors.values()
                if actor.hp > 0
            },
        )
        return prepare_server_spell(
            struct.pack(">qqiih", actor_id, uid, *target),
            character,
            {},
            fight,
            owner_id,
            deck,
            action_id=action_id,
            line_of_sight=line_of_sight,
            critical=False,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )

    def test_wauwau_book_control_death_retirement_and_reinvocation(self):
        characters, decks, fight = self.fixture()
        fight, _ = prepare_server_initialization(
            characters[7],
            {},
            fight,
            3,
            decks[7],
            action_id=1,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        fight, _ = prepare_server_initialization(
            characters[8],
            {},
            fight,
            4,
            decks[8],
            action_id=2,
            rng=Random(7),
            fight_start=True,
            player_characters=characters,
            deck_blobs=decks,
        )
        while fight.current.id != 7:
            fight, _ = self.finish_current(characters, decks, fight, 11)
        self.assertIn(6286, granted_spells(fight, 7))

        summon_cell = (-3, -18, 0)
        first = self.cast(characters, decks, fight, 7, 6286, summon_cell, 13)
        first_id = next(iter(set(first.fight.actors) - set(fight.actors)))
        wauwau = first.fight.actors[first_id]
        self.assertEqual(wauwau.native_summon_source["ref"], 4559)
        self.assertEqual(
            (wauwau.team, wauwau.controlled, wauwau.owner_id), (0, True, 3)
        )
        self.assertEqual(wauwau.native_controller_id, 7)
        self.assertEqual(
            {row["uid"] for row in wauwau.native_summon_action_book["actions"]},
            {6291, 6292, 6293, 6294},
        )
        self.assertEqual(set(actor_spellbook(wauwau).levels), {6291, 6292, 6293, 6294})
        registration = first.fight.native_summon_registrations[first_id]
        self.assertEqual(registration["controller_id"], 7)
        self.assertTrue(first.packets)

        # The caster retains its current turn; the exact fresh insertion gives
        # the registered summon the following controlled activation.
        fight = first.fight
        while fight.current.id != first_id:
            fight, _ = self.finish_current(characters, decks, fight, 15)
        controlled = self.cast(
            characters,
            decks,
            fight,
            first_id,
            6294,
            fight.actors[first_id].position,
            17,
        )
        self.assertEqual(controlled.plan["spell_id"], 6294)
        self.assertTrue(controlled.packets)

        fight = controlled.fight
        old_slot = fight.actors[first_id].native_obstacle_id
        killed = None
        action_id = 20
        for _ in range(4):
            while fight.current.id != 8:
                fight, _ = self.finish_current(characters, decks, fight, action_id)
                action_id += 1
            for spell in (6266, 6261):
                if fight.actors[first_id].hp <= 0:
                    break
                killed = self.cast(
                    characters,
                    decks,
                    fight,
                    8,
                    (8 << 32) | spell,
                    fight.actors[first_id].position,
                    action_id,
                )
                action_id += 1
                fight = killed.fight
            if fight.actors[first_id].hp <= 0:
                break
            fight, _ = self.finish_current(characters, decks, fight, action_id)
            action_id += 1
        self.assertIsNotNone(killed)
        self.assertEqual(fight.actors[first_id].hp, 0)
        self.assertIn(first_id, retired_summon_ids(fight))
        self.assertEqual(fight.actors[first_id].native_obstacle_id, -1)
        self.assertTrue(killed.packets)

        # Death releases the summon cell and its native QI slot, so the same
        # legal native cell can host a distinct fresh Wauwau on the next turn.
        last_summon_turn = fight.native_spell_usage["7"]["last"]["6286"]
        for action_id in range(22, 70):
            if (
                fight.current.id == 7
                and fight.native_table_turn - last_summon_turn >= 4
            ):
                break
            fight, _ = self.finish_current(characters, decks, fight, action_id)
        self.assertEqual(fight.current.id, 7)
        self.assertGreaterEqual(fight.native_table_turn - last_summon_turn, 4)
        second = self.cast(characters, decks, fight, 7, 6286, summon_cell, 70)
        second_ids = set(second.fight.actors) - set(fight.actors)
        self.assertEqual(len(second_ids), 1)
        second_id = next(iter(second_ids))
        self.assertNotEqual(second_id, first_id)
        self.assertEqual(second.fight.actors[second_id].position, summon_cell)
        self.assertIn(first_id, retired_summon_ids(second.fight))
        self.assertEqual(second.fight.actors[first_id].hp, 0)
        self.assertEqual(second.fight.actors[first_id].native_obstacle_id, -1)
        self.assertEqual(
            second.fight.actors[second_id].native_summon_source["ref"], 4559
        )
        self.assertEqual(second.fight.actors[second_id].native_obstacle_id, old_slot)

    def test_paid_fracture_ticks_after_target_movement_expires_at_end_and_real_bowwow_echo_is_passive_scoped(
        self,
    ):
        """Player poison use, actual paid companion, and a matched passive control."""
        import sys
        from pathlib import Path
        import test_combat_spell_transaction as native_fixture_module

        sys.path.insert(
            0, str(Path(native_fixture_module.__file__).resolve().parents[1] / "tools")
        )
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import validate_deck, owned_spell_records

        outcomes = {}
        for passive in (None, 6273):
            with self.subTest(passive=passive):
                characters, decks, old = self.fixture(owner_level=200)
                decks[7] = encode_deck([6269], [] if passive is None else [passive])
                validate_deck(decks[7], 15, characters[7]["level"])
                self.assertIn(
                    6269, {ref for _, ref, _ in owned_spell_records(characters[7])}
                )
                if passive is not None:
                    self.assertIn(
                        passive,
                        {ref for _, ref, _ in owned_spell_records(characters[7])},
                    )
                arena = local_arena(
                    1134,
                    7,
                    old.actors[7].position,
                    old.actors[8].position,
                    relocate_monsters=False,
                )
                resources = {
                    uid: combat_resources(character)
                    for uid, character in characters.items()
                }
                actors = [
                    Actor(
                        uid,
                        old.actors[uid].team,
                        old.actors[uid].position,
                        character["hp"],
                        resources[uid]["ap"],
                        resources[uid]["mp"],
                        resources[uid]["initiative"],
                        character["level"],
                        character["account_id"],
                        True,
                        max_hp=character["max_hp"],
                    )
                    for uid, character in characters.items()
                ]
                for actor in actors:
                    actor.direction = old.actors[actor.id].direction
                fight = Fight(
                    old.id,
                    actors,
                    arena["validated_cells"],
                    {0: {old.actors[7].position}, 1: {old.actors[8].position}},
                    arena["valid_edges"],
                )
                fight.native_qi_snapshot = {
                    key: arena[key]
                    for key in ("x", "y", "width", "height", "cell_masks")
                }
                fight.native_qi_surface_provenance = dict(
                    arena["native_qi_surface_provenance"]
                )
                freeze_terrain(fight)
                initialize_global_pv_collections(fight, (7, 8))
                initialize_fight_snapshots(
                    fight,
                    characters=characters,
                    monsters={},
                    wp_resources={
                        uid: (values["wp"], values["wp"])
                        for uid, values in resources.items()
                    },
                    running_effects={uid: () for uid in fight.actors},
                    initial_effect_uid=1,
                )
                fight.ready(3)
                fight.ready(4)
                rng = Random(7)
                common = dict(player_characters=characters, deck_blobs=decks)
                for identity in (7, 8):
                    fight, _ = prepare_server_initialization(
                        characters[identity],
                        {},
                        fight,
                        characters[identity]["account_id"],
                        decks[identity],
                        action_id=identity,
                        rng=rng,
                        fight_start=identity == 8,
                        **common,
                    )
                runtime = RuntimeMessages(
                    fight,
                    turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                        characters[7],
                        {},
                        preview,
                        decks[7],
                        rng=rng,
                        **common,
                        **boundary,
                    ),
                    turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                        characters[7],
                        {},
                        preview,
                        decks[7],
                        rng=rng,
                        **common,
                        **boundary,
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[7],
                        {},
                        decks[7],
                        action_id=action_id,
                        critical=False,
                        rng=rng,
                        **common,
                    )[0],
                )
                for _ in range(8):
                    if runtime.fight.current.id == 7:
                        break
                    advance_actual_turn(runtime)
                self.assertEqual(runtime.fight.current.id, 7)
                self.assertIn(6286, granted_spells(runtime.fight, 7))
                summoned = self.cast(
                    characters,
                    decks,
                    runtime.fight,
                    7,
                    6286,
                    (-4, -17, 0),
                    runtime.action_id + 1,
                )
                summon_id = next(
                    iter(set(summoned.fight.actors) - set(runtime.fight.actors))
                )
                self.assertEqual(
                    summoned.fight.actors[summon_id].native_summon_source["ref"], 4559
                )
                self.assertEqual(
                    summoned.fight.actors[summon_id].native_controller_id, 7
                )
                self.assertEqual(summoned.plan["costs"]["ap"], 3)
                runtime.fight = summoned.fight
                runtime.action_id = summoned.action_id
                runtime.prepare_delivery(summoned.packets)
                before = snapshot(runtime.fight)
                hp = runtime.fight.actors[8].hp
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    poisoned = self.cast(
                        characters,
                        decks,
                        runtime.fight,
                        7,
                        (7 << 32) | 6269,
                        runtime.fight.actors[8].position,
                        runtime.action_id + 1,
                    )
                self.assertEqual(snapshot(runtime.fight), before)
                self.assertEqual(poisoned.plan["costs"]["ap"], 2)
                self.assertIn(
                    7523,
                    {
                        s.reference
                        for s in poisoned.fight.actors[8].state_ledger.entries
                    },
                )
                echo = [
                    r
                    for r in trace
                    if r.get("effect_reference") == 341420
                    and r.get("status") == "completed"
                ]
                if passive is None:
                    self.assertEqual(echo, [])
                else:
                    self.assertTrue(echo, trace)
                    self.assertTrue(
                        any(
                            r.get("caster_id") == summon_id and r.get("target_id") == 8
                            for r in echo
                        ),
                        echo,
                    )
                runtime.fight = poisoned.fight
                runtime.action_id = poisoned.action_id
                runtime.prepare_delivery(poisoned.packets)
                after_cast = runtime.fight.actors[8].hp
                self.assertLess(after_cast, hp)
                for _ in range(8):
                    if runtime.fight.current.id == 8:
                        break
                    advance_actual_turn(runtime)
                    self.assertEqual(runtime.fight.actors[8].hp, after_cast)
                self.assertEqual(runtime.fight.current.id, 8)
                self.assertIn(
                    7523,
                    {s.reference for s in runtime.fight.actors[8].state_ledger.entries},
                )
                # Native content.4.6269 and content.33.339726 specify damage
                # after movement during the target's turn; END is expiry only.
                from wakfu_server.combat_actor import actual_actor_stats
                from wakfu_server.combat_area_transaction import prepare_area_movement
                from wakfu_server.combat_movement_runtime import apply_client
                from wakfu_server.breed_resources import live_wp

                target = runtime.fight.actors[8]
                destinations = [
                    destination
                    for origin, destination in sorted(runtime.fight.edges)
                    if origin == target.position
                    and destination
                    not in {
                        actor.position
                        for actor in runtime.fight.actors.values()
                        if actor.hp > 0
                    }
                ]
                self.assertTrue(destinations)
                # Prefer the legal outward step, away from the opposing owner.
                destination = max(
                    destinations,
                    key=lambda cell: abs(cell[0] - runtime.fight.actors[7].position[0])
                    + abs(cell[1] - runtime.fight.actors[7].position[1]),
                )
                before_mp = target.mp

                def provider(preview, **boundary):
                    return prepare_area_movement(
                        characters[8],
                        {},
                        preview,
                        decks[8],
                        rng=rng,
                        **common,
                        **boundary,
                    )

                def target_stats(actor):
                    wp = live_wp(runtime.fight, actor.id)
                    return actual_actor_stats(
                        characters[8],
                        actor,
                        runtime.fight.id,
                        wp_current=wp[0],
                        wp_maximum=wp[1],
                    )

                movement_trace = []
                with combat_diagnostic_scope(
                    lambda **row: movement_trace.append(row), limit=8192
                ):
                    apply_client(
                        runtime,
                        characters[8]["account_id"],
                        struct.pack(">qiih", 8, *destination),
                        target_stats,
                        area_provider=provider,
                    )
                self.assertEqual(runtime.fight.actors[8].position, destination)
                self.assertLess(runtime.fight.actors[8].mp, before_mp)
                self.assertLess(runtime.fight.actors[8].hp, after_cast)
                completed = {
                    r.get("effect_reference")
                    for r in movement_trace
                    if r.get("status") == "completed"
                }
                self.assertTrue({339727, 341061} & completed, movement_trace)
                after_movement = runtime.fight.actors[8].hp
                self.assertIn(
                    7523,
                    {s.reference for s in runtime.fight.actors[8].state_ledger.entries},
                )
                advance_actual_turn(runtime)
                self.assertIsNone(runtime.awaiting_ack)
                self.assertEqual(runtime.fight.actors[8].hp, after_movement)
                self.assertNotIn(
                    7523,
                    {s.reference for s in runtime.fight.actors[8].state_ledger.entries},
                )
                outcomes[passive] = dict(
                    direct_damage=hp - after_cast,
                    movement_damage=after_cast - after_movement,
                )
        # Failed subTests already report their primary cause; avoid a trailing
        # KeyError that would obscure an initialization/ownership failure.
        if set(outcomes) == {None, 6273}:
            self.assertGreater(
                outcomes[6273]["direct_damage"], outcomes[None]["direct_damage"]
            )
