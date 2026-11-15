"""World revalidates external lifecycle proposals under fresh live fences.

Clock observation and policy selection moved to Rust lifecycle_contract; these
cases retain the original claim/harvest/departure/publication acceptance checks.
"""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import ExitStack

from wakfu_server import ecology_mobs, monster_maturation, monster_reproduction


class Fence:
    def __init__(self):
        self.lock = threading.RLock()
        self.held = False

    def __enter__(self):
        self.lock.acquire()
        self.held = True
        return self

    def __exit__(self, *_):
        self.held = False
        self.lock.release()


class WorldCoordinationFixture:
    kind = "maturation"

    def setUp(self):
        self.domain = (
            monster_maturation if self.kind == "maturation" else monster_reproduction
        )
        self.groups = SimpleNamespace(lock=Fence())
        self.harvests = SimpleNamespace(lock=Fence(), targets=set())
        self.players = [dict(id=7, map_id=1, instance_id=0, x=20, y=20, z=0)]
        self.world = SimpleNamespace(
            snapshot=lambda: list(self.players), emit_location=Mock()
        )
        self.row = dict(group_id=3, status="available", members=[dict(id=-10)])
        self.configuration = dict(interval_ms=60000)
        self.proposal = dict(
            kind=self.kind,
            scope=[1, 0],
            world_epoch="worker",
            expected_members=[dict(id=-10)],
            configuration=self.configuration,
            ticket={},
            draw=0.0,
            group_draw=0.0,
        )

    def apply(self, proposal=None):
        return ecology_mobs.apply(
            object(),
            self.groups,
            self.harvests,
            self.world,
            proposal or self.proposal,
            world_epoch="worker",
        )

    def patches(self):
        patches = ExitStack()
        self.addCleanup(patches.close)
        self.policy = patches.enter_context(
            patch.object(self.domain, "policy", return_value=self.configuration)
        )
        self.attempt = patches.enter_context(
            patch.object(
                self.domain,
                "attempt",
                return_value=dict(group_id=3, child_group_id=3, duplicate=False),
            )
        )
        self.unpublished = patches.enter_context(
            patch.object(
                self.domain, "unpublished", side_effect=lambda *a, **k: [dict(self.row)]
            )
        )
        self.acknowledge = patches.enter_context(
            patch.object(self.domain, "acknowledge")
        )
        patches.enter_context(
            patch.object(ecology_mobs, "_edges", return_value=(None, {}))
        )
        patches.enter_context(
            patch(
                "wakfu_server.combat_monster_world.remove_message",
                return_value=(12002, b"remove"),
            )
        )
        patches.enter_context(
            patch(
                "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
            )
        )

    def test_departure_before_attempt_pauses_growth(self):
        self.patches()
        # This proposal was prepared while occupied; World sees the later exit.
        self.players.clear()
        self.assertEqual(self.apply(), dict(status="absent"))
        self.attempt.assert_not_called()
        self.world.emit_location.assert_not_called()

    def test_harvest_and_player_changes_between_operations_refresh_attempt(self):
        self.patches()
        snapshots = []

        def current_snapshot():
            self.assertTrue(self.groups.lock.held)
            self.assertTrue(self.harvests.lock.held)
            snapshots.append(list(self.players))
            return list(self.players)

        self.world.snapshot = current_snapshot
        # External preparation cannot authorize a later harvesting mutation.
        self.harvests.targets.add(-10)
        self.assertEqual(self.apply(), dict(status="harvesting"))
        self.assertEqual(snapshots, [self.players])
        self.attempt.assert_not_called()
        self.harvests.targets.clear()
        self.assertEqual(self.apply(), dict(status="applied"))
        self.assertTrue(self.attempt.call_args.kwargs["present"])
        self.assertEqual(self.attempt.call_args.kwargs["excluded_ids"], set())

    def test_claim_after_outbox_enumeration_cannot_publish_stale_available_group(self):
        self.patches()
        proposal = dict(self.proposal, kind="publish_" + self.kind, group_id=3)
        # The external proposal describes availability before this claim.
        self.row["status"] = "fighting"
        self.assertEqual(self.apply(proposal), dict(status="applied"))
        self.unpublished.assert_called_once()
        self.assertEqual(self.unpublished.call_args.kwargs, dict(group_id=3))
        self.acknowledge.assert_not_called()
        self.world.emit_location.assert_not_called()

    def test_removal_spawn_and_acknowledgment_share_publication_fence(self):
        self.patches()
        order = []

        def emit(*args):
            self.assertTrue(self.groups.lock.held)
            self.assertTrue(self.harvests.lock.held)
            order.append(args[2])

        def acknowledge(*_):
            self.assertTrue(self.groups.lock.held)
            self.assertTrue(self.harvests.lock.held)
            order.append("ack")

        self.world.emit_location = emit
        self.acknowledge.side_effect = acknowledge
        self.apply(dict(self.proposal, kind="publish_" + self.kind, group_id=3))
        self.assertEqual(order, [12002, 12608, "ack"])


class MaturationCoordinationTests(WorldCoordinationFixture, unittest.TestCase):
    pass
