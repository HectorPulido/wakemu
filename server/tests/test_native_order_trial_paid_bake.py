"""A paid native recipe action after real entry, Ready and conveyor movement."""
from collections import deque
import struct

from test_native_order_trial_owned_spawn import NativeOrderTrialOwnedSpawnTests


class NativeOrderTrialPaidBakeTests(NativeOrderTrialOwnedSpawnTests):
    def test_actual_paid4536_starts_native3123_and_original120461_finishes(self):
        self._run_owned_fixture(probe=self._paid_bake)

    def test_actual_pickup_tenderize_garnish_and_bake_use_native_paid_actions(self):
        self._run_owned_fixture(probe=lambda case: self._paid_bake(case, garnish=True))

    def test_actual_requested_recipe_earns_its_frozen_reviewed_score(self):
        self._run_owned_fixture(
            probe=lambda case: self._paid_bake(case, garnish=True, require_score=True)
        )

    def _paid_bake(self, case, *, garnish=False, require_score=False):
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.native_order_trial_movement import area_provider
        from wakfu_server.native_order_trial_events import observe_pending
        from wakfu_server.native_order_trial_checkpoint import validate
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint

        runtime, owner_id = case.runtime, case.owner_id
        observed = 0

        def accept_events():
            nonlocal observed
            events = runtime.fight.events[observed:]
            observe_pending(runtime.fight, events=events)
            observed = len(runtime.fight.events)

        def acknowledge():
            for _ in range(20):
                if runtime.awaiting_ack is None:
                    return
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            self.fail("Native turn ACK loop did not settle")

        def next_owner_turn():
            fight = runtime.fight
            runtime.end_turn(case.account_id, owner_id, current_wire_turn(fight))
            acknowledge()
            accept_events()
            for _ in range(20):
                fight = runtime.fight
                self.assertEqual(fight.phase, "active")
                if fight.current.id == owner_id:
                    return
                print(
                    "PAID_BAKE_AUTOMATIC",
                    dict(
                        actor_id=fight.current.id,
                        turn_id=fight.turn_id,
                        position=fight.current.position,
                        mp=fight.current.mp,
                        command=getattr(fight, "native_order_commands", {}).get(
                            str(fight.current.id)
                        ),
                    ),
                    flush=True,
                )
                runtime.end_automatic_npc_turn(fight.current.id, fight.turn_id)
                acknowledge()
                accept_events()
            self.fail("Native automatic actors did not return the owner turn")

        def cast(spell, cell):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", owner_id, spell, *cell),
                case.character,
                {},
                runtime.fight,
                case.account_id,
                case.deck,
                action_id=runtime.action_id + 1,
                critical=False,
                line_of_sight=lambda source, destination, candidate: authoritative_visible(
                    885,
                    source,
                    destination,
                    candidate,
                    blocking_footprints={
                        actor.id: footprint(actor.position, actor.physical_radius)
                        for actor in candidate.actors.values()
                        if actor.hp > 0
                    },
                ),
            )
            commit_spell_transaction(
                runtime, transaction, stats_serializer=runtime.runtime_stats_serializer
            )
            accept_events()
            return transaction

        def path_to(goal):
            fight = runtime.fight
            actor = fight.actors[owner_id]
            from wakfu_server.combat_qi_movement import movement_blocked_cells

            blocked = movement_blocked_cells(fight, actor, tuple(fight.walkable))
            self.assertIsNotNone(blocked)
            queue, previous = deque([actor.position]), {actor.position: None}
            outgoing = {}
            for before, after in fight.edges:
                outgoing.setdefault(before, []).append(after)
            while queue:
                cell = queue.popleft()
                if cell == goal:
                    path = []
                    while previous[cell] is not None:
                        path.append(cell)
                        cell = previous[cell]
                    return tuple(reversed(path))
                for adjacent in sorted(outgoing.get(cell, ())):
                    if adjacent not in previous and adjacent not in blocked:
                        previous[adjacent] = cell
                        queue.append(adjacent)
            self.fail("No native QI path to the reviewed oven approach")

        accept_events()
        # This is the declared hard-mode west contact closest to the owner.
        # Every step and the final push use the ordinary native paid actions.
        goal = (-5, -4, 0)
        chosen = None
        ingredient = None
        picked_up = not garnish
        if garnish:
            _, _, initial = validate(
                runtime.fight.native_order_trial,
                encounter_id=runtime.fight.id,
                replay=False,
            )
            first = initial.larvae[0]
            ingredient = next(
                (item for color, item in initial.orders if color == first.color),
                initial.orders[0][1],
            )
        barrel_x = {"tomato": -3, "cheese": -1, "pepper": 1}
        for _ in range(32 if require_score else 12):
            fight = runtime.fight
            owner = fight.actors[owner_id]
            self.assertEqual(fight.current.id, owner_id)
            candidates = [
                actor
                for actor in fight.actors.values()
                if actor.id != owner_id
                and actor.hp > 0
                and actor.position == (-6, -4, 0)
            ]
            if picked_up and owner.position == goal and owner.mp >= 2 and candidates:
                candidate = candidates[0]
                _, _, current = validate(
                    runtime.fight.native_order_trial,
                    encounter_id=runtime.fight.id,
                    replay=False,
                )
                larva = next(
                    row for row in current.larvae if row.actor_id == candidate.id
                )
                if not require_score or (larva.color, ingredient) in current.orders:
                    chosen = candidate.id
                    break
                # The original second tenderize kills an unwanted color without
                # a strike. Wait for its genuine native replacement; never
                # rewrite a request, breed, ingredient or RNG result.
                self.assertGreaterEqual(owner.ap, 6)
                cast(4535, candidate.position)
                cast(4535, candidate.position)
                self.assertEqual(runtime.fight.actors[candidate.id].hp, 0)
                next_owner_turn()
                continue
            destination = goal if picked_up else (barrel_x[ingredient], -4, 0)
            if not picked_up and owner.position == destination:
                transaction = cast(4538, (barrel_x[ingredient], -5, 0))
                self.assertEqual(transaction.plan["costs"]["ap"], 2)
                _, _, supplied = validate(
                    runtime.fight.native_order_trial,
                    encounter_id=runtime.fight.id,
                    replay=False,
                )
                self.assertEqual(
                    (supplied.ingredient, supplied.charges), (ingredient, 2)
                )
                picked_up = True
                destination = goal
                owner = runtime.fight.actors[owner_id]
            path = path_to(destination)[: owner.mp]
            if path:
                body = struct.pack(">q", owner_id) + b"".join(
                    struct.pack(">iih", *cell) for cell in path
                )
                apply_client(
                    runtime,
                    case.account_id,
                    body,
                    runtime.stats_serializer,
                    area_provider=area_provider(runtime),
                    runtime_stats_serializer=runtime.runtime_stats_serializer,
                )
                accept_events()
            if not picked_up and runtime.fight.actors[owner_id].position == (
                barrel_x[ingredient],
                -4,
                0,
            ):
                self.assertEqual(
                    cast(4538, (barrel_x[ingredient], -5, 0)).plan["costs"]["ap"], 2
                )
                _, _, supplied = validate(
                    runtime.fight.native_order_trial,
                    encounter_id=runtime.fight.id,
                    replay=False,
                )
                self.assertEqual(
                    (supplied.ingredient, supplied.charges), (ingredient, 2)
                )
                picked_up = True
            next_owner_turn()
        self.assertIsNotNone(
            chosen, "No genuine conveyor larva reached the oven approach"
        )
        expected_score = 0
        if garnish:
            _, rules, state = validate(
                runtime.fight.native_order_trial,
                encounter_id=runtime.fight.id,
                replay=False,
            )
            larva = next(row for row in state.larvae if row.actor_id == chosen)
            recipe = (larva.color, ingredient)
            expected_score = (
                dict(rules.weights)[recipe] if recipe in state.orders else 0
            )
            target_cell = runtime.fight.actors[chosen].position
            self.assertEqual(cast(4535, target_cell).plan["costs"]["ap"], 3)
            self.assertEqual(cast(4537, target_cell).plan["costs"]["ap"], 2)
            _, _, garnished = validate(
                runtime.fight.native_order_trial,
                encounter_id=runtime.fight.id,
                replay=False,
            )
            self.assertEqual(
                next(
                    row.ingredient for row in garnished.larvae if row.actor_id == chosen
                ),
                ingredient,
            )
            self.assertEqual(garnished.charges, 1)
        target = runtime.fight.actors[chosen]
        before = runtime.fight.actors[owner_id]
        resources = before.ap, before.mp
        transaction = cast(4536, target.position)
        self.assertEqual(transaction.plan["costs"]["ap"], 1)
        self.assertEqual(transaction.plan["costs"]["mp"], 2)
        actor = runtime.fight.actors[chosen]
        self.assertEqual(actor.position, (-7, -4, 0))
        self.assertEqual(
            [
                (entry.reference, entry.level)
                for entry in actor.state_ledger.entries
                if entry.reference == 3123
            ],
            [(3123, 1)],
        )
        owner = runtime.fight.actors[owner_id]
        self.assertEqual((owner.ap, owner.mp), (resources[0] - 1, resources[1] - 2))
        for _ in range(4):
            if runtime.fight.actors[chosen].hp <= 0:
                break
            next_owner_turn()
        self.assertEqual(runtime.fight.actors[chosen].hp, 0)
        self.assertTrue(
            any(
                row.get("kind") == "kill_hp_minimum_update"
                and row.get("generic_effect") == 120461
                and row.get("target_id") == chosen
                for row in runtime.fight.events
            )
        )
        self.assertTrue(
            any(
                row.get("kind") == "native_order_baking_completed"
                and row.get("target_id") == chosen
                for row in runtime.fight.events
            )
        )
        _, _, state = validate(
            runtime.fight.native_order_trial,
            encounter_id=runtime.fight.id,
            replay=False,
        )
        if garnish:
            self.assertEqual(state.strikes, 0)
            self.assertEqual(state.score, expected_score)
            if require_score:
                self.assertGreater(expected_score, 0)
            print(
                "PAID_GARNISHED_RESULT",
                dict(recipe=recipe, score=state.score, requested=expected_score > 0),
                flush=True,
            )
        else:
            self.assertEqual(state.strikes, 1)
            self.assertEqual(
                [
                    (entry.reference, entry.level)
                    for entry in runtime.fight.actors[owner_id].state_ledger.entries
                    if entry.reference == 3124
                ],
                [(3124, 1)],
            )
