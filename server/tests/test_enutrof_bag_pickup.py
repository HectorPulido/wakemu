"""Actual owned bag production and movement pickup, including the companion."""
from collections import deque
import unittest

from wakfu_server.combat_area_transaction import prepare_area_event
from wakfu_server.combat_qi_fight import move_registered_actor


class EnutrofBagPickupTests(unittest.TestCase):
    def test_qq_owner_root_source_policy_keeps_unrelated_glyphs_unchanged(self):
        import test_combat_effect_area_events as area_fixture

        runtime, row, calls = area_fixture.AreaEventTests().fixture()
        runtime.dispatcher.effects = {
            "298554": {"children": [900001]},
            "900001": {"native_target_selector": {"class": "fcE", "mask": 1 << 46}},
        }
        self.assertTrue(
            runtime._activate(row, runtime.definitions["1474"], runtime.fight.actors[8])
        )
        self.assertEqual((calls[0].caster_id, calls[0].target_id), (901, 8))
        calls.clear()
        runtime.dispatcher.effects["900001"]["native_target_selector"]["mask"] = 4
        self.assertTrue(
            runtime._activate(row, runtime.definitions["1474"], runtime.fight.actors[8])
        )
        self.assertEqual((calls[0].caster_id, calls[0].target_id), (7, 8))

    def test_repeated_actual_conversion_respects_native_occupied_bag_cell_exclusion(
        self,
    ):
        import test_enutrof_runtime as enutrof_fixture
        from test_aniripsa_grant_summon_pipeline import AniripsaGrantSummonPipelineTests

        helper = enutrof_fixture.EnutrofRuntimeTests()
        fixture = helper.fixture(actives=(2026,))
        first = helper.cast(fixture, 2026, fixture[2].actors[7].position)
        first_bags = {
            row["uid"]
            for row in first.fight.native_effect_areas.values()
            if row["reference"] == 207
        }
        fixture = (*fixture[:2], first.fight, *fixture[3:])
        turns = AniripsaGrantSummonPipelineTests()
        fight = first.fight
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        for _ in range(20):
            if fight.current.id == companion.id:
                break
            turns.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, companion.id)
        # Recreate a real deposit before converting again; conversion alone
        # does not create bags when its previous deposits were all consumed.
        import struct
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            server_runtime,
            prepare_server_spell,
        )

        character, monster, _, deck, rng = fixture
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=20, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            3541,
            actor_id=companion.id,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=16,
        )
        self.assertTrue(candidates["eligible"], candidates)
        owner_cell = fight.actors[7].position
        cell = min(
            (candidate["target"] for candidate in candidates["eligible"]),
            key=lambda target: sum(abs(target[i] - owner_cell[i]) for i in (0, 1)),
        )
        self.assertLessEqual(sum(abs(cell[i] - owner_cell[i]) for i in (0, 1)), 2)
        deposited = prepare_server_spell(
            struct.pack(">qqiih", companion.id, 3541, *cell),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=20,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        fight = deposited.fight
        fixture = (*fixture[:2], fight, *fixture[3:])
        self.assertTrue(
            any(
                row["reference"] in (202, 203, 204, 205)
                for row in fight.native_effect_areas.values()
            )
        )
        upgraded = set()
        for cycle in range(1, 11):
            turns.next_player_turn(fight, fixture)
            if cycle == 1:
                self.assertTrue(first_bags.isdisjoint(fight.native_effect_areas))
                upgraded = {
                    row["uid"]
                    for row in fight.native_effect_areas.values()
                    if row["reference"] == 209
                }
                self.assertEqual(len(upgraded), len(first_bags))
            elif cycle == 2:
                self.assertTrue(upgraded.isdisjoint(fight.native_effect_areas))
            before_conversion = [
                {key: row.get(key) for key in ("uid", "reference", "owner_id", "cell")}
                for row in fight.native_effect_areas.values()
            ]
            try:
                second = helper.cast(
                    fixture, 2026, fight.actors[7].position, action_id=30 + cycle
                )
            except ValueError as error:
                if "Native spell cast interval has not elapsed" not in str(error):
                    raise
            else:
                break
        else:
            self.fail(
                "Actual conversion cooldown did not expire within ten owner turns"
            )
        second_bags = {
            row["uid"]
            for row in second.fight.native_effect_areas.values()
            if row["reference"] == 207
        } - {row["uid"] for row in before_conversion if row["reference"] == 207}
        # Native 385371/386177 explicitly exclude cells already containing
        # owned bag 207/209. Natural turn-start deposits may share those
        # cells, so conversion consumes them without adding another bag.
        prior_bags = [
            row for row in before_conversion if row["reference"] in (207, 209)
        ]
        prior_deposits = [
            row for row in before_conversion if row["reference"] in (202, 203, 204, 205)
        ]
        self.assertTrue(prior_deposits)
        occupied_bag_cells = {tuple(row["cell"]) for row in prior_bags}
        self.assertTrue(all(row["owner_id"] == 7 for row in prior_deposits))
        deposit_cells = {tuple(row["cell"]) for row in prior_deposits}
        # Natural turn-start deposits may include a new unoccupied cell as
        # well as cells covered by an older bag. Only the covered cells are
        # negative conversion controls; unrelated new deposits still convert.
        self.assertTrue(deposit_cells & occupied_bag_cells, before_conversion)
        second_bag_rows = [
            row
            for row in second.fight.native_effect_areas.values()
            if row["uid"] in second_bags
        ]
        self.assertEqual(
            {tuple(row["cell"]) for row in second_bag_rows},
            deposit_cells - occupied_bag_cells,
        )
        self.assertTrue(all(row["owner_id"] == 7 for row in second_bag_rows))
        self.assertEqual(
            {row["uid"] for row in prior_bags},
            {
                row["uid"]
                for row in second.fight.native_effect_areas.values()
                if row["reference"] in (207, 209) and row["uid"] not in second_bags
            },
        )
        self.assertTrue(
            all(
                row["uid"] not in second.fight.native_effect_areas
                for row in prior_deposits
            )
        )
        live_bags = [
            row
            for row in second.fight.native_effect_areas.values()
            if row["reference"] in (207, 209)
        ]
        self.assertEqual(len({tuple(row["cell"]) for row in live_bags}), len(live_bags))
        self.assertEqual(len({row["uid"] for row in live_bags}), len(live_bags))
        self.assertEqual(len({row["effect_uid"] for row in live_bags}), len(live_bags))
        # Bag identities remain unique; no second bag was stacked on a cell.

    def test_actual_small_and_large_bags_consume_once_for_owner_and_companion(self):
        import test_enutrof_runtime as enutrof_fixture

        helper = enutrof_fixture.EnutrofRuntimeTests()
        for passive, reference in ((None, 207), (5076, 209)):
            for collector in ("owner", "companion"):
                with self.subTest(reference=reference, collector=collector):
                    fixture = helper.fixture(
                        actives=(2026,), passives=() if passive is None else (passive,)
                    )
                    character, monster, fight, deck, rng = fixture
                    transaction = helper.cast(fixture, 2026, fight.actors[7].position)
                    fight = transaction.fight
                    bags = [
                        row
                        for row in fight.native_effect_areas.values()
                        if row["reference"] == reference
                    ]
                    self.assertGreaterEqual(len(bags), 2)
                    self.assertEqual(
                        len({tuple(row["cell"]) for row in bags}), len(bags)
                    )
                    bag = bags[0]
                    actor = (
                        fight.actors[7]
                        if collector == "owner"
                        else next(
                            actor
                            for actor in fight.actors.values()
                            if getattr(actor, "native_summon_source", None)
                        )
                    )
                    origin = actor.position
                    destination = tuple(bag["cell"])
                    # Exercise the committed-coordinate callback with genuine
                    # actor/QI relocation, never an unregistered position edit.
                    move_registered_actor(fight, actor, destination)
                    result, packets = prepare_area_event(
                        character,
                        {-7: monster},
                        fight,
                        deck,
                        actor_id=actor.id,
                        action_id=10,
                        event="movement",
                        from_cell=origin,
                        to_cell=destination,
                        rng=rng,
                    )
                    self.assertNotIn(bag["uid"], result.native_effect_areas)
                    import struct
                    from wakfu_server.combat_effect_removal import _identity_fields

                    removals = []
                    for kind, body in packets:
                        if (
                            kind != 12613
                            or struct.unpack_from(">i", body, 13)[0] != 843
                        ):
                            continue
                        self.assertEqual(body[12], 1)
                        size = struct.unpack_from(">h", body, 17)[0]
                        self.assertEqual(len(body), 19 + size)
                        fields = _identity_fields(body[19:])
                        if fields.get(7) == bag["uid"]:
                            removals.append(fields)
                    self.assertEqual(len(removals), 1, packets)
                    self.assertEqual(
                        removals[0][3], 386191 if reference == 207 else 411589
                    )
                    self.assertEqual(removals[0][6], 7)
                    self.assertTrue(
                        all(
                            row["uid"] in result.native_effect_areas for row in bags[1:]
                        )
                    )
                    repeated, repeated_packets = prepare_area_event(
                        character,
                        {-7: monster},
                        result,
                        deck,
                        actor_id=actor.id,
                        action_id=11,
                        event="movement",
                        from_cell=destination,
                        to_cell=destination,
                        rng=rng,
                    )
                    self.assertEqual(repeated_packets, ())
                    self.assertEqual(
                        set(repeated.native_effect_areas),
                        set(result.native_effect_areas),
                    )

    def test_owner_picks_up_bag_through_actual_client_movement_handler(self):
        """Cover opcode12161's committed per-step area callback end to end."""
        import struct

        import test_enutrof_runtime as enutrof_fixture
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        helper = enutrof_fixture.EnutrofRuntimeTests()
        character, monster, fight, deck, rng = helper.fixture(actives=(2026,))
        fight = helper.cast(
            (character, monster, fight, deck, rng),
            2026,
            fight.actors[7].position,
        ).fight
        actor = fight.actors[7]
        self.assertEqual(fight.current.id, actor.id)
        bags = {
            row["uid"]: row
            for row in fight.native_effect_areas.values()
            if row["reference"] == 207 and row["owner_id"] == actor.id
        }
        self.assertTrue(bags)

        # Find a legal route that fits this turn's real MP budget. Avoid other
        # area cells so this step only tests entry into the selected bag.
        neighbors = {}
        for left, right in fight.edges:
            neighbors.setdefault(left, set()).add(right)
        occupied = {
            other.position
            for other in fight.actors.values()
            if other.id != actor.id and other.hp > 0
        }
        other_area_cells = {
            tuple(row["cell"])
            for row in fight.native_effect_areas.values()
            if row["uid"] not in bags
        }
        route_for = {}
        for bag in bags.values():
            destination = tuple(bag["cell"])
            queue = deque([(actor.position, ())])
            visited = {actor.position}
            while queue:
                cell, path = queue.popleft()
                if cell == destination:
                    route_for[bag["uid"]] = path
                    break
                if len(path) >= actor.mp:
                    continue
                for next_cell in sorted(neighbors.get(cell, ())):
                    if next_cell in visited or next_cell in occupied:
                        continue
                    if next_cell in other_area_cells and next_cell != destination:
                        continue
                    visited.add(next_cell)
                    queue.append((next_cell, (*path, next_cell)))
        reachable = [
            (len(path), uid, path)
            for uid, path in route_for.items()
            if path and len(path) <= actor.mp
        ]
        self.assertTrue(reachable, {uid: row["cell"] for uid, row in bags.items()})
        _, selected_uid, path = min(reachable)
        before_max_mp = actor.max_mp
        runtime = RuntimeMessages(fight)

        def area_provider(candidate, **boundary):
            return prepare_area_movement(
                character,
                {-7: monster},
                candidate,
                deck,
                rng=rng,
                **boundary,
            )

        body = struct.pack(">q", actor.id) + b"".join(
            struct.pack(">iih", *cell) for cell in path
        )
        packets, event = apply_client(
            runtime,
            actor.owner_id,
            body,
            lambda moved: b"",
            area_provider=area_provider,
        )
        after = runtime.fight
        self.assertEqual(event["path"], list(path))
        self.assertEqual(after.actors[actor.id].position, path[-1])
        self.assertEqual(after.actors[actor.id].max_mp, before_max_mp + 1)
        self.assertNotIn(selected_uid, after.native_effect_areas)
        # A bag is a Qs/Qq area manager, not a registered QI blocker. Make sure
        # retirement doesn't leave a spatial registration that can haunt cells.
        from wakfu_server.combat_qi_fight import current_registry

        for candidate in (after,):
            registry = current_registry(candidate)
            self.assertFalse(
                any(
                    slot is not None
                    and slot["identity"] == ["effect_area", selected_uid]
                    for slot in registry.slots
                )
            )
        self.assertTrue(
            all(uid in after.native_effect_areas for uid in bags if uid != selected_uid)
        )

        from wakfu_server.combat_effect_removal import _identity_fields

        removals = []
        for kind, payload in packets:
            if kind != 12613 or len(payload) < 19:
                continue
            # Byte 12 is cvX/eIK (execute=1, retain=0), not the native Qq
            # area type. Family 843 is the executable Qs.b retirement route.
            if struct.unpack_from(">i", payload, 13)[0] != 843 or payload[12] != 1:
                continue
            size = struct.unpack_from(">h", payload, 17)[0]
            if len(payload) != 19 + size:
                continue
            fields = _identity_fields(payload[19:])
            if fields.get(7) == selected_uid:
                removals.append(fields)
        self.assertEqual(len(removals), 1, packets)
        self.assertEqual(removals[0][3], 386191)
        self.assertEqual(removals[0][6], actor.id)


if __name__ == "__main__":
    unittest.main()
