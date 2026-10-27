"""Real player disengagement through opcode12161 and native area callbacks."""
from copy import deepcopy
import random
import struct
import unittest
from wakfu_server.fight_checkpoint_store import snapshot

from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_actor import actual_actor_stats
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_tackle_movement import movement_tackle_cost
from wakfu_server.combat_terrain import local_arena
from wakfu_server.equipment_stats import effective_character
from wakfu_server.health import maximum
from wakfu_server.spells import encode_deck


class PartialTacklePaidPipelineTests(unittest.TestCase):
    def fixture(self):
        positions = {7: (-8, -7, -1), 8: (-7, -7, -1), 9: (-5, -7, -1)}
        characters = {
            uid: effective_character(
                dict(
                    id=uid,
                    account_id=owner,
                    map_id=1134,
                    breed=1,
                    level=60,
                    hp=maximum(1, 60),
                    builds={},
                    inventory_items=[],
                )
            )
            for uid, owner in ((7, 3), (8, 4), (9, 5))
        }
        actors = [
            Actor(
                uid,
                team,
                positions[uid],
                characters[uid]["hp"],
                6,
                3,
                initiative,
                60,
                characters[uid]["account_id"],
                True,
                max_hp=characters[uid]["max_hp"],
            )
            for uid, team, initiative in ((7, 0, 30), (8, 1, 20), (9, 1, 10))
        ]
        arena = local_arena(
            1134,
            78036,
            positions[7],
            [positions[8], positions[9]],
            compact=False,
            relocate_monsters=False,
            variation_seed=17,
        )
        fight = Fight(
            78036,
            actors,
            arena["validated_cells"],
            {0: {positions[7]}, 1: {positions[8], positions[9]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8, 9))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources={uid: (6, 6) for uid in characters},
            running_effects={uid: () for uid in characters},
            initial_effect_uid=1,
        )
        for owner in (3, 4, 5):
            fight.ready(owner)
        decks = {uid: encode_deck() for uid in characters}
        for index, uid in enumerate((7, 8, 9), 1):
            fight, _ = prepare_server_initialization(
                characters[uid],
                {},
                fight,
                characters[uid]["account_id"],
                decks[uid],
                action_id=index,
                fight_start=(uid == 9),
                player_characters=characters,
                deck_blobs=decks,
                rng=random.Random(17),
            )
        fight.actors[8].direction = 5
        self.assertEqual(fight.current.id, 7)
        return fight, characters, decks

    def test_partial_paid_native_departure(self):
        baseline, characters, decks = self.fixture()
        path = [(-8, -6, -1)]
        self.assertIn((baseline.actors[7].position, path[0]), baseline.edges)

        def stats(actor, current):
            return actual_actor_stats(
                characters[actor.id],
                actor,
                current.id,
                fight=current,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            )

        for name in (
            "zero",
            "partial",
            "exact",
            "no_ap",
            "no_mp",
            "locked",
            "two_lockers",
        ):
            with self.subTest(case=name):
                fight = deepcopy(baseline)
                actor = fight.current
                from wakfu_server.combat_qi_fight import move_registered_actor
                from wakfu_server.combat_resource_pa_notifications import (
                    set_resource_current,
                )

                if name == "zero":
                    move_registered_actor(fight, fight.actors[8], (-6, -7, -1))
                if name == "partial":
                    fight.actors[8].direction = 3  # Side tax leaves one MP.
                if name == "two_lockers":
                    move_registered_actor(fight, fight.actors[9], (-9, -7, -1))
                    fight.actors[9].direction = 1
                if name == "exact":
                    set_resource_current(fight, actor, 2, 1)
                if name == "no_ap":
                    set_resource_current(fight, actor, 2, 0)
                if name in ("no_mp", "locked"):
                    set_resource_current(fight, actor, 3, 2 if name == "no_mp" else 0)
                departures = []
                tax = movement_tackle_cost(fight, actor, path, capture=departures)
                expected = (
                    (0, 0)
                    if name == "zero"
                    else (1, 1)
                    if name == "partial"
                    else (1, 2)
                )
                self.assertEqual(tax, expected)
                if name == "two_lockers":
                    self.assertEqual(set(departures[0]["causer_ids"]), {8, 9})
                common = dict(player_characters=characters, deck_blobs=decks)
                runtime = RuntimeMessages(
                    fight,
                    turn_end_provider=lambda current, **boundary: prepare_server_turn_end(
                        characters[7], {}, current, decks[7], **common, **boundary
                    ),
                    turn_start_provider=lambda current, **boundary: prepare_server_turn_start(
                        characters[7],
                        {},
                        current,
                        decks[7],
                        area_callbacks=True,
                        **common,
                        **boundary
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[7],
                        {},
                        decks[7],
                        action_id=action_id,
                        critical=False,
                        **common
                    )[0],
                )

                def provider(current, **boundary):
                    return prepare_area_movement(
                        characters[7],
                        {},
                        current,
                        decks[7],
                        player_characters=characters,
                        deck_blobs=decks,
                        rng=random.Random(17),
                        **boundary
                    )

                before = snapshot(fight)
                ap, mp = actor.ap, actor.mp

                def move():
                    return apply_client(
                        runtime,
                        3,
                        struct.pack(">qiih", 7, *path[0]),
                        lambda candidate: stats(candidate, runtime.fight),
                        area_provider=provider,
                        runtime_stats_serializer=stats,
                    )

                if name in ("no_ap", "no_mp", "locked"):
                    with self.assertRaisesRegex(ValueError, "insufficient AP/MP"):
                        move()
                    self.assertEqual(snapshot(runtime.fight), before)
                    self.assertEqual(runtime.action_id, 0)
                    continue
                packets, event = move()
                moved = runtime.fight.actors[7]
                self.assertEqual(
                    (moved.ap, moved.mp, moved.position),
                    (ap - tax[0], mp - 1 - tax[1], path[0]),
                )
                self.assertEqual(
                    (
                        event.get("tackle_ap", 0),
                        event.get("tackle_mp", 0),
                        event["cost"],
                    ),
                    (*tax, 1 + tax[1]),
                )
                self.assertIn(13624, [opcode for opcode, _ in packets])
                self.assertIn(12873, [opcode for opcode, _ in packets])
                if name == "partial":
                    from tools.combat_audit_turns import advance_actual_turn
                    from wakfu_server.combat_timeline_snapshot import current_wire_turn

                    ended = runtime.end_turn(3, 7, current_wire_turn(runtime.fight))
                    self.assertTrue(ended)
                    self.assertIsNotNone(runtime.awaiting_ack)
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                    self.assertEqual(runtime.fight.current.id, 8)
                    advance_actual_turn(runtime)
                    advance_actual_turn(runtime)
                    self.assertEqual(runtime.fight.current.id, 7)
                    self.assertEqual(
                        (runtime.fight.current.ap, runtime.fight.current.mp), (6, 3)
                    )
