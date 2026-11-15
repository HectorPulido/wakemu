"""World bulk commit retains independent group fences and native packet bounds.

Worker-only contracts now exercise production Rust kernels:
- mobs::tests::cleanup_filling_background_capacity_cannot_starve_wander
- mobs::tests::live_zone_cap_omits_blocked_birth_before_identity_allocation
- mobs::tests::small_proposal_budget_rotates_maps_instead_of_starving_later_scope
- mobs::tests::lifecycle_categories_rotate_without_consuming_wander_reservation
- mob_geometry::tests::cyclic_native_path_never_returns_roster_to_its_start
- mob_geometry::tests::visible_group_rotation_preserves_one_position_stride_and_reaches_the_end
- mob_geometry::tests::wander_batch_rejects_ninth_group_and_forty_first_member_without_partial_state
"""

from test_ecology_mobs_apply import prepared_movement_packet
import unittest
from contextlib import nullcontext
from copy import deepcopy
from unittest.mock import patch
import test_ecology_mobs_apply as fixtures
from wakfu_server import ecology_mobs, monster_wander, monster_maturation


class EcologyWanderBulkTests(unittest.TestCase):
    configuration = fixtures.EcologyMobsApplyTests.configuration

    def entry(self, identity):
        before = dict(id=-7000 - identity, ref=60, team=1, x=0, y=identity * 3, z=0)
        after = dict(before, x=1)
        opcode, body = prepared_movement_packet(
            before["id"], (0, identity * 3, 0), (1, identity * 3, 0)
        )
        return dict(
            group_id=identity,
            expected_members=[before],
            moved_members=[after],
            packets=[[opcode, body.hex()]],
        )

    def apply_bulk(
        self,
        entries,
        *,
        statuses=None,
        excluded=(),
        fail_ids=(),
        habitat=None,
        native_habitat=False
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
        ), patch.dict(monster_maturation.STAGES, {60: [dict(family_id=1)]}), (
            nullcontext()
            if native_habitat
            else patch(
                "wakfu_server.ecology_mobs._native_habitat_paths_allowed",
                side_effect=lambda scope, paths: all(
                    (habitat or (lambda *_args, **_kwargs: True))(*scope, cell)
                    for path in paths.values()
                    for cell in path
                ),
            )
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

    def test_bulk_rejects_group_count_beyond_eight_before_moving(self):
        with self.assertRaises(ValueError):
            self.apply_bulk([self.entry(i) for i in range(1, 10)])

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

    def test_native_habitat_batch_rejects_intermediate_cell_and_keeps_healthy_group(
        self,
    ):
        from test_monster_habitat_cells import native_habitat_sources

        first, second = self.entry(1), self.entry(2)
        first["moved_members"][0]["x"] = 2
        opcode, encoded = first["packets"][0]
        body = bytes.fromhex(encoded)
        # Two explicit eastward steps; only the endpoint has a native surface.
        first["packets"] = [[opcode, (body[:18] + bytes([2]) + body[19:] * 2).hex()]]
        with native_habitat_sources(1134, [(2, 3, 0), (1, 6, 0)]):
            result, groups, world = self.apply_bulk(
                [first, second], native_habitat=True
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
