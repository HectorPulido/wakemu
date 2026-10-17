"""Earned Ouginak Fracture reacts once to actual Eliotrope portal travel."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropePoisonPortalTests(unittest.TestCase):
    def test_earned_fracture_reacts_once_to_paid_portal_travel(self):
        from combat_audit_turns import advance_actual_turn
        from class_spell_eligible_targets import candidate_cells, eligible_cast_targets
        from wakfu_server.combat_actor import actual_actor_stats
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_reproduction_state import encode_state
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.equipment_stats import combat_resources, effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck, validate_deck
        from unittest.mock import patch

        positions = {7: (-4, -18, 0), 8: (-2, -18, 0)}
        characters = {}
        actors = []
        resources = {}
        for identity, account, team, breed in ((7, 3, 0, 15), (8, 4, 1, 18)):
            character = effective_character(
                dict(
                    id=identity,
                    account_id=account,
                    breed=breed,
                    level=200,
                    hp=maximum(breed, 200),
                    max_hp=maximum(breed, 200),
                    map_id=1134,
                    builds={},
                    inventory_items=[],
                )
            )
            characters[identity] = character
            values = combat_resources(character)
            resources[identity] = values
            actor = Actor(
                identity,
                team,
                positions[identity],
                character["hp"],
                values["ap"],
                values["mp"],
                values["initiative"],
                200,
                account,
                True,
                max_hp=character["max_hp"],
            )
            actor.direction = 0 if identity == 7 else 3
            actors.append(actor)
        decks = {7: encode_deck([6269]), 8: encode_deck([4668, 4692, 4699])}
        for identity in characters:
            validate_deck(decks[identity], characters[identity]["breed"], 200)
        arena = local_arena(
            1134, 7, positions[7], positions[8], relocate_monsters=False
        )
        fight = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {positions[7]}, 1: {positions[8]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, (7, 8))
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources={
                identity: (values["wp"], values["wp"])
                for identity, values in resources.items()
            },
            running_effects={identity: () for identity in characters},
            initial_effect_uid=1,
        )
        fight.ready(3)
        fight.ready(4)
        rng = random.Random(7)
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
                **common
            )

        def stats(actor, current=None):
            current = runtime.fight if current is None else current
            return actual_actor_stats(
                characters[actor.id],
                actor,
                current.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )

        runtime = RuntimeMessages(
            fight,
            stats_serializer=stats,
            runtime_stats_serializer=stats,
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                characters[7], {}, preview, decks[7], rng=rng, **common, **boundary
            ),
            turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                characters[7], {}, preview, decks[7], rng=rng, **common, **boundary
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {},
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                **common
            )[0],
        )

        def own_turn(identity):
            for _ in range(8):
                if runtime.fight.current.id == identity:
                    self.assertIsNone(runtime.awaiting_ack)
                    return
                advance_actual_turn(runtime)
            self.fail("Actual turn sequence did not reach requested owner")

        def los(identity):
            return lambda origin, destination, current: authoritative_visible(
                characters[identity]["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        def cast(identity, uid, target):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", identity, uid, *target),
                characters[identity],
                {},
                runtime.fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=runtime.action_id + 1,
                line_of_sight=los(identity),
                critical=False,
                rng=rng,
                **common
            )
            runtime.fight = transaction.fight
            runtime.action_id = transaction.action_id
            runtime.prepare_delivery(transaction.packets)
            return transaction

        def portal(near):
            _, adapter = server_runtime(
                characters[8],
                {},
                decks[8],
                action_id=runtime.action_id + 1,
                critical=False,
                rng=rng,
                **common
            )
            cells, total = candidate_cells(runtime.fight, 8, limit=4096)
            occupied = {a.position for a in runtime.fight.actors.values() if a.hp > 0}
            used = {
                tuple(row["cell"]) for row in runtime.fight.native_effect_areas.values()
            }
            ordered = tuple(
                sorted(
                    (cell for cell in cells if cell not in occupied | used),
                    key=lambda cell: (
                        abs(cell[0] - near[0]) + abs(cell[1] - near[1]),
                        cell,
                    ),
                )
            )
            uid = granted_spells(runtime.fight, 8)[4678]["uid"]
            with patch(
                "class_spell_eligible_targets.candidate_cells",
                return_value=(ordered, total),
            ):
                eligibility = eligible_cast_targets(
                    runtime.fight,
                    characters[8],
                    decks[8],
                    uid,
                    adapter=adapter,
                    line_of_sight=los(8),
                    actor_id=8,
                    limit=4096,
                    maximum_eligible=16,
                )
            self.assertTrue(eligibility["eligible"], eligibility)
            before = set(runtime.fight.native_effect_areas)
            transaction = cast(8, uid, eligibility["eligible"][0]["target"])
            created = set(runtime.fight.native_effect_areas) - before
            self.assertEqual(len(created), 1)
            row = runtime.fight.native_effect_areas[created.pop()]
            self.assertEqual((row["reference"], row["native_type_id"]), (823, 19))
            return row

        def movement_provider(preview, **boundary):
            return prepare_area_movement(
                characters[8], {}, preview, decks[8], rng=rng, **common, **boundary
            )

        def move(cell):
            return apply_client(
                runtime,
                4,
                struct.pack(">qiih", 8, *cell),
                stats,
                runtime_stats_serializer=stats,
                area_provider=movement_provider,
            )

        own_turn(8)
        entry = portal(runtime.fight.actors[8].position)
        exit = portal((-8, -10, 0))
        origin, destination = tuple(entry["cell"]), tuple(exit["cell"])
        self.assertGreater(
            abs(origin[0] - destination[0]) + abs(origin[1] - destination[1]), 1
        )
        self.assertEqual(
            abs(origin[0] - runtime.fight.actors[8].position[0])
            + abs(origin[1] - runtime.fight.actors[8].position[1]),
            1,
        )
        move(origin)  # A real paid12161 entry step; no position injection.
        advance_actual_turn(runtime)
        own_turn(7)
        direct_before = runtime.fight.actors[8].hp
        transaction = cast(7, (7 << 32) | 6269, runtime.fight.actors[8].position)
        self.assertEqual(transaction.plan["costs"]["ap"], 2)
        self.assertIn(
            7523,
            {state.reference for state in runtime.fight.actors[8].state_ledger.entries},
        )
        self.assertLess(runtime.fight.actors[8].hp, direct_before)
        own_turn(8)
        before_hp = runtime.fight.actors[8].hp
        before_mp = runtime.fight.actors[8].mp
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
            packets, event = move(destination)
        self.assertTrue(event["on_gates"])
        self.assertEqual(runtime.fight.actors[8].position, destination)
        self.assertEqual(runtime.fight.actors[8].mp, before_mp - 1 - event["tackle_mp"])
        self.assertLess(runtime.fight.actors[8].hp, before_hp)
        completed = [
            row
            for row in trace
            if row.get("status") == "completed"
            and row.get("effect_reference") in (339727, 341061)
        ]
        self.assertEqual(len(completed), 1, trace)
        animation = next(body for opcode, body in packets if opcode == 13624)
        self.assertEqual(animation[21], 3)
        self.assertFalse(
            hasattr(runtime.fight, "_wakemu_native_gate_movement_boundary")
        )
        # An unrelated nonportal destination cannot pay or trigger poison again.
        nonportal = next(
            cell
            for cell in sorted(runtime.fight.walkable)
            if cell not in (origin, destination)
            and abs(cell[0] - destination[0]) + abs(cell[1] - destination[1]) > 1
        )
        before = encode_state(runtime)
        with self.assertRaises(ValueError):
            move(nonportal)
        self.assertEqual(encode_state(runtime), before)
