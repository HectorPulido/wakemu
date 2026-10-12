"""Bulk wandering retains independent group fences and bounded native packets."""
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_ecology_mobs_apply as fixtures
from wakfu_server import ecology_mobs, monster_wander, monster_maturation


class EcologyWanderBulkTests(unittest.TestCase):
    configuration = fixtures.EcologyMobsApplyTests.configuration

    def entry(self, identity):
        before = dict(id=-7000 - identity, ref=60, team=1, x=0, y=identity * 3, z=0)
        after = dict(before, x=1)
        opcode, body = monster_wander.movement_packet(
            before["id"], (0, identity * 3, 0), (1, identity * 3, 0)
        )
        return dict(
            group_id=identity,
            expected_members=[before],
            moved_members=[after],
            packets=[[opcode, body.hex()]],
        )

    def apply_bulk(
        self, entries, *, statuses=None, excluded=(), fail_ids=(), habitat=None
    ):
        statuses = statuses or {}
        groups = fixtures.FakeGroups(
            [
                dict(
                    group_id=e["group_id"],
                    status=statuses.get(e["group_id"], "available"),
                    members=e["expected_members"],
                )
                for e in entries
            ]
        )

        def move(key, expected, replacement):
            groups.move_calls.append((key, expected, replacement))
            return key[-1] not in fail_ids

        groups.move_members = move
        world = fixtures.FakeWorld(
            [dict(id=9001, map_id=1134, instance_id=0, x=20, y=20, z=0)]
        )
        world.batches = []
        world.emit_location_batch = lambda *args: world.batches.append(args)
        proposal = dict(
            kind="wander_bulk",
            world_epoch="boot-a",
            scope=[1134, 0],
            configuration=self.configuration,
            moves=entries,
        )
        with patch.object(
            monster_wander, "policy", return_value=self.configuration
        ), patch.dict(monster_maturation.STAGES, {60: [dict(family_id=1)]}), patch(
            "wakfu_server.ecology_mobs.habitat_destination_allowed",
            side_effect=habitat or (lambda *_args, **_kwargs: True),
        ):
            result = ecology_mobs.apply(
                object(),
                groups,
                fixtures.FakeHarvests(excluded),
                world,
                proposal,
                world_epoch="boot-a",
            )
        return result, groups, world

    def test_fighting_harvesting_and_failed_cas_do_not_block_healthy_group(self):
        entries = [self.entry(i) for i in range(1, 5)]
        result, groups, world = self.apply_bulk(
            entries, statuses={1: "fighting"}, excluded={-7002}, fail_ids={3}
        )
        self.assertEqual([call[0][-1] for call in groups.move_calls], [3, 4])
        self.assertEqual(len(world.batches), 1)
        self.assertEqual(world.emitted, [])

    def test_healthy_groups_emit_one_batch_and_stale_epoch_emits_nothing(self):
        result, groups, world = self.apply_bulk([self.entry(1), self.entry(2)])
        self.assertEqual(len(groups.move_calls), 2)
        self.assertEqual(len(world.batches), 1)
        proposal = dict(
            kind="wander_bulk",
            world_epoch="old",
            scope=[1134, 0],
            configuration=self.configuration,
            moves=[self.entry(1)],
        )
        result = ecology_mobs.apply(
            object(),
            groups,
            fixtures.FakeHarvests(),
            world,
            proposal,
            world_epoch="new",
        )
        self.assertEqual(result["status"], "stale_epoch")
        self.assertEqual(len(world.batches), 1)

    def test_cyclic_native_walk_never_returns_group_to_start(self):
        class Rng:
            def randint(self, *_):
                return 2

            def choice(self, values):
                return values[0]

        member = dict(id=-1, ref=60, x=0, y=0, z=0)
        result = monster_wander.plan_path(
            [member],
            [dict(x=0, y=2, z=0)],
            [((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (0, 0, 0))],
            min_steps=2,
            max_steps=2,
            rng=Rng(),
        )
        if result is not None:
            self.assertNotEqual(
                (
                    result["members"][0]["x"],
                    result["members"][0]["y"],
                    result["members"][0]["z"],
                ),
                (0, 0, 0),
            )

    def test_bulk_rejects_group_count_beyond_eight_before_moving(self):
        with self.assertRaises(ValueError):
            self.apply_bulk([self.entry(i) for i in range(1, 10)])

    def prepare(
        self,
        *,
        tick=0,
        cleanup=(),
        limit=2,
        scopes=((1134, 0),),
        groups_count=12,
        members_per_group=1,
        publications=False,
        reproduction_policy=None,
        reproduction_pending=(),
    ):
        from contextlib import ExitStack
        from unittest.mock import MagicMock
        from wakfu_server import monster_maturation, monster_reproduction

        groups = [
            dict(
                group_id=i,
                status="available",
                members=[
                    self.entry((i - 1) * members_per_group + j + 1)["expected_members"][
                        0
                    ]
                    for j in range(members_per_group)
                ],
            )
            for i in range(1, groups_count + 1)
        ]
        store = MagicMock()
        db = store.connection.return_value.__enter__.return_value
        db.execute.side_effect = (
            lambda sql, *_: groups if "FROM combat_groups" in sql else []
        )
        snapshot = dict(
            world_epoch="boot-a",
            players=[
                dict(
                    id=i * groups_count + group_id,
                    map_id=scope[0],
                    instance_id=scope[1],
                    x=2,
                    y=group_id * members_per_group * 3,
                    z=0,
                )
                for i, scope in enumerate(scopes)
                for group_id in range(1, groups_count + 1)
            ],
            excluded_ids=[],
            locations=[list(scope) for scope in scopes],
            now_ms=1000,
            domain_planning_tick=tick,
            allow_wander=True,
        )

        def path(members, *_args, **_kwargs):
            moved = [dict(member, x=member["x"] + 1) for member in members]
            return dict(
                members=moved,
                packets=[
                    monster_wander.movement_packet(
                        before["id"],
                        monster_wander.point(before),
                        monster_wander.point(after),
                    )
                    for before, after in zip(members, moved)
                ],
            )

        with ExitStack() as patches:
            patches.enter_context(
                patch(
                    "wakfu_server.monster_life_plans.attach",
                    side_effect=lambda store, scope, kind, tickets, policy: tickets,
                )
            )
            for domain in (monster_maturation, monster_reproduction):
                policy = (
                    reproduction_policy
                    if domain is monster_reproduction
                    and reproduction_policy is not None
                    else {}
                )
                pending = reproduction_pending if domain is monster_reproduction else []
                patches.enter_context(
                    patch.object(domain, "policy", return_value=policy)
                )
                patches.enter_context(
                    patch.object(domain, "pending", return_value=pending)
                )
                patches.enter_context(
                    patch.object(
                        domain,
                        "unpublished",
                        return_value=[{"group_id": 1}] if publications else [],
                    )
                )
                patches.enter_context(patch.object(domain, "observe"))
            patches.enter_context(
                patch.object(
                    monster_reproduction, "dungeon_population", return_value=False
                )
            )
            patches.enter_context(
                patch(
                    "wakfu_server.monster_population_cleanup.prepare",
                    return_value=list(cleanup),
                )
            )
            patches.enter_context(
                patch.object(monster_wander, "policy", return_value=self.configuration)
            )
            patches.enter_context(
                patch.object(monster_wander, "plan_group_path", side_effect=path)
            )
            patches.enter_context(
                patch.object(ecology_mobs, "_edges", return_value=(set(), {}))
            )
            patches.enter_context(
                patch.object(ecology_mobs.random, "random", return_value=0)
            )
            return ecology_mobs.prepare(store, snapshot, limit=limit)

    def test_cleanup_filling_background_reservation_cannot_starve_wander(self):
        cleanup = dict(kind="cleanup_unassigned", world_epoch="boot-a", scope=[1134, 0])
        plans = self.prepare(cleanup=[cleanup])
        self.assertTrue(any(plan["kind"] == "wander_bulk" for plan in plans))
        self.assertLessEqual(len(plans), 2)

    def test_known_zone_member_cap_does_not_enqueue_blocked_reproduction_ticket(self):
        ticket = dict(
            group_id=1,
            monster_id=-7001,
            reference=60,
            cycle=1,
            map_id=1134,
            instance_id=0,
        )
        policy = dict(
            interval_ms=1000,
            birth_probability=1.0,
            birth_stage_decay=1.0,
            new_group_probability=0.0,
            max_members=8,
            max_zone_members=12,
            max_zone_groups=100,
        )
        plans = self.prepare(
            tick=1,
            limit=2,
            reproduction_policy=policy,
            reproduction_pending=[ticket],
        )
        self.assertFalse(any(plan["kind"] == "reproduction" for plan in plans))
        self.assertTrue(any(plan["kind"] == "wander_bulk" for plan in plans))

    def test_rotating_group_start_allows_newer_groups_to_move(self):
        first = next(
            plan
            for plan in self.prepare(tick=0, limit=1)
            if plan["kind"] == "wander_bulk"
        )
        second = next(
            plan
            for plan in self.prepare(tick=1, limit=1)
            if plan["kind"] == "wander_bulk"
        )
        self.assertLessEqual(len(first["moves"]), 8)
        self.assertTrue(
            {9, 10, 11, 12}.issubset({group["group_id"] for group in second["moves"]})
        )

    def test_small_proposal_budget_rotates_maps_instead_of_starving_later_scope(self):
        scopes = ((1134, 0), (1135, 0))
        first = self.prepare(tick=0, limit=1, scopes=scopes)
        second = self.prepare(tick=1, limit=1, scopes=scopes)
        self.assertEqual(first[0]["scope"], [1134, 0])
        self.assertEqual(second[0]["scope"], [1135, 0])

    def test_lifecycle_categories_rotate_without_consuming_wander_reservation(self):
        first = self.prepare(tick=0, publications=True)
        second = self.prepare(tick=1, publications=True)
        self.assertEqual(first[0]["kind"], "publish_maturation")
        self.assertEqual(second[0]["kind"], "publish_reproduction")
        self.assertTrue(any(plan["kind"] == "wander_bulk" for plan in first))
        self.assertTrue(any(plan["kind"] == "wander_bulk" for plan in second))

    def test_bulk_time_budget_keeps_first_atomic_move_and_skips_remaining(self):
        with patch.object(
            ecology_mobs.time, "monotonic", side_effect=[0, 0, 0.026, 0.026]
        ):
            result, groups, world = self.apply_bulk([self.entry(1), self.entry(2)])
        self.assertEqual(len(groups.move_calls), 1)
        self.assertEqual(len(world.batches), 1)
        self.assertEqual(result["skip_reason"], "budget")

    def test_bulk_rejects_more_than_forty_moving_members(self):
        entries = [self.entry(i) for i in range(1, 42)]
        oversized = dict(
            group_id=1,
            expected_members=[entry["expected_members"][0] for entry in entries],
            moved_members=[entry["moved_members"][0] for entry in entries],
            packets=[entry["packets"][0] for entry in entries],
        )
        result, groups, world = self.apply_bulk([oversized])
        self.assertEqual(result["status"], "stale_group")
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.batches, [])

    def test_invalid_native_habitat_skips_only_affected_group(self):
        def allowed(_map, _instance, cell, **_kwargs):
            return cell[1] != 3

        result, groups, world = self.apply_bulk(
            [self.entry(1), self.entry(2)], habitat=allowed
        )
        self.assertEqual([call[0][-1] for call in groups.move_calls], [2])
        self.assertEqual(result["applied_groups"], 1)
        self.assertEqual(result["skipped_groups"], 1)
        self.assertEqual(len(world.batches), 1)

    def test_bulk_semantic_identity_retains_first_path_and_isolates_roster_and_epoch(
        self,
    ):
        from wakfu_server.ecology.proposal_identity import identity
        from wakfu_server.ecology.protocol import proposal

        payload = dict(
            kind="wander_bulk",
            scope=[1134, 0],
            configuration=self.configuration,
            moves=[self.entry(1)],
        )
        first = identity(proposal("mobs", payload, "boot"))
        changed_path = deepcopy(payload)
        changed_path["moves"][0]["packets"] = [[13852, "changed"]]
        self.assertEqual(first, identity(proposal("mobs", changed_path, "boot")))
        changed_roster = deepcopy(payload)
        changed_roster["moves"][0]["expected_members"][0]["x"] = 8
        newer = identity(proposal("mobs", changed_roster, "boot"))
        self.assertEqual(first[0], newer[0])
        self.assertNotEqual(first[1], newer[1])
        self.assertNotEqual(
            first[0], identity(proposal("mobs", payload, "otherboot"))[0]
        )

    def test_bulk_wire_envelope_above_224_kib_is_rejected_before_locks(self):
        groups = fixtures.FakeGroups()
        world = fixtures.FakeWorld([])
        oversized = dict(
            kind="wander_bulk",
            world_epoch="boot",
            scope=[1134, 0],
            moves=[self.entry(1)],
            configuration=self.configuration,
            padding="x" * (224 * 1024),
        )
        with self.assertRaises(ValueError):
            ecology_mobs.apply(
                object(),
                groups,
                fixtures.FakeHarvests(),
                world,
                oversized,
                world_epoch="boot",
            )
        self.assertEqual(groups.lock.entered, 0)

    def test_five_thousand_members_remain_bounded_and_last_groups_receive_turn(self):
        for tick, expected in ((0, set(range(1, 9))), (124, set(range(993, 1001)))):
            with self.subTest(tick=tick):
                plans = self.prepare(
                    tick=tick, limit=1, groups_count=1000, members_per_group=5
                )
                self.assertEqual(len(plans), 1)
                moves = plans[0]["moves"]
                self.assertEqual({move["group_id"] for move in moves}, expected)
                self.assertEqual(sum(len(move["moved_members"]) for move in moves), 40)
