"""A real allied player spends its last MP collecting another owner's bag."""
from collections import deque
from copy import deepcopy
import os
import random
import struct
import unittest
from unittest.mock import patch

import test_enutrof_remaining_companion_actions as helpers
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_maximum_resource import NativeMaximumResourceHandler


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EnutrofTwoOwnerBagMovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helpers.EnutrofRemainingCompanionActionsTests.setUpClass()

    def test_ally_last_paid_mp_retires_one_bag_and_preserves_other_owner_areas(self):
        helper = helpers.EnutrofRemainingCompanionActionsTests()
        fight, characters, monster, decks = helper.fixture()
        rng = random.Random(17)
        helper.reach(fight, characters, monster, decks, 9, rng)
        collector = fight.actors[9]
        self.assertNotEqual(collector.id, 7)
        self.assertEqual(collector.team, fight.actors[7].team)
        self.assertEqual(collector.ap, 6)
        self.assertGreater(collector.mp, 1)
        bags = {
            tuple(row["cell"]): row
            for row in fight.native_effect_areas.values()
            if row["reference"] == 207 and row["owner_id"] == 7
        }
        self.assertTrue(bags)
        occupied = {
            a.position
            for a in fight.actors.values()
            if a.hp > 0 and a.id != collector.id
        }
        area_cells = {tuple(row["cell"]) for row in fight.native_effect_areas.values()}
        enemies = [
            a for a in fight.actors.values() if a.hp > 0 and a.team != collector.team
        ]
        neighbors = {}
        for origin, destination in fight.edges:
            neighbors.setdefault(origin, []).append(destination)
        queue = deque([(collector.position, ())])
        seen = {(collector.position, 0)}
        route = None
        while queue:
            cell, path = queue.popleft()
            if len(path) == collector.mp:
                if cell in bags:
                    route = path
                    break
                continue
            for destination in sorted(neighbors.get(cell, ())):
                key = (destination, len(path) + 1)
                if key in seen or destination in occupied:
                    continue
                if any(
                    sum(abs(destination[i] - enemy.position[i]) for i in (0, 1)) <= 1
                    for enemy in enemies
                ):
                    continue
                last_step = len(path) + 1 == collector.mp
                if destination in area_cells and not (
                    last_step and destination in bags
                ):
                    continue
                seen.add(key)
                queue.append((destination, (*path, destination)))
        self.assertIsNotNone(
            route, dict(origin=collector.position, mp=collector.mp, bags=list(bags))
        )
        bag = deepcopy(bags[route[-1]])
        runtime = RuntimeMessages(fight)

        def area_provider(current, **boundary):
            return prepare_area_movement(
                characters[9],
                {-7: monster},
                current,
                decks[9],
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
                **boundary
            )

        def move(path):
            return apply_client(
                runtime,
                characters[9]["account_id"],
                struct.pack(">q", 9)
                + b"".join(struct.pack(">iih", *cell) for cell in path),
                lambda actor: b"",
                area_provider=area_provider,
            )

        move(route[:-1])
        self.assertEqual(runtime.fight.actors[9].mp, 1)
        self.assertEqual(runtime.fight.actors[9].ap, 6)
        before_areas = deepcopy(runtime.fight.native_effect_areas)
        foreign = {
            uid: row
            for uid, row in before_areas.items()
            if row.get("owner_id") == 8
            and row["reference"] in (202, 203, 204, 205, 207, 209)
        }
        self.assertTrue(foreign)
        self.assertTrue(any(row["reference"] in (207, 209) for row in foreign.values()))
        maximum_before = runtime.fight.actors[9].max_mp
        reward_trace = []
        maximum_apply = NativeMaximumResourceHandler.__call__

        def observe_reward(handler, effect, values, invocation):
            target = handler.fight.actors.get(invocation.target_id)
            before = None if target is None else (target.mp, target.max_mp)
            outcome = maximum_apply(handler, effect, values, invocation)
            if invocation.reference == 384633:
                target = handler.fight.actors[invocation.target_id]
                reward_trace.append(
                    (invocation.target_id, before, (target.mp, target.max_mp), outcome)
                )
            return outcome

        with patch.object(NativeMaximumResourceHandler, "__call__", observe_reward):
            packets, _ = move(route[-1:])
        after = runtime.fight
        self.assertEqual(after.actors[9].position, route[-1])
        # Native384633 family41 gives +1 maximum/current MP. The paid
        # entry consumes1 first, then this real bag reward replenishes1.
        self.assertEqual(after.actors[9].mp, 1, reward_trace)
        self.assertEqual(after.actors[9].max_mp, maximum_before + 1)
        self.assertEqual(
            [(target, before, current) for target, before, current, _ in reward_trace],
            [(9, (0, maximum_before), (1, maximum_before + 1))],
        )
        self.assertEqual(after.actors[9].ap, 6)
        self.assertNotIn(bag["uid"], after.native_effect_areas)
        # The replenished MP must really be spendable after Qq self-removal,
        # rather than merely displayed by the client with a broken container.
        extra_packets, _ = move(route[-2:-1])
        packets = list(packets) + list(extra_packets)
        after = runtime.fight
        self.assertEqual(after.actors[9].position, route[-2])
        self.assertEqual(after.actors[9].mp, 0)
        self.assertEqual(after.actors[9].ap, 6)
        self.assertNotIn(bag["uid"], after.native_effect_areas)
        entered_mines = {
            uid
            for uid, row in before_areas.items()
            if row.get("owner_id") == 7
            and row["reference"] in (202, 203, 204, 205)
            and tuple(row["cell"]) == tuple(bag["cell"])
        }
        # A mine may legitimately share the bag cell. Its own10001 callback
        # consumes that mine as well; unrelated/foreign areas must survive.
        self.assertTrue(entered_mines.isdisjoint(after.native_effect_areas))
        for uid, row in before_areas.items():
            if uid not in entered_mines | {bag["uid"]} and row["reference"] in (
                202,
                203,
                204,
                205,
                207,
                209,
            ):
                self.assertEqual(
                    after.native_effect_areas.get(uid),
                    row,
                    dict(bag=bag, route=route, area=row),
                )
        for uid, row in foreign.items():
            self.assertEqual(after.native_effect_areas.get(uid), row)
        removals = []
        mine_removals = []
        for kind, body in packets:
            if kind == 12613 and struct.unpack_from(">i", body, 13)[0] == 843:
                fields = _identity_fields(body[19:])
                if fields.get(7) == bag["uid"]:
                    removals.append(fields)
                if fields.get(7) in entered_mines:
                    mine_removals.append(fields)
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0][3], 386191)
        self.assertEqual(removals[0][6], 7)
        self.assertEqual({fields[7] for fields in mine_removals}, entered_mines)
        self.assertEqual(len(mine_removals), len(entered_mines))
