"""Queued pre-fence work cannot cross birth homes or reach World after rejection."""
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from test_ecology_service_transport import service
from wakfu_server import ecology_mobs, monster_home_delivery as delivery, monster_wander


class BirthHomeDeliveryTests(unittest.TestCase):
    def test_long_displaced_native_route_is_planned_and_accepted_without_leaving_home_again(
        self,
    ):
        import random
        from protocol_codec import decode_body
        from wakfu_server.monster_home_paths import homing_path

        edges = [((x, 0, 0), (x - 1, 0, 0)) for x in range(1, 302)]
        edges.append(((300, 0, 0), (301, 0, 0)))
        indexed = monster_wander.edge_index(edges)
        before = dict(id=-1, ref=4, level=10, x=300, y=0, z=0)
        result = homing_path(
            [before],
            [dict(x=300, y=3, z=0)],
            indexed,
            11,
            lambda cell: 11 if cell[0] <= 0 else 22,
            min_steps=8,
            max_steps=8,
            rng=random.Random(17),
            map_id=(999999, (0,)),
        )
        self.assertIsNotNone(result)
        self.assertEqual(monster_wander.point(result["members"][0]), (292, 0, 0))
        self.assertEqual(decode_body("in", *result["packets"][0])["step_count"], 8)
        move = dict(
            group_id=17,
            expected_members=[before],
            moved_members=result["members"],
            packets=[[opcode, payload.hex()] for opcode, payload in result["packets"]],
        )
        row = dict(
            domain="mobs",
            payload=dict(kind="wander_bulk", scope=[999999, 0], moves=[move]),
        )
        with self.guards(edges):
            self.assertTrue(delivery.validate_proposal(object(), row))
            self.assertFalse(
                delivery.validate_proposal(
                    object(), self.row([(300, 0, 0), (301, 0, 0)])
                )
            )

    def row(self, path, *, flag=None, kind="wander_bulk"):
        before = dict(id=-1, ref=4, level=10, x=path[0][0], y=path[0][1], z=path[0][2])
        moved = dict(before, x=path[-1][0], y=path[-1][1], z=path[-1][2])
        import struct

        deltas = bytes(
            monster_wander.movement_packet(-1, a, b)[1][-1]
            for a, b in zip(path, path[1:])
        )
        body = struct.pack(">qiihB", -1, *path[0], len(deltas)) + deltas
        move = dict(
            group_id=17,
            expected_members=[before],
            moved_members=[moved],
            packets=[[13852, body.hex()]],
        )
        if flag:
            move[flag] = True
        payload = dict(
            kind=kind, scope=[999999, 0], world_epoch="birth-home", moves=[move]
        )
        if kind == "wander":
            payload.pop("moves")
            payload.update(move)
        return dict(
            id="queued-home", domain="mobs", world_epoch="birth-home", payload=payload
        )

    def guards(self, edges, *, radius=0):
        stack = ExitStack()
        stack.enter_context(patch.object(delivery, "_tracked_scope", return_value=True))
        stack.enter_context(patch.object(delivery, "_home", return_value=11))
        stack.enter_context(
            patch.object(delivery, "native_physical_radius", return_value=radius)
        )
        stack.enter_context(
            patch.object(
                delivery,
                "home_destination_allowed",
                side_effect=lambda _map, _home, cell, *, radii=(0,): cell[0]
                + max(radii)
                <= 0,
            )
        )
        stack.enter_context(
            patch.object(
                ecology_mobs, "_edges", return_value=monster_wander.edge_index(edges)
            )
        )
        return stack

    def test_old_roaming_and_escape_markers_cannot_leave_home(self):
        edges = [((0, 0, 0), (1, 0, 0)), ((0, 0, 0), (-1, 0, 0))]
        with self.guards(edges):
            for flag in (None, "dispersal", "overlap_escape"):
                with self.subTest(flag=flag):
                    self.assertFalse(
                        delivery.validate_proposal(
                            object(), self.row([(0, 0, 0), (1, 0, 0)], flag=flag)
                        )
                    )
                    self.assertTrue(
                        delivery.validate_proposal(
                            object(), self.row([(0, 0, 0), (-1, 0, 0)], flag=flag)
                        )
                    )
            self.assertFalse(
                delivery.validate_proposal(
                    object(), self.row([(0, 0, 0), (1, 0, 0)], kind="wander")
                )
            )

    def test_displaced_queue_can_only_get_closer_then_stay_home_on_native_edges(self):
        edges = [
            ((2, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (0, 0, 0)),
            ((2, 0, 0), (3, 0, 0)),
            ((3, 0, 0), (2, 0, 0)),
            ((0, 0, 0), (1, 0, 0)),
        ]
        with self.guards(edges):
            self.assertTrue(
                delivery.validate_proposal(
                    object(), self.row([(2, 0, 0), (1, 0, 0), (0, 0, 0)])
                )
            )
            self.assertFalse(
                delivery.validate_proposal(object(), self.row([(2, 0, 0), (3, 0, 0)]))
            )
            self.assertFalse(
                delivery.validate_proposal(
                    object(), self.row([(2, 0, 0), (1, 0, 0), (0, 0, 0), (1, 0, 0)])
                )
            )
        with self.guards([]):
            self.assertFalse(
                delivery.validate_proposal(object(), self.row([(0, 0, 0), (-1, 0, 0)]))
            )

    def test_homing_uses_whole_footprint_when_center_already_appears_inside(self):
        with self.guards([((0, 0, 0), (-1, 0, 0))], radius=1):
            self.assertTrue(
                delivery.validate_proposal(object(), self.row([(0, 0, 0), (-1, 0, 0)]))
            )

    def test_reproduction_and_bulk_reproduction_require_child_home(self):
        with self.guards([]):
            for x, allowed in ((-1, True), (1, False)):
                operation = dict(
                    kind="reproduction",
                    scope=[999999, 0],
                    ticket=dict(group_id=17),
                    expected_members=[dict(id=-1, ref=4, x=0, y=0, z=0)],
                    destination=[x, 0, 0],
                    child=dict(id=-2, ref=4, x=x, y=0, z=0),
                )
                row = dict(domain="mobs", payload=operation)
                self.assertEqual(delivery.validate_proposal(object(), row), allowed)
                self.assertEqual(
                    delivery.validate_proposal(
                        object(),
                        dict(
                            domain="mobs",
                            payload=dict(kind="lifecycle_bulk", operations=[operation]),
                        ),
                    ),
                    allowed,
                )

    def test_worker_acknowledges_rejected_old_work_without_sending_to_world(self):
        repository, client = Mock(spec=service.Repository), Mock()
        repository.store = object()
        worker = service.Worker(
            repository,
            client,
            {"mobs": lambda *_: []},
            proposal_validator=delivery.validate_proposal,
        )
        row = self.row([(0, 0, 0), (1, 0, 0)])
        with self.guards([((0, 0, 0), (1, 0, 0))]):
            result = worker.deliver([row])
        client.apply.assert_not_called()
        repository.acknowledge.assert_called_once_with(
            [dict(id=row["id"], status="stale")]
        )
        self.assertEqual(result, [dict(id=row["id"], status="stale")])
